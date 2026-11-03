# app.py
import html
import io
import os
import re
import tempfile
from datetime import datetime

from core.bootstrap import DEPS_APP, garantir_dependencias

# antes de importar streamlit/pdfplumber/openpyxl, que vêm logo abaixo.
# Para o primeiro arranque, quando nem o streamlit existe, use `python iniciar.py`.
garantir_dependencias(DEPS_APP)

import streamlit as st  # noqa: E402

from core import (acesso, armazenamento, cnpj, consulta, diagnostico, edicao,  # noqa: E402
                  log, planilha)
from core.execucao import Execucao  # noqa: E402
from core.pdf_text import MARCA_CITACAO  # noqa: E402
from interface import design, formularios  # noqa: E402

log.configurar_log(armazenamento.pasta_dados())

_FORCAR = {"Detectar automaticamente": None,
           "Forçar Consulta": "consulta",
           "Forçar Regime": "regime"}
_CRITERIOS = {"Primeira ocorrência": "primeira",
              "Mais completo": "completo",
              "Mais recente": "recente"}
_PERFIS = {acesso.PERFIL_ADMIN: "Administrador",
           acesso.PERFIL_CONSULTA: "Consulta"}

# MAPEADOR_BANCO permite apontar para um banco de teste/alternativo; sem a
# variável, cai no padrão de armazenamento.conectar() (mapeamento.db na raiz
# do projeto).
_CAMINHO_BANCO = os.environ.get("MAPEADOR_BANCO") or None

# Visual: Design System Martinelli (interface/design.py + .streamlit/config.toml).
st.set_page_config(page_title="Mapeador Tributário PR", page_icon="⚖️",
                   layout="wide")
design.injetar_tema()

def _persistir(lote, sobrescrever=()):
    """Grava o lote no banco e devolve o resumo de novos/atualizados."""
    with armazenamento.sessao(_CAMINHO_BANCO) as conn:
        return armazenamento.persistir_lote(conn, lote, sobrescrever)


def _data_br(iso) -> str:
    """'2026-11-02T21:34:00+00:00' -> '02/11/2026' (data local); sem dado, '—'."""
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y")
    except ValueError:
        return "—"


def _atos(n: int) -> str:
    return f"{n} ato localizado" if n == 1 else f"{n} atos localizados"


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
    st.session_state.pop("editando", None)


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


def _comecar_edicao(prefixo: str):
    st.session_state["editando"] = prefixo


def _cancelar_edicao():
    st.session_state.pop("editando", None)
    st.session_state.pop("erro_edicao", None)


def _avisar(r: dict, o_que: str):
    """Mensagem do resultado de uma edição (vira toast depois do st.rerun)."""
    if not r["alterados"]:
        st.session_state["aviso"] = "Nenhum campo foi alterado."
        return
    st.session_state["aviso"] = (f"{o_que}: {len(r['alterados'])} campo(s) alterado(s)."
                                 + (" A chave foi corrigida." if r["chave_trocada"] else ""))


def _salvar_edicao(tipo: str, registro: dict, colunas: list, prefixo: str):
    """on_click do formulário do detalhe: roda ANTES do script, por isso pode zerar a
    seleção da tabela (o que não se pode fazer depois que ela foi desenhada). Grava a
    edição (só administrador); em erro de regra guarda a mensagem para o detalhe mostrar
    e mantém o formulário aberto; com sucesso o detalhe fecha."""
    acesso.exige_admin(st.session_state.get("perfil"))
    novos = {c: st.session_state.get(f"{prefixo}|{c}", "") for c in colunas}
    chave_atual = {c: registro[c] for c in edicao.TIPOS[tipo][2]}
    try:
        with armazenamento.sessao(_CAMINHO_BANCO) as conn:
            r = edicao.editar_registro(conn, tipo, chave_atual, novos)
    except (edicao.ChaveEmConflito, edicao.ChaveVazia, edicao.RegistroInexistente) as erro:
        st.session_state["erro_edicao"] = str(erro)
        return
    st.session_state.pop("erro_edicao", None)
    _avisar(r, "Ato atualizado")
    _fecha_selecao_da_tabela()


