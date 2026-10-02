# app.py
import base64
import html
import io
import os
import re
import tempfile

from core.bootstrap import DEPS_APP, garantir_dependencias

# antes de importar streamlit/pdfplumber/openpyxl, que vêm logo abaixo.
# Para o primeiro arranque, quando nem o streamlit existe, use `python iniciar.py`.
garantir_dependencias(DEPS_APP)

import streamlit as st  # noqa: E402

from core import acesso, armazenamento, consulta, pipeline, planilha  # noqa: E402
from core.pdf_text import MARCA_CITACAO  # noqa: E402

_FORCAR = {"Detectar automaticamente": None,
           "Forçar Consulta": "consulta",
           "Forçar Regime": "regime"}

# MAPEADOR_BANCO permite apontar para um banco de teste/alternativo; sem a
# variável, cai no padrão de armazenamento.conectar() (mapeamento.db na raiz
# do projeto).
_CAMINHO_BANCO = os.environ.get("MAPEADOR_BANCO") or None

# Identidade visual "ICMS Tech" (Martinelli Advogados) — ver manual de marca
# "ICMS Tech — Conceito 1c". Cores/fonte/raio ficam em .streamlit/config.toml
# (tema nativo do Streamlit); aqui só o que o config.toml não cobre: logo,
# sombra dos cards e a cor de alerta da métrica de descartes.
_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_ICONE_ESCURO = os.path.join(_ASSETS, "icms_tech_icon_dark.png")   # squircle grafite — fundos claros
_ICONE_CLARO = os.path.join(_ASSETS, "icms_tech_icon_light.png")   # squircle branco — fundos escuros

# Vermelho de alerta: não está no manual (sinalizado na entrega desta tarefa)
# — usado só na métrica "Descartes registrados", que já representa pendência.
_VERMELHO_ALERTA = "#C0362C"
# Cor do endosso "MARTINELLI ADVOGADOS" amostrada do próprio lockup.png
# (região abaixo do wordmark) — o manual não deu um hex para ela.
_CINZA_ENDOSSO = "#6B7280"
# Azul institucional — mesmo valor de .streamlit/config.toml (theme.primaryColor).
# Repetido aqui porque o CSS injetado não lê o config.toml.
_AZUL_INSTITUCIONAL = "#1C62CB"
# Âmbar amostrado da tela de referência (busca de normas) enviada pelo
# usuário, só para o texto "Total de atos localizados" na aba Consultar —
# não faz parte do manual ICMS Tech.
_AMBAR_TOTAL = "#A66C00"


