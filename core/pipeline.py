# core/pipeline.py
"""Orquestração comum à CLI (processar.py) e à interface (app.py).

Processa um PDF por vez e acumula o resultado num Lote. Uma falha num PDF
vira uma linha de erro em `lote.arquivos` e nunca interrompe os demais.
"""
from dataclasses import dataclass, field

from core import pdf_text
from parsers import consultas as p_consultas
from parsers import regimes as p_regimes

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


def dedup(linhas, campos):
    """Remove repetidos pela chave `campos`, mantendo a primeira ocorrência."""
    vistos, unicos = set(), []
    for r in linhas:
        chave = tuple(r.get(c, '') for c in campos)
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)
    return unicos


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
            regs = p_consultas.parse(pdf_text.texto_simples(caminho))
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
        linha['Tipo'] = 'erro'
        linha['Erro'] = f"{type(erro).__name__}: {erro}"
    lote.arquivos.append(linha)
    return linha


def finalizar(lote: Lote) -> Lote:
    """Deduplica consultas e regimes do lote (no lugar) e o devolve."""
    lote.consultas = dedup(lote.consultas, CHAVE_CONSULTAS)
    lote.regimes = dedup(lote.regimes, CHAVE_REGIMES)
    return lote
