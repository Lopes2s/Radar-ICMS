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


# --- reimportação: proteção dos ajustes e apelidos --------------------------
def test_reimportar_mantem_o_campo_ajustado_a_mao_e_atualiza_o_resto(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})

    resultado = armazenamento.salvar_regimes(
        conn, [_regime(**{'VIGÊNCIA DO RE': '', 'EMENTA': 'ementa nova'})])

    assert resultado == {'novos': 0, 'atualizados': 1}
    salvo = armazenamento.buscar_regimes(conn)[0]
    assert salvo['VIGÊNCIA DO RE'] == '12 meses'          # ajuste mantido
    assert salvo['EMENTA'] == 'ementa nova'               # o resto segue o PDF
    hist = armazenamento.historico_de(conn, 'regimes', _chave_regime())
    assert [h['origem'] for h in hist] == ['importacao', 'manual']   # mais recente primeiro
    assert hist[0]['campos_alterados'] == ['EMENTA']


def test_sobrescrever_aplica_o_pdf_e_limpa_os_ajustes(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    chave = tuple(_chave_regime().values())

    armazenamento.salvar_regimes(conn, [_regime(**{'VIGÊNCIA DO RE': ''})], sobrescrever={chave})

    assert armazenamento.buscar_regimes(conn)[0]['VIGÊNCIA DO RE'] == ''
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, chave) == []
    ultimo = armazenamento.historico_de(conn, 'regimes', _chave_regime())[0]
    assert ultimo['origem'] == 'importacao'
    assert ultimo['registro_anterior']['VIGÊNCIA DO RE'] == '12 meses'


def test_reimportar_o_pdf_original_cai_no_ato_com_a_chave_corrigida(tmp_path):
    conn = _conn(tmp_path)
    errado = _regime(**{'CNPJ REQUERENTE': '00.000.000/0000-00'})
    armazenamento.salvar_regimes(conn, [errado])
    edicao.editar_registro(conn, 'regime',
                           {c: errado[c] for c in CHAVE_R},
                           {'CNPJ REQUERENTE': '11.222.333/0001-81'})

    resultado = armazenamento.salvar_regimes(conn, [{**errado, 'EMENTA': 'ementa do PDF 2'}])

    assert resultado == {'novos': 0, 'atualizados': 1}            # não duplicou
    linhas = armazenamento.buscar_regimes(conn)
    assert len(linhas) == 1
    assert linhas[0]['CNPJ REQUERENTE'] == '11.222.333/0001-81'   # a chave corrigida prevalece
    assert linhas[0]['EMENTA'] == 'ementa do PDF 2'


def test_duas_correcoes_seguidas_de_chave_reimportando_a_primeira(tmp_path):
    conn = _conn(tmp_path)
    a = _regime(**{'CNPJ REQUERENTE': 'A'})
    armazenamento.salvar_regimes(conn, [a])
    num = '9.053/2026'
    edicao.editar_registro(conn, 'regime', {'Nº DO REGIME ESPECIAL': num, 'CNPJ REQUERENTE': 'A'},
                           {'CNPJ REQUERENTE': 'B'})
    edicao.editar_registro(conn, 'regime', {'Nº DO REGIME ESPECIAL': num, 'CNPJ REQUERENTE': 'B'},
                           {'CNPJ REQUERENTE': 'C'})
    armazenamento.salvar_regimes(conn, [a])
    linhas = armazenamento.buscar_regimes(conn)
    assert len(linhas) == 1 and linhas[0]['CNPJ REQUERENTE'] == 'C'


