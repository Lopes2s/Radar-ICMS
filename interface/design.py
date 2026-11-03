# interface/design.py
"""Design System Martinelli aplicado ao Streamlit.

Fonte: showcase-design-martinelli.html. O tema nativo (cores, fonte, raios,
cores semânticas dos alertas) fica em .streamlit/config.toml, nos blocos
[theme.light] e [theme.dark]. Aqui entra só o que o config.toml não cobre:
as variáveis de cor do tema ativo, o CSS dos componentes (cartões, indicadores,
botões, campos, abas, alertas) e pequenos blocos de HTML (marca, cabeçalho de
página, estado vazio, perfil).

Regras do showcase seguidas aqui:
- toda cor vem de variável (nada de cor fixa no CSS novo);
- azul é a ação principal; verde é concluído, âmbar é espera/aviso e vermelho é
  erro — nunca só enfeite;
- todo botão e campo mostra anel de foco azul ao navegar pelo teclado;
- logo escuro em fundo claro e logo branco em fundo escuro, sem alterar
  proporção nem cores;
- todo texto vindo de dados passa por html.escape antes de entrar no HTML.
"""
import base64
import functools
import html
import os
from urllib.parse import quote

import streamlit as st

from interface.icones import ICONES

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGOS = {
    "light": os.path.join(_RAIZ, "assets", "martinelli_logo_escuro.png"),
    "dark": os.path.join(_RAIZ, "assets", "martinelli_logo_branco.png"),
}

# Tokens do showcase: nome -> (claro, escuro). Os mesmos valores estão em
# .streamlit/config.toml (o CSS injetado não lê o config.toml).
TOKENS = {
    "primary": ("#1C62CB", "#1C62CB"),
    "primary-hover": ("#154A9F", "#3F7BDB"),
    "primary-light": ("#E8EFF9", "#1F3050"),
    "primary-ink": ("#1C62CB", "#7FAAF0"),
    "success": ("#3D7A30", "#4E9A3F"),
    "success-light": ("#EEF5EC", "#1E2C1C"),
    "success-ink": ("#3D7A30", "#7FC46F"),
    "warning": ("#E6960A", "#E6960A"),
    "warning-light": ("#FDF5E6", "#3A2C10"),
    "warning-ink": ("#B87408", "#F0AC38"),
    "error": ("#C62828", "#D64545"),
    "error-light": ("#FCEAEA", "#3C1F1F"),
    "error-ink": ("#C62828", "#F27C7C"),
    "charcoal": ("#262626", "#565C69"),   # fundo de ícone neutro (no escuro, o cinza do showcase)
    "gray": ("#6B7280", "#6B7280"),
    "bg": ("#F1F1F1", "#161617"),
    "surface": ("#FFFFFF", "#232324"),
    "field": ("#F1F1F1", "#2C2C2E"),
    "border": ("#9CA3AF", "#5A5F69"),
    "border-light": ("#E8EAED", "#34363A"),
    "text": ("#262626", "#F1F1F1"),
    "text-2": ("#52575F", "#B9BEC6"),
    "text-3": ("#6B7280", "#8F95A0"),
    "text-dis": ("#B0B5BD", "#60656E"),
    "shadow-card": ("0 1px 2px rgba(0,0,0,.05)", "0 1px 2px rgba(0,0,0,.4)"),
    "shadow-xl": ("0 16px 48px rgba(0,0,0,.12)", "0 16px 48px rgba(0,0,0,.5)"),
    "focus": ("0 0 0 3px #E8EFF9", "0 0 0 3px #1F3050"),
}

# Indicadores (st.metric dentro de st.container(key=...)): prefixo da chave -> (ícone, cor).
# O Streamlit não aceita a mesma key duas vezes na página, então cada tela usa
# um sufixo ("-base", "-analise", "-resumo") e o CSS casa pelo prefixo.
KPIS = {
    "kpi-consultas": ("file", "var(--primary)"),
    "kpi-regimes": ("building", "var(--charcoal)"),
    "kpi-anos": ("calendar", "var(--gray)"),
    "kpi-importacao": ("clock", "var(--gray)"),
    "kpi-descartes": ("alert", "var(--gray)"),
    "kpi-descartes-alerta": ("alert", "var(--error)"),
}


