# tests/test_pdf_text.py
import os
from core import pdf_text

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

def test_texto_simples_extrai_consulta():
    caminho = os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf")
    texto = pdf_text.texto_simples(caminho)
    # deve conter as três âncoras de consulta
    assert "CONSULTA Nº 001" in texto
    assert "CONSULTA Nº 002" in texto
    assert "CONSULTA Nº 003" in texto

def test_limpa_ruido_ocr_junta_numeros_e_sigla():
    # '2 5.152' -> '25.152' ; 'I CMS' -> 'ICMS'
    sujo = "PROTOCOLOS: 2 5.152.191-3\nSÚMULA: I CMS. DIFERIMENTO."
    limpo = pdf_text._limpa_ruido_ocr(sujo)
    assert "25.152.191-3" in limpo
    assert "ICMS" in limpo

def test_texto_por_colunas_mantem_beneficiaria_integra():
    caminho = os.path.join(FIX, "Regime_Krona_2col.pdf")
    texto = pdf_text.texto_por_colunas(caminho)
    # se as colunas foram lidas corretamente, o nome da beneficiária
    # aparece colado ao rótulo, não quebrado com texto da outra coluna
    assert "KRONA TUBOS E CONEXÕES LTDA" in texto
    assert "SPAL INDÚSTRIA BRASILEIRA DE BEBIDAS" in texto

def test_detecta_fonte_consulta():
    caminho = os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf")
    assert pdf_text.detecta_fonte(caminho) == "consulta"

def test_detecta_fonte_regime():
    caminho = os.path.join(FIX, "Regime_Krona_2col.pdf")
    assert pdf_text.detecta_fonte(caminho) == "regime"


# Regressão: a limpeza removia QUALQUER espaço em branco entre dígitos,
# inclusive quebras de linha. O dígito final de uma linha era colado ao
# dígito que abre a seguinte (item numerado "1. DA ABRANGÊNCIA"),
# corrompendo CNPJ e vigência.

def test_limpeza_nao_cola_cnpj_com_item_numerado_da_linha_seguinte():
    sujo = "CNPJ: 54.386.340/0001-21\n1. DA ABRANGÊNCIA"
    assert pdf_text._limpa_ruido_ocr(sujo) == sujo


def test_limpeza_nao_cola_data_com_item_numerado_da_linha_seguinte():
    sujo = "cuja eficácia se encerra em 31/12/2026\n2. DAS OBRIGAÇÕES"
    assert pdf_text._limpa_ruido_ocr(sujo) == sujo


def test_limpeza_nao_mexe_em_numeros_separados_fora_do_protocolo():
    sujo = "conforme o art. 2 3 e 4 do Anexo"
    assert pdf_text._limpa_ruido_ocr(sujo) == sujo


def test_limpeza_junta_protocolos_quebrados_na_mesma_linha():
    sujo = "PROTOCOLOS: 2 5.152.191-3, 2 5.152.192-1\nCONSULTA Nº 001"
    limpo = pdf_text._limpa_ruido_ocr(sujo)
    assert limpo == "PROTOCOLOS: 25.152.191-3, 25.152.192-1\nCONSULTA Nº 001"


def test_detecta_fonte_pdf_sem_paginas_e_desconhecido(monkeypatch):
    class _PdfVazio:
        pages = []

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(pdf_text.pdfplumber, 'open', lambda caminho: _PdfVazio())
    assert pdf_text.detecta_fonte("vazio.pdf") == "desconhecido"


# --- texto_com_paragrafos --------------------------------------------------
M = pdf_text.MARCA_PARAGRAFO
_PDF_CONSULTAS = os.path.join(os.path.dirname(__file__), "fixtures",
                              "Consultas_1_a_3_de_2026.pdf")


def _l(texto, x0, top):
    return {'text': texto, 'x0': x0, 'top': top}


def test_recuo_de_primeira_linha_abre_paragrafo():
    linhas = [_l('abertura', 108, 100), _l('cont 1', 36, 112.8),
              _l('cont 2', 36, 125.6), _l('outro', 108, 147.4),
              _l('cont 3', 36, 160.2), _l('cont 4', 36, 173.0)]
    assert pdf_text._marca_paragrafos_da_pagina(linhas) == [
        M + 'abertura', 'cont 1', 'cont 2', M + 'outro', 'cont 3', 'cont 4']


