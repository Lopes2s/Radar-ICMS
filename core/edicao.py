# core/edicao.py
"""Edição manual de consultas e regimes pelo administrador.

Dois momentos:
- ato já gravado: `editar_registro` (grava na hora, com histórico 'manual');
- ato ainda na análise: `ajustar_no_lote` (só altera o Lote em memória; o que o
  administrador ajustou vira `ajustes`/apelidos de chave quando o lote é gravado).

Tudo que o administrador ajusta à mão fica marcado em `ajustes`: a reimportação
do PDF não sobrescreve esses campos, a menos que o administrador confirme
(ver `ajustes_em_conflito` e o parâmetro `sobrescrever` de persistir_lote).
Corrigir a CHAVE de um ato também é permitido; a chave antiga vira apelido
(`chaves_substituidas`) para o PDF original continuar caindo no mesmo ato.

Sem Streamlit: quem chama (app.py) cuida do perfil (`acesso.exige_admin`).
"""
from core import armazenamento, pipeline

TIPOS = {
    'consulta': ('consultas', armazenamento.COLUNAS_CONSULTAS, pipeline.CHAVE_CONSULTAS),
    'regime': ('regimes', armazenamento.COLUNAS_REGIMES, pipeline.CHAVE_REGIMES),
}


class RegistroInexistente(LookupError):
    """Não há ato com a chave informada."""


class ChaveEmConflito(ValueError):
    """A chave nova já pertence a outro ato."""


class ChaveVazia(ValueError):
    """Nenhum campo da chave pode ficar em branco."""


def _tipo(tipo: str):
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de {tuple(TIPOS)}: {tipo!r}")
    return TIPOS[tipo]


def _limpo(valor) -> str:
    return '' if valor is None else str(valor).strip()


def _texto(valor) -> str:
    return '' if valor is None else str(valor)


def _validar(colunas, novos):
    desconhecidos = sorted(set(novos) - set(colunas))
    if desconhecidos:
        raise ValueError(f"campo(s) inexistente(s): {desconhecidos}")


def editar_registro(conn, tipo: str, chave_atual: dict, novos: dict) -> dict:
    """Edita um ato JÁ GRAVADO. `novos` traz só os campos (ou todos) a alterar,
    inclusive a chave. Devolve {'alterados': [campos], 'chave_trocada': bool}.

    Tudo ou nada: se algo falhar no meio, nada é gravado. Cada edição guarda a
    versão anterior em `historico` (origem 'manual') e marca os campos editados em
    `ajustes`. Levanta RegistroInexistente, ChaveVazia ou ChaveEmConflito."""
    tabela, colunas, chave = _tipo(tipo)
    _validar(colunas, novos)
    atual = armazenamento.buscar_detalhe(conn, tabela, chave, chave_atual)
    if atual is None:
        raise RegistroInexistente(f"Não há ato com a chave {chave_atual!r}.")
    final = {c: (_limpo(novos[c]) if c in novos else _texto(atual.get(c))) for c in colunas}
    alterados = [c for c in colunas if _texto(atual.get(c)) != final[c]]
    if not alterados:
        return {'alterados': [], 'chave_trocada': False}

    antiga = tuple(_texto(atual[c]) for c in chave)
    nova = tuple(final[c] for c in chave)
    if not all(nova):
        raise ChaveVazia("O número e os demais campos da chave não podem ficar em branco.")
    trocada = nova != antiga
    if trocada and armazenamento.buscar_detalhe(
            conn, tabela, chave, dict(zip(chave, nova))) is not None:
        raise ChaveEmConflito(
            "Já existe outro ato com essa chave. Corrija a chave para um valor livre "
            "ou edite o ato existente.")
    try:
        armazenamento.registrar_alteracao(conn, tabela, chave, antiga, atual, alterados,
                                          origem='manual')
        sets = ', '.join(f'"{c}" = ?' for c in alterados)
        onde = ' AND '.join(f'"{c}" = ?' for c in chave)
        conn.execute(f'UPDATE {tabela} SET {sets} WHERE {onde}',
                     [final[c] for c in alterados] + list(antiga))
        armazenamento.juntar_ajustes(conn, tabela, chave, antiga,
                                     [c for c in alterados if c not in chave])
        if trocada:
            armazenamento.mover_chave_auxiliares(conn, tabela, chave, antiga, nova)
            armazenamento.registrar_substituicao(conn, tabela, chave, antiga, nova)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {'alterados': alterados, 'chave_trocada': trocada}


