# Amostras do nini-datagen

seed = 2026 · 0.2.0.dev0

## Primeiras linhas

```
shape: (12, 14)
┌───────────────┬──────────┬───────────────┬─────────────────┬────────────────┬────────────┬────────────────────────────┬────────┬─────┬─────┬────────────┬────────────┬──────────────────────────────────┬───────────────────────────────┐
│ integer(1..6) ┆ uniform  ┆ normal(10, 2) ┆ lognormal(8, 1) ┆ boolean(p=0.3) ┆ date       ┆ datetime                   ┆ choice ┆ sex ┆ age ┆ first_name ┆ last_name  ┆ full_name                        ┆ full_name(null_fraction=0.1)  │
│ ---           ┆ ---      ┆ ---           ┆ ---             ┆ ---            ┆ ---        ┆ ---                        ┆ ---    ┆ --- ┆ --- ┆ ---        ┆ ---        ┆ ---                              ┆ ---                           │
│ i32           ┆ f64      ┆ f64           ┆ f64             ┆ bool           ┆ date       ┆ datetime[μs]               ┆ str    ┆ str ┆ i32 ┆ str        ┆ str        ┆ str                              ┆ str                           │
╞═══════════════╪══════════╪═══════════════╪═════════════════╪════════════════╪════════════╪════════════════════════════╪════════╪═════╪═════╪════════════╪════════════╪══════════════════════════════════╪═══════════════════════════════╡
│ 2             ┆ 0.502215 ┆ 8.901544      ┆ 1892.493538     ┆ false          ┆ 2001-02-25 ┆ 2023-09-20 18:33:27.186878 ┆ prata  ┆ M   ┆ 83  ┆ José       ┆ Nascimento ┆ João Paulo Gomes Costa           ┆ Maria Nelma Ferreira Santos   │
│ 2             ┆ 0.030375 ┆ 15.041382     ┆ 5925.589133     ┆ false          ┆ 2016-05-11 ┆ 2005-08-13 04:27:49.802138 ┆ bronze ┆ F   ┆ 5   ┆ Taísa      ┆ Nery       ┆ Cibele Cardozo Nascimento        ┆ Gabriel Conceição Ferreira    │
│ 5             ┆ 0.982939 ┆ 9.391207      ┆ 538.299014      ┆ false          ┆ 2001-05-25 ┆ 2000-01-24 03:55:10.640754 ┆ ouro   ┆ M   ┆ 12  ┆ José       ┆ Rocha      ┆ Luiz Bitencourt Reis             ┆ Raimundo Teixeira Cavalcanti  │
│ 6             ┆ 0.218825 ┆ 9.9794        ┆ 6070.092724     ┆ false          ┆ 2011-05-24 ┆ 2001-05-10 19:59:21.718914 ┆ bronze ┆ M   ┆ 4   ┆ João       ┆ Santos     ┆ Marcos Fábio Abreu               ┆ Carlos Koshiyama Pinheiro     │
│ 6             ┆ 0.557227 ┆ 13.042956     ┆ 12098.129301    ┆ false          ┆ 2000-11-26 ┆ 2018-11-10 16:39:55.769903 ┆ prata  ┆ M   ┆ 13  ┆ Zacarias   ┆ Catarino   ┆ João Paulo Alves Oliveira        ┆ Olívia Freitas Siqueira       │
│ 6             ┆ 0.513697 ┆ 10.553132     ┆ 6942.877018     ┆ true           ┆ 2005-05-12 ┆ 2002-07-19 09:51:17.659311 ┆ bronze ┆ M   ┆ 38  ┆ Luiz       ┆ de Paula   ┆ Valdomiro Huguenin               ┆ Pedro Henrique Valandro Silva │
│ 4             ┆ 0.616965 ┆ 11.343015     ┆ 21307.992893    ┆ true           ┆ 2002-03-03 ┆ 2014-08-29 21:25:04.502227 ┆ bronze ┆ F   ┆ 49  ┆ Antônio    ┆ Domingos   ┆ Maria Gabriela Silva Machado     ┆ Maria Rebeca Gomes Silva      │
│ 4             ┆ 0.02661  ┆ 10.530246     ┆ 1819.512686     ┆ true           ┆ 2001-06-11 ┆ 2007-11-26 17:23:03.835088 ┆ ouro   ┆ M   ┆ 19  ┆ Juliana    ┆ Teixeira   ┆ Márcio Sousa Brandão             ┆ José Melo Mota                │
│ 2             ┆ 0.760463 ┆ 11.398302     ┆ 1156.569732     ┆ true           ┆ 2010-07-25 ┆ 2005-02-18 12:30:37.938465 ┆ prata  ┆ M   ┆ 43  ┆ Francisco  ┆ Lima       ┆ Antônio Lourival Quintão Pacheco ┆ Manuel Coelho Souza           │
│ 4             ┆ 0.033589 ┆ 11.862752     ┆ 11532.704192    ┆ true           ┆ 2005-01-19 ┆ 2015-11-03 15:07:27.810695 ┆ bronze ┆ F   ┆ 1   ┆ Jorge      ┆ Silva      ┆ Patrícia Costa Barreto           ┆ Silas Pereira Diniz           │
│ 3             ┆ 0.262513 ┆ 9.181303      ┆ 652.250681      ┆ false          ┆ 2020-05-20 ┆ 2008-10-04 22:00:26.197420 ┆ prata  ┆ F   ┆ 6   ┆ Rosália    ┆ Silva      ┆ Juliana Soler Lima               ┆ João Pinto Silva              │
│ 4             ┆ 0.346125 ┆ 6.658577      ┆ 1924.274588     ┆ true           ┆ 2008-09-19 ┆ 2011-01-07 15:20:51.610999 ┆ prata  ┆ M   ┆ 69  ┆ Ana        ┆ Matos      ┆ Geraldo Reis Souza               ┆ Francisca Sousa Knorst        │
└───────────────┴──────────┴───────────────┴─────────────────┴────────────────┴────────────┴────────────────────────────┴────────┴─────┴─────┴────────────┴────────────┴──────────────────────────────────┴───────────────────────────────┘
```

