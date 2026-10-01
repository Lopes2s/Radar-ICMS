# parsers/consultas.py
import re
from datetime import datetime

from core.pdf_text import MARCA_CITACAO, MARCA_PARAGRAFO

# Cada página extraída traz cabeçalho E rodapé: o cabeçalho ("SECRETARIA ...
# DO PARANÁ - SEFA", NA LINHA SEGUINTE "SETOR CONSULTIVO" + traços) abre o
# texto da página; o rodapé (traços + número da página, em linha própria)
# fecha o texto DESSA MESMA página — portanto sobra, na concatenação, entre
# o fim do conteúdo de uma página e o cabeçalho da página seguinte:
# "...fim do conteúdo\n_____\n3\nSECRETARIA...SETOR CONSULTIVO\n_____\n...".
# A versão antiga só casava o cabeçalho; o rodapé da página anterior (traços
# + nº de página) sobrava intocado no meio da frase sempre que a quebra de
# página caía dentro de um campo (bug real: "acesso a" + rodapé da pág. 3 +
# "recursos especializados..." no Problema da Consulta nº 002 do documento
# de 2026). "[^\n]*\n" no cabeçalho impede o casamento de atravessar
# parágrafos: sem isso, uma menção à Secretaria no corpo do texto casava até
# o cabeçalho da página seguinte e apagava tudo no meio.
#
# O rodapé só é reconhecido com 1 ou 2 dígitos e não seguido de outro dígito
# (`\d{1,2}(?!\d)`): isso o distingue de um número que abre legitimamente o
# parágrafo seguinte, como um ano ("2023 foi o ano..." tem 4 dígitos e não
# casa). Sem cabeçalho depois (rodapé da última página do documento), o
# rodapé ainda é removido sozinho — necessário para o campo RESPOSTA, que
# pode se estender até o fim do texto.
_CABECALHO = re.compile(
    r'_+\s*\d{1,2}(?!\d)\s*(?:SECRETARIA DE ESTADO DA FAZENDA DO PARAN[ÁA][^\n]*'
    r'\n\s*SETOR CONSULTIVO(?:\s*_+)*)?'
    r'|SECRETARIA DE ESTADO DA FAZENDA DO PARAN[ÁA][^\n]*\n\s*SETOR CONSULTIVO(?:\s*_+)*',
    re.IGNORECASE,
)

# "CONSULTA" em caixa alta só aparece no título de cada matéria; citações de
# precedentes no corpo do texto usam caixa mista ("Consulta nº", "consulta
# nº"). Por isso a âncora é case-sensitive nesse literal — não usa
# re.IGNORECASE — o que evita casar citações internas como títulos.
# "N[ºo°]\s*:?" tolera tanto "CONSULTA Nº 001" (2026) quanto "CONSULTA Nº:
# 001" (2023, com dois-pontos). O fim da data aceita ponto OU quebra de
# linha, porque nem todo formato termina a linha do título com ponto final.
_ANCORA = re.compile(
    r'\bCONSULTA\s+N[ºo°]\s*:?\s*(\d+)\s*,\s*de\s+([^\n.]+?)(?:\.|\n)',
)

_MESES = {
    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'marco': 3, 'abril': 4,
    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9,
    'outubro': 10, 'novembro': 11, 'dezembro': 12,
}


def _data_extenso_para_iso(texto_data: str):
    m = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', texto_data, re.IGNORECASE)
    if not m:
        return texto_data.strip()
    dia, mes_nome, ano = m.groups()
    mes = _MESES.get(mes_nome.lower())
    if not mes:
        return texto_data.strip()
    try:
        return datetime(int(ano), mes, int(dia)).strftime('%Y-%m-%d')
    except ValueError:
        return texto_data.strip()


# A maioria das consultas usa "SÚMULA:", mas parte delas (ex.: Consulta
# 001/2023) usa "ASSUNTO:" para o mesmo campo. Os dois alimentam o mesmo
# lugar na planilha.
_ROTULO_RESUMO = r'(?:S[ÚU]MULA|ASSUNTO)'