def tema_ativo() -> str:
    """'dark' ou 'light', conforme o tema que o Streamlit está usando agora
    (config.toml, menu de configurações ou preferência do sistema). Sem a
    informação (ex.: execução em teste), 'light'."""
    try:
        tipo = st.context.theme.type
    except Exception:  # noqa: BLE001 — a API varia por versão/contexto
        tipo = None
    return "dark" if tipo == "dark" else "light"


def variaveis_css(tema: str) -> str:
    """Bloco :root com os tokens do tema."""
    i = 1 if tema == "dark" else 0
    linhas = "".join(f"--{nome}: {valores[i]};" for nome, valores in TOKENS.items())
    return f":root {{{linhas}}}"


def icone_uri(nome: str, cor: str = "#FFFFFF", traco: float = 2) -> str:
    """Ícone do showcase como data URI (SVG com traço na cor dada). Serve para
    <img> e para CSS (mask/background), onde currentColor não funciona."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{cor}" stroke-width="{traco}" stroke-linecap="round" '
        f'stroke-linejoin="round">{ICONES[nome]}</svg>'
    )
    return "data:image/svg+xml," + quote(svg, safe="")


@functools.lru_cache(maxsize=None)
def _logo_uri(tema: str) -> str:
    with open(_LOGOS[tema], "rb") as fh:
        return "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")


def _css_kpis() -> str:
    regras = []
    for chave, (icone, cor) in KPIS.items():
        regras.append(
            f'div[class*="st-key-{chave}"] [data-testid="stMetric"]::after {{'
            'content: ""; position: absolute; top: 16px; right: 18px;'
            'width: 34px; height: 34px; border-radius: 10px;'
            f'background: {cor} url("{icone_uri(icone)}") center / 17px no-repeat;}}'
        )
    regras.append(
        'div[class*="st-key-kpi-descartes-alerta"] [data-testid="stMetricValue"] '
        '{ color: var(--error-ink); }'
    )
    return "\n".join(regras)


_CSS_COMPONENTES = """
/* ---------- base ---------- */
.stApp { background: var(--bg); color: var(--text); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1280px; padding: 2rem 2rem 4rem; }
hr { border-color: var(--border-light) !important; }
a { color: var(--primary-ink); }
:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }

/* ---------- barra lateral ---------- */
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
.ds-side-head { padding: 2px 2px 14px; border-bottom: 1px solid var(--border-light); margin-bottom: 14px; }
.ds-side-head img { height: 22px; width: auto; display: block; margin-bottom: 12px; }
.ds-side-label { font-size: 11px !important; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--text-3); margin: 0 !important; }
.ds-who { display: flex; align-items: center; gap: 10px; padding: 14px 2px 10px; border-top: 1px solid var(--border-light); margin-top: 18px; }
.ds-avatar { width: 34px; height: 34px; border-radius: 12px; background: var(--primary); color: #fff; font-weight: 700; font-size: 12px; display: grid; place-items: center; flex: none; }
.ds-who b { display: block; font-size: 13px; font-weight: 700; line-height: 1.3; }
.ds-who span { font-size: 11px; color: var(--text-3); }
.ds-sec { font-size: 11px !important; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--text-3); margin: 10px 0 8px !important; }

/* ---------- cabeçalho de página ---------- */
.ds-page-head { margin: 2px 0 20px; }
.ds-overline { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--text-3); }
.ds-page-head h1 { font-size: 26px !important; font-weight: 800 !important; letter-spacing: -.02em; line-height: 1.15 !important; margin: 4px 0 4px !important; padding: 0 !important; color: var(--text); }
.ds-page-head p { color: var(--text-2); margin: 0; }

/* ---------- abas ---------- */
[data-baseweb="tab-list"] { gap: 4px; }
button[data-baseweb="tab"] { font-weight: 600; color: var(--text-2); padding: 10px 16px; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--primary-ink); }
[data-baseweb="tab-highlight"] { background-color: var(--primary) !important; height: 3px !important; }
[data-baseweb="tab-border"] { background-color: var(--border-light) !important; }

