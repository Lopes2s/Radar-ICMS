# tests/test_app.py
"""Fumaça da interface. O AppTest do Streamlit não simula upload de arquivo,
então o fluxo com PDFs é verificado manualmente (ver plano, Tarefa 11); aqui
garantimos que a página abre sem erro e mostra o resultado guardado."""
import io
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402
from core import acesso, armazenamento, diagnostico, edicao, pipeline  # noqa: E402
from interface import formularios  # noqa: E402

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


def _etapa_da_senha(monkeypatch, senha="segredo"):
    """Tela inicial -> clica em "Administrador" -> segunda etapa (senha)."""
    at = _tela_inicial(monkeypatch, senha)
    at.button(key="entrar-admin").click().run(timeout=30)
    return at


def test_abre_na_escolha_do_perfil_sem_abas_nem_uploader_nem_senha(monkeypatch):
    at = _tela_inicial(monkeypatch, "segredo")
    assert not at.exception
    assert len(at.tabs) == 0
    assert len(at.get("file_uploader")) == 0
    assert {b.key for b in at.button} >= {"entrar-consulta", "entrar-admin"}
    assert len(at.text_input) == 0            # a senha só aparece depois de escolher o admin
    assert any("Como deseja entrar" in m.value for m in at.markdown)


def test_perfil_consulta_ve_so_a_aba_consultar(monkeypatch):
    at = _tela_inicial(monkeypatch, "segredo")
    at.button(key="entrar-consulta").click().run(timeout=30)
    assert not at.exception
    assert len(at.tabs) == 1 and "Consultar" in at.tabs[0].label
    assert len(at.get("file_uploader")) == 0
    assert "Trocar perfil" in [b.label for b in at.button]


def test_escolher_administrador_pede_a_senha_sem_entrar(monkeypatch):
    at = _etapa_da_senha(monkeypatch)
    assert not at.exception
    assert len(at.text_input) == 1 and at.text_input(key="senha-admin").value == ""
    assert {b.key for b in at.button} >= {"confirmar-admin", "voltar-login"}
    assert "entrar-consulta" not in {b.key for b in at.button}
    assert len(at.tabs) == 0
    assert at.session_state.filtered_state.get("perfil") is None


def test_voltar_da_senha_retorna_a_escolha_do_perfil(monkeypatch):
    at = _etapa_da_senha(monkeypatch)
    at.button(key="voltar-login").click().run(timeout=30)
    assert not at.exception
    assert len(at.text_input) == 0
    assert {b.key for b in at.button} >= {"entrar-consulta", "entrar-admin"}


def test_admin_com_senha_errada_e_recusado_e_continua_pedindo(monkeypatch):
    at = _etapa_da_senha(monkeypatch)
    at.text_input(key="senha-admin").input("errada")
    at.button(key="confirmar-admin").click().run(timeout=30)
    assert not at.exception
    assert len(at.error) == 1
    assert len(at.tabs) == 0
    assert at.session_state.filtered_state.get("perfil") is None
    assert len(at.text_input) == 1             # segue na etapa da senha


def test_admin_com_senha_certa_ve_as_duas_abas(monkeypatch):
    at = _etapa_da_senha(monkeypatch)
    at.text_input(key="senha-admin").input("segredo")
    at.button(key="confirmar-admin").click().run(timeout=30)
    assert not at.exception
    assert [t.label for t in at.tabs][0].endswith("Processar e mapear")
    assert len(at.tabs) == 2
    assert len(at.get("file_uploader")) == 1
    assert "login_etapa" not in at.session_state.filtered_state   # etapa limpa ao entrar


def test_sem_senha_configurada_o_admin_fica_desabilitado(monkeypatch):
    at = _tela_inicial(monkeypatch)          # nenhum secret definido
    assert at.button(key="entrar-admin").disabled is True
    assert any("não configurada" in w.value for w in at.warning)
    assert len(at.text_input) == 0
    # e o perfil Consulta continua disponível
    assert at.button(key="entrar-consulta").disabled is False


def test_trocar_perfil_volta_para_a_escolha_do_perfil(monkeypatch):
    at = _etapa_da_senha(monkeypatch)
    at.text_input(key="senha-admin").input("segredo")
    at.button(key="confirmar-admin").click().run(timeout=30)
    at.button(key="trocar-perfil").click().run(timeout=30)
    assert not at.exception
    assert len(at.tabs) == 0
    assert len(at.text_input) == 0             # volta à escolha, não à senha
    assert "entrar-consulta" in {b.key for b in at.button}


