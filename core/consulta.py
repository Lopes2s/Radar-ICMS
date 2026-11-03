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


def historico(conn, tipo: str, registro: dict) -> list:
    """Versões anteriores do ato (consulta ou regime), da mais recente para a
    mais antiga. `registro` precisa conter as colunas da chave natural."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")
    chave = {c: registro.get(c, '') for c in CHAVES[tipo]}
    return armazenamento.historico_de(conn, _TABELAS[tipo], chave)


def resumo_do_banco(conn) -> dict:
    """Números para os indicadores da tela de consulta: quantos atos há em cada
    tabela, os anos cobertos (união das duas, sem vazios, em ordem) e a data da
    última importação (ISO UTC, ou None se nunca houve)."""
    n_consultas = conn.execute('SELECT COUNT(*) FROM consultas').fetchone()[0]
    n_regimes = conn.execute('SELECT COUNT(*) FROM regimes').fetchone()[0]
    anos = sorted({a for tipo in TIPOS for a in anos_disponiveis(conn, tipo) if a})
    ultima = conn.execute('SELECT MAX(importado_em) FROM importacoes').fetchone()[0]
    return {'consultas': n_consultas, 'regimes': n_regimes, 'anos': anos,
            'ultima_importacao': ultima}


def ajustes(conn, tipo: str, registro: dict) -> list:
    """Campos deste ato que o administrador ajustou à mão (lista vazia se nenhum)."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")
    chave = CHAVES[tipo]
    return armazenamento.ajustes_de(conn, _TABELAS[tipo], chave,
                                    tuple(registro.get(c, '') for c in chave))


def receita(conn, registro: dict):
    """Dados do CNPJ do regime na Receita Federal (CNAE e situação), guardados em
    cnpj_receita; None se o CNPJ ainda não foi consultado."""
    return armazenamento.cnpj_receita_de(conn, registro.get('CNPJ REQUERENTE'))