def _avisar_receita(resumo):
    """Deixa para o toast o resultado da consulta de CNPJs feita ao gravar."""
    mensagem = cnpj.mensagem_do_resumo(resumo)
    if mensagem:
        st.session_state["aviso"] = f"Receita Federal: {mensagem}"


def _consultar_cnpj(cnpj_do_regime: str):
    """Consulta (ou refaz a consulta de) um CNPJ pelo detalhe do regime. Roda no
    on_click do botão: o toast sai na reexecução seguinte e o detalhe continua aberto."""
    acesso.exige_admin(st.session_state.get("perfil"))
    with armazenamento.sessao(_CAMINHO_BANCO) as conn:
        resumo = cnpj.atualizar(conn, [cnpj_do_regime], forcar=True)
    if resumo["consultados"]:
        st.session_state["aviso"] = "Receita Federal: CNPJ consultado."
    elif resumo["falhas"]:
        st.session_state["aviso"] = f"Receita Federal: {resumo['falhas'][0][1]}."
    else:
        st.session_state["aviso"] = "Receita Federal: CNPJ em branco ou inválido, nada a consultar."


def _aplicar_cnae(registro: dict, receita: dict):
    """Grava no regime o CNAE da Receita (vira ajuste manual, com histórico)."""
    acesso.exige_admin(st.session_state.get("perfil"))
    chave_atual = {c: registro[c] for c in edicao.TIPOS["regime"][2]}
    novos = {"CNAE REQUERENTE": cnpj.formatar_cnae(receita["cnae_codigo"]),
             "DESCRIÇÃO CNAE": receita["cnae_descricao"]}
    try:
        with armazenamento.sessao(_CAMINHO_BANCO) as conn:
            r = edicao.editar_registro(conn, "regime", chave_atual, novos)
    except edicao.RegistroInexistente as erro:
        st.session_state["aviso"] = str(erro)
        return
    _avisar(r, "CNAE aplicado")
    _fecha_selecao_da_tabela()


def _bloco_receita(registro: dict, receita, pode_editar: bool):
    """CNAE e situação do CNPJ na Receita Federal (BrasilAPI), guardados à parte do regime."""
    st.markdown('<div class="icms-campo-detalhe-rotulo">Receita Federal (BrasilAPI)</div>',
                unsafe_allow_html=True)
    if not receita:
        st.caption("CNPJ ainda não consultado.")
    else:
        st.write(f"CNAE principal: {cnpj.formatar_cnae(receita['cnae_codigo'])}"
                 f" — {receita['cnae_descricao']}")
        st.write(f"Situação cadastral: {receita['situacao'] or '—'}")
        st.caption(f"Consultado em {_data_br(receita['consultado_em'])}. É o CNAE atual da "
                   "empresa, que pode diferir do vigente na data do regime.")
        divergente = cnpj.divergencia(registro, receita)
        if divergente:
            st.warning(f"O CNAE informado no regime ({divergente['regime']}) difere do "
                       f"da Receita ({divergente['receita']}).")
    if not pode_editar:
        return
    st.button("Atualizar consulta" if receita else "Consultar CNPJ", key="consultar-cnpj",
              icon=":material/search:", on_click=_consultar_cnpj,
              args=(registro.get("CNPJ REQUERENTE", ""),))
    if (receita and receita["cnae_codigo"]
            and cnpj.so_digitos(registro.get("CNAE REQUERENTE")) != receita["cnae_codigo"]):
        st.button("Aplicar CNAE da Receita ao regime", key="aplicar-cnae",
                  icon=":material/check:", on_click=_aplicar_cnae, args=(registro, receita))