def test_trocar_perfil_do_consulta_volta_para_a_escolha_do_perfil():
    at = _app("consulta").run(timeout=30)
    at.button(key="trocar-perfil").click().run(timeout=30)
    assert not at.exception
    assert len(at.tabs) == 0
    assert {b.key for b in at.button} >= {"entrar-consulta", "entrar-admin"}


def test_login_nao_mostra_a_lateral_nem_a_marca_da_lateral(monkeypatch):
    at = _tela_inicial(monkeypatch, "segredo")
    assert len(at.sidebar.markdown) == 0 and len(at.sidebar.button) == 0


def test_depois_do_login_a_lateral_tem_a_marca(monkeypatch):
    at = _tela_inicial(monkeypatch, "segredo")
    at.button(key="entrar-consulta").click().run(timeout=30)
    assert any("Martinelli Advogados" in m.value for m in at.sidebar.markdown)


def test_citacao_legal_ganha_recuo_e_o_marcador_invisivel_nunca_aparece():
    from core import armazenamento as arm
    from core.pdf_text import MARCA_CITACAO
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS.', 'Problema da Consulta': 'p',
         'CNAE Detectado': '',
         'Resposta': ('Texto do fisco.@@' + MARCA_CITACAO + '"Art. 31. Citado <b>."@@'
                      'Fisco de novo.').replace('@@', chr(10) * 2)},
    ])
    at = _app().run(timeout=30)
    at.tabs[1].selectbox[0].set_value("consulta").run(timeout=30)
    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}
    at.run(timeout=30)
    assert not at.exception
    campo = next(m.value for m in at.markdown if '<p class="icms-resposta-paragrafo' in m.value
                 and 'Texto do fisco.' in m.value)
    assert MARCA_CITACAO not in campo
    assert campo.count('<p class="icms-resposta-paragrafo">') == 2
    # o recuo vai INLINE: o CSS do Streamlit para <p> dentro do markdown é mais
    # específico que uma regra só por classe e a anulava (visto no navegador).
    assert ('<p class="icms-resposta-paragrafo icms-resposta-citacao" '
            'style="margin-left:2.5rem">'
            '&quot;Art. 31. Citado &lt;b&gt;.&quot;</p>') in campo
    assert campo.count('style="margin-left') == 1   # só a citação, não o fisco


def test_banco_de_versao_mais_nova_mostra_erro_amigavel():
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    conn.execute(f"PRAGMA user_version = {armazenamento.SCHEMA_VERSAO + 1}")
    conn.commit()
    conn.close()

    at = _app().run(timeout=30)

    assert not at.exception
    assert any("mais nova" in e.value for e in at.error)


def test_renderizar_a_aba_nao_gera_o_xlsx(monkeypatch):
    # a planilha só pode ser montada quando o usuário clica em "Baixar"
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    armazenamento.criar_esquema(conn)
    armazenamento.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Súmula': 'ICMS'},
    ])
    conn.close()

    def _nao_deve_rodar(*args, **kwargs):
        raise AssertionError("xlsx gerado sem clique")

    monkeypatch.setattr("core.consulta.exportar_xlsx", _nao_deve_rodar)

    at = _app().run(timeout=30)

    assert not at.exception


def _lote_com_uma_consulta():
    from core import pipeline
    return pipeline.Lote(
        consultas=[{'Ano': '2026', 'Nº da Consulta': '001',
                    'Data da Publicação': '2026-01-19', 'Protocolo': '',
                    'Súmula': 'ICMS', 'Problema da Consulta': 'a',
                    'CNAE Detectado': '', 'Resposta': 'r'}],
        arquivos=[{'Arquivo': 'c.pdf', 'Tipo': 'consulta', 'Consultas': 1,
                   'Regimes': 0, 'Descartes': 0, 'Erro': ''}])


def _com_analise(lote):
    from core import diagnostico
    at = _app()
    at.session_state["analise"] = {"lote": lote,
                                   "diagnostico": diagnostico.diagnosticar(lote)}
    return at


