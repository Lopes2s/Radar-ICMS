# tests/test_consultas.py
import os
from core import pdf_text
from parsers import consultas

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

def _texto():
    return pdf_text.texto_simples(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"))

def test_detecta_tres_consultas():
    regs = consultas.parse(_texto())
    assert len(regs) == 3

def test_campos_da_primeira_consulta():
    regs = consultas.parse(_texto())
    r = regs[0]
    assert r["Nº da Consulta"] == "001"
    assert r["Data da Publicação"] == "2026-01-19"
    assert r["Ano"] == "2026"
    assert "DIFERIMENTO" in r["Súmula"]
    assert r["CNAE Detectado"] == "1623-4/00"

def test_data_extenso_para_iso():
    assert consultas._data_extenso_para_iso("19 de janeiro de 2026") == "2026-01-19"
    assert consultas._data_extenso_para_iso("20 de janeiro de 2026") == "2026-01-20"


# Regressão: consultas de 2023 (documento real "Consultas Tributarias -
# 01.2023 à 12.2023.pdf", 226 páginas) usam "CONSULTA Nº:" com dois-pontos e
# a linha de título termina em quebra de linha, sem o ponto final que o
# formato de 2026 tem. A âncora antiga exigia os dois (sem dois-pontos, com
# ponto final) e não casava nenhum dos 60 títulos reais do documento.

def test_titulo_2023_com_dois_pontos_e_sem_ponto_final():
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.708.497-9.\n"
        "CONSULTA Nº: 001, de 17 de janeiro de 2023\n"
        "ASSUNTO: ICMS. ATIVIDADE MISTA DE PRESTAÇÃO DE SERVIÇO.\n"
        "A consulente informa atuar no ramo de transporte rodoviário.\n"
        "RESPOSTA\n"
        "Diante do exposto, responde-se que...\n"
    )
    regs = consultas.parse(texto)
    assert len(regs) == 1
    r = regs[0]
    assert r["Nº da Consulta"] == "001"
    assert r["Data da Publicação"] == "2023-01-17"


def test_duas_consultas_2023_seguidas_sem_vazamento():
    # trechos verbatim do documento real de 2023, para provar que o
    # fatiamento não mistura o conteúdo de uma consulta com a seguinte
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.945.632-6\n"
        "CONSULTA Nº: 006, de 9 de fevereiro de 2023\n"
        "SÚMULA: ICMS. FERRAMENTAS PARA USO PROFISSIONAL. REDUÇÃO DE BASE "
        "DE CÁLCULO.\n"
        "A consulente, estabelecida no Estado do Rio Grande do Sul...\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
        "PROTOCOLO: 20.057.794-9.\n"
        "CONSULTA Nº: 007, de 2 de março de 2023\n"
        "SÚMULA: ICMS. FARMÁCIA DE MANIPULAÇÃO. AQUISIÇÃO DE INSUMOS.\n"
        "A consulente, optante pelo Simples Nacional...\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    regs = consultas.parse(texto)
    assert len(regs) == 2
    assert [r["Nº da Consulta"] for r in regs] == ["006", "007"]
    assert "FERRAMENTAS" in regs[0]["Súmula"]
    assert "FARMÁCIA" in regs[1]["Súmula"]


def test_nao_confunde_citacao_interna_com_titulo():
    # citações de precedentes no corpo aparecem em caixa mista ("Consulta
    # nº"), nunca em caixa alta como o título real ("CONSULTA Nº"). A âncora
    # antiga usava re.IGNORECASE e casava essas citações como se fossem
    # títulos — foi a causa dos "falsos positivos" no diagnóstico do PDF real.
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.884.315-6.\n"
        "CONSULTA Nº: 002, de 19 de janeiro de 2023\n"
        "SÚMULA: ICMS. SUBSTITUIÇÃO TRIBUTÁRIA. VENDA INTERESTADUAL.\n"
        "A consulente, atuando na importação de veículos, cita "
        "precedentes: conforme a Consulta nº 26, de 16 de março de 2021, e "
        "também a consulta nº 99, de 1 de janeiro de 2020.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    regs = consultas.parse(texto)
    assert len(regs) == 1
    assert regs[0]["Nº da Consulta"] == "002"