@st.dialog("Detalhes", width="large", on_dismiss=_fecha_selecao_da_tabela)
def _mostra_detalhe(tipo: str, registro: dict, colunas: list, historico=(),
                    pode_editar: bool = False, ajustes=(), receita=None):
    st.subheader(_titulo_do_registro(tipo, registro))
    chave = edicao.TIPOS[tipo][2]
    prefixo = formularios.prefixo_de(tipo, [registro[c] for c in chave])

    if pode_editar and st.session_state.get("editando") == prefixo:
        st.caption("Edite os campos e salve. Cada alteração fica no histórico do ato.")
        erro = st.session_state.pop("erro_edicao", None)
        if erro:
            st.error(erro)
        formularios.formulario_registro(tipo, registro, colunas, chave, prefixo=prefixo,
                                        ao_enviar=_salvar_edicao,
                                        args=(tipo, registro, colunas, prefixo))
        st.button("Cancelar", key="cancelar-edicao", type="tertiary",
                  icon=":material/close:", on_click=_cancelar_edicao)
        return

    if ajustes:
        st.caption("Ajustado manualmente: " + ", ".join(ajustes))
    for campo in colunas:
        valor = registro.get(campo, "")
        if not valor:
            continue
        st.markdown(f'<div class="icms-campo-detalhe-rotulo">{html.escape(campo)}</div>',
                    unsafe_allow_html=True)
        if tipo == "regime":
            st.markdown(_com_quebras_por_topico(valor))
        elif tipo == "consulta" and campo == "Resposta":
            st.markdown(_resposta_em_paragrafos(valor), unsafe_allow_html=True)
        else:
            st.write(valor)
    if tipo == "regime":
        _bloco_receita(registro, receita, pode_editar)
    if pode_editar:
        st.button("Editar", key="editar-registro", icon=":material/edit:",
                  on_click=_comecar_edicao, args=(prefixo,))
    if historico:
        with st.expander(f"Histórico de alterações ({len(historico)})"):
            for h in historico:
                quem = "ajuste manual" if h.get("origem") == "manual" else "importação"
                st.markdown(f"**{h['alterado_em']}** · {quem} (versão {h['versao_app']}) — "
                            f"campos alterados: {', '.join(h['campos_alterados'])}")


def _conflitos_com_o_banco(lote) -> list:
    """Atos desta análise que já têm ajuste manual no banco e divergem do PDF."""
    with armazenamento.sessao(_CAMINHO_BANCO) as conn:
        return edicao.ajustes_em_conflito(conn, lote)


def _reanalisar(analise):
    """Refaz o diagnóstico e os conflitos depois de uma edição na análise."""
    analise["diagnostico"] = diagnostico.diagnosticar(analise["lote"])
    analise["conflitos"] = _conflitos_com_o_banco(analise["lote"])


def _analisar(enviados, forcar, criterio):
    """Lê os PDFs e diagnostica, SEM gravar. Devolve o que a sessão guarda
    até o usuário decidir gravar."""
    acesso.exige_admin(st.session_state.get("perfil"))
    barra = st.progress(0.0, text="Lendo os PDFs...")

    def progresso(fase, atual, total, texto):
        barra.progress(atual / (total or 1),
                       text=f"Lendo: {texto}" if texto else "Lendo os PDFs...")

    temporarios = []
    try:
        pares = []
        for arq in sorted(enviados, key=lambda a: a.name):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                temporarios.append(tmp.name)
                tmp.write(arq.getbuffer())
            pares.append((tmp.name, arq.name))
        execucao = Execucao(progresso=progresso, dedup=criterio)
        lote = execucao.carregar(pares, forcar=forcar)
    finally:
        for caminho in temporarios:
            os.unlink(caminho)
        barra.empty()
    return {"lote": lote, "diagnostico": execucao.diagnostico,
            "conflitos": _conflitos_com_o_banco(lote)}


def _chave_da_caixa(item: dict) -> str:
    return "sobrescrever|" + "|".join(str(v) for v in edicao.chave_do_item(item))


def _sobrescrever_marcados(analise) -> list:
    """Atos com ajuste manual cujo PDF o administrador mandou sobrescrever."""
    return [edicao.chave_do_item(i) for i in analise.get("conflitos", [])
            if st.session_state.get(_chave_da_caixa(i))]


def _gravar(analise, sobrescrever=()):
    """Persiste o lote analisado e devolve o resultado a guardar na sessão
    (mesmas chaves de sempre)."""
    acesso.exige_admin(st.session_state.get("perfil"))
    lote = analise["lote"]
    mapeamento = _persistir(lote, sobrescrever)
    if cnpj.habilitada():
        with st.spinner("Consultando os CNPJs na Receita Federal…"):
            with armazenamento.sessao(_CAMINHO_BANCO) as conn:
                _avisar_receita(cnpj.atualizar_do_lote(conn, lote))

    # planilha em memória, exportação opcional: nada de cópia em disco
    buf = io.BytesIO()
    planilha.gerar_xlsx(buf, lote.consultas, lote.regimes, lote.descartes,
                        lote.arquivos)
    return {"arquivos": lote.arquivos, "consultas": lote.consultas,
            "regimes": lote.regimes, "descartes": lote.descartes,
            "mapeamento": mapeamento, "xlsx": buf.getvalue()}


