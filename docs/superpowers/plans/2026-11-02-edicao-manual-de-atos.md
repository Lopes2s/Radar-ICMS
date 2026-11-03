# Edição manual de consultas e regimes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que o administrador corrija consultas e regimes — depois de gravados (no detalhe do ato) e antes de gravar (na análise) — inclusive a chave do ato, sem que a reimportação do PDF desfaça as correções sem confirmação.

**Architecture:** Um módulo novo `core/edicao.py` (sem Streamlit) concentra as regras de edição. O banco ganha o schema 3: `ajustes` (campos corrigidos à mão por ato), `chaves_substituidas` (apelido: chave antiga → chave nova) e `historico.origem` (importação ou ajuste manual). O upsert passa a resolver apelidos de chave e a **não sobrescrever campos ajustados**, salvo para os atos que o administrador mandar sobrescrever. A interface ganha um formulário reutilizável (`interface/formularios.py`) usado no detalhe (grava dentro do `on_click` do formulário) e na análise (edita só o `Lote` em memória).

**Tech Stack:** Python 3.10+, SQLite (`sqlite3`), Streamlit 1.63, pytest. Nenhuma dependência nova.

**Spec:** `docs/superpowers/specs/2026-11-02-edicao-manual-de-atos-design.md`

## Global Constraints

- Nenhuma dependência de terceiros nova; nenhum pino de `requirements.txt` muda.
- Comando de testes: `python -m pytest -q` (o `pytest` puro não está no PATH). Linha de base ao escrever este plano: **307 testes** passando; ao fim do plano: **357**.
- **Contratos que não podem mudar:** `salvar_consultas`/`salvar_regimes` devolvem exatamente `{'novos': N, 'atualizados': M}`; `persistir_lote` devolve exatamente `{'consultas': {...}, 'regimes': {...}}`; cada linha de `lote.arquivos` tem as 6 chaves de sempre; os dicts dos parsers não ganham chaves; `st.session_state["resultado"]` mantém suas 6 chaves; `armazenamento._CAMINHO_PADRAO` continua existindo; a CLI mantém `Uso:` em stdout com código 1 para uso incorreto e os códigos 0/1/2 de hoje.
- **Só o administrador edita.** Nada na interface do perfil Consulta pode oferecer ou executar edição; as funções da interface que gravam chamam `acesso.exige_admin`.
- Edição é **tudo ou nada**: se algo falhar no meio, nada fica gravado (`rollback`).
- A reimportação **nunca** sobrescreve campo ajustado à mão sem o administrador marcar o ato (interface) ou passar `--sobrescrever-ajustes` (CLI).
- Textos da interface e mensagens em português, com acentuação correta; toda cor/estilo segue o Design System já aplicado (nada de cor fixa nova).
- **Commits: em português, no formato `tipo: descrição`, SEM linha `Co-Authored-By` e sem rodapé de geração** (o commit sai só em nome do usuário; é preferência explícita dele). Um commit por tarefa, na branch `edicao-manual-de-atos`. **Não fazer push** nem merge: isso é decisão do usuário.
- O Streamlit **não permite alterar `st.session_state[<chave de um widget>]` depois que o widget foi desenhado** na mesma execução. Por isso o salvamento do detalhe roda no `on_click` do botão do formulário (que executa antes do script). Não troque isso por `st.rerun()` + mexer na seleção da tabela: falha com `StreamlitWidgetAlreadyInstantiatedError`.

## Review Focus

Condições que a spec implica mas que nenhuma tarefa exercitaria por acaso; cada uma tem seu teste na tarefa dona do código:

1. **Chave corrigida para uma que já existe** — a edição é recusada com mensagem clara e **nada** muda (nem histórico, nem apelido). → Tarefa 2 (`test_chave_em_conflito_e_recusada_sem_alterar_nada`) e Tarefas 5 e 8 (edição na análise e no detalhe).
2. **Reimportar o PDF original depois de corrigir a chave** (inclusive depois de duas correções seguidas) — cai no ato corrigido, sem duplicar. → Tarefa 3.
3. **Reimportação de um ato com campo ajustado** — por padrão mantém o ajuste e atualiza o resto; marcado para sobrescrever, o PDF vence e o ajuste é limpo. → Tarefas 3, 6 (CLI) e 9 (interface).
4. **Banco do schema 2 abre no schema 3** sem perder o histórico (linhas antigas ficam com origem `importacao`). → Tarefa 1.
5. **Perfil Consulta nunca vê nem aciona a edição; uma falha no meio da edição não deixa gravação parcial.** → Tarefas 8 e 2 (`test_falha_no_meio_da_edicao_nao_deixa_gravacao_parcial`).

## Verificação do plano

O código e os testes deste plano foram validados antes de serem escritos aqui: as operações de cada tarefa foram aplicadas, **literalmente e em ordem**, a uma cópia limpa do projeto, e a suíte inteira foi rodada **após cada tarefa**. Resultado (testes passando): T1 **313** · T2 **324** · T3 **329** · T4 **332** · T5 **336** · T6 **341** · T7 **346** · T8 **352** · T9 **357** · T10 **357**. Se uma contagem diferir ao executar, algo foi aplicado fora de ordem ou com texto diferente do plano.
---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `core/armazenamento.py` | modificar | schema 3; primitivas de ajustes/apelidos; upsert que protege ajustes; `persistir_lote(..., sobrescrever)` |
| `core/edicao.py` | criar | `editar_registro`, `ajustes_em_conflito`, `ajustar_no_lote` e os erros de regra |
| `core/pipeline.py` | modificar | `Lote.ajustados` e `Lote.chaves_substituidas` |
| `core/execucao.py` | modificar | `gravar(conn, sobrescrever)` |
| `core/consulta.py` | modificar | `ajustes(conn, tipo, registro)` |
| `processar.py` | modificar | `--sobrescrever-ajustes` e aviso dos ajustes em conflito |
| `interface/formularios.py` | criar | formulário reutilizável de um ato |
| `app.py` | modificar | edição no detalhe; ajuste e escolha de conflitos na análise |
| `tests/test_ajustes.py`, `tests/test_edicao.py`, `tests/test_formularios.py` | criar | testes novos |
| `README.md`, `CHANGELOG.md`, `core/versao.py` | modificar | documentação e versão 0.8.0 |

Dependências entre tarefas: 1 → 2 → 3 → 4 → 5 → 6; 7 independe de 3–6 (precisa só da 1); 8 depende de 2 e 7; 9 depende de 3, 4, 5, 7 e 8; 10 por último.

### Task 0: Preparação

- [ ] **Step 1: Criar a branch e conferir a linha de base**

```bash
git switch -c edicao-manual-de-atos
python -m pytest -q
```

Expected: branch criada a partir de `main` e **307 testes passando**. Se algo falhar já aqui, **pare** e avise: o plano assume base verde.

---

### Task 1: Esquema 3: ajustes, apelidos de chave e origem no histórico

**Files:**
- Modify: `core/armazenamento.py`
- Modify: `tests/test_armazenamento.py` (o teste que fixa a versão 2)
- Create: `tests/test_ajustes.py`

**Interfaces:**
- Consumes: `armazenamento.criar_esquema`, `historico_de`, `salvar_consultas` (código existente).
- Produces: `SCHEMA_VERSAO = 3`; tabelas `ajustes` e `chaves_substituidas`; coluna `historico.origem`; `registrar_alteracao(conn, tabela, chave, valores_chave, anterior, alterados, origem='importacao')`; `ajustes_de(conn, tabela, chave, valores_chave) -> list`; `juntar_ajustes(...)`; `limpar_ajustes(...)`; `resolver_chave(conn, tabela, chave, valores_chave) -> tuple`; `registrar_substituicao(conn, tabela, chave, antiga, nova)`; `mover_chave_auxiliares(conn, tabela, chave, antiga, nova)`; `historico_de` passa a devolver `origem` em cada item.

- [ ] **Step 1: Escrever os testes que falham**

O teste antigo `test_schema_sobe_para_a_versao_2_e_banco_v1_e_migrado` fixava o número 2; ele é reescrito para a constante (a mudança é intencional: o schema sobe para 3). Os testes novos cobrem o esquema, a migração do schema 2, os ajustes e os apelidos de chave.

Crie `tests/test_ajustes.py`:

```python
# tests/test_ajustes.py
from core import armazenamento, pipeline

CHAVE_R = pipeline.CHAVE_REGIMES
CHAVE_C = pipeline.CHAVE_CONSULTAS


def _conn(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "e.db"))
    armazenamento.criar_esquema(conn)
    return conn


def _consulta(**campos):
    base = {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
            'Súmula': 'ICMS', 'Resposta': 'resposta'}
    return {**base, **campos}


# --- primitivas de armazenamento -------------------------------------------
def test_esquema_3_tem_ajustes_substituicoes_e_origem_no_historico(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.SCHEMA_VERSAO == 3
    conn.execute("SELECT COUNT(*) FROM ajustes")
    conn.execute("SELECT COUNT(*) FROM chaves_substituidas")
    assert 'origem' in armazenamento._colunas_existentes(conn, 'historico')


def test_banco_v2_migra_para_v3_preservando_o_historico(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(Súmula='a')])
    armazenamento.salvar_consultas(conn, [_consulta(Súmula='b')])   # gera 1 linha de histórico
    # volta o banco ao formato do schema 2: histórico sem 'origem' e sem as tabelas novas
    conn.execute("ALTER TABLE historico RENAME TO historico_novo")
    conn.execute("""CREATE TABLE historico (id INTEGER PRIMARY KEY AUTOINCREMENT, tabela TEXT NOT NULL,
        chave TEXT NOT NULL, registro_anterior TEXT NOT NULL, campos_alterados TEXT NOT NULL,
        alterado_em TEXT NOT NULL, versao_app TEXT NOT NULL)""")
    conn.execute("""INSERT INTO historico (id, tabela, chave, registro_anterior, campos_alterados,
        alterado_em, versao_app) SELECT id, tabela, chave, registro_anterior, campos_alterados,
        alterado_em, versao_app FROM historico_novo""")
    conn.execute("DROP TABLE historico_novo")
    conn.execute("DROP TABLE ajustes")
    conn.execute("DROP TABLE chaves_substituidas")
    conn.execute("PRAGMA user_version = 2")
    conn.commit()

    armazenamento.criar_esquema(conn)

    assert armazenamento.versao_do_schema(conn) == 3
    itens = armazenamento.historico_de(conn, 'consultas', {'Ano': '2026', 'Nº da Consulta': '001'})
    assert len(itens) == 1 and itens[0]['origem'] == 'importacao'
    conn.execute("SELECT COUNT(*) FROM ajustes")


def test_ajustes_juntam_campos_sem_repetir(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.juntar_ajustes(conn, 'regimes', CHAVE_R, ('1', '2'), ['EMENTA'])
    armazenamento.juntar_ajustes(conn, 'regimes', CHAVE_R, ('1', '2'), ['EMENTA', 'DATA'])
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, ('1', '2')) == ['DATA', 'EMENTA']
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, ('9', '9')) == []
    armazenamento.limpar_ajustes(conn, 'regimes', CHAVE_R, ('1', '2'))
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, ('1', '2')) == []


def test_resolver_chave_sem_apelido_devolve_a_mesma(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, ('1', '2')) == ('1', '2')


def test_apelidos_encadeados_apontam_sempre_para_a_chave_atual(tmp_path):
    conn = _conn(tmp_path)
    a, b, c = ('A', '1'), ('B', '1'), ('C', '1')
    armazenamento.registrar_substituicao(conn, 'regimes', CHAVE_R, a, b)
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, a) == b
    armazenamento.registrar_substituicao(conn, 'regimes', CHAVE_R, b, c)
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, a) == c   # A->B->C vira A->C
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, b) == c
    armazenamento.registrar_substituicao(conn, 'regimes', CHAVE_R, c, a)    # a chave voltou a A
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, a) == a   # A é real de novo
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, b) == a
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R, c) == a


def test_mover_chave_leva_historico_e_ajustes(tmp_path):
    conn = _conn(tmp_path)
    antiga, nova = ('1', '2'), ('3', '4')
    armazenamento.registrar_alteracao(conn, 'regimes', CHAVE_R, antiga, {'EMENTA': 'x'}, ['EMENTA'])
    armazenamento.juntar_ajustes(conn, 'regimes', CHAVE_R, antiga, ['EMENTA'])
    armazenamento.mover_chave_auxiliares(conn, 'regimes', CHAVE_R, antiga, nova)
    chave_nova = dict(zip(CHAVE_R, nova))
    assert len(armazenamento.historico_de(conn, 'regimes', chave_nova)) == 1
    assert armazenamento.historico_de(conn, 'regimes', dict(zip(CHAVE_R, antiga))) == []
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, nova) == ['EMENTA']
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, antiga) == []
```

Em `tests/test_armazenamento.py` (este é o último teste do arquivo; passa a comparar com a constante e a apagar também as tabelas novas), substitua tudo desde a linha `def test_schema_sobe_para_a_versao_2_e_banco_v1_e_migrado` até o fim do arquivo por:

```python
def test_schema_sobe_para_a_versao_atual_e_banco_v1_e_migrado(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "v1.db"))
    armazenamento.criar_esquema(conn)
    conn.execute("DROP TABLE historico")
    conn.execute("DROP TABLE importacoes")
    conn.execute("DROP TABLE ajustes")
    conn.execute("DROP TABLE chaves_substituidas")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()

    armazenamento.criar_esquema(conn)

    assert armazenamento.versao_do_schema(conn) == armazenamento.SCHEMA_VERSAO
    conn.execute("SELECT COUNT(*) FROM historico")
    conn.execute("SELECT COUNT(*) FROM importacoes")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_ajustes.py tests/test_armazenamento.py -q`
Expected: FAIL — `AttributeError: module 'core.armazenamento' has no attribute 'juntar_ajustes'` e `sqlite3.OperationalError: no such table: ajustes`.

- [ ] **Step 3: Implementar**

As primitivas **não fazem commit**: quem chama controla a transação.

Em `core/armazenamento.py`, substitua:

```python
SCHEMA_VERSAO = 2
```

por:

```python
SCHEMA_VERSAO = 3
```

Em `core/armazenamento.py` (o histórico ganha a coluna `origem`; entram as tabelas `ajustes` e `chaves_substituidas`), substitua:

```python
    alterado_em TEXT NOT NULL,
    versao_app TEXT NOT NULL
)"""
_DDL_IMPORTACOES = """
```

por:

```python
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
```

Em `core/armazenamento.py` (dentro de `criar_esquema`), substitua:

```python
    conn.execute(_DDL_HISTORICO)
    conn.execute(_DDL_IMPORTACOES)
```

por:

```python
    conn.execute(_DDL_HISTORICO)
    if 'origem' not in _colunas_existentes(conn, 'historico'):  # banco do schema 2
        conn.execute("ALTER TABLE historico ADD COLUMN origem TEXT NOT NULL DEFAULT 'importacao'")
    conn.execute(_DDL_IMPORTACOES)
    conn.execute(_DDL_AJUSTES)
    conn.execute(_DDL_SUBSTITUICOES)
```

Em `core/armazenamento.py` (`_guarda_historico` vira `registrar_alteracao` (com `origem`) e entram as primitivas de ajustes e de chaves), substitua:

```python
def _guarda_historico(conn, tabela, chave, valores_chave, anterior, alterados):
    conn.execute(
        'INSERT INTO historico (tabela, chave, registro_anterior, '
        'campos_alterados, alterado_em, versao_app) VALUES (?, ?, ?, ?, ?, ?)',
        (tabela,
         json.dumps(dict(zip(chave, valores_chave)), ensure_ascii=False, sort_keys=True),
         json.dumps(dict(anterior), ensure_ascii=False),
         json.dumps(alterados, ensure_ascii=False),
         _agora(), VERSAO_APP))
```

por:

```python
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
```

Em `core/armazenamento.py` (a chamada dentro de `_upsert`), substitua:

```python
                _guarda_historico(conn, tabela, chave, chave_valores,
                                  anterior, alterados)
```

por:

```python
                registrar_alteracao(conn, tabela, chave, chave_valores,
                                    anterior, alterados)
```

Em `core/armazenamento.py` (dentro de `historico_de`), substitua:

```python
    return [{'alterado_em': l['alterado_em'], 'versao_app': l['versao_app'],
             'campos_alterados':
```

por:

```python
    return [{'alterado_em': l['alterado_em'], 'versao_app': l['versao_app'],
             'origem': l['origem'],
             'campos_alterados':
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_ajustes.py tests/test_armazenamento.py -q` — Expected: PASS.
Depois a suíte inteira: `python -m pytest -q` — Expected: **313 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/armazenamento.py tests/test_armazenamento.py tests/test_ajustes.py
git commit -m "feat: schema 3 com ajustes manuais, apelidos de chave e origem no histórico"
```

(Sem `Co-Authored-By`: o commit sai só em nome do usuário.)

---

### Task 2: Editar um ato já gravado (`core/edicao.py`)

**Files:**
- Create: `core/edicao.py`
- Create: `tests/test_edicao.py`

**Interfaces:**
- Consumes: Primitivas da Tarefa 1; `armazenamento.buscar_detalhe`, `COLUNAS_*`; `pipeline.CHAVE_*`.
- Produces: `edicao.TIPOS`; erros `RegistroInexistente`, `ChaveEmConflito`, `ChaveVazia`; `edicao.editar_registro(conn, tipo, chave_atual: dict, novos: dict) -> {'alterados': list, 'chave_trocada': bool}`.

- [ ] **Step 1: Escrever os testes que falham**

Cobrem: editar campo (histórico `manual` + ajuste marcado), não gravar nada sem mudança, aparar espaços, consulta, pedidos inválidos, troca de chave (move o ato, o histórico e cria o apelido), chave em conflito, chave em branco e **rollback** se algo falhar no meio.

Crie `tests/test_edicao.py`:

```python
# tests/test_edicao.py
import pytest

from core import armazenamento, edicao, pipeline

CHAVE_R = pipeline.CHAVE_REGIMES
CHAVE_C = pipeline.CHAVE_CONSULTAS


def _conn(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "e.db"))
    armazenamento.criar_esquema(conn)
    return conn


def _regime(**campos):
    base = {'ANO': '2026', 'DATA': '2026-03-01', 'Nº DO REGIME ESPECIAL': '9.053/2026',
            'EMPRESA': 'Alfa Ltda', 'CNPJ REQUERENTE': '11.222.333/0001-81',
            'VIGÊNCIA DO RE': '', 'EMENTA': 'ementa original'}
    return {**base, **campos}


def _consulta(**campos):
    base = {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
            'Súmula': 'ICMS', 'Resposta': 'resposta'}
    return {**base, **campos}


def _chave_regime(reg=None):
    reg = reg or _regime()
    return {c: reg[c] for c in CHAVE_R}


# --- editar_registro --------------------------------------------------------
def test_editar_campo_grava_historico_manual_e_marca_o_ajuste(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    r = edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    assert r == {'alterados': ['VIGÊNCIA DO RE'], 'chave_trocada': False}
    salvo = armazenamento.buscar_regimes(conn)[0]
    assert salvo['VIGÊNCIA DO RE'] == '12 meses' and salvo['EMPRESA'] == 'Alfa Ltda'
    hist = armazenamento.historico_de(conn, 'regimes', _chave_regime())
    assert len(hist) == 1 and hist[0]['origem'] == 'manual'
    assert hist[0]['campos_alterados'] == ['VIGÊNCIA DO RE']
    assert hist[0]['registro_anterior']['VIGÊNCIA DO RE'] == ''
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R,
                                    tuple(_chave_regime().values())) == ['VIGÊNCIA DO RE']


def test_editar_sem_mudanca_nao_grava_nada(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    r = edicao.editar_registro(conn, 'regime', _chave_regime(), {'EMPRESA': 'Alfa Ltda'})
    assert r == {'alterados': [], 'chave_trocada': False}
    assert armazenamento.historico_de(conn, 'regimes', _chave_regime()) == []


def test_editar_apara_espacos_das_pontas(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'EMPRESA': '  Beta S.A.  '})
    assert armazenamento.buscar_regimes(conn)[0]['EMPRESA'] == 'Beta S.A.'