# Regressão: algumas consultas de 2023 (ex.: Consulta 001) usam "ASSUNTO:" no
# lugar de "SÚMULA:" para o mesmo campo — e nenhuma das duas termina no
# primeiro ponto, porque súmula e assunto costumam ter vários ("ICMS.
# DIFERIMENTO. CONDIÇÕES."). Confirmado contra o documento real de 2023: as
# 60 consultas começam o parágrafo do problema logo após o rótulo com "A
# consulente"/"A Consulente" — é esse marcador que separa os dois campos.

def test_assunto_maiusculo_preenche_sumula():
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.708.497-9.\n"
        "CONSULTA Nº: 001, de 17 de janeiro de 2023\n"
        "ASSUNTO: ICMS. ATIVIDADE MISTA DE PRESTAÇÃO DE SERVIÇO.\n"
        "A consulente informa atuar no ramo de transporte.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    r = consultas.parse(texto)[0]
    assert "ATIVIDADE MISTA" in r["Súmula"]


def test_assunto_caixa_mista_e_reconhecido():
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.708.497-9.\n"
        "CONSULTA Nº: 002, de 18 de janeiro de 2023\n"
        "Assunto: ICMS. CRÉDITO PRESUMIDO. APLICABILIDADE.\n"
        "A consulente informa que atua no ramo de laticínios.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    r = consultas.parse(texto)[0]
    assert "CRÉDITO PRESUMIDO" in r["Súmula"]


def test_sumula_maiuscula_continua_funcionando():
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.708.497-9.\n"
        "CONSULTA Nº: 003, de 20 de janeiro de 2023\n"
        "SÚMULA: ICMS. ISENÇÃO. FRUTAS CONGELADAS.\n"
        "A consulente é fabricante de conservas de frutas.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    r = consultas.parse(texto)[0]
    assert "ISENÇÃO" in r["Súmula"]


def test_sumula_com_varios_pontos_nao_vaza_para_problema__sumula():
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.708.497-9.\n"
        "CONSULTA Nº: 004, de 21 de janeiro de 2023\n"
        "SÚMULA: ICMS. DIFERIMENTO. CONDIÇÕES. SAÍDA DE MERCADORIA.\n"
        "A consulente atua no ramo de fabricação de embalagens.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    r = consultas.parse(texto)[0]
    problema = r["Problema da Consulta"]
    assert "DIFERIMENTO" not in problema
    assert "CONDIÇÕES" not in problema
    assert "fabricação de embalagens" in problema


def test_sumula_com_varios_pontos_nao_vaza_para_problema__assunto():
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.708.497-9.\n"
        "CONSULTA Nº: 005, de 22 de janeiro de 2023\n"
        "ASSUNTO: ICMS. SUBSTITUIÇÃO TRIBUTÁRIA. BASE DE CÁLCULO. AJUSTE.\n"
        "A consulente informa que revende autopeças.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    r = consultas.parse(texto)[0]
    problema = r["Problema da Consulta"]
    assert "SUBSTITUIÇÃO TRIBUTÁRIA" not in problema
    assert "BASE DE CÁLCULO" not in problema
    assert "revende autopeças" in problema


def test_problema_longo_nao_e_truncado():
    frase = ("A consulente relata que sua operação envolve diversas etapas "
             "de industrialização e comercialização de produtos variados. ")
    corpo_longo = frase * 30  # bem além dos 1200 caracteres do limite antigo
    assert len(corpo_longo) > 1200
    ultima_frase = "Esta é a última frase do problema, antes da resposta."
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.708.497-9.\n"
        "CONSULTA Nº: 006, de 23 de janeiro de 2023\n"
        "SÚMULA: ICMS. INDUSTRIALIZAÇÃO. TRATAMENTO TRIBUTÁRIO.\n"
        f"{corpo_longo}{ultima_frase}\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    r = consultas.parse(texto)[0]
    problema = r["Problema da Consulta"]
    assert ultima_frase.rstrip('.') in problema
    assert len(problema) > 1200


