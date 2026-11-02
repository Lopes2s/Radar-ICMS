# core/pipeline.py
"""Orquestração comum à CLI (processar.py) e à interface (app.py).

Processa um PDF por vez e acumula o resultado num Lote. Uma falha num PDF
vira uma linha de erro em `lote.arquivos` e nunca interrompe os demais.
"""
import logging
import re
from dataclasses import dataclass, field

from core import pdf_text
from parsers import consultas as p_consultas
from parsers import regimes as p_regimes

log = logging.getLogger('mapeador')

CHAVE_CONSULTAS = ['Ano', 'Nº da Consulta']
CHAVE_REGIMES = ['Nº DO REGIME ESPECIAL', 'CNPJ REQUERENTE']
TIPOS_FORCAVEIS = ('consulta', 'regime')


@dataclass
class Lote:
    consultas: list = field(default_factory=list)
    regimes: list = field(default_factory=list)
    descartes: list = field(default_factory=list)
    # uma linha por PDF: Arquivo, Tipo, Consultas, Regimes, Descartes, Erro
    arquivos: list = field(default_factory=list)


CRITERIOS_DEDUP = ('primeira', 'completo', 'recente')
CRITERIO_PADRAO = 'primeira'
_DATA_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')


def _preenchidos(registro: dict) -> int:
    return sum(1 for v in registro.values() if str(v or '').strip())


def _data_iso(registro: dict) -> str:
    """Data do ato em AAAA-MM-DD ('' se ausente ou fora do padrão)."""
    for campo in ('Data da Publicação', 'DATA'):
        valor = str(registro.get(campo, '') or '')
        if _DATA_ISO.fullmatch(valor):
            return valor
    return ''


def _prefere_o_novo(criterio: str, novo: dict, atual: dict) -> bool:
    if criterio == 'completo':
        return _preenchidos(novo) > _preenchidos(atual)   # empate: fica o primeiro
    if criterio == 'recente':
        return _data_iso(novo) >= _data_iso(atual)        # empate: o último processado
    return False                                          # 'primeira'


def dedup(linhas, campos, criterio=CRITERIO_PADRAO):
    """Um registro por chave `campos`. `criterio` decide qual fica quando a
    chave se repete: 'primeira' ocorrência (padrão), 'completo' (mais campos
    preenchidos) ou 'recente' (maior data; empate: o último processado).
    A ordem de saída é a ordem em que cada chave apareceu pela 1ª vez."""
    if criterio not in CRITERIOS_DEDUP:
        raise ValueError(f"criterio deve ser um de {CRITERIOS_DEDUP}: {criterio!r}")
    escolhidos, ordem = {}, []
    for r in linhas:
        chave = tuple(r.get(c, '') for c in campos)
        if chave not in escolhidos:
            escolhidos[chave] = r
            ordem.append(chave)
        elif _prefere_o_novo(criterio, r, escolhidos[chave]):
            escolhidos[chave] = r
    return [escolhidos[chave] for chave in ordem]


def _texto_com_paragrafos_ou_none(caminho: str):
    """Texto com marcas de parágrafo, ou None se a extração falhar: os
    parágrafos são um acréscimo; sem eles a Resposta sai achatada como antes."""
    try:
        return pdf_text.texto_com_paragrafos(caminho)
    except Exception:  # noqa: BLE001
        log.warning('parágrafos indisponíveis para %s; usando texto achatado',
                    caminho, exc_info=True)
        return None


def processar_arquivo(lote: Lote, caminho: str, nome: str,
                      forcar: str | None = None) -> dict:
    """Processa um PDF, acumula no `lote` e devolve a linha do arquivo.

    `forcar` é None (detecta pelo conteúdo), 'consulta' ou 'regime'.
    Exceções ao ler/parsear o PDF viram Tipo 'erro' com a mensagem em
    'Erro' — o lote segue. Só um `forcar` inválido levanta ValueError,
    porque é erro de quem chama, não do PDF.
    """
    if forcar is not None and forcar not in TIPOS_FORCAVEIS:
        raise ValueError(f"forcar deve ser None ou um de {TIPOS_FORCAVEIS}: {forcar!r}")

    linha = {'Arquivo': nome, 'Tipo': '', 'Consultas': 0, 'Regimes': 0,
             'Descartes': 0, 'Erro': ''}
    try:
        tipo = forcar or pdf_text.detecta_fonte(caminho)
        if tipo == 'consulta':
            regs = p_consultas.parse(pdf_text.texto_simples(caminho),
                                     _texto_com_paragrafos_ou_none(caminho))
            lote.consultas.extend(regs)
            linha['Consultas'] = len(regs)
        elif tipo == 'regime':
            regs, desc = p_regimes.parse(pdf_text.texto_por_colunas(caminho))
            for d in desc:
                d['Arquivo'] = nome
            lote.regimes.extend(regs)
            lote.descartes.extend(desc)
            linha['Regimes'] = len(regs)
            linha['Descartes'] = len(desc)
        linha['Tipo'] = tipo
    except Exception as erro:  # noqa: BLE001 — um PDF ruim não pode matar o lote
        log.error('falha ao processar %s', nome, exc_info=True)
        linha['Tipo'] = 'erro'
        linha['Erro'] = f"{type(erro).__name__}: {erro}"
    lote.arquivos.append(linha)
    return linha


def finalizar(lote: Lote, criterio: str = CRITERIO_PADRAO) -> Lote:
    """Deduplica consultas e regimes do lote (no lugar) e o devolve."""
    lote.consultas = dedup(lote.consultas, CHAVE_CONSULTAS, criterio)
    lote.regimes = dedup(lote.regimes, CHAVE_REGIMES, criterio)
    return lote