def _base64_png(caminho: str) -> str:
    with open(caminho, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


st.set_page_config(page_title="Mapeador Tributário PR", page_icon=_ICONE_ESCURO,
                    layout="wide")

# CSS injetado: contorno para o que .streamlit/config.toml não expõe
# nativamente (sombra de card, cor condicional de métrica, o lockup
# compacto da sidebar, que é HTML próprio porque não existe um PNG do
# lockup já preparado para fundo escuro — só o ícone tem as duas versões).
st.markdown(f"""
<style>
/* Cards brancos com leve elevação — manual: "cantos arredondados, sombra
   suave". baseRadius do tema já arredonda; a sombra precisa de CSS porque
   o tema do Streamlit não tem uma opção nativa para box-shadow. */
div[class*="st-key-card-"] {{
    box-shadow: 0 1px 3px rgba(38, 38, 38, 0.12);
}}

/* Métrica "Descartes registrados": vermelho de alerta em vez do grafite
   padrão, porque semanticamente representa pendência/divergência — manual:
   "quando o dado é um alerta ou divergência, o número usa a cor de alerta". */
div[class*="st-key-metric-descartes"] [data-testid="stMetricValue"] {{
    color: {_VERMELHO_ALERTA};
}}

/* Lockup compacto no topo da sidebar escura (ícone + wordmark + endosso).
   HTML próprio, não o lockup.png: esse PNG foi montado para fundo claro
   (ícone grafite, texto grafite) e ficaria ilegível sobre a sidebar escura
   — por isso reconstruímos com o ícone claro (squircle branco) e o texto
   em branco/cinza-claro, mesma tipografia do manual (Urbanist 700+300 no
   wordmark, 600 com letter-spacing no endosso). */
.icms-sidebar-logo {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    /* área de proteção mínima (manual: 1/4 da altura do ícone) nos dois
       lados do bloco, para nada encostar no ícone nem no texto */
    padding: 0.5rem 0.35rem 1rem 0.35rem;
}}
.icms-sidebar-logo img {{
    height: 40px;
    width: 40px;
}}
.icms-sidebar-logo .icms-textos {{
    line-height: 1.05;
}}
.icms-sidebar-logo .icms-wordmark {{
    font-family: 'Urbanist', 'Inter', 'Manrope', sans-serif;
    font-size: 1.05rem;
    color: #FFFFFF;
}}
.icms-sidebar-logo .icms-wordmark b {{
    font-weight: 700;
}}
.icms-sidebar-logo .icms-wordmark span {{
    font-weight: 300;
}}
.icms-sidebar-logo .icms-endosso {{
    font-family: 'Urbanist', 'Inter', 'Manrope', sans-serif;
    font-weight: 600;
    font-size: 0.55rem;
    letter-spacing: 0.22em;
    color: {_CINZA_ENDOSSO};
}}

/* Painel de busca da aba Consultar, no estilo da tela de referência (busca
   de normas): rótulos dos campos em azul institucional. Reusa o azul da
   marca ICMS Tech (#1C62CB) em vez do azul-marinho da referência (#00205B)
   — mantém uma única cor de destaque no app. Duas variantes de seletor
   porque não confirmei em navegador qual delas o Streamlit 1.63 realmente
   usa para o rótulo do widget (contorno, ver observações da entrega). */
.st-key-painel-busca [data-testid="stWidgetLabel"] p,
.st-key-painel-busca label {{
    color: {_AZUL_INSTITUCIONAL};
    font-weight: 600;
}}

/* Barra "RESULTADO DA PESQUISA" da tela de referência — mesma cor azul da
   marca em vez do azul-marinho da imagem, pelo mesmo motivo acima. */
.icms-resultado-barra {{
    background: {_AZUL_INSTITUCIONAL};
    color: #FFFFFF;
    font-weight: 700;
    text-align: center;
    padding: 0.5rem 0;
    border-radius: 0.4rem;
    margin-bottom: 0.6rem;
    letter-spacing: 0.04em;
}}

/* "Total de atos localizados: N" — cor âmbar amostrada da própria imagem de
   referência enviada pelo usuário (não é uma cor do manual ICMS Tech; ver
   decisões sinalizadas na entrega). */
.icms-total-atos {{
    color: {_AMBAR_TOTAL};
    font-weight: 700;
    margin-bottom: 0.5rem;
}}

/* Rótulo de cada campo no modal de detalhe de uma consulta/regime */
.icms-campo-detalhe-rotulo {{
    color: {_AZUL_INSTITUCIONAL};
    font-weight: 700;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 0.9rem;
}}

.icms-resposta-paragrafo {{
    margin: 0 0 0.9em 0;
    line-height: 1.55;
    text-align: justify;
}}
</style>
""", unsafe_allow_html=True)

# Sem cabeçalho principal: a única marca do app fica no lockup compacto da
# sidebar (a pedido do usuário, ao restilizar a aba Consultar — antes havia
# aqui o lockup horizontal + legenda).
with st.sidebar:
    st.markdown(f"""
    <div class="icms-sidebar-logo">
        <img src="data:image/png;base64,{_base64_png(_ICONE_CLARO)}" />
        <div class="icms-textos">
            <div class="icms-wordmark"><b>ICMS</b> <span>Tech</span></div>
            <div class="icms-endosso">MARTINELLI ADVOGADOS</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()


def _conexao():
    conn = armazenamento.conectar(_CAMINHO_BANCO)
    armazenamento.criar_esquema(conn)
    return conn


def _titulo_do_registro(tipo: str, registro: dict) -> str:
    if tipo == "consulta":
        numero, ano = registro.get("Nº da Consulta", ""), registro.get("Ano", "")
        return f"Consulta nº {numero}/{ano}" if numero else "Consulta"
    numero = registro.get("Nº DO REGIME ESPECIAL", "")
    return f"Regime Especial nº {numero}" if numero else "Regime Especial"


def _fecha_selecao_da_tabela():
    """Callback do fechar do modal: reseta a seleção da tabela para o modal
    não reabrir sozinho no próximo rerun (a linha continuaria "selecionada"
    senão). Reatribui a chave inteira — o estado de seleção do st.dataframe
    é só-leitura, não dá para mudar em lugar (ver DataframeSelectionState)."""
    st.session_state["tabela-resultados"] = {"selection": {"rows": []}}


# Os campos numerados de regime (ABRANGÊNCIA, BENEFÍCIOS/PROCEDIMENTOS,
# DISPOSIÇÕES GERAIS) saem de parsers/regimes.py como um parágrafo só — de
# propósito, para caber numa célula de planilha (ver comentário de
# _extrai_abrangencia). Só na exibição do modal, quebramos de novo antes de
# cada tópico numerado ("2.1.1.", "3.7." etc.), para ficar legível como lista.
#
# "(?<=\s)...(?=\s+[A-ZÀ-Ü])" exige: precedido de espaço (não é o meio de
# outro número), pelo menos um ponto interno (rejeita citação de decreto/lei
# de nível único, tipo "Decreto nº 7.871.") e maiúscula logo depois (rejeita
# valor monetário, tipo "R$ 10.000.000,00"). Testado contra os campos reais
# extraídos do PDF Regime_Agroantunes.pdf: nenhum falso positivo.
_MARCADOR_DE_TOPICO = re.compile(r'(?<=\s)(\d+(?:\.\d+)+\.)(?=\s+[A-ZÀ-Ü])')


def _com_quebras_por_topico(texto: str) -> str:
    return _MARCADOR_DE_TOPICO.sub(r'\n\n\1', texto)


_RECUO_CITACAO = "2.5rem"


def _resposta_em_paragrafos(texto: str) -> str:
    """Resposta da consulta como HTML: um <p> por parágrafo ("\\n\\n"), com o
    texto escapado — assim "a)", "1." ou "*" no início de um parágrafo não
    viram lista em Markdown e "<" ou "&" aparecem literalmente. Tudo numa
    linha só: uma linha em branco encerraria o bloco HTML no Markdown. Os
    parágrafos de citação legal ganham a classe de recuo."""
    paragrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    saida = []
    for p in paragrafos:
        # MARCA_CITACAO (invisível) abre o parágrafo de citação legal: vira a
        # classe de recuo e nunca chega ao HTML como texto.
        classe, estilo = "icms-resposta-paragrafo", ""
        if p.startswith(MARCA_CITACAO):
            # O recuo vai INLINE (além da classe): o CSS do Streamlit para <p>
            # dentro do markdown é mais específico que uma regra só por classe
            # e a anulava — comprovado no navegador.
            classe += " icms-resposta-citacao"
            estilo = f' style="margin-left:{_RECUO_CITACAO}"'
        texto_p = p.replace(MARCA_CITACAO, "").strip()
        if texto_p:
            saida.append(f'<p class="{classe}"{estilo}>{html.escape(texto_p)}</p>')
    return "".join(saida)


@st.dialog("Detalhes", width="large", on_dismiss=_fecha_selecao_da_tabela)
def _mostra_detalhe(tipo: str, registro: dict, colunas: list):
    st.subheader(_titulo_do_registro(tipo, registro))
    for campo in colunas:
        valor = registro.get(campo, "")
        if not valor:
            continue
        st.markdown(f'<div class="icms-campo-detalhe-rotulo">{campo}</div>',
                    unsafe_allow_html=True)
        if tipo == "regime":
            st.markdown(_com_quebras_por_topico(valor))
        elif tipo == "consulta" and campo == "Resposta":
            st.markdown(_resposta_em_paragrafos(valor), unsafe_allow_html=True)
        else:
            st.write(valor)


def _processar(enviados, forcar):
    """Processa os uploads, persiste no banco e devolve o resultado a
    guardar na sessão."""
    acesso.exige_admin(st.session_state.get("perfil"))
    lote = pipeline.Lote()
    barra = st.progress(0.0, text="Processando...")
    for i, arq in enumerate(enviados):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(arq.getbuffer())
            caminho = tmp.name
        try:
            pipeline.processar_arquivo(lote, caminho, arq.name, forcar=forcar)
        finally:
            os.unlink(caminho)
        barra.progress((i + 1) / len(enviados), text=f"Processado: {arq.name}")
    barra.empty()
    pipeline.finalizar(lote)

    mapeamento = armazenamento.persistir_lote(_conexao(), lote)

    # planilha em memória, exportação opcional: nada de cópia em disco
    buf = io.BytesIO()
    planilha.gerar_xlsx(buf, lote.consultas, lote.regimes, lote.descartes,
                        lote.arquivos)
    return {"arquivos": lote.arquivos, "consultas": lote.consultas,
            "regimes": lote.regimes, "descartes": lote.descartes,
            "mapeamento": mapeamento, "xlsx": buf.getvalue()}


def _tela_inicial():
    """Escolha de perfil. Consulta entra direto; Administrador exige a senha
    de .streamlit/secrets.toml e fica desabilitado se ela não estiver
    configurada (nunca cai em acesso aberto)."""
    st.markdown("### Como deseja entrar?")
    esperada = acesso.senha_admin(st.secrets)
    col_consulta, col_admin = st.columns(2)

    with col_consulta, st.container(border=True, key="perfil-consulta"):
        st.subheader("Consulta")
        st.caption("Pesquisar as consultas e os regimes já mapeados. Sem senha.")
        if st.button("Entrar para consulta", key="entrar-consulta", type="primary"):
            st.session_state["perfil"] = acesso.PERFIL_CONSULTA
            st.rerun()

    with col_admin, st.container(border=True, key="perfil-admin"):
        st.subheader("Administrador")
        st.caption("Importar PDFs e reprocessar o banco. Exige senha.")
        if esperada is None:
            st.warning("Senha do administrador não configurada. Crie "
                       ".streamlit/secrets.toml com a seção [admin] e a chave senha (veja o README).")
        senha = st.text_input("Senha", type="password", key="senha-admin",
                              disabled=esperada is None)
        if st.button("Entrar como administrador", key="entrar-admin",
                     disabled=esperada is None):
            if acesso.confere(senha, esperada):
                st.session_state["perfil"] = acesso.PERFIL_ADMIN
                st.rerun()
            else:
                st.error("Senha incorreta.")


perfil = st.session_state.get("perfil")
if perfil not in (acesso.PERFIL_CONSULTA, acesso.PERFIL_ADMIN):
    _tela_inicial()
    st.stop()

with st.sidebar:
    if st.button("Trocar perfil", key="trocar-perfil"):
        for chave in ("perfil", "resultado"):
            st.session_state.pop(chave, None)
        st.rerun()

if perfil == acesso.PERFIL_ADMIN:
    aba_processar, aba_consultar = st.tabs(["📥 Processar e mapear", "🔎 Consultar"])
else:
    aba_processar = None
    (aba_consultar,) = st.tabs(["🔎 Consultar"])

if aba_processar is not None:
  with aba_processar:
      with st.sidebar:
          st.header("Como funciona")
          st.markdown(
              "1. Envie os PDFs (consultas SEFA e/ou páginas do Diário).\n"
              "2. A ferramenta detecta o tipo, extrai os campos e mapeia no "
              "banco local.\n"
              "3. Use a aba **Consultar** para buscar o que já foi mapeado, "
              "ou baixe a planilha desta sessão se quiser.\n\n"
              "Reprocessar o mesmo PDF atualiza o que já estava mapeado, "
              "sem duplicar."
          )
          st.divider()
          escolha = st.radio(
              "Tipo do PDF", list(_FORCAR),
              help="Use 'forçar' se a detecção automática errar.",
          )

      arquivos = st.file_uploader("Arraste os PDFs aqui", type=["pdf"],
                                  accept_multiple_files=True)

      if arquivos and st.button("▶️ Processar", type="primary"):
          st.session_state["resultado"] = _processar(arquivos, _FORCAR[escolha])

      # Exibido a partir da sessão, e não de dentro do `if st.button`: assim o
      # resultado continua na tela depois de qualquer reexecução do script
      # (por exemplo, o clique em "Baixar").
      resultado = st.session_state.get("resultado")
      if resultado:
          # bloco inteiro num card branco — manual: "blocos de informação em
          # cards brancos, cantos arredondados, leve elevação"
          with st.container(border=True, key="card-resumo"):
              st.subheader("Resumo do processamento")
              st.dataframe(resultado["arquivos"], width="stretch", hide_index=True)
              erros = [a for a in resultado["arquivos"] if a["Tipo"] == "erro"]
              if erros:
                  st.warning(f"{len(erros)} arquivo(s) não puderam ser lidos — veja a "
                             "coluna Erro acima.")

              c1, c2, c3 = st.columns(3)
              c1.metric("Consultas", len(resultado["consultas"]))
              c2.metric("Regimes", len(resultado["regimes"]))
              # container próprio só para dar um gancho de CSS à cor de alerta
              # (ver <style> acima) — o st.metric em si não muda de assinatura
              with c3, st.container(key="metric-descartes"):
                  st.metric("Descartes registrados", len(resultado["descartes"]))

              mapa = resultado["mapeamento"]
              st.caption(
                  f"Mapeado: {mapa['consultas']['novos']} consulta(s) nova(s), "
                  f"{mapa['consultas']['atualizados']} atualizada(s); "
                  f"{mapa['regimes']['novos']} regime(s) novo(s), "
                  f"{mapa['regimes']['atualizados']} atualizado(s)."
              )

              if resultado["descartes"]:
                  with st.expander(f"Ver {len(resultado['descartes'])} descartes"):
                      st.dataframe(resultado["descartes"], width="stretch", hide_index=True)

              st.download_button(
                  "⬇️ Baixar planilha desta sessão (.xlsx)", resultado["xlsx"],
                  file_name="mapeamento.xlsx",
                  mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                  on_click="ignore",
              )
      else:
          st.info("Envie um ou mais PDFs e clique em **Processar**.")

with aba_consultar:
    conn = _conexao()

    # Painel de busca no estilo da tela de referência (busca de normas):
    # os mesmos 3 filtros de sempre (tipo/texto/ano), só reorganizados lado
    # a lado num card com rótulos em destaque — nenhum campo novo, nenhuma
    # mudança na lógica de core.consulta.buscar().
    with st.container(border=True, key="painel-busca"):
        col_tipo, col_texto, col_ano = st.columns(3)
        with col_tipo:
            tipo = st.selectbox("Tipo de ato", ["consulta", "regime"])
        with col_texto:
            texto = st.text_input("Busca textual")
        with col_ano:
            anos = consulta.anos_disponiveis(conn, tipo)
            ano = st.selectbox("Ano do ato", ["Todos"] + anos)

    resultados = consulta.buscar(conn, tipo, texto=texto or None,
                                 ano=None if ano == "Todos" else ano)

    with st.container(border=True, key="card-consultar"):
        st.markdown('<div class="icms-resultado-barra">RESULTADO DA PESQUISA</div>',
                    unsafe_allow_html=True)
        st.markdown(
            f'<div class="icms-total-atos">Total de atos localizados: {len(resultados)}</div>',
            unsafe_allow_html=True,
        )
        st.caption("Selecione uma linha para ver a consulta/regime por inteiro.")
        st.dataframe(resultados, width="stretch", hide_index=True,
                     on_select="rerun", selection_mode="single-row",
                     key="tabela-resultados")

        linhas_selecionadas = st.session_state["tabela-resultados"]["selection"]["rows"]
        if linhas_selecionadas:
            cols_do_tipo = planilha.COLS_CONSULTAS if tipo == "consulta" else planilha.COLS_REGIMES
            _mostra_detalhe(tipo, resultados[linhas_selecionadas[0]], cols_do_tipo)

        if resultados:
            st.download_button(
                "⬇️ Baixar estes resultados (.xlsx)",
                consulta.exportar_xlsx(tipo, resultados),
                file_name=f"{tipo}s_filtrados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click="ignore",
            )
