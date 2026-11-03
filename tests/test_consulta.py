# tests/test_consulta.py
import io

import pytest
from openpyxl import load_workbook
from core import armazenamento, consulta


@pytest.fixture
def conn(tmp_path):
    c = armazenamento.conectar(str(tmp_path / "t.db"))
    armazenamento.criar_esquema(c)
    armazenamento.salvar_consultas(c, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS', 'Problema da Consulta': 'madeira',
         'CNAE Detectado': ''},
        {'Ano': '2023', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': '', 'Problema da Consulta': '',
         'CNAE Detectado': ''},
    ])
    armazenamento.salvar_regimes(c, [
        {'ANO': '2026', 'DATA': '', 'Nº DOE': '', 'RE PR COMPETITIVO': '',
         'Nº DO REGIME ESPECIAL': '1/2026', 'EMPRESA': 'KRONA', 'CNPJ REQUERENTE': '',
         'CAD/ICMS': '', 'CNAE REQUERENTE': '', 'DESCRIÇÃO CNAE': '',
         'VIGÊNCIA DO RE': '', 'EMENTA': ''},
    ])
    return c


def test_buscar_consulta_delega_para_armazenamento(conn):
    assert len(consulta.buscar(conn, 'consulta', texto='madeira')) == 1


def test_buscar_regime_delega_para_armazenamento(conn):
    assert len(consulta.buscar(conn, 'regime', texto='KRONA')) == 1


def test_tipo_invalido_levanta_erro_de_programacao(conn):
    with pytest.raises(ValueError):
        consulta.buscar(conn, 'algo_que_nao_existe')


def test_anos_disponiveis_consulta(conn):
    assert consulta.anos_disponiveis(conn, 'consulta') == ['2023', '2026']


def test_anos_disponiveis_regime(conn):
    assert consulta.anos_disponiveis(conn, 'regime') == ['2026']


def test_anos_disponiveis_tipo_invalido_levanta_erro(conn):
    with pytest.raises(ValueError):
        consulta.anos_disponiveis(conn, 'algo_que_nao_existe')


def test_exportar_xlsx_consulta_gera_planilha_so_com_a_aba_de_consultas():
    from openpyxl import load_workbook
    resultados = [{'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
                  'Protocolo': '', 'Súmula': 'ICMS', 'Problema da Consulta': 'x',
                  'CNAE Detectado': ''}]
    conteudo = consulta.exportar_xlsx('consulta', resultados)
    wb = load_workbook(io.BytesIO(conteudo))
    assert wb.sheetnames == ['Consultas — a revisar']
    ws = wb['Consultas — a revisar']
    assert ws.cell(row=2, column=2).value == '001'


def test_exportar_xlsx_regime_gera_planilha_so_com_a_aba_de_regimes():
    from openpyxl import load_workbook
    resultados = [{'ANO': '2026', 'DATA': '', 'Nº DOE': '', 'RE PR COMPETITIVO': '',
                  'Nº DO REGIME ESPECIAL': '1/2026', 'EMPRESA': 'KRONA',
                  'CNPJ REQUERENTE': '', 'CAD/ICMS': '', 'CNAE REQUERENTE': '',
                  'DESCRIÇÃO CNAE': '', 'VIGÊNCIA DO RE': '', 'EMENTA': ''}]
    conteudo = consulta.exportar_xlsx('regime', resultados)
    wb = load_workbook(io.BytesIO(conteudo))
    assert wb.sheetnames == ['Regimes — a revisar']


def test_exportar_xlsx_sem_resultados_ainda_gera_planilha_valida():
    from openpyxl import load_workbook
    conteudo = consulta.exportar_xlsx('consulta', [])
    load_workbook(io.BytesIO(conteudo))  # não pode levantar exceção


def test_exportar_xlsx_tipo_invalido_levanta_erro():
    with pytest.raises(ValueError):
        consulta.exportar_xlsx('algo_que_nao_existe', [])


