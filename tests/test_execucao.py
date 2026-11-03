import os

import pytest

from core import armazenamento
from core.execucao import Execucao

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
CONSULTAS_PDF = os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf")


def test_carregar_avisa_o_progresso_e_chama_ao_arquivo():
    eventos, linhas = [], []
    ex = Execucao(progresso=lambda *a: eventos.append(a), ao_arquivo=linhas.append)

    lote = ex.carregar([(CONSULTAS_PDF, "c.pdf")])

    assert eventos[0] == ('leitura', 0, 1, 'c.pdf')
    assert eventos[-1] == ('leitura', 1, 1, '')
    assert [l['Arquivo'] for l in linhas] == ['c.pdf']
    assert len(lote.consultas) == 3
    assert ex.lote is lote
    assert ex.diagnostico['pode_continuar'] is True


def test_carregar_lista_vazia_nao_quebra():
    ex = Execucao()
    lote = ex.carregar([])
    assert lote.consultas == [] and lote.regimes == []
    assert ex.diagnostico['pode_continuar'] is False


def test_pdf_corrompido_nao_derruba_o_lote_e_aparece_em_arquivos_com_erro(tmp_path):
    ruim = tmp_path / "corrompido.pdf"
    ruim.write_bytes(b"isto nao e um pdf")
    ex = Execucao()

    ex.carregar([(CONSULTAS_PDF, "c.pdf"), (str(ruim), "corrompido.pdf")])

    assert len(ex.lote.consultas) == 3
    erros = ex.arquivos_com_erro()
    assert [e['Arquivo'] for e in erros] == ['corrompido.pdf']
    assert erros[0]['Erro']


def test_gravar_persiste_e_avisa_o_progresso(tmp_path):
    eventos = []
    ex = Execucao(progresso=lambda *a: eventos.append(a))
    ex.carregar([(CONSULTAS_PDF, "c.pdf")])

    with armazenamento.sessao(str(tmp_path / "e.db")) as conn:
        resultado = ex.gravar(conn)
        assert len(armazenamento.buscar_consultas(conn)) == 3
        assert conn.execute("SELECT COUNT(*) FROM importacoes").fetchone()[0] == 1

    assert resultado['consultas'] == {'novos': 3, 'atualizados': 0}
    assert ('gravacao', 0, 1, '') in eventos and ('gravacao', 1, 1, '') in eventos


def test_criterio_de_dedup_invalido_e_recusado():
    with pytest.raises(ValueError):
        Execucao(dedup='aleatorio')


def test_forcar_invalido_continua_sendo_erro_de_programacao():
    with pytest.raises(ValueError):
        Execucao().carregar([(CONSULTAS_PDF, "c.pdf")], forcar='outro')


def test_gravar_repassa_o_sobrescrever_ao_armazenamento(tmp_path):
    from core import edicao
    ex = Execucao()
    ex.carregar([(CONSULTAS_PDF, "c.pdf")])
    with armazenamento.sessao(str(tmp_path / "s.db")) as conn:
        ex.gravar(conn)
        edicao.editar_registro(conn, 'consulta', {'Ano': '2026', 'Nº da Consulta': '001'},
                               {'Protocolo': 'AJUSTADO'})
        ex.gravar(conn)                                         # padrão: mantém o ajuste
        assert [r for r in armazenamento.buscar_consultas(conn)
                if r['Nº da Consulta'] == '001'][0]['Protocolo'] == 'AJUSTADO'
        ex.gravar(conn, sobrescrever=[('consulta', '2026', '001')])
        assert [r for r in armazenamento.buscar_consultas(conn)
                if r['Nº da Consulta'] == '001'][0]['Protocolo'] != 'AJUSTADO'