def _atos_da_analise(lote) -> list:
    """[(rótulo, tipo, chave_dict)] de todos os atos da análise (mesmos rótulos do diagnóstico)."""
    atos = []
    for tipo, registros in (("consulta", lote.consultas), ("regime", lote.regimes)):
        chave = edicao.TIPOS[tipo][2]
        for reg in registros:
            chave_dict = {c: reg.get(c, "") for c in chave}
            rotulo = edicao.rotulo_do_ato(tipo, chave_dict)
            if tipo == "regime" and reg.get("EMPRESA"):
                rotulo += f" — {reg['EMPRESA']}"
            atos.append((rotulo, tipo, chave_dict))
    return atos


def _editor_da_analise(analise):
    """Corrige um ato ANTES de gravar (nada vai ao banco ainda)."""
    lote = analise["lote"]
    atos = _atos_da_analise(lote)
    if not atos:
        return
    with st.expander("Ajustar um ato antes de gravar"):
        st.caption("Escolha o ato apontado nos avisos, corrija os campos e salve. "
                   "O diagnóstico é refeito na hora; a gravação continua sendo um passo à parte.")
        i = st.selectbox("Ato", range(len(atos)), format_func=lambda n: atos[n][0],
                         key="ajuste-escolha")
        _, tipo, chave_atual = atos[i]
        _, colunas, chave = edicao.TIPOS[tipo]
        registro = next(r for r in (lote.consultas if tipo == "consulta" else lote.regimes)
                        if all(str(r.get(c, "")) == str(chave_atual[c]) for c in chave))
        novos = formularios.formulario_registro(
            tipo, registro, colunas, chave,
            prefixo=formularios.prefixo_de(tipo, [chave_atual[c] for c in chave],
                                           contexto="analise"),
            rotulo_envio="Salvar ajuste")
        if novos is not None:
            try:
                with armazenamento.sessao(_CAMINHO_BANCO) as conn:
                    r = edicao.ajustar_no_lote(lote, tipo, chave_atual, novos, conn=conn)
            except (edicao.ChaveEmConflito, edicao.ChaveJaGravada, edicao.ChaveVazia,
                    edicao.RegistroInexistente) as erro:
                st.error(str(erro))
            else:
                _reanalisar(analise)
                _avisar(r, "Ajuste feito na análise")
                st.rerun()


def _escolha_de_conflitos(analise):
    """Atos que já têm ajuste manual no banco: por padrão o ajuste é mantido."""
    conflitos = analise.get("conflitos") or []
    if not conflitos:
        return
    st.warning(f"{len(conflitos)} ato(s) já têm ajuste manual e o PDF traz outro valor. "
               "Por padrão o valor ajustado é mantido; marque para gravar o valor do PDF.")
    for item in conflitos:
        with st.container(border=True):
            st.checkbox(f"Sobrescrever com o PDF — {item['rotulo']}", key=_chave_da_caixa(item))
            st.dataframe(
                [{"Campo": c["campo"], "Valor ajustado": c["atual"], "Valor do PDF": c["pdf"]}
                 for c in item["campos"]], width="stretch", hide_index=True)


def _mostra_analise(analise):
    lote, diag = analise["lote"], analise["diagnostico"]
    with st.container(border=True, key="card-analise"):
        st.subheader("Análise dos arquivos (nada foi gravado ainda)")
        st.dataframe(lote.arquivos, width="stretch", hide_index=True)
        for linha in lote.arquivos:
            if linha["Tipo"] == "erro":
                st.error(f"**{linha['Arquivo']}** não pôde ser lido: {linha['Erro']}")
        c1, c2 = st.columns(2)
        with c1, st.container(key="kpi-consultas-analise"):
            st.metric("Consultas", len(lote.consultas))
        with c2, st.container(key="kpi-regimes-analise"):
            st.metric("Regimes", len(lote.regimes))
        for m in diag["mensagens"]:
            if m["codigo"] == "E001":
                continue  # o erro do arquivo já foi mostrado acima, com o motivo
            aviso = f"**{m['codigo']} — {m['titulo']}.** {m['texto']}"
            (st.warning if m["nivel"] == "aviso" else st.error)(aviso)
        if not diag["pode_continuar"]:
            st.info("Não há nenhum registro para gravar.")
        _editor_da_analise(analise)
        _escolha_de_conflitos(analise)


