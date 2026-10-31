# nini-datagen

Dados sintéticos realistas do Brasil, em escala: CPF, CNPJ (inclusive alfanumérico), nomes com a distribuição real do
IBGE, endereços do CNEFE, telefones, e-mails, textos e mais. Os geradores são kernels C++ que escrevem direto na
memória do Polars (Arrow `string_view`), sem passar string por string pelo Python.

> **Estado:** v0.2.0 em construção (veja [CHANGELOG.md](CHANGELOG.md)). Já existem os geradores de números, datas,
> booleanos, escolha em lista e pessoa (sexo, idade, nomes); documentos, rede, endereço, tabelas e LazyFrame entram
> nas próximas fases.

## Uso

```python
import nini_datagen as dg

dg.first_name(5, seed=42)  # pl.Series String com nomes na frequência do Censo
dg.integer(1_000_000, low=1, high=6)  # sem seed: semente nova a cada chamada

g = dg.DataGen(seed=42)  # semente, locale e threads fixos
sexo = g.sex(1_000_000)  # "F"/"M", 51,5% de mulheres
nome = g.first_name(1_000_000, sex=sexo)  # nomes coerentes com o sexo de cada linha
idade = g.age(1_000_000)  # pirâmide etária aproximada do Brasil
plano = g.choice(1_000_000, ["bronze", "prata", "ouro"], weights=[6, 3, 1], null_fraction=0.05)
```

Toda configuração é um modelo Pydantic imutável. Dá para passar o objeto, um dict ou kwargs; nome de parâmetro
errado ou valor inválido vira `ValidationError`:

```python
cfg = dg.IntegerConfig(low=18, high=90, null_fraction=0.1)
g.integer(1000, cfg)
g.integer(1000, cfg, high=65)  # kwargs sobrescrevem campos
g.integer(1000, hihg=65)  # ValidationError: Extra inputs are not permitted
```

| gerador | configuração | tipo |
|---|---|---|
| `integer` | `IntegerConfig(low, high, dtype)` | Int32 / Int64 |
| `uniform` | `UniformConfig(low, high, dtype)` | Float64 / Float32 |
| `normal`, `lognormal` | `NormalConfig(mean, std)`, `LognormalConfig(mean, sigma)` | Float64 |
| `boolean` | `BooleanConfig(p)` | Boolean |
| `date`, `datetime` | `DateConfig(start, end)`, `DatetimeConfig(start, end, unit)` | Date / Datetime |
| `choice` | `ChoiceConfig(values, weights)` | String, Int64, Float64 ou Boolean |
| `sex` | `SexConfig(p_female, labels)` | String |
| `age` | `AgeConfig(low, high, weights)` | Int32 |
| `first_name`, `last_name` | `FirstNameConfig(sex)`, `LastNameConfig()` | String |
| `full_name` | `FullNameConfig(sex, compound, two_surnames)` | String |
| `cpf` | `CPFConfig(formatted, unique)` | String |
| `cnpj` | `CNPJConfig(alphanumeric, branch, formatted, unique)` | String |
| `pis`, `voter_id`, `rg` | `PISConfig(formatted)`, `VoterIDConfig(formatted)`, `RGConfig(formatted)` | String |
| `cnh`, `iban`, `ean13` | `CNHConfig()`, `IBANConfig()`, `EAN13Config()` | String |
| `license_plate` | `LicensePlateConfig(style)` (`"mercosul"` ou `"old"`) | String |
| `credit_card` | `CreditCardConfig(brand, formatted)` | String |
| `uuid`, `ipv6`, `mac`, `url` | `UUIDConfig()`, `IPv6Config()`, `MACConfig()`, `URLConfig()` | String |
| `ipv4` | `IPv4Config(private)` | String |
| `phone` | `PhoneConfig(style, mobile, uf)` | String |
| `email`, `username` | `EmailConfig(domains, domain_weights, style_weights)`, `UsernameConfig(style_weights)` | String |
| `company`, `occupation` | `CompanyConfig()`, `OccupationConfig(zipf)` | String |
| `vehicle` | `VehicleConfig(year_low, year_high)` | Struct `{brand, model, year}` |
| `cep` | `CepConfig(formatted, uf, source)` | String |
| `address` | `AddressConfig(uf, complement, phone, coords, full, source)` | Struct `{street, number, complement, neighborhood, city, state, cep, ...}` |
| `city`, `state` | `CityConfig(uf, with_state)`, `StateConfig(weighted)` | String |
| `sentence`, `paragraph` | `SentenceConfig(theme, templates, slots)`, `ParagraphConfig(..., sentences)` | String |

Todos aceitam `name` (nome da coluna) e `null_fraction` (fração de nulos).

