"""Bases grandes baixadas sob demanda (hoje: o CNEFE completo), com cache local e conferência de integridade.

>>> import nini_datagen as dg
>>> dg.datasets.download("cnefe")       # doctest: +SKIP  (~55 MB, uma vez só)
>>> dg.address(10, source="full")         # doctest: +SKIP

O arquivo fica em ``platformdirs.user_cache_dir("nini-datagen")`` (ou na pasta da variável ``NINI_DATAGEN_CACHE``),
numa subpasta por versão (``cnefe-v1``). O download é conferido pelo SHA-256 do manifesto antes de extrair, e a
extração vai para uma pasta temporária renomeada no fim: um download interrompido nunca deixa uma base pela metade.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

__all__ = ["Dataset", "DatasetError", "cache_dir", "download", "get", "path"]

_DONE = ".complete"  # marcador: a extração terminou (o conteúdo é o SHA-256 do zip)


class DatasetError(RuntimeError):
    """Base indisponível: não publicada, download corrompido ou formato incompatível com esta versão."""


@dataclass(frozen=True)
class Dataset:
    name: str
    description: str
    version: int
    format: int
    url: str
    sha256: str
    size: int

    @property
    def folder(self) -> str:
        return f"{self.name}-v{self.version}"


@cache
def _manifest() -> dict[str, Dataset]:
    raw = json.loads((Path(__file__).with_name("manifest.json")).read_text(encoding="utf-8"))
    return {k: Dataset(name=k, **v) for k, v in raw.items()}


def get(name: str) -> Dataset:
    """Descrição da base ``name`` no manifesto deste pacote."""
    m = _manifest()
    if name not in m:
        raise ValueError(f"base desconhecida: {name!r}; disponíveis: {', '.join(sorted(m))}")
    return m[name]


def cache_dir() -> Path:
    """Pasta do cache (``NINI_DATAGEN_CACHE`` ou a pasta de cache do usuário no sistema)."""
    env = os.environ.get("NINI_DATAGEN_CACHE")
    if env:
        return Path(env)
    import platformdirs  # noqa: PLC0415

    return Path(platformdirs.user_cache_dir("nini-datagen"))


def path(name: str) -> Path | None:
    """Pasta da base já baixada e completa, ou None."""
    d = cache_dir() / get(name).folder
    return d if (d / _DONE).is_file() else None


def _fetch(url: str, dest: Path) -> str:
    """Baixa ``url`` em ``dest`` e devolve o SHA-256 (calculado durante o download)."""
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as fh:
        while chunk := resp.read(1 << 20):
            h.update(chunk)
            fh.write(chunk)
    return h.hexdigest()


def download(name: str = "cnefe", *, force: bool = False) -> Path:
    """Baixa (se preciso) e devolve a pasta da base ``name``. ``force=True`` baixa de novo."""
    ds = get(name)
    if not ds.sha256:
        raise DatasetError(f"a base {name!r} ainda não foi publicada nesta versão do pacote")
    done = path(name)
    if done is not None and not force:
        return done
    root = cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    final = root / ds.folder
    with tempfile.TemporaryDirectory(dir=root, prefix=f".{ds.folder}-") as tmp:
        zpath = Path(tmp) / "base.zip"
        digest = _fetch(ds.url, zpath)
        if digest != ds.sha256:
            raise DatasetError(f"download de {name!r} corrompido: SHA-256 {digest}, esperado {ds.sha256}")
        out = Path(tmp) / "out"
        with zipfile.ZipFile(zpath) as z:
            for member in z.namelist():  # nada fora da pasta de destino (zip com "../")
                if Path(member).is_absolute() or ".." in Path(member).parts:
                    raise DatasetError(f"arquivo suspeito dentro do zip: {member!r}")
            z.extractall(out)
        (out / _DONE).write_text(digest, encoding="utf-8")
        if final.exists():
            shutil.rmtree(final)
        out.rename(final)
    return final
