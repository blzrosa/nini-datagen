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

## Documentos e rede

**cpf** (199,969 distintos em 200,000): `48958531444` · `68215459528` · `05703808472` · `73570303268` · `48810136454` · `89400876661`

**cpf(formatted, unique)** (200,000 distintos em 200,000): `814.184.500-49` · `196.632.845-10` · `189.065.525-21` · `732.847.854-34` · `300.604.861-04` · `646.072.991-38`

**cnpj(formatted)** (199,787 distintos em 200,000): `81.286.984/0001-10` · `99.561.408/0001-08` · `16.458.523/0001-16` · `39.910.916/0001-14` · `21.928.972/0001-10` · `81.783.645/0001-40`

**cnpj(alphanumeric, formatted)** (200,000 distintos em 200,000): `NY.DYJ.44H/0001-60` · `9M.IR0.6U7/0001-51` · `JB.4FN.345/0001-42` · `DL.BNI.3F3/0001-05` · `JE.ZEA.DZF/0001-00` · `LE.J3R.BYO/0001-02`

**cnpj(branch=None)** (200,000 distintos em 200,000): `21996254053544` · `87552414365622` · `09876046967982` · `29321876909675` · `29842361156760` · `98628397717205`

**pis(formatted)** (199,999 distintos em 200,000): `881.79980.75-4` · `175.32006.99-7` · `397.83606.36-8` · `557.19583.77-0` · `739.49106.34-3` · `999.65936.52-9`

**voter_id(formatted)** (199,990 distintos em 200,000): `1572 1111 0981` · `3074 2381 1465` · `1005 3667 0507` · `3967 5760 0604` · `8785 8690 1236` · `0711 7252 2216`

**cnh** (199,979 distintos em 200,000): `85191845239` · `99003089123` · `71799408975` · `25124053632` · `46572728563` · `43928054668`

**rg(formatted)** (199,796 distintos em 200,000): `48.083.273-0` · `67.844.459-6` · `60.934.576-X` · `49.032.933-0` · `19.198.612-4` · `60.069.248-6`

**license_plate** (199,956 distintos em 200,000): `EXZ6Y08` · `PUH5R18` · `ZDB7A31` · `SBJ2U93` · `FCZ1B41` · `NOQ0G33`

**license_plate(old)** (199,878 distintos em 200,000): `HYT-6520` · `CKN-3807` · `OJF-5389` · `ILC-4360` · `TTY-3141` · `YUG-5787`

**credit_card(formatted)** (200,000 distintos em 200,000): `4210 5936 8564 6194` · `5136 9168 0523 7628` · `5271 7951 0339 4793` · `4692 0326 4555 2793` · `5521 5500 8907 1297` · `4283 1186 4612 3752`

**iban** (200,000 distintos em 200,000): `BR3486862340053134348869678P1` · `BR9646277704280364469475425C1` · `BR3559363624563267643229911P1` · `BR3053662814300686210205945P1` · `BR2779128013550755113727558P1` · `BR7381236350490804263249739P1`

**ean13** (199,977 distintos em 200,000): `7896402877417` · `7899100081827` · `7895924134213` · `7890479507826` · `7896839229919` · `7893744801285`

**uuid** (200,000 distintos em 200,000): `8586b5be-f549-4dd6-9d8b-b4887a4b5f13` · `b5c7f1fa-b7ac-49a0-82b1-41a5d1110e33` · `e500d461-395f-4ec2-82a0-7ffe67ffd953` · `c2670b50-d21b-485b-99f4-ed26540ac7dc` · `f37c7108-f689-482b-bddc-3bdc3bbb0b31` · `62da7402-6234-48ba-953c-77063caf22e4`

**ipv4** (199,994 distintos em 200,000): `64.12.159.194` · `37.219.41.48` · `142.107.33.137` · `96.13.173.111` · `149.14.161.152` · `77.120.221.88`

**ipv4(private)** (172,972 distintos em 200,000): `192.168.90.151` · `172.28.235.20` · `192.168.34.216` · `10.53.129.35` · `172.20.166.42` · `192.168.243.248`

**ipv6** (200,000 distintos em 200,000): `b148:2c6d:a60d:7dad:6501:39e4:9775:4e25` · `53c0:fbdc:4f7a:2f19:fe9b:d47f:6003:6f6d` · `6bfc:dc5b:c5fb:b7a5:5e1c:dd35:2e19:57cf` · `eb24:213c:4030:8e8b:c85f:3705:8cb8:8f20` · `e02e:16c4:8a14:7327:4d46:0b35:a8c7:ead1` · `ce7f:016f:2d6e:0fde:8510:d04c:8b6b:8e0a`

