# core/armazenamento.py
"""Persistência local (SQLite) de consultas e regimes já extraídos.

Upsert pela mesma chave natural que core.pipeline já usa para deduplicar em
memória (CHAVE_CONSULTAS/CHAVE_REGIMES): reprocessar um PDF já mapeado
atualiza o registro em vez de duplicar. Nenhuma dependência nova — sqlite3 é
biblioteca padrão.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from core.pipeline import CHAVE_CONSULTAS, CHAVE_REGIMES, Lote
from core.texto import normalizar
from core.versao import VERSAO_APP

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
COLUNAS_LISTA_CONSULTAS = ['Ano', 'Nº da Consulta', 'Data da Publicação',
                           'Súmula', 'CNAE Detectado']
COLUNAS_LISTA_REGIMES = ['ANO', 'DATA', 'Nº DO REGIME ESPECIAL', 'EMPRESA',
                         'CNPJ REQUERENTE', 'VIGÊNCIA DO RE', 'EMENTA']


def _select(colunas) -> str:
    return '*' if not colunas else ', '.join(f'"{c}"' for c in colunas)


SCHEMA_VERSAO = 3

_DDL_HISTORICO = """
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabela TEXT NOT NULL,
    chave TEXT NOT NULL,
    registro_anterior TEXT NOT NULL,
    campos_alterados TEXT NOT NULL,
    alterado_em TEXT NOT NULL,
    versao_app TEXT NOT NULL,
    origem TEXT NOT NULL DEFAULT 'importacao'
)"""
# campos que o administrador ajustou à mão num ato (a reimportação não os sobrescreve sem confirmação)
_DDL_AJUSTES = """
CREATE TABLE IF NOT EXISTS ajustes (
    tabela TEXT NOT NULL,
    chave TEXT NOT NULL,
    campos TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    PRIMARY KEY (tabela, chave)
)"""
# chave antiga -> chave nova, quando o administrador corrigiu a chave de um ato
_DDL_SUBSTITUICOES = """
CREATE TABLE IF NOT EXISTS chaves_substituidas (
    tabela TEXT NOT NULL,
    chave_antiga TEXT NOT NULL,
    chave_nova TEXT NOT NULL,
    trocada_em TEXT NOT NULL,
    PRIMARY KEY (tabela, chave_antiga)
)"""
_DDL_IMPORTACOES = """
CREATE TABLE IF NOT EXISTS importacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arquivo TEXT, sha256 TEXT, tipo TEXT, n_registros INTEGER,
    importado_em TEXT NOT NULL,
    versao_app TEXT NOT NULL
)"""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class SchemaMaisNovo(RuntimeError):
    """O banco foi criado por uma versão mais nova da ferramenta."""


def versao_do_schema(conn: sqlite3.Connection) -> int:
    return conn.execute('PRAGMA user_version').fetchone()[0]


def pasta_dados() -> str:
    """Pasta do banco e dos logs: `MAPEADOR_DADOS` ou a raiz do projeto.
    É criada se não existir."""
    pasta = os.environ.get('MAPEADOR_DADOS') or _RAIZ
    os.makedirs(pasta, exist_ok=True)
    return pasta


def caminho_do_banco(caminho_bd: str | None = None) -> str:
    """Precedência: argumento > MAPEADOR_BANCO > <pasta_dados>/mapeamento.db."""
    return (caminho_bd or os.environ.get('MAPEADOR_BANCO')
            or os.path.join(pasta_dados(), 'mapeamento.db'))


def conectar(caminho_bd: str | None = None) -> sqlite3.Connection:
    """Abre (ou cria) o banco (ver `caminho_do_banco` para a escolha do arquivo)."""
    conn = sqlite3.connect(caminho_do_banco(caminho_bd))
    conn.row_factory = sqlite3.Row
    conn.create_function('norm', 1, normalizar, deterministic=True)
    return conn


@contextmanager
def aberta(caminho_bd: str | None = None):
    """Conexão que é FECHADA ao sair do bloco, com ou sem erro."""
    conn = conectar(caminho_bd)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def sessao(caminho_bd: str | None = None):
    """Como `aberta`, com o esquema já criado/atualizado (idempotente)."""
    with aberta(caminho_bd) as conn:
        criar_esquema(conn)
        yield conn


def _chave_json(chave: list, valores) -> str:
    """A chave natural como JSON estável (usada em historico, ajustes e chaves_substituidas)."""
    return json.dumps(dict(zip(chave, valores)), ensure_ascii=False, sort_keys=True)


def registrar_alteracao(conn, tabela, chave, valores_chave, anterior, alterados,
                        origem='importacao'):
    """Guarda a linha ANTERIOR de um ato em `historico`. `origem`: 'importacao'
    (reimportação do PDF) ou 'manual' (edição do administrador). Não faz commit."""
    conn.execute(
        'INSERT INTO historico (tabela, chave, registro_anterior, '
        'campos_alterados, alterado_em, versao_app, origem) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (tabela, _chave_json(chave, valores_chave),
         json.dumps(dict(anterior), ensure_ascii=False),
         json.dumps(alterados, ensure_ascii=False),
         _agora(), VERSAO_APP, origem))


def ajustes_de(conn, tabela, chave, valores_chave) -> list:
    """Campos que o administrador ajustou à mão neste ato (ordem alfabética)."""
    linha = conn.execute('SELECT campos FROM ajustes WHERE tabela = ? AND chave = ?',
                         (tabela, _chave_json(chave, valores_chave))).fetchone()
    return json.loads(linha['campos']) if linha else []


def juntar_ajustes(conn, tabela, chave, valores_chave, campos) -> None:
    """Acrescenta `campos` aos ajustes do ato (união, sem repetir). Não faz commit."""
    uniao = sorted(set(ajustes_de(conn, tabela, chave, valores_chave)) | set(campos))
    if not uniao:
        return
    conn.execute(
        'INSERT OR REPLACE INTO ajustes (tabela, chave, campos, atualizado_em) '
        'VALUES (?, ?, ?, ?)',
        (tabela, _chave_json(chave, valores_chave),
         json.dumps(uniao, ensure_ascii=False), _agora()))


def limpar_ajustes(conn, tabela, chave, valores_chave) -> None:
    conn.execute('DELETE FROM ajustes WHERE tabela = ? AND chave = ?',
                 (tabela, _chave_json(chave, valores_chave)))


def resolver_chave(conn, tabela, chave, valores_chave) -> tuple:
    """Chave ATUAL do ato: se a chave recebida foi trocada por uma edição, devolve
    a nova; senão, a mesma. É assim que reimportar o PDF original cai no ato já
    corrigido, em vez de criar um duplicado."""
    atual, vistos = tuple(valores_chave), set()
    while atual not in vistos:
        vistos.add(atual)
        linha = conn.execute(
            'SELECT chave_nova FROM chaves_substituidas WHERE tabela = ? AND chave_antiga = ?',
            (tabela, _chave_json(chave, atual))).fetchone()
        if linha is None:
            break
        nova = json.loads(linha['chave_nova'])
        atual = tuple(nova[c] for c in chave)
    return atual


def registrar_substituicao(conn, tabela, chave, antiga, nova) -> None:
    """Anota que `antiga` agora é `nova`. Mantém as cadeias achatadas (A->B depois
    B->C vira A->C e B->C) e apaga o apelido de uma chave que voltou a ser real
    (C->A apaga A->C). Não faz commit."""
    ja, jn = _chave_json(chave, antiga), _chave_json(chave, nova)
    if ja == jn:
        return
    conn.execute('DELETE FROM chaves_substituidas WHERE tabela = ? AND chave_antiga = ?',
                 (tabela, jn))
    conn.execute('UPDATE chaves_substituidas SET chave_nova = ? '
                 'WHERE tabela = ? AND chave_nova = ?', (jn, tabela, ja))
    conn.execute(
        'INSERT OR REPLACE INTO chaves_substituidas (tabela, chave_antiga, chave_nova, '
        'trocada_em) VALUES (?, ?, ?, ?)', (tabela, ja, jn, _agora()))


def mover_chave_auxiliares(conn, tabela, chave, antiga, nova) -> None:
    """Depois de trocar a chave de um ato, leva o histórico e os ajustes para a
    chave nova. Não faz commit."""
    ja, jn = _chave_json(chave, antiga), _chave_json(chave, nova)
    conn.execute('UPDATE historico SET chave = ? WHERE tabela = ? AND chave = ?',
                 (jn, tabela, ja))
    conn.execute('DELETE FROM ajustes WHERE tabela = ? AND chave = ?', (tabela, jn))
    conn.execute('UPDATE ajustes SET chave = ? WHERE tabela = ? AND chave = ?',
                 (jn, tabela, ja))


def _upsert(conn: sqlite3.Connection, tabela: str, colunas: list,
           chave: list, registros: list) -> dict:
    """Upsert genérico por chave natural. Devolve {'novos': N, 'atualizados': M}.

    Quando o registro já existe e algum campo (fora a chave) muda, a linha
    anterior é guardada em `historico` antes de ser sobrescrita. O valor novo
    sempre vence, inclusive vazio: o histórico é que preserva o anterior.
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
        anterior = conn.execute(
            f'SELECT * FROM {tabela} WHERE {chave_sql}', chave_valores
        ).fetchone()
        if anterior is not None:
            alterados = [c for c in colunas if c not in chave
                         and str(anterior[c] or '') != str(reg.get(c, '') or '')]
            if alterados:
                registrar_alteracao(conn, tabela, chave, chave_valores,
                                    anterior, alterados)
        conn.execute(upsert_sql, tuple(reg.get(c, '') for c in colunas))
        novos += anterior is None
        atualizados += anterior is not None
    conn.commit()
    return {'novos': novos, 'atualizados': atualizados}