/* ---------- cartões ---------- */
div[class*="st-key-card-"], .st-key-painel-busca, .st-key-perfil-consulta, .st-key-perfil-admin {
  background: var(--surface); border: 1px solid var(--border) !important; border-radius: 12px !important;
  box-shadow: var(--shadow-card); padding: 20px 22px;
}
.ds-card-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
.ds-card-head h2 { font-size: 16px; font-weight: 700; letter-spacing: -.01em; margin: 0; padding: 0; }
.ds-card-head .sub { font-size: 12px; color: var(--text-3); }
.ds-ico { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; margin-bottom: 10px; }
.ds-ico img { width: 20px; height: 20px; }
.bg-primary { background: var(--primary); } .bg-charcoal { background: var(--charcoal); }

/* ---------- indicadores (st.metric) ---------- */
[data-testid="stMetric"] { position: relative; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; box-shadow: var(--shadow-card); }
[data-testid="stMetricLabel"] { padding-right: 46px; min-height: 36px; }
[data-testid="stMetricLabel"] p { font-size: 12.5px; font-weight: 500; color: var(--text-2); }
[data-testid="stMetricValue"] { font-weight: 800; letter-spacing: -.02em; line-height: 1.1; }

/* ---------- botões ---------- */
[data-testid^="stBaseButton-"] { border-radius: 10px; font-weight: 600; border-width: 1.5px; transition: background .15s, border-color .15s; }
[data-testid="stBaseButton-primary"] { background: var(--primary); border-color: var(--primary); color: #fff; }
[data-testid="stBaseButton-primary"]:hover:not(:disabled) { background: var(--primary-hover); border-color: var(--primary-hover); color: #fff; }
[data-testid="stBaseButton-secondary"] { background: transparent; border: 1.5px solid var(--border); color: var(--text); }
[data-testid="stBaseButton-secondary"]:hover:not(:disabled) { background: var(--field); border-color: var(--border); color: var(--text); }
[data-testid^="stBaseButton-"]:disabled { opacity: .5; cursor: not-allowed; }
[data-testid^="stBaseButton-"]:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(28, 98, 203, .35); }

/* ---------- campos ---------- */
[data-testid="stWidgetLabel"] p { font-size: 12.5px; font-weight: 600; color: var(--text); }
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
  border: 1.5px solid var(--border) !important; border-radius: 10px !important; background: var(--surface) !important;
}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color: var(--primary) !important; box-shadow: var(--focus);
}
[data-testid="stFileUploaderDropzone"] { border: 2px dashed var(--border); border-radius: 12px; background: var(--surface); }

/* ---------- alertas (azul informa, verde conclui, âmbar avisa, vermelho erra) ---------- */
[data-testid="stAlert"] { background: var(--surface) !important; border: 1.5px solid var(--border); border-left-width: 4px; border-radius: 8px; color: var(--text); }
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) { border-left-color: var(--primary); }
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) { border-left-color: var(--success); }
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) { border-left-color: var(--warning); }
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) { border-left-color: var(--error); }

/* ---------- expansores, diálogos e estado vazio ---------- */
[data-testid="stExpander"] details { border: 1px solid var(--border); border-radius: 12px; background: var(--surface); }
div[role="dialog"] { background: var(--surface) !important; border-radius: 16px; box-shadow: var(--shadow-xl); }
div[role="dialog"] h3 { font-size: 1.2rem !important; line-height: 1.3 !important; }
.ds-empty { border: 2px dashed var(--border); border-radius: 12px; padding: 34px 24px; text-align: center; margin: 6px 0 4px; }
.ds-empty .ei { width: 52px; height: 52px; border-radius: 16px; background: var(--field); display: grid; place-items: center; margin: 0 auto 12px; }
.ds-empty .ei img { width: 24px; height: 24px; }
.ds-empty h3 { font-size: 15px; font-weight: 700; margin: 0 0 4px; padding: 0; }
.ds-empty p { color: var(--text-3); font-size: 12.5px; max-width: 46ch; margin: 0 auto; }