def _mostra_resumo(resultado):
    """Resultado da última gravação: indicadores, avisos por arquivo e planilha."""
    with st.container(border=True, key="card-resumo"):
        st.subheader("Resumo do processamento")
        st.dataframe(resultado["arquivos"], width="stretch", hide_index=True)
        erros = [a for a in resultado["arquivos"] if a["Tipo"] == "erro"]
        for e in erros:
            st.error(f"**{e['Arquivo']}** não pôde ser lido: {e['Erro']}")

        n_descartes = len(resultado["descartes"])
        c1, c2, c3 = st.columns(3)
        with c1, st.container(key="kpi-consultas-resumo"):
            st.metric("Consultas", len(resultado["consultas"]))
        with c2, st.container(key="kpi-regimes-resumo"):
            st.metric("Regimes", len(resultado["regimes"]))
        # o vermelho só aparece quando há descartes: a cor sinaliza pendência
        with c3, st.container(key=("kpi-descartes-alerta-resumo" if n_descartes
                                   else "kpi-descartes-resumo")):
            st.metric("Descartes registrados", n_descartes)

        mapa = resultado["mapeamento"]
        st.success(
            f"Gravado: {mapa['consultas']['novos']} consulta(s) nova(s), "
            f"{mapa['consultas']['atualizados']} atualizada(s); "
            f"{mapa['regimes']['novos']} regime(s) novo(s), "
            f"{mapa['regimes']['atualizados']} atualizado(s)."
        )

        if resultado["descartes"]:
            with st.expander(f"Ver {n_descartes} descartes"):
                st.dataframe(resultado["descartes"], width="stretch", hide_index=True)

        st.download_button(
            "Baixar planilha desta sessão (.xlsx)", resultado["xlsx"],
            file_name="mapeamento.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            on_click="ignore", icon=":material/download:",
        )


def _entrar_como(perfil_escolhido: str):
    st.session_state["perfil"] = perfil_escolhido
    st.session_state.pop("login_etapa", None)
    st.rerun()


def _login_escolha(senha_configurada: bool):
    """Etapa 1: escolher o perfil. Consulta entra direto; Administrador segue
    para a etapa da senha (e fica desabilitado se a senha não estiver
    configurada — nunca cai em acesso aberto)."""
    design.cabecalho_login("Mapeador Tributário PR", "Como deseja entrar?",
                           "Escolha o perfil para continuar.")
    if st.button("Consulta", key="entrar-consulta", type="primary",
                 icon=":material/search:", width="stretch"):
        _entrar_como(acesso.PERFIL_CONSULTA)
    design.nota_de_opcao("Pesquisar os atos já mapeados. Sem senha.")

    if st.button("Administrador", key="entrar-admin", icon=":material/lock:",
                 disabled=not senha_configurada, width="stretch"):
        st.session_state["login_etapa"] = "senha"
        st.rerun()
    design.nota_de_opcao("Importar PDFs e gerenciar o banco. Exige senha.")
    if not senha_configurada:
        st.warning("Senha do administrador não configurada. Crie "
                   ".streamlit/secrets.toml com a seção [admin] e a chave senha (veja o README).")


def _login_senha(esperada: str):
    """Etapa 2: senha do administrador (Enter também confirma)."""
    design.cabecalho_login("Administrador", "Digite a senha",
                           "Acesso para importar PDFs e gerenciar o banco.")
    with st.form("form-login", border=False):
        senha = st.text_input("Senha", type="password", key="senha-admin",
                              placeholder="Senha do administrador")
        confirmou = st.form_submit_button("Entrar", key="confirmar-admin",
                                          type="primary", icon=":material/login:",
                                          width="stretch")
    if confirmou:
        if acesso.confere(senha, esperada):
            _entrar_como(acesso.PERFIL_ADMIN)
        st.error("Senha incorreta.")
    if st.button("Voltar", key="voltar-login", type="tertiary",
                 icon=":material/arrow_back:", width="stretch"):
        st.session_state.pop("login_etapa", None)
        st.rerun()