def historico_de(conn: sqlite3.Connection, tabela: str, chave: dict) -> list:
    """Versões anteriores de um registro (a chave natural como dict), da mais
    recente para a mais antiga."""
    linhas = conn.execute(
        'SELECT * FROM historico WHERE tabela = ? AND chave = ? ORDER BY id DESC',
        (tabela, json.dumps(chave, ensure_ascii=False, sort_keys=True))).fetchall()
    return [{'alterado_em': l['alterado_em'], 'versao_app': l['versao_app'],
             'origem': l['origem'],
             'campos_alterados': json.loads(l['campos_alterados']),
             'registro_anterior': json.loads(l['registro_anterior'])}
            for l in linhas]


def registrar_importacoes(conn: sqlite3.Connection, importacoes: list) -> None:
    """Uma linha por PDF importado (nome, SHA-256, tipo, quantidade, quando, versão)."""
    for i in importacoes:
        conn.execute(
            'INSERT INTO importacoes (arquivo, sha256, tipo, n_registros, '
            'importado_em, versao_app) VALUES (?, ?, ?, ?, ?, ?)',
            (i['arquivo'], i['sha256'], i['tipo'], i['n_registros'],
             _agora(), VERSAO_APP))
    conn.commit()


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
    """Cria/atualiza as tabelas. Idempotente e só aditivo.

    Recusa (SchemaMaisNovo) um banco criado por versão mais nova, ANTES de
    mexer em qualquer coisa. O `user_version` só é regravado quando muda, para
    que abrir o banco a cada rerun da interface não tome o bloqueio de escrita.
    """
    atual = versao_do_schema(conn)
    if atual > SCHEMA_VERSAO:
        raise SchemaMaisNovo(
            f"Este banco foi criado por uma versão mais nova da ferramenta "
            f"(schema {atual}; esta versão conhece até {SCHEMA_VERSAO}). "
            f"Atualize a ferramenta antes de abrir este banco.")
    _criar_tabela(conn, 'consultas', COLUNAS_CONSULTAS, CHAVE_CONSULTAS)
    _criar_tabela(conn, 'regimes', COLUNAS_REGIMES, CHAVE_REGIMES)
    conn.execute(_DDL_HISTORICO)
    if 'origem' not in _colunas_existentes(conn, 'historico'):  # banco do schema 2
        conn.execute("ALTER TABLE historico ADD COLUMN origem TEXT NOT NULL DEFAULT 'importacao'")
    conn.execute(_DDL_IMPORTACOES)
    conn.execute(_DDL_AJUSTES)
    conn.execute(_DDL_SUBSTITUICOES)
    if atual != SCHEMA_VERSAO:
        conn.execute(f'PRAGMA user_version = {SCHEMA_VERSAO}')
    conn.commit()


