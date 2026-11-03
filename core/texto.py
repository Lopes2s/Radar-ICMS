# core/texto.py
"""Normalização de texto para busca: sem acento, sem diferença de caixa."""
import re
import unicodedata

from core.pdf_text import MARCA_CITACAO, MARCA_PARAGRAFO

_ESPACOS = re.compile(r'\s+')


def normalizar(texto) -> str:
    """'Substituição  TRIBUTÁRIA' -> 'substituicao tributaria'.

    Também descarta as marcas invisíveis que o parser deixa na Resposta
    (MARCA_CITACAO some; MARCA_PARAGRAFO vira espaço) e colapsa qualquer
    sequência de espaços/quebras num espaço só. None e vazio viram ''."""
    if not texto:
        return ''
    texto = str(texto).replace(MARCA_CITACAO, '').replace(MARCA_PARAGRAFO, ' ')
    decomposto = unicodedata.normalize('NFKD', texto)
    sem_acento = ''.join(c for c in decomposto if not unicodedata.combining(c))
    return _ESPACOS.sub(' ', sem_acento).strip().casefold()