## Resumo (200 mil linhas)

| coluna | tipo | nulos | distintos | mais comuns |
|---|---|---:|---:|---|
| integer(1..6) | Int32 | 0 | 6 | 6 (16.8%), 5 (16.7%), 2 (16.7%), 4 (16.7%), 3 (16.6%) |
| uniform | Float64 | 0 | 200,000 | 0.5022154316962373 (0.0%), 0.030375132217437595 (0.0%), 0.982939229633272 (0.0%), 0.21882527746958413 (0.0%), 0.5572266468062518 (0.0%) |
| normal(10, 2) | Float64 | 0 | 200,000 | 8.90154370672057 (0.0%), 15.041382074941966 (0.0%), 9.391207154613967 (0.0%), 9.979399753279498 (0.0%), 13.04295552580828 (0.0%) |
| lognormal(8, 1) | Float64 | 0 | 200,000 | 1892.4935382175586 (0.0%), 5925.589132651272 (0.0%), 538.2990140379617 (0.0%), 6070.09272363705 (0.0%), 12098.129300909244 (0.0%) |
| boolean(p=0.3) | Boolean | 0 | 2 | False (70.0%), True (30.0%) |
| date | Date | 0 | 9,497 | 2007-02-03 (0.0%), 2016-01-03 (0.0%), 2006-04-29 (0.0%), 2000-03-22 (0.0%), 2013-05-19 (0.0%) |
| datetime | Datetime(time_unit='us', time_zone=None) | 0 | 200,000 | 2023-09-20 18:33:27.186878 (0.0%), 2005-08-13 04:27:49.802138 (0.0%), 2000-01-24 03:55:10.640754 (0.0%), 2001-05-10 19:59:21.718914 (0.0%), 2018-11-10 16:39:55.769903 (0.0%) |
| choice | String | 0 | 3 | bronze (60.1%), prata (29.9%), ouro (9.9%) |
| sex | String | 0 | 2 | F (51.4%), M (48.6%) |
| age | Int32 | 0 | 100 | 20 (1.5%), 33 (1.5%), 4 (1.5%), 15 (1.5%), 2 (1.5%) |
| first_name | String | 0 | 1,366 | Maria (10.4%), José (5.1%), Ana (2.7%), João (2.6%), Antônio (2.2%) |
| first_name(sex=coluna) | String | 0 | 1,365 | Maria (10.9%), José (4.7%), Ana (2.8%), João (2.5%), Antônio (2.2%) |
| last_name | String | 0 | 6,492 | Silva (12.9%), Santos (7.5%), Oliveira (4.4%), Souza (3.4%), Lima (2.0%) |
| full_name | String | 0 | 172,670 | Maria Silva (0.2%), Maria Santos (0.1%), José Silva (0.1%), Maria Silva Santos (0.1%), Maria Santos Silva (0.1%) |
| full_name(null_fraction=0.1) | String | 19,935 | 156,469 | None (10.0%), Maria Silva (0.2%), Maria Santos (0.1%), José Silva (0.1%), Maria Silva Santos (0.1%) |

## Nomes por sexo

F: Maria (21,769), Ana (5,689), Francisca (1,366), Patrícia (1,085), Antônia (1,077), Juliana (1,050), Adriana (1,028), Márcia (1,003), Aline (972), Fernanda (966), Bruna (909), Sandra (893), Amanda (891), Camila (887), Jéssica (881)

M: José (9,388), João (5,045), Antônio (4,319), Francisco (3,096), Carlos (2,538), Paulo (2,358), Pedro (2,025), Luiz (1,937), Marcos (1,863), Lucas (1,829), Luís (1,571), Gabriel (1,467), Rafael (1,431), Daniel (1,209), Marcelo (1,206)

## 30 nomes completos

- João Paulo Gomes Costa
- Cibele Cardozo Nascimento
- Luiz Bitencourt Reis
- Marcos Fábio Abreu
- João Paulo Alves Oliveira
- Valdomiro Huguenin
- Maria Gabriela Silva Machado
- Márcio Sousa Brandão
- Antônio Lourival Quintão Pacheco
- Patrícia Costa Barreto
- Juliana Soler Lima
- Geraldo Reis Souza
- Beatriz Silva Ferreira
- Leandro Santos Ribeiro
- Antônio Fábio Vargas
- Otávio Oliveira Pereira
- Amanda Cáceres Santos
- Francisca Bosa Fragas
- Marcos Bispo Vicente
- Ana Santos Pires
- Maria Sônia Amaral Barros
- Ana Maria Giovanini Lopes
- Davi Souza Santos
- Maria Sandra Oliveira Nunes
- Júlia Santos Tosin
- Bruna Silva
- Aparecida Ferreira Sousa
- Kelly Ângelo
- Eduardo Santana de Jesus
- Antônio Santos Lopes
