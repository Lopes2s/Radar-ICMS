# tests/test_regimes.py
import os
from core import pdf_text
from parsers import regimes

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

def _texto_krona():
    return pdf_text.texto_por_colunas(os.path.join(FIX, "Regime_Krona_2col.pdf"))

def _texto_agro():
    return pdf_text.texto_por_colunas(os.path.join(FIX, "Regime_Agroantunes.pdf"))

def test_krona_captura_dois_regimes_sem_fantasmas():
    regs, descartes = regimes.parse(_texto_krona())
    numeros = sorted(r["Nº DO REGIME ESPECIAL"] for r in regs)
    assert numeros == ["9.053/2026", "9.055/2026"]
    # citações internas (8.662/2025, 6.247/2019) NÃO viram registros nem descartes
    assert all("8.662" not in d["Nº RE"] for d in descartes)

def test_krona_campos_objetivos():
    regs, _ = regimes.parse(_texto_krona())
    krona = [r for r in regs if r["Nº DO REGIME ESPECIAL"] == "9.055/2026"][0]
    assert krona["EMPRESA"] == "KRONA TUBOS E CONEXÕES LTDA"
    assert krona["CNPJ REQUERENTE"] == "00.145.602/0001-37"
    assert "Alteração do Regime Especial nº 6.247/2019" in krona["EMENTA"]

def test_agroantunes_vigencia_e_cnpj():
    regs, _ = regimes.parse(_texto_agro())
    assert len(regs) == 1
    r = regs[0]
    assert r["Nº DO REGIME ESPECIAL"] == "8.729/2025"
    assert r["CNPJ REQUERENTE"] == "54.386.340/0001-21"
    assert r["VIGÊNCIA DO RE"] == "31/12/2026"

def test_agroantunes_empresa_quebrada_em_duas_linhas_vem_inteira():
    r = regimes.parse(_texto_agro())[0][0]
    assert r["EMPRESA"] == "AGROANTUNES COMÉRCIO DE TABACOS E CEREAIS LTDA"


def test_krona_data_e_numero_do_doe():
    for r in regimes.parse(_texto_krona())[0]:
        assert r["DATA"] == "2026-08-14"
        assert r["Nº DOE"] == "12.196"


def test_beneficiaria_sem_rotulo_seguinte_usa_a_propria_linha():
    fatia = "BENEFICIÁRIA: EMPRESA X LTDA.\nTexto livre sem outros rótulos."
    assert regimes._beneficiaria(fatia) == "EMPRESA X LTDA"


def test_mes_desconhecido_nao_vira_data_invalida():
    assert regimes._data_edicao_iso("14/XYZ/2026") == "14/XYZ/2026"
    assert regimes._data_edicao_iso("14/Ago/2026") == "2026-08-14"


def test_beneficiaria_nao_engole_paragrafos_ate_um_rotulo_distante():
    fatia = ("BENEFICIÁRIA: EMPRESA X LTDA.\n"
             + "Parágrafo longo do despacho sem rótulos. " * 20
             + "\nCNPJ: 00.000.000/0001-00")
    assert regimes._beneficiaria(fatia) == "EMPRESA X LTDA"


# Um título "REGIME ESPECIAL Nº" (caixa alta) que não casou com a âncora
# completa (ex.: a linha "COORDENAÇÃO DE FISCALIZAÇÃO" foi para a outra
# coluna) não pode sumir: vira descarte "titulo_sem_ancora" para revisão.

def test_titulo_de_regime_sem_ancora_vira_descarte():
    texto = (
        "COORDENAÇÃO DE FISCALIZAÇÃO\n"
        "REGIME ESPECIAL Nº 9.001/2026\n"
        "BENEFICIÁRIA: EMPRESA A LTDA\nCNPJ: 00.000.000/0001-00\n"
        "EMENTA: Concessão de regime.\n"
        "texto que veio da outra coluna\n"
        "REGIME ESPECIAL Nº 9.002/2026\n"
        "BENEFICIÁRIA: EMPRESA B LTDA\nCNPJ: 11.111.111/0001-11\n"
        "EMENTA: Concessão de regime.\n"
    )
    regs, descartes = regimes.parse(texto)
    assert [r["Nº DO REGIME ESPECIAL"] for r in regs] == ["9.001/2026"]
    assert descartes == [
        {"Nº RE": "9.002/2026", "Motivo": "titulo_sem_ancora", "Empresa": ""},
    ]


# Regressão: regimes emitidos pela INSPETORIA GERAL DE FISCALIZAÇÃO (em vez
# da COORDENAÇÃO DE FISCALIZAÇÃO, único departamento que a âncora
# reconhecia) viravam "titulo_sem_ancora" em vez de registro — confirmado
# contra o texto real do Regime Especial nº 8.715/2025 (JAGUAFRANGOS).

