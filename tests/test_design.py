# tests/test_design.py
import base64
import os
import tomllib
from urllib.parse import unquote

import pytest

from interface import design
from interface.icones import ICONES

CONFIG = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "config.toml")


def test_todo_token_tem_valor_claro_e_escuro():
    assert all(len(valores) == 2 and all(valores) for valores in design.TOKENS.values())


def test_variaveis_css_usam_os_valores_do_tema():
    claro, escuro = design.variaveis_css("light"), design.variaveis_css("dark")
    assert "--bg: #F1F1F1;" in claro and "--bg: #161617;" in escuro
    assert "--primary-ink: #1C62CB;" in claro and "--primary-ink: #7FAAF0;" in escuro
    assert claro.startswith(":root {") and claro.endswith("}")


def test_tema_ativo_cai_em_claro_quando_a_api_falha(monkeypatch):
    class Quebrado:
        @property
        def theme(self):
            raise RuntimeError("sem contexto")

    monkeypatch.setattr(design.st, "context", Quebrado())
    assert design.tema_ativo() == "light"


@pytest.mark.parametrize("tipo, esperado", [("dark", "dark"), ("light", "light"), (None, "light")])
def test_tema_ativo_segue_o_tipo_do_streamlit(monkeypatch, tipo, esperado):
    class Ctx:
        class theme:  # noqa: N801
            type = tipo

    monkeypatch.setattr(design.st, "context", Ctx())
    assert design.tema_ativo() == esperado


def test_config_toml_esta_em_sincronia_com_os_tokens():
    with open(CONFIG, "rb") as fh:
        tema = tomllib.load(fh)["theme"]
    pares = {"primaryColor": "primary", "backgroundColor": "bg", "secondaryBackgroundColor": "surface",
             "textColor": "text", "borderColor": "border", "redColor": "error", "redBackgroundColor": "error-light",
             "redTextColor": "error-ink", "greenColor": "success", "greenBackgroundColor": "success-light",
             "greenTextColor": "success-ink", "yellowColor": "warning", "yellowBackgroundColor": "warning-light",
             "yellowTextColor": "warning-ink", "blueBackgroundColor": "primary-light", "blueTextColor": "primary-ink"}
    for i, nome_do_tema in enumerate(("light", "dark")):
        for chave_toml, token in pares.items():
            assert tema[nome_do_tema][chave_toml].upper() == design.TOKENS[token][i].upper(), \
                f"{nome_do_tema}.{chave_toml} difere do token {token}"


def test_marca_leva_os_dois_logos_e_o_css_escolhe_pelo_tema():
    # a troca de tema pode acontecer ao vivo, então os dois logos vão no HTML
    saida = design.html_marca("Mapeador")
    assert saida.count("data:image/png;base64,") == 2
    assert 'class="ds-logo-l"' in saida and 'class="ds-logo-d"' in saida
    assert "Martinelli Advogados" in saida and "Mapeador" in saida
    claro, escuro = design.css("light"), design.css("dark")
    assert ':root[data-ds-tema="dark"] .ds-logo-d { display: block; }' in claro
    assert ".ds-logo-l { display: none; } .ds-logo-d { display: block; }" in escuro  # valor inicial no escuro
    assert ".ds-logo-l { display: none; } .ds-logo-d { display: block; }" not in claro


def test_css_amarra_os_dois_temas_ao_atributo_do_html():
    css = design.css("light")
    assert ':root[data-ds-tema="dark"] {' in css and ':root[data-ds-tema="light"] {' in css
    # o atributo vem depois do :root padrão e tem mais especificidade: ganha
    assert css.index(":root {") < css.index(':root[data-ds-tema="dark"]')
    assert "--bg: #161617;" in css.split(':root[data-ds-tema="dark"]')[1]


def test_css_nao_redefine_o_fundo_do_app():
    # o script de tema decide claro/escuro lendo a cor de fundo NATIVA de .stApp;
    # se o CSS a sobrescrevesse com var(--bg), o tema ficaria preso no valor inicial
    css = design.css("light")
    assert ".stApp {" not in css and ".stApp{" not in css
    assert 'data-testid="stSidebar"] {' not in css


def test_script_de_tema_le_o_fundo_nativo_e_marca_o_html():
    js = design._JS_TEMA
    assert "data-ds-tema" in js and "getComputedStyle(app).backgroundColor" in js
    assert "window.__dsTema" in js            # instala uma vez só
    assert "<script>" in js and "</script>" in js
    assert "${" not in js                      # texto fixo: nada interpolado


def test_cabecalho_escapa_o_texto_vindo_de_fora():
    saida = design.html_cabecalho("<b>rótulo</b>", "Título & cia", '"sub"')
    assert "<b>" not in saida and "&lt;b&gt;" in saida
    assert "Título &amp; cia" in saida and "&quot;sub&quot;" in saida
    assert "\n" not in saida  # uma linha só: linha em branco encerra o bloco no Markdown


def test_cabecalho_de_login_tem_os_dois_logos_e_escapa_o_texto():
    saida = design.html_login_cabecalho("Acesso", "<Título>", "sub & cia")
    assert saida.count("data:image/png;base64,") == 2
    assert 'class="ds-logo-l"' in saida and 'class="ds-logo-d"' in saida
    assert "&lt;Título&gt;" in saida and "sub &amp; cia" in saida
    assert "\n" not in saida


def test_css_centraliza_o_cartao_de_login():
    css = design.css("light")
    assert ".stMainBlockContainer:has(.st-key-card-login)" in css
    assert ".st-key-card-login { max-width: 440px;" in css
    # o bloco interno do Streamlit cresce (flex-grow: 1); é ele que precisa centralizar o cartão
    assert 'stMainBlockContainer:has(.st-key-card-login) > [data-testid="stVerticalBlock"]' in css


def test_cabecalho_sem_subtitulo_nao_gera_paragrafo():
    assert "<p>" not in design.html_cabecalho("a", "b")


def test_estado_vazio_e_titulo_de_cartao_escapam():
    assert "&lt;x&gt;" in design.html_vazio("search", "<x>", "texto")
    assert "&lt;y&gt;" in design.html_titulo_cartao("<y>", "sub")


def test_perfil_gera_iniciais():
    assert "AD</div>" in design.html_perfil("Administrador", "Perfil atual")
    assert "JS</div>" in design.html_perfil("João Santos", "x")


def test_icone_uri_e_um_svg_valido_com_a_cor_pedida():
    uri = design.icone_uri("search", "#112233")
    assert uri.startswith("data:image/svg+xml,")
    svg = unquote(uri.split(",", 1)[1])
    assert svg.startswith("<svg") and 'stroke="#112233"' in svg and ICONES["search"] in svg


def test_css_inclui_variaveis_e_uma_regra_de_icone_por_indicador():
    css = design.css("dark")
    assert css.startswith("<style>") and css.endswith("</style>")
    assert "--surface: #232324;" in css
    for chave in design.KPIS:
        assert f'st-key-{chave}"]' in css


def test_logos_existem_e_sao_png():
    for caminho in design._LOGOS.values():
        with open(caminho, "rb") as fh:
            assert fh.read(8) == b"\x89PNG\r\n\x1a\n"


def test_icones_em_base64_decodificam():
    # o data URI do logo é base64 válido
    uri = design._logo_uri("light")
    assert base64.b64decode(uri.split(",", 1)[1])[:4] == b"\x89PNG"
