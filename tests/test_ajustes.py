# tests/test_ajustes.py
from core import armazenamento, pipeline

CHAVE_R = pipeline.CHAVE_REGIMES
CHAVE_C = pipeline.CHAVE_CONSULTAS


def _conn(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "e.db"))
    armazenamento.criar_esquema(conn)
    return conn


def _consulta(**campos):
    base = {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
            'Súmula': 'ICMS', 'Resposta': 'resposta'}
    return {**base, **campos}


# --- primitivas de armazenamento -------------------------------------------
def test_esquema_3_tem_ajustes_substituicoes_e_origem_no_historico(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.SCHEMA_VERSAO == 3
    conn.execute("SELECT COUNT(*) FROM ajustes")
    conn.execute("SELECT COUNT(*) FROM chaves_substituidas")
    assert 'origem' in armazenamento._colunas_existentes(conn, 'historico')


def test_banco_v2_migra_para_v3_preservando_o_historico(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(Súmula='a')])
    armazenamento.salvar_consultas(conn, [_consulta(Súmula='b')])   # gera 1 linha de histórico
    # volta o banco ao formato do schema 2: histórico sem 'origem' e sem as tabelas novas
    conn.execute("ALTER TABLE historico RENAME TO historico_novo")
    conn.execute("""CREATE TABLE historico (id INTEGER PRIMARY KEY AUTOINCREMENT, tabela TEXT NOT NULL,
        chave TEXT NOT NULL, registro_anterior TEXT NOT NULL, campos_alterados TEXT NOT NULL,
        alterado_em TEXT NOT NULL, versao_app TEXT NOT NULL)""")
    conn.execute("""INSERT INTO historico (id, tabela, chave, registro_anterior, campos_alterados,
        alterado_em, versao_app) SELECT id, tabela, chave, registro_anterior, campos_alterados,
        alterado_em, versao_app FROM historico_novo""")
    conn.execute("DROP TABLE historico_novo")
    conn.execute("DROP TABLE ajustes")
    conn.execute("DROP TABLE chaves_substituidas")
    conn.execute("PRAGMA user_version = 2")
    conn.commit()

    armazenamento.criar_esquema(conn)

    assert armazenamento.versao_do_schema(conn) == 3
    itens = armazenamento.historico_de(conn, 'consultas', {'Ano': '2026', 'Nº da Consulta': '001'})
    assert len(itens) == 1 and itens[0]['origem'] == 'importacao'
    conn.execute("SELECT COUNT(*) FROM ajustes")


def test_ajustes_juntam_campos_sem_repetir(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.juntar_ajustes(conn, 'regimes', CHAVE_R, ('1', '2'), ['EMENTA'])
    armazenamento.juntar_ajustes(conn, 'regimes', CHAVE_R, ('1', '2'), ['EMENTA', 'DATA'])
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, ('1', '2')) == ['DATA', 'EMENTA']
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, ('9', '9')) == []
    armazenamento.limpar_ajustes(conn, 'regimes', CHAVE_R, ('1', '2'))
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, ('1', '2')) == []


def test_resolver_chave_sem_apelido_devolve_a_mesma(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, ('1', '2')) == ('1', '2')


def test_apelidos_encadeados_apontam_sempre_para_a_chave_atual(tmp_path):
    conn = _conn(tmp_path)
    a, b, c = ('A', '1'), ('B', '1'), ('C', '1')
    armazenamento.registrar_substituicao(conn, 'regimes', CHAVE_R, a, b)
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, a) == b
    armazenamento.registrar_substituicao(conn, 'regimes', CHAVE_R, b, c)
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, a) == c   # A->B->C vira A->C
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, b) == c
    armazenamento.registrar_substituicao(conn, 'regimes', CHAVE_R, c, a)    # a chave voltou a A
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, a) == a   # A é real de novo
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, b) == a
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, c) == a


def test_mover_chave_leva_historico_e_ajustes(tmp_path):
    conn = _conn(tmp_path)
    antiga, nova = ('1', '2'), ('3', '4')
    armazenamento.registrar_alteracao(conn, 'regimes', CHAVE_R, antiga, {'EMENTA': 'x'}, ['EMENTA'])
    armazenamento.juntar_ajustes(conn, 'regimes', CHAVE_R, antiga, ['EMENTA'])
    armazenamento.mover_chave_auxiliares(conn, 'regimes', CHAVE_R, antiga, nova)
    chave_nova = dict(zip(CHAVE_R, nova))
    assert len(armazenamento.historico_de(conn, 'regimes', chave_nova)) == 1
    assert armazenamento.historico_de(conn, 'regimes', dict(zip(CHAVE_R, antiga))) == []
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, nova) == ['EMENTA']
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, antiga) == []