def _tela_login():
    """Login centralizado na tela, em duas etapas: escolha do perfil e, para o
    Administrador, a senha de .streamlit/secrets.toml."""
    esperada = acesso.senha_admin(st.secrets)
    with st.container(border=True, key="card-login"):
        if st.session_state.get("login_etapa") == "senha" and esperada is not None:
            _login_senha(esperada)
        else:
            st.session_state.pop("login_etapa", None)
            _login_escolha(esperada is not None)


perfil = st.session_state.get("perfil")
if perfil not in (acesso.PERFIL_CONSULTA, acesso.PERFIL_ADMIN):
    _tela_login()
    st.stop()

with st.sidebar:
    design.marca_lateral("Mapeador Tributário PR")

try:
    with armazenamento.sessao(_CAMINHO_BANCO):
        pass
except armazenamento.SchemaMaisNovo as erro:
    st.error(str(erro))
    st.stop()

_aviso = st.session_state.pop("aviso", None)   # mensagem deixada antes de um st.rerun()
if _aviso:
    st.toast(_aviso, icon=":material/check_circle:")

if perfil == acesso.PERFIL_ADMIN:
    aba_processar, aba_consultar = st.tabs(
        [":material/upload: Processar e mapear", ":material/search: Consultar"])
else:
    aba_processar = None
    (aba_consultar,) = st.tabs([":material/search: Consultar"])

if aba_processar is not None:
    with aba_processar:
        design.cabecalho_pagina(
            "Importação", "Processar e mapear",
            "Envie os PDFs, confira a análise e grave no banco.")

        with st.sidebar:
            design.secao_lateral("Como funciona")
            st.markdown(
                "1. Envie os PDFs (consultas SEFA e/ou páginas do Diário).\n"
                "2. A ferramenta detecta o tipo, extrai os campos e mostra uma "
                "análise para você conferir; só então grava no banco local.\n"
                "3. Use a aba **Consultar** para buscar o que já foi mapeado, "
                "ou baixe a planilha desta sessão se quiser.\n\n"
                "Reprocessar o mesmo PDF atualiza o que já estava mapeado, "
                "sem duplicar."
            )
            design.secao_lateral("Tipo do PDF")
            escolha = st.radio(
                "Tipo do PDF", list(_FORCAR), label_visibility="collapsed",
                help="Use ‘forçar’ se a detecção automática errar.",
            )

        with st.container(border=True, key="card-envio"):
            design.titulo_cartao("Arquivos", "PDFs da SEFA-PR e do Diário Oficial")
            arquivos = st.file_uploader("Arraste os PDFs aqui", type=["pdf"],
                                        accept_multiple_files=True)
            criterio = st.selectbox(
                "Se o mesmo ato aparecer em mais de um arquivo", list(_CRITERIOS),
                help="Primeira ocorrência: a do primeiro arquivo (ordem alfabética). "
                     "Mais completo: o registro com mais campos preenchidos. "
                     "Mais recente: o de maior data de publicação.",
            )
            clicou_analisar = st.button("Analisar", type="primary", key="analisar",
                                        icon=":material/search:",
                                        disabled=not arquivos)

        if arquivos and clicou_analisar:
            st.session_state.pop("resultado", None)
            st.session_state["analise"] = _analisar(arquivos, _FORCAR[escolha],
                                                    _CRITERIOS[criterio])
            st.session_state["analise"]["nomes"] = tuple(a.name for a in arquivos)

        # Exibidos a partir da sessão, e não de dentro do `if st.button`: assim a
        # análise/o resultado continuam na tela depois de qualquer reexecução do
        # script (por exemplo, o clique em "Baixar").
        analise = st.session_state.get("analise")
        if analise and "nomes" in analise and (
                tuple(a.name for a in arquivos) != analise["nomes"]):
            st.session_state.pop("analise", None)
            analise = None
        resultado = st.session_state.get("resultado")
        if analise:
            _mostra_analise(analise)
            if st.button("Gravar no banco", type="primary", key="gravar",
                         icon=":material/save:",
                         disabled=not analise["diagnostico"]["pode_continuar"]):
                st.session_state["resultado"] = _gravar(analise, _sobrescrever_marcados(analise))
                st.session_state.pop("analise", None)
                st.rerun()
        elif resultado:
            _mostra_resumo(resultado)
        else:
            st.info("Envie um ou mais PDFs e clique em **Analisar**.")