def test_editar_consulta_tambem_funciona(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(Resposta='')])
    chave = {c: _consulta()[c] for c in CHAVE_C}
    r = edicao.editar_registro(conn, 'consulta', chave, {'Resposta': 'texto corrigido'})
    assert r['alterados'] == ['Resposta']
    assert armazenamento.buscar_consultas(conn)[0]['Resposta'] == 'texto corrigido'
    assert armazenamento.historico_de(conn, 'consultas', chave)[0]['origem'] == 'manual'


@pytest.mark.parametrize("tipo, chave, novos, erro", [
    ('regime', {'Nº DO REGIME ESPECIAL': 'x', 'CNPJ REQUERENTE': 'y'}, {'EMPRESA': 'a'},
     edicao.RegistroInexistente),
    ('regime', None, {'CAMPO_QUE_NAO_EXISTE': 'a'}, ValueError),
    ('outro', {}, {}, ValueError),
])
def test_editar_recusa_pedidos_invalidos(tmp_path, tipo, chave, novos, erro):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    with pytest.raises(erro):
        edicao.editar_registro(conn, tipo, chave or _chave_regime(), novos)


def test_trocar_a_chave_move_o_ato_o_historico_e_cria_o_apelido(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime(**{'CNPJ REQUERENTE': '00.000.000/0000-00'})])
    antiga = {'Nº DO REGIME ESPECIAL': '9.053/2026', 'CNPJ REQUERENTE': '00.000.000/0000-00'}
    r = edicao.editar_registro(conn, 'regime', antiga,
                               {'CNPJ REQUERENTE': '11.222.333/0001-81', 'VIGÊNCIA DO RE': '6 meses'})
    assert r['chave_trocada'] is True
    assert set(r['alterados']) == {'CNPJ REQUERENTE', 'VIGÊNCIA DO RE'}
    linhas = armazenamento.buscar_regimes(conn)
    assert len(linhas) == 1 and linhas[0]['CNPJ REQUERENTE'] == '11.222.333/0001-81'
    nova = dict(zip(CHAVE_R, ('9.053/2026', '11.222.333/0001-81')))
    assert len(armazenamento.historico_de(conn, 'regimes', nova)) == 1     # histórico foi junto
    assert armazenamento.historico_de(conn, 'regimes', antiga) == []
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R,
                                        tuple(antiga.values())) == tuple(nova.values())
    # só o campo não-chave vira "ajuste"
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, tuple(nova.values())) == ['VIGÊNCIA DO RE']


def test_chave_em_conflito_e_recusada_sem_alterar_nada(tmp_path):
    conn = _conn(tmp_path)
    outro = _regime(**{'Nº DO REGIME ESPECIAL': '1/2026', 'EMPRESA': 'Outra'})
    armazenamento.salvar_regimes(conn, [_regime(), outro])
    with pytest.raises(edicao.ChaveEmConflito):
        edicao.editar_registro(conn, 'regime', _chave_regime(),
                               {'Nº DO REGIME ESPECIAL': '1/2026', 'EMPRESA': 'Mudou'})
    assert {r['EMPRESA'] for r in armazenamento.buscar_regimes(conn)} == {'Alfa Ltda', 'Outra'}
    assert conn.execute("SELECT COUNT(*) FROM historico").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM chaves_substituidas").fetchone()[0] == 0


def test_chave_em_branco_e_recusada(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    with pytest.raises(edicao.ChaveVazia):
        edicao.editar_registro(conn, 'regime', _chave_regime(), {'CNPJ REQUERENTE': '   '})
    assert armazenamento.buscar_regimes(conn)[0]['CNPJ REQUERENTE'] == '11.222.333/0001-81'


def test_falha_no_meio_da_edicao_nao_deixa_gravacao_parcial(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime(**{'CNPJ REQUERENTE': '00'})])

    def quebra(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(armazenamento, 'mover_chave_auxiliares', quebra)
    with pytest.raises(RuntimeError):
        edicao.editar_registro(conn, 'regime',
                               {'Nº DO REGIME ESPECIAL': '9.053/2026', 'CNPJ REQUERENTE': '00'},
                               {'CNPJ REQUERENTE': '11', 'EMPRESA': 'Mudou'})
    salvo = armazenamento.buscar_regimes(conn)[0]
    assert salvo['CNPJ REQUERENTE'] == '00' and salvo['EMPRESA'] == 'Alfa Ltda'
    assert conn.execute("SELECT COUNT(*) FROM historico").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ajustes").fetchone()[0] == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_edicao.py -q`
Expected: FAIL — `ImportError: cannot import name 'edicao' from 'core'`.

- [ ] **Step 3: Implementar**

A edição é uma transação única: histórico, `UPDATE`, ajustes, troca de chave e apelido ou tudo ou nada.

Crie `core/edicao.py`:

```python
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
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_edicao.py -q` — Expected: PASS.
Depois a suíte inteira: `python -m pytest -q` — Expected: **324 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/edicao.py tests/test_edicao.py
git commit -m "feat: editar um ato já gravado, inclusive a chave, com histórico manual"
```

(Sem `Co-Authored-By`: o commit sai só em nome do usuário.)

---

### Task 3: Reimportação que respeita ajustes e apelidos

**Files:**
- Modify: `core/armazenamento.py` (`_upsert`, `salvar_*`, `persistir_lote`)
- Modify: `tests/test_edicao.py`

**Interfaces:**
- Consumes: `resolver_chave`, `ajustes_de`, `limpar_ajustes`, `registrar_alteracao` (Tarefa 1); `edicao.editar_registro` (Tarefa 2).
- Produces: `salvar_consultas(conn, registros, sobrescrever=())`, `salvar_regimes(conn, registros, sobrescrever=())` e `persistir_lote(conn, lote, sobrescrever=())` — `sobrescrever` é um conjunto de tuplas com os valores da chave (em `persistir_lote`: `('consulta'|'regime', *valores_da_chave)`). Os formatos de retorno **não mudam**.

- [ ] **Step 1: Escrever os testes que falham**

Cobrem: o PDF mantém o campo ajustado e atualiza o resto; `sobrescrever` aplica o PDF e limpa os ajustes; o PDF com a chave antiga cai no ato de chave corrigida (inclusive após duas correções seguidas); `persistir_lote` repassa `sobrescrever` e mantém o formato de retorno.

Acrescente ao final de `tests/test_edicao.py`:

```python
# --- reimportação: proteção dos ajustes e apelidos --------------------------
def test_reimportar_mantem_o_campo_ajustado_a_mao_e_atualiza_o_resto(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})

    resultado = armazenamento.salvar_regimes(
        conn, [_regime(**{'VIGÊNCIA DO RE': '', 'EMENTA': 'ementa nova'})])

    assert resultado == {'novos': 0, 'atualizados': 1}
    salvo = armazenamento.buscar_regimes(conn)[0]
    assert salvo['VIGÊNCIA DO RE'] == '12 meses'          # ajuste mantido
    assert salvo['EMENTA'] == 'ementa nova'               # o resto segue o PDF
    hist = armazenamento.historico_de(conn, 'regimes', _chave_regime())
    assert [h['origem'] for h in hist] == ['importacao', 'manual']   # mais recente primeiro
    assert hist[0]['campos_alterados'] == ['EMENTA']


def test_sobrescrever_aplica_o_pdf_e_limpa_os_ajustes(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    chave = tuple(_chave_regime().values())

    armazenamento.salvar_regimes(conn, [_regime(**{'VIGÊNCIA DO RE': ''})], sobrescrever={chave})

    assert armazenamento.buscar_regimes(conn)[0]['VIGÊNCIA DO RE'] == ''
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, chave) == []
    ultimo = armazenamento.historico_de(conn, 'regimes', _chave_regime())[0]
    assert ultimo['origem'] == 'importacao'
    assert ultimo['registro_anterior']['VIGÊNCIA DO RE'] == '12 meses'


def test_reimportar_o_pdf_original_cai_no_ato_com_a_chave_corrigida(tmp_path):
    conn = _conn(tmp_path)
    errado = _regime(**{'CNPJ REQUERENTE': '00.000.000/0000-00'})
    armazenamento.salvar_regimes(conn, [errado])
    edicao.editar_registro(conn, 'regime',
                           {c: errado[c] for c in CHAVE_R},
                           {'CNPJ REQUERENTE': '11.222.333/0001-81'})

    resultado = armazenamento.salvar_regimes(conn, [{**errado, 'EMENTA': 'ementa do PDF 2'}])

    assert resultado == {'novos': 0, 'atualizados': 1}            # não duplicou
    linhas = armazenamento.buscar_regimes(conn)
    assert len(linhas) == 1
    assert linhas[0]['CNPJ REQUERENTE'] == '11.222.333/0001-81'   # a chave corrigida prevalece
    assert linhas[0]['EMENTA'] == 'ementa do PDF 2'


def test_duas_correcoes_seguidas_de_chave_reimportando_a_primeira(tmp_path):
    conn = _conn(tmp_path)
    a = _regime(**{'CNPJ REQUERENTE': 'A'})
    armazenamento.salvar_regimes(conn, [a])
    num = '9.053/2026'
    edicao.editar_registro(conn, 'regime', {'Nº DO REGIME ESPECIAL': num, 'CNPJ REQUERENTE': 'A'},
                           {'CNPJ REQUERENTE': 'B'})
    edicao.editar_registro(conn, 'regime', {'Nº DO REGIME ESPECIAL': num, 'CNPJ REQUERENTE': 'B'},
                           {'CNPJ REQUERENTE': 'C'})
    armazenamento.salvar_regimes(conn, [a])
    linhas = armazenamento.buscar_regimes(conn)
    assert len(linhas) == 1 and linhas[0]['CNPJ REQUERENTE'] == 'C'


