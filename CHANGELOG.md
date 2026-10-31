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

- Fase 3: configurações Pydantic (`BaseConfig` com `name` e `null_fraction`, imutáveis, `extra="forbid"`),
  `registry` de geradores, `DataGen` e funções soltas, locale `pt_BR` com as bases de nomes (IBGE, grafia corrigida
  pelo TSE) e sobrenomes (TSE 2024). Geradores: `integer`, `uniform`, `normal`, `lognormal`, `boolean`, `date`,
  `datetime`, `choice`, `sex`, `age`, `first_name` (também por coluna de sexo), `last_name`, `full_name` (prenome
  composto em 25% e dois sobrenomes em 90% por padrão). Cada
  coluna é montada em buffers únicos (um chunk só), preenchidos bloco a bloco em paralelo; nulos por fluxo próprio.
  Gabaritos (`tests/golden/`, comparados pelo datacompolars no caminho columnwise) e `tools/bench.py`.

- Determinismo entre sistemas: `normal`/`lognormal` usam log e exp próprios (sem a biblioteca matemática do sistema)
  e o C++ é compilado sem fusão de multiplicação e soma (`-ffp-contract=off`); a mesma semente dá os mesmos bits em
  Windows, Linux, macOS, x86-64 e ARM64, conferido por teste. ABI 2.
- `full_name` decide as partes por índice e monta o texto de uma vez no C++ (`dg_join_views`), em paralelo por bloco.
- Windows: `DG_CLANGCL=1` compila com clang-cl (os wheels usam); sem a variável, MSVC.

### Próximas fases
- Fase 4: documentos (CPF, CNPJ numérico e alfanumérico, PIS, título, CNH, RG, placa, cartão, IBAN, EAN), rede (UUID,
  IP, MAC, URL), email, username, empresa, veículo e frases.
- Fase 5: endereço e CEP no C++, CNEFE reduzido no pacote e `download` da base completa.
- Fase 6: `table`/`scan` (esquema, LazyFrame) em paralelo por blocos; testes com arquivos de referência (datacompolars).
