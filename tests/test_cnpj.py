# tests/test_cnpj.py
"""Consulta do CNPJ na BrasilAPI. NENHUM teste aqui usa a rede: a abertura da URL é
sempre um `abrir` falso."""
import io
import json
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from core import armazenamento, cnpj
from core.pipeline import Lote

BB = '00.000.000/0001-91'
ALFA = '11.222.333/0001-81'
CNPJS_VALIDOS = ['00000000000191', '11222333000181', '33000167000101', '60746948000112']
AGORA = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def _resposta(cnae=6422100, situacao='ATIVA', razao='BANCO DO BRASIL SA'):
    return json.dumps({
        'cnpj': '00000000000191', 'razao_social': razao, 'cnae_fiscal': cnae,
        'cnae_fiscal_descricao': 'Bancos múltiplos, com carteira comercial',
        'descricao_situacao_cadastral': situacao,
        'cnaes_secundarios': [{'codigo': 6499999, 'descricao': 'Outras'}],
    }).encode('utf-8')


class Rede:
    """`abrir` falso: devolve uma resposta pronta (ou levanta o erro dado) e anota as URLs."""
    def __init__(self, resposta=None, erro=None):
        self.resposta = _resposta() if resposta is None else resposta
        self.erro, self.urls = erro, []

    def __call__(self, url, *args, **kw):
        self.urls.append(url)
        if self.erro is not None:
            raise self.erro
        return self.resposta


def _http(codigo):
    return urllib.error.HTTPError('u', codigo, 'x', {}, io.BytesIO(b''))


def _conn(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / 'c.db'))
    armazenamento.criar_esquema(conn)
    return conn


# --- consultar --------------------------------------------------------------
def test_consultar_devolve_cnae_e_situacao_e_pede_so_os_digitos():
    rede = Rede()
    dados = cnpj.consultar(BB, rede)
    assert rede.urls == ['https://brasilapi.com.br/api/cnpj/v1/00000000000191']
    assert dados == {'cnpj': '00000000000191', 'razao_social': 'BANCO DO BRASIL SA',
                     'cnae_codigo': '6422100',
                     'cnae_descricao': 'Bancos múltiplos, com carteira comercial',
                     'situacao': 'ATIVA'}


def test_cnae_com_zero_a_esquerda_volta_com_sete_digitos():
    assert cnpj.consultar(BB, Rede(_resposta(cnae=111301)))['cnae_codigo'] == '0111301'


def test_cnpj_invalido_nem_chama_a_rede():
    rede = Rede()
    with pytest.raises(cnpj.CnpjInvalido):
        cnpj.consultar('11.111.111/1111-11', rede)
    with pytest.raises(cnpj.CnpjInvalido):
        cnpj.consultar('', rede)
    assert rede.urls == []


@pytest.mark.parametrize('erro,esperado', [
    (_http(404), cnpj.CnpjNaoEncontrado),
    (_http(400), cnpj.CnpjInvalido),
    (_http(429), cnpj.ConsultaIndisponivel),
    (_http(503), cnpj.ConsultaIndisponivel),
    (urllib.error.URLError('sem rede'), cnpj.ConsultaIndisponivel),
    (TimeoutError('demorou'), cnpj.ConsultaIndisponivel),
    (ConnectionResetError('caiu'), cnpj.ConsultaIndisponivel),
])
def test_erros_de_rede_viram_as_excecoes_do_modulo(erro, esperado):
    with pytest.raises(esperado):
        cnpj.consultar(BB, Rede(erro=erro))


@pytest.mark.parametrize('corpo', [b'<html>manutencao</html>', b'[1, 2]', b''])
def test_resposta_ilegivel_e_consulta_indisponivel(corpo):
    with pytest.raises(cnpj.ConsultaIndisponivel):
        cnpj.consultar(BB, Rede(corpo))


def test_formatar_cnae():
    assert cnpj.formatar_cnae('6422100') == '6422-1/00'
    assert cnpj.formatar_cnae('4930-2/02') == '4930-2/02'
    assert cnpj.formatar_cnae('') == ''
    assert cnpj.formatar_cnae('123') == '123'


@pytest.mark.parametrize('valor,esperado', [
    (None, True), ('1', True), ('0', False), ('não', False), ('OFF', False), ('false', False)])
def test_habilitada_le_a_variavel_de_ambiente(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv('MAPEADOR_CONSULTA_CNPJ', raising=False)
    else:
        monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', valor)
    assert cnpj.habilitada() is esperado


# --- atualizar ---------------------------------------------------------------
def test_atualizar_consulta_grava_e_reaproveita_a_consulta_recente(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    r1 = cnpj.atualizar(conn, [BB, '00000000000191'], abrir=rede, agora=AGORA,
                        dormir=lambda s: None)
    assert (r1['consultados'], r1['do_cache']) == (1, 0)       # repetido na lista: uma vez
    assert armazenamento.cnpj_receita_de(conn, BB)['cnae_codigo'] == '6422100'
    r2 = cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA + timedelta(days=29),
                        dormir=lambda s: None)
    assert (r2['consultados'], r2['do_cache']) == (0, 1)
    assert len(rede.urls) == 1


def test_consulta_com_mais_de_30_dias_e_refeita(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA, dormir=lambda s: None)
    r = cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA + timedelta(days=31),
                       dormir=lambda s: None)
    assert r['consultados'] == 1 and len(rede.urls) == 2


def test_forcar_ignora_a_consulta_guardada(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA, dormir=lambda s: None)
    r = cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA, dormir=lambda s: None, forcar=True)
    assert r['consultados'] == 1 and len(rede.urls) == 2


