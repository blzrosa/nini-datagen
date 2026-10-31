from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from nini_datagen import NativeLibraryError, _native
from nini_datagen._signatures import ABI_VERSION, SIGNATURES

ROOT = Path(__file__).resolve().parents[1]


def test_loads_and_abi(lib):
    assert lib.dg_abi_version() == ABI_VERSION
    assert _native.library_path().is_file()
    assert _native.lib() is lib  # carregada uma vez só


def test_all_signatures_applied(lib):
    for name, (restype, argtypes) in SIGNATURES.items():
        fn = getattr(lib, name)
        assert fn.restype is restype
        assert list(fn.argtypes) == argtypes


def test_init_is_idempotent(lib):
    assert lib.dg_init() == 1
    assert lib.dg_init() == 1


def test_ptr_requires_contiguous():
    a = np.zeros((4, 4), np.uint32)
    assert _native.ptr(a) == a.ctypes.data
    with pytest.raises(ValueError, match="contíguo"):
        _native.ptr(a[:, ::2])


def test_env_var_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv(_native.ENV_VAR, str(tmp_path / "nao_existe.so"))
    _native._reset()
    try:
        with pytest.raises(NativeLibraryError, match="não encontrada"):
            _native.lib()
    finally:
        monkeypatch.undo()
        _native._reset()


def test_wrong_library_is_rejected(monkeypatch):
    """Uma biblioteca compartilhada qualquer (a do próprio numpy) não passa pela checagem."""
    other = Path(np._core._multiarray_umath.__file__ if hasattr(np, "_core") else np.core._multiarray_umath.__file__)
    monkeypatch.setenv(_native.ENV_VAR, str(other))
    _native._reset()
    try:
        with pytest.raises(NativeLibraryError, match="dg_abi_version"):
            _native.lib()
    finally:
        monkeypatch.undo()
        _native._reset()


def test_native_error_is_import_error():
    assert issubclass(NativeLibraryError, ImportError)


@pytest.mark.skipif(not (ROOT / "tools" / "gen_bindings.py").exists(), reason="fora do repositório")
def test_bindings_up_to_date():
    """datagen.h e _signatures.py precisam bater com as assinaturas DG_EXPORT dos .cpp."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_bindings.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