**mac** (200,000 distintos em 200,000): `2e:78:33:c3:72:16` · `76:8b:d9:d8:ce:4d` · `58:69:7f:cf:9a:3c` · `86:1a:af:f0:28:a8` · `a4:51:71:10:d6:c9` · `f8:b7:52:a7:1e:2d`

**url** (150,085 distintos em 200,000): `https://banco.com.br/foto/farmacia` · `https://www.novidades.com.br/esporte` · `https://planos-saude.com.br/login` · `https://www.verde.edu.br/games/tech/turismo` · `https://www.express-carrinho.com.br` · `https://www.pet.com/construcao`

**phone** (199,998 distintos em 200,000): `33940201908` · `6254940974` · `37955189844` · `32905839400` · `85938422380` · `6931968632`

**phone(masked, uf=SP)** (199,983 distintos em 200,000): `(19) 92076-2792` · `(14) 93348-6980` · `(11) 91067-6481` · `(18) 98666-6354` · `(11) 97131-0962` · `(18) 3351-4139`

**email** (148,050 distintos em 200,000): `claudiaalves16@gmail.com` · `oliveira.marlene@gmail.com` · `marciasilva89@yahoo.com.br` · `silva.patricia@gmail.com` · `francisconeri1993@icloud.com` · `francisco_silva@gmail.com`

**username** (119,192 distintos em 200,000): `mferreira` · `laercio.araujo` · `bispo.orlando` · `leonardo.santos` · `marcos_evangelista` · `julianasouza`

**company** (96,732 distintos em 200,000): `Nova Ouro Comércio de Alimentos LTDA` · `Silva & Reis Auto Peças ME` · `Sperança & Lima Farmácia LTDA` · `Nova Bom Preço Papelaria S.A.` · `Ramos Agropecuária LTDA` · `Dias & Rodrigues Contabilidade LTDA`

**occupation** (72 distintos em 200,000): `Médico` · `Analista de sistemas` · `Técnico de enfermagem` · `Advogado` · `Padeiro` · `Advogado`

## Frases (6 de cada)

**sentence** (28,853 distintas em 200,000)

- Não compraria novamente.
- Reembolso de R$ 439,78 em análise.
- A titular relatou que o site apresenta erro ao fazer login desde segunda-feira.
- O preço compensa pela qualidade.
- O cliente solicitou a devolução do pedido.
- A dependente apresentou o comprovante de residência para atualização cadastral.

**sentence(theme=atendimento)** (40,361 distintas em 200,000)

- Protocolo 6593751234 registrado pelo WhatsApp; prazo de retorno em até 72 horas.
- O cliente entrou em contato pelo site para negociar um débito em atraso.
- Protocolo 7426247512 registrado pelo site; prazo de retorno no próximo dia útil.
- O cliente pediu o estorno da última cobrança; prazo de resposta em até 7 dias úteis.
- O cliente entrou em contato pelo WhatsApp para alterar a forma de pagamento.
- Informado o prazo de resposta de 10 dias úteis.

**sentence(theme=saude)** (21,599 distintas em 200,000)

- A beneficiária solicitou autorização para consulta com dermatologista.
- Reembolso de R$ 627,00 aguardando documentação complementar.
- Reembolso de R$ 6.745,10 negado por falta de nota fiscal.
- Atendimento realizado no consultório pela segunda vez nesta semana.
- O dependente solicitou autorização para procedimento ambulatorial.
- O titular solicitou autorização para consulta com ortopedista.

**sentence(theme=entrega)** (34,917 distintas em 200,000)

- Transportadora informou que a entrega foi concluída com assinatura do porteiro.
- Primeira tentativa de entrega sem sucesso: endereço não localizado.
- Código de rastreio CC021499028BR atualizado pela segunda vez nesta semana.
- Primeira tentativa de entrega sem sucesso: estabelecimento fechado.
- Transportadora informou aumento no volume de entregas.
- Código de rastreio MS319567579BR atualizado ontem.

**sentence(theme=avaliacao)** (2,371 distintas em 200,000)

- A capinha chegou bem embalada.
- Entrega rápida e a embalagem veio bem protegida.
- A camiseta chegou bem embalada, mas o preço subiu logo depois.
- Entrega com alguns dias de atraso e ninguém respondeu às minhas mensagens.
- Na primeira semana, estou muito satisfeito.
- A fritadeira é menor do que eu esperava e o preço subiu logo depois.

**sentence(theme=cadastro)** (8,590 distintas em 200,000)

- Senha de acesso redefinida pelo site nesta manhã.
- Telefone alterado a pedido do titular.
- Divergência no e-mail de contato.
- Cadastro validado no dia 06/05 pelo site.
- Cliente com histórico de atraso nos pagamentos.
- Dados conferidos e aprovados pela equipe de compliance.

