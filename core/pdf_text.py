# core/pdf_text.py
import re
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
