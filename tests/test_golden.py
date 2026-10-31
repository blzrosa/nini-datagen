"""Gabaritos da v0.2.0: a saída com semente fixa tem que ser idêntica, valor a valor, à gravada.

A comparação usa o datacompolars no caminho **columnwise** (coluna a coluna, sem hash de linha): o caminho por hash tem
uma chance minúscula de não acusar uma diferença, e aqui 100% mais lento é melhor que 99,999999% mais rápido.

Gravar (só quando o gerador estiver no formato final da v0.2.0):

    uv run pytest tests/test_golden.py --record-golden
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pl = pytest.importorskip("polars")
if getattr(pl, "IS_FAKE", False):
    pytest.skip("precisa do Polars de verdade", allow_module_level=True)

from .golden_cases import GOLDEN_CASES, PENDING, build  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden"


def _compare(expected: Path, actual: Path) -> Any:
    dcp = pytest.importorskip("datacompolars")

    class Exact(dcp.BaseComparator):
        """Igualdade exata; qualquer comparador customizado força o caminho columnwise do datacompolars."""

        def compare(self, col_l: str, col_r: str, **kwargs: Any) -> Any:
            return pl.col(col_l) == pl.col(col_r)

    cols = [c for c in pl.read_parquet_schema(expected) if c != "_linha"]
    settings = dcp.CompareSettings(
        join_columns=["_linha"],
        left_name="gabarito",
        right_name="atual",
        lowercase_columns=False,
        custom_comparators={c: Exact() for c in cols},
    )
    return dcp.compare(expected, actual, settings)


@pytest.mark.parametrize("name", sorted(GOLDEN_CASES))
def test_golden(name: str, request: pytest.FixtureRequest, tmp_path: Path) -> None:
    path = GOLDEN / f"{name}.parquet"
    recording = request.config.getoption("--record-golden")
    if recording and name in PENDING:
        pytest.skip(f"{name} está em PENDING (golden_cases.py): conferir as amostras antes de gravar")
    df = build(name)
    if recording:
        GOLDEN.mkdir(exist_ok=True)
        df.write_parquet(path, compression="zstd", compression_level=19, statistics=False)
        pytest.skip(f"gabarito gravado: {path.name}")
    if not path.exists() and name in PENDING:
        pytest.skip(f"gabarito {path.name} ainda não gravado (aguardando a conferência das amostras)")
    if not path.exists():
        pytest.fail(f"gabarito {path.name} não existe; grave com `uv run pytest tests/test_golden.py --record-golden`")

    expected = pl.read_parquet(path)
    assert expected.schema == df.schema, "o tipo de alguma coluna mudou"
    actual = tmp_path / f"{name}.parquet"
    df.write_parquet(actual)
    r = _compare(path, actual)
    assert r.execution is not None
    assert r.execution.path == "columnwise", f"o datacompolars usou o caminho {r.execution.path!r}"
    assert r.rows.left_total == r.rows.right_total == len(df)
    bad = {st.column: st.mismatches for st in r.column_stats if st.mismatches}
    assert r.is_match, f"valores diferentes do gabarito: {bad}"
