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


# --- Resposta com parágrafos no pipeline ----------------------------------
def test_pipeline_entrega_resposta_com_paragrafos_e_demais_campos_iguais():
    import os
    from core import pdf_text
    from parsers import consultas as p_consultas
    pdf = os.path.join(os.path.dirname(__file__), "fixtures", "Consultas_1_a_3_de_2026.pdf")
    lote = pipeline.Lote()
    pipeline.processar_arquivo(lote, pdf, "c.pdf")
    base = p_consultas.parse(pdf_text.texto_simples(pdf))
    assert len(lote.consultas) == len(base) == 3
    assert "\n\n" in lote.consultas[0]["Resposta"]
    for b, n in zip(base, lote.consultas):
        assert {k: v for k, v in n.items() if k != "Resposta"} == \
               {k: v for k, v in b.items() if k != "Resposta"}


def test_pipeline_de_regime_nao_foi_tocado():
    import os
    from core import pdf_text
    from parsers import regimes as p_regimes
    pdf = os.path.join(os.path.dirname(__file__), "fixtures", "Regime_Krona_2col.pdf")
    lote = pipeline.Lote()
    pipeline.processar_arquivo(lote, pdf, "r.pdf")
    esperado, _ = p_regimes.parse(pdf_text.texto_por_colunas(pdf))
    assert lote.regimes == esperado


def test_reimportar_pdf_atualiza_resposta_achatada_do_banco_sem_duplicar(tmp_path):
    import os
    from core import armazenamento, consulta
    pdf = os.path.join(os.path.dirname(__file__), "fixtures", "Consultas_1_a_3_de_2026.pdf")
    conn = armazenamento.conectar(str(tmp_path / "t.db"))
    armazenamento.criar_esquema(conn)
    # registro antigo, achatado, com a mesma chave natural (Ano + Nº)
    armazenamento.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
         'Protocolo': '', 'Súmula': 'velha', 'Problema da Consulta': '',
         'CNAE Detectado': '', 'Resposta': 'antiga achatada'}])
    for _ in range(2):  # duas vezes: também prova idempotência
        lote = pipeline.Lote()
        pipeline.processar_arquivo(lote, pdf, "c.pdf")
        pipeline.finalizar(lote)
        armazenamento.persistir_lote(conn, lote)
    achados = consulta.buscar(conn, "consulta")
    assert len(achados) == 3
    r001 = next(r for r in achados if r["Nº da Consulta"] == "001")
    assert "\n\n" in r001["Resposta"]
    assert r001["Resposta"] != "antiga achatada"


def test_falha_nos_paragrafos_cai_no_texto_achatado(monkeypatch):
    from parsers import consultas

    def _quebra(caminho):
        raise RuntimeError("falha nos parágrafos")

    monkeypatch.setattr(pipeline.pdf_text, "texto_com_paragrafos", _quebra)
    lote = pipeline.Lote()
    linha = pipeline.processar_arquivo(lote, CONSULTAS_PDF, "c.pdf")
    assert linha["Tipo"] == "consulta"
    assert linha["Erro"] == ""
    assert linha["Consultas"] == 3
    achatado = consultas.parse(pdf_text.texto_simples(CONSULTAS_PDF))
    assert [r["Resposta"] for r in lote.consultas] == [r["Resposta"] for r in achatado]