def salvar_consultas(conn: sqlite3.Connection, registros: list) -> dict:
    """Upsert por CHAVE_CONSULTAS. Devolve {'novos': N, 'atualizados': M}."""
    return _upsert(conn, 'consultas', COLUNAS_CONSULTAS, CHAVE_CONSULTAS, registros)


def salvar_regimes(conn: sqlite3.Connection, registros: list) -> dict:
    """Upsert por CHAVE_REGIMES. Devolve {'novos': N, 'atualizados': M}."""
    return _upsert(conn, 'regimes', COLUNAS_REGIMES, CHAVE_REGIMES, registros)


_CAMPOS_BUSCA_CONSULTAS = ['Nº da Consulta', 'Súmula', 'Problema da Consulta',
                           'CNAE Detectado', 'Resposta']
_CAMPOS_BUSCA_REGIMES = ['Nº DO REGIME ESPECIAL', 'EMPRESA', 'CNPJ REQUERENTE',
                         'EMENTA', 'BENEFÍCIOS/PROCEDIMENTOS']
_ESCAPE = " ESCAPE '\\'"  # em SQL: ESCAPE '\'


def _filtro_texto(campos: list, texto: str | None):
    """(condição SQL, parâmetros) da busca textual, ou None se não há o que
    filtrar. Compara `norm(campo)` com o texto normalizado; `%` e `_` digitados
    pelo usuário valem como caracteres comuns."""
    alvo = normalizar(texto)
    if not alvo:
        return None
    literal = alvo.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    condicao = ' OR '.join(f'norm("{c}") LIKE ?{_ESCAPE}' for c in campos)
    return f'({condicao})', [f'%{literal}%'] * len(campos)


