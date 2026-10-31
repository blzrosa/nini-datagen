# Guia do nini-datagen

Dados sintéticos realistas do Brasil em escala, direto em Polars. Este guia cobre tudo o que a biblioteca faz; o
[README](../README.md) tem o resumo.

- [Instalação](#instalação)
- [Primeiros passos](#primeiros-passos)
- [Configurações](#configurações)
- [Geradores](#geradores)
- [Tabelas: `Schema`, `table` e `scan`](#tabelas-schema-table-e-scan)
- [Colunas que dependem de outras](#colunas-que-dependem-de-outras)
- [Dados sujos e duplicatas](#dados-sujos-e-duplicatas)
- [Arquivos grandes](#arquivos-grandes)
- [Endereços do CNEFE](#endereços-do-cnefe)
- [Reprodutibilidade](#reprodutibilidade)
- [Threads e desempenho](#threads-e-desempenho)
- [Validadores](#validadores)

## Instalação

```bash
pip install nini-datagen      # ou: uv add nini-datagen
```

Os wheels trazem a biblioteca C++ compilada para Linux (x86-64 e ARM64), macOS (Intel e Apple Silicon) e Windows
(x86-64), para qualquer Python ≥ 3.11. Em outra plataforma o `pip` compila a partir do código-fonte: precisa de um
compilador C++17.

Dependências: `polars` ≥ 1.30, `pyarrow` ≥ 19, `numpy`, `pydantic` ≥ 2.7 e `platformdirs`.

## Primeiros passos

```python
import nini_datagen as dg

dg.cpf(5, seed=42)  # funções soltas: um gerador por chamada
g = dg.DataGen(seed=42)  # semente, locale e threads fixos
g.first_name(1_000_000)  # pl.Series com 1 milhão de nomes
g.choice(10, ["bronze", "prata", "ouro"], weights=[6, 3, 1])
```

Toda função devolve uma `pl.Series` (ou `pl.DataFrame`/`pl.LazyFrame`, nas tabelas). O nome da coluna é o do gerador
(`"cpf"`), ou o que vier em `name=`.

Sem `seed`, cada chamada sorteia uma semente nova; com `seed`, o resultado é sempre o mesmo. `g.seed` mostra a
semente sorteada, para reproduzir depois.

## Configurações

Cada gerador tem uma configuração Pydantic imutável (`dg.CPFConfig`, `dg.AddressConfig`...). Dá para passar o objeto,
um dict ou kwargs; nome de parâmetro errado ou valor inválido vira `ValidationError` em vez de ser ignorado:

```python
cfg = dg.IntegerConfig(low=18, high=90, null_fraction=0.1)
g.integer(1000, cfg)
g.integer(1000, cfg, high=65)  # kwargs sobrescrevem campos
g.integer(1000, hihg=65)  # ValidationError: Extra inputs are not permitted
```

Campos que todo gerador aceita:

| campo | o que faz |
|---|---|
| `name` | nome da coluna e do fluxo de números aleatórios (veja [Reprodutibilidade](#reprodutibilidade)) |
| `null_fraction` | fração de nulos, sorteados linha a linha num fluxo próprio |
| `dirty` | defeitos de dados reais (veja [Dados sujos](#dados-sujos-e-duplicatas)) |

## Geradores

`dg.DataGen.kinds()` lista todos. Os parâmetros de cada um estão na docstring da configuração (`help(dg.PhoneConfig)`).

| área | geradores |
|---|---|
| números e datas | `integer`, `uniform`, `normal`, `lognormal`, `boolean`, `date`, `datetime`, `choice` |
| pessoa | `sex`, `age`, `first_name`, `last_name`, `full_name` |
| documentos (DV correto) | `cpf`, `cnpj` (numérico e alfanumérico), `pis`, `voter_id`, `cnh`, `rg`, `credit_card`, `iban`, `ean13`, `license_plate` |
| rede | `uuid`, `ipv4`, `ipv6`, `mac`, `url` |
| contato e empresa | `phone`, `email`, `username`, `company`, `vehicle`, `occupation` |
| texto | `sentence`, `paragraph` (gramática com concordância; temas ou modelos próprios) |
| endereço (CNEFE) | `cep`, `address`, `city`, `state` |
| dependentes | `birthdate`, `correlated`, `choice_by` (veja abaixo) |

Exemplos:

```python
g.cpf(1_000_000, unique=True, formatted=True)  # sem repetição (até 10^9)
g.cnpj(10, alphanumeric=True, formatted=True)  # formato novo da Receita
g.phone(10, style="masked", uf=["SP", "RJ"])  # DDD com peso pela população da UF
g.sentence(3, theme="saude")
g.sentence(3, templates=["Pedido {cod} enviado.", ("Sem observações.", 3)], slots={"cod": ["{d}{d}{d}"]})
g.vehicle(5).struct.unnest()  # brand, model, year coerentes
g.address(5, phone=True, coords=True, full=True).struct.unnest()
```

## Tabelas: `Schema`, `table` e `scan`

Um `Schema` descreve a tabela; é validado e compilado uma vez e pode ser reaproveitado:

```python
import polars as pl

schema = dg.Schema(
    {
        "id": ("cpf", {"unique": True, "formatted": True}),
        "sexo": "sex",
        "nome": ("full_name", {"sex": dg.ref("sexo")}),
        "idade": ("age", {"low": 18, "high": 90}),
        "cliente_desde": ("date", {"start": "2015-01-01", "end": "2026-01-01"}),
        "plano": dg.column("choice", ["bronze", "prata", "ouro"], weights=[6, 3, 1]),
        "meses": pl.col("idade") * 12,
    }
)
df = g.table(1_000_000, schema)  # pl.DataFrame
lf = g.scan(10**9, schema)  # pl.LazyFrame: nada é gerado até o collect
lf.filter(pl.col("idade") >= 60).select("nome").head(10).collect()
```

Formas aceitas para uma coluna: `"tipo"`, `("tipo", {parâmetros})`, `("tipo", Config(...))`, uma configuração
(`dg.CPFConfig(...)`), `dg.column("tipo", ...)` (aceita o argumento posicional, como a lista do `choice`) ou uma
expressão do Polars sobre outras colunas.

- `table` preenche bloco a bloco (65.536 linhas) todas as colunas de um bloco de uma vez, com os blocos em paralelo.
- `scan` registra o schema como fonte do Polars: ele recebe as colunas pedidas, o filtro e o limite, e gera em lotes
  só o necessário (só as colunas pedidas e as de que elas dependem; com `head`, só as primeiras linhas).
- Cada coluna sai igual a `g.generate(tipo, n, name=coluna, ...)`; reordenar, tirar ou acrescentar colunas não muda as
  outras; e `scan(n, schema).collect()` é igual a `table(n, schema)`.
- No `scan`, as expressões rodam lote a lote: use só expressões linha a linha (nada de `mean()`, `rank()`...).
- Ciclo, coluna inexistente e `ref` num parâmetro que não é de dados dão erro ao compilar o schema.

## Colunas que dependem de outras

Os geradores abaixo recebem uma coluna como dado: numa tabela, por `dg.ref("coluna")`; sozinhos, uma Series.

| gerador | dado | o que faz |
|---|---|---|
| `first_name`, `full_name` | `sex` | nomes coerentes com o sexo da linha (primeira letra F/M; o resto é sorteado) |
| `birthdate` | `age` | nascimento coerente com a idade na data `on` (fixe `on` para reproduzir em outro dia) |
| `correlated` | `other` | real com correlação `rho` com a coluna; `lognormal=True` para renda, preço... |
| `choice_by` | `by` | escolha que depende do valor da coluna: `options={"F": [...], "M": (lista, pesos)}`, `default` |

```python
schema = dg.Schema(
    {
        "idade": ("age", {"low": 18, "high": 90}),
        "nascimento": ("birthdate", {"age": dg.ref("idade"), "on": "2026-01-01"}),
        "renda": ("correlated", {"other": dg.ref("idade"), "rho": 0.4, "mean": 8, "std": 0.6, "lognormal": True}),
        "marca": ("choice", {"values": ["Fiat", "Toyota"]}),
        "modelo": ("choice_by", {"by": dg.ref("marca"), "options": {"Fiat": ["Argo", "Mobi"], "Toyota": ["Corolla"]}}),
    }
)
```

Em `correlated`, `center` e `scale` são a média e o desvio de `other`: numa tabela, com `ref` para um gerador de
distribuição conhecida (`integer`, `uniform`, `normal`, `lognormal`, `age`), vêm dela; para uma expressão, passe os
dois.

## Dados sujos e duplicatas

`dirty` funciona em qualquer coluna (gerada sozinha ou numa tabela); cada valor é a fração das linhas afetadas:

| defeito | efeito |
|---|---|
| `accents` | `"São Paulo"` → `"Sao Paulo"` |
| `mojibake` | `"São"` → `"SÃ£o"` (UTF-8 lido como Latin-1) |
| `unmask` | `"529.982.247-25"` → `"52998224725"` (pontuação de máscara e espaços) |
| `typo` | apaga, troca com a vizinha, repete ou substitui uma letra |
| `truncate` | corta o fim |
| `case` | tudo maiúsculo ou tudo minúsculo |
| `whitespace` | espaço sobrando no começo, no fim ou nos dois |
| `null_like` | `""`, `"N/A"`, `"NULL"`, `"-"`... (`null_tokens` troca a lista) |
| `outliers` | números multiplicados por `-1`, `10`, `100` ou `1000` (`outlier_factors`) |
| `sentinel` | `[(valor, fração), ...]`: `-1`, `0`, `9999`... |

```python
g.cpf(1000, formatted=True, dirty={"unmask": 0.3, "whitespace": 0.02})
dg.dirty(df["nome"], typo=0.02, seed=7)  # qualquer coluna pronta
com_dups = g.add_duplicates(df, 0.05, dirty={"nome": {"typo": 0.5}})
```

`add_duplicates` acrescenta cópias (exatas ou sujas) de linhas sorteadas; `row_id` numera todas e `dup_of` aponta
para a original nas cópias: os pares são o gabarito para testar deduplicação e fuzzy matching.

## Arquivos grandes

```python
g.write_parquet_dataset("saida/", 100_000_000, schema, partition_by="uf", rows_per_file=1_000_000)
pl.scan_parquet("saida/", hive_partitioning=True)
```

- Gera em lotes (`batch_rows`, padrão ~1 milhão de linhas) com no máximo dois lotes na memória, o seguinte sendo
  gerado enquanto o atual é gravado.
- Os arquivos juntos são exatamente `table(n, schema)`, na mesma ordem, para qualquer `batch_rows`.
- `rows_per_file`: arquivos com exatamente essa quantidade de linhas (o último de cada partição fica menor).
- `partition_by`: pastas no estilo Hive (`uf=SP/part-00000.parquet`); nulos vão para `__HIVE_DEFAULT_PARTITION__`.
- `compression`: `zstd` (padrão, nível 1), `lz4`, `snappy`, `gzip`, `brotli` ou `uncompressed`.

## Endereços do CNEFE

Os endereços são reais, do Cadastro Nacional de Endereços para Fins Estatísticos do IBGE (Censo 2022): rua, bairro,
cidade, UF e CEP existem juntos, sorteados pelo número de endereços de cada trecho.

- A base leve vem no pacote: 1% dos endereços de cada município, todos os 5.570 municípios, sem as faixas de número.
- A completa (~55 MB, 4 milhões de trechos, com a faixa real de números de cada rua) é baixada uma vez:
  `dg.datasets.download("cnefe")`. Fica no cache do usuário (`platformdirs`, ou a pasta de `NINI_DATAGEN_CACHE`),
  conferida por SHA-256.
- `source="auto"` (padrão) usa a completa se baixada, senão a leve; `"lite"` e `"full"` forçam uma delas. A mesma
  semente dá endereços diferentes em cada base: fixe `source` para reproduzir em outra máquina.

## Reprodutibilidade

A partir da 0.2.0, a mesma `seed` dá sempre a mesma saída, em qualquer sistema (Windows, Linux, macOS; x86-64 e ARM64),
com qualquer número de threads. O CI confere isso em cada sistema contra gabaritos gravados uma vez (`tests/golden/`).

- Cada coluna tem seu fluxo de números aleatórios, identificado pelo nome: colunas com nomes diferentes não saem
  correlacionadas, e a mesma coluna sai sempre igual.
- Os nulos e cada defeito de `dirty` têm fluxos próprios: mudar `null_fraction` não muda os valores das outras linhas.
- A geração é estável por prefixo: `n=1_000` dá exatamente as primeiras linhas de `n=1_000_000`.
- Não use a mesma semente com versões diferentes da biblioteca esperando a mesma saída sem olhar o
  [CHANGELOG](../CHANGELOG.md): uma mudança intencional nos dados sai como versão nova, com o motivo registrado.

## Threads e desempenho

`DataGen(threads=None)` usa todas as CPUs (ou `NINI_DATAGEN_THREADS`); o resultado não depende disso. Geradores muito
baratos (booleano) ficam numa thread só, porque dividir não compensa.

Os números de referência estão em [desempenho.md](desempenho.md); `tools/bench.py`, `tools/profile_table.py` e
`tools/compare.py` medem na sua máquina.

## Validadores

`dg.validators` confere textos de qualquer origem, com ou sem máscara:

```python
dg.validators.cpf("529.982.247-25")  # True
dg.validators.cnpj("HI.EJT.HBE/0001-69")  # CNPJ alfanumérico
dg.validators.credit_card("4111 1111 1111 1111")
```

Há validadores para `cpf`, `cnpj`, `pis`, `voter_id`, `cnh`, `rg`, `credit_card`, `iban` e `ean13`.