def test_regime_da_inspetoria_geral_de_fiscalizacao_vira_registro():
    texto = (
        "SECRETARIA DE ESTADO DA FAZENDA\n"
        "RECEITA ESTADUAL DO PARANÁ\n"
        "INSPETORIA GERAL DE FISCALIZAÇÃO\n"
        "REGIME ESPECIAL Nº 8.715/2025\n"
        "PROTOCOLO: 23.448.040-7\n"
        "BENEFICIÁRIA: JAGUAFRANGOS IND. E COM. DE ALIMENTOS LTDA\n"
        "CAD/ICMS :61700643-03 CNPJ: 85.090.033/0001-22\n"
        "EMENTA: Implementação de tratamentos tributários.\n"
    )
    regs, descartes = regimes.parse(texto)
    assert [r["Nº DO REGIME ESPECIAL"] for r in regs] == ["8.715/2025"]
    assert descartes == []


def test_fixtures_reais_nao_geram_descarte_de_titulo_sem_ancora():
    for texto in (_texto_krona(), _texto_agro()):
        _, descartes = regimes.parse(texto)
        assert all(d["Motivo"] != "titulo_sem_ancora" for d in descartes)


# ---- ABRANGÊNCIA / BENEFÍCIOS-PROCEDIMENTOS / DISPOSIÇÕES GERAIS ----
#
# Rótulos reais confirmados no PDF de regimes (Regime_Agroantunes.pdf, já na
# suíte, e o texto verbatim do Regime Especial nº 8.715/2025 colado abaixo):
# "1. DA ABRANGÊNCIA" e "N. DAS DISPOSIÇÕES GERAIS[, complemento variável]"
# aparecem de forma estável; a seção do meio não tem rótulo estável (no
# Agroantunes são DUAS seções com títulos totalmente diferentes — "DAS
# OPERAÇÕES DE AQUISIÇÃO..." e "DAS OPERAÇÕES DE SAÍDAS..."; no Jaguafrangos
# é "DOS PROCEDIMENTOS ESPECIAIS"). Por isso BENEFÍCIOS/PROCEDIMENTOS captura
# todo o "miolo" numerado entre o fim da Abrangência e o início das
# Disposições Gerais, não importa quantas seções nem seus títulos.

def test_agroantunes_abrangencia_beneficios_e_disposicoes():
    r = regimes.parse(_texto_agro())[0][0]
    assert r["ABRANGÊNCIA"] == (
        "1.1. A disciplina de que trata este Regime Especial aplica-se "
        "exclusivamente a operações com fumo em folhas realizadas pelo "
        "estabelecimento acima identificado."
    )
    assert "AQUISIÇÃO DE FUMO EM FOLHA" in r["BENEFÍCIOS/PROCEDIMENTOS"]
    assert "SAÍDAS INTERESTADUAIS DE FUMO" in r["BENEFÍCIOS/PROCEDIMENTOS"]
    assert "DISPOSIÇÕES GERAIS" not in r["BENEFÍCIOS/PROCEDIMENTOS"]
    assert r["DISPOSIÇÕES GERAIS"].startswith(
        "4.1. A Beneficiária deve manter, em arquivo digital"
    )
    # a assinatura final não pode vazar para dentro do campo
    assert "firmam este instrumento" not in r["DISPOSIÇÕES GERAIS"]
    assert "Diretora da Receita Estadual" not in r["DISPOSIÇÕES GERAIS"]


def test_krona_nao_tem_secoes_de_regime_novo_e_fica_vazio():
    # Krona/SPAL são regimes de ALTERAÇÃO: não têm ABRANGÊNCIA/PROCEDIMENTOS/
    # DISPOSIÇÕES GERAIS — os três campos novos devem ficar vazios sem
    # quebrar a extração dos demais campos já existentes
    for r in regimes.parse(_texto_krona())[0]:
        assert r["ABRANGÊNCIA"] == ""
        assert r["BENEFÍCIOS/PROCEDIMENTOS"] == ""
        assert r["DISPOSIÇÕES GERAIS"] == ""
        assert r["EMPRESA"]  # os campos existentes continuam funcionando


