# tests/test_app.py
"""Fumaça da interface. O AppTest do Streamlit não simula upload de arquivo,
então o fluxo com PDFs é verificado manualmente (ver plano, Tarefa 11); aqui
garantimos que a página abre sem erro e mostra o resultado guardado."""
import io
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402
from core import acesso, armazenamento  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")


@pytest.fixture(autouse=True)
def _isola_banco(monkeypatch, tmp_path):
    """Todo teste deste arquivo usa um banco isolado em tmp_path.

    AppTest.run() executa app.py inteiro, inclusive o bloco
    `with aba_consultar:` — Streamlit roda o script todo a cada rerun,
    independentemente de qual aba está selecionada visualmente. Sem esta
    fixture, um teste que não define MAPEADOR_BANCO cai no caminho padrão
    de armazenamento.conectar() e escreve no mapeamento.db real do
    projeto (achado na revisão final do branch: rodar a suíte criava/
    alterava esse arquivo fora de qualquer sandbox de teste).
    """
    monkeypatch.setenv("MAPEADOR_BANCO", str(tmp_path / "app_teste.db"))


def _app(perfil="admin"):
    """AppTest já 'logado'. O portão de perfil é testado nos testes próprios
    mais abaixo; os demais testes só precisam do app aberto."""
    at = AppTest.from_file(APP)
    if perfil:
        at.session_state["perfil"] = perfil
    return at


def test_isolamento_nunca_usa_o_banco_real_do_projeto():
    banco_do_teste = os.environ.get("MAPEADOR_BANCO")
    assert banco_do_teste is not None
    assert os.path.abspath(banco_do_teste) != os.path.abspath(armazenamento._CAMINHO_PADRAO)


def test_pagina_abre_sem_erro_e_pede_pdfs():
    at = _app().run(timeout=30)
    assert not at.exception
    assert any("Envie um ou mais PDFs" in i.value for i in at.info)


def test_resultado_guardado_sobrevive_a_reexecucao():
    # simula o estado deixado por um processamento anterior: é isto que o
    # clique em "Baixar" (que reexecuta o script) precisa encontrar.
    at = _app()
    at.session_state["resultado"] = {
        "arquivos": [{'Arquivo': 'c.pdf', 'Tipo': 'consulta', 'Consultas': 1,
                      'Regimes': 0, 'Descartes': 0, 'Erro': ''}],
        "consultas": [{'Ano': '2026', 'Nº da Consulta': '001'}],
        "regimes": [], "descartes": [],
        "mapeamento": {"consultas": {"novos": 1, "atualizados": 0},
                      "regimes": {"novos": 0, "atualizados": 0}},
        "xlsx": io.BytesIO(b"conteudo").getvalue(),
    }
    at.run(timeout=30)
    assert not at.exception
    assert [m.value for m in at.metric][:1] == ["1"]


def test_aba_consultar_aparece():
    at = _app().run(timeout=30)
    assert not at.exception
    assert any("Consultar" in t.label for t in at.tabs)


def test_botao_de_exportar_so_aparece_com_resultados():
    at = _app().run(timeout=30)
    aba = at.tabs[1]
    assert not any("Baixar estes resultados" in b.label for b in aba.download_button)

    from core import armazenamento as arm
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS', 'Problema da Consulta': 'madeira',
         'CNAE Detectado': ''},
    ])

    at.tabs[1].selectbox[0].set_value("consulta").run(timeout=30)  # força rerun
    aba = at.tabs[1]
    botoes = [b for b in aba.download_button if "Baixar estes resultados" in b.label]
    assert len(botoes) == 1


# Regressão: o AppTest não simula clique/seleção de linha em st.dataframe (a
# classe Dataframe do harness de teste não expõe esse método, só .value).
# O jeito documentado de simular programaticamente é escrever direto na
# chave de sessão do widget, do mesmo jeito que o próprio Streamlit grava a
# seleção real do usuário — ver core.armazenamento.buscar_consultas e a
# chave "tabela-resultados" em app.py.

def test_selecionar_linha_abre_o_modal_de_detalhe(monkeypatch):
    from core import armazenamento as arm
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
         'Protocolo': '25.152.191-3', 'Súmula': 'ICMS. TESTE.',
         'Problema da Consulta': 'problema teste', 'CNAE Detectado': '',
         'Resposta': 'RESPOSTA_MARCADOR_UNICO'},
    ])

    at = _app().run(timeout=30)
    at.tabs[1].selectbox[0].set_value("consulta").run(timeout=30)
    assert not any("RESPOSTA_MARCADOR_UNICO" in m.value for m in at.markdown)

    # simula a seleção da 1ª linha, como o Streamlit faria ao clicar nela
    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}
    at.run(timeout=30)

    assert not at.exception
    assert any("Consulta nº 001/2026" in s.value for s in at.subheader)
    assert any("RESPOSTA_MARCADOR_UNICO" in m.value for m in at.markdown)


