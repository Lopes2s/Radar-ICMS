# parsers/regimes.py
import re

_EDICAO = re.compile(
    r'(\d{1,2}/\w{3}/\d{4})\s*[-–]\s*EDI[ÇC][ÃA]O\s*N[°º]?\s*([\d\.]+)',
    re.IGNORECASE,
)

# Mesmo padrão de _EDICAO, mas com o nº de página e o dia da semana à
# esquerda (ex.: "32 6ª FEIRA |14/AGO/2026 - EDIÇÃO N° 12.196"), para
# remover a repetição inteira do corpo — _EDICAO sozinho só localiza a data/
# edição, não o cabeçalho de página completo.
_CABECALHO_DE_PAGINA = re.compile(
    r'\d{1,3}\s*\d[ªa]\s*FEIRA\s*\|\s*\d{1,2}/\w{3}/\d{4}\s*[-–]\s*'
    r'EDI[ÇC][ÃA]O\s*N[°º]?\s*[\d\.]+',
    re.IGNORECASE,
)

# âncora robusta: número do RE precedido do cabeçalho do bloco.
# Isso distingue o TÍTULO da matéria de citações do mesmo número no corpo.
# O departamento que assina varia por regime: "COORDENAÇÃO DE FISCALIZAÇÃO"
# (Krona, Agroantunes) ou "INSPETORIA GERAL DE FISCALIZAÇÃO" (Jaguafrangos,
# Jandrei) — sem aceitar os dois, regimes dessa segunda vira "titulo_sem_
# ancora" em vez de registro (confirmado no Regime Especial nº 8.715/2025).
_ANCORA_RE = re.compile(
    r'(?:COORDENA[ÇC][ÃA]O|INSPETORIA\s+GERAL)\s+DE\s+FISCALIZA[ÇC][ÃA]O\s*\n\s*'
    r'REGIME\s+ESPECIAL\s+N[ºo°]\s*([\d\.]+)\s*/\s*(\d{4})',
    re.IGNORECASE,
)

# Qualquer título de matéria em caixa alta, com ou sem o cabeçalho acima.
# Citações no corpo ("Regime Especial nº 6.247/2019") são caixa mista e,
# por ser case-sensitive, este regex não as pega.
_TITULO_RE = re.compile(r'REGIME\s+ESPECIAL\s+N[ºo°]\s*([\d\.]+)\s*/\s*(\d{4})')

_MESES_ABREV = {
    'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04', 'MAI': '05', 'JUN': '06',
    'JUL': '07', 'AGO': '08', 'SET': '09', 'OUT': '10', 'NOV': '11', 'DEZ': '12',
}


def _data_edicao_iso(txt: str) -> str:
    m = re.match(r'(\d{1,2})/(\w{3})/(\d{4})', txt)
    if not m:
        return txt
    d, mes, a = m.groups()
    mes_num = _MESES_ABREV.get(mes.upper())
    if not mes_num:
        return txt  # mês não reconhecido: melhor o texto original que "2026-00-14"
    return f"{a}-{mes_num}-{d.zfill(2)}"


def _campo(fatia: str, rotulo: str) -> str:
    m = re.search(rf'{rotulo}:\s*(.+)', fatia, re.IGNORECASE)
    return m.group(1).strip() if m else ""


# O nome da beneficiária pode quebrar em várias linhas; termina no próximo
# rótulo do bloco, até 200 caracteres (nome de empresa não passa disso; sem o
# teto, um rótulo distante puxaria parágrafos inteiros). Sem rótulo dentro
# desse alcance, cai no comportamento de uma linha.
_BENEFICIARIA = re.compile(
    r'BENEFICI[ÁA]RIA:\s*(.{1,200}?)\s*(?=CAD/ICMS:|CNPJ:|ENDERE[ÇC]O:|EMENTA:)',
    re.IGNORECASE | re.DOTALL,
)


def _beneficiaria(fatia: str) -> str:
    m = _BENEFICIARIA.search(fatia)
    nome = re.sub(r'\s+', ' ', m.group(1)) if m else _campo(fatia, 'BENEFICI[ÁA]RIA')
    return nome.strip().rstrip('.')


