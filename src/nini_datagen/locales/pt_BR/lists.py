"""Listas pequenas do pt_BR, embutidas no código (as bases grandes ficam em ``data/``).

Pesos marcados como *plausíveis* são estimativas para os dados parecerem reais, não estatística oficial.
"""

from __future__ import annotations

# UF -> (nome, população no Censo 2022 do IBGE, DDDs da UF)
UFS: dict[str, tuple[str, int, tuple[int, ...]]] = {
    "AC": ("Acre", 830_018, (68,)),
    "AL": ("Alagoas", 3_127_683, (82,)),
    "AM": ("Amazonas", 3_941_613, (92, 97)),
    "AP": ("Amapá", 733_759, (96,)),
    "BA": ("Bahia", 14_141_626, (71, 73, 74, 75, 77)),
    "CE": ("Ceará", 8_794_957, (85, 88)),
    "DF": ("Distrito Federal", 2_817_381, (61,)),
    "ES": ("Espírito Santo", 3_833_712, (27, 28)),
    "GO": ("Goiás", 7_056_495, (62, 64)),
    "MA": ("Maranhão", 6_776_699, (98, 99)),
    "MG": ("Minas Gerais", 20_539_989, (31, 32, 33, 34, 35, 37, 38)),
    "MS": ("Mato Grosso do Sul", 2_757_013, (67,)),
    "MT": ("Mato Grosso", 3_658_649, (65, 66)),
    "PA": ("Pará", 8_120_131, (91, 93, 94)),
    "PB": ("Paraíba", 3_974_687, (83,)),
    "PE": ("Pernambuco", 9_058_931, (81, 87)),
    "PI": ("Piauí", 3_271_199, (86, 89)),
    "PR": ("Paraná", 11_444_380, (41, 42, 43, 44, 45, 46)),
    "RJ": ("Rio de Janeiro", 16_055_174, (21, 22, 24)),
    "RN": ("Rio Grande do Norte", 3_302_729, (84,)),
    "RO": ("Rondônia", 1_581_196, (69,)),
    "RR": ("Roraima", 636_707, (95,)),
    "RS": ("Rio Grande do Sul", 10_882_965, (51, 53, 54, 55)),
    "SC": ("Santa Catarina", 7_610_361, (47, 48, 49)),
    "SE": ("Sergipe", 2_210_004, (79,)),
    "SP": ("São Paulo", 44_411_238, (11, 12, 13, 14, 15, 16, 17, 18, 19)),
    "TO": ("Tocantins", 1_511_460, (63,)),
}

# domínios de e-mail com pesos plausíveis
EMAIL_DOMAINS: tuple[tuple[str, float], ...] = (
    ("gmail.com", 0.55), ("hotmail.com", 0.12), ("outlook.com", 0.08), ("yahoo.com.br", 0.07), ("icloud.com", 0.04),
    ("live.com", 0.03), ("uol.com.br", 0.03), ("bol.com.br", 0.02), ("terra.com.br", 0.01), ("msn.com", 0.01),
    ("protonmail.com", 0.02), ("yahoo.com", 0.02),
)  # fmt: skip

# Razão social: "Sobrenome Ramo Tipo", "Sobrenome & Sobrenome Ramo Tipo" ou "Marca Marca Ramo Tipo"
COMPANY_SECTORS = (
    "Comércio de Alimentos", "Serviços de Tecnologia", "Construções", "Transportes", "Consultoria Empresarial",
    "Material de Construção", "Restaurante", "Farmácia", "Clínica Médica", "Auto Peças", "Confecções",
    "Padaria e Confeitaria", "Informática", "Agropecuária", "Educação", "Logística", "Engenharia", "Móveis",
    "Cosméticos", "Eletrônicos", "Eventos", "Publicidade", "Contabilidade", "Imobiliária", "Academia", "Pet Shop",
    "Papelaria", "Gráfica", "Segurança", "Limpeza", "Distribuidora", "Importação e Exportação",
)  # fmt: skip
COMPANY_BRANDS = (
    "Nova", "Central", "Brasil", "Sul", "Norte", "Premium", "Master", "Top", "Real", "Bom Preço", "Vale Verde",
    "Aliança", "União", "Progresso", "Horizonte", "Estrela", "Global", "Líder", "Ouro", "Prime",
)  # fmt: skip
COMPANY_TYPES: tuple[tuple[str, float], ...] = (("LTDA", 0.55), ("ME", 0.28), ("EPP", 0.12), ("S.A.", 0.05))