def test_fechar_modal_limpa_a_selecao_e_ele_nao_reabre_sozinho():
    # _fecha_selecao_da_tabela (o on_dismiss do modal) faz exatamente isto:
    # reatribui a chave de sessão com "rows" vazio. Não importamos a função
    # de app.py diretamente — os testes deste arquivo só rodam app.py através
    # do AppTest (exec isolado); um `import app` direto o executaria de novo
    # em modo bare, fora do sandbox do AppTest.
    from core import armazenamento as arm
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS. X.', 'Problema da Consulta': '',
         'CNAE Detectado': '', 'Resposta': ''},
    ])

    at = _app().run(timeout=30)
    at.tabs[1].selectbox[0].set_value("consulta").run(timeout=30)
    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}
    at.run(timeout=30)
    assert any("Consulta nº 001/2026" in s.value for s in at.subheader)

    at.session_state["tabela-resultados"] = {"selection": {"rows": []}}
    at.run(timeout=30)

    assert not at.exception
    assert not any("Consulta nº 001/2026" in s.value for s in at.subheader)


def test_selecionar_linha_de_regime_tambem_abre_o_modal_de_detalhe():
    # mesmo mecanismo do teste de consulta, mas para regime — confirma que
    # _titulo_do_registro() e a escolha de COLS_REGIMES em app.py funcionam
    # para o outro tipo, não só para consulta.
    from core import armazenamento as arm
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_regimes(conn, [
        {'ANO': '2025', 'DATA': '2025-08-14', 'Nº DOE': '12.196',
         'RE PR COMPETITIVO': 'Não', 'Nº DO REGIME ESPECIAL': '8.715/2025',
         'EMPRESA': 'JAGUAFRANGOS IND. E COM. DE ALIMENTOS LTDA',
         'CNPJ REQUERENTE': '85.090.033/0001-22', 'CAD/ICMS': '61700643-03',
         'CNAE REQUERENTE': '', 'DESCRIÇÃO CNAE': '', 'VIGÊNCIA DO RE': '',
         'EMENTA': 'Implementação de tratamentos tributários.',
         'ABRANGÊNCIA': 'ABRANGENCIA_MARCADOR_UNICO',
         'BENEFÍCIOS/PROCEDIMENTOS': 'PROCEDIMENTOS_MARCADOR_UNICO',
         'DISPOSIÇÕES GERAIS': 'DISPOSICOES_MARCADOR_UNICO'},
    ])

    at = _app().run(timeout=30)
    at.tabs[1].selectbox[0].set_value("regime").run(timeout=30)
    assert not any("ABRANGENCIA_MARCADOR_UNICO" in m.value for m in at.markdown)

    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}
    at.run(timeout=30)

    assert not at.exception
    assert any("Regime Especial nº 8.715/2025" in s.value for s in at.subheader)
    textos = [m.value for m in at.markdown]
    assert any("ABRANGENCIA_MARCADOR_UNICO" in t for t in textos)
    assert any("PROCEDIMENTOS_MARCADOR_UNICO" in t for t in textos)
    assert any("DISPOSICOES_MARCADOR_UNICO" in t for t in textos)
    # campos vazios (CNAE REQUERENTE, DESCRIÇÃO CNAE, VIGÊNCIA DO RE) não
    # devem aparecer como rótulo sem valor
    assert not any(">CNAE REQUERENTE<" in t for t in textos)


# Regressão/pedido: os campos numerados de regime (ABRANGÊNCIA, BENEFÍCIOS/
# PROCEDIMENTOS, DISPOSIÇÕES GERAIS) saem da extração como um parágrafo só
# (parsers/regimes.py colapsa a quebra de linha original de propósito, para
# caber numa célula de planilha) — no modal, cada tópico numerado ("2.1.1.",
# "3.7." etc.) deve reaparecer em linha própria, para ficar legível.

def test_topicos_numerados_do_regime_ganham_quebra_de_linha_no_modal():
    from core import armazenamento as arm
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_regimes(conn, [
        {'ANO': '2025', 'Nº DO REGIME ESPECIAL': '8.729/2025', 'DATA': '',
         'Nº DOE': '', 'RE PR COMPETITIVO': '', 'EMPRESA': '',
         'CNPJ REQUERENTE': '', 'CAD/ICMS': '', 'CNAE REQUERENTE': '',
         'DESCRIÇÃO CNAE': '', 'VIGÊNCIA DO RE': '', 'EMENTA': '',
         'ABRANGÊNCIA': '',
         'BENEFÍCIOS/PROCEDIMENTOS': (
             '2.1. Fica estabelecido forma e prazo de apuração. '
             '2.1.1. Em substituição à regra estabelecida no dispositivo. '
             '2.1.1.1. O recolhimento baseado no item anterior.'
         ),
         'DISPOSIÇÕES GERAIS': ''},
    ])

    at = _app().run(timeout=30)
    at.tabs[1].selectbox[0].set_value("regime").run(timeout=30)
    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}
    at.run(timeout=30)

    assert not at.exception
    campo = next(m.value for m in at.markdown if "2.1. Fica estabelecido" in m.value)
    assert "\n\n2.1.1. Em substituição" in campo
    assert "\n\n2.1.1.1. O recolhimento" in campo
    # o próprio 2.1. inicial não precisa de quebra antes (já é o começo do campo)
    assert campo.startswith("2.1. Fica estabelecido")