def test_analise_guardada_mostra_o_diagnostico_e_nao_grava_ainda():
    at = _com_analise(_lote_com_uma_consulta()).run(timeout=30)

    assert not at.exception
    assert any("nada foi gravado" in s.value for s in at.subheader)
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    armazenamento.criar_esquema(conn)
    assert armazenamento.buscar_consultas(conn) == []


def test_clicar_em_gravar_persiste_e_mostra_o_resultado():
    at = _com_analise(_lote_com_uma_consulta()).run(timeout=30)

    at.button(key="gravar").click().run(timeout=30)

    assert not at.exception
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    assert len(armazenamento.buscar_consultas(conn)) == 1
    assert "analise" not in at.session_state
    assert at.session_state["resultado"]["mapeamento"]["consultas"]["novos"] == 1


def test_analise_nomeia_o_arquivo_com_erro_e_ainda_deixa_gravar_os_bons():
    lote = _lote_com_uma_consulta()
    lote.arquivos.append({'Arquivo': 'ruim.pdf', 'Tipo': 'erro', 'Consultas': 0,
                          'Regimes': 0, 'Descartes': 0,
                          'Erro': 'PDFSyntaxError: arquivo inválido'})

    at = _com_analise(lote).run(timeout=30)

    assert any("ruim.pdf" in e.value and "PDFSyntaxError" in e.value for e in at.error)
    assert at.button(key="gravar").disabled is False


def test_gravar_fica_desabilitado_quando_nao_ha_registros():
    from core import pipeline
    lote = pipeline.Lote(arquivos=[{'Arquivo': 'x.pdf', 'Tipo': 'desconhecido',
                                    'Consultas': 0, 'Regimes': 0,
                                    'Descartes': 0, 'Erro': ''}])
    at = _com_analise(lote).run(timeout=30)
    assert at.button(key="gravar").disabled is True


def test_trocar_perfil_descarta_a_analise_pendente():
    at = _com_analise(_lote_com_uma_consulta()).run(timeout=30)
    at.button(key="trocar-perfil").click().run(timeout=30)
    assert "analise" not in at.session_state


def test_analise_de_outros_arquivos_e_descartada():
    at = _com_analise(_lote_com_uma_consulta())
    at.session_state["analise"]["nomes"] = ("outro.pdf",)
    at.run(timeout=30)
    assert "analise" not in at.session_state
    assert not any(b.key == "gravar" for b in at.button)


def _semeia(consultas=(), regimes=()):
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    armazenamento.criar_esquema(conn)
    armazenamento.salvar_consultas(conn, list(consultas))
    armazenamento.salvar_regimes(conn, list(regimes))
    conn.close()


def test_pagina_injeta_o_tema_e_a_marca_martinelli():
    at = _app().run(timeout=30)
    assert not at.exception
    textos = [m.value for m in at.markdown]
    assert any("--primary: #1C62CB" in t and "<style>" in t for t in textos)
    assert any("Martinelli Advogados" in t and "Mapeador Tribut" in t for t in textos)


def test_consultar_mostra_os_indicadores_do_banco():
    _semeia(
        consultas=[{'Ano': '2025', 'Nº da Consulta': '001'}, {'Ano': '2026', 'Nº da Consulta': '002'}],
        regimes=[{'ANO': '2026', 'Nº DO REGIME ESPECIAL': '1/2026', 'CNPJ REQUERENTE': '11'}],
    )
    at = _app().run(timeout=30)
    assert not at.exception
    valores = {m.label: m.value for m in at.metric}
    assert valores["Consultas mapeadas"] == "2"
    assert valores["Regimes mapeados"] == "1"
    assert valores["Anos cobertos"] == "2025–2026"
    assert valores["Última importação"] == "—"   # nada foi importado por PDF neste banco


def test_banco_vazio_mostra_o_estado_vazio():
    at = _app().run(timeout=30)
    assert any("Ainda não há atos mapeados" in m.value for m in at.markdown)
    assert len(at.dataframe) == 0   # sem atos, não há tabela


def test_busca_sem_resultado_mostra_o_estado_vazio_de_filtro():
    _semeia(consultas=[{'Ano': '2026', 'Nº da Consulta': '001', 'Súmula': 'ICMS'}])
    at = _app().run(timeout=30)
    at.tabs[1].text_input[0].input("termo-que-nao-existe").run(timeout=30)
    assert not at.exception
    assert any("Nenhum ato com esses filtros" in m.value for m in at.markdown)
    assert not any("Baixar estes resultados" in b.label for b in at.tabs[1].download_button)