def test_cnpj_invalido_ou_em_branco_e_ignorado_sem_chamar_a_rede(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    r = cnpj.atualizar(conn, ['', '11.111.111/1111-11', None], abrir=rede, agora=AGORA)
    assert r['ignorados'] == 2 and r['consultados'] == 0 and rede.urls == []  # '' e None contam uma vez


def test_duas_falhas_de_conexao_seguidas_interrompem_o_resto_do_lote(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede(erro=urllib.error.URLError('sem rede'))
    r = cnpj.atualizar(conn, CNPJS_VALIDOS, abrir=rede, agora=AGORA, dormir=lambda s: None)
    assert len(rede.urls) == 2                                  # parou na segunda falha
    assert r['interrompido'] is True and r['pendentes'] == 2 and len(r['falhas']) == 2
    assert r['consultados'] == 0
    assert armazenamento.cnpj_receita_de(conn, BB) is None      # nada gravado


def test_cnpj_nao_encontrado_nao_interrompe_o_lote(tmp_path):
    conn = _conn(tmp_path)
    respostas = iter([_http(404), _http(404), _http(404), None])

    def abrir(url):
        r = next(respostas)
        if r is not None:
            raise r
        return _resposta()

    r = cnpj.atualizar(conn, CNPJS_VALIDOS, abrir=abrir, agora=AGORA, dormir=lambda s: None)
    assert r['interrompido'] is False and len(r['falhas']) == 3 and r['consultados'] == 1


def test_pausa_entre_consultas_reais_mas_nao_antes_da_primeira(tmp_path):
    conn = _conn(tmp_path)
    pausas = []
    cnpj.atualizar(conn, CNPJS_VALIDOS[:3], abrir=Rede(), agora=AGORA, dormir=pausas.append)
    assert pausas == [cnpj.PAUSA, cnpj.PAUSA]


def test_atualizar_do_lote_usa_so_os_cnpjs_dos_regimes(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    lote = Lote(regimes=[{'CNPJ REQUERENTE': ALFA}, {'CNPJ REQUERENTE': ''}],
                consultas=[{'CNPJ REQUERENTE': BB}])
    r = cnpj.atualizar_do_lote(conn, lote, abrir=rede, agora=AGORA, dormir=lambda s: None)
    assert rede.urls == ['https://brasilapi.com.br/api/cnpj/v1/11222333000181']
    assert r['consultados'] == 1 and r['ignorados'] == 1


def test_erro_inesperado_na_consulta_nao_escapa_de_atualizar(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede(erro=ValueError('boom'))
    r = cnpj.atualizar(conn, [ALFA], abrir=rede, agora=AGORA, dormir=lambda s: None)
    assert r['consultados'] == 0 and len(r['falhas']) == 1
    assert r['falhas'][0][1].startswith('erro inesperado')


def test_erros_inesperados_seguidos_interrompem_o_lote(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede(erro=ValueError('boom'))
    r = cnpj.atualizar(conn, ['00000000000191', '11222333000181', '33000167000101'],
                       abrir=rede, agora=AGORA, dormir=lambda s: None)
    assert r['interrompido'] and r['pendentes'] == 1 and len(rede.urls) == 2


def test_atualizar_do_lote_consulta_o_cnpj_corrigido_do_ato(tmp_path):
    from core import edicao
    conn = _conn(tmp_path)
    regime = {'ANO': '2026', 'DATA': '2026-03-01', 'Nº DO REGIME ESPECIAL': '9.053/2026',
              'EMPRESA': 'Alfa', 'CNPJ REQUERENTE': ALFA, 'VIGÊNCIA DO RE': '', 'EMENTA': 'e'}
    armazenamento.salvar_regimes(conn, [regime])
    edicao.editar_registro(conn, 'regime',
                           {'Nº DO REGIME ESPECIAL': '9.053/2026', 'CNPJ REQUERENTE': ALFA},
                           {'CNPJ REQUERENTE': BB})
    rede = Rede()
    lote = Lote(regimes=[dict(regime)])
    cnpj.atualizar_do_lote(conn, lote, abrir=rede, agora=AGORA, dormir=lambda s: None)
    assert rede.urls == ['https://brasilapi.com.br/api/cnpj/v1/00000000000191']


# --- mensagem e divergência --------------------------------------------------
def test_mensagem_do_resumo():
    base = {'consultados': 0, 'do_cache': 0, 'ignorados': 0, 'falhas': [],
            'interrompido': False, 'pendentes': 0}
    assert cnpj.mensagem_do_resumo(None) is None
    assert cnpj.mensagem_do_resumo(base) is None
    assert cnpj.mensagem_do_resumo({**base, 'do_cache': 4, 'ignorados': 1}) is None
    msg = cnpj.mensagem_do_resumo({**base, 'consultados': 3,
                                   'falhas': [('x', 'sem acesso à BrasilAPI (timeout)')],
                                   'pendentes': 2})
    assert '3 CNPJ(s) consultado(s)' in msg
    assert '1 sem resposta (sem acesso à BrasilAPI (timeout))' in msg
    assert '2 ficaram pendentes' in msg


def test_divergencia_so_existe_quando_o_regime_tem_cnae_diferente():
    receita = {'cnae_codigo': '6422100'}
    assert cnpj.divergencia({'CNAE REQUERENTE': ''}, receita) is None          # em branco
    assert cnpj.divergencia({'CNAE REQUERENTE': '6422-1/00'}, receita) is None  # igual
    assert cnpj.divergencia({'CNAE REQUERENTE': '4930202'}, receita) == {
        'regime': '4930-2/02', 'receita': '6422-1/00'}
    assert cnpj.divergencia({'CNAE REQUERENTE': '4930202'}, None) is None