def test_resposta_do_modal_vira_um_p_por_paragrafo_com_texto_escapado():
    from core import armazenamento as arm
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS.', 'Problema da Consulta': 'p',
         'CNAE Detectado': '',
         'Resposta': 'a) primeiro item\n\n1. segundo <b>item</b> & $x$\n\n* terceiro'},
    ])
    at = _app().run(timeout=30)
    at.tabs[1].selectbox[0].set_value("consulta").run(timeout=30)
    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}
    at.run(timeout=30)
    assert not at.exception
    campo = next(m.value for m in at.markdown
                 if '<p class="icms-resposta-paragrafo">' in m.value)
    assert campo.count('<p class="icms-resposta-paragrafo">') == 3
    assert '<p class="icms-resposta-paragrafo">a) primeiro item</p>' in campo
    assert '1. segundo &lt;b&gt;item&lt;/b&gt; &amp; $x$' in campo
    assert '<b>item</b>' not in campo
    assert '\n' not in campo   # uma linha só: sem linha em branco que encerre o bloco HTML


def test_resposta_antiga_sem_quebras_aparece_como_um_paragrafo():
    from core import armazenamento as arm
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '002', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS.', 'Problema da Consulta': '',
         'CNAE Detectado': '', 'Resposta': 'texto achatado antigo'}])
    at = _app().run(timeout=30)
    at.tabs[1].selectbox[0].set_value("consulta").run(timeout=30)
    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}
    at.run(timeout=30)
    campo = next(m.value for m in at.markdown if "texto achatado antigo" in m.value)
    assert campo.count('<p class="icms-resposta-paragrafo">') == 1


# --- perfis ----------------------------------------------------------------
def _tela_inicial(monkeypatch, senha=None):
    """Tela inicial com a senha de admin controlada pelo teste. Substitui
    acesso.senha_admin (o app a chama pelo módulo), de modo que um
    .streamlit/secrets.toml real da máquina nunca influencia o resultado."""
    monkeypatch.setattr(acesso, "senha_admin", lambda _secrets: senha)
    return AppTest.from_file(APP).run(timeout=30)


def test_abre_na_tela_inicial_sem_abas_nem_uploader(monkeypatch):
    at = _tela_inicial(monkeypatch, "segredo")
    assert not at.exception
    assert len(at.tabs) == 0
    assert len(at.get("file_uploader")) == 0
    assert {b.key for b in at.button} >= {"entrar-consulta", "entrar-admin"}


def test_perfil_consulta_ve_so_a_aba_consultar(monkeypatch):
    at = _tela_inicial(monkeypatch, "segredo")
    at.button(key="entrar-consulta").click().run(timeout=30)
    assert not at.exception
    assert len(at.tabs) == 1 and "Consultar" in at.tabs[0].label
    assert len(at.get("file_uploader")) == 0
    assert "Trocar perfil" in [b.label for b in at.button]


def test_admin_com_senha_errada_e_recusado(monkeypatch):
    at = _tela_inicial(monkeypatch, "segredo")
    at.text_input(key="senha-admin").input("errada")
    at.button(key="entrar-admin").click().run(timeout=30)
    assert not at.exception
    assert len(at.error) == 1
    assert len(at.tabs) == 0
    assert at.session_state.filtered_state.get("perfil") is None


def test_admin_com_senha_certa_ve_as_duas_abas(monkeypatch):
    at = _tela_inicial(monkeypatch, "segredo")
    at.text_input(key="senha-admin").input("segredo")
    at.button(key="entrar-admin").click().run(timeout=30)
    assert not at.exception
    assert [t.label for t in at.tabs][0].endswith("Processar e mapear")
    assert len(at.tabs) == 2
    assert len(at.get("file_uploader")) == 1


def test_sem_senha_configurada_o_botao_admin_fica_desabilitado(monkeypatch):
    at = _tela_inicial(monkeypatch)          # nenhum secret definido
    assert at.button(key="entrar-admin").disabled is True
    assert at.text_input(key="senha-admin").disabled is True
    assert any("não configurada" in w.value for w in at.warning)
    # e o perfil Consulta continua disponível
    assert at.button(key="entrar-consulta").disabled is False


def test_trocar_perfil_volta_para_a_tela_inicial():
    at = _app("consulta").run(timeout=30)
    at.button(key="trocar-perfil").click().run(timeout=30)
    assert not at.exception
    assert len(at.tabs) == 0
    assert "entrar-consulta" in {b.key for b in at.button}
