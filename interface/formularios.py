# interface/formularios.py
"""Formulário de edição de um ato (consulta ou regime), usado no detalhe e na análise.

Um campo por coluna: caixa de texto para os curtos e área de texto para os longos.
O formulário só DEVOLVE o que foi digitado; quem chama grava (edicao.editar_registro
ou edicao.ajustar_no_lote) e decide o que fazer com os erros de regra."""
import streamlit as st

# colunas que costumam ter texto corrido
CAMPOS_LONGOS = {
    'Súmula', 'Problema da Consulta', 'Resposta',
    'EMENTA', 'ABRANGÊNCIA', 'BENEFÍCIOS/PROCEDIMENTOS', 'DISPOSIÇÕES GERAIS',
}
_LIMITE_CAMPO_CURTO = 80   # valor maior que isso também vira área de texto


def prefixo_de(tipo: str, valores_chave) -> str:
    """Prefixo único (por ato) das chaves dos widgets do formulário, para o Streamlit
    não reaproveitar o texto digitado de um ato em outro."""
    return "|".join(["edit", tipo, *(str(v) for v in valores_chave)])


def campo_longo(campo: str, valor: str) -> bool:
    return campo in CAMPOS_LONGOS or len(valor) > _LIMITE_CAMPO_CURTO


def altura_da_area(valor: str) -> int:
    """Altura (px) da área de texto: cresce com o texto, entre 110 e 360."""
    linhas = valor.count("\n") + len(valor) // 90 + 1
    return max(110, min(360, 24 * linhas + 40))


def campos_alterados(original: dict, novos: dict) -> list:
    """Campos de `novos` cujo valor (sem espaços nas pontas) difere do original."""
    return [c for c, v in novos.items()
            if str(original.get(c) or '') != ('' if v is None else str(v)).strip()]


def formulario_registro(tipo: str, registro: dict, colunas: list, chave: list, *,
                        prefixo: str, rotulo_envio: str = "Salvar alterações",
                        ao_enviar=None, args=()):
    """Mostra o formulário. Dois modos de receber o que foi digitado:

    - sem `ao_enviar`: devolve {coluna: texto} quando o administrador envia, ou None
      enquanto não enviou;
    - com `ao_enviar`: o Streamlit chama `ao_enviar(*args)` ANTES de rodar o script de
      novo (use para gravar e para mexer no estado de outros widgets, o que não é
      permitido depois que eles foram desenhados); o texto digitado fica em
      st.session_state[f"{prefixo}|{coluna}"]. Nesse modo a função devolve None.

    Enter não envia (há áreas de texto)."""
    with st.form(f"form|{prefixo}", border=False, enter_to_submit=False):
        novos = {}
        for campo in colunas:
            valor = str(registro.get(campo) or '')
            rotulo = f"{campo} (chave)" if campo in chave else campo
            ajuda = ("Identifica o ato. Corrigir a chave não duplica o ato: reimportar o PDF "
                     "original continua caindo neste registro.") if campo in chave else None
            if campo_longo(campo, valor):
                novos[campo] = st.text_area(rotulo, value=valor, key=f"{prefixo}|{campo}",
                                            height=altura_da_area(valor), help=ajuda)
            else:
                novos[campo] = st.text_input(rotulo, value=valor, key=f"{prefixo}|{campo}",
                                             help=ajuda)
        enviado = st.form_submit_button(rotulo_envio, key=f"{prefixo}|enviar", type="primary",
                                        icon=":material/save:", on_click=ao_enviar, args=args)
    return novos if (enviado and ao_enviar is None) else None
