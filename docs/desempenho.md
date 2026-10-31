# Desempenho

Números da v0.2.0 em nanossegundos por linha (menor é melhor), medidos no PC de desenvolvimento (Windows 11, 16
threads, Python 3.11, Polars 2.1; wheels compilados com clang-cl e x86-64-v2). Em outra máquina, rode as ferramentas
abaixo: os valores absolutos mudam, as proporções costumam se manter.

| ferramenta | o que mede |
|---|---|
| `uv run python tools/bench.py` | cada gerador com 1 thread e com todas, contra o protótipo (MVP, v0.1.0) |
| `uv run python tools/profile_table.py` | a tabela de 20 colunas por etapa e por coluna; endereços com a base leve e a completa |
| `uv run --isolated --python 3.14 --group bench python tools/compare.py` | contra Faker, Mimesis e dataforge (o dataforge pede Python ≥ 3.12) |

## Contra o protótipo (MVP)

A regra do projeto é nenhum gerador mais de 10% mais lento que o MVP com 1 thread; `uv run pytest -m bench` confere.

| caso | 1 thread | 16 threads | MVP 1 thread | MVP 16 threads |
|---|---:|---:|---:|---:|
| `sentence` | 60,1 | 10,7 | 78,1 | 15,7 |
| `cep` (base completa) | 21,9 | 5,8 | 60,8 | 60,1 |
| `address` (base completa) | 102,8 | 27,1 | 187,4 | 187,5 |
| `address(full=True)` (base completa) | 222,6 | 51,8 | 443,5 | 420,8 |
| tabela de 20 colunas | 302–314 | 110–117 | 320,5 | 165,7 |

A tabela de 20 colunas é a do benchmark do MVP (CPF, CNPJ, sexo, nome pelo sexo, sobrenome, e-mail, telefone, idade,
nascimento pela idade, renda correlacionada, CEP, UUID, IP, placa, empresa, frase com 30% de nulos, booleano, real,
inteiro e data; `TABLE_20` em `tools/bench.py`). Quase todo o tempo é das próprias colunas (a soma delas sozinhas dá
~298 ns/linha); o planejamento e a montagem da tabela somam ~15.

Com a base completa do CNEFE (4 milhões de trechos), cada sorteio cai num lugar aleatório de tabelas maiores que o
cache do processador. Os kernels de endereço pedem a memória de 64 linhas de uma vez (prefetch), para as esperas se
sobreporem: foi o que levou o `cep` de 44 para 22 ns e o `address` de 229 para 103 ns.

## Contra outras bibliotecas

Resultado de `tools/compare.py` em `benchmarks/comparacao.md` (todas com 1 thread, locale pt_BR, saída como coluna do
Polars). As bibliotecas que geram um valor por chamada (Faker, Mimesis) ficam na casa de microssegundos por linha; a
vantagem do nini-datagen vem de gerar a coluna inteira no C++, direto na memória do Polars.

## Pontos conhecidos

- `scan` com muitas threads: a geração dentro do `scan` custa o mesmo que no `table` (~110 ns/linha com 16 threads),
  mas o `collect` leva ~255 ns/linha; a diferença está do lado do Polars (provavelmente as threads dele disputando os
  núcleos com as da geração). Com 1 thread a diferença é pequena (~20 ns/linha). Para gerar tudo de uma vez, prefira
  `table`; para filtrar ou pegar só algumas colunas e linhas de uma tabela enorme, `scan` gera bem menos.
- O ganho com 16 threads na tabela é de ~2,8×: parte do trabalho (planejar colunas que dependem de outras, montar a
  tabela) não divide, e a escrita de centenas de MB por milhão de linhas pesa na memória.