def test_analisar_fica_desabilitado_sem_arquivos():
    at = _app().run(timeout=30)
    assert at.button(key="analisar").disabled is True


# --- edição manual (detalhe e análise) --------------------------------------
REGIME = {'ANO': '2026', 'DATA': '2026-03-01', 'Nº DO REGIME ESPECIAL': '9.053/2026',
          'EMPRESA': 'Alfa Ltda', 'CNPJ REQUERENTE': '11.222.333/0001-81',
          'VIGÊNCIA DO RE': '', 'EMENTA': 'ementa original'}
PREFIXO = formularios.prefixo_de('regime', [REGIME['Nº DO REGIME ESPECIAL'],
                                            REGIME['CNPJ REQUERENTE']])
PREFIXO_ANALISE = formularios.prefixo_de('regime', [REGIME['Nº DO REGIME ESPECIAL'],
                                                    REGIME['CNPJ REQUERENTE']],
                                         contexto="analise")


def _banco_do_teste():
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    armazenamento.criar_esquema(conn)
    return conn


def _regimes_no_banco():
    conn = _banco_do_teste()
    try:
        return armazenamento.buscar_regimes(conn)
    finally:
        conn.close()


def _linha_0(at):
    """O AppTest não guarda a seleção da tabela entre execuções (um navegador guarda):
    reinjeta a linha 0 antes de cada interação com o detalhe."""
    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}


def _abre_o_detalhe_do_regime(perfil, regimes=(REGIME,)):
    """Semeia os regimes, abre a aba Consultar no tipo 'regime' e seleciona a linha 0."""
    _semeia(regimes=list(regimes))
    at = _app(perfil).run(timeout=30)
    aba = at.tabs[1] if perfil == "admin" else at.tabs[0]
    aba.selectbox[0].set_value("regime").run(timeout=30)
    _linha_0(at)
    at.run(timeout=30)
    return at


def test_perfil_consulta_nao_ve_o_botao_editar():
    at = _abre_o_detalhe_do_regime("consulta")
    assert any("Regime Especial nº 9.053/2026" in s.value for s in at.subheader)
    assert "editar-registro" not in {b.key for b in at.button}


def test_admin_ve_o_botao_editar_e_o_formulario_traz_os_valores_atuais():
    at = _abre_o_detalhe_do_regime("admin")
    assert "editar-registro" in {b.key for b in at.button}
    _linha_0(at)
    at.button(key="editar-registro").click().run(timeout=30)
    assert not at.exception
    assert at.text_input(key=f"{PREFIXO}|EMPRESA").value == "Alfa Ltda"
    assert at.text_input(key=f"{PREFIXO}|CNPJ REQUERENTE").value == "11.222.333/0001-81"
    assert at.text_area(key=f"{PREFIXO}|EMENTA").value == "ementa original"


def test_admin_edita_um_campo_do_regime_pelo_detalhe():
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="editar-registro").click().run(timeout=30)
    at.text_input(key=f"{PREFIXO}|VIGÊNCIA DO RE").input("12 meses")
    _linha_0(at)
    at.button(key=f"{PREFIXO}|enviar").click().run(timeout=30)
    assert not at.exception
    assert _regimes_no_banco()[0]['VIGÊNCIA DO RE'] == '12 meses'
    conn = _banco_do_teste()
    historico = armazenamento.historico_de(conn, 'regimes', {
        'Nº DO REGIME ESPECIAL': '9.053/2026', 'CNPJ REQUERENTE': '11.222.333/0001-81'})
    conn.close()
    assert historico[0]['origem'] == 'manual'
    assert "editando" not in at.session_state.filtered_state       # saiu do modo edição
    assert any("Ato atualizado" in t.value for t in at.toast)


def test_admin_corrige_a_chave_do_regime_pelo_detalhe():
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="editar-registro").click().run(timeout=30)
    at.text_input(key=f"{PREFIXO}|CNPJ REQUERENTE").input("99.999.999/0001-99")
    _linha_0(at)
    at.button(key=f"{PREFIXO}|enviar").click().run(timeout=30)
    assert not at.exception
    linhas = _regimes_no_banco()
    assert len(linhas) == 1 and linhas[0]['CNPJ REQUERENTE'] == '99.999.999/0001-99'
    assert any("chave foi corrigida" in t.value for t in at.toast)


