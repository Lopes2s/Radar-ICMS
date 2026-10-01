# core/pdf_text.py
import re
import statistics
from collections import Counter
import pdfplumber


_LINHA_PROTOCOLO = re.compile(r'(PROTOCOLOS?:)([^\n]*)', re.IGNORECASE)
_ESPACO_ENTRE_DIGITOS = re.compile(r'(?<=\d)[ \t](?=\d)')


def _junta_digitos_do_protocolo(m: re.Match) -> str:
    return m.group(1) + _ESPACO_ENTRE_DIGITOS.sub('', m.group(2))


def _limpa_ruido_ocr(texto: str) -> str:
    """Corrige ruídos comuns de extração.

    - Espaço espúrio dentro do número de protocolo:
      'PROTOCOLOS: 2 5.152.191-3' -> 'PROTOCOLOS: 25.152.191-3'
    - 'I CMS' -> 'ICMS' (recorrente nas súmulas)

    Conservador: a junção de dígitos só vale na linha do rótulo PROTOCOLO(S),
    onde o ruído foi observado, e nunca atravessa quebra de linha. Aplicada
    ao texto todo, colava CNPJ e datas ao item numerado da linha seguinte
    ('0001-21\n1. DA' -> '0001-211. DA').
    """
    if not texto:
        return ""
    texto = _LINHA_PROTOCOLO.sub(_junta_digitos_do_protocolo, texto)
    texto = texto.replace('I CMS', 'ICMS')
    return texto


def texto_simples(caminho_pdf: str) -> str:
    """Concatena o texto de todas as páginas (layout de coluna única)."""
    partes = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            partes.append(pagina.extract_text() or "")
    return _limpa_ruido_ocr("\n".join(partes))


def texto_por_colunas(caminho_pdf: str) -> str:
    """Extrai respeitando 2 colunas: lê a coluna esquerda inteira, depois a direita.

    Mantém cada matéria (regime/despacho) contígua em vez de intercalar linhas.
    """
    blocos = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            w, h = pagina.width, pagina.height
            esquerda = pagina.within_bbox((0, 0, w / 2, h)).extract_text() or ""
            direita = pagina.within_bbox((w / 2, 0, w, h)).extract_text() or ""
            blocos.append(esquerda)
            blocos.append(direita)
    return _limpa_ruido_ocr("\n".join(blocos))


def detecta_fonte(caminho_pdf: str) -> str:
    """Heurística textual: 'consulta', 'regime' ou 'desconhecido'.

    Pode ser reforçada pela pasta de origem, mas isto já funciona como
    confirmação pelo conteúdo da primeira página.
    """
    with pdfplumber.open(caminho_pdf) as pdf:
        if not pdf.pages:
            return "desconhecido"
        amostra = (pdf.pages[0].extract_text() or "")[:1500].upper()
    if "SETOR CONSULTIVO" in amostra or "CONSULTA Nº" in amostra:
        return "consulta"
    if ("RECEITA ESTADUAL DO PARANÁ" in amostra or "REGIME ESPECIAL" in amostra
            or "DIÁRIO" in amostra):
        return "regime"
    return "desconhecido"


# Marcador de início de parágrafo (U+2029, "separador de parágrafo").
# Prefixa a linha que abre um parágrafo. Não é uma linha em branco porque a
# limpeza de cabeçalho/rodapé do parser deixa linhas em branco no MEIO de
# parágrafos que atravessam a página; o marcador não tem essa ambiguidade.
# Removendo-o, o texto é idêntico ao de texto_simples().
MARCA_PARAGRAFO = "\u2029"

# Linhas que se repetem em toda página e que o parser descarta: traços,
# número de página (1-2 dígitos) e o cabeçalho "SECRETARIA ... / SETOR
# CONSULTIVO". Nunca abrem parágrafo e interrompem a referência de salto.
_RUIDO_DE_PAGINA = re.compile(
    r'^(?:_+|\d{1,2}|SECRETARIA DE ESTADO DA FAZENDA.*|SETOR CONSULTIVO)$',
    re.IGNORECASE,
)
_RECUO_MINIMO = 10          # pt acima da margem do corpo = recuo de 1ª linha
_FATOR_SALTO = 1.4          # salto > 1,4x o espaçamento mediano = novo parágrafo
_TETO_ESPACAMENTO = 30      # pt; saltos maiores não entram na mediana


def _marca_paragrafos_da_pagina(linhas: list[dict]) -> list[str]:
    """Devolve o texto de cada linha, prefixado com MARCA_PARAGRAFO quando a
    linha abre um parágrafo: recuo de primeira linha em relação à margem do
    corpo, ou salto vertical maior que o espaçamento normal da página.

    A margem do corpo é o x0 mais comum da página (empate: o menor), e o
    espaçamento normal é a mediana dos intervalos entre linhas do corpo —
    ambos derivados da própria página, não valores fixos.
    """
    corpo = [l for l in linhas if not _RUIDO_DE_PAGINA.match(l['text'].strip())]
    if not corpo:
        return [l['text'] for l in linhas]

    contagem = Counter(round(l['x0']) for l in corpo)
    maior = max(contagem.values())
    margem = min(x for x, n in contagem.items() if n == maior)
    intervalos = [b['top'] - a['top'] for a, b in zip(corpo, corpo[1:])
                  if 0 < b['top'] - a['top'] < _TETO_ESPACAMENTO]
    normal = statistics.median(intervalos) if intervalos else None

    saida, anterior = [], None
    for linha in linhas:
        if _RUIDO_DE_PAGINA.match(linha['text'].strip()):
            saida.append(linha['text'])
            anterior = None
            continue
        abre = linha['x0'] > margem + _RECUO_MINIMO
        if (not abre and anterior is not None and normal is not None
                and linha['top'] - anterior['top'] > normal * _FATOR_SALTO):
            abre = True
        saida.append((MARCA_PARAGRAFO if abre else '') + linha['text'])
        anterior = linha
    return saida


def texto_com_paragrafos(caminho_pdf: str) -> str:
    """Como texto_simples(), mas com MARCA_PARAGRAFO no início das linhas que
    abrem parágrafo (ver _marca_paragrafos_da_pagina). Usado só para o campo
    Resposta das consultas; o resto do parser segue lendo texto_simples()."""
    paginas = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            paginas.append("\n".join(
                _marca_paragrafos_da_pagina(pagina.extract_text_lines())))
    return _limpa_ruido_ocr("\n".join(paginas))
