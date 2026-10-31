# Fontes de dados

As bases embutidas no pacote (e a base completa de endereços, baixada sob demanda) vêm de dados abertos. O código do
nini-datagen é MIT (veja LICENSE); os dados mantêm as condições das fontes abaixo.

- **IBGE** (https://www.ibge.gov.br): localidades (UFs e municípios), estimativas de população (SIDRA) e frequência de
  nomes (Censo Demográfico, API Nomes). Dados abertos (Decreto 8.777/2016). Fonte: *IBGE*.
- **IBGE, Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE), Censo Demográfico 2022**
  (https://www.ibge.gov.br/estatisticas/sociais/populacao/38734-cadastro-nacional-de-enderecos-para-fins-estatisticos.html):
  as bases de endereços (a versão reduzida, dentro do pacote, e a completa, baixada com `download`) são agregações
  (CEP x logradouro) desses dados abertos. Fonte: IBGE, CNEFE, Censo Demográfico 2022.
- **TSE, Repositório de Dados Eleitorais, candidatos 2024**
  (https://dadosabertos.tse.jus.br): usado só para estatísticas agregadas de sobrenomes e da grafia dos nomes
  (acentuação). Nenhum nome completo nem dado individual de candidato é distribuído. Fonte: *TSE*.
- **Faker / Mimesis** (listas pt_BR de apoio, quando usadas): licença MIT. Faker © Daniele Faraglia e colaboradores; Mimesis ©
  Isaak Uchakaev e colaboradores. Texto da licença: https://opensource.org/license/mit
- **Modelos de frase** (gerador `text`): texto original deste projeto, fictício.