# Trecho verbatim do Regime Especial nº 8.715/2025 (JAGUAFRANGOS), publicado
# pela INSPETORIA GERAL DE FISCALIZAÇÃO na Edição nº 12048 do Diário Oficial
# do Paraná: a seção "2. DOS PROCEDIMENTOS ESPECIAIS" atravessa a quebra
# entre as páginas 25 e 26 do Diário, com o cabeçalho de página (nº da
# página + dia da semana + data + edição) sobrando no meio da frase; e o
# rótulo da seção 3 vem com complemento (", VIGÊNCIA E EXTINÇÃO").
_JAGUAFRANGOS_REAL = (
    "SECRETARIA DE ESTADO DA FAZENDA\n"
    "RECEITA ESTADUAL DO PARANÁ\n"
    "INSPETORIA GERAL DE FISCALIZAÇÃO\n"
    "REGIME ESPECIAL Nº 8.715/2025\n"
    "PROTOCOLO: 23.448.040-7\n"
    "BENEFICIÁRIA: JAGUAFRANGOS IND. E COM. DE ALIMENTOS LTDA\n"
    "CAD/ICMS :61700643-03 CNPJ: 85.090.033/0001-22\n"
    "ENDEREÇO: Rod. PR-340, Lote 213/214-A - Jaguapitã - Paraná\n"
    "EMENTA: Implementação de tratamentos tributários decorrentes do Programa \n"
    "Paraná Competitivo. Protocolo de Intenções nº 019/2025. \n"
    "Diante do previsto no Parecer Técnico AAET/DIF nº 144/2025, concede-se o \n"
    "seguinte Regime Especial:\n"
    "1. DA ABRANGÊNCIA \n"
    "1.1. A disciplina de que trata este Regime Especial: \n"
    "1.1.1. Aplica-se ao estabelecimento identificado no preâmbulo deste instrumento, e \n"
    "é relacionada ao projeto de investimento de sua unidade industrial.\n"
    "2. DOS PROCEDIMENTOS ESPECIAIS \n"
    "2.1. Ficam concedidos à Beneficiária os seguintes tratamentos tributários \n"
    "diferenciados:\n"
    "2.1.9. Em relação aos subitens 2.1.4., 2.1.5 e 2.1.6 a Beneficiária deverá debitar-\n"
    "se, mensalmente, à razão de 1/48 avos do total do valor do imposto suspenso ou \n"
    "diferido, na forma prevista nos §§ 9º e 10º do Art. 74 do RICMS, aprovado pelo \n"
    "26 3ª feira | 06/Jan/2026 - Edição nº 12048\n"
    "Decreto nº 7.871/2017, e creditar-se observando o disposto no Art. 26, § 3º do \n"
    "mesmo diploma regulamentar.\n"
    "2.1.9.1. Em havendo a desincorporação do ativo, por qualquer motivo, anteriormente \n"
    "ao prazo de 48 (quarenta e oito) meses, a Beneficiária se responsabilizará pelo \n"
    "pagamento integral do imposto suspenso ou diferido.\n"
    "3. DAS DISPOSIÇÕES GERAIS, VIGÊNCIA E EXTINÇÃO \n"
    "3.1. Sujeita-se à apresentação, à Delegacia Regional da Receita à qual a Beneficiária \n"
    "está subordinada, dos documentos necessários à comprovação e homologação dos \n"
    "valores investidos no Programa Paraná Competitivo.\n"
    "3.7. Deve ser lavrado termo no Registro de Ocorrências Eletrônico - RO-e, \n"
    "mencionando, no mínimo, o número do Regime Especial, sua descrição sucinta \n"
    "e o período de vigência.\n"
    "O Secretário de Estado da Fazenda, a Diretora da Receita Estadual do Paraná e a \n"
    "Beneficiária firmam este instrumento.\n"
    "Curitiba, 02 de dezembro de 2025.\n"
)


def test_jaguafrangos_abrangencia_sem_ruido():
    r = regimes.parse(_JAGUAFRANGOS_REAL)[0][0]
    assert r["ABRANGÊNCIA"] == (
        "1.1. A disciplina de que trata este Regime Especial: 1.1.1. Aplica-se "
        "ao estabelecimento identificado no preâmbulo deste instrumento, e é "
        "relacionada ao projeto de investimento de sua unidade industrial."
    )


def test_jaguafrangos_beneficios_procedimentos_atravessa_quebra_de_pagina():
    r = regimes.parse(_JAGUAFRANGOS_REAL)[0][0]
    miolo = r["BENEFÍCIOS/PROCEDIMENTOS"]
    assert "aprovado pelo Decreto nº 7.871/2017" in miolo
    assert "Edição" not in miolo
    assert "3ª feira" not in miolo


def test_jaguafrangos_disposicoes_gerais_com_rotulo_com_complemento():
    r = regimes.parse(_JAGUAFRANGOS_REAL)[0][0]
    disposicoes = r["DISPOSIÇÕES GERAIS"]
    assert disposicoes.startswith("3.1. Sujeita-se à apresentação")
    assert "RO-e" in disposicoes
    assert "firmam este instrumento" not in disposicoes
