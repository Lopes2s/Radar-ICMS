# core/cnpj.py
"""Consulta do CNPJ do requerente na BrasilAPI: CNAE principal e situação cadastral.

A consulta roda sozinha ao GRAVAR um lote (Execucao.gravar na CLI; app.py na
interface) e, sob demanda, pelo botão do detalhe do regime. O resultado fica na
tabela `cnpj_receita`, À PARTE do regime: o CNAE da Receita é o CNAE ATUAL da
empresa e pode diferir do vigente na data do regime, então ele nunca sobrescreve
os campos do regime sozinho (o administrador decide aplicá-lo; ver app.py).

Falha de rede nunca impede a gravação: `atualizar` não levanta por causa de
internet fora do ar ou da API; devolve o que aconteceu num resumo. Só o CNPJ sai
da máquina (dado público); a consulta pode ser desligada com
MAPEADOR_CONSULTA_CNPJ=0 (e, na CLI, com --sem-consulta-cnpj).

Sem Streamlit; sem dependência de terceiros (só `urllib`).
"""
import http.client
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from core import armazenamento
from core.diagnostico import cnpj_valido
from core.pipeline import CHAVE_REGIMES

URL = 'https://brasilapi.com.br/api/cnpj/v1/{cnpj}'
TIMEOUT = 5              # segundos por consulta
CACHE_DIAS = 30          # consulta mais nova que isso é reaproveitada
PAUSA = 0.3              # segundos entre duas consultas reais (gentileza com a API pública)
MAX_FALHAS_SEGUIDAS = 2  # sem internet: para de tentar o resto do lote


class CnpjInvalido(ValueError):
    """CNPJ mal formado ou com dígitos verificadores errados."""


class CnpjNaoEncontrado(LookupError):
    """A Receita não conhece esse CNPJ."""


class ConsultaIndisponivel(RuntimeError):
    """Sem internet, API fora do ar, limite de uso ou resposta ilegível."""


def so_digitos(cnpj) -> str:
    return ''.join(c for c in str(cnpj or '') if c.isdigit())


def formatar_cnae(codigo) -> str:
    """'6422100' -> '6422-1/00'; qualquer outra coisa volta como veio."""
    digitos = so_digitos(codigo)
    return f'{digitos[:4]}-{digitos[4]}/{digitos[5:]}' if len(digitos) == 7 else str(codigo or '')


def habilitada() -> bool:
    """MAPEADOR_CONSULTA_CNPJ=0 desliga a consulta automática (máquina sem internet)."""
    valor = os.environ.get('MAPEADOR_CONSULTA_CNPJ', '1').strip().lower()
    return valor not in ('0', 'nao', 'não', 'false', 'off')


def _abrir(url: str, timeout: float = TIMEOUT) -> bytes:
    pedido = urllib.request.Request(
        url, headers={'User-Agent': 'mapeador-pr', 'Accept': 'application/json'})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return resposta.read()


def consultar(cnpj, abrir=None) -> dict:
    """Consulta UM CNPJ. `abrir(url) -> bytes` é injetável (os testes nunca usam a rede).

    Devolve {'cnpj', 'razao_social', 'cnae_codigo', 'cnae_descricao', 'situacao'}.
    Levanta CnpjInvalido (sem chamar a rede se os dígitos não conferem),
    CnpjNaoEncontrado ou ConsultaIndisponivel."""
    digitos = so_digitos(cnpj)
    if not cnpj_valido(digitos):
        raise CnpjInvalido(f'CNPJ inválido: {cnpj!r}')
    abrir = abrir or _abrir
    try:
        bruto = abrir(URL.format(cnpj=digitos))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            raise CnpjNaoEncontrado(f'CNPJ {digitos} não encontrado na Receita') from erro
        if erro.code == 400:
            raise CnpjInvalido(f'A BrasilAPI recusou o CNPJ {digitos}') from erro
        raise ConsultaIndisponivel(f'BrasilAPI respondeu HTTP {erro.code}') from erro
    except (OSError, http.client.HTTPException) as erro:   # URLError e timeout são OSError
        raise ConsultaIndisponivel(f'sem acesso à BrasilAPI ({erro})') from erro
    try:
        dados = json.loads(bruto)
    except ValueError as erro:
        raise ConsultaIndisponivel('resposta da BrasilAPI ilegível') from erro
    if not isinstance(dados, dict):
        raise ConsultaIndisponivel('resposta da BrasilAPI ilegível')
    codigo = so_digitos(dados.get('cnae_fiscal'))
    return {'cnpj': digitos,
            'razao_social': str(dados.get('razao_social') or ''),
            'cnae_codigo': codigo.zfill(7) if codigo else '',
            'cnae_descricao': str(dados.get('cnae_fiscal_descricao') or ''),
            'situacao': str(dados.get('descricao_situacao_cadastral') or '')}