def test_chave_em_conflito_mostra_o_erro_e_nao_grava():
    outro = {**REGIME, 'Nº DO REGIME ESPECIAL': '1/2026', 'EMPRESA': 'Outra'}
    at = _abre_o_detalhe_do_regime("admin", regimes=(REGIME, outro))
    _linha_0(at)
    at.button(key="editar-registro").click().run(timeout=30)
    # a linha 0 aberta pode ser qualquer um dos dois: lê a chave que está na tela
    campo = next(t for t in at.text_input
                 if (t.key or "").endswith("|Nº DO REGIME ESPECIAL"))
    prefixo = campo.key.rsplit("|", 1)[0]
    de_fora = '1/2026' if campo.value == '9.053/2026' else '9.053/2026'
    campo.input(de_fora)
    _linha_0(at)
    at.button(key=f"{prefixo}|enviar").click().run(timeout=30)
    assert not at.exception
    assert any("Já existe outro ato com essa chave" in e.value for e in at.error)
    assert {r['Nº DO REGIME ESPECIAL'] for r in _regimes_no_banco()} == {'9.053/2026', '1/2026'}


def test_cancelar_a_edicao_volta_ao_detalhe():
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="editar-registro").click().run(timeout=30)
    _linha_0(at)
    at.button(key="cancelar-edicao").click().run(timeout=30)
    assert not at.exception
    assert "editar-registro" in {b.key for b in at.button}
    assert _regimes_no_banco()[0]['EMENTA'] == 'ementa original'


def _analise_com(lote):
    conn = _banco_do_teste()
    try:
        conflitos = edicao.ajustes_em_conflito(conn, lote)
    finally:
        conn.close()
    return {"lote": lote, "diagnostico": diagnostico.diagnosticar(lote), "conflitos": conflitos}


def _lote_sem_vigencia():
    lote = pipeline.Lote(
        regimes=[dict(REGIME)],
        arquivos=[{'Arquivo': 'r.pdf', 'Tipo': 'regime', 'Consultas': 0, 'Regimes': 1,
                   'Descartes': 0, 'Erro': ''}])
    lote.origem[('regime', REGIME['Nº DO REGIME ESPECIAL'], REGIME['CNPJ REQUERENTE'])] = 'r.pdf'
    return lote


def test_na_analise_o_admin_corrige_um_campo_e_o_aviso_some():
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    assert any("A303" in w.value for w in at.warning)                # vigência vazia avisada
    at.text_input(key=f"{PREFIXO_ANALISE}|VIGÊNCIA DO RE").input("12 meses")
    at.button(key=f"{PREFIXO_ANALISE}|enviar").click().run(timeout=30)
    assert not at.exception
    analise = at.session_state["analise"]
    assert analise["lote"].regimes[0]['VIGÊNCIA DO RE'] == '12 meses'
    assert not any("A303" in w.value for w in at.warning)            # diagnóstico refeito
    assert analise["lote"].ajustados == {
        ('regime', '9.053/2026', '11.222.333/0001-81'): {'VIGÊNCIA DO RE'}}
    assert _regimes_no_banco() == []                                 # nada foi gravado ainda


def test_gravar_depois_de_ajustar_na_analise_protege_o_ajuste_na_reimportacao():
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.text_input(key=f"{PREFIXO_ANALISE}|VIGÊNCIA DO RE").input("12 meses")
    at.button(key=f"{PREFIXO_ANALISE}|enviar").click().run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert _regimes_no_banco()[0]['VIGÊNCIA DO RE'] == '12 meses'
    # reimportar o PDF original (sem vigência) não desfaz o ajuste
    conn = _banco_do_teste()
    armazenamento.salvar_regimes(conn, [dict(REGIME)])
    conn.close()
    assert _regimes_no_banco()[0]['VIGÊNCIA DO RE'] == '12 meses'


def test_na_analise_chave_repetida_mostra_o_erro():
    lote = _lote_sem_vigencia()
    lote.regimes.append({**REGIME, 'Nº DO REGIME ESPECIAL': '1/2026', 'EMPRESA': 'Outra'})
    at = _app("admin")
    at.session_state["analise"] = _analise_com(lote)
    at.run(timeout=30)
    at.text_input(key=f"{PREFIXO_ANALISE}|Nº DO REGIME ESPECIAL").input("1/2026")
    at.button(key=f"{PREFIXO_ANALISE}|enviar").click().run(timeout=30)
    assert not at.exception
    assert any("Outro ato desta análise já usa essa chave" in e.value for e in at.error)
    assert at.session_state["analise"]["lote"].regimes[0]['Nº DO REGIME ESPECIAL'] == '9.053/2026'