def test_exportar_busca_abre_conexao_propria_e_devolve_xlsx(tmp_path):
    caminho = str(tmp_path / "e.db")
    with armazenamento.sessao(caminho) as c:
        armazenamento.salvar_consultas(c, [
            {'Ano': '2026', 'Nº da Consulta': '001', 'Súmula': 'ICMS',
             'Problema da Consulta': 'madeira'},
            {'Ano': '2026', 'Nº da Consulta': '002', 'Súmula': 'ICMS',
             'Problema da Consulta': 'soja'},
        ])

    dados = consulta.exportar_busca('consulta', texto='madeira', caminho_bd=caminho)

    ws = load_workbook(io.BytesIO(dados))['Consultas — a revisar']
    assert ws.max_row == 2  # cabeçalho + 1 resultado


def test_buscar_lista_traz_so_colunas_leves_e_detalhe_traz_tudo(tmp_path):
    with armazenamento.sessao(str(tmp_path / "l.db")) as c:
        armazenamento.salvar_consultas(c, [
            {'Ano': '2026', 'Nº da Consulta': '001', 'Súmula': 'ICMS',
             'Resposta': 'resposta completa'}])
        lista = consulta.buscar_lista(c, 'consulta')
        assert 'Resposta' not in lista[0]
        assert lista[0]['Súmula'] == 'ICMS'
        completo = consulta.detalhe(c, 'consulta', lista[0])
        assert completo['Resposta'] == 'resposta completa'


def test_detalhe_de_registro_inexistente_devolve_none(tmp_path):
    with armazenamento.sessao(str(tmp_path / "l.db")) as c:
        assert consulta.detalhe(c, 'regime', {'Nº DO REGIME ESPECIAL': 'x',
                                              'CNPJ REQUERENTE': 'y'}) is None


def test_buscar_lista_tipo_invalido_levanta_erro(tmp_path):
    with armazenamento.sessao(str(tmp_path / "l.db")) as c:
        with pytest.raises(ValueError):
            consulta.buscar_lista(c, 'outro')


def test_historico_do_registro_por_tipo(tmp_path):
    with armazenamento.sessao(str(tmp_path / "h.db")) as c:
        base = {'Ano': '2026', 'Nº da Consulta': '001', 'Protocolo': ''}
        armazenamento.salvar_consultas(c, [base])
        armazenamento.salvar_consultas(c, [{**base, 'Protocolo': 'x'}])
        itens = consulta.historico(c, 'consulta', base)
        assert len(itens) == 1
        assert itens[0]['campos_alterados'] == ['Protocolo']


def test_resumo_do_banco_vazio(tmp_path):
    with armazenamento.sessao(str(tmp_path / "r.db")) as c:
        assert consulta.resumo_do_banco(c) == {
            'consultas': 0, 'regimes': 0, 'anos': [], 'ultima_importacao': None}


def test_resumo_do_banco_conta_atos_une_anos_e_traz_a_ultima_importacao(tmp_path):
    with armazenamento.sessao(str(tmp_path / "r.db")) as c:
        armazenamento.salvar_consultas(c, [
            {'Ano': '2025', 'Nº da Consulta': '001'},
            {'Ano': '2026', 'Nº da Consulta': '002'},
        ])
        armazenamento.salvar_regimes(c, [
            {'ANO': '2026', 'Nº DO REGIME ESPECIAL': '1/2026', 'CNPJ REQUERENTE': '11'},
            {'ANO': '2024', 'Nº DO REGIME ESPECIAL': '2/2024', 'CNPJ REQUERENTE': '22'},
            {'ANO': '', 'Nº DO REGIME ESPECIAL': '3/x', 'CNPJ REQUERENTE': '33'},
        ])
        armazenamento.registrar_importacoes(c, [
            {'arquivo': 'a.pdf', 'sha256': 'x', 'tipo': 'consulta', 'n_registros': 2}])
        resumo = consulta.resumo_do_banco(c)
    assert resumo['consultas'] == 2
    assert resumo['regimes'] == 3
    assert resumo['anos'] == ['2024', '2025', '2026']   # união, sem repetir e sem vazio
    assert resumo['ultima_importacao'][:4].isdigit()      # ISO UTC gravado pelo armazenamento
