"""Interface C do Arrow sem o pyarrow (`core.arrow_c`): exportar buffers para o Polars e ler colunas dele."""

from __future__ import annotations

import gc
import subprocess
import sys
import textwrap

import numpy as np
import polars as pl

from nini_datagen.core import arrow_c
from nini_datagen.core.arrow import bits_to_series, primitive_to_series, string_view_buffers, views_to_series
from nini_datagen.core.memory import POOL_MIN_BYTES, empty, pool_stats

from .test_views import STRINGS, make_views


def test_export_keeps_buffers_until_series_dies() -> None:
    gc.collect()
    before = pool_stats()["in_use"]
    n = POOL_MIN_BYTES // 8
    values = empty(n, np.int64)
    values[:] = np.arange(n)
    validity = np.full(-(-n // 64), np.uint64(0xFFFFFFFFFFFFFFFF))
    validity[0] = np.uint64(0xFFFFFFFFFFFFFFFE)  # linha 0 nula
    s = primitive_to_series(values, "x", validity)
    del values
    gc.collect()
    assert pool_stats()["in_use"] > before  # o Polars ainda segura o bloco
    assert s.null_count() == 1
    assert s[0] is None
    assert s[n - 1] == n - 1
    assert s.sum() == n * (n - 1) // 2
    del s
    gc.collect()
    assert pool_stats()["in_use"] == before  # o release do Polars devolveu o bloco
    assert not arrow_c._live


def test_strings_with_nulls_and_many_buffers() -> None:
    v1, d1 = make_views(STRINGS)
    v2, d2 = make_views(STRINGS[::-1])
    v2 = v2.copy()
    v2[v2[:, 0] > 12, 2] = 1  # as views longas da segunda metade apontam para o 2º buffer
    views = np.ascontiguousarray(np.vstack([v1, v2]))
    m = len(views)
    validity = np.packbits(np.array([i % 3 != 0 for i in range(m)], np.uint8), bitorder="little")
    validity = np.concatenate([validity, np.zeros(8, np.uint8)])
    s = views_to_series(views, [d1, d2], "t", validity, trim_data=False)
    want = [x.decode() for x in STRINGS] + [x.decode() for x in STRINGS[::-1]]
    assert s.to_list() == [None if i % 3 == 0 else w for i, w in enumerate(want)]
    assert s.null_count() == sum(1 for i in range(m) if i % 3 == 0)


def test_bits_and_dates() -> None:
    bits = np.packbits(np.array([1, 0, 1, 1, 0], np.uint8), bitorder="little")
    valid = np.packbits(np.array([1, 1, 0, 1, 1], np.uint8), bitorder="little")
    assert bits_to_series(bits, 5, "b", valid).to_list() == [True, False, None, True, False]
    from nini_datagen.core.arrow import arrow_type  # noqa: PLC0415

    days = np.array([0, 1, 19_000], np.int32)
    valid_days = np.packbits(np.array([1, 0, 1], np.uint8), bitorder="little")
    s = primitive_to_series(days, "d", valid_days, arrow_type("date"))
    assert s.dtype == pl.Date
    assert s.to_list()[1] is None
    assert str(s[2]) == "2022-01-08"


def test_read_polars_string_column_without_copy() -> None:
    s = pl.Series("s", ["F", None, "masculino", "um texto bem mais comprido que doze bytes"])
    got = string_view_buffers(s)
    assert got is not None, "o Polars não entregou a coluna como string_view de um pedaço só"
    assert got.views.shape == (4, 4)
    assert got.validity is not None
    lengths = [int(x) for x in got.views[:, 0]]
    assert [lengths[0], lengths[2], lengths[3]] == [1, 9, len("um texto bem mais comprido que doze bytes")]
    long = got.views[3]
    data = got.datas[int(long[2])]
    off = int(long[3])
    assert bytes(data[off : off + int(long[0])]).decode() == "um texto bem mais comprido que doze bytes"


def test_works_without_pyarrow() -> None:
    """O pacote inteiro roda sem o pyarrow: gerar de tudo um pouco não importa o pyarrow (instalado ou não)."""
    code = textwrap.dedent(
        """
        import sys
        import polars as pl
        import nini_datagen as dg
        g = dg.DataGen(seed=1)
        df = g.table(150_000, {
            "cpf": ("cpf", {"formatted": True, "null_fraction": 0.1}),
            "sexo": "sex",
            "nome": ("full_name", {"sex": dg.ref("sexo")}),
            "idade": ("age", {"null_fraction": 0.2}),
            "nasc": ("birthdate", {"age": dg.ref("idade"), "on": "2026-01-01"}),
            "ativo": ("boolean", {"null_fraction": 0.3}),
            "valor": ("uniform", {"null_fraction": 0.1}),
            "obs": ("sentence", {"null_fraction": 0.3}),
            "end": "address",
        })
        assert df.height == 150_000
        assert df["cpf"].null_count() > 0 and df["ativo"].null_count() > 0
        assert df["nasc"].dtype == pl.Date
        out = dg.scan(10**9, {"x": "uuid"}, seed=1).head(5).collect()
        assert out.height == 5
        assert "pyarrow" not in sys.modules, "algo importou o pyarrow"
        print("ok")
        """
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "ok"
