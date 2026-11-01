"""Benchmark contra o MVP (fora da suíte padrão): ``uv run pytest -m bench -s``."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

pl = pytest.importorskip("polars")
if getattr(pl, "IS_FAKE", False):
    pytest.skip("precisa do Polars de verdade", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
bench = importlib.import_module("bench")

pytestmark = pytest.mark.bench


REF, SOURCE = bench.mvp_reference()


@pytest.mark.parametrize("case", [c for c in bench.CASES if c.name in REF], ids=lambda c: c.name)
def test_not_slower_than_mvp(case):
    new = bench.measure_runs(case, 5_000_000, 1)
    ref = REF[case.name][0]
    status, bad = bench.verdict(case.name, new, ref)
    print(f"\n{case.name}: {new} ns/linha, MVP {ref} ({SOURCE}): {status}")
    if case.name in bench.EXCEPTIONS and "exceção" in status:
        pytest.xfail(f"exceção conhecida: {bench.EXCEPTIONS[case.name]}")
    assert not bad, f"{case.name}: {status}"