def test_salto_vertical_abre_paragrafo_mesmo_sem_recuo():
    linhas = [_l('a', 36, 100), _l('b', 36, 112.8), _l('c', 36, 125.6),
              _l('d', 36, 147.4), _l('e', 36, 160.2)]
    assert pdf_text._marca_paragrafos_da_pagina(linhas) == [
        'a', 'b', 'c', M + 'd', 'e']


def test_ruido_de_pagina_nunca_e_marcado_e_nao_gera_salto():
    linhas = [_l('SECRETARIA DE ESTADO DA FAZENDA DO PARANÁ - SEFA', 138, 37),
              _l('SETOR CONSULTIVO', 240, 61),
              _l('__________', 159, 84),
              _l('continua o paragrafo da pagina anterior', 36, 145),
              _l('segunda linha', 36, 157.8),
              _l('terceira linha', 36, 170.6)]
    saida = pdf_text._marca_paragrafos_da_pagina(linhas)
    assert M not in "".join(saida)


def test_pagina_sem_linhas_ou_so_com_ruido_nao_quebra():
    assert pdf_text._marca_paragrafos_da_pagina([]) == []
    so_ruido = [_l('__________', 36, 10), _l('3', 36, 20)]
    assert pdf_text._marca_paragrafos_da_pagina(so_ruido) == ['__________', '3']


def test_empate_de_margem_escolhe_a_menor():
    # 2 linhas a 108 e 2 a 36: a margem do corpo é 36, não 108
    linhas = [_l('a', 108, 100), _l('b', 36, 112.8),
              _l('c', 108, 134.6), _l('d', 36, 147.4)]
    assert pdf_text._marca_paragrafos_da_pagina(linhas) == [
        M + 'a', 'b', M + 'c', 'd']


def test_texto_com_paragrafos_so_acrescenta_marcas():
    com = pdf_text.texto_com_paragrafos(_PDF_CONSULTAS)
    assert M in com
    assert com.replace(M, "") == pdf_text.texto_simples(_PDF_CONSULTAS)


def test_paragrafos_da_resposta_da_consulta_001():
    com = pdf_text.texto_com_paragrafos(_PDF_CONSULTAS)
    assert M + 'Cabe transcrever' in com
    assert M + 'Art. 1' in com
    assert M + 'a) o in' in com
    assert M + 'II - a receita' in com
    # a frase que recomeça logo após o cabeçalho da página seguinte continua
    # o parágrafo anterior: está no texto, mas NÃO abre parágrafo
    assert 'do "caput", os estabelecimentos industriais' in com
    assert M + 'do "caput", os estabelecimentos industriais' not in com


def test_bloco_citado_recuado_so_abre_paragrafo_no_salto_vertical():
    # corpo na margem 36; citação toda em x0=108: 10,9 pt entre linhas do
    # mesmo parágrafo citado, 19,9 pt entre parágrafos citados
    linhas = [_l('b1', 36, 100), _l('b2', 36, 112.8), _l('b3', 36, 125.6),
              _l('b4', 36, 138.4),
              _l('q1a', 108, 151.2), _l('q1b', 108, 162.1), _l('q1c', 108, 173.0),
              _l('q2a', 108, 192.9), _l('q2b', 108, 203.8),
              _l('n1', 36, 226.0), _l('n2', 36, 238.8)]
    assert pdf_text._marca_paragrafos_da_pagina(linhas) == [
        'b1', 'b2', 'b3', 'b4',
        M + 'q1a', 'q1b', 'q1c', M + 'q2a', 'q2b',
        M + 'n1', 'n2']


def test_resposta_da_consulta_001_nao_quebra_citacao_linha_a_linha():
    from parsers import consultas
    regs = consultas.parse(pdf_text.texto_simples(_PDF_CONSULTAS),
                           pdf_text.texto_com_paragrafos(_PDF_CONSULTAS))
    paragrafos = regs[0]["Resposta"].split("\n\n")
    assert len(paragrafos) == 22
    assert any(p.startswith('"Art. 31. Sem prejuízo')
               and p.endswith('seguintes mercadorias:') for p in paragrafos)
    assert any(p.startswith('§ 7.º') and p.endswith('serviço de comunicação.')
               for p in paragrafos)
    p8 = [p for p in paragrafos if p.startswith('§ 8.º')]
    assert len(p8) == 1
    assert 'do "caput", os estabelecimentos industriais' in p8[0]
    assert len(regs[1]["Resposta"].split("\n\n")) == 5
    assert len(regs[2]["Resposta"].split("\n\n")) == 3
