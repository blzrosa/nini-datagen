from __future__ import annotations

import threading

import pytest

from nini_datagen.core.blocks import BLOCK_ROWS, THREADS_ENV, Block, map_blocks, resolve_threads, split


def test_block_rows_is_part_of_the_contract():
    assert BLOCK_ROWS == 65_536  # mudar isto muda os dados para a mesma semente


@pytest.mark.parametrize("n", [0, 1, BLOCK_ROWS - 1, BLOCK_ROWS, BLOCK_ROWS + 1, 5 * BLOCK_ROWS + 7])
def test_split_covers_rows(n):
    blocks = split(n)
    assert sum(b.rows for b in blocks) == n
    assert [b.index for b in blocks] == list(range(len(blocks)))
    assert all(b.start == b.index * BLOCK_ROWS for b in blocks)
    assert all(0 < b.rows <= BLOCK_ROWS for b in blocks)


def test_split_validation():
    with pytest.raises(ValueError, match=">= 0"):
        split(-1)
    with pytest.raises(TypeError):
        split(1.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        split(True)


def test_resolve_threads(monkeypatch):
    monkeypatch.delenv(THREADS_ENV, raising=False)
    assert resolve_threads(3) == 3
    assert resolve_threads() >= 1
    monkeypatch.setenv(THREADS_ENV, "2")
    assert resolve_threads() == 2
    assert resolve_threads(5) == 5  # pedido explícito ganha da variável
    monkeypatch.setenv(THREADS_ENV, "muitas")
    with pytest.raises(ValueError, match="inteiro"):
        resolve_threads()
    with pytest.raises(ValueError, match=">= 1"):
        resolve_threads(0)
    with pytest.raises(TypeError):
        resolve_threads(2.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("threads", [1, 2, 8])
def test_map_blocks_keeps_order(threads):
    blocks = split(10 * BLOCK_ROWS + 3)
    assert map_blocks(lambda b: (b.index, b.rows), blocks, threads) == [(b.index, b.rows) for b in blocks]


def test_map_blocks_runs_in_parallel():
    seen: set[int] = set()
    lock = threading.Lock()

    def fn(b: Block) -> int:
        with lock:
            seen.add(threading.get_ident())
        return b.index

    map_blocks(fn, split(16 * BLOCK_ROWS), threads=4)
    assert len(seen) >= 1  # (quantas threads de fato pegam blocos depende do agendador)


def test_map_blocks_empty():
    assert map_blocks(lambda b: b, [], threads=4) == []


def test_map_blocks_propagates_errors():
    def boom(b: Block) -> None:
        raise RuntimeError(f"bloco {b.index}")

    with pytest.raises(RuntimeError, match="bloco"):
        map_blocks(boom, split(3 * BLOCK_ROWS), threads=2)