def _caixa(at, tipo="regime", chave=(REGIME['Nº DO REGIME ESPECIAL'], REGIME['CNPJ REQUERENTE'])):
    return at.checkbox(key="sobrescrever|" + "|".join([tipo, *chave]))


def _banco_com_vigencia_ajustada():
    conn = _banco_do_teste()
    armazenamento.salvar_regimes(conn, [dict(REGIME)])
    edicao.editar_registro(conn, 'regime', {c: REGIME[c] for c in pipeline.CHAVE_REGIMES},
                           {'VIGÊNCIA DO RE': '12 meses'})
    conn.close()


def test_conflito_de_ajuste_aparece_desmarcado_e_gravar_mantem_o_ajuste():
    _banco_com_vigencia_ajustada()
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())    # o PDF traz vigência vazia
    at.run(timeout=30)
    assert any("já têm ajuste manual" in w.value for w in at.warning)
    assert _caixa(at).value is False
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert _regimes_no_banco()[0]['VIGÊNCIA DO RE'] == '12 meses'


def test_marcar_sobrescrever_grava_o_valor_do_pdf():
    _banco_com_vigencia_ajustada()
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    _caixa(at).check().run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert _regimes_no_banco()[0]['VIGÊNCIA DO RE'] == ''


def test_editar_no_detalhe_de_ato_que_tambem_esta_na_analise_nao_duplica_chaves():
    conn = _banco_do_teste()
    armazenamento.salvar_regimes(conn, [dict(REGIME)])
    conn.close()
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.tabs[1].selectbox[0].set_value("regime").run(timeout=30)
    _linha_0(at)
    at.run(timeout=30)
    _linha_0(at)
    at.button(key="editar-registro").click().run(timeout=30)
    assert not at.exception
    assert at.text_input(key=f"{PREFIXO}|EMPRESA").value == "Alfa Ltda"
    assert at.text_input(key=f"{PREFIXO_ANALISE}|EMPRESA").value == "Alfa Ltda"


def test_na_analise_trocar_a_chave_de_ato_ja_gravado_mostra_o_erro_e_nada_muda():
    conn = _banco_do_teste()
    armazenamento.salvar_regimes(conn, [dict(REGIME)])
    conn.close()
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.text_input(key=f"{PREFIXO_ANALISE}|CNPJ REQUERENTE").input("99.999.999/0001-99")
    at.button(key=f"{PREFIXO_ANALISE}|enviar").click().run(timeout=30)
    assert not at.exception
    assert any("já está gravado" in e.value for e in at.error)
    lote = at.session_state["analise"]["lote"]
    assert lote.regimes[0]['CNPJ REQUERENTE'] == REGIME['CNPJ REQUERENTE']
    assert lote.chaves_substituidas == []

# --- consulta do CNPJ (Receita Federal) --------------------------------------
CNPJ_DO_REGIME = '11222333000181'


def _com_rede(monkeypatch):
    from tests.test_cnpj import Rede
    rede = Rede()
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '1')
    monkeypatch.setattr('core.cnpj._abrir', rede)
    return rede


def _guarda_receita(cnae_codigo='6422100'):
    conn = _banco_do_teste()
    armazenamento.salvar_cnpj_receita(
        conn, {'cnpj': CNPJ_DO_REGIME, 'razao_social': 'Alfa Ltda', 'cnae_codigo': cnae_codigo,
               'cnae_descricao': 'Bancos múltiplos', 'situacao': 'ATIVA'},
        consultado_em='2026-11-03T12:00:00+00:00')
    conn.close()


def _textos(at):
    return [m.value for m in at.markdown] + [c.value for c in at.caption]


def test_detalhe_do_regime_sem_consulta_avisa_e_so_o_admin_ve_o_botao():
    at = _abre_o_detalhe_do_regime("consulta")
    assert any("ainda não consultado" in t for t in _textos(at))
    assert "consultar-cnpj" not in {b.key for b in at.button}
    at = _abre_o_detalhe_do_regime("admin")
    assert any("ainda não consultado" in t for t in _textos(at))
    assert "consultar-cnpj" in {b.key for b in at.button}