def test_persistir_lote_repassa_o_sobrescrever_e_mantem_o_formato_do_retorno(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    lote = pipeline.Lote(regimes=[_regime(**{'VIGÊNCIA DO RE': ''})])

    r1 = armazenamento.persistir_lote(conn, lote)
    assert r1 == {'consultas': {'novos': 0, 'atualizados': 0},
                  'regimes': {'novos': 0, 'atualizados': 1}}
    assert armazenamento.buscar_regimes(conn)[0]['VIGÊNCIA DO RE'] == '12 meses'

    chave = ('regime', *tuple(_chave_regime().values()))
    armazenamento.persistir_lote(conn, lote, sobrescrever=[chave])
    assert armazenamento.buscar_regimes(conn)[0]['VIGÊNCIA DO RE'] == ''


# --- conflitos para a análise ----------------------------------------------
def test_conflitos_listam_so_atos_ajustados_cujo_pdf_diverge(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime(), _regime(**{'Nº DO REGIME ESPECIAL': '2/2026'})])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})

    lote = pipeline.Lote(regimes=[_regime(**{'VIGÊNCIA DO RE': ''}),
                                  _regime(**{'Nº DO REGIME ESPECIAL': '2/2026'})])
    itens = edicao.ajustes_em_conflito(conn, lote)

    assert len(itens) == 1
    assert itens[0]['tipo'] == 'regime' and itens[0]['rotulo'] == 'RE 9.053/2026'
    assert itens[0]['campos'] == [{'campo': 'VIGÊNCIA DO RE', 'atual': '12 meses', 'pdf': ''}]
    assert edicao.chave_do_item(itens[0]) == ('regime', '9.053/2026', '11.222.333/0001-81')


def test_sem_divergencia_ou_sem_ato_gravado_nao_ha_conflito(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    igual = pipeline.Lote(regimes=[_regime(**{'VIGÊNCIA DO RE': '12 meses'})])
    novo = pipeline.Lote(regimes=[_regime(**{'Nº DO REGIME ESPECIAL': '7/2026'})])
    assert edicao.ajustes_em_conflito(conn, igual) == []
    assert edicao.ajustes_em_conflito(conn, novo) == []


def test_conflito_usa_a_chave_atual_quando_o_pdf_traz_a_chave_antiga(tmp_path):
    conn = _conn(tmp_path)
    errado = _regime(**{'CNPJ REQUERENTE': '00'})
    armazenamento.salvar_regimes(conn, [errado])
    edicao.editar_registro(conn, 'regime', {c: errado[c] for c in CHAVE_R},
                           {'CNPJ REQUERENTE': '11', 'EMPRESA': 'Corrigida'})
    itens = edicao.ajustes_em_conflito(conn, pipeline.Lote(regimes=[errado]))
    assert len(itens) == 1
    assert itens[0]['chave']['CNPJ REQUERENTE'] == '11'
    assert itens[0]['campos'] == [{'campo': 'EMPRESA', 'atual': 'Corrigida', 'pdf': 'Alfa Ltda'}]


# --- edição na análise (em memória) ----------------------------------------
def _lote_com_regimes():
    lote = pipeline.Lote(regimes=[_regime(), _regime(**{'Nº DO REGIME ESPECIAL': '2/2026'})])
    lote.origem[('regime', '9.053/2026', '11.222.333/0001-81')] = 'a.pdf'
    return lote


def test_ajustar_campo_no_lote_altera_o_registro_e_anota_o_ajuste():
    lote = _lote_com_regimes()
    r = edicao.ajustar_no_lote(lote, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    assert r == {'alterados': ['VIGÊNCIA DO RE'], 'chave_trocada': False}
    assert lote.regimes[0]['VIGÊNCIA DO RE'] == '12 meses'
    assert lote.ajustados == {('regime', '9.053/2026', '11.222.333/0001-81'): {'VIGÊNCIA DO RE'}}
    assert lote.chaves_substituidas == []


def test_ajustar_a_chave_no_lote_acompanha_origem_ajustes_e_apelidos():
    lote = _lote_com_regimes()
    edicao.ajustar_no_lote(lote, 'regime', _chave_regime(), {'EMENTA': 'x'})
    r = edicao.ajustar_no_lote(lote, 'regime', _chave_regime(),
                               {'CNPJ REQUERENTE': '99.999.999/0001-99'})
    assert r['chave_trocada'] is True
    nova = ('9.053/2026', '99.999.999/0001-99')
    assert lote.regimes[0]['CNPJ REQUERENTE'] == '99.999.999/0001-99'
    assert lote.origem[('regime', *nova)] == 'a.pdf'
    assert ('regime', '9.053/2026', '11.222.333/0001-81') not in lote.origem
    assert lote.ajustados == {('regime', *nova): {'EMENTA'}}              # o ajuste acompanhou a chave
    assert lote.chaves_substituidas == [('regime', ('9.053/2026', '11.222.333/0001-81'), nova)]


def test_ajustar_no_lote_recusa_chave_repetida_vazia_e_ato_inexistente():
    lote = _lote_com_regimes()
    with pytest.raises(edicao.ChaveEmConflito):
        edicao.ajustar_no_lote(lote, 'regime', _chave_regime(), {'Nº DO REGIME ESPECIAL': '2/2026',
                                                                  'CNPJ REQUERENTE': '11.222.333/0001-81'})
    with pytest.raises(edicao.ChaveVazia):
        edicao.ajustar_no_lote(lote, 'regime', _chave_regime(), {'CNPJ REQUERENTE': ''})
    with pytest.raises(edicao.RegistroInexistente):
        edicao.ajustar_no_lote(lote, 'regime', {'Nº DO REGIME ESPECIAL': 'x', 'CNPJ REQUERENTE': 'y'}, {})
    assert lote.regimes[0]['CNPJ REQUERENTE'] == '11.222.333/0001-81'      # nada mudou


def test_gravar_o_lote_ajustado_cria_ajustes_e_apelidos_que_protegem_a_reimportacao(tmp_path):
    conn = _conn(tmp_path)
    lote = _lote_com_regimes()
    edicao.ajustar_no_lote(lote, 'regime', _chave_regime(),
                           {'VIGÊNCIA DO RE': '12 meses', 'CNPJ REQUERENTE': '55'})
    armazenamento.persistir_lote(conn, lote)

    nova = ('9.053/2026', '55')
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, nova) == ['VIGÊNCIA DO RE']
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R,
                                        ('9.053/2026', '11.222.333/0001-81')) == nova
    # reimportar o PDF original (chave antiga, sem vigência) não desfaz o ajuste nem duplica
    armazenamento.salvar_regimes(conn, [_regime(**{'VIGÊNCIA DO RE': ''})])
    linhas = [r for r in armazenamento.buscar_regimes(conn) if r['Nº DO REGIME ESPECIAL'] == '9.053/2026']
    assert len(linhas) == 1 and linhas[0]['CNPJ REQUERENTE'] == '55'
    assert linhas[0]['VIGÊNCIA DO RE'] == '12 meses'