**paragraph** (199,908 distintas em 200,000)

- O kit é bonito, mas o acabamento poderia ser melhor. O fone não é igual ao anunciado. A jaqueta é menor do que eu esperava e a embalagem chegou amassada. O kit funciona perfeitamente. Não compraria novamente.
- Cadastro bloqueado hoje por telefone. Divergência entre o CPF informado e o nome cadastrado. Nome social alterado a pedido do titular. RG validado com sucesso. Registro arquivado por inatividade. Dados bancários atualizados pelo site.
- O tênis deixou a desejar e o preço subiu logo depois. O ventilador esquenta demais. Não compraria novamente. A cadeira tem ótimo custo-benefício, mas a cor é diferente da foto.
- Reembolso de R$ 255,39 negado por falta de nota fiscal. Reembolso de R$ 4.176,92 em análise. O titular recebeu orientação para aguardar o contato da central. Agendado retorno com cardiologista para o início do próximo mês. A dependente solicitou autorização para exame de mamografia.
- A central de atendimento orientou a solicitante a aguardar o contato do setor comercial. O atendente orientou a usuária a aguardar o contato do setor jurídico. O solicitante entrou em contato pelo WhatsApp com dúvidas sobre a fatura. A titular relatou que não consegue acessar o aplicativo há 15 dias.
- A cliente reclamou da demora no atendimento. A cliente relatou que aguarda o reembolso prometido desde ontem. Atendimento encerrado sem pendências. O atendente orientou a titular a atualizar o aplicativo para a versão mais recente.

## Veículos

```
shape: (12, 3)
┌────────────┬─────────┬──────┐
│ brand      ┆ model   ┆ year │
│ ---        ┆ ---     ┆ ---  │
│ str        ┆ str     ┆ i32  │
╞════════════╪═════════╪══════╡
│ Ford       ┆ Ranger  ┆ 2017 │
│ Ford       ┆ Ka      ┆ 2023 │
│ Volkswagen ┆ Nivus   ┆ 2021 │
│ Fiat       ┆ Mobi    ┆ 2024 │
│ Jeep       ┆ Compass ┆ 2015 │
│ …          ┆ …       ┆ …    │
│ Fiat       ┆ Pulse   ┆ 2023 │
│ Ford       ┆ Ranger  ┆ 2018 │
│ Chevrolet  ┆ S10     ┆ 2018 │
│ Fiat       ┆ Mobi    ┆ 2019 │
│ Fiat       ┆ Strada  ┆ 2021 │
└────────────┴─────────┴──────┘
```

Marcas: Fiat (20.0%), Chevrolet (17.1%), Volkswagen (15.9%), Hyundai (8.9%), Toyota (8.0%), Renault (7.0%), Honda (7.0%), Ford (6.0%), Jeep (4.0%), Nissan (3.0%), Peugeot (1.5%), Citroën (1.5%)

## Endereços (base full: 4,035,259 trechos)