def _renderiza_consultar(conn):
    design.cabecalho_pagina(
        "Base de atos", "Consultar",
        "Pesquise as consultas e os regimes especiais já mapeados.")

    resumo = consulta.resumo_do_banco(conn)
    anos = resumo["anos"]
    faixa_de_anos = (anos[0] if len(anos) == 1 else f"{anos[0]}–{anos[-1]}") if anos else "—"
    k1, k2, k3, k4 = st.columns(4)
    with k1, st.container(key="kpi-consultas-base"):
        st.metric("Consultas mapeadas", resumo["consultas"])
    with k2, st.container(key="kpi-regimes-base"):
        st.metric("Regimes mapeados", resumo["regimes"])
    with k3, st.container(key="kpi-anos-base"):
        st.metric("Anos cobertos", faixa_de_anos)
    with k4, st.container(key="kpi-importacao-base"):
        st.metric("Última importação", _data_br(resumo["ultima_importacao"]))

    # Os 3 filtros de sempre (tipo/texto/ano), lado a lado num cartão.
    with st.container(border=True, key="painel-busca"):
        col_tipo, col_texto, col_ano = st.columns(3)
        with col_tipo:
            tipo = st.selectbox("Tipo de ato", ["consulta", "regime"])
        with col_texto:
            texto = st.text_input("Busca textual")
        with col_ano:
            anos_do_tipo = consulta.anos_disponiveis(conn, tipo)
            ano = st.selectbox("Ano do ato", ["Todos"] + anos_do_tipo)

    ano_filtro = None if ano == "Todos" else ano
    resultados = consulta.buscar_lista(conn, tipo, texto=texto or None, ano=ano_filtro)

    with st.container(border=True, key="card-consultar"):
        design.titulo_cartao("Resultados", _atos(len(resultados)))
        if not resultados:
            if texto or ano_filtro:
                design.estado_vazio("search", "Nenhum ato com esses filtros",
                                    "Ajuste a busca ou limpe os filtros para ver todos os atos.")
            else:
                design.estado_vazio("folder", "Ainda não há atos mapeados",
                                    "Peça a um administrador para importar os PDFs.")
            return

        st.caption("Selecione uma linha para abrir o detalhe completo.")
        st.dataframe(resultados, width="stretch", hide_index=True,
                     on_select="rerun", selection_mode="single-row",
                     key="tabela-resultados")

        linhas_selecionadas = st.session_state["tabela-resultados"]["selection"]["rows"]
        if linhas_selecionadas:
            cols_do_tipo = planilha.COLS_CONSULTAS if tipo == "consulta" else planilha.COLS_REGIMES
            completo = consulta.detalhe(conn, tipo, resultados[linhas_selecionadas[0]])
            if completo is not None:
                _mostra_detalhe(tipo, completo, cols_do_tipo,
                                consulta.historico(conn, tipo, completo),
                                pode_editar=(perfil == acesso.PERFIL_ADMIN),
                                ajustes=consulta.ajustes(conn, tipo, completo),
                                receita=(consulta.receita(conn, completo)
                                         if tipo == "regime" else None))

        st.download_button(
            "Baixar estes resultados (.xlsx)",
            lambda: consulta.exportar_busca(tipo, texto or None, ano_filtro,
                                            _CAMINHO_BANCO),
            file_name=f"{tipo}s_filtrados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            on_click="ignore", icon=":material/download:",
        )


with aba_consultar:
    with armazenamento.sessao(_CAMINHO_BANCO) as conn:
        _renderiza_consultar(conn)

# No fim do script, para ficar embaixo do conteúdo da barra lateral.
with st.sidebar:
    design.perfil_lateral(_PERFIS[perfil], "Perfil atual")
    if st.button("Trocar perfil", key="trocar-perfil",
                 icon=":material/swap_horiz:", width="stretch"):
        for chave in ("perfil", "resultado", "analise", "login_etapa"):
            st.session_state.pop(chave, None)
        st.rerun()