def test_detalhe_mostra_o_cnae_e_a_situacao_da_receita_para_qualquer_perfil():
    _guarda_receita()
    at = _abre_o_detalhe_do_regime("consulta")
    textos = " ".join(_textos(at))
    assert "6422-1/00" in textos and "Bancos múltiplos" in textos and "ATIVA" in textos
    assert "03/11/2026" in textos
    assert not {"consultar-cnpj", "aplicar-cnae"} & {b.key for b in at.button}


def test_admin_consulta_o_cnpj_pelo_detalhe(monkeypatch):
    rede = _com_rede(monkeypatch)
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="consultar-cnpj").click().run(timeout=30)
    assert not at.exception
    assert rede.urls == [f'https://brasilapi.com.br/api/cnpj/v1/{CNPJ_DO_REGIME}']
    assert any("CNPJ consultado" in t.value for t in at.toast)
    assert at.session_state["tabela-resultados"]["selection"]["rows"] == []   # detalhe fechado
    _linha_0(at)
    at.run(timeout=30)
    assert "6422-1/00" in " ".join(_textos(at))
    assert "aplicar-cnae" in {b.key for b in at.button}


def test_consulta_pelo_detalhe_mostra_o_motivo_quando_a_rede_falha(monkeypatch):
    import urllib.error
    from tests.test_cnpj import Rede
    monkeypatch.setattr('core.cnpj._abrir', Rede(erro=urllib.error.URLError('sem rede')))
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="consultar-cnpj").click().run(timeout=30)
    assert not at.exception
    assert any("sem acesso à BrasilAPI" in t.value for t in at.toast)
    assert at.session_state["tabela-resultados"]["selection"]["rows"] == []   # detalhe fechado


def test_admin_aplica_o_cnae_da_receita_ao_regime():
    _guarda_receita()
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="aplicar-cnae").click().run(timeout=30)
    assert not at.exception
    linha = _regimes_no_banco()[0]
    assert linha['CNAE REQUERENTE'] == '6422-1/00'
    assert linha['DESCRIÇÃO CNAE'] == 'Bancos múltiplos'
    from core import consulta
    conn = _banco_do_teste()
    assert set(consulta.ajustes(conn, 'regime', REGIME)) == {'CNAE REQUERENTE', 'DESCRIÇÃO CNAE'}
    conn.close()
    assert any("CNAE aplicado" in t.value for t in at.toast)


def test_divergencia_de_cnae_aparece_so_quando_o_regime_ja_tem_outro_cnae():
    _guarda_receita()
    at = _abre_o_detalhe_do_regime("admin", regimes=({**REGIME, 'CNAE REQUERENTE': '4930-2/02'},))
    assert any("difere" in w.value and "4930-2/02" in w.value and "6422-1/00" in w.value
               for w in at.warning)
    at = _abre_o_detalhe_do_regime("admin")           # CNAE em branco: sem divergência
    assert not any("difere" in w.value for w in at.warning)


def test_gravar_na_analise_consulta_os_cnpjs_e_avisa(monkeypatch):
    rede = _com_rede(monkeypatch)
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert rede.urls == [f'https://brasilapi.com.br/api/cnpj/v1/{CNPJ_DO_REGIME}']
    assert any("Receita Federal: 1 CNPJ(s) consultado(s)" in t.value for t in at.toast)
    assert set(at.session_state["resultado"]) == {
        "arquivos", "consultas", "regimes", "descartes", "mapeamento", "xlsx"}
    conn = _banco_do_teste()
    assert armazenamento.cnpj_receita_de(conn, CNPJ_DO_REGIME)['cnae_codigo'] == '6422100'
    conn.close()


def test_gravar_sem_internet_grava_e_avisa(monkeypatch):
    import urllib.error
    from tests.test_cnpj import Rede
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '1')
    monkeypatch.setattr('core.cnpj._abrir', Rede(erro=urllib.error.URLError('sem rede')))
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert len(_regimes_no_banco()) == 1
    assert any("Receita Federal:" in t.value and "sem resposta" in t.value for t in at.toast)


def test_gravar_com_a_consulta_desligada_nao_chama_a_rede(monkeypatch):
    rede = _com_rede(monkeypatch)
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '0')
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert rede.urls == [] and len(_regimes_no_banco()) == 1