def rotulo_do_ato(tipo: str, chave_dict: dict) -> str:
    """'Consulta 001/2026' ou 'RE 9.053/2026' (mesmos rótulos do diagnóstico)."""
    if tipo == 'consulta':
        return f"Consulta {chave_dict.get('Nº da Consulta', '')}/{chave_dict.get('Ano', '')}"
    return f"RE {chave_dict.get('Nº DO REGIME ESPECIAL', '')}"


def chave_do_item(item: dict) -> tuple:
    """('consulta'|'regime', *valores) de um item de `ajustes_em_conflito`; é o formato
    que `persistir_lote(..., sobrescrever=...)` espera."""
    chave = TIPOS[item['tipo']][2]
    return (item['tipo'], *(item['chave'][c] for c in chave))


def ajustes_em_conflito(conn, lote) -> list:
    """Atos do `lote` que já têm ajuste manual no banco e cujo valor do PDF DIFERE
    do ajuste. Para cada um: {'tipo', 'chave' (chave atual), 'rotulo', 'campos':
    [{'campo', 'atual' (ajustado), 'pdf'}]}. Só lê o banco."""
    itens = []
    for tipo, registros in (('consulta', lote.consultas), ('regime', lote.regimes)):
        tabela, colunas, chave = TIPOS[tipo]
        for reg in registros:
            recebida = tuple(_texto(reg.get(c)) for c in chave)
            chave_atual = armazenamento.resolver_chave(conn, tabela, chave, recebida)
            salvo = armazenamento.buscar_detalhe(conn, tabela, chave,
                                                 dict(zip(chave, chave_atual)))
            if salvo is None:
                continue
            campos = []
            for campo in armazenamento.ajustes_de(conn, tabela, chave, chave_atual):
                manual, do_pdf = _texto(salvo.get(campo)), _texto(reg.get(campo))
                if manual != do_pdf:
                    campos.append({'campo': campo, 'atual': manual, 'pdf': do_pdf})
            if campos:
                chave_dict = dict(zip(chave, chave_atual))
                itens.append({'tipo': tipo, 'chave': chave_dict, 'campos': campos,
                              'rotulo': rotulo_do_ato(tipo, chave_dict)})
    return itens


def ajustar_no_lote(lote, tipo: str, chave_atual: dict, novos: dict) -> dict:
    """Edita um ato que ainda está na ANÁLISE (só em memória). Mesmas regras de
    `editar_registro`, sem tocar o banco: registra em `lote.ajustados` os campos
    editados e em `lote.chaves_substituidas` a chave corrigida; `lote.origem` acompanha
    a troca. O chamador refaz o diagnóstico depois."""
    tabela, colunas, chave = _tipo(tipo)
    _validar(colunas, novos)
    registros = lote.consultas if tipo == 'consulta' else lote.regimes

    def chave_de(reg):
        return tuple(_texto(reg.get(c)) for c in chave)

    procurada = tuple(_texto(chave_atual.get(c)) for c in chave)
    alvo = next((r for r in registros if chave_de(r) == procurada), None)
    if alvo is None:
        raise RegistroInexistente(f"Não há ato com a chave {chave_atual!r} nesta análise.")
    final = {c: (_limpo(novos[c]) if c in novos else _texto(alvo.get(c))) for c in colunas}
    alterados = [c for c in colunas if _texto(alvo.get(c)) != final[c]]
    if not alterados:
        return {'alterados': [], 'chave_trocada': False}

    nova = tuple(final[c] for c in chave)
    if not all(nova):
        raise ChaveVazia("O número e os demais campos da chave não podem ficar em branco.")
    trocada = nova != procurada
    if trocada and any(chave_de(r) == nova for r in registros if r is not alvo):
        raise ChaveEmConflito("Outro ato desta análise já usa essa chave.")

    alvo.update({c: final[c] for c in alterados})
    campos = set(lote.ajustados.pop((tipo, *procurada), set()))
    campos |= {c for c in alterados if c not in chave}
    if campos:
        lote.ajustados[(tipo, *nova)] = campos
    if trocada:
        arquivo = lote.origem.pop((tipo, *procurada), None)
        if arquivo is not None:
            lote.origem[(tipo, *nova)] = arquivo
        lote.chaves_substituidas.append((tipo, procurada, nova))
    return {'alterados': alterados, 'chave_trocada': trocada}