def _recente(consultado_em, agora) -> bool:
    try:
        return agora - datetime.fromisoformat(consultado_em) < timedelta(days=CACHE_DIAS)
    except (TypeError, ValueError):
        return False


def atualizar(conn, cnpjs, abrir=None, agora=None, dormir=time.sleep, forcar=False) -> dict:
    """Consulta e grava em `cnpj_receita` os CNPJs sem consulta recente.

    `forcar` ignora a consulta guardada. Não levanta por falha de rede: duas
    falhas de conexão seguidas interrompem o resto do lote (ficam `pendentes`).
    Devolve {'consultados', 'do_cache', 'ignorados' (inválidos/em branco),
    'falhas': [(cnpj, motivo)], 'interrompido': bool, 'pendentes'}."""
    agora = agora or datetime.now(timezone.utc)
    resumo = {'consultados': 0, 'do_cache': 0, 'ignorados': 0, 'falhas': [],
              'interrompido': False, 'pendentes': 0}
    vistos, seguidas, ja_consultou = set(), 0, False
    for bruto in cnpjs:
        digitos = so_digitos(bruto)
        if digitos in vistos:
            continue
        vistos.add(digitos)
        if not cnpj_valido(digitos):
            resumo['ignorados'] += 1
            continue
        try:
            guardado = armazenamento.cnpj_receita_de(conn, digitos)
            if not forcar and guardado and _recente(guardado['consultado_em'], agora):
                resumo['do_cache'] += 1
                continue
            if resumo['interrompido']:
                resumo['pendentes'] += 1
                continue
            if ja_consultou:
                dormir(PAUSA)
            ja_consultou = True
            try:
                dados = consultar(digitos, abrir)
            except ConsultaIndisponivel as erro:
                resumo['falhas'].append((digitos, str(erro)))
                seguidas += 1
                resumo['interrompido'] = seguidas >= MAX_FALHAS_SEGUIDAS
                continue
            except (CnpjNaoEncontrado, CnpjInvalido) as erro:
                resumo['falhas'].append((digitos, str(erro)))
                seguidas = 0
                continue
            seguidas = 0
            armazenamento.salvar_cnpj_receita(
                conn, dados, consultado_em=agora.isoformat(timespec='seconds'))
            resumo['consultados'] += 1
        except Exception as erro:   # a gravação já foi feita: nada aqui pode escapar
            logging.getLogger('mapeador').exception('Erro inesperado ao consultar o CNPJ %s', digitos)
            resumo['falhas'].append(
                (digitos, f'erro inesperado ({type(erro).__name__}: {erro})'))
            seguidas += 1
            resumo['interrompido'] = seguidas >= MAX_FALHAS_SEGUIDAS
    return resumo


def atualizar_do_lote(conn, lote, **opcoes) -> dict:
    """`atualizar` para os CNPJs dos regimes do lote (as consultas não têm CNPJ).

    Usa o CNPJ que o ato tem AGORA: se o administrador corrigiu a chave do regime,
    o CNPJ do PDF é só um apelido (`chaves_substituidas`) e vale o corrigido."""
    return atualizar(conn, [_cnpj_atual(conn, r) for r in lote.regimes], **opcoes)


def _cnpj_atual(conn, regime) -> str:
    chave = tuple(regime.get(c, '') for c in CHAVE_REGIMES)
    try:
        return armazenamento.resolver_chave(conn, 'regimes', CHAVE_REGIMES, chave)[-1]
    except Exception:   # sem a resolução, vale o CNPJ do PDF
        return chave[-1]


def mensagem_do_resumo(resumo) -> str | None:
    """Uma frase para a tela/CLI; None quando não houve nada a dizer."""
    if not resumo:
        return None
    partes = []
    if resumo['consultados']:
        partes.append(f"{resumo['consultados']} CNPJ(s) consultado(s)")
    if resumo['falhas']:
        partes.append(f"{len(resumo['falhas'])} sem resposta ({resumo['falhas'][0][1]})")
    if resumo['pendentes']:
        partes.append(f"{resumo['pendentes']} ficaram pendentes "
                      "(consulte pelo detalhe do regime)")
    return '; '.join(partes) or None


def divergencia(regime: dict, receita: dict | None) -> dict | None:
    """Se o regime TEM um CNAE informado e ele difere do da Receita, devolve os dois
    já formatados; senão None (CNAE em branco não é divergência)."""
    do_regime = so_digitos(regime.get('CNAE REQUERENTE'))
    da_receita = so_digitos((receita or {}).get('cnae_codigo'))
    if do_regime and da_receita and do_regime != da_receita:
        return {'regime': formatar_cnae(do_regime), 'receita': formatar_cnae(da_receita)}
    return None