Os documentos saem com dígitos verificadores corretos (não são documentos reais de ninguém), e `dg.validators` confere
textos de qualquer origem:

```python
g.cpf(1_000_000, unique=True)  # sem repetição (até 10^9)
g.cnpj(10, alphanumeric=True, formatted=True)  # "HI.EJT.HBE/0001-69", o formato novo da Receita
dg.validators.cpf("529.982.247-25")  # True
```

Frases saem de uma gramática com concordância (temas `atendimento`, `saude`, `entrega`, `avaliacao`, `cadastro` ou
`geral`), ou de modelos próprios:

```python
g.sentence(3, theme="saude")  # "Reembolso de R$ 964,22 liberado para pagamento."
g.paragraph(3, sentences=(2, 4))
g.sentence(3, templates=["Pedido {cod} enviado {prazo}.", ("Sem observações.", 3)], slots={"cod": ["{d}{d}{d}"]})
g.vehicle(5).struct.unnest()  # colunas brand, model, year
```

Endereços são reais, do CNEFE do IBGE (Censo 2022): rua, bairro, cidade, UF e CEP existem juntos, sorteados pelo
número de endereços. O pacote traz uma base leve (1% dos endereços de cada município, todos os 5.570 municípios); a
completa (~55 MB, com a faixa real de números de cada rua) é baixada uma vez e fica em cache:

```python
g.address(5, full=True).struct.unnest()  # street, number, complement, neighborhood, city, state, cep, full
g.cep(5, uf="SP")
dg.datasets.download("cnefe")  # depois disso, source="auto" usa a base completa
```

## Reprodutibilidade

A partir da 0.2.0, a mesma `seed` dá sempre a mesma saída, em qualquer sistema e com qualquer número de threads, e
`n=1_000` dá exatamente as primeiras linhas de `n=1_000_000`. Cada coluna tem seu próprio fluxo de números aleatórios,
identificado pelo nome (`name`, que por padrão é o tipo do gerador): colunas com nomes diferentes não saem
correlacionadas, e a mesma coluna sai sempre igual (`g.integer(10)` duas vezes dá o mesmo resultado). Os nulos têm
fluxo próprio: mudar `null_fraction` não muda os valores das linhas que continuam preenchidas.

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
uv run pytest -m bench -s                 # benchmarks contra o MVP (fora da suíte padrão)
uv run python tools/bench.py              # tabela completa de ns/linha
uv run python tools/samples.py            # amostras de cada gerador
uv run ruff check . && uv run pyright     # qualidade
uv run python tools/gen_bindings.py       # depois de mudar a assinatura de uma função DG_EXPORT
```

`uv sync` / `uv run` recompilam sozinhos quando um arquivo de `cpp/` muda (ou as variáveis abaixo).

- `DG_CLANGCL=1` (Windows): compila com clang-cl em vez do MSVC, como os wheels publicados; bem mais rápido nos
  kernels. Precisa dos componentes "C++ Clang Compiler for Windows" e "MSBuild support for LLVM (clang-cl) toolset"
  do Visual Studio Installer.
- `DG_NATIVE=ON`: compila para as instruções da sua CPU (`-march=native`), só para medir; os wheels usam x86-64-v2.
  O resultado não muda: o código não depende de FMA nem da biblioteca matemática do sistema.

### Estrutura

```
cpp/                     kernels C++ (ABI em C, prefixo dg_), um arquivo por domínio
src/nini_datagen/
  __init__.py, api.py    funções soltas (dg.integer...) e exportações
  generator.py           DataGen: semente, locale e threads; um método por gerador
  registry.py            registro dos geradores por nome e montagem das configurações
  config/                modelos Pydantic (um por gerador)
  providers/             um gerador por tipo: plan() aloca, Job.fill() preenche cada bloco, Job.finish() entrega
  locales/pt_BR/         dados e regras do Brasil (data/*.tsv)
  core/                  sementes e fluxos, blocos e threads, views do Arrow, tabelas alias e vocabulários
  _native.py             carrega a biblioteca C++ e confere a versão da ABI
tests/                   pytest; tests/golden/ guarda os gabaritos da v0.2.0
tools/                   bindings, benchmark, amostras
```

Gerador novo: uma configuração em `config/`, um provider com `@registry.register` em `providers/` e um atalho em
`generator.py`/`api.py`; o resto (blocos, threads, nulos, semente) vem do roteiro comum em `providers/base.py`.

## Licença

Código: MIT ([LICENSE](LICENSE)). Dados: fontes abertas do IBGE e do TSE, com créditos em
[DATA_LICENSES.md](DATA_LICENSES.md).