def buscar_consultas(conn: sqlite3.Connection, texto: str | None = None,
                     ano: str | None = None, colunas: list | None = None) -> list:
    condicoes, parametros = [], []
    filtro = _filtro_texto(_CAMPOS_BUSCA_CONSULTAS, texto)
    if filtro:
        condicoes.append(filtro[0])
        parametros += filtro[1]
    if ano:
        condicoes.append('"Ano" = ?')
        parametros.append(ano)
    where = f'WHERE {" AND ".join(condicoes)}' if condicoes else ''
    linhas = conn.execute(
        f'SELECT {_select(colunas)} FROM consultas {where}', parametros).fetchall()
    return [dict(linha) for linha in linhas]


def buscar_regimes(conn: sqlite3.Connection, texto: str | None = None,
                   ano: str | None = None, colunas: list | None = None) -> list:
    condicoes, parametros = [], []
    filtro = _filtro_texto(_CAMPOS_BUSCA_REGIMES, texto)
    if filtro:
        condicoes.append(filtro[0])
        parametros += filtro[1]
    if ano:
        condicoes.append('"ANO" = ?')
        parametros.append(ano)
    where = f'WHERE {" AND ".join(condicoes)}' if condicoes else ''
    linhas = conn.execute(
        f'SELECT {_select(colunas)} FROM regimes {where}', parametros).fetchall()
    return [dict(linha) for linha in linhas]


def buscar_detalhe(conn: sqlite3.Connection, tabela: str, chave: list,
                   valores: dict) -> dict | None:
    """O registro completo pela chave natural, ou None. `tabela` é sempre
    'consultas' ou 'regimes' (vem do código, nunca do usuário)."""
    if tabela not in ('consultas', 'regimes'):
        raise ValueError(f"tabela inválida: {tabela!r}")
    where = ' AND '.join(f'"{c}" = ?' for c in chave)
    linha = conn.execute(f'SELECT * FROM {tabela} WHERE {where}',
                         tuple(valores.get(c, '') for c in chave)).fetchone()
    return dict(linha) if linha else None


def persistir_lote(conn: sqlite3.Connection, lote: Lote) -> dict:
    """Persiste um core.pipeline.Lote inteiro (consultas + regimes) de uma vez."""
    resultado = {'consultas': salvar_consultas(conn, lote.consultas),
                 'regimes': salvar_regimes(conn, lote.regimes)}
    registrar_importacoes(conn, lote.importacoes)
    return resultado