def _bloco_resumo(fatia: str):
    """Casa o bloco do rótulo (Súmula/Assunto). group(1) termina exatamente
    onde começa o parágrafo do problema — confirmado nas 60 consultas do
    documento real de 2023: todas retomam com "A consulente"/"A Consulente"
    logo após o rótulo. Esse mesmo ponto de corte alimenta _extrai_sumula()
    e _extrai_problema(), então a súmula não pode vazar para o problema por
    construção — ao contrário de cortar no primeiro ponto final, o que
    falha porque a súmula costuma ter vários ("ICMS. DIFERIMENTO.
    CONDIÇÕES.").
    """
    return re.search(
        rf'{_ROTULO_RESUMO}:\s*(.+?)(?:\n\s*\n|\nA consulente|\nRESPOSTA|\Z)',
        fatia, re.DOTALL | re.IGNORECASE,
    )


def _extrai_sumula(fatia: str) -> str:
    m = _bloco_resumo(fatia)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ""


# Fallback só para o caso degenerado de a fatia não conter "RESPOSTA" (não
# deveria acontecer com o formato real). Sem isso, um documento malformado
# devolveria a fatia inteira como problema; nunca é usado no caminho normal.
_LIMITE_SEGURANCA_PROBLEMA = 20000


def _extrai_problema(fatia: str) -> str:
    m = _bloco_resumo(fatia)
    inicio = m.end(1) if m else 0
    # "RESPOSTA" em caixa alta é sempre o cabeçalho de seção (confirmado:
    # 60 ocorrências em caixa alta == 60 consultas, uma por cabeçalho). Em
    # caixa baixa/mista a palavra aparece normalmente na prosa do problema
    # e da resposta (25 ocorrências no documento real, ex.: "em caso de
    # resposta afirmativa") — usar IGNORECASE aqui cortaria o problema no
    # meio de uma frase legítima em vez de no cabeçalho real.
    m_resposta = re.search(r'\bRESPOSTA\b', fatia[inicio:])
    fim = inicio + m_resposta.start() if m_resposta else inicio + _LIMITE_SEGURANCA_PROBLEMA
    return re.sub(r'\s+', ' ', fatia[inicio:fim]).strip()


# "RESPOSTA" em caixa alta é sempre o cabeçalho de seção que abre a resposta
# da SEFA (mesma âncora usada por _extrai_problema() para saber onde o
# problema termina). O campo Resposta é tudo o que vem depois desse
# cabeçalho até o fim da fatia — mas a fatia vai até o INÍCIO do título da
# consulta seguinte ("CONSULTA Nº..."), e a linha "PROTOCOLOS:" dessa
# próxima consulta fica ANTES do próprio título dela (mesmo motivo por que
# _extrai_protocolo busca no trecho ANTERIOR ao título, não dentro da
# fatia) — por isso sobra colada no fim da Resposta sempre que existe uma
# consulta seguinte no documento. _PROTOCOLO_DA_PROXIMA corta a Resposta
# antes dessa linha. Sem o rótulo "RESPOSTA" na fatia, o campo fica vazio em
# vez de quebrar a extração das demais consultas do lote.
_PROTOCOLO_DA_PROXIMA = re.compile(r'\n\s*PROTOCOLOS?:\s*\d', re.IGNORECASE)


def _extrai_resposta(fatia: str) -> str:
    m = re.search(r'\bRESPOSTA\b', fatia)
    if not m:
        return ""
    resto = fatia[m.end():]
    m_protocolo = _PROTOCOLO_DA_PROXIMA.search(resto)
    fim = m_protocolo.start() if m_protocolo else len(resto)
    return re.sub(r'\s+', ' ', resto[:fim]).strip()


# Aceita "CNAE 4930-2/02", "CNAE: 4930-2/02", "CNAE n.º 4930-2/02". O grupo
# começa e termina em dígito, para não levar o ponto final da frase.
_CNAE = re.compile(r'CNAE[\s:]*(?:n\.?\s*[ºo°]\.?\s*)?(\d[\d.\-/]*\d)', re.IGNORECASE)


def _extrai_cnae(problema: str) -> str:
    """CNAE da consulente. Recebe só o texto do problema: CNAEs citados na
    resposta (exemplos, precedentes) não são da consulente."""
    m = _CNAE.search(problema)
    return m.group(1) if m else ""


_DATA_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')


# O rótulo "PROTOCOLO(S):" fica na linha ANTERIOR ao título "CONSULTA Nº",
# por isso o protocolo é procurado no trecho entre a consulta anterior e o
# título atual, e não na fatia que começa no título. O rótulo pode vir no
# plural com vários números na mesma linha ("25.152.191-3, 25.152.192-1 e
# ..."); todos são mantidos, separados por "; ".
_LINHA_PROTOCOLO = re.compile(r'PROTOCOLOS?:([^\n]*)', re.IGNORECASE)
_NUMERO_PROTOCOLO = re.compile(r'\d{1,2}\.\d{3}\.\d{3}-\d')