# marca -> (peso da marca, ((modelo, peso), ...)): amostra plausível do mercado brasileiro de automóveis (não é FIPE)
VEHICLES: dict[str, tuple[float, tuple[tuple[str, float], ...]]] = {
    "Fiat": (0.20, (("Strada", 4), ("Argo", 3), ("Mobi", 3), ("Uno", 3), ("Toro", 2), ("Cronos", 2), ("Palio", 2),
                    ("Pulse", 1))),
    "Volkswagen": (0.16, (("Gol", 4), ("Polo", 3), ("T-Cross", 3), ("Nivus", 2), ("Saveiro", 2), ("Virtus", 2),
                          ("Fox", 2), ("Jetta", 1))),
    "Chevrolet": (0.17, (("Onix", 5), ("Tracker", 3), ("S10", 2), ("Prisma", 2), ("Celta", 2), ("Spin", 1),
                         ("Cruze", 1), ("Montana", 1))),
    "Hyundai": (0.09, (("HB20", 6), ("Creta", 3), ("HB20S", 1), ("ix35", 1))),
    "Toyota": (0.08, (("Corolla", 4), ("Hilux", 3), ("Yaris", 2), ("Etios", 2), ("SW4", 1), ("Corolla Cross", 2))),
    "Honda": (0.07, (("Civic", 3), ("HR-V", 3), ("Fit", 2), ("City", 2), ("CR-V", 1))),
    "Renault": (0.07, (("Kwid", 4), ("Sandero", 3), ("Duster", 2), ("Logan", 2), ("Captur", 1))),
    "Jeep": (0.04, (("Renegade", 3), ("Compass", 3), ("Commander", 1))),
    "Ford": (0.06, (("Ka", 4), ("EcoSport", 3), ("Fiesta", 2), ("Ranger", 2), ("Focus", 1))),
    "Nissan": (0.03, (("Kicks", 3), ("Versa", 2), ("March", 2), ("Frontier", 1))),
    "Peugeot": (0.015, (("208", 3), ("2008", 2), ("206", 1))),
    "Citroën": (0.015, (("C3", 4), ("C4 Cactus", 2), ("Aircross", 1))),
}  # fmt: skip

# profissões, da mais para a menos comum (pesos de Zipf suaves; ordem plausível, não estatística oficial)
OCCUPATIONS = (
    "Vendedor", "Auxiliar administrativo", "Professor", "Motorista", "Técnico de enfermagem", "Pedreiro",
    "Auxiliar de limpeza", "Cozinheiro", "Operador de caixa", "Analista de sistemas", "Contador", "Enfermeiro",
    "Advogado", "Engenheiro civil", "Médico", "Eletricista", "Mecânico", "Recepcionista", "Gerente comercial",
    "Desenvolvedor de software", "Pintor", "Costureira", "Padeiro", "Agricultor", "Segurança", "Porteiro",
    "Cabeleireiro", "Atendente de telemarketing", "Assistente financeiro", "Farmacêutico", "Dentista", "Psicólogo",
    "Arquiteto", "Designer gráfico", "Analista de dados", "Cientista de dados", "Administrador", "Economista",
    "Fisioterapeuta", "Nutricionista", "Jornalista", "Publicitário", "Bancário", "Corretor de imóveis", "Entregador",
    "Estoquista", "Garçom", "Barbeiro", "Soldador", "Encanador", "Marceneiro", "Operador de máquinas", "Zelador",
    "Babá", "Diarista", "Autônomo", "Empresário", "Servidor público", "Policial militar", "Bombeiro", "Piloto",
    "Veterinário", "Biólogo", "Químico", "Matemático", "Estatístico", "Fotógrafo", "Músico", "Ator", "Personal trainer",
    "Manicure", "Frentista",
)  # fmt: skip

# complementos de endereço (sorteio uniforme)
ADDRESS_COMPLEMENTS = (
    *(f"Apto {a}" for a in (11, 12, 21, 22, 31, 32, 41, 42, 51, 52, 61, 62, 71, 72)),
    *(f"Apto {a}" for a in (101, 102, 201, 202, 301, 302, 401, 402)),
    *(f"Casa {a}" for a in (1, 2, 3, 4, 5, 6)),
    *(f"Bloco {b} Apto {a}" for b in "ABC" for a in (11, 22, 33, 44)),
    *(f"Sala {a}" for a in (1, 2, 3, 4, 5, 10, 12, 101, 201, 301)),
    "Fundos", "Térreo", "Loja", "Sobrado",
)  # fmt: skip