def test_persistir_lote_repassa_o_sobrescrever_e_mantem_o_formato_do_retorno(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    lote = pipeline.Lote(regimes=[_regime(**{'VIGÊNCIA DO RE': ''})])

    r1 = armazenamento.persistir_lote(conn, lote)
    assert r1 == {'consultas': {'novos': 0, 'atualizados': 0},
                  'regimes': {'novos': 0, 'atualizados': 1}}
    assert armazenamento.buscar_regimes(conn)[0]['VIGÊNCIA DO RE'] == '12 meses'

    chave = ('regime', *tuple(_chave_regime().values()))
    armazenamento.persistir_lote(conn, lote, sobrescrever=[chave])
    assert armazenamento.buscar_regimes(conn)[0]['VIGÊNCIA DO RE'] == ''
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_edicao.py tests/test_armazenamento.py -q`
Expected: FAIL — campo ajustado sobrescrito pela reimportação, e `TypeError: ... got an unexpected keyword argument 'sobrescrever'`.

- [ ] **Step 3: Implementar**

Os testes antigos de upsert/histórico (`test_armazenamento.py`, `test_pipeline.py`) continuam valendo sem alteração: sem ajustes, o comportamento é o mesmo de antes.

Em `core/armazenamento.py` (o upsert passa a resolver apelidos de chave e a proteger campos ajustados), substitua tudo desde a linha `def _upsert(` até a linha anterior a `def historico_de(` por:

```python
def _upsert(conn: sqlite3.Connection, tabela: str, colunas: list, chave: list,
            registros: list, sobrescrever=()) -> dict:
    """Upsert por chave natural. Devolve {'novos': N, 'atualizados': M}.

    - A chave recebida passa por `resolver_chave`: se o ato teve a chave corrigida
      à mão, a reimportação cai nele (não duplica).
    - Quando o ato já existe e algum campo (fora a chave) muda, a linha anterior
      vai para `historico` antes da atualização.
    - Campos ajustados à mão (tabela `ajustes`) NÃO são sobrescritos, salvo se a
      chave do ato estiver em `sobrescrever` (conjunto de tuplas de valores da
      chave atual): aí o valor do PDF vence e os ajustes do ato são apagados.
    """
    sobrescrever = {tuple(k) for k in sobrescrever}
    colnames = ', '.join(f'"{c}"' for c in colunas)
    placeholders = ', '.join('?' for _ in colunas)
    insert_sql = f'INSERT INTO {tabela} ({colnames}) VALUES ({placeholders})'
    where = ' AND '.join(f'"{c}" = ?' for c in chave)
    novos = atualizados = 0
    for reg in registros:
        recebida = tuple(reg.get(c, '') for c in chave)
        chave_valores = resolver_chave(conn, tabela, chave, recebida)
        reg = {**reg, **dict(zip(chave, chave_valores))}
        anterior = conn.execute(
            f'SELECT * FROM {tabela} WHERE {where}', chave_valores).fetchone()
        if anterior is None:
            conn.execute(insert_sql, tuple(reg.get(c, '') for c in colunas))
            novos += 1
            continue
        atualizados += 1
        sobrescreve = chave_valores in sobrescrever
        protegidos = set() if sobrescreve else set(
            ajustes_de(conn, tabela, chave, chave_valores))
        a_atualizar = [c for c in colunas if c not in chave and c not in protegidos]
        alterados = [c for c in a_atualizar
                     if str(anterior[c] or '') != str(reg.get(c, '') or '')]
        if alterados:
            registrar_alteracao(conn, tabela, chave, chave_valores, anterior, alterados)
            sets = ', '.join(f'"{c}" = ?' for c in alterados)
            conn.execute(f'UPDATE {tabela} SET {sets} WHERE {where}',
                         [reg.get(c, '') for c in alterados] + list(chave_valores))
        if sobrescreve:
            limpar_ajustes(conn, tabela, chave, chave_valores)
    conn.commit()
    return {'novos': novos, 'atualizados': atualizados}
```

Em `core/armazenamento.py`, substitua tudo desde a linha `def salvar_consultas(` até a linha anterior a `_CAMPOS_BUSCA_CONSULTAS` por:

```python
def salvar_consultas(conn: sqlite3.Connection, registros: list, sobrescrever=()) -> dict:
    """Upsert por CHAVE_CONSULTAS. Devolve {'novos': N, 'atualizados': M}.
    `sobrescrever`: tuplas (Ano, Nº da Consulta) cujos ajustes manuais o PDF vence."""
    return _upsert(conn, 'consultas', COLUNAS_CONSULTAS, CHAVE_CONSULTAS, registros,
                   sobrescrever)


def salvar_regimes(conn: sqlite3.Connection, registros: list, sobrescrever=()) -> dict:
    """Upsert por CHAVE_REGIMES. Devolve {'novos': N, 'atualizados': M}.
    `sobrescrever`: tuplas (Nº DO REGIME ESPECIAL, CNPJ REQUERENTE) cujos ajustes
    manuais o PDF vence."""
    return _upsert(conn, 'regimes', COLUNAS_REGIMES, CHAVE_REGIMES, registros,
                   sobrescrever)
```

Em `core/armazenamento.py` (é a última função do arquivo), substitua tudo desde a linha `def persistir_lote(` até o fim do arquivo por:

```python
def persistir_lote(conn: sqlite3.Connection, lote: Lote, sobrescrever=()) -> dict:
    """Persiste um core.pipeline.Lote inteiro (consultas + regimes) de uma vez.

    `sobrescrever`: itens ('consulta'|'regime', *valores_da_chave) cujos ajustes
    manuais o PDF deve vencer; os demais atos ajustados mantêm o valor do ajuste."""
    por_tipo = {'consulta': set(), 'regime': set()}
    for item in sobrescrever:
        por_tipo[item[0]].add(tuple(item[1:]))
    resultado = {
        'consultas': salvar_consultas(conn, lote.consultas, por_tipo['consulta']),
        'regimes': salvar_regimes(conn, lote.regimes, por_tipo['regime'])}
    registrar_importacoes(conn, lote.importacoes)
    return resultado
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_edicao.py tests/test_armazenamento.py -q` — Expected: PASS.
Depois a suíte inteira: `python -m pytest -q` — Expected: **329 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/armazenamento.py tests/test_edicao.py
git commit -m "feat: reimportação mantém campos ajustados e segue apelidos de chave"
```

(Sem `Co-Authored-By`: o commit sai só em nome do usuário.)

---

### Task 4: Conflitos entre ajustes manuais e o PDF

**Files:**
- Modify: `core/edicao.py`
- Modify: `tests/test_edicao.py`

**Interfaces:**
- Consumes: `armazenamento.resolver_chave`, `ajustes_de`, `buscar_detalhe`; `pipeline.Lote`.
- Produces: `edicao.rotulo_do_ato(tipo, chave_dict) -> str` ('Consulta 001/2026' / 'RE 9.053/2026'); `edicao.chave_do_item(item) -> tuple` (formato de `sobrescrever`); `edicao.ajustes_em_conflito(conn, lote) -> list[{'tipo','chave','rotulo','campos':[{'campo','atual','pdf'}]}]` (só lê o banco).

- [ ] **Step 1: Escrever os testes que falham**

Cobrem: só entram atos ajustados cujo valor do PDF **difere**; ato sem ajuste, igual ao PDF ou ainda não gravado não gera conflito; a chave do item é a **atual** mesmo quando o PDF traz a chave antiga.

Acrescente ao final de `tests/test_edicao.py`:

```python
# --- conflitos para a análise ----------------------------------------------
def test_conflitos_listam_so_atos_ajustados_cujo_pdf_diverge(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime(), _regime(**{'Nº DO REGIME ESPECIAL': '2/2026'})])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})

    lote = pipeline.Lote(regimes=[_regime(**{'VIGÊNCIA DO RE': ''}),
                                  _regime(**{'Nº DO REGIME ESPECIAL': '2/2026'})])
    itens = edicao.ajustes_em_conflito(conn, lote)

    assert len(itens) == 1
    assert itens[0]['tipo'] == 'regime' and itens[0]['rotulo'] == 'RE 9.053/2026'
    assert itens[0]['campos'] == [{'campo': 'VIGÊNCIA DO RE', 'atual': '12 meses', 'pdf': ''}]
    assert edicao.chave_do_item(itens[0]) == ('regime', '9.053/2026', '11.222.333/0001-81')


def test_sem_divergencia_ou_sem_ato_gravado_nao_ha_conflito(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [_regime()])
    edicao.editar_registro(conn, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    igual = pipeline.Lote(regimes=[_regime(**{'VIGÊNCIA DO RE': '12 meses'})])
    novo = pipeline.Lote(regimes=[_regime(**{'Nº DO REGIME ESPECIAL': '7/2026'})])
    assert edicao.ajustes_em_conflito(conn, igual) == []
    assert edicao.ajustes_em_conflito(conn, novo) == []


def test_conflito_usa_a_chave_atual_quando_o_pdf_traz_a_chave_antiga(tmp_path):
    conn = _conn(tmp_path)
    errado = _regime(**{'CNPJ REQUERENTE': '00'})
    armazenamento.salvar_regimes(conn, [errado])
    edicao.editar_registro(conn, 'regime', {c: errado[c] for c in CHAVE_R},
                           {'CNPJ REQUERENTE': '11', 'EMPRESA': 'Corrigida'})
    itens = edicao.ajustes_em_conflito(conn, pipeline.Lote(regimes=[errado]))
    assert len(itens) == 1
    assert itens[0]['chave']['CNPJ REQUERENTE'] == '11'
    assert itens[0]['campos'] == [{'campo': 'EMPRESA', 'atual': 'Corrigida', 'pdf': 'Alfa Ltda'}]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_edicao.py -q`
Expected: FAIL — `AttributeError: module 'core.edicao' has no attribute 'ajustes_em_conflito'`.

- [ ] **Step 3: Implementar**


Acrescente ao final de `core/edicao.py`:

```python
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
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_edicao.py -q` — Expected: PASS.
Depois a suíte inteira: `python -m pytest -q` — Expected: **332 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/edicao.py tests/test_edicao.py
git commit -m "feat: detectar atos com ajuste manual em conflito com o PDF"
```

(Sem `Co-Authored-By`: o commit sai só em nome do usuário.)

---

### Task 5: Ajustar na análise (em memória) e gravar os ajustes

**Files:**
- Modify: `core/pipeline.py` (`Lote`)
- Modify: `core/edicao.py`
- Modify: `core/armazenamento.py`
- Modify: `tests/test_edicao.py`

**Interfaces:**
- Consumes: `edicao._validar`, erros e `TIPOS` (Tarefa 2); `persistir_lote` (Tarefa 3).
- Produces: `Lote.ajustados: dict` e `Lote.chaves_substituidas: list`; `edicao.ajustar_no_lote(lote, tipo, chave_atual, novos) -> {'alterados', 'chave_trocada'}` (mesmas regras de `editar_registro`, sem banco; mantém `lote.origem` em dia); `persistir_lote` grava `ajustes` e apelidos do que foi ajustado na análise.

- [ ] **Step 1: Escrever os testes que falham**

Cobrem: campo ajustado no lote, troca de chave acompanhando origem/ajustes/apelidos, recusas (chave repetida na análise, vazia, ato inexistente — sem alterar nada), e gravar o lote ajustado cria ajustes e apelidos que **protegem a reimportação seguinte**.

Acrescente ao final de `tests/test_edicao.py`:

```python
# --- edição na análise (em memória) ----------------------------------------
def _lote_com_regimes():
    lote = pipeline.Lote(regimes=[_regime(), _regime(**{'Nº DO REGIME ESPECIAL': '2/2026'})])
    lote.origem[('regime', '9.053/2026', '11.222.333/0001-81')] = 'a.pdf'
    return lote


def test_ajustar_campo_no_lote_altera_o_registro_e_anota_o_ajuste():
    lote = _lote_com_regimes()
    r = edicao.ajustar_no_lote(lote, 'regime', _chave_regime(), {'VIGÊNCIA DO RE': '12 meses'})
    assert r == {'alterados': ['VIGÊNCIA DO RE'], 'chave_trocada': False}
    assert lote.regimes[0]['VIGÊNCIA DO RE'] == '12 meses'
    assert lote.ajustados == {('regime', '9.053/2026', '11.222.333/0001-81'): {'VIGÊNCIA DO RE'}}
    assert lote.chaves_substituidas == []


def test_ajustar_a_chave_no_lote_acompanha_origem_ajustes_e_apelidos():
    lote = _lote_com_regimes()
    edicao.ajustar_no_lote(lote, 'regime', _chave_regime(), {'EMENTA': 'x'})
    r = edicao.ajustar_no_lote(lote, 'regime', _chave_regime(),
                               {'CNPJ REQUERENTE': '99.999.999/0001-99'})
    assert r['chave_trocada'] is True
    nova = ('9.053/2026', '99.999.999/0001-99')
    assert lote.regimes[0]['CNPJ REQUERENTE'] == '99.999.999/0001-99'
    assert lote.origem[('regime', *nova)] == 'a.pdf'
    assert ('regime', '9.053/2026', '11.222.333/0001-81') not in lote.origem
    assert lote.ajustados == {('regime', *nova): {'EMENTA'}}              # o ajuste acompanhou a chave
    assert lote.chaves_substituidas == [('regime', ('9.053/2026', '11.222.333/0001-81'), nova)]


def test_ajustar_no_lote_recusa_chave_repetida_vazia_e_ato_inexistente():
    lote = _lote_com_regimes()
    with pytest.raises(edicao.ChaveEmConflito):
        edicao.ajustar_no_lote(lote, 'regime', _chave_regime(), {'Nº DO REGIME ESPECIAL': '2/2026',
                                                                  'CNPJ REQUERENTE': '11.222.333/0001-81'})
    with pytest.raises(edicao.ChaveVazia):
        edicao.ajustar_no_lote(lote, 'regime', _chave_regime(), {'CNPJ REQUERENTE': ''})
    with pytest.raises(edicao.RegistroInexistente):
        edicao.ajustar_no_lote(lote, 'regime', {'Nº DO REGIME ESPECIAL': 'x', 'CNPJ REQUERENTE': 'y'}, {})
    assert lote.regimes[0]['CNPJ REQUERENTE'] == '11.222.333/0001-81'      # nada mudou


def test_gravar_o_lote_ajustado_cria_ajustes_e_apelidos_que_protegem_a_reimportacao(tmp_path):
    conn = _conn(tmp_path)
    lote = _lote_com_regimes()
    edicao.ajustar_no_lote(lote, 'regime', _chave_regime(),
                           {'VIGÊNCIA DO RE': '12 meses', 'CNPJ REQUERENTE': '55'})
    armazenamento.persistir_lote(conn, lote)

    nova = ('9.053/2026', '55')
    assert armazenamento.ajustes_de(conn, 'regimes', CHAVE_R, nova) == ['VIGÊNCIA DO RE']
    assert armazenamento.resolver_chave(conn, 'regimes', CHAVE_R,
                                        ('9.053/2026', '11.222.333/0001-81')) == nova
    # reimportar o PDF original (chave antiga, sem vigência) não desfaz o ajuste nem duplica
    armazenamento.salvar_regimes(conn, [_regime(**{'VIGÊNCIA DO RE': ''})])
    linhas = [r for r in armazenamento.buscar_regimes(conn) if r['Nº DO REGIME ESPECIAL'] == '9.053/2026']
    assert len(linhas) == 1 and linhas[0]['CNPJ REQUERENTE'] == '55'
    assert linhas[0]['VIGÊNCIA DO RE'] == '12 meses'
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_edicao.py tests/test_pipeline.py -q`
Expected: FAIL — `AttributeError: module 'core.edicao' has no attribute 'ajustar_no_lote'`.

- [ ] **Step 3: Implementar**

Os campos novos de `Lote` têm valor padrão, então todo `Lote(...)` existente continua válido.

Em `core/pipeline.py`, substitua:

```python
    # ('consulta', Ano, Nº) / ('regime', Nº RE, CNPJ) -> nome do 1º arquivo de origem
    origem: dict = field(default_factory=dict)
```

por:

```python
    # ('consulta', Ano, Nº) / ('regime', Nº RE, CNPJ) -> nome do 1º arquivo de origem
    origem: dict = field(default_factory=dict)
    # edições feitas na ANÁLISE (antes de gravar): ('consulta'|'regime', *chave) -> campos
    # ajustados (fora a chave), e as chaves corrigidas [(tipo, antiga, nova), ...]
    ajustados: dict = field(default_factory=dict)
    chaves_substituidas: list = field(default_factory=list)
```

Acrescente ao final de `core/edicao.py`:

```python
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
```

Em `core/armazenamento.py` (entra o helper que grava os ajustes e as chaves corrigidas na análise), substitua:

```python
def persistir_lote(conn: sqlite3.Connection, lote: Lote, sobrescrever=()) -> dict:
```

por:

```python
_TABELA_E_CHAVE = {'consulta': ('consultas', CHAVE_CONSULTAS),
                   'regime': ('regimes', CHAVE_REGIMES)}


def _gravar_ajustes_do_lote(conn: sqlite3.Connection, lote: Lote) -> None:
    """Leva para o banco o que o administrador ajustou na ANÁLISE: os campos
    editados viram `ajustes` do ato e as chaves corrigidas viram apelidos."""
    for (tipo, *valores), campos in lote.ajustados.items():
        tabela, chave = _TABELA_E_CHAVE[tipo]
        atual = resolver_chave(conn, tabela, chave, tuple(valores))
        juntar_ajustes(conn, tabela, chave, atual, sorted(campos))
    for tipo, antiga, nova in lote.chaves_substituidas:
        tabela, chave = _TABELA_E_CHAVE[tipo]
        registrar_substituicao(conn, tabela, chave, tuple(antiga), tuple(nova))
    conn.commit()


def persistir_lote(conn: sqlite3.Connection, lote: Lote, sobrescrever=()) -> dict:
```

Em `core/armazenamento.py` (dentro de `persistir_lote`), substitua:

```python
    registrar_importacoes(conn, lote.importacoes)
    return resultado
```

por:

```python
    _gravar_ajustes_do_lote(conn, lote)
    registrar_importacoes(conn, lote.importacoes)
    return resultado
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_edicao.py tests/test_pipeline.py -q` — Expected: PASS.
Depois a suíte inteira: `python -m pytest -q` — Expected: **336 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/pipeline.py core/edicao.py core/armazenamento.py tests/test_edicao.py
git commit -m "feat: ajustar atos na análise e gravar os ajustes junto com o lote"
```

(Sem `Co-Authored-By`: o commit sai só em nome do usuário.)

---

### Task 6: `Execucao` e CLI: `--sobrescrever-ajustes`

**Files:**
- Modify: `core/execucao.py`
- Modify: `processar.py`
- Modify: `tests/test_execucao.py`
- Modify: `tests/test_processar.py`

**Interfaces:**
- Consumes: `persistir_lote(..., sobrescrever)` (Tarefa 3); `edicao.ajustes_em_conflito` e `edicao.chave_do_item` (Tarefa 4).
- Produces: `Execucao.gravar(conn, sobrescrever=())`; CLI: opção `--sobrescrever-ajustes`; a CLI lista os ajustes em conflito (e mostra se foram mantidos ou sobrescritos); `--simular` mostra os conflitos **sem criar nem migrar o banco**.

- [ ] **Step 1: Escrever os testes que falham**

Cobrem: reimportar mantém o ajuste e avisa; `--sobrescrever-ajustes` aplica o PDF; `--simular` informa sem alterar o banco; `--simular` em banco do schema antigo não o migra; `Execucao.gravar` repassa `sobrescrever`.

Acrescente ao final de `tests/test_execucao.py`:

```python
def test_gravar_repassa_o_sobrescrever_ao_armazenamento(tmp_path):
    from core import edicao
    ex = Execucao()
    ex.carregar([(CONSULTAS_PDF, "c.pdf")])
    with armazenamento.sessao(str(tmp_path / "s.db")) as conn:
        ex.gravar(conn)
        edicao.editar_registro(conn, 'consulta', {'Ano': '2026', 'Nº da Consulta': '001'},
                               {'Protocolo': 'AJUSTADO'})
        ex.gravar(conn)                                         # padrão: mantém o ajuste
        assert [r for r in armazenamento.buscar_consultas(conn)
                if r['Nº da Consulta'] == '001'][0]['Protocolo'] == 'AJUSTADO'
        ex.gravar(conn, sobrescrever=[('consulta', '2026', '001')])
        assert [r for r in armazenamento.buscar_consultas(conn)
                if r['Nº da Consulta'] == '001'][0]['Protocolo'] != 'AJUSTADO'
```

Acrescente ao final de `tests/test_processar.py`:

```python
# --- ajustes manuais x reimportação ----------------------------------------
def _importa_e_ajusta_o_protocolo(tmp_path):
    """Importa o PDF de consultas e, como o administrador faria na interface, ajusta o
    Protocolo da consulta 001/2026. Devolve (pasta, banco)."""
    from core import edicao
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")
    banco = tmp_path / "m.db"
    assert processar.main([str(pasta), "--banco", str(banco)]) == 0
    conn = armazenamento.conectar(str(banco))
    edicao.editar_registro(conn, 'consulta', {'Ano': '2026', 'Nº da Consulta': '001'},
                           {'Protocolo': 'AJUSTADO'})
    conn.close()
    return pasta, banco


def _protocolo(banco):
    conn = armazenamento.conectar(str(banco))
    try:
        achado = [r for r in armazenamento.buscar_consultas(conn) if r['Nº da Consulta'] == '001']
        return achado[0]['Protocolo']
    finally:
        conn.close()


def test_reimportar_mantem_o_ajuste_manual_e_avisa(tmp_path, capsys):
    pasta, banco = _importa_e_ajusta_o_protocolo(tmp_path)
    capsys.readouterr()

    codigo = processar.main([str(pasta), "--banco", str(banco)])

    assert codigo == 0
    assert _protocolo(banco) == 'AJUSTADO'
    saida = capsys.readouterr().out
    assert "Ajustes manuais encontrados" in saida and "Consulta 001/2026" in saida
    assert "mantidos" in saida


def test_sobrescrever_ajustes_aplica_o_valor_do_pdf(tmp_path, capsys):
    pasta, banco = _importa_e_ajusta_o_protocolo(tmp_path)
    capsys.readouterr()

    codigo = processar.main([str(pasta), "--banco", str(banco), "--sobrescrever-ajustes"])

    assert codigo == 0
    assert _protocolo(banco) == '25.152.191-3'
    assert "Valor do PDF aplicado" in capsys.readouterr().out


def test_simular_mostra_os_ajustes_sem_alterar_o_banco(tmp_path, capsys):
    pasta, banco = _importa_e_ajusta_o_protocolo(tmp_path)
    capsys.readouterr()
    conn = armazenamento.conectar(str(banco))
    antes = conn.execute("SELECT COUNT(*) FROM historico").fetchone()[0]
    conn.close()

    codigo = processar.main([str(pasta), "--banco", str(banco), "--simular"])

    assert codigo == 0
    assert "Ajustes manuais encontrados" in capsys.readouterr().out
    assert _protocolo(banco) == 'AJUSTADO'
    conn = armazenamento.conectar(str(banco))
    assert conn.execute("SELECT COUNT(*) FROM historico").fetchone()[0] == antes
    conn.close()


def test_simular_em_banco_do_schema_antigo_nao_o_migra(tmp_path):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")
    banco = tmp_path / "antigo.db"
    conn = armazenamento.conectar(str(banco))
    armazenamento.criar_esquema(conn)
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()

    assert processar.main([str(pasta), "--banco", str(banco), "--simular"]) == 0

    conn = armazenamento.conectar(str(banco))
    assert armazenamento.versao_do_schema(conn) == 2      # continua como estava
    conn.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_execucao.py tests/test_processar.py -q`
Expected: FAIL — a CLI ignora `--sobrescrever-ajustes` e não imprime os conflitos; `Execucao.gravar() got an unexpected keyword argument 'sobrescrever'`.

- [ ] **Step 3: Implementar**


Em `core/execucao.py`, substitua:

```python
        return self.lote

    def gravar(self, conn) -> dict:
        """Persiste o lote carregado. Devolve o resumo de novos/atualizados."""
        self._progresso('gravacao', 0, 1, '')
        resultado = armazenamento.persistir_lote(conn, self.lote)
        self._progresso('gravacao', 1, 1, '')
        return resultado
```

por:

```python
        return self.lote

    def gravar(self, conn, sobrescrever=()) -> dict:
        """Persiste o lote carregado. Devolve o resumo de novos/atualizados.

        `sobrescrever`: itens ('consulta'|'regime', *chave) cujos ajustes manuais o
        PDF deve vencer (ver edicao.ajustes_em_conflito); os demais ajustes são mantidos."""
        self._progresso('gravacao', 0, 1, '')
        resultado = armazenamento.persistir_lote(conn, self.lote, sobrescrever)
        self._progresso('gravacao', 1, 1, '')
        return resultado
```

Em `processar.py`, substitua:

```python
"""CLI: python processar.py <pasta_com_pdfs> [--banco arquivo.db] [--xlsx saida.xlsx]
                            [--dedup primeira|completo|recente] [--simular]

Persiste no banco por padrão. A planilha é uma exportação opcional (--xlsx).
--simular lê e diagnostica os PDFs sem gravar nada.

Códigos de saída: 0 = tudo certo; 1 = uso incorreto, nenhum PDF, planilha
```

por:

```python
"""CLI: python processar.py <pasta_com_pdfs> [--banco arquivo.db] [--xlsx saida.xlsx]
                            [--dedup primeira|completo|recente] [--simular]
                            [--sobrescrever-ajustes]

Persiste no banco por padrão. A planilha é uma exportação opcional (--xlsx).
--simular lê e diagnostica os PDFs sem gravar nada.
Atos que o administrador ajustou à mão na interface MANTÊM o valor ajustado ao
reimportar; --sobrescrever-ajustes faz o valor do PDF vencer em todos eles.

Códigos de saída: 0 = tudo certo; 1 = uso incorreto, nenhum PDF, planilha
```

Em `processar.py`, substitua:

```python
_USO = ("Uso: python processar.py <pasta_com_pdfs> [--banco arquivo.db] "
        "[--xlsx saida.xlsx] [--dedup primeira|completo|recente] [--simular]")
```

por:

```python
_USO = ("Uso: python processar.py <pasta_com_pdfs> [--banco arquivo.db] "
        "[--xlsx saida.xlsx] [--dedup primeira|completo|recente] [--simular] "
        "[--sobrescrever-ajustes]")
```

Em `processar.py`, substitua:

```python
        return 1
    simular = "--simular" in argv

    pdfs = sorted(glob.glob(os.path.join(pasta, "*.pdf")))
```

por:

```python
        return 1
    simular = "--simular" in argv
    sobrescrever_ajustes = "--sobrescrever-ajustes" in argv

    pdfs = sorted(glob.glob(os.path.join(pasta, "*.pdf")))
```

Em `processar.py`, substitua:

```python
    # testes, por exemplo — nunca dispare um pip install.
    garantir_dependencias(DEPS_CLI)
    from core import armazenamento, log, pipeline, planilha  # noqa: E402
    from core.execucao import Execucao  # noqa: E402
```

por:

```python
    # testes, por exemplo — nunca dispare um pip install.
    garantir_dependencias(DEPS_CLI)
    from core import armazenamento, edicao, log, pipeline, planilha  # noqa: E402
    from core.execucao import Execucao  # noqa: E402
```

Em `processar.py`, substitua:

```python
    if simular:
        print("\nSimulação: nada foi gravado no banco.")
        return _finaliza(erros)
```

por:

```python
    if simular:
        _conflitos_na_simulacao(armazenamento, edicao, banco, lote)
        print("\nSimulação: nada foi gravado no banco.")
        return _finaliza(erros)
```

Em `processar.py`, substitua:

```python
    try:
        with armazenamento.sessao(banco) as conn:
            resultado = execucao.gravar(conn)
    except armazenamento.SchemaMaisNovo as erro:
        print(f"\n{erro}", file=sys.stderr)
```

por:

```python
    try:
        with armazenamento.sessao(banco) as conn:
            conflitos = edicao.ajustes_em_conflito(conn, lote)
            _imprime_conflitos(conflitos, sobrescrever_ajustes)
            sobrescrever = ([edicao.chave_do_item(i) for i in conflitos]
                            if sobrescrever_ajustes else ())
            resultado = execucao.gravar(conn, sobrescrever)
    except armazenamento.SchemaMaisNovo as erro:
        print(f"\n{erro}", file=sys.stderr)
```

Em `processar.py`, substitua:

```python
        print(f"  Planilha:  {xlsx}")
    return _finaliza(erros)
```

por:

```python
        print(f"  Planilha:  {xlsx}")
    return _finaliza(erros)


def _imprime_conflitos(conflitos: list, sobrescrevendo: bool) -> None:
    """Atos com ajuste manual cujo valor difere do PDF."""
    if not conflitos:
        return
    print(f"\nAjustes manuais encontrados em {len(conflitos)} ato(s):")
    for item in conflitos:
        for c in item['campos']:
            print(f"  - {item['rotulo']} · {c['campo']}: ajustado {c['atual']!r} | PDF {c['pdf']!r}")
    print("Valor do PDF aplicado (--sobrescrever-ajustes)." if sobrescrevendo else
          "Valores ajustados mantidos. Use --sobrescrever-ajustes para aplicar o PDF.")


def _conflitos_na_simulacao(armazenamento, edicao, banco, lote) -> None:
    """Na simulação só LÊ: se o banco já existe e está no schema atual, mostra os
    ajustes que seriam mantidos; nunca cria nem migra o banco."""
    if not os.path.exists(armazenamento.caminho_do_banco(banco)):
        return
    with armazenamento.aberta(banco) as conn:
        if armazenamento.versao_do_schema(conn) < armazenamento.SCHEMA_VERSAO:
            return
        _imprime_conflitos(edicao.ajustes_em_conflito(conn, lote), False)
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_execucao.py tests/test_processar.py -q` — Expected: PASS.
Depois a suíte inteira: `python -m pytest -q` — Expected: **341 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/execucao.py processar.py tests/test_execucao.py tests/test_processar.py
git commit -m "feat: CLI mantém ajustes manuais e ganha --sobrescrever-ajustes"
```

(Sem `Co-Authored-By`: o commit sai só em nome do usuário.)

---

### Task 7: Formulário reutilizável e ajustes do ato

**Files:**
- Create: `interface/formularios.py`
- Modify: `core/consulta.py`
- Create: `tests/test_formularios.py`
- Modify: `tests/test_consulta.py`

**Interfaces:**
- Consumes: `armazenamento.ajustes_de` (Tarefa 1); `consulta.CHAVES`, `_TABELAS` (código existente).
- Produces: `formularios.prefixo_de(tipo, valores_chave) -> str`; `formularios.campo_longo`, `altura_da_area`, `campos_alterados`; `formularios.formulario_registro(tipo, registro, colunas, chave, *, prefixo, rotulo_envio='Salvar alterações', ao_enviar=None, args=())` (com `ao_enviar` o Streamlit chama o callback antes do script; sem ele devolve `{coluna: texto}` ao enviar); `consulta.ajustes(conn, tipo, registro) -> list`.

- [ ] **Step 1: Escrever os testes que falham**

Cobrem os auxiliares puros do formulário e `consulta.ajustes`. O comportamento dos widgets é coberto pelos testes de interface das Tarefas 8 e 9.

Crie `tests/test_formularios.py`:

```python
# tests/test_formularios.py
from interface import formularios


def test_prefixo_e_unico_por_ato():
    a = formularios.prefixo_de('regime', ['9.053/2026', '11'])
    b = formularios.prefixo_de('regime', ['9.053/2026', '22'])
    c = formularios.prefixo_de('consulta', ['2026', '001'])
    assert a == "edit|regime|9.053/2026|11"
    assert len({a, b, c}) == 3


def test_campos_de_texto_corrido_viram_area_de_texto():
    assert formularios.campo_longo('EMENTA', '')
    assert formularios.campo_longo('Resposta', 'curta')
    assert not formularios.campo_longo('EMPRESA', 'Alfa Ltda')
    assert formularios.campo_longo('EMPRESA', 'x' * 81)      # valor longo também vira área


def test_altura_da_area_cresce_com_o_texto_dentro_de_limites():
    assert formularios.altura_da_area('') == 110
    assert formularios.altura_da_area('linha\n' * 5) > formularios.altura_da_area('curta')
    assert formularios.altura_da_area('x\n' * 500) == 360


def test_campos_alterados_ignora_espacos_das_pontas_e_none():
    original = {'EMPRESA': 'Alfa', 'EMENTA': None, 'DATA': '2026-01-01'}
    novos = {'EMPRESA': '  Alfa  ', 'EMENTA': '', 'DATA': '2026-02-01'}
    assert formularios.campos_alterados(original, novos) == ['DATA']
```

Acrescente ao final de `tests/test_consulta.py`:

```python
def test_ajustes_do_ato_por_tipo(tmp_path):
    ato = {'ANO': '2026', 'Nº DO REGIME ESPECIAL': '9.053/2026',
           'CNPJ REQUERENTE': '11.222.333/0001-81', 'EMENTA': 'x'}
    with armazenamento.sessao(str(tmp_path / "a.db")) as c:
        armazenamento.salvar_regimes(c, [ato])
        armazenamento.juntar_ajustes(c, 'regimes', consulta.CHAVES['regime'],
                                     ('9.053/2026', '11.222.333/0001-81'), ['EMENTA'])
        assert consulta.ajustes(c, 'regime', ato) == ['EMENTA']
        assert consulta.ajustes(c, 'regime', {**ato, 'CNPJ REQUERENTE': '00'}) == []
        with pytest.raises(ValueError):
            consulta.ajustes(c, 'outro', ato)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_formularios.py tests/test_consulta.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'interface.formularios'` e `AttributeError: module 'core.consulta' has no attribute 'ajustes'`.

- [ ] **Step 3: Implementar**


Crie `interface/formularios.py`:

```python
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
```

Em `core/consulta.py`, substitua:

```python
    return {'consultas': n_consultas, 'regimes': n_regimes, 'anos': anos,
            'ultima_importacao': ultima}
```

por:

```python
    return {'consultas': n_consultas, 'regimes': n_regimes, 'anos': anos,
            'ultima_importacao': ultima}


def ajustes(conn, tipo: str, registro: dict) -> list:
    """Campos deste ato que o administrador ajustou à mão (lista vazia se nenhum)."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")
    chave = CHAVES[tipo]
    return armazenamento.ajustes_de(conn, _TABELAS[tipo], chave,
                                    tuple(registro.get(c, '') for c in chave))
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_formularios.py tests/test_consulta.py -q` — Expected: PASS.
Depois a suíte inteira: `python -m pytest -q` — Expected: **346 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add interface/formularios.py core/consulta.py tests/test_formularios.py tests/test_consulta.py
git commit -m "feat: formulário reutilizável de edição de atos e consulta dos ajustes"
```

(Sem `Co-Authored-By`: o commit sai só em nome do usuário.)

---

### Task 8: Editar pelo detalhe (só administrador)

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `edicao.editar_registro` e os erros (Tarefa 2); `formularios.*` e `consulta.ajustes` (Tarefa 7).
- Produces: No detalhe do ato (aba Consultar), o **administrador** vê **Editar**; o formulário traz todos os campos, salva dentro do `on_click`, mostra erro de regra no próprio detalhe e, com sucesso, fecha o detalhe e avisa por toast. O detalhe mostra os campos ajustados e, no histórico, se cada alteração foi *importação* ou *ajuste manual*.

- [ ] **Step 1: Escrever os testes que falham**

No AppTest a seleção da linha injetada **não persiste entre execuções** (um navegador mantém): os testes reinjetam a linha 0 antes de cada interação (helper `_linha_0`). Cobrem: o perfil Consulta não vê **Editar**; o admin edita um campo, corrige a chave, recebe erro de chave em conflito sem gravar, e cancela.

Em `tests/test_app.py` (imports no topo), substitua:

```python
from core import acesso, armazenamento  # noqa: E402
```

por:

```python
from core import acesso, armazenamento, diagnostico, edicao, pipeline  # noqa: E402
from interface import formularios  # noqa: E402
```

Acrescente ao final de `tests/test_app.py`:

```python
# --- edição manual (detalhe e análise) --------------------------------------
REGIME = {'ANO': '2026', 'DATA': '2026-03-01', 'Nº DO REGIME ESPECIAL': '9.053/2026',
          'EMPRESA': 'Alfa Ltda', 'CNPJ REQUERENTE': '11.222.333/0001-81',
          'VIGÊNCIA DO RE': '', 'EMENTA': 'ementa original'}
PREFIXO = formularios.prefixo_de('regime', [REGIME['Nº DO REGIME ESPECIAL'],
                                            REGIME['CNPJ REQUERENTE']])


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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_app.py -q`
Expected: FAIL — `KeyError: 'editar-registro'` (o botão ainda não existe).

- [ ] **Step 3: Implementar**

Este é o ponto sensível do plano: o salvamento **precisa** ser o `on_click` do formulário (ver Global Constraints).

Em `app.py`, substitua:

```python
from core import acesso, armazenamento, consulta, log, planilha  # noqa: E402
```

por:

```python
from core import acesso, armazenamento, consulta, edicao, log, planilha  # noqa: E402
```

Em `app.py`, substitua:

```python
from interface import design  # noqa: E402
```

por:

```python
from interface import design, formularios  # noqa: E402
```

Em `app.py` (o aviso (toast) deixado antes de um `st.rerun()` aparece na execução seguinte), substitua:

```python
if perfil == acesso.PERFIL_ADMIN:
    aba_processar, aba_consultar = st.tabs(
```

por:

```python
_aviso = st.session_state.pop("aviso", None)   # mensagem deixada antes de um st.rerun()
if _aviso:
    st.toast(_aviso, icon=":material/check_circle:")

if perfil == acesso.PERFIL_ADMIN:
    aba_processar, aba_consultar = st.tabs(
```

Em `app.py` (dentro de `_fecha_selecao_da_tabela`: fechar o detalhe também encerra uma edição), substitua:

```python
    st.session_state["tabela-resultados"] = {"selection": {"rows": []}}
```

por:

```python
    st.session_state["tabela-resultados"] = {"selection": {"rows": []}}
    st.session_state.pop("editando", None)
```

Em `app.py` (o detalhe ganha o modo de edição e os rótulos de origem no histórico), substitua tudo desde a linha `@st.dialog("Detalhes"` até a linha anterior a `def _analisar(` por:

```python
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


@st.dialog("Detalhes", width="large", on_dismiss=_fecha_selecao_da_tabela)
def _mostra_detalhe(tipo: str, registro: dict, colunas: list, historico=(),
                    pode_editar: bool = False, ajustes=()):
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
    if pode_editar:
        st.button("Editar", key="editar-registro", icon=":material/edit:",
                  on_click=_comecar_edicao, args=(prefixo,))
    if historico:
        with st.expander(f"Histórico de alterações ({len(historico)})"):
            for h in historico:
                quem = "ajuste manual" if h.get("origem") == "manual" else "importação"
                st.markdown(f"**{h['alterado_em']}** · {quem} (versão {h['versao_app']}) — "
                            f"campos alterados: {', '.join(h['campos_alterados'])}")
```

Em `app.py` (dentro de `_renderiza_consultar`), substitua:

```python
                _mostra_detalhe(tipo, completo, cols_do_tipo,
                                consulta.historico(conn, tipo, completo))
```

por:

```python
                _mostra_detalhe(tipo, completo, cols_do_tipo,
                                consulta.historico(conn, tipo, completo),
                                pode_editar=(perfil == acesso.PERFIL_ADMIN),
                                ajustes=consulta.ajustes(conn, tipo, completo))
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_app.py -q` — Expected: PASS.
Depois a suíte inteira: `python -m pytest -q` — Expected: **352 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: administrador edita consultas e regimes pelo detalhe"
```

(Sem `Co-Authored-By`: o commit sai só em nome do usuário.)

---

### Task 9: Ajustar na análise e escolher o que sobrescrever

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `edicao.ajustar_no_lote`, `ajustes_em_conflito`, `chave_do_item` (Tarefas 4 e 5); `persistir_lote(..., sobrescrever)` (Tarefa 3); formulário (Tarefa 7); `_avisar` (Tarefa 8).
- Produces: Na análise: expansor **Ajustar um ato antes de gravar** (formulário do ato escolhido; o diagnóstico é refeito na hora); aviso dos atos que já têm ajuste manual com uma caixa *Sobrescrever com o PDF* **desmarcada** por padrão e a tabela valor ajustado × valor do PDF; **Gravar** repassa as caixas marcadas.

- [ ] **Step 1: Escrever os testes que falham**

Cobrem: o aviso `A303` some depois de corrigir a vigência; chave repetida na análise mostra erro e não altera; gravar protege o ajuste na reimportação; conflito aparece desmarcado e **gravar mantém** o ajuste; marcar a caixa **grava o valor do PDF**.

Acrescente ao final de `tests/test_app.py`:

```python
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
    at.text_input(key=f"{PREFIXO}|VIGÊNCIA DO RE").input("12 meses")
    at.button(key=f"{PREFIXO}|enviar").click().run(timeout=30)
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
    at.text_input(key=f"{PREFIXO}|VIGÊNCIA DO RE").input("12 meses")
    at.button(key=f"{PREFIXO}|enviar").click().run(timeout=30)
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
    at.text_input(key=f"{PREFIXO}|Nº DO REGIME ESPECIAL").input("1/2026")
    at.button(key=f"{PREFIXO}|enviar").click().run(timeout=30)
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_app.py -q`
Expected: FAIL — `KeyError` ao procurar o campo do formulário na análise e `KeyError: 'sobrescrever|regime|...'`.

- [ ] **Step 3: Implementar**


Em `app.py`, substitua:

```python
from core import acesso, armazenamento, consulta, edicao, log, planilha  # noqa: E402
```

por:

```python
from core import acesso, armazenamento, consulta, diagnostico, edicao, log, planilha  # noqa: E402
```

Em `app.py`, substitua:

```python
def _persistir(lote):
    """Grava o lote no banco e devolve o resumo de novos/atualizados."""
    with armazenamento.sessao(_CAMINHO_BANCO) as conn:
        return armazenamento.persistir_lote(conn, lote)
```

por:

```python
def _persistir(lote, sobrescrever=()):
    """Grava o lote no banco e devolve o resumo de novos/atualizados."""
    with armazenamento.sessao(_CAMINHO_BANCO) as conn:
        return armazenamento.persistir_lote(conn, lote, sobrescrever)
```

Em `app.py` (análise com editor, escolha dos ajustes a sobrescrever e `_gravar` com `sobrescrever`), substitua tudo desde a linha `def _analisar(` até a linha anterior a `def _mostra_resumo(` por:

```python
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
            prefixo=formularios.prefixo_de(tipo, [chave_atual[c] for c in chave]),
            rotulo_envio="Salvar ajuste")
        if novos is not None:
            try:
                r = edicao.ajustar_no_lote(lote, tipo, chave_atual, novos)
            except (edicao.ChaveEmConflito, edicao.ChaveVazia, edicao.RegistroInexistente) as erro:
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
```

Em `app.py` (no botão Gravar), substitua:

```python
                st.session_state["resultado"] = _gravar(analise)
```

por:

```python
                st.session_state["resultado"] = _gravar(analise, _sobrescrever_marcados(analise))
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_app.py -q` — Expected: PASS.
Depois a suíte inteira: `python -m pytest -q` — Expected: **357 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: ajustar atos na análise e escolher quais ajustes o PDF sobrescreve"
```

(Sem `Co-Authored-By`: o commit sai só em nome do usuário.)

---

### Task 10: Documentação, versão 0.8.0 e verificação final

**Files:**
- Modify: `core/versao.py`, `CHANGELOG.md`, `README.md`

**Interfaces:** nenhuma nova; fecha o plano.

- [ ] **Step 1: Atualizar versão, changelog e README**

Substitua o conteúdo de `core/versao.py`:

```python
# core/versao.py
"""Versão do app. Gravada no banco (histórico e importações) para saber com
qual versão do parser cada dado foi extraído."""

VERSAO_APP = "0.8.0"
```

Em `CHANGELOG.md`, substitua:

```markdown
# Histórico de versões

## 0.7.0
```

por:

```markdown
# Histórico de versões

## 0.8.0
- **Edição manual** pelo administrador, de consultas e regimes: no detalhe do ato (aba Consultar) e na análise, antes de gravar. Todos os campos podem ser editados, inclusive a chave (número e CNPJ).
- Corrigir a chave não duplica o ato: a chave antiga vira apelido, então reimportar o PDF original cai no ato corrigido.
- Campos ajustados à mão **não são sobrescritos** pela reimportação. A análise lista os atos em conflito e o administrador marca quais sobrescrever com o PDF; na CLI, `--sobrescrever-ajustes`.
- O histórico do ato diz se a alteração veio de **importação** ou de **ajuste manual**.
- Schema 3 (`ajustes`, `chaves_substituidas` e `origem` no histórico); bancos do schema 2 migram sozinhos.

## 0.7.0
```

Em `README.md`, substitua:

```markdown
Versão atual: **0.7.0**
```

por:

```markdown
Versão atual: **0.8.0**
```

Em `README.md`, substitua:

```markdown
O banco guarda a versão do schema em `PRAGMA user_version` (atual: 2).
```

por:

```markdown
O banco guarda a versão do schema em `PRAGMA user_version` (atual: 3).
```

Em `README.md`, substitua:

```markdown
A suíte tem 297 testes e leva cerca de um minuto.
```

por:

```markdown
A suíte tem 357 testes e leva cerca de um minuto.
```

Em `README.md`, substitua:

```markdown
                    [--dedup primeira|completo|recente] [--simular]
```
```

por:

```markdown
                    [--dedup primeira|completo|recente] [--simular]
                    [--sobrescrever-ajustes]
```
```

Em `README.md`, substitua:

```markdown
| `--simular` | lê e diagnostica os PDFs **sem gravar nada** |
```

por:

```markdown
| `--simular` | lê e diagnostica os PDFs **sem gravar nada** |
| `--sobrescrever-ajustes` | o valor do PDF vence também nos campos que o administrador ajustou à mão (por padrão o ajuste é mantido e a CLI avisa) |
```

Em `README.md`, substitua:

```markdown
## 4. Linha de comando
```

por:

```markdown
### Edição manual (Administrador)
O administrador corrige consultas e regimes em dois momentos:

- **Depois de gravado**: na aba Consultar, abra o detalhe do ato e use **Editar**. Todos os campos são editáveis, inclusive a chave (número e CNPJ do regime; ano e número da consulta). Se a chave nova já pertencer a outro ato, a edição é recusada e nada muda.
- **Na análise, antes de gravar**: em *Ajustar um ato antes de gravar*, escolha o ato apontado nos avisos e corrija os campos. O diagnóstico é refeito na hora e nada vai ao banco até **Gravar**.

Cada edição guarda a versão anterior no histórico do ato (origem *ajuste manual*) e marca os campos editados como **ajustados**. Ao reimportar o PDF:

- os campos ajustados **não são sobrescritos** — a análise lista os atos em conflito e você marca *Sobrescrever com o PDF* só nos que quiser (por padrão, nenhum);
- se a chave foi corrigida, o PDF original **cai no ato corrigido** em vez de criar um duplicado.

## 4. Linha de comando
```

- [ ] **Step 2: Rodar a suíte inteira**

Run: `python -m pytest -q` — Expected: **357 testes passando**, saída limpa.

- [ ] **Step 3: Verificação manual no navegador** (o `AppTest` não simula upload nem o visual real)

Rode `python iniciar.py` (ou `Mapeador.bat`), entre como **Administrador** e confira:

1. **Detalhe**: na aba Consultar, selecione um regime com vigência vazia → **Editar** → preencha a vigência → **Salvar alterações**. O detalhe fecha, aparece o aviso, o campo fica corrigido e o histórico mostra *ajuste manual*. Os campos ajustados aparecem sob o título do detalhe.
2. **Chave**: edite o CNPJ de um regime para um valor livre (funciona, e o aviso diz que a chave foi corrigida) e depois para o CNPJ de **outro** regime (deve recusar com mensagem e não gravar nada).
3. **Análise**: envie um PDF com avisos `A303`/`A304`, abra **Ajustar um ato antes de gravar**, corrija o ato apontado: o aviso some e nada é gravado até **Gravar no banco**.
4. **Reimportação**: reenvie o mesmo PDF. A análise deve avisar que há atos com ajuste manual, com a caixa *Sobrescrever com o PDF* **desmarcada**. Grave sem marcar → o ajuste continua. Reenvie e marque → o valor do PDF volta.
5. **Perfil Consulta**: entre como Consulta e abra um detalhe — **não** pode haver o botão **Editar**.
6. **Visual**: confira nos temas claro e escuro o formulário no diálogo (largura, áreas de texto grandes, botão **Salvar alterações** e **Cancelar**) e o expansor da análise — o plano não inspeciona o visual desses dois formulários.
7. **CLI**: `python processar.py <pasta> --simular` lista os ajustes em conflito sem alterar o banco; sem a opção, o ajuste é mantido; com `--sobrescrever-ajustes`, vence o PDF.

- [ ] **Step 4: Commit**

```bash
git add core/versao.py CHANGELOG.md README.md
git commit -m "docs: edição manual de atos (README, changelog e versão 0.8.0)"
```

(Sem `Co-Authored-By`.) Depois é decisão do usuário mesclar em `main` e publicar.

---

## Fora deste plano

- **Excluir** atos e **editar em lote** (várias linhas de uma vez).
- **Restaurar** uma versão anterior com um clique (o histórico guarda a versão anterior, mas não há botão de desfazer).
- **Quem** editou: hoje há um único perfil administrador com senha, então o histórico registra *ajuste manual*, mas não o autor.
- Revalidar na edição manual as regras do diagnóstico (CNPJ válido, data ISO): o administrador pode digitar qualquer valor; o diagnóstico da análise é refeito, mas a edição de um ato já gravado não bloqueia valores fora do padrão.
