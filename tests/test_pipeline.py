# tests/test_pipeline.py
import os
import shutil

import pytest

from core import pdf_text, pipeline

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
CONSULTAS_PDF = os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf")
KRONA_PDF = os.path.join(FIX, "Regime_Krona_2col.pdf")


class _PaginaSemTexto:
    def extract_text(self):
        return None


class _PdfFalso:
    """Imita pdfplumber.open(): context manager com .pages."""
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_dedup_mantem_a_primeira_ocorrencia():
    linhas = [
        {'Ano': '2026', 'Nº da Consulta': '001', 'x': 'a'},
        {'Ano': '2026', 'Nº da Consulta': '001', 'x': 'b'},
        {'Ano': '2026', 'Nº da Consulta': '002', 'x': 'c'},
    ]
    out = pipeline.dedup(linhas, pipeline.CHAVE_CONSULTAS)
    assert [r['x'] for r in out] == ['a', 'c']


def test_processa_pdf_de_consultas():
    lote = pipeline.Lote()
    linha = pipeline.processar_arquivo(lote, CONSULTAS_PDF, "consultas.pdf")
    assert linha == {'Arquivo': 'consultas.pdf', 'Tipo': 'consulta',
                     'Consultas': 3, 'Regimes': 0, 'Descartes': 0, 'Erro': ''}
    assert len(lote.consultas) == 3
    assert lote.arquivos == [linha]


def test_processa_pdf_de_regimes():
    lote = pipeline.Lote()
    linha = pipeline.processar_arquivo(lote, KRONA_PDF, "krona.pdf")
    assert linha['Tipo'] == 'regime'
    assert linha['Regimes'] == 2
    assert len(lote.regimes) == 2


def test_pdf_corrompido_vira_linha_de_erro_e_nao_derruba_o_lote(tmp_path):
    ruim = tmp_path / "corrompido.pdf"
    ruim.write_bytes(b"isto nao e um pdf")
    lote = pipeline.Lote()

    linha_ruim = pipeline.processar_arquivo(lote, str(ruim), "corrompido.pdf")
    pipeline.processar_arquivo(lote, CONSULTAS_PDF, "consultas.pdf")

    assert linha_ruim['Tipo'] == 'erro'
    assert linha_ruim['Erro']  # mensagem não vazia, com o tipo da exceção
    assert len(lote.consultas) == 3  # o arquivo bom foi processado
    assert [a['Tipo'] for a in lote.arquivos] == ['erro', 'consulta']


def test_forcar_tipo_ignora_a_deteccao():
    lote = pipeline.Lote()
    linha = pipeline.processar_arquivo(lote, CONSULTAS_PDF, "c.pdf", forcar='regime')
    assert linha['Tipo'] == 'regime'


def test_forcar_tipo_invalido_e_erro_de_programacao():
    with pytest.raises(ValueError):
        pipeline.processar_arquivo(pipeline.Lote(), CONSULTAS_PDF, "c.pdf",
                                   forcar='Forçar Consulta')


def test_pdf_sem_camada_de_texto_aparece_como_desconhecido(monkeypatch):
    # PDF escaneado: pdfplumber abre, mas extract_text() devolve None
    monkeypatch.setattr(pdf_text.pdfplumber, 'open',
                        lambda caminho: _PdfFalso([_PaginaSemTexto()]))
    lote = pipeline.Lote()
    linha = pipeline.processar_arquivo(lote, "escaneado.pdf", "escaneado.pdf")
    assert linha['Tipo'] == 'desconhecido'
    assert linha['Erro'] == ''
    assert lote.arquivos == [linha]


def test_mesmo_pdf_duas_vezes_nao_duplica_registros(tmp_path):
    copia = tmp_path / "copia.pdf"
    shutil.copy(CONSULTAS_PDF, copia)
    lote = pipeline.Lote()
    pipeline.processar_arquivo(lote, CONSULTAS_PDF, "original.pdf")
    pipeline.processar_arquivo(lote, str(copia), "copia.pdf")

    pipeline.finalizar(lote)

    assert len(lote.consultas) == 3
    assert len(lote.arquivos) == 2  # os dois arquivos continuam listados


def test_descartes_registram_o_arquivo_de_origem(monkeypatch):
    monkeypatch.setattr(pipeline.p_regimes, 'parse',
                        lambda texto: ([], [{'Nº RE': '1/2026', 'Motivo': 'revogacao',
                                             'Empresa': 'X'}]))
    lote = pipeline.Lote()
    pipeline.processar_arquivo(lote, KRONA_PDF, "krona.pdf")
    assert lote.descartes[0]['Arquivo'] == 'krona.pdf'
