# core/consulta.py
"""Busca unificada por tipo (consulta/regime), para a interface."""
import io

from core import armazenamento, planilha

TIPOS = ('consulta', 'regime')


def buscar(conn, tipo: str, texto=None, ano=None) -> list:
    if tipo == 'consulta':
        return armazenamento.buscar_consultas(conn, texto, ano)
    if tipo == 'regime':
        return armazenamento.buscar_regimes(conn, texto, ano)
    raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")


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