def test_problema_nao_inclui_texto_da_resposta():
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.708.497-9.\n"
        "CONSULTA Nº: 007, de 24 de janeiro de 2023\n"
        "SÚMULA: ICMS. TRANSPORTE. CRÉDITO.\n"
        "A consulente atua no transporte de cargas e questiona o crédito.\n"
        "RESPOSTA\n"
        "Diante do exposto, esta resposta conclui que o crédito é devido.\n"
    )
    r = consultas.parse(texto)[0]
    problema = r["Problema da Consulta"]
    assert "crédito é devido" not in problema
    assert "questiona o crédito" in problema


# Regressão: o "PROTOCOLOS:" vem na linha ANTERIOR ao título "CONSULTA Nº".
# A versão antiga procurava o protocolo dentro da fatia que começa no título
# e, por isso, atribuía a cada consulta o protocolo da consulta seguinte.

def test_protocolos_do_fixture_2026_na_consulta_certa():
    regs = consultas.parse(_texto())
    assert [r["Protocolo"] for r in regs] == [
        "25.152.191-3", "25.111.212-6", "25.163.340-1",
    ]


def test_protocolo_com_ponto_final_vem_limpo():
    texto = (
        "ANO: 2023\n"
        "PROTOCOLO: 19.708.497-9.\n"
        "CONSULTA Nº: 001, de 17 de janeiro de 2023\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente informa.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    assert consultas.parse(texto)[0]["Protocolo"] == "19.708.497-9"


def test_consulta_sem_protocolo_fica_vazia_e_nao_herda_da_seguinte():
    texto = (
        "ANO: 2023\n"
        "CONSULTA Nº: 001, de 17 de janeiro de 2023\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente informa.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
        "PROTOCOLO: 20.057.794-9.\n"
        "CONSULTA Nº: 002, de 2 de março de 2023\n"
        "SÚMULA: ICMS. Y.\n"
        "A consulente informa.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    regs = consultas.parse(texto)
    assert [r["Protocolo"] for r in regs] == ["", "20.057.794-9"]


def test_multiplos_protocolos_ficam_todos_no_campo():
    texto = (
        "ANO: 2026\n"
        "PROTOCOLOS: 25.152.191-3, 25.152.192-1 e 25.152.193-0\n"
        "CONSULTA Nº 004, de 21 de janeiro de 2026.\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente informa.\n"
        "RESPOSTA\n"
        "Diante do exposto...\n"
    )
    assert consultas.parse(texto)[0]["Protocolo"] == (
        "25.152.191-3; 25.152.192-1; 25.152.193-0"
    )


# Regressão: o regex de cabeçalho atravessava parágrafos. Uma menção à
# "Secretaria de Estado da Fazenda do Paraná" no corpo casava como início
# de cabeçalho e apagava tudo até o "SETOR CONSULTIVO" da página seguinte,
# inclusive consultas inteiras.

_CABECALHO_PAGINA = (
    "SECRETARIA DE ESTADO DA FAZENDA DO PARANÁ - SEFA\n"
    "SETOR CONSULTIVO\n"
    "__________________________________________________\n"
)


def test_mencao_a_sefa_no_corpo_nao_apaga_a_consulta_seguinte():
    texto = (
        "ANO: 2026\n"
        + _CABECALHO_PAGINA
        + "PROTOCOLOS: 25.152.191-3\n"
        "CONSULTA Nº 001, de 19 de janeiro de 2026.\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente, conforme norma da Secretaria de Estado da Fazenda "
        "do Paraná, informa FATO_A.\n"
        "RESPOSTA\n"
        "Resposta um.\n"
        "PROTOCOLOS: 25.111.212-6\n"
        "CONSULTA Nº 002, de 20 de janeiro de 2026.\n"
        "SÚMULA: ICMS. Y.\n"
        "A consulente informa FATO_C.\n"
        "RESPOSTA\n"
        "Resposta dois.\n"
        + _CABECALHO_PAGINA
        + "continuação da resposta dois.\n"
    )
    regs = consultas.parse(texto)
    assert [r["Nº da Consulta"] for r in regs] == ["001", "002"]
    assert "FATO_A" in regs[0]["Problema da Consulta"]
    assert "FATO_C" in regs[1]["Problema da Consulta"]


def test_cabecalho_de_pagina_real_continua_removido():
    regs = consultas.parse(_texto())
    for r in regs:
        assert "SETOR CONSULTIVO" not in r["Problema da Consulta"]
        assert "SEFA" not in r["Problema da Consulta"]


# Regressão: o rodapé de cada página real (linha de sublinhado + número da
# página) fica no FIM do texto extraído daquela página, não junto do
# cabeçalho da página seguinte. _CABECALHO só casava o cabeçalho; o rodapé
# da página anterior (ex.: "__________\n3") sobrava intocado bem no meio da
# frase, sempre que a quebra de página caía no meio de um campo. No PDF real
# (Consultas_1_a_3_de_2026.pdf), isso ocorre no Problema da Consulta nº 002:
# a frase "...apoio emocional e acesso a" (fim da página 3) continua em
# "recursos especializados..." (início da página 4), com o rodapé da
# página 3 sobrando entre as duas.

def test_rodape_de_pagina_real_nao_vaza_para_o_problema():
    regs = consultas.parse(_texto())
    problema_002 = [r for r in regs if r["Nº da Consulta"] == "002"][0][
        "Problema da Consulta"
    ]
    assert "acesso a recursos especializados" in problema_002
    assert "_" not in problema_002


def test_rodape_com_numero_de_pagina_de_dois_digitos_nao_vaza():
    # mesmo padrão do PDF real, mas com número de página de dois dígitos,
    # para provar que a correção não depende do exemplo específico do PDF
    texto = (
        "ANO: 2026\n"
        "PROTOCOLOS: 25.152.191-3\n"
        "CONSULTA Nº 001, de 19 de janeiro de 2026.\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente informa que o texto continua na página seguinte a\n"
        "__________________________________________________\n"
        "12\n"
        + _CABECALHO_PAGINA
        + "sem qualquer ruído no meio da frase.\n"
        "RESPOSTA\n"
        "Resposta.\n"
    )
    problema = consultas.parse(texto)[0]["Problema da Consulta"]
    assert "continua na página seguinte a sem qualquer ruído" in problema


def test_cabecalho_nao_come_numero_de_paragrafo_da_linha_seguinte():
    texto = (
        "ANO: 2026\n"
        "PROTOCOLOS: 25.152.191-3\n"
        "CONSULTA Nº 001, de 19 de janeiro de 2026.\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente informa o seguinte:\n"
        + _CABECALHO_PAGINA
        + "2023 foi o ano da primeira operação.\n"
        "RESPOSTA\n"
        "Resposta.\n"
    )
    problema = consultas.parse(texto)[0]["Problema da Consulta"]
    assert "2023 foi o ano" in problema


# ---- Ano: vem da data da própria consulta; ANO: do documento é fallback ----

def _consulta_unica(titulo, ano_doc="ANO: 2023\n"):
    return consultas.parse(
        ano_doc + "PROTOCOLO: 19.708.497-9.\n" + titulo + "\n"
        "SÚMULA: ICMS. X.\nA consulente informa.\nRESPOSTA\nDiante do exposto...\n"
    )[0]


def test_ano_vem_da_data_da_consulta_quando_difere_do_documento():
    r = _consulta_unica("CONSULTA Nº: 001, de 5 de janeiro de 2024")
    assert r["Ano"] == "2024"


def test_ano_usa_documento_quando_a_data_nao_e_reconhecida():
    r = _consulta_unica("CONSULTA Nº: 001, de 5 de jan de 2024")
    assert r["Ano"] == "2023"


def test_ano_fica_vazio_em_vez_de_lixo_sem_data_e_sem_ano_do_documento():
    r = _consulta_unica("CONSULTA Nº 010, de 5 de jan de 2026.", ano_doc="")
    assert r["Ano"] == ""


# ---- Resposta: texto completo da resposta da SEFA à consulta ----

def test_resposta_de_tamanho_normal():
    texto = (
        "ANO: 2026\n"
        "PROTOCOLOS: 25.152.191-3\n"
        "CONSULTA Nº 001, de 19 de janeiro de 2026.\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente informa.\n"
        "RESPOSTA\n"
        "Diante do exposto, a resposta é favorável ao pedido da consulente.\n"
    )
    r = consultas.parse(texto)[0]
    assert r["Resposta"] == (
        "Diante do exposto, a resposta é favorável ao pedido da consulente."
    )


def test_resposta_do_fixture_real_atravessa_quebras_de_pagina_sem_ruido():
    # a Resposta da Consulta nº 001 do PDF real atravessa a quebra das
    # páginas 1->2 e 2->3 (reaproveita a correção do rodapé da Parte 1)
    regs = consultas.parse(_texto())
    resposta_001 = regs[0]["Resposta"]
    assert "_" not in resposta_001
    assert "SETOR CONSULTIVO" not in resposta_001
    # início da resposta (pág. 1) e um trecho que só existe na pág. 3,
    # unidos sem nenhum ruído de cabeçalho/rodapé no meio
    assert "encontra-se disciplinada nos seguintes termos" in resposta_001
    assert "excluída dessa sistemática" in resposta_001
    assert "ISENÇÃO. IMUNIDADE" not in resposta_001  # já é da Consulta nº 002


# Regressão: a fatia de uma consulta vai até o INÍCIO do título da consulta
# seguinte ("CONSULTA Nº..."), mas a linha "PROTOCOLOS:" dessa próxima
# consulta fica ANTES do próprio título (ver _extrai_protocolo) — portanto
# sobra dentro da fatia atual, colada no fim da Resposta, sempre que existe
# uma consulta seguinte no mesmo documento.

def test_resposta_nao_traz_o_protocolo_da_consulta_seguinte():
    regs = consultas.parse(_texto())
    assert regs[0]["Resposta"].endswith("excluída dessa sistemática.")
    assert "PROTOCOLO" not in regs[0]["Resposta"]
    assert "PROTOCOLO" not in regs[1]["Resposta"]


def test_resposta_nao_encontrada_fica_vazia_e_nao_quebra_o_lote():
    texto = (
        "ANO: 2026\n"
        "PROTOCOLOS: 25.152.191-3\n"
        "CONSULTA Nº 001, de 19 de janeiro de 2026.\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente informa, sem que o documento traga uma resposta.\n"
        "PROTOCOLOS: 25.111.212-6\n"
        "CONSULTA Nº 002, de 20 de janeiro de 2026.\n"
        "SÚMULA: ICMS. Y.\n"
        "A consulente informa.\n"
        "RESPOSTA\n"
        "Diante do exposto, a resposta da segunda consulta.\n"
    )
    regs = consultas.parse(texto)
    assert len(regs) == 2
    assert regs[0]["Resposta"] == ""
    assert regs[1]["Resposta"] == "Diante do exposto, a resposta da segunda consulta."


# ---- CNAE: variações de rótulo, sem pontuação final, só do problema ----

def _cnae_de(problema, resposta="Diante do exposto..."):
    return consultas.parse(
        "ANO: 2026\nPROTOCOLOS: 25.152.191-3\n"
        "CONSULTA Nº 001, de 19 de janeiro de 2026.\n"
        "SÚMULA: ICMS. X.\n" + problema + "\nRESPOSTA\n" + resposta + "\n"
    )[0]["CNAE Detectado"]


def test_cnae_com_dois_pontos():
    assert _cnae_de("A consulente, CNAE: 4930-2/02, informa.") == "4930-2/02"


def test_cnae_sem_ponto_final_colado():
    assert _cnae_de("A consulente atua sob o CNAE 4930-2/02.") == "4930-2/02"


def test_cnae_com_n_ordinal():
    assert _cnae_de("A consulente, CNAE n.º 4930-2/02, informa.") == "4930-2/02"


def test_cnae_citado_so_na_resposta_nao_e_atribuido_a_consulente():
    assert _cnae_de("A consulente informa.",
                    resposta="Empresas do CNAE 1091-1/01 não se enquadram.") == ""
