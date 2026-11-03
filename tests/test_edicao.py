# tests/test_edicao.py
import pytest

from core import armazenamento, edicao, pipeline

CHAVE_R = pipeline.CHAVE_REGIMES
CHAVE_C = pipeline.CHAVE_CONSULTAS


def _conn(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "e.db"))
    armazenamento.criar_esquema(conn)
    return conn


def _regime(**campos):
    base = {'ANO': '2026', 'DATA': '2026-03-01', 'Nº DO REGIME ESPECIAL': '9.053/2026',
            'EMPRESA': 'Alfa Ltda', 'CNPJ REQUERENTE': '11.222.333/0001-81',
            'VIGÊNCIA DO RE': '', 'EMENTA': 'ementa original'}
    return {**base, **campos}


def _consulta(**campos):
    base = {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
            'Súmula': 'ICMS', 'Resposta': 'resposta'}
    return {**base, **campos}


def _chave_regime(reg=None):
    reg = reg or _regime()
    return {c: reg[c] for c in CHAVE_R}


# --- editar_registro --------------------------------------------------------
def test_editar_campo_grava_historico_manual_e_marca_o_ajuste(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    r = edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    assert r == {'alterados': ['VIGÊNCIA DO RE'], 'chave_trocada': False}
    salvo = armazenamento.buscar_regimes(conn)[0]
    assert salvo['VIGÊNCIA DO RE'] == '12 meses' and salvo['EMPRESA'] == 'Alfa Ltda'
    hist = armazenamento.historico_de(conn, 'regimes', _chave_regime())
    assert len(hist) == 1 and hist[0]['origem'] == 'manual'
    assert hist[0]['campos_alterados'] == ['VIGÊNCIA DO RE']
    assert hist[0]['registro_anterior']['VIGÊNCIA DO RE'] == ''
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R,
                                    tuple(_chave_regime().values())) == ['VIGÊNCIA DO RE']


def test_editar_sem_mudanca_nao_grava_nada(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    r = edicao.editar_registro(conn, 'regime', _chave_regime(), {'EMPRESA': 'Alfa Ltda'})
    assert r == {'alterados': [], 'chave_trocada': False}
    assert armazenamento.historico_de(conn, 'regimes', _chave_regime()) == []


def test_editar_apara_espacos_das_pontas(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'EMPRESA': '  Beta S.A.  '})
    assert armazenamento.buscar_regimes(conn)[0]['EMPRESA'] == 'Beta S.A.'


def test_editar_consulta_tambem_funciona(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(Resposta='')])
    chave = {c: _consulta()[c] for c in CHAVE_C}
    r = edicao.editar_registro(conn, 'consulta', chave, {'Resposta': 'texto corrigido'})
    assert r['alterados'] == ['Resposta']
    assert armazenamento.buscar_consultas(conn)[0]['Resposta'] == 'texto corrigido'
    assert armazenamento.historico_de(conn, 'consultas', chave)[0]['origem'] == 'manual'


@pytest.mark.parametrize("tipo, chave, novos, erro", [
    ('regime', {'Nº DO REGIME ESPECIAL': 'x', 'CNPJ REQUERENTE': 'y'}, {'EMPRESA': 'a'},
     edicao.RegistroInexistente),
    ('regime', None, {'CAMPO_QUE_NAO_EXISTE': 'a'}, ValueError),
    ('outro', {}, {}, ValueError),
])
def test_editar_recusa_pedidos_invalidos(tmp_path, tipo, chave, novos, erro):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    with pytest.raises(erro):
        edicao.editar_registro(conn, tipo, chave or _chave_regime(), novos)


def test_trocar_a_chave_move_o_ato_o_historico_e_cria_o_apelido(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime(**{'CNPJ REQUERENTE': '00.000.000/0000-00'})])
    antiga = {'Nº DO REGIME ESPECIAL': '9.053/2026', 'CNPJ REQUERENTE': '00.000.000/0000-00'}
    r = edicao.editar_registro(conn, 'regime', antiga,
                               {'CNPJ REQUERENTE': '11.222.333/0001-81', 'VIGÊNCIA DO RE': '6 meses'})
    assert r['chave_trocada'] is True
    assert set(r['alterados']) == {'CNPJ REQUERENTE', 'VIGÊNCIA DO RE'}
    linhas = armazenamento.buscar_regimes(conn)
    assert len(linhas) == 1 and linhas[0]['CNPJ REQUERENTE'] == '11.222.333/0001-81'
    nova = dict(zip(CHAVE_R, ('9.053/2026', '11.222.333/0001-81')))
    assert len(armazenamento.historico_de(conn, 'regimes', nova)) == 1     # histórico foi junto
    assert armazenamento.historico_de(conn, 'regimes', antiga) == []
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R,
                                        tuple(antiga.values())) == tuple(nova.values())
    # só o campo não-chave vira "ajuste"
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, tuple(nova.values())) == ['VIGÊNCIA DO RE']


def test_chave_em_conflito_e_recusada_sem_alterar_nada(tmp_path):
    conn = _conn(tmp_path)
    outro = _regime(**{'Nº DO REGIME ESPECIAL': '1/2026', 'EMPRESA': 'Outra'})
    armazenamento.salvar_regimes(conn, [_regime(), outro])
    with pytest.raises(edicao.ChaveEmConflito):
        edicao.editar_registro(conn, 'regime', _chave_regime(),
                               {'Nº DO REGIME ESPECIAL': '1/2026', 'EMPRESA': 'Mudou'})
    assert {r['EMPRESA'] for r in armazenamento.buscar_regimes(conn)} == {'Alfa Ltda', 'Outra'}
    assert conn.execute("SELECT COUNT(*) FROM historico").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM chaves_substituidas").fetchone()[0] == 0


def test_chave_em_branco_e_recusada(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    with pytest.raises(edicao.ChaveVazia):
        edicao.editar_registro(conn, 'regime', _chave_regime(), {'CNPJ REQUERENTE': '   '})
    assert armazenamento.buscar_regimes(conn)[0]['CNPJ REQUERENTE'] == '11.222.333/0001-81'


def test_falha_no_meio_da_edicao_nao_deixa_gravacao_parcial(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime(**{'CNPJ REQUERENTE': '00'})])

    def quebra(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(armazenamento, 'mover_chave_auxiliares', quebra)
    with pytest.raises(RuntimeError):
        edicao.editar_registro(conn, 'regime',
                               {'Nº DO REGIME ESPECIAL': '9.053/2026', 'CNPJ REQUERENTE': '00'},
                               {'CNPJ REQUERENTE': '11', 'EMPRESA': 'Mudou'})
    salvo = armazenamento.buscar_regimes(conn)[0]
    assert salvo['CNPJ REQUERENTE'] == '00' and salvo['EMPRESA'] == 'Alfa Ltda'
    assert conn.execute("SELECT COUNT(*) FROM historico").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ajustes").fetchone()[0] == 0
