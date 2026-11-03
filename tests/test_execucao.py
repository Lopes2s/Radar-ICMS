import os
import urllib.error

import pytest

from core import armazenamento, pipeline
from core.execucao import Execucao
from tests.test_cnpj import Rede

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

# --- consulta do CNPJ ao gravar ----------------------------------------------
REGIME = {'ANO': '2026', 'DATA': '2026-03-01', 'Nº DO REGIME ESPECIAL': '9.053/2026',
          'EMPRESA': 'Alfa Ltda', 'CNPJ REQUERENTE': '11.222.333/0001-81',
          'VIGÊNCIA DO RE': '12 meses', 'EMENTA': 'ementa'}


def _execucao_com_regime(**opcoes):
    ex = Execucao(**opcoes)
    ex.lote = pipeline.Lote(regimes=[dict(REGIME)])
    return ex


def test_gravar_consulta_o_cnpj_dos_regimes_e_guarda_o_resumo(tmp_path, monkeypatch):
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '1')
    rede = Rede()
    ex = _execucao_com_regime(abrir_cnpj=rede)
    with armazenamento.sessao(str(tmp_path / 'g.db')) as conn:
        resultado = ex.gravar(conn)
        receita = armazenamento.cnpj_receita_de(conn, REGIME['CNPJ REQUERENTE'])
    assert set(resultado) == {'consultas', 'regimes'} and resultado['regimes']['novos'] == 1
    assert receita['cnae_codigo'] == '6422100'
    assert ex.resumo_cnpj['consultados'] == 1


def test_falha_de_rede_nao_impede_a_gravacao(tmp_path, monkeypatch):
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '1')
    ex = _execucao_com_regime(abrir_cnpj=Rede(erro=urllib.error.URLError('sem rede')))
    with armazenamento.sessao(str(tmp_path / 'g.db')) as conn:
        resultado = ex.gravar(conn)
        assert len(armazenamento.buscar_regimes(conn)) == 1
    assert resultado['regimes']['novos'] == 1
    assert len(ex.resumo_cnpj['falhas']) == 1 and ex.resumo_cnpj['consultados'] == 0


def test_erro_inesperado_na_consulta_nao_impede_a_gravacao(tmp_path, monkeypatch):
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '1')
    ex = _execucao_com_regime(abrir_cnpj=Rede(erro=ValueError('boom')))
    with armazenamento.sessao(str(tmp_path / 'g.db')) as conn:
        resultado = ex.gravar(conn)
        assert len(armazenamento.buscar_regimes(conn)) == 1
    assert set(resultado) == {'consultas', 'regimes'}
    assert ex.resumo_cnpj['falhas'][0][1].startswith('erro inesperado')


@pytest.mark.parametrize('consultar_cnpj,variavel', [(False, '1'), (True, '0')])
def test_consulta_desligada_nao_chama_a_rede(tmp_path, monkeypatch, consultar_cnpj, variavel):
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', variavel)
    rede = Rede()
    ex = _execucao_com_regime(abrir_cnpj=rede, consultar_cnpj=consultar_cnpj)
    with armazenamento.sessao(str(tmp_path / 'g.db')) as conn:
        resultado = ex.gravar(conn)
    assert resultado['regimes']['novos'] == 1
    assert rede.urls == [] and ex.resumo_cnpj is None
