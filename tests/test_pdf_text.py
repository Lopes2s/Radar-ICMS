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
