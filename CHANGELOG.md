# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões: [SemVer](https://semver.org/lang/pt-BR/).

## [0.2.0] — 2026-10-31

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

- Fase 4 (em andamento): documentos com dígito verificador correto — `cpf` e `cnpj` (numérico e alfanumérico, ordem
  fixa ou sorteada, opção `unique` sem repetição: a linha `i` recebe `perm(i)`, uma cifra de Feistel com chave
  tirada da semente, então os valores parecem aleatórios e continuam estáveis por prefixo; ABI 4), `pis`,
  `voter_id` (válido nas duas leituras da regra de SP/MG), `cnh`, `rg` (padrão SP), `license_plate` (Mercosul ou
  antiga), `credit_card` (Luhn; Visa, Mastercard, Amex), `iban` (Brasil) e `ean13` (prefixo 789); rede — `uuid` (v4),
  `ipv4` (público sem faixas reservadas, ou privado), `ipv6`, `mac` (unicast) e `url` (palavras e TLDs do locale).
  Validadores públicos em `nini_datagen.validators`. Os textos saem prontos do C++ nas views do Arrow (`TextJob`).
- Fase 4, segunda parte: `phone` (DDD com peso pela população da UF no Censo 2022, filtro por `uf`; celular, fixo,
  máscara e +55), `email` e `username` (8 estilos, nomes e sobrenomes com o peso das bases), `company` (razão social),
  `vehicle` (struct `{brand, model, year}` coerente), `occupation`, `sentence` e `paragraph` (gramática de frases com
  concordância, 5 temas ou modelos próprios com `templates`/`slots`). ABI 5.
- Gramática: símbolos só de literais ({d}, {pessoa}...) viram folhas copiadas direto, sem pilha; o buffer de texto é
  reservado pela média estimada e, se encher, o kernel para e continua num buffer novo com o mesmo estado (a saída não
  depende do corte).
- Mais rápidos: IBAN (DV módulo 97 calculado por partes, sem percorrer os dígitos), URL (menos chamadas do gerador,
  palavras sorteadas 2 por número), cartão (Luhn por tabela), e todos os textos com buffer: o índice do buffer nas views
  é gravado no C++ (`dg_views_used`) em vez de máscara do numpy, que custava ~7 ns por linha.
- Gramática (ABI 6): toda opção termina com um token de fim e o tipo do token sai de 2 bits de uma vez (menos desvios
  mal previstos); folhas vizinhas viram uma folha combinada (`{d1}{d}{d}` -> 900 opções, mesma distribuição, menos
  sorteios); no parágrafo, uma frase igual à anterior é sorteada de novo (até 16 vezes). Concordância corrigida em
  duas opções do tema atendimento ("transferido", "contatado").

- Fase 5: endereços do CNEFE (IBGE, Censo 2022) em kernel: `cep`, `address` (struct com rua, número, complemento,
  bairro, cidade, UF e CEP coerentes; opcionais `phone` com o DDD da UF, `coords` e `full`), `city` e `state` pela
  população. O trecho é sorteado pelo número de endereços e os textos são cópias de views das tabelas de nomes, sem
  Polars no caminho (escala com as threads). Base leve no pacote; a completa em `nini_datagen.datasets.download`
  (cache local, SHA-256, versão do formato). `tools/build_cnefe.py` gera as duas a partir dos dados do MVP. ABI 7.

- Fase 6, primeira parte: `Schema` (validado e compilado uma vez: colunas de gerador, `dg.ref` para dependências,
  expressões do Polars, ordem por níveis com erro claro para ciclo ou coluna inexistente), `table` com paralelismo
  por bloco de linhas (todas as colunas de um bloco de uma vez) e `scan`, um `pl.LazyFrame` registrado como fonte de
  dados do Polars que respeita projeção, filtro e limite e gera em lotes. Os geradores podem começar em qualquer
  bloco da coluna (`first_block`), e é isso que garante `scan(...).collect() == table(...)`. Geradores novos que
  dependem de outra coluna: `birthdate` (coerente com a idade), `correlated` (correlação `rho`, também na escala
  do log; numa tabela, o centro e a escala vêm da distribuição da coluna referida) e `choice_by` (escolha condicional).
  `correlated` roda no C++ com o exp determinístico (`dg_correlated`), e as médias e desvios usados como centro e
  escala são somas exatas (`math.fsum`), para a mesma semente dar os mesmos bits em Windows, Linux e macOS (o `np.exp`
  e o `pow` do sistema mudam o último bit conforme a máquina). ABI 8.

- Fase 6, segunda parte: dados sujos em qualquer coluna (`dirty={"typo": 0.02, "unmask": 0.3}` ou `DirtyConfig`:
  acentos, mojibake, máscara, erro de digitação, corte, maiúsculas, espaços, textos de vazio, outliers e
  sentinelas), com fluxos próprios por defeito alinhados aos blocos (a coluna suja também sai igual em lotes);
  `dg.dirty` para colunas prontas; `add_duplicates` (cópias exatas ou sujas, com gabarito `row_id`/`dup_of`);
  `write_parquet_dataset` (lotes com memória limitada, `rows_per_file`, partições Hive, compressão), cujos arquivos
  juntos são exatamente `table(n, schema)` para qualquer tamanho de lote. `tools/profile_table.py` mostra o custo de
  cada coluna da tabela e dos endereços com a base leve e a completa.
- CI também em Linux ARM64; wheel Intel do macOS no `macos-15-intel` (o `macos-13` foi desativado).
- Desempenho (ABI 10): o sorteio de trechos do CNEFE busca a memória em lotes de 64 linhas com prefetch (tabela
  alias, registro de 32 bytes por trecho com CEP, rua, bairro, cidade, UF e faixa de números, e os nomes da rua e do
  bairro) e escreve todas as views do endereço numa passada (`dg_address_core`), o que pesa na base completa (4
  milhões de trechos, maior que o cache); `birthdate` e o `z` de `correlated`
  passaram para o C++; a tabela planeja e monta as colunas de cada nível em paralelo. Saída idêntica (gabaritos
  inalterados).

- Fase 6, terceira parte: documentação (`docs/guia.md`, `docs/desempenho.md`, `examples/`), `tools/compare.py`
  (contra Faker, Mimesis e dataforge: ns por linha e validade das regras brasileiras; grupo `bench`), publicação no
  TestPyPI por `workflow_dispatch` com teste de instalação em máquinas limpas dos cinco alvos e no PyPI por release,
  CI com as versões mínimas das dependências (Polars 1.30), que mostrou que o pacote precisa do pyarrow ≥ 19
  (string_view com vários buffers de texto). Testada como 0.2.0rc1 no TestPyPI: o wheel instala e gera dados em
  máquinas limpas dos cinco alvos (Windows x86-64, Linux x86-64 e ARM64, macOS Intel e Apple Silicon), Python 3.11 e 3.14.
- Meta de desempenho revista: a tabela de 20 colunas com 1 thread fica em ~300 ns/linha (MVP: 320,5); a meta de
  200 ns pediria reescrever os geradores mais caros (frase, e-mail, empresa), que já estão no ritmo do MVP ou melhor.
  Vale a regra geral de nenhum gerador ou tabela mais lento que o MVP.

### Próximo
- `scan` com muitas threads (a diferença está do lado do Polars), buffers sem pyarrow (PyCapsule) e
  wheels para Windows ARM64.
