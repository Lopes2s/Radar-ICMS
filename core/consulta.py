# core/consulta.py
"""Busca unificada por tipo (consulta/regime), para a interface."""
import io

from core import armazenamento, pipeline, planilha

TIPOS = ('consulta', 'regime')
COLUNAS_LISTA = {'consulta': armazenamento.COLUNAS_LISTA_CONSULTAS,
                 'regime': armazenamento.COLUNAS_LISTA_REGIMES}
CHAVES = {'consulta': pipeline.CHAVE_CONSULTAS, 'regime': pipeline.CHAVE_REGIMES}
_TABELAS = {'consulta': 'consultas', 'regime': 'regimes'}


def buscar(conn, tipo: str, texto=None, ano=None) -> list:
    if tipo == 'consulta':
        return armazenamento.buscar_consultas(conn, texto, ano)
    if tipo == 'regime':
        return armazenamento.buscar_regimes(conn, texto, ano)
    raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")


def buscar_lista(conn, tipo: str, texto=None, ano=None) -> list:
    """Como `buscar`, só com as colunas curtas da tabela da tela (sem o texto
    integral da Resposta). O detalhe vem de `detalhe`."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")
    if tipo == 'consulta':
        return armazenamento.buscar_consultas(conn, texto, ano, COLUNAS_LISTA[tipo])
    return armazenamento.buscar_regimes(conn, texto, ano, COLUNAS_LISTA[tipo])


def detalhe(conn, tipo: str, linha_da_lista: dict):
    """Registro completo da linha escolhida na lista, pela chave natural."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")
    return armazenamento.buscar_detalhe(conn, _TABELAS[tipo], CHAVES[tipo],
                                        linha_da_lista)


def anos_disponiveis(conn, tipo: str) -> list:
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")
    campo_ano = 'Ano' if tipo == 'consulta' else 'ANO'
    tabela = 'consultas' if tipo == 'consulta' else 'regimes'
    linhas = conn.execute(
        f'SELECT DISTINCT "{campo_ano}" FROM {tabela} ORDER BY "{campo_ano}"'
    ).fetchall()
    return [linha[0] for linha in linhas]


def exportar_xlsx(tipo: str, resultados: list) -> bytes:
    """Gera um .xlsx (em memória) só com os resultados de uma busca —
    a planilha deixou de ser o produto final, mas continua disponível como
    extração a partir do que foi pesquisado."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")
    buf = io.BytesIO()
    if tipo == 'consulta':
        planilha.gerar_xlsx(buf, consultas=resultados)
    else:
        planilha.gerar_xlsx(buf, regimes=resultados)
    return buf.getvalue()


def exportar_busca(tipo: str, texto=None, ano=None, caminho_bd=None) -> bytes:
    """Refaz a busca com conexão PRÓPRIA e devolve o .xlsx.

    O `st.download_button` executa esta função numa thread à parte, quando o
    usuário clica; uma conexão SQLite aberta em outra thread não pode ser
    usada ali."""
    with armazenamento.aberta(caminho_bd) as conn:
        return exportar_xlsx(tipo, buscar(conn, tipo, texto, ano))
