# tests/test_receita_banco.py
"""Tabela cnpj_receita (schema 4): dados da Receita Federal guardados à parte do regime."""
from core import armazenamento

BB = '00.000.000/0001-91'
DADOS = {'cnpj': '00000000000191', 'razao_social': 'BANCO DO BRASIL SA',
         'cnae_codigo': '6422100', 'cnae_descricao': 'Bancos múltiplos, com carteira comercial',
         'situacao': 'ATIVA'}


def _conn(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / 'r.db'))
    armazenamento.criar_esquema(conn)
    return conn


def test_esquema_4_cria_a_tabela_da_receita_vazia(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.SCHEMA_VERSAO >= 4
    assert conn.execute('SELECT COUNT(*) FROM cnpj_receita').fetchone()[0] == 0
    assert armazenamento.cnpj_receita_de(conn, BB) is None


def test_banco_do_schema_3_ganha_a_tabela_sem_perder_os_atos(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [{'ANO': '2026', 'Nº DO REGIME ESPECIAL': '1/2026',
                                         'CNPJ REQUERENTE': '11.222.333/0001-81'}])
    conn.execute('DROP TABLE cnpj_receita')
    conn.execute('PRAGMA user_version = 3')
    armazenamento.criar_esquema(conn)
    assert armazenamento.versao_do_schema(conn) == armazenamento.SCHEMA_VERSAO
    assert conn.execute('SELECT COUNT(*) FROM cnpj_receita').fetchone()[0] == 0
    assert len(armazenamento.buscar_regimes(conn)) == 1


def test_salvar_e_ler_a_receita_aceita_cnpj_com_pontuacao(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_cnpj_receita(conn, DADOS, consultado_em='2026-11-03T12:00:00+00:00')
    lido = armazenamento.cnpj_receita_de(conn, BB)
    assert lido == {**DADOS, 'consultado_em': '2026-11-03T12:00:00+00:00'}
    assert armazenamento.cnpj_receita_de(conn, '00000000000191') == lido


def test_salvar_de_novo_substitui_a_consulta_anterior(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_cnpj_receita(conn, DADOS, consultado_em='2026-11-03T12:00:00+00:00')
    armazenamento.salvar_cnpj_receita(conn, {**DADOS, 'situacao': 'BAIXADA'},
                                      consultado_em='2026-12-03T12:00:00+00:00')
    assert armazenamento.cnpj_receita_de(conn, BB)['situacao'] == 'BAIXADA'
    assert conn.execute('SELECT COUNT(*) FROM cnpj_receita').fetchone()[0] == 1


def test_consultar_sem_cnpj_devolve_none(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.cnpj_receita_de(conn, '') is None
    assert armazenamento.cnpj_receita_de(conn, None) is None