/* ---------- detalhe do ato e resposta ---------- */
.icms-campo-detalhe-rotulo { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--text-3); margin-top: 14px; padding-top: 8px; border-top: 1px solid var(--border-light); }
.icms-resposta-paragrafo { margin: 0 0 .9em 0; line-height: 1.55; text-align: justify; }
"""


def css(tema: str | None = None) -> str:
    tema = tema or tema_ativo()
    return f"<style>{variaveis_css(tema)}{_CSS_COMPONENTES}{_css_kpis()}</style>"


def injetar_tema() -> str:
    """Injeta variáveis e CSS na página e devolve o tema ativo."""
    tema = tema_ativo()
    st.markdown(css(tema), unsafe_allow_html=True)
    return tema


# ---------- blocos de HTML (uma linha só: linha em branco encerra o bloco no Markdown) ----------

def html_marca(rotulo: str, tema: str) -> str:
    """Logo Martinelli (escuro no tema claro, branco no escuro) e o nome do app."""
    return (
        '<div class="ds-side-head">'
        f'<img src="{_logo_uri(tema)}" alt="Martinelli Advogados">'
        f'<p class="ds-side-label">{html.escape(rotulo)}</p></div>'
    )


def html_cabecalho(rotulo: str, titulo: str, subtitulo: str = "") -> str:
    sub = f"<p>{html.escape(subtitulo)}</p>" if subtitulo else ""
    return (
        '<div class="ds-page-head">'
        f'<div class="ds-overline">{html.escape(rotulo)}</div>'
        f"<h1>{html.escape(titulo)}</h1>{sub}</div>"
    )


def html_titulo_cartao(titulo: str, sub: str = "") -> str:
    complemento = f'<span class="sub">{html.escape(sub)}</span>' if sub else ""
    return (
        '<div class="ds-card-head">'
        f"<h2>{html.escape(titulo)}</h2>{complemento}</div>"
    )


def html_vazio(icone: str, titulo: str, texto: str) -> str:
    cinza = icone_uri(icone, "#8F95A0" if tema_ativo() == "dark" else "#B0B5BD")
    return (
        '<div class="ds-empty">'
        f'<div class="ei"><img src="{cinza}" alt=""></div>'
        f"<h3>{html.escape(titulo)}</h3><p>{html.escape(texto)}</p></div>"
    )


def html_icone_cartao(icone: str, fundo: str) -> str:
    """Quadrado de ícone (fundo: 'primary' ou 'charcoal') que abre um cartão."""
    return (
        f'<div class="ds-ico bg-{fundo}">'
        f'<img src="{icone_uri(icone)}" alt=""></div>'
    )


def html_perfil(nome: str, papel: str) -> str:
    palavras = nome.split()
    if len(palavras) > 1:
        iniciais = (palavras[0][0] + palavras[1][0]).upper()
    else:
        iniciais = nome[:2].upper() or "?"
    return (
        '<div class="ds-who">'
        f'<div class="ds-avatar" aria-hidden="true">{html.escape(iniciais)}</div>'
        f"<div><b>{html.escape(nome)}</b><span>{html.escape(papel)}</span></div></div>"
    )


# ---------- atalhos que já escrevem na página ----------

def marca_lateral(rotulo: str, tema: str) -> None:
    st.markdown(html_marca(rotulo, tema), unsafe_allow_html=True)


def cabecalho_pagina(rotulo: str, titulo: str, subtitulo: str = "") -> None:
    st.markdown(html_cabecalho(rotulo, titulo, subtitulo), unsafe_allow_html=True)


def titulo_cartao(titulo: str, sub: str = "") -> None:
    st.markdown(html_titulo_cartao(titulo, sub), unsafe_allow_html=True)


def estado_vazio(icone: str, titulo: str, texto: str) -> None:
    st.markdown(html_vazio(icone, titulo, texto), unsafe_allow_html=True)


def icone_cartao(icone: str, fundo: str) -> None:
    st.markdown(html_icone_cartao(icone, fundo), unsafe_allow_html=True)


def perfil_lateral(nome: str, papel: str) -> None:
    st.markdown(html_perfil(nome, papel), unsafe_allow_html=True)


def secao_lateral(texto: str) -> None:
    st.markdown(f'<p class="ds-sec">{html.escape(texto)}</p>', unsafe_allow_html=True)