def _extrai_protocolo(antes_do_titulo: str) -> str:
    linhas = _LINHA_PROTOCOLO.findall(antes_do_titulo)
    if not linhas:
        return ""
    return '; '.join(_NUMERO_PROTOCOLO.findall(linhas[-1]))


def _extrai_resposta_em_paragrafos(fatia_p: str) -> str:
    """Como _extrai_resposta(), mas parte da fatia do texto com
    MARCA_PARAGRAFO: junta as linhas de cada parágrafo com espaço e separa os
    parágrafos com linha em branco ("\\n\\n")."""
    m = re.search(r'\bRESPOSTA\b', fatia_p)
    if not m:
        return ""
    resto = fatia_p[m.end():]
    m_protocolo = _PROTOCOLO_DA_PROXIMA.search(resto)
    fim = m_protocolo.start() if m_protocolo else len(resto)
    paragrafos = (re.sub(r'\s+', ' ', p).strip()
                  for p in resto[:fim].split(MARCA_PARAGRAFO))
    return '\n\n'.join(p for p in paragrafos if p)


def _fatias_por_consulta(texto_paragrafos: str) -> dict:
    """Fatia o texto com marcadores pelas mesmas âncoras de parse() e indexa
    por (número, data ISO). Chave repetida é descartada: sem como saber qual
    fatia é de qual consulta, vale o texto achatado."""
    limpo = _CABECALHO.sub('\n', texto_paragrafos)
    ancoras = list(_ANCORA.finditer(limpo))
    fatias, repetidas = {}, set()
    for i, anc in enumerate(ancoras):
        fim = ancoras[i + 1].start() if i + 1 < len(ancoras) else len(limpo)
        chave = (anc.group(1).zfill(3), _data_extenso_para_iso(anc.group(2)))
        if chave in fatias:
            repetidas.add(chave)
        fatias[chave] = limpo[anc.start():fim]
    for chave in repetidas:
        del fatias[chave]
    return fatias


def _resposta_com_paragrafos(plana: str, fatia_p) -> str:
    """Troca a Resposta achatada pela versão com parágrafos só se ela tiver
    EXATAMENTE o mesmo texto (normalizada): parágrafos só acrescentam quebras,
    nunca alteram conteúdo. Qualquer divergência cai no achatado."""
    if fatia_p is None:
        return plana
    com = _extrai_resposta_em_paragrafos(fatia_p)
    # MARCA_CITACAO não é texto: sai da comparação (e só dela).
    sem_marcas = com.replace(MARCA_CITACAO, '')
    return com if ' '.join(sem_marcas.split()) == plana else plana


def parse(texto: str, texto_paragrafos: str | None = None) -> list[dict]:
    limpo = _CABECALHO.sub('\n', texto)
    ano_m = re.search(r'ANO:\s*(\d{4})', limpo)
    ano_doc = ano_m.group(1) if ano_m else ""
    fatias_p = _fatias_por_consulta(texto_paragrafos) if texto_paragrafos else {}

    ancoras = list(_ANCORA.finditer(limpo))
    registros = []
    for i, anc in enumerate(ancoras):
        inicio_antes = ancoras[i - 1].end() if i else 0
        inicio = anc.start()
        fim = ancoras[i + 1].start() if i + 1 < len(ancoras) else len(limpo)
        fatia = limpo[inicio:fim]
        numero = anc.group(1).zfill(3)
        data_iso = _data_extenso_para_iso(anc.group(2))
        problema = _extrai_problema(fatia)
        # a numeração reinicia a cada ano: o ano da própria consulta vale mais
        # que o "ANO:" do documento, que só entra quando a data não foi lida.
        ano = data_iso[:4] if _DATA_ISO.fullmatch(data_iso) else ano_doc
        registros.append({
            'Ano': ano,
            'Nº da Consulta': numero,
            'Data da Publicação': data_iso,
            'Protocolo': _extrai_protocolo(limpo[inicio_antes:inicio]),
            'Súmula': _extrai_sumula(fatia),
            'Problema da Consulta': problema,
            'CNAE Detectado': _extrai_cnae(problema),
            'Resposta': _resposta_com_paragrafos(_extrai_resposta(fatia), fatias_p.get((numero, data_iso))),
        })
    return registros
