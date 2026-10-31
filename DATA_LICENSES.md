# Fontes de dados

As bases embutidas no pacote (e a base completa de endereços, baixada sob demanda) vêm de dados abertos. O código do
nini-datagen é MIT (veja LICENSE); os dados mantêm as condições das fontes abaixo.

- **IBGE** (https://www.ibge.gov.br): localidades (UFs e municípios), estimativas de população (SIDRA) e frequência de
  nomes (Censo Demográfico, API Nomes; `locales/pt_BR/data/first_names.tsv`). Dados abertos (Decreto 8.777/2016).
  Fonte: *IBGE*.
- **IBGE, Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE), Censo Demográfico 2022**
  (https://www.ibge.gov.br/estatisticas/sociais/populacao/38734-cadastro-nacional-de-enderecos-para-fins-estatisticos.html):
  as bases de endereços (a versão reduzida, dentro do pacote, e a completa, baixada com `download`) são agregações
  (CEP x logradouro) desses dados abertos. Fonte: IBGE, CNEFE, Censo Demográfico 2022.
- **TSE, Repositório de Dados Eleitorais, candidatos 2024**
  (https://dadosabertos.tse.jus.br): usado só para estatísticas agregadas: frequência de sobrenomes
  (`locales/pt_BR/data/last_names.tsv`, sobrenomes com pelo menos 3 pessoas) e grafia acentuada dos primeiros nomes.
  Nenhum nome completo nem dado individual de candidato é distribuído. Fonte: *TSE*.
- **Modelos de frase** (gerador `text`): texto original deste projeto, fictício.
