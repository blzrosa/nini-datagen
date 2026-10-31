# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões: [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado] — 0.2.0

Primeira versão pública. A v0.1.0 foi o protótipo local (nunca publicado); a v0.2.0 reescreve a estrutura.

### Garantia de reprodutibilidade
- A partir da 0.2.0, a mesma `seed` dá sempre a mesma saída, em qualquer sistema, com qualquer número de threads.
  Gerar `n` linhas dá exatamente as primeiras `n` linhas de qualquer `n` maior (blocos fixos de 65.536 linhas, cada um
  com estado próprio do gerador). Se uma versão futura precisar mudar dados gerados, isso sai como mudança incompatível
  e fica registrado aqui.
- A saída **não** é compatível com a do protótipo 0.1.0.

### Requisitos
- Python ≥ 3.11 (o mesmo mínimo do datacompolars, usado nos testes), `polars>=1.30`, `pydantic>=2.7`.

### Feito até aqui
- Fase 1: repositório (uv, scikit-build-core + CMake, ruff, pyright, pytest, CI com Python 3.11–3.14 em Linux,
  Windows e macOS, wheels por cibuildwheel para x86-64 e ARM64).
- Fase 2: kernels C++ divididos por domínio (`cpp/`), ABI em C com prefixo `dg_` e verificação de versão,
  assinaturas do ctypes geradas a partir dos `.cpp` (`tools/gen_bindings.py`), `__int128` trocado por `mulhi64`
  portátil (MSVC), fluxos do xoshiro256++ por `jump()` no C++, núcleo Python (`core.rng`, `core.blocks`,
  `core.views`, `core.arrow`). Sem caminhos alternativos em Python: a biblioteca C++ é obrigatória.

### Próximas fases
- Fase 3: geradores públicos com configurações Pydantic (`CPFConfig`, `CNPJConfig(alphanumeric=True)`...).
- Fase 4: bases embutidas (nomes, sobrenomes com grafia corrigida pelo TSE, CNEFE reduzido) e `download` da base
  completa de endereços.
- Fase 5: endereço e CEP no C++.
- Fase 6: `table`/`scan` (esquema, LazyFrame) em paralelo por blocos; testes com arquivos de referência (datacompolars).