# --- chave trocada na análise confere o banco --------------------------------
def _lote_de(*regs):
    return pipeline.Lote(regimes=list(regs))


def test_analise_recusa_chave_que_pertence_a_outro_ato_do_banco(tmp_path):
    conn = _conn(tmp_path)
    a, b = _regime(), _regime(**{'Nº DO REGIME ESPECIAL': '2/2026', 'EMPRESA': 'Beta'})
    armazenamento.salvar_regimes(conn, [a, b])
    lote = _lote_de(dict(a))
    with pytest.raises(edicao.ChaveEmConflito):
        edicao.ajustar_no_lote(lote, 'regime', _chave_regime(a),
                               {'Nº DO REGIME ESPECIAL': '2/2026'}, conn=conn)
    assert lote.regimes[0] == a and lote.ajustados == {} and lote.chaves_substituidas == []


def test_analise_recusa_trocar_a_chave_de_ato_ja_gravado(tmp_path):
    conn = _conn(tmp_path)
    a = _regime()
    armazenamento.salvar_regimes(conn, [a])
    lote = _lote_de(dict(a))
    with pytest.raises(edicao.ChaveJaGravada):
        edicao.ajustar_no_lote(lote, 'regime', _chave_regime(a),
                               {'CNPJ REQUERENTE': '33'}, conn=conn)
    assert lote.regimes[0] == a and lote.ajustados == {} and lote.chaves_substituidas == []
    assert len(armazenamento.buscar_regimes(conn)) == 1


def test_analise_ainda_deixa_corrigir_a_chave_e_campos_de_ato_ainda_nao_gravado(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime(**{'Nº DO REGIME ESPECIAL': '2/2026'})])
    a = _regime()
    lote = _lote_de(dict(a))
    r = edicao.ajustar_no_lote(lote, 'regime', _chave_regime(a),
                               {'CNPJ REQUERENTE': '33'}, conn=conn)
    assert r['chave_trocada'] is True and lote.regimes[0]['CNPJ REQUERENTE'] == '33'
    # editar campo comum de ato já gravado continua permitido
    gravado = _regime(**{'Nº DO REGIME ESPECIAL': '2/2026'})
    lote2 = _lote_de(dict(gravado))
    r = edicao.ajustar_no_lote(lote2, 'regime', _chave_regime(gravado),
                               {'EMENTA': 'x'}, conn=conn)
    assert r['alterados'] == ['EMENTA']