```
shape: (12, 10)
┌─────────────────────────────────┬────────┬─────────────────┬──────────────────────┬───────────────────────┬───────┬───────────┬─────────────────┬──────────┬───────────┐
│ street                          ┆ number ┆ complement      ┆ neighborhood         ┆ city                  ┆ state ┆ cep       ┆ phone           ┆ latitude ┆ longitude │
│ ---                             ┆ ---    ┆ ---             ┆ ---                  ┆ ---                   ┆ ---   ┆ ---       ┆ ---             ┆ ---      ┆ ---       │
│ str                             ┆ i32    ┆ str             ┆ str                  ┆ str                   ┆ str   ┆ str       ┆ str             ┆ f64      ┆ f64       │
╞═════════════════════════════════╪════════╪═════════════════╪══════════════════════╪═══════════════════════╪═══════╪═══════════╪═════════════════╪══════════╪═══════════╡
│ Rua João Ferreira de Paiva      ┆ 90     ┆ null            ┆ Centro               ┆ Porto Firme           ┆ MG    ┆ 36568-000 ┆ (37) 93016-1194 ┆ -20.6704 ┆ -43.0917  │
│ Rua José de Alencar             ┆ 33     ┆ null            ┆ Selectas             ┆ Xinguara              ┆ PA    ┆ 68557-145 ┆ (94) 98709-8593 ┆ -7.109   ┆ -49.9562  │
│ Avenida Rui Barbosa             ┆ 229    ┆ null            ┆ Gramacho             ┆ Duque de Caxias       ┆ RJ    ┆ 25055-260 ┆ (21) 98069-7381 ┆ -22.7535 ┆ -43.2828  │
│ Edf Qi 23 Lote 3 Edifício Milão ┆ 531    ┆ null            ┆ Guará II             ┆ Brasília              ┆ DF    ┆ 71060-631 ┆ (61) 90649-3200 ┆ -15.8281 ┆ -47.9827  │
│ Rua Hamilton Veran              ┆ 245    ┆ null            ┆ Jardim São Conrado   ┆ Campo Grande          ┆ MS    ┆ 79093-201 ┆ (67) 93656-5950 ┆ -20.4947 ┆ -54.6746  │
│ Rua Cinquenta e Três            ┆ 80     ┆ null            ┆ Jardim Paulista      ┆ Paulista              ┆ PE    ┆ 53409-570 ┆ (87) 95589-8236 ┆ -7.9493  ┆ -34.8985  │
│ Avenida Elias Jorge Daniel      ┆ 159    ┆ null            ┆ Vila Aparecida       ┆ Capão Bonito          ┆ SP    ┆ 18303-000 ┆ (17) 3818-9897  ┆ -23.9798 ┆ -48.3458  │
│ Rua Ataliba Caldas              ┆ 154    ┆ null            ┆ São Deocleciano      ┆ São José do Rio Preto ┆ SP    ┆ 15057-040 ┆ (12) 93701-9712 ┆ -20.7939 ┆ -49.3473  │
│ Avenida Jacobus Baldi           ┆ 371    ┆ null            ┆ Cidade Fim de Semana ┆ São Paulo             ┆ SP    ┆ 05847-000 ┆ (19) 93737-2926 ┆ -23.6548 ┆ -46.7478  │
│ Avenida das Avencas             ┆ 670    ┆ null            ┆ Portal dos Ipês 3    ┆ Cajamar               ┆ SP    ┆ 07791-080 ┆ (14) 91113-8994 ┆ -23.4024 ┆ -46.8552  │
│ Rua Vieira de Morais            ┆ 667    ┆ null            ┆ Campo Belo           ┆ São Paulo             ┆ SP    ┆ 04617-012 ┆ (17) 92027-9839 ┆ -23.6196 ┆ -46.6748  │
│ Povoado Olho Dagua              ┆ 25     ┆ Bloco B Apto 33 ┆ Olho Dagua           ┆ Uibaí                 ┆ BA    ┆ 44950-000 ┆ (77) 93547-5625 ┆ -11.3829 ┆ -42.102   │
└─────────────────────────────────┴────────┴─────────────────┴──────────────────────┴───────────────────────┴───────┴───────────┴─────────────────┴──────────┴───────────┘
```

Endereço completo:

- Rua João Ferreira de Paiva, 90 - Centro, Porto Firme - MG, 36568-000
- Rua José de Alencar, 33 - Selectas, Xinguara - PA, 68557-145
- Avenida Rui Barbosa, 229 - Gramacho, Duque de Caxias - RJ, 25055-260
- Edf Qi 23 Lote 3 Edifício Milão, 531 - Guará II, Brasília - DF, 71060-631
- Rua Hamilton Veran, 245 - Jardim São Conrado, Campo Grande - MS, 79093-201
- Rua Cinquenta e Três, 80 - Jardim Paulista, Paulista - PE, 53409-570
- Avenida Elias Jorge Daniel, 159 - Vila Aparecida, Capão Bonito - SP, 18303-000
- Rua Ataliba Caldas, 154 - São Deocleciano, São José do Rio Preto - SP, 15057-040
- Avenida Jacobus Baldi, 371 - Cidade Fim de Semana, São Paulo - SP, 05847-000
- Avenida das Avencas, 670 - Portal dos Ipês 3, Cajamar - SP, 07791-080
- Rua Vieira de Morais, 667 - Campo Belo, São Paulo - SP, 04617-012
- Povoado Olho Dagua, 25 - Olho Dagua, Uibaí - BA, 44950-000

UFs: SP (21.1%), MG (10.9%), RJ (8.1%), BA (8.1%), RS (5.9%), PR (5.5%), PE (4.5%), CE (4.2%), SC (3.7%), GO (3.6%)
Número: mediana 86, máximo 99999; complemento em 24.9%

CEP (só SP): `03165-001` · `18701-220` · `14120-000` · `05857-210` · `18547-160` · `09781-270` · `12225-790` · `05524-160`

Cidades (pela população): São Paulo (5.6%), Rio de Janeiro (3.1%), Brasília (1.4%), Fortaleza (1.2%), Salvador (1.2%), Belo Horizonte (1.1%), Manaus (1.0%), Curitiba (0.9%), Recife (0.7%), Goiânia (0.7%)

UFs (pela população): SP (21.8%), MG (10.2%), RJ (8.0%), BA (6.9%), PR (5.7%), RS (5.4%)