def _cnpj(fatia: str) -> str:
    m = re.search(r'CNPJ:\s*([\d\.\/-]+)', fatia, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _cad_icms(fatia: str) -> str:
    m = re.search(r'CAD/ICMS:\s*([\d\.\-]+)', fatia, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _ementa(fatia: str) -> str:
    m = re.search(
        r'EMENTA:\s*(.+?)(?:Diante do previsto|A Diretora|O Diretor|'
        r'\n\s*1\.\s|\n\s*\d+\.\s*O\s|\Z)',
        fatia, re.DOTALL | re.IGNORECASE,
    )
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ""


def _vigencia(fatia: str) -> str:
    m = re.search(r'efic[áa]cia\s+se\s+encerra\s+em\s+([\d/]+)', fatia, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'prazo final.*?alterado para\s+(.+?)\.', fatia, re.IGNORECASE)
    if m:
        return re.sub(r'\s+', ' ', m.group(1)).strip()
    return ""


def _classifica(fatia: str) -> str:
    tem_beneficiaria = re.search(r'BENEFICI[ÁA]RIA:', fatia, re.IGNORECASE)
    tem_ementa = re.search(r'EMENTA:', fatia, re.IGNORECASE)
    eh_revogacao = re.search(r'DESPACHO\s+N[ºo°].*?Revog', fatia,
                             re.IGNORECASE | re.DOTALL)
    if eh_revogacao and not tem_beneficiaria:
        return 'revogacao'
    if tem_beneficiaria and tem_ementa:
        return 'concessao_ou_alteracao'
    return 'descartar'


# Título de uma seção numerada de nível 1 do Regime Especial (ex.: "1. DA
# ABRANGÊNCIA", "2. DOS PROCEDIMENTOS ESPECIAIS", "4. DAS DISPOSIÇÕES
# GERAIS"). "(?!\d)" logo após o número distingue o título (nível 1) de um
# subitem como "2.1." ou "2.1.1." — sem isso, o subitem seria confundido
# com o início da seção seguinte e cortaria o campo anterior cedo demais.
_SECAO_NIVEL_1 = re.compile(r'\n\s*\d+\.(?!\d)\s*D[AO]S?\s+[A-ZÀ-Ü]')

_ABRANGENCIA_INICIO = re.compile(r'\d+\.(?!\d)\s*DA\s+ABRANG[ÊE]NCIA\s*\n')

# O rótulo real varia entre regimes: "DAS DISPOSIÇÕES GERAIS" isolado
# (Agroantunes) ou com complemento na mesma linha, "DAS DISPOSIÇÕES GERAIS,
# VIGÊNCIA E EXTINÇÃO" (Jaguafrangos). "[^\n]*" absorve esse complemento
# variável antes do conteúdo da seção começar na linha seguinte.
_DISPOSICOES_GERAIS_INICIO = re.compile(
    r'\d+\.(?!\d)\s*DAS\s+DISPOSI[ÇC][ÕO]ES\s+GERAIS[^\n]*\n'
)

# Bloco de assinatura que fecha o Regime Especial (variantes observadas: "O
# Secretário [de Estado da Fazenda]", "A Diretora [da Receita Estadual]", "O
# Diretor[-Adjunto]"). Sem esse limite, Disposições Gerais — normalmente a
# última seção antes da assinatura — vazaria para dentro da assinatura e do
# protocolo do item seguinte, quando a fatia não termina logo ali.
_FIM_DE_SECAO = re.compile(r'\n\s*(?:O\s+Secret[áa]rio|A\s+Diretora|O\s+Diretor)')


def _fim_do_bloco(resto: str) -> int:
    candidatos = [m.start() for m in
                  (_SECAO_NIVEL_1.search(resto), _FIM_DE_SECAO.search(resto))
                  if m]
    return min(candidatos) if candidatos else len(resto)


def _extrai_abrangencia(fatia: str) -> str:
    m_inicio = _ABRANGENCIA_INICIO.search(fatia)
    if not m_inicio:
        return ""
    resto = fatia[m_inicio.end():]
    return re.sub(r'\s+', ' ', resto[:_fim_do_bloco(resto)]).strip()


def _extrai_disposicoes_gerais(fatia: str) -> str:
    m_inicio = _DISPOSICOES_GERAIS_INICIO.search(fatia)
    if not m_inicio:
        return ""
    resto = fatia[m_inicio.end():]
    return re.sub(r'\s+', ' ', resto[:_fim_do_bloco(resto)]).strip()


def _extrai_beneficios_procedimentos(fatia: str) -> str:
    """"Miolo" numerado do Regime Especial: tudo entre o fim da seção de
    Abrangência e o início da seção de Disposições Gerais, não importa
    quantas seções existam no meio nem seus títulos — que variam muito
    entre tipos de regime (ex.: "DOS PROCEDIMENTOS ESPECIAIS" num, "DAS
    OPERAÇÕES DE AQUISIÇÃO..." + "DAS OPERAÇÕES DE SAÍDAS..." noutro), sem
    nenhum rótulo estável em comum além de "BENEFÍCIOS" ou "PROCEDIMENTOS"
    não aparecerem sempre. Sem as duas âncoras (Abrangência e Disposições
    Gerais), o campo fica vazio em vez de arriscar um recorte errado.
    """
    m_abrangencia = _ABRANGENCIA_INICIO.search(fatia)
    m_disposicoes = _DISPOSICOES_GERAIS_INICIO.search(fatia)
    if not m_abrangencia or not m_disposicoes:
        return ""
    m_fim_abrangencia = _SECAO_NIVEL_1.search(fatia[m_abrangencia.end():])
    if not m_fim_abrangencia:
        return ""
    inicio = m_abrangencia.end() + m_fim_abrangencia.start()
    fim = m_disposicoes.start()
    if fim <= inicio:
        return ""
    return re.sub(r'\s+', ' ', fatia[inicio:fim]).strip()


def _pr_competitivo(ementa: str) -> str:
    if re.search(r'paran[áa]\s+competitivo|protocolo de inten', ementa, re.IGNORECASE):
        return 'Sim'
    return 'Não'


def parse(texto: str):
    """Retorna (registros, descartes)."""
    ed = _EDICAO.search(texto)
    data_ed = _data_edicao_iso(ed.group(1)) if ed else ""
    n_doe = ed.group(2) if ed else ""

    # o cabeçalho de página (nº da página + dia da semana + data + edição,
    # ex.: "26 3ª feira | 06/Jan/2026 - Edição nº 12048") se repete a cada
    # página do Diário Oficial. _EDICAO acima já pegou a primeira ocorrência
    # para DATA/Nº DOE; as demais precisam sumir do corpo, senão sobram no
    # meio de uma seção sempre que a quebra de página cai dentro dela (caso
    # real: "DOS PROCEDIMENTOS ESPECIAIS" do Regime Especial nº 8.715/2025).
    texto = _CABECALHO_DE_PAGINA.sub('\n', texto)

    ancoras = list(_ANCORA_RE.finditer(texto))
    registros, descartes = [], []

    for i, anc in enumerate(ancoras):
        inicio = anc.start()
        fim = ancoras[i + 1].start() if i + 1 < len(ancoras) else len(texto)
        fatia = texto[inicio:fim]
        tipo = _classifica(fatia)
        num_re = f"{anc.group(1)}/{anc.group(2)}"

        if tipo != 'concessao_ou_alteracao':
            benef = _beneficiaria(fatia) or _campo(fatia, 'INTERESSADO')
            descartes.append({'Nº RE': num_re, 'Motivo': tipo, 'Empresa': benef[:60]})
            continue

        ementa = _ementa(fatia)
        registros.append({
            'ANO': anc.group(2),
            'DATA': data_ed,
            'Nº DOE': n_doe,
            'RE PR COMPETITIVO': _pr_competitivo(ementa),
            'Nº DO REGIME ESPECIAL': num_re,
            'EMPRESA': _beneficiaria(fatia),
            'CNPJ REQUERENTE': _cnpj(fatia),
            'CAD/ICMS': _cad_icms(fatia),
            'CNAE REQUERENTE': '',
            'DESCRIÇÃO CNAE': '',
            'VIGÊNCIA DO RE': _vigencia(fatia),
            'EMENTA': ementa,
            'ABRANGÊNCIA': _extrai_abrangencia(fatia),
            'BENEFÍCIOS/PROCEDIMENTOS': _extrai_beneficios_procedimentos(fatia),
            'DISPOSIÇÕES GERAIS': _extrai_disposicoes_gerais(fatia),
        })

    descartes.extend(_titulos_sem_ancora(texto, ancoras))
    return registros, descartes


def _titulos_sem_ancora(texto: str, ancoras: list) -> list[dict]:
    """Títulos de regime fora de qualquer âncora casada, como descartes."""
    faixas = [(a.start(), a.end()) for a in ancoras]
    perdidos = []
    for m in _TITULO_RE.finditer(texto):
        if not any(ini <= m.start() < fim for ini, fim in faixas):
            perdidos.append({'Nº RE': f"{m.group(1)}/{m.group(2)}",
                             'Motivo': 'titulo_sem_ancora', 'Empresa': ''})
    return perdidos
