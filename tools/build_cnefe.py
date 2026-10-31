"""build_cnefe.py -- gera as bases de endereço do pacote a partir dos dados do MVP (fake-data).

    uv run python tools/build_cnefe.py --mvp ../fake-data          # tudo: municípios, base leve e base completa
    uv run python tools/build_cnefe.py --mvp ../fake-data --lite-coverage 0.02

Entrada (pasta do MVP):
  data/municipios.parquet                       (fetch_ibge.py: id, nome, uf, populacao)
  data/cnefe/{enderecos,logradouros,bairros}.parquet
                                                (compactar_cnefe.py, base completa: cep, municipio_id, logradouro_id,
                                                 bairro_id, num_min, num_max, lat_eN, lon_eN, enderecos)
Saída:
  src/nini_datagen/locales/pt_BR/data/municipalities.tsv     municípios (vai no pacote)
  src/nini_datagen/locales/pt_BR/data/cnefe_lite/            base leve (vai no pacote): cobertura de 1% dos
                                                             endereços de cada município (no mínimo 3 trechos), sem
                                                             faixa de números, coordenadas com 3 casas
  dist/cnefe-full-v1.zip                                     base completa (vai no release do GitHub)
  src/nini_datagen/datasets/manifest.json                    SHA-256 e tamanho do zip atualizados

Depois: conferir as amostras, commitar os arquivos do pacote e publicar o zip no release ``data-cnefe-v1``:

    gh release create data-cnefe-v1 dist/cnefe-full-v1.zip --title "CNEFE completo v1" --notes "IBGE, CNEFE 2022"
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
PKG_DATA = ROOT / "src" / "nini_datagen" / "locales" / "pt_BR" / "data"
MANIFEST = ROOT / "src" / "nini_datagen" / "datasets" / "manifest.json"
DIST = ROOT / "dist"
FORMAT = 1
VERSION = 1


def mb(p: Path) -> float:
    return p.stat().st_size / 1e6


def municipalities(mvp: Path) -> pl.DataFrame:
    df = pl.read_parquet(mvp / "data" / "municipios.parquet")
    out = df.select(
        pl.col("id").cast(pl.Int32).alias("ibge_id"),
        pl.col("nome").alias("name"),
        pl.col("uf"),
        pl.col("populacao").fill_null(0).cast(pl.Int64).alias("population"),
    ).sort("ibge_id")
    if out["name"].str.contains("\t").any():
        raise SystemExit("nome de município com tabulação: o TSV quebraria")
    path = PKG_DATA / "municipalities.tsv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE)
        w.writerow(out.columns)
        w.writerows(out.iter_rows())
    print(f"{path.relative_to(ROOT)}: {out.height:,} municípios, {mb(path):.2f} MB")
    return out


def read_full(mvp: Path) -> tuple[pl.DataFrame, pl.Series, pl.Series, int]:
    """Base completa do MVP com os nomes de colunas do pacote; devolve também as casas decimais das coordenadas."""
    d = mvp / "data" / "cnefe"
    if not (d / "enderecos.parquet").exists():
        raise SystemExit(f"{d} não existe: rode `uv run python compactar_cnefe.py` na pasta do MVP antes")
    e = pl.read_parquet(d / "enderecos.parquet")
    lat = next((c for c in e.columns if c.startswith("lat_e")), None)
    decimals = int(lat[5:]) if lat else 0
    ren = {"municipio_id": "city_id", "logradouro_id": "street", "bairro_id": "district", "num_min": "number_min",
           "num_max": "number_max", "enderecos": "weight"}  # fmt: skip
    if lat:
        ren |= {lat: "lat", "lon" + lat[3:]: "lon"}
    e = e.rename({k: v for k, v in ren.items() if k in e.columns})
    streets = pl.read_parquet(d / "logradouros.parquet")["nome"].alias("name")
    districts = pl.read_parquet(d / "bairros.parquet")["nome"].alias("name")
    return e, streets, districts, decimals


def lite(e: pl.DataFrame, streets: pl.Series, districts: pl.Series, decimals: int, *, coverage: float, min_rows: int):
    """Em cada município, os trechos mais povoados até somar ``coverage`` dos endereços (no mínimo ``min_rows``);
    sem faixa de números; coordenadas com 3 casas; ids de nomes renumerados só com os que sobraram."""
    e = (
        e.sort(["city_id", "weight", "cep"], descending=[False, True, False])
        .with_columns(
            cum=pl.col("weight").cast(pl.Int64).cum_sum().over("city_id"),
            tot=pl.col("weight").cast(pl.Int64).sum().over("city_id"),
            rank=pl.int_range(pl.len()).over("city_id"),
        )
        .filter(((pl.col("cum") - pl.col("weight")) < coverage * pl.col("tot")) | (pl.col("rank") < min_rows))
        # os pesos dos trechos que ficaram são reescalados para o município manter o total de endereços da base
        # completa: sem isso, cidades pequenas (que ficam com quase tudo por causa do mínimo de trechos) pesariam
        # demais e as grandes de menos (SP saía com 15% dos endereços em vez de ~22%)
        .with_columns(
            # em Float64: weight * tot em UInt32 estoura nas cidades grandes (SP saía com peso de menos)
            (
                pl.col("weight").cast(pl.Float64)
                * pl.col("tot").cast(pl.Float64)
                / pl.col("weight").cast(pl.Float64).sum().over("city_id")
            )
            .round()
            .clip(1, None)
            .cast(pl.UInt32)
            .alias("weight")
        )
        .drop("cum", "tot", "rank", "number_min", "number_max", strict=False)
        .sort("cep", "city_id")
    )
    if decimals > 3:
        k = 10 ** (decimals - 3)
        e = e.with_columns((pl.col(c).cast(pl.Float64) / k).round().cast(pl.Int32) for c in ("lat", "lon"))
    used_s = e["street"].unique().sort()
    used_d = e["district"].drop_nulls().unique().sort()
    e = e.with_columns(
        pl.col("street").replace_strict(used_s, pl.int_range(len(used_s), eager=True), return_dtype=pl.UInt32),
        pl.col("district").replace_strict(used_d, pl.int_range(len(used_d), eager=True), default=None,
                                          return_dtype=pl.UInt32),
    )  # fmt: skip
    return e, streets.gather(used_s), districts.gather(used_d), min(decimals, 3)


def write(folder: Path, e: pl.DataFrame, streets: pl.Series, districts: pl.Series, decimals: int) -> float:
    """Grava a pasta no formato do pacote (Parquet zstd com codificação delta, como o compactar_cnefe do MVP)."""
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    cols = ["cep", "city_id", "street", "district", "number_min", "number_max", "lat", "lon", "weight"]
    types = {"cep": pl.UInt32, "city_id": pl.Int32, "street": pl.UInt32, "district": pl.UInt32, "number_min": pl.Int32,
             "number_max": pl.Int32, "lat": pl.Int32, "lon": pl.Int32, "weight": pl.UInt32}  # fmt: skip
    e = e.select(pl.col(c).cast(types[c]) for c in cols if c in e.columns)
    frames = {"addresses": e, "streets": streets.to_frame("name"), "districts": districts.to_frame("name")}
    for name, df in frames.items():
        tbl = df.to_arrow()
        tbl = tbl.cast(pa.schema([pa.field(f.name, pa.string() if not pa.types.is_integer(f.type) else f.type)
                                  for f in tbl.schema]))  # fmt: skip
        enc = {f.name: "DELTA_BINARY_PACKED" if pa.types.is_integer(f.type) else "DELTA_BYTE_ARRAY" for f in tbl.schema}
        path = folder / f"{name}.parquet"
        pq.write_table(tbl, path, compression="zstd", compression_level=22, use_dictionary=False,
                       column_encoding=enc, write_statistics=False, row_group_size=1 << 20)  # fmt: skip
        back = pl.read_parquet(path)
        if back.height != df.height or not all(back[c].equals(df[c].cast(back[c].dtype)) for c in df.columns):
            raise SystemExit(f"{path}: o arquivo lido de volta não confere com o gravado")
    meta = {"format": FORMAT, "version": VERSION, "coord_scale": 10**decimals if "lat" in e.columns else 1,
            "rows": e.height, "source": "IBGE, CNEFE, Censo Demográfico 2022"}  # fmt: skip
    (folder / "format.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return sum(mb(p) for p in folder.iterdir())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mvp", type=Path, required=True, help="pasta do MVP (fake-data)")
    ap.add_argument("--lite-coverage", type=float, default=0.01)
    ap.add_argument("--lite-min-rows", type=int, default=3)
    ap.add_argument("--skip-full", action="store_true", help="não gera o zip da base completa")
    a = ap.parse_args()

    mun = municipalities(a.mvp)
    e, streets, districts, decimals = read_full(a.mvp)
    missing = set(e["city_id"].unique().to_list()) - set(mun["ibge_id"].to_list())
    if missing:
        raise SystemExit(f"{len(missing)} municípios do CNEFE não estão em municipios.parquet: {sorted(missing)[:5]}")
    total = int(e["weight"].sum())
    without = mun.filter(~pl.col("ibge_id").is_in(e["city_id"].unique().implode()))
    if without.height:  # municípios criados depois do Censo 2022 não têm endereço no CNEFE
        names = ", ".join(f"{r['name']}/{r['uf']}" for r in without.head(10).iter_rows(named=True))
        print(f"aviso: {without.height} município(s) sem endereço no CNEFE: {names}")

    le, ls, ld, ldec = lite(e, streets, districts, decimals, coverage=a.lite_coverage, min_rows=a.lite_min_rows)
    size = write(PKG_DATA / "cnefe_lite", le, ls, ld, ldec)
    uf = mun.select("ibge_id", "uf")
    share = (
        le.join(uf, left_on="city_id", right_on="ibge_id").group_by("uf").agg(lite=pl.col("weight").sum())
        .join(e.join(uf, left_on="city_id", right_on="ibge_id").group_by("uf").agg(full=pl.col("weight").sum()),
              on="uf")
        .with_columns(pl.col("lite") / pl.col("lite").sum(), pl.col("full") / pl.col("full").sum())
        .sort("full", descending=True)
    )  # fmt: skip
    print(
        f"cnefe_lite: {size:.2f} MB | {le.height:,} trechos, {len(ls):,} ruas, {len(ld):,} bairros | "
        f"{le['city_id'].n_unique():,} municípios | peso total {int(le['weight'].sum()) / total:.3f} do completo"
    )
    print("  UFs (leve / completa): " + ", ".join(f"{r[0]} {r[1]:.1%}/{r[2]:.1%}" for r in share.head(6).iter_rows()))

    if a.skip_full:
        return
    folder = DIST / f"cnefe-full-v{VERSION}"
    size = write(folder, e.sort("cep", "city_id"), streets, districts, decimals)
    zpath = DIST / f"cnefe-full-v{VERSION}.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED) as z:  # o Parquet já vem comprimido
        for p in sorted(folder.iterdir()):
            z.write(p, p.name)
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    m["cnefe"].update(sha256=digest, size=zpath.stat().st_size, version=VERSION, format=FORMAT)
    MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"{zpath.relative_to(ROOT)}: {mb(zpath):.1f} MB ({size:.1f} MB descompactado) | {e.height:,} trechos | "
        f"sha256 {digest[:16]}... gravado no manifesto"
    )


if __name__ == "__main__":
    main()
