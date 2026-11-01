# Desempenho

Números da v0.2.1 em nanossegundos por linha (menor é melhor), medidos no PC de desenvolvimento (Windows 11, 16
threads, Python 3.11, Polars 2.1; wheels compilados com clang-cl e x86-64-v2). Em outra máquina, rode as ferramentas
abaixo: os valores absolutos mudam, as proporções costumam se manter.

| ferramenta | o que mede |
|---|---|
| `uv run python tools/bench.py` | cada gerador com 1 thread e com todas, contra o protótipo (MVP, v0.1.0) |
| `uv run python tools/profile_table.py` | a tabela de 20 colunas por etapa e por coluna; endereços com a base leve e a completa |
| `uv run --isolated --python 3.14 --group bench python tools/compare.py` | contra Faker, Mimesis e dataforge (o dataforge pede Python ≥ 3.12) |

## Contra o protótipo (MVP)

A regra do projeto é nenhum gerador mais de 10% mais lento que o MVP com 1 thread. As medidas têm ruído (de uma
rodada para outra, um gerador de ~1,5 ns/linha varia mais de 30%), então a comparação é estatística: o MVP é medido
100 vezes (`tools/bench_mvp.py`, no ambiente do MVP, gravado em `tools/mvp_stats.json`), a versão nova 10 vezes
(`tools/bench.py` e `uv run pytest -m bench`), e a razão das médias ganha um intervalo de 95% (Welch). Só reprova
com o intervalo inteiro acima de 1,10; cruzando 1,10, o resultado é inconclusivo. Médias em ns/linha:

| caso | 1 thread | 16 threads | MVP 1 thread | MVP 16 threads | novo / MVP, 1 thread [IC 95%] |
|---|---:|---:|---:|---:|---|
| `integer` | 1,37 | 1,63 | 2,31 | 1,73 | 0,59 [0,52; 0,67] |
| `uniform` | 1,89 | 1,53 | 2,57 | 1,35 | 0,74 [0,58; 0,89] |
| `normal` | 2,98 | 0,98 | 4,08 | 1,55 | 0,73 [0,63; 0,83] |
| `lognormal` | 4,35 | 0,96 | 4,89 | 1,85 | 0,89 [0,78; 1,00] |
| `boolean` | 0,18 | 0,14 | 0,27 | 1,31 | 0,69 [0,55; 0,82] |
| `date` | 1,68 | 1,25 | 1,26 | 1,42 | 1,33 [0,89; 1,76] |
| `datetime` | 1,70 | 1,08 | 1,69 | 1,49 | 1,01 [0,69; 1,33] |
| `sex` | 1,86 | 0,91 | 5,14 | 2,88 | 0,36 [0,31; 0,42] |
| `age` | 1,34 | 0,63 | 1,84 | 1,43 | 0,73 [0,60; 0,85] |
| `first_name` | 1,69 | 0,91 | 6,02 | 2,86 | 0,28 [0,27; 0,29] |
| `first_name (pelo sexo)` | 8,10 | 5,82 | 13,33 | 10,50 | 0,61 [0,51; 0,70] |
| `last_name` | 2,22 | 0,97 | 5,35 | 3,16 | 0,41 [0,34; 0,49] |
| `sentence` | 55,60 | 8,14 | 84,91 | 16,75 | 0,65 [0,60; 0,71] |
| `cep (base completa)` | 14,10 | 2,79 | 82,98 | 78,46 | 0,17 [0,14; 0,20] |
| `address (base completa)` | 49,23 | 13,33 | 365,58 | 345,60 | 0,13 [0,13; 0,14] |
| `address(full=True) (base completa)` | 125,12 | 27,14 | 605,80 | 609,16 | 0,21 [0,20; 0,22] |
| tabela de 20 colunas | 204,89 | 45,04 | 381,66 | 172,53 | 0,54 [0,48; 0,59] |

`normal` e `lognormal` usam log e exp próprios, sem FMA nem a biblioteca do sistema, para a mesma semente dar os
mesmos bits em qualquer máquina. Os laços deles têm uma segunda cópia compilada para AVX2, escolhida na hora quando
a CPU tem; os números acima são dela (build com clang-cl, como os wheels). Sem AVX2 (ou num build local com o MSVC, o
padrão no Windows), `lognormal` fica em ~9 ns/linha, 1,8× o MVP, e o benchmark o trata como exceção.

A tabela de 20 colunas é a do benchmark do MVP (CPF, CNPJ, sexo, nome pelo sexo, sobrenome, e-mail, telefone, idade,
nascimento pela idade, renda correlacionada, CEP, UUID, IP, placa, empresa, frase com 30% de nulos, booleano, real,
inteiro e data; `TABLE_20` em `tools/bench.py`). Quase todo o tempo é das próprias colunas (a soma delas sozinhas dá
~250 ns/linha quando cada uma pede memória nova ao sistema); o planejamento e a montagem da tabela somam ~15.

Com a base completa do CNEFE (4 milhões de trechos), cada sorteio cai num lugar aleatório de tabelas maiores que o
cache do processador. Os kernels de endereço pedem a memória de 64 linhas de uma vez (prefetch), para as esperas se
sobreporem: foi o que levou o `cep` de 44 para 22 ns e o `address` de 229 para 103 ns. Na 0.2.1, o número da casa
passou a tirar o log dos limites da faixa de uma tabela pronta, e o `address` caiu para 70 ns.

## Contra outras bibliotecas

Resultado de `tools/compare.py` em `benchmarks/comparacao.md` (todas com 1 thread, locale pt_BR, saída como coluna do
Polars). As bibliotecas que geram um valor por chamada (Faker, Mimesis) ficam na casa de microssegundos por linha; a
vantagem do nini-datagen vem de gerar a coluna inteira no C++, direto na memória do Polars.

## Pontos conhecidos

- `scan`: até a 0.2.0, o motor streaming do Polars (o padrão) pedia lotes pequenos e a geração rodava um ou dois
  blocos por vez, sem paralelismo (~220 ns/linha com 16 threads, contra ~90 do `table`). A 0.2.1 ignora essa
  sugestão e gera lotes de 1.048.576 linhas (ou o `batch_size` pedido); o Polars divide o lote depois.
- Memória: os buffers grandes vêm de um pool próprio (desde a 0.3.0; na 0.2.1, o do pyarrow), que guarda até 1 GiB
  de memória liberada para a próxima geração (é o que evita pagar de novo a entrega das páginas pelo sistema). Por
  isso o processo pode continuar com essa memória depois de liberar uma tabela grande: `dg.release_memory()` devolve
  ao sistema, e `dg.pool_limit(bytes)` muda o limite (0 desliga a guarda).
- O ganho com 16 threads na tabela é de ~3,8×: parte do trabalho (planejar colunas que dependem de outras, montar a
  tabela) não divide, e escrever 228 MB por milhão de linhas esbarra na velocidade da memória.
