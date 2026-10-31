# nini-datagen

Dados sintéticos realistas do Brasil, em escala: CPF, CNPJ (inclusive alfanumérico), nomes com a distribuição real do
IBGE, endereços do CNEFE, telefones, e-mails, textos e mais. Os geradores são kernels C++ que escrevem direto na
memória do Polars (Arrow `string_view`), sem passar string por string pelo Python.

> **Estado:** v0.2.0 em construção. O núcleo (biblioteca C++, sementes, blocos, buffers) está pronto; a API pública
> entra nas próximas fases (veja [CHANGELOG.md](CHANGELOG.md)).

## Como vai ficar

```python
import nini_datagen as dg

df = dg.table(
    {
        "nome": dg.name(),
        "cpf": dg.cpf(formatted=True),
        "empresa": dg.cnpj(dg.CNPJConfig(alphanumeric=True)),
        "cidade": dg.address("city"),
    },
    n=1_000_000,
    seed=42,
)

lf = dg.scan(schema, n=100_000_000, seed=42)  # LazyFrame: gera sob demanda, em blocos
```

## Reprodutibilidade

A partir da 0.2.0, a mesma `seed` dá sempre a mesma saída, em qualquer sistema e com qualquer número de threads, e
`n=1_000` dá exatamente as primeiras linhas de `n=1_000_000`. Cada gerador tem seu próprio fluxo de números aleatórios:
`cpf` e `phone` com a mesma semente não saem correlacionados.

## Instalação

```bash
pip install nini-datagen      # ou: uv add nini-datagen
```

Os wheels já trazem a biblioteca C++ compilada (Linux, Windows e macOS; x86-64 e ARM64) e funcionam com qualquer
Python ≥ 3.11.

## Desenvolvimento

Precisa de [uv](https://docs.astral.sh/uv/) e de um compilador C++17 (GCC, Clang ou MSVC). CMake e Ninja vêm sozinhos
pelo scikit-build-core.

```bash
uv sync                                   # cria o ambiente e compila o C++
uv run pytest                             # testes
uv run pytest -m bench                    # benchmarks
uv run ruff check . && uv run pyright     # qualidade
uv run python tools/gen_bindings.py       # depois de mudar a assinatura de uma função DG_EXPORT
```

`uv sync` / `uv run` recompilam sozinhos quando um arquivo de `cpp/` muda. Para medir com as instruções da sua CPU:
`DG_NATIVE=ON uv sync --reinstall-package nini-datagen` (os wheels publicados usam a base x86-64-v2).

### Estrutura

```
cpp/                  kernels C++ (ABI em C, prefixo dg_), um arquivo por domínio
  common.hpp          tipos, xoshiro256++, mulhi64 portátil, alias
  datagen.h           ABI em C (gerado por tools/gen_bindings.py)
src/nini_datagen/
  _native.py          carrega a biblioteca e confere a versão da ABI
  _signatures.py      tipos do ctypes de cada função (gerado)
  core/rng.py         sementes e fluxos (SeedSequence + jump do xoshiro)
  core/blocks.py      blocos fixos de 65.536 linhas e threads
  core/views.py       layout das views do Arrow (só numpy)
  core/arrow.py       entrega dos buffers ao Polars
tests/                pytest
tools/                geração de bindings e preparo das bases
```

## Licença

Código: MIT ([LICENSE](LICENSE)). Dados: fontes abertas do IBGE e do TSE, com créditos em
[DATA_LICENSES.md](DATA_LICENSES.md).
