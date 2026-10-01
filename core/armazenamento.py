# core/armazenamento.py
"""Persistência local (SQLite) de consultas e regimes já extraídos.

Upsert pela mesma chave natural que core.pipeline já usa para deduplicar em
memória (CHAVE_CONSULTAS/CHAVE_REGIMES): reprocessar um PDF já mapeado
atualiza o registro em vez de duplicar. Nenhuma dependência nova — sqlite3 é
biblioteca padrão.
"""
import os
import sqlite3

from core.pipeline import CHAVE_CONSULTAS, CHAVE_REGIMES, Lote

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CAMINHO_PADRAO = os.path.join(_RAIZ, 'mapeamento.db')

COLUNAS_CONSULTAS = [
    'Ano', 'Nº da Consulta', 'Data da Publicação', 'Protocolo',
    'Súmula', 'Problema da Consulta', 'CNAE Detectado', 'Resposta',
]
COLUNAS_REGIMES = [
    'ANO', 'DATA', 'Nº DOE', 'RE PR COMPETITIVO', 'Nº DO REGIME ESPECIAL',
    'EMPRESA', 'CNPJ REQUERENTE', 'CAD/ICMS', 'CNAE REQUERENTE',
    'DESCRIÇÃO CNAE', 'VIGÊNCIA DO RE', 'EMENTA',
    'ABRANGÊNCIA', 'BENEFÍCIOS/PROCEDIMENTOS', 'DISPOSIÇÕES GERAIS',
]


def conectar(caminho_bd: str | None = None) -> sqlite3.Connection:
    """Abre (ou cria) o banco. Sem `caminho_bd`, usa mapeamento.db na raiz
    do projeto."""
    conn = sqlite3.connect(caminho_bd or _CAMINHO_PADRAO)
    conn.row_factory = sqlite3.Row
    return conn


def _upsert(conn: sqlite3.Connection, tabela: str, colunas: list,
           chave: list, registros: list) -> dict:
    """Upsert genérico por chave natural. Devolve {'novos': N, 'atualizados': M}.

    Uma SELECT por registro antes do upsert, só para contar novo vs
    atualizado (o ON CONFLICT DO UPDATE do sqlite3 não distingue os dois
    casos no retorno). Aceitável dado o volume desta ferramenta
    (publicações oficiais, não uma base transacional).
    """
    chave_sql = ' AND '.join(f'"{c}" = ?' for c in chave)
    colnames = ', '.join(f'"{c}"' for c in colunas)
    placeholders = ', '.join('?' for _ in colunas)
    conflito = ', '.join(f'"{c}"' for c in chave)
    sets = ', '.join(f'"{c}"=excluded."{c}"' for c in colunas if c not in chave)
    upsert_sql = (
        f'INSERT INTO {tabela} ({colnames}) VALUES ({placeholders}) '
        f'ON CONFLICT({conflito}) DO UPDATE SET {sets}'
    )
    novos = atualizados = 0
    for reg in registros:
        chave_valores = tuple(reg.get(c, '') for c in chave)
        existe = conn.execute(
            f'SELECT 1 FROM {tabela} WHERE {chave_sql}', chave_valores
        ).fetchone()
        conn.execute(upsert_sql, tuple(reg.get(c, '') for c in colunas))
        novos += existe is None
        atualizados += existe is not None
    conn.commit()
    return {'novos': novos, 'atualizados': atualizados}


def _colunas_existentes(conn: sqlite3.Connection, tabela: str) -> set:
    return {linha[1] for linha in conn.execute(f'PRAGMA table_info("{tabela}")')}


def _criar_tabela(conn: sqlite3.Connection, tabela: str, colunas: list,
                  chave: list) -> None:
    """Cria a tabela se não existir e, se já existir, adiciona por ALTER TABLE
    as colunas novas que faltarem (ex.: 'Resposta' num mapeamento.db já
    commitado, criado antes desse campo existir). CREATE TABLE IF NOT EXISTS
    sozinho não altera uma tabela já criada — sem isso, o próximo upsert
    quebraria com "no such column" assim que um campo novo fosse adicionado
    ao parser. Só adiciona coluna, nunca remove/renomeia: aditivo e seguro
    para rodar sobre uma base com dados reais.
    """
    chave_sql = ', '.join(f'"{c}"' for c in chave)
    cols_sql = ', '.join(f'"{c}" TEXT' for c in colunas)
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS {tabela} ({cols_sql}, UNIQUE({chave_sql}))'
    )
    existentes = _colunas_existentes(conn, tabela)
    for coluna in colunas:
        if coluna not in existentes:
            conn.execute(f'ALTER TABLE {tabela} ADD COLUMN "{coluna}" TEXT')


def criar_esquema(conn: sqlite3.Connection) -> None:
    """Cria as tabelas de consultas e regimes se não existirem. Idempotente."""
    _criar_tabela(conn, 'consultas', COLUNAS_CONSULTAS, CHAVE_CONSULTAS)
    _criar_tabela(conn, 'regimes', COLUNAS_REGIMES, CHAVE_REGIMES)
    conn.commit()


def salvar_consultas(conn: sqlite3.Connection, registros: list) -> dict:
    """Upsert por CHAVE_CONSULTAS. Devolve {'novos': N, 'atualizados': M}."""
    return _upsert(conn, 'consultas', COLUNAS_CONSULTAS, CHAVE_CONSULTAS, registros)


def salvar_regimes(conn: sqlite3.Connection, registros: list) -> dict:
    """Upsert por CHAVE_REGIMES. Devolve {'novos': N, 'atualizados': M}."""
    return _upsert(conn, 'regimes', COLUNAS_REGIMES, CHAVE_REGIMES, registros)


def buscar_consultas(conn: sqlite3.Connection, texto: str | None = None,
                     ano: str | None = None) -> list:
    condicoes, parametros = [], []
    if texto:
        condicoes.append('("Súmula" LIKE ? OR "Problema da Consulta" LIKE ? '
                         'OR "CNAE Detectado" LIKE ?)')
        parametros += [f'%{texto}%'] * 3
    if ano:
        condicoes.append('"Ano" = ?')
        parametros.append(ano)
    where = f'WHERE {" AND ".join(condicoes)}' if condicoes else ''
    linhas = conn.execute(f'SELECT * FROM consultas {where}', parametros).fetchall()
    return [dict(linha) for linha in linhas]


def buscar_regimes(conn: sqlite3.Connection, texto: str | None = None,
                   ano: str | None = None) -> list:
    condicoes, parametros = [], []
    if texto:
        condicoes.append('("EMPRESA" LIKE ? OR "EMENTA" LIKE ?)')
        parametros += [f'%{texto}%'] * 2
    if ano:
        condicoes.append('"ANO" = ?')
        parametros.append(ano)
    where = f'WHERE {" AND ".join(condicoes)}' if condicoes else ''
    linhas = conn.execute(f'SELECT * FROM regimes {where}', parametros).fetchall()
    return [dict(linha) for linha in linhas]


def persistir_lote(conn: sqlite3.Connection, lote: Lote) -> dict:
    """Persiste um core.pipeline.Lote inteiro (consultas + regimes) de uma vez."""
    return {'consultas': salvar_consultas(conn, lote.consultas),
            'regimes': salvar_regimes(conn, lote.regimes)}
