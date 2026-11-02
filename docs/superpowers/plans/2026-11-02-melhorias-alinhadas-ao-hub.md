# Melhorias alinhadas ao padrão do hub — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao `mapeador_pr` o desenho do hub Martinelli Ferramentas (motor com progresso, diagnóstico antes de gravar, proveniência, logging, schema versionado, CLI com códigos de saída) sem quebrar o comportamento hoje testado.

**Architecture:** O motor continua em `core/` e `parsers/` (sem Streamlit). Entra uma camada nova `core/execucao.py` por cima de `pipeline` + `armazenamento` + `diagnostico`, usada pela CLI e pela interface. O banco ganha tabelas aditivas (`historico`, `importacoes`) e `PRAGMA user_version`; nada existente é removido nem renomeado. A interface passa a ter o fluxo "Analisar → Gravar".

**Tech Stack:** Python 3.10+, SQLite (`sqlite3`, biblioteca padrão), pdfplumber, openpyxl, Streamlit 1.63, pytest.

**Spec:** `docs/superpowers/specs/2026-11-02-melhorias-alinhadas-ao-hub-design.md`

## Global Constraints

- Não adicionar dependência de terceiros. Só biblioteca padrão além de pdfplumber, openpyxl, streamlit e pytest.
- `requirements.txt` hoje: `pdfplumber>=0.11.9,<0.12`, `openpyxl>=3.1.5,<3.2`, `streamlit>=1.50,<2`. Única mudança permitida: piso do streamlit sobe para `>=1.63` (Tarefa 6; é a versão em que `st.download_button` aceita função, verificada).
- O servidor continua só em `127.0.0.1`; a telemetria do Streamlit continua desligada.
- Textos, mensagens e comentários em português, com acentuação correta.
- `salvar_consultas`/`salvar_regimes` devolvem exatamente `{'novos': N, 'atualizados': M}`; `persistir_lote` devolve exatamente `{'consultas': {...}, 'regimes': {...}}`. **Não** acrescentar chaves.
- Cada linha de `lote.arquivos` tem exatamente 6 chaves: `Arquivo, Tipo, Consultas, Regimes, Descartes, Erro`. **Não** acrescentar chaves.
- Os dicts de registro (consultas/regimes) produzidos pelos parsers **não ganham chaves**.
- `st.session_state["resultado"]` mantém as chaves `arquivos, consultas, regimes, descartes, mapeamento, xlsx`.
- `armazenamento._CAMINHO_PADRAO` continua existindo e terminando em `mapeamento.db`.
- A CLI mantém `Uso:` em stdout com código de saída 1 para uso incorreto; código 1 também para planilha aberta no Excel; código **2** quando algum PDF falhar.
- Cada tarefa termina com a suíte inteira verde: `pytest -q`. Linha de base ao escrever este plano: 184 testes passando.
- Commits em português, no formato `tipo: descrição` (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), um por tarefa.

## Review Focus

Entradas e condições que a spec implica mas nenhuma tarefa testaria por si só; cada linha tem o teste na tarefa dona do código:

1. **Busca com `%`, `_` ou só espaços** — `10%` deve achar o texto literal "10%" (não "tudo que começa com 10"); `campo_um` não casa `campoXum`; texto só de espaços equivale a "sem filtro". → Tarefa 7.
2. **PDF corrompido no meio de um lote** — os PDFs bons são gravados, a CLI sai com 2 e o erro aparece com o nome do arquivo e o motivo (CLI e interface). → Tarefas 14 e 15.
3. **O mesmo ato em dois PDFs com conteúdo diferente** — cada critério (`primeira`, `completo`, `recente`) escolhe o registro esperado, inclusive nos empates. → Tarefa 9.
4. **Banco antigo (sem `user_version`) e banco de versão mais nova** — o antigo é atualizado sem perder dados; o mais novo é recusado com mensagem clara, sem ser alterado. → Tarefa 4.
5. **Reimportação** — reimportar registro idêntico não cria histórico; reimportar com campo diferente cria exatamente uma linha com o campo alterado e o valor anterior. → Tarefa 11.

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `core/versao.py` | criar | `VERSAO_APP` (única fonte da versão) |
| `core/texto.py` | criar | `normalizar()` para busca sem acento/caixa |
| `core/log.py` | criar | `configurar_log(pasta)` — log rotativo |
| `core/diagnostico.py` | criar | `cnpj_valido()` e `diagnosticar(lote)` |
| `core/execucao.py` | criar | classe `Execucao` (carregar → diagnosticar → gravar) |
| `core/armazenamento.py` | modificar | pasta de dados, `aberta`/`sessao`, `user_version`, busca normalizada, listagem leve, `historico`, `importacoes` |
| `core/consulta.py` | modificar | `exportar_busca`, `buscar_lista`, `detalhe`, `historico` |
| `core/pipeline.py` | modificar | critérios de dedup, `Lote.importacoes/origem`, hash, log |
| `processar.py` | modificar | usa `Execucao`; `--dedup`, `--simular`; código 2; erros por arquivo |
| `app.py` | modificar | `sessao`, exportação sob demanda, listagem leve, fluxo Analisar → Gravar, histórico |
| `Mapeador.bat`, `README.md`, `CHANGELOG.md`, `.gitignore`, `requirements.txt` | modificar/criar | `.venv`, documentação, versão |
| `tests/conftest.py` | criar | isola `MAPEADOR_DADOS` e fecha handlers de log |

Dependências entre tarefas: 1 → 2 → 3 → 4; 5 depende de 2; 6 depende de 3; 7, 8 dependem de 3; 9 e 10 independentes entre si; 11 depende de 4 e 10; 12 depende de 10; 13 depende de 9, 11, 12 e 5; 14 e 15 dependem de 13 (15 também de 8 e 11); 16 por último.

---

### Task 1: Preparação — branch, isolamento de testes e versão

**Files:**
- Create: `core/versao.py`
- Create: `tests/conftest.py`
- Create: `tests/test_versao.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `core.versao.VERSAO_APP: str` (formato `X.Y.Z`); variável de ambiente `MAPEADOR_DADOS` isolada em todo teste (usada a partir da Tarefa 2).

- [ ] **Step 1: Criar a branch e conferir a linha de base**

```bash
git switch -c melhorias-alinhadas-ao-hub
pytest -q
```
Expected: todos os testes passam (184 ao escrever este plano). Se algo falhar já aqui, **pare** e avise: o plano assume base verde.

- [ ] **Step 2: Escrever o teste que falha**

`tests/test_versao.py`:
```python
import re

from core.versao import VERSAO_APP


def test_versao_segue_o_formato_semantico():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSAO_APP)
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `pytest tests/test_versao.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'core.versao'`.

- [ ] **Step 4: Implementar**

`core/versao.py`:
```python
# core/versao.py
"""Versão do app. Gravada no banco (histórico e importações) para saber com
qual versão do parser cada dado foi extraído."""

VERSAO_APP = "0.7.0"
```

`tests/conftest.py`:
```python
# tests/conftest.py
import logging

import pytest


@pytest.fixture(autouse=True)
def _dados_isolados(monkeypatch, tmp_path_factory):
    """Banco e logs de qualquer teste vão para uma pasta temporária, nunca
    para a raiz do projeto. Ao fim, solta o arquivo de log (no Windows um
    handler aberto impede apagar a pasta temporária)."""
    pasta = tmp_path_factory.mktemp("dados")
    monkeypatch.setenv("MAPEADOR_DADOS", str(pasta))
    yield
    logger = logging.getLogger("mapeador")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
```

Acrescentar ao final de `.gitignore`:
```
logs/
.venv/
```

- [ ] **Step 5: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa (o teste novo incluído).

- [ ] **Step 6: Commit**

```bash
git add core/versao.py tests/conftest.py tests/test_versao.py .gitignore
git commit -m "chore: versão do app e isolamento da pasta de dados nos testes"
```

---

### Task 2: Pasta de dados configurável

**Files:**
- Modify: `core/armazenamento.py` (bloco `_RAIZ`/`_CAMINHO_PADRAO`/`conectar`)
- Test: `tests/test_armazenamento.py`

**Interfaces:**
- Consumes: nada.
- Produces: `armazenamento.pasta_dados() -> str` (cria a pasta se não existir); `armazenamento.caminho_do_banco(caminho_bd: str | None = None) -> str` (precedência: argumento > `MAPEADOR_BANCO` > `<pasta_dados>/mapeamento.db`); `armazenamento.conectar(caminho_bd=None)` passa a usar `caminho_do_banco`.

- [ ] **Step 1: Escrever os testes que falham** (acrescentar a `tests/test_armazenamento.py`)

```python
import os


def test_pasta_dados_usa_a_variavel_e_cria_a_pasta(tmp_path, monkeypatch):
    alvo = tmp_path / "dados" / "fundo"
    monkeypatch.setenv("MAPEADOR_DADOS", str(alvo))
    assert armazenamento.pasta_dados() == str(alvo)
    assert alvo.is_dir()


def test_pasta_dados_sem_variavel_e_a_raiz_do_projeto(monkeypatch):
    monkeypatch.delenv("MAPEADOR_DADOS", raising=False)
    assert armazenamento.pasta_dados() == armazenamento._RAIZ


def test_caminho_do_banco_respeita_a_precedencia(tmp_path, monkeypatch):
    monkeypatch.setenv("MAPEADOR_DADOS", str(tmp_path))
    monkeypatch.delenv("MAPEADOR_BANCO", raising=False)
    assert armazenamento.caminho_do_banco() == os.path.join(str(tmp_path), "mapeamento.db")
    monkeypatch.setenv("MAPEADOR_BANCO", str(tmp_path / "x.db"))
    assert armazenamento.caminho_do_banco() == str(tmp_path / "x.db")
    assert armazenamento.caminho_do_banco("explicito.db") == "explicito.db"


def test_conectar_sem_caminho_cai_na_pasta_de_dados(tmp_path, monkeypatch):
    monkeypatch.setenv("MAPEADOR_DADOS", str(tmp_path))
    monkeypatch.delenv("MAPEADOR_BANCO", raising=False)
    conn = armazenamento.conectar()
    conn.execute("CREATE TABLE t (x)")
    conn.commit()
    conn.close()
    assert (tmp_path / "mapeamento.db").exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_armazenamento.py -k "pasta_dados or caminho_do_banco or cai_na_pasta" -v`
Expected: FAIL com `AttributeError: module 'core.armazenamento' has no attribute 'pasta_dados'`.

- [ ] **Step 3: Implementar**

Em `core/armazenamento.py`, substituir a função `conectar` atual:
```python
def conectar(caminho_bd: str | None = None) -> sqlite3.Connection:
    """Abre (ou cria) o banco. Sem `caminho_bd`, usa mapeamento.db na raiz
    do projeto."""
    conn = sqlite3.connect(caminho_bd or _CAMINHO_PADRAO)
    conn.row_factory = sqlite3.Row
    return conn
```
por:
```python
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
    return conn
```
(`_RAIZ` e `_CAMINHO_PADRAO` ficam como estão.)

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa.

- [ ] **Step 5: Commit**

```bash
git add core/armazenamento.py tests/test_armazenamento.py
git commit -m "feat: pasta de dados configurável (MAPEADOR_DADOS) e banco por MAPEADOR_BANCO também na CLI"
```

---

### Task 3: Conexão aberta e fechada a cada uso (`aberta`/`sessao`)

**Files:**
- Modify: `core/armazenamento.py`
- Modify: `app.py` (`_conexao`, `_processar`, bloco `with aba_consultar:`)
- Test: `tests/test_armazenamento.py`

**Interfaces:**
- Consumes: `armazenamento.conectar`, `armazenamento.criar_esquema` (Tarefa 2 e código existente).
- Produces: `armazenamento.aberta(caminho_bd=None)` (context manager: abre e **fecha**); `armazenamento.sessao(caminho_bd=None)` (igual a `aberta`, mais `criar_esquema`); em `app.py`, `_persistir(lote) -> dict` e `_renderiza_consultar(conn)`.

- [ ] **Step 1: Escrever os testes que falham** (acrescentar a `tests/test_armazenamento.py`)

```python
import sqlite3

import pytest


def test_aberta_fecha_a_conexao_ao_sair(tmp_path):
    with armazenamento.aberta(str(tmp_path / "a.db")) as conn:
        conn.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_sessao_cria_o_esquema_e_fecha_mesmo_com_erro(tmp_path):
    caminho = str(tmp_path / "s.db")
    with pytest.raises(RuntimeError):
        with armazenamento.sessao(caminho) as conn:
            assert armazenamento.buscar_consultas(conn) == []
            raise RuntimeError("falha")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_armazenamento.py -k "aberta or sessao" -v`
Expected: FAIL com `AttributeError: ... no attribute 'aberta'`.

- [ ] **Step 3: Implementar em `core/armazenamento.py`**

Acrescentar `from contextlib import contextmanager` junto aos imports e, logo após `conectar`:
```python
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
```
(`criar_esquema` é definida mais abaixo no arquivo; isso é válido porque só é chamada em tempo de execução.)

- [ ] **Step 4: Ajustar `app.py`**

(a) Substituir a função:
```python
def _conexao():
    conn = armazenamento.conectar(_CAMINHO_BANCO)
    armazenamento.criar_esquema(conn)
    return conn
```
por:
```python
def _persistir(lote):
    """Grava o lote no banco e devolve o resumo de novos/atualizados."""
    with armazenamento.sessao(_CAMINHO_BANCO) as conn:
        return armazenamento.persistir_lote(conn, lote)
```
(b) Em `_processar`, trocar a linha
```python
    mapeamento = armazenamento.persistir_lote(_conexao(), lote)
```
por:
```python
    mapeamento = _persistir(lote)
```
(c) No bloco final, trocar as duas primeiras linhas
```python
with aba_consultar:
    conn = _conexao()

```
por:
```python
def _renderiza_consultar(conn):
```
(o corpo, que já está indentado com 4 espaços, **não muda**) e acrescentar ao fim do arquivo:
```python


with aba_consultar:
    with armazenamento.sessao(_CAMINHO_BANCO) as conn:
        _renderiza_consultar(conn)
```

- [ ] **Step 5: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa (inclusive os 18 de `tests/test_app.py`).

- [ ] **Step 6: Commit**

```bash
git add core/armazenamento.py app.py tests/test_armazenamento.py
git commit -m "fix: fecha a conexão do banco a cada rerun da interface"
```

---

### Task 4: Versão do schema (`PRAGMA user_version`)

**Files:**
- Modify: `core/armazenamento.py` (`criar_esquema`)
- Modify: `app.py` (logo após o portão de perfil)
- Test: `tests/test_armazenamento.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `armazenamento.criar_esquema`, `armazenamento.sessao` (Tarefa 3).
- Produces: `armazenamento.SCHEMA_VERSAO: int` (= 1 nesta tarefa; a Tarefa 11 sobe para 2); `armazenamento.versao_do_schema(conn) -> int`; `armazenamento.SchemaMaisNovo(RuntimeError)`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_armazenamento.py`:
```python
def test_criar_esquema_grava_a_versao_do_schema(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.versao_do_schema(conn) == armazenamento.SCHEMA_VERSAO


def test_banco_antigo_sem_versao_e_atualizado_sem_perder_dados(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "antigo.db"))
    conn.execute('CREATE TABLE consultas ("Ano" TEXT, "Nº da Consulta" TEXT, '
                 'UNIQUE("Ano", "Nº da Consulta"))')
    conn.execute("INSERT INTO consultas VALUES (?, ?)", ("2025", "007"))
    conn.commit()
    assert armazenamento.versao_do_schema(conn) == 0

    armazenamento.criar_esquema(conn)

    assert armazenamento.versao_do_schema(conn) == armazenamento.SCHEMA_VERSAO
    assert armazenamento.buscar_consultas(conn)[0]["Nº da Consulta"] == "007"


def test_banco_de_versao_mais_nova_e_recusado_sem_ser_alterado(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "novo.db"))
    conn.execute(f"PRAGMA user_version = {armazenamento.SCHEMA_VERSAO + 1}")
    conn.commit()

    with pytest.raises(armazenamento.SchemaMaisNovo) as exc:
        armazenamento.criar_esquema(conn)

    assert str(armazenamento.SCHEMA_VERSAO + 1) in str(exc.value)
    criou = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'consultas'").fetchone()
    assert criou is None
```
Em `tests/test_app.py`:
```python
def test_banco_de_versao_mais_nova_mostra_erro_amigavel():
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    conn.execute(f"PRAGMA user_version = {armazenamento.SCHEMA_VERSAO + 1}")
    conn.commit()
    conn.close()

    at = _app().run(timeout=30)

    assert not at.exception
    assert any("mais nova" in e.value for e in at.error)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_armazenamento.py tests/test_app.py -k "versao" -v`
Expected: FAIL (`AttributeError: ... 'versao_do_schema'` / `SCHEMA_VERSAO`).

- [ ] **Step 3: Implementar em `core/armazenamento.py`**

Acrescentar logo após `COLUNAS_REGIMES`:
```python
SCHEMA_VERSAO = 1


class SchemaMaisNovo(RuntimeError):
    """O banco foi criado por uma versão mais nova da ferramenta."""


def versao_do_schema(conn: sqlite3.Connection) -> int:
    return conn.execute('PRAGMA user_version').fetchone()[0]
```
Substituir `criar_esquema`:
```python
def criar_esquema(conn: sqlite3.Connection) -> None:
    """Cria as tabelas de consultas e regimes se não existirem. Idempotente."""
    _criar_tabela(conn, 'consultas', COLUNAS_CONSULTAS, CHAVE_CONSULTAS)
    _criar_tabela(conn, 'regimes', COLUNAS_REGIMES, CHAVE_REGIMES)
    conn.commit()
```
por:
```python
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
    if atual != SCHEMA_VERSAO:
        conn.execute(f'PRAGMA user_version = {SCHEMA_VERSAO}')
    conn.commit()
```

- [ ] **Step 4: Ajustar `app.py`**

Logo após o bloco (portão de perfil)
```python
perfil = st.session_state.get("perfil")
if perfil not in (acesso.PERFIL_CONSULTA, acesso.PERFIL_ADMIN):
    _tela_inicial()
    st.stop()
```
acrescentar:
```python

try:
    with armazenamento.sessao(_CAMINHO_BANCO):
        pass
except armazenamento.SchemaMaisNovo as erro:
    st.error(str(erro))
    st.stop()
```

- [ ] **Step 5: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa.

- [ ] **Step 6: Commit**

```bash
git add core/armazenamento.py app.py tests/test_armazenamento.py tests/test_app.py
git commit -m "feat: versão do schema do banco (user_version) e recusa de banco mais novo"
```

---

### Task 5: Logging em arquivo

**Files:**
- Create: `core/log.py`
- Create: `tests/test_log.py`
- Modify: `core/pipeline.py` (log nas falhas)
- Modify: `processar.py`, `app.py` (configurar o log)
- Test: `tests/test_pipeline.py`, `tests/test_processar.py`

**Interfaces:**
- Consumes: `armazenamento.pasta_dados()` (Tarefa 2).
- Produces: `core.log.configurar_log(pasta: str) -> logging.Logger` (logger `"mapeador"`, arquivo `<pasta>/logs/app.log`, rotativo 1 MB × 3; idempotente); `pipeline` registra falhas no logger `"mapeador"`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_log.py`:
```python
from core import log


def test_configurar_log_cria_o_arquivo_e_registra(tmp_path):
    logger = log.configurar_log(str(tmp_path))
    logger.info("olá, log")
    for handler in logger.handlers:
        handler.flush()
    conteudo = (tmp_path / "logs" / "app.log").read_text(encoding="utf-8")
    assert "olá, log" in conteudo


def test_configurar_log_duas_vezes_nao_duplica_o_handler(tmp_path):
    log.configurar_log(str(tmp_path))
    logger = log.configurar_log(str(tmp_path))
    com_arquivo = [h for h in logger.handlers if getattr(h, "baseFilename", None)]
    assert len(com_arquivo) == 1
```
Em `tests/test_pipeline.py` (acrescentar `import logging` no topo):
```python
def test_falha_ao_processar_e_registrada_no_log_com_traceback(tmp_path, caplog):
    ruim = tmp_path / "corrompido.pdf"
    ruim.write_bytes(b"isto nao e um pdf")
    with caplog.at_level(logging.ERROR, logger="mapeador"):
        pipeline.processar_arquivo(pipeline.Lote(), str(ruim), "corrompido.pdf")
    assert any("corrompido.pdf" in r.getMessage() and r.exc_info
               for r in caplog.records)
```
Em `tests/test_processar.py`:
```python
def test_processar_grava_o_log_na_pasta_de_dados(tmp_path):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")

    processar.main([str(pasta), "--banco", str(tmp_path / "m.db")])

    assert os.path.exists(os.path.join(os.environ["MAPEADOR_DADOS"], "logs", "app.log"))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_log.py tests/test_pipeline.py tests/test_processar.py -k "log" -v`
Expected: FAIL (`ModuleNotFoundError: core.log`; os outros por falta de log/arquivo).

- [ ] **Step 3: Implementar**

`core/log.py`:
```python
# core/log.py
"""Log do app: <pasta de dados>/logs/app.log (rotativo, ~1 MB × 3 arquivos).

Só biblioteca padrão e sem dependência de `armazenamento`: quem chama passa a
pasta (ver `armazenamento.pasta_dados`)."""
import logging
import os
from logging.handlers import RotatingFileHandler

NOME = "mapeador"


def configurar_log(pasta: str) -> logging.Logger:
    """Liga o log em arquivo. Idempotente: chamar de novo com a mesma pasta
    não duplica o handler."""
    logger = logging.getLogger(NOME)
    destino = os.path.join(pasta, "logs")
    os.makedirs(destino, exist_ok=True)
    arquivo = os.path.abspath(os.path.join(destino, "app.log"))
    for handler in logger.handlers:
        if getattr(handler, "baseFilename", None) == arquivo:
            return logger
    handler = RotatingFileHandler(arquivo, maxBytes=1_000_000, backupCount=3,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
```

Em `core/pipeline.py`: acrescentar `import logging` aos imports e, depois dos imports, `log = logging.getLogger('mapeador')`. Em `_texto_com_paragrafos_ou_none`, trocar `except Exception:  # noqa: BLE001\n        return None` por:
```python
    except Exception:  # noqa: BLE001
        log.warning('parágrafos indisponíveis para %s; usando texto achatado',
                    caminho, exc_info=True)
        return None
```
Em `processar_arquivo`, no `except Exception as erro:` acrescentar como primeira linha do bloco:
```python
        log.error('falha ao processar %s', nome, exc_info=True)
```

Em `processar.py`, depois da linha `from core import armazenamento, pipeline, planilha  # noqa: E402`, trocar por:
```python
    from core import armazenamento, log, pipeline, planilha  # noqa: E402

    log.configurar_log(armazenamento.pasta_dados())
```
Em `app.py`: trocar o import `from core import acesso, armazenamento, consulta, pipeline, planilha  # noqa: E402` por `from core import acesso, armazenamento, consulta, log, pipeline, planilha  # noqa: E402` e, logo depois da linha `from core.pdf_text import MARCA_CITACAO  # noqa: E402`, acrescentar:
```python

log.configurar_log(armazenamento.pasta_dados())
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa.

- [ ] **Step 5: Commit**

```bash
git add core/log.py core/pipeline.py processar.py app.py tests/test_log.py tests/test_pipeline.py tests/test_processar.py
git commit -m "feat: log rotativo em arquivo com traceback das falhas de PDF"
```

---

### Task 6: Exportação `.xlsx` só ao clicar

**Files:**
- Modify: `requirements.txt`
- Modify: `core/consulta.py`
- Modify: `app.py` (`_renderiza_consultar`)
- Test: `tests/test_consulta.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `armazenamento.aberta` (Tarefa 3), `consulta.buscar`, `consulta.exportar_xlsx`.
- Produces: `consulta.exportar_busca(tipo, texto=None, ano=None, caminho_bd=None) -> bytes` (abre conexão própria: o `download_button` chama a função em outra thread e conexão SQLite não atravessa threads).

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_consulta.py` (garantir `import io` e `from openpyxl import load_workbook` no topo):
```python
def test_exportar_busca_abre_conexao_propria_e_devolve_xlsx(tmp_path):
    caminho = str(tmp_path / "e.db")
    with armazenamento.sessao(caminho) as c:
        armazenamento.salvar_consultas(c, [
            {'Ano': '2026', 'Nº da Consulta': '001', 'Súmula': 'ICMS',
             'Problema da Consulta': 'madeira'},
            {'Ano': '2026', 'Nº da Consulta': '002', 'Súmula': 'ICMS',
             'Problema da Consulta': 'soja'},
        ])

    dados = consulta.exportar_busca('consulta', texto='madeira', caminho_bd=caminho)

    ws = load_workbook(io.BytesIO(dados))['Consultas — a revisar']
    assert ws.max_row == 2  # cabeçalho + 1 resultado
```
Em `tests/test_app.py`:
```python
def test_renderizar_a_aba_nao_gera_o_xlsx(monkeypatch):
    # a planilha só pode ser montada quando o usuário clica em "Baixar"
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    armazenamento.criar_esquema(conn)
    armazenamento.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Súmula': 'ICMS'},
    ])
    conn.close()

    def _nao_deve_rodar(*args, **kwargs):
        raise AssertionError("xlsx gerado sem clique")

    monkeypatch.setattr("core.consulta.exportar_xlsx", _nao_deve_rodar)

    at = _app().run(timeout=30)

    assert not at.exception
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_consulta.py tests/test_app.py -k "exportar_busca or nao_gera" -v`
Expected: FAIL (`AttributeError: ... 'exportar_busca'`; e o teste do app falha com `AssertionError: xlsx gerado sem clique`).

- [ ] **Step 3: Implementar**

`requirements.txt`: trocar `streamlit>=1.50,<2` por `streamlit>=1.63,<2`.

Em `core/consulta.py`, acrescentar ao final:
```python
def exportar_busca(tipo: str, texto=None, ano=None, caminho_bd=None) -> bytes:
    """Refaz a busca com conexão PRÓPRIA e devolve o .xlsx.

    O `st.download_button` executa esta função numa thread à parte, quando o
    usuário clica; uma conexão SQLite aberta em outra thread não pode ser
    usada ali."""
    with armazenamento.aberta(caminho_bd) as conn:
        return exportar_xlsx(tipo, buscar(conn, tipo, texto, ano))
```
Em `app.py`, dentro de `_renderiza_consultar`, trocar
```python
    resultados = consulta.buscar(conn, tipo, texto=texto or None,
                                 ano=None if ano == "Todos" else ano)
```
por:
```python
    ano_filtro = None if ano == "Todos" else ano
    resultados = consulta.buscar(conn, tipo, texto=texto or None, ano=ano_filtro)
```
e trocar a linha `                consulta.exportar_xlsx(tipo, resultados),` por:
```python
                lambda: consulta.exportar_busca(tipo, texto or None, ano_filtro,
                                                _CAMINHO_BANCO),
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa. Se `test_bootstrap` reclamar do piso do streamlit, a versão instalada (1.63.0) atende; não altere o teste.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt core/consulta.py app.py tests/test_consulta.py tests/test_app.py
git commit -m "perf: gera o .xlsx de consulta só quando o usuário clica em baixar"
```

---

### Task 7: Busca sem acento e sem diferença de maiúsculas, em mais campos

**Files:**
- Create: `core/texto.py`
- Create: `tests/test_texto.py`
- Modify: `core/armazenamento.py` (`conectar`, `buscar_consultas`, `buscar_regimes`)
- Test: `tests/test_armazenamento.py`

**Interfaces:**
- Consumes: `core.pdf_text.MARCA_CITACAO`, `core.pdf_text.MARCA_PARAGRAFO`.
- Produces: `core.texto.normalizar(texto) -> str` (sem acento, caixa baixa, espaços colapsados, marcas invisíveis removidas; `None`/vazio → `''`); função SQL `norm(x)` registrada em toda conexão; `buscar_consultas`/`buscar_regimes` continuam com a mesma assinatura `(conn, texto=None, ano=None)`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_texto.py`:
```python
from core.pdf_text import MARCA_CITACAO, MARCA_PARAGRAFO
from core.texto import normalizar


def test_remove_acentos_e_ignora_caixa():
    assert normalizar("Substituição TRIBUTÁRIA") == "substituicao tributaria"


def test_colapsa_espacos_e_quebras_de_paragrafo():
    assert normalizar("a \n\n  b") == "a b"


def test_descarta_as_marcas_invisiveis():
    assert normalizar(f"a{MARCA_PARAGRAFO}{MARCA_CITACAO}b") == "a b"


def test_vazio_e_none_viram_texto_vazio():
    assert normalizar(None) == ""
    assert normalizar("   ") == ""
```
Em `tests/test_armazenamento.py`:
```python
def _consulta(**campos):
    base = {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
            'Protocolo': '', 'Súmula': '', 'Problema da Consulta': '',
            'CNAE Detectado': '', 'Resposta': ''}
    return {**base, **campos}


def test_busca_ignora_acentos_e_caixa(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(**{'Súmula': 'Substituição Tributária'})])
    assert len(armazenamento.buscar_consultas(conn, texto='SUBSTITUICAO')) == 1
    assert len(armazenamento.buscar_consultas(conn, texto='substituição tributária')) == 1


def test_busca_alcanca_a_resposta_mesmo_atravessando_paragrafos(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [
        _consulta(Resposta='primeiro trecho\n\nsegundo trecho do fisco')])
    # a frase atravessa a quebra de parágrafo ("\n\n" vira um espaço na comparação)
    assert len(armazenamento.buscar_consultas(conn, texto='trecho segundo')) == 1
    assert len(armazenamento.buscar_consultas(conn, texto='segundo   trecho')) == 1
    assert len(armazenamento.buscar_consultas(conn, texto='segundo primeiro')) == 0


def test_percentual_e_sublinhado_valem_como_texto_literal(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [
        _consulta(**{'Nº da Consulta': '001', 'Súmula': 'desconto de 10% no preço'}),
        _consulta(**{'Nº da Consulta': '002', 'Súmula': 'prazo de 10 dias'}),
        _consulta(**{'Nº da Consulta': '003', 'Súmula': 'campo_um'}),
        _consulta(**{'Nº da Consulta': '004', 'Súmula': 'campoXum'}),
    ])
    achadas = armazenamento.buscar_consultas(conn, texto='10%')
    assert [r['Nº da Consulta'] for r in achadas] == ['001']
    achadas = armazenamento.buscar_consultas(conn, texto='campo_um')
    assert [r['Nº da Consulta'] for r in achadas] == ['003']


def test_texto_so_com_espacos_equivale_a_sem_filtro(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(), _consulta(**{'Nº da Consulta': '002'})])
    assert len(armazenamento.buscar_consultas(conn, texto='   ')) == 2


def test_busca_de_regime_por_cnpj_e_por_numero(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [
        {'ANO': '2026', 'Nº DO REGIME ESPECIAL': '10.001/2026',
         'CNPJ REQUERENTE': '11.222.333/0001-81', 'EMPRESA': 'Alfa'},
        {'ANO': '2026', 'Nº DO REGIME ESPECIAL': '10.002/2026',
         'CNPJ REQUERENTE': '44.555.666/0001-00', 'EMPRESA': 'Beta'},
    ])
    assert [r['EMPRESA'] for r in armazenamento.buscar_regimes(conn, texto='0001-81')] == ['Alfa']
    assert [r['EMPRESA'] for r in armazenamento.buscar_regimes(conn, texto='10.002')] == ['Beta']
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_texto.py tests/test_armazenamento.py -v`
Expected: FAIL (`ModuleNotFoundError: core.texto`; os de busca por acento/`%`/cnpj falham).

- [ ] **Step 3: Implementar**

`core/texto.py`:
```python
# core/texto.py
"""Normalização de texto para busca: sem acento, sem diferença de caixa."""
import re
import unicodedata

from core.pdf_text import MARCA_CITACAO, MARCA_PARAGRAFO

_ESPACOS = re.compile(r'\s+')


def normalizar(texto) -> str:
    """'Substituição  TRIBUTÁRIA' -> 'substituicao tributaria'.

    Também descarta as marcas invisíveis que o parser deixa na Resposta
    (MARCA_CITACAO some; MARCA_PARAGRAFO vira espaço) e colapsa qualquer
    sequência de espaços/quebras num espaço só. None e vazio viram ''."""
    if not texto:
        return ''
    texto = str(texto).replace(MARCA_CITACAO, '').replace(MARCA_PARAGRAFO, ' ')
    decomposto = unicodedata.normalize('NFKD', texto)
    sem_acento = ''.join(c for c in decomposto if not unicodedata.combining(c))
    return _ESPACOS.sub(' ', sem_acento).strip().casefold()
```
Em `core/armazenamento.py`:
- acrescentar `from core.texto import normalizar` aos imports;
- em `conectar`, antes do `return conn`, acrescentar:
```python
    conn.create_function('norm', 1, normalizar, deterministic=True)
```
- acrescentar antes de `buscar_consultas`:
```python
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
```
- em `buscar_consultas`, substituir o bloco `if texto: ... parametros += [f'%{texto}%'] * 3` por:
```python
    filtro = _filtro_texto(_CAMPOS_BUSCA_CONSULTAS, texto)
    if filtro:
        condicoes.append(filtro[0])
        parametros += filtro[1]
```
- em `buscar_regimes`, idem, com `_CAMPOS_BUSCA_REGIMES` (substitui o bloco `if texto: ... parametros += [f'%{texto}%'] * 2`).

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa.

- [ ] **Step 5: Commit**

```bash
git add core/texto.py core/armazenamento.py tests/test_texto.py tests/test_armazenamento.py
git commit -m "feat: busca sem acento e sem diferença de caixa, também na resposta, CNPJ e número do regime"
```

---

### Task 8: Listagem leve e detalhe sob demanda

**Files:**
- Modify: `core/armazenamento.py`
- Modify: `core/consulta.py`
- Modify: `app.py` (`_renderiza_consultar`)
- Test: `tests/test_armazenamento.py`, `tests/test_consulta.py`

**Interfaces:**
- Consumes: `pipeline.CHAVE_CONSULTAS`, `pipeline.CHAVE_REGIMES`.
- Produces:
  - `armazenamento.COLUNAS_LISTA_CONSULTAS`, `armazenamento.COLUNAS_LISTA_REGIMES` (listas; contêm as colunas da chave natural);
  - `armazenamento.buscar_consultas(conn, texto=None, ano=None, colunas=None)` e `buscar_regimes(...)` com `colunas` opcional (`None` = todas);
  - `armazenamento.buscar_detalhe(conn, tabela: str, chave: list, valores: dict) -> dict | None`;
  - `consulta.buscar_lista(conn, tipo, texto=None, ano=None) -> list[dict]`;
  - `consulta.detalhe(conn, tipo, linha_da_lista: dict) -> dict | None`;
  - `consulta.CHAVES: dict` (`'consulta'`/`'regime'` → lista de colunas da chave).

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_armazenamento.py`:
```python
def test_buscar_com_colunas_devolve_so_as_pedidas(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(Resposta='texto longo')])
    linhas = armazenamento.buscar_consultas(conn, colunas=['Ano', 'Nº da Consulta'])
    assert list(linhas[0]) == ['Ano', 'Nº da Consulta']


def test_buscar_detalhe_pela_chave_natural(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(Resposta='texto longo')])
    achado = armazenamento.buscar_detalhe(
        conn, 'consultas', pipeline.CHAVE_CONSULTAS,
        {'Ano': '2026', 'Nº da Consulta': '001'})
    assert achado['Resposta'] == 'texto longo'
    ausente = armazenamento.buscar_detalhe(
        conn, 'consultas', pipeline.CHAVE_CONSULTAS,
        {'Ano': '1999', 'Nº da Consulta': '9'})
    assert ausente is None


def test_colunas_da_lista_incluem_a_chave_natural():
    assert set(pipeline.CHAVE_CONSULTAS) <= set(armazenamento.COLUNAS_LISTA_CONSULTAS)
    assert set(pipeline.CHAVE_REGIMES) <= set(armazenamento.COLUNAS_LISTA_REGIMES)
```
Em `tests/test_consulta.py`:
```python
def test_buscar_lista_traz_so_colunas_leves_e_detalhe_traz_tudo(tmp_path):
    with armazenamento.sessao(str(tmp_path / "l.db")) as c:
        armazenamento.salvar_consultas(c, [
            {'Ano': '2026', 'Nº da Consulta': '001', 'Súmula': 'ICMS',
             'Resposta': 'resposta completa'}])
        lista = consulta.buscar_lista(c, 'consulta')
        assert 'Resposta' not in lista[0]
        assert lista[0]['Súmula'] == 'ICMS'
        completo = consulta.detalhe(c, 'consulta', lista[0])
        assert completo['Resposta'] == 'resposta completa'


def test_detalhe_de_registro_inexistente_devolve_none(tmp_path):
    with armazenamento.sessao(str(tmp_path / "l.db")) as c:
        assert consulta.detalhe(c, 'regime', {'Nº DO REGIME ESPECIAL': 'x',
                                              'CNPJ REQUERENTE': 'y'}) is None


def test_buscar_lista_tipo_invalido_levanta_erro(tmp_path):
    with armazenamento.sessao(str(tmp_path / "l.db")) as c:
        with pytest.raises(ValueError):
            consulta.buscar_lista(c, 'outro')
```
(garantir `import pytest` em `tests/test_consulta.py`.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_armazenamento.py tests/test_consulta.py -k "colunas or detalhe or lista" -v`
Expected: FAIL (`TypeError: ... unexpected keyword argument 'colunas'`, `AttributeError`).

- [ ] **Step 3: Implementar**

Em `core/armazenamento.py`, acrescentar após `COLUNAS_REGIMES`:
```python
COLUNAS_LISTA_CONSULTAS = ['Ano', 'Nº da Consulta', 'Data da Publicação',
                           'Súmula', 'CNAE Detectado']
COLUNAS_LISTA_REGIMES = ['ANO', 'DATA', 'Nº DO REGIME ESPECIAL', 'EMPRESA',
                         'CNPJ REQUERENTE', 'VIGÊNCIA DO RE', 'EMENTA']


def _select(colunas) -> str:
    return '*' if not colunas else ', '.join(f'"{c}"' for c in colunas)
```
Substituir as duas funções de busca por:
```python
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
```
(Se a Tarefa 7 já deixou `buscar_*` quase assim, apenas acrescente `colunas` e `_select`; o resultado final deve ser exatamente o acima.)

Em `core/consulta.py`: trocar o import por `from core import armazenamento, pipeline, planilha` e acrescentar:
```python
COLUNAS_LISTA = {'consulta': armazenamento.COLUNAS_LISTA_CONSULTAS,
                 'regime': armazenamento.COLUNAS_LISTA_REGIMES}
CHAVES = {'consulta': pipeline.CHAVE_CONSULTAS, 'regime': pipeline.CHAVE_REGIMES}
_TABELAS = {'consulta': 'consultas', 'regime': 'regimes'}


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
```
Em `app.py`, dentro de `_renderiza_consultar`: trocar
```python
    resultados = consulta.buscar(conn, tipo, texto=texto or None, ano=ano_filtro)
```
por `resultados = consulta.buscar_lista(conn, tipo, texto=texto or None, ano=ano_filtro)` e trocar
```python
            _mostra_detalhe(tipo, resultados[linhas_selecionadas[0]], cols_do_tipo)
```
por:
```python
            completo = consulta.detalhe(conn, tipo, resultados[linhas_selecionadas[0]])
            if completo is not None:
                _mostra_detalhe(tipo, completo, cols_do_tipo)
```
(O botão "Baixar" continua usando `consulta.exportar_busca`, que busca as linhas completas.)

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa (os testes de modal em `test_app.py` continuam vendo a resposta completa porque o detalhe a busca no banco).

- [ ] **Step 5: Commit**

```bash
git add core/armazenamento.py core/consulta.py app.py tests/test_armazenamento.py tests/test_consulta.py
git commit -m "perf: lista de resultados leve e detalhe buscado sob demanda"
```

---

### Task 9: Critério de duplicados (`primeira` / `completo` / `recente`)

**Files:**
- Modify: `core/pipeline.py` (`dedup`, `finalizar`)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Produces: `pipeline.CRITERIOS_DEDUP = ('primeira', 'completo', 'recente')`; `pipeline.CRITERIO_PADRAO = 'primeira'`; `pipeline.dedup(linhas, campos, criterio='primeira')`; `pipeline.finalizar(lote, criterio='primeira')`. Chamadas antigas (`dedup(linhas, campos)`, `finalizar(lote)`) mantêm o comportamento.

- [ ] **Step 1: Escrever os testes que falham** (acrescentar a `tests/test_pipeline.py`)

```python
def _c(x, **extra):
    return {'Ano': '2026', 'Nº da Consulta': '001', 'x': x, **extra}


def test_dedup_completo_fica_com_o_registro_mais_preenchido():
    linhas = [_c('a', Resposta=''), _c('b', Resposta='texto')]
    out = pipeline.dedup(linhas, pipeline.CHAVE_CONSULTAS, criterio='completo')
    assert [r['x'] for r in out] == ['b']


def test_dedup_completo_empata_na_primeira():
    out = pipeline.dedup([_c('a'), _c('b')], pipeline.CHAVE_CONSULTAS,
                         criterio='completo')
    assert [r['x'] for r in out] == ['a']


def test_dedup_recente_usa_a_data_e_empata_no_ultimo_processado():
    mais_nova_primeiro = [_c('a', **{'Data da Publicação': '2026-02-01'}),
                          _c('b', **{'Data da Publicação': '2026-01-01'})]
    out = pipeline.dedup(mais_nova_primeiro, pipeline.CHAVE_CONSULTAS,
                         criterio='recente')
    assert [r['x'] for r in out] == ['a']

    sem_data = [_c('a'), _c('b')]
    out = pipeline.dedup(sem_data, pipeline.CHAVE_CONSULTAS, criterio='recente')
    assert [r['x'] for r in out] == ['b']


def test_dedup_recente_funciona_para_regimes_pela_coluna_data():
    chave = pipeline.CHAVE_REGIMES
    base = {'Nº DO REGIME ESPECIAL': '1/2026', 'CNPJ REQUERENTE': '11'}
    linhas = [{**base, 'x': 'a', 'DATA': '2026-03-01'},
              {**base, 'x': 'b', 'DATA': '2026-04-01'}]
    out = pipeline.dedup(linhas, chave, criterio='recente')
    assert [r['x'] for r in out] == ['b']


def test_dedup_mantem_a_ordem_de_chegada_das_chaves():
    linhas = [_c('a'), {'Ano': '2026', 'Nº da Consulta': '002', 'x': 'c'},
              _c('b', Resposta='mais completo')]
    out = pipeline.dedup(linhas, pipeline.CHAVE_CONSULTAS, criterio='completo')
    assert [r['Nº da Consulta'] for r in out] == ['001', '002']
    assert out[0]['x'] == 'b'


def test_dedup_criterio_invalido_e_erro_de_programacao():
    with pytest.raises(ValueError):
        pipeline.dedup([], pipeline.CHAVE_CONSULTAS, criterio='aleatorio')


def test_finalizar_aceita_o_criterio():
    lote = pipeline.Lote(consultas=[_c('a', Resposta=''), _c('b', Resposta='t')])
    pipeline.finalizar(lote, criterio='completo')
    assert [r['x'] for r in lote.consultas] == ['b']
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_pipeline.py -k "dedup or finalizar" -v`
Expected: FAIL (`TypeError: dedup() got an unexpected keyword argument 'criterio'`).

- [ ] **Step 3: Implementar em `core/pipeline.py`**

Acrescentar `import re` aos imports. Substituir `dedup` e `finalizar` por:
```python
CRITERIOS_DEDUP = ('primeira', 'completo', 'recente')
CRITERIO_PADRAO = 'primeira'
_DATA_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')


def _preenchidos(registro: dict) -> int:
    return sum(1 for v in registro.values() if str(v or '').strip())


def _data_iso(registro: dict) -> str:
    """Data do ato em AAAA-MM-DD ('' se ausente ou fora do padrão)."""
    for campo in ('Data da Publicação', 'DATA'):
        valor = str(registro.get(campo, '') or '')
        if _DATA_ISO.fullmatch(valor):
            return valor
    return ''


def _prefere_o_novo(criterio: str, novo: dict, atual: dict) -> bool:
    if criterio == 'completo':
        return _preenchidos(novo) > _preenchidos(atual)   # empate: fica o primeiro
    if criterio == 'recente':
        return _data_iso(novo) >= _data_iso(atual)        # empate: o último processado
    return False                                          # 'primeira'


def dedup(linhas, campos, criterio=CRITERIO_PADRAO):
    """Um registro por chave `campos`. `criterio` decide qual fica quando a
    chave se repete: 'primeira' ocorrência (padrão), 'completo' (mais campos
    preenchidos) ou 'recente' (maior data; empate: o último processado).
    A ordem de saída é a ordem em que cada chave apareceu pela 1ª vez."""
    if criterio not in CRITERIOS_DEDUP:
        raise ValueError(f"criterio deve ser um de {CRITERIOS_DEDUP}: {criterio!r}")
    escolhidos, ordem = {}, []
    for r in linhas:
        chave = tuple(r.get(c, '') for c in campos)
        if chave not in escolhidos:
            escolhidos[chave] = r
            ordem.append(chave)
        elif _prefere_o_novo(criterio, r, escolhidos[chave]):
            escolhidos[chave] = r
    return [escolhidos[chave] for chave in ordem]
```
e `finalizar`:
```python
def finalizar(lote: Lote, criterio: str = CRITERIO_PADRAO) -> Lote:
    """Deduplica consultas e regimes do lote (no lugar) e o devolve."""
    lote.consultas = dedup(lote.consultas, CHAVE_CONSULTAS, criterio)
    lote.regimes = dedup(lote.regimes, CHAVE_REGIMES, criterio)
    return lote
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa (`test_dedup_mantem_a_primeira_ocorrencia` continua verde: o padrão é `primeira`).

- [ ] **Step 5: Commit**

```bash
git add core/pipeline.py tests/test_pipeline.py
git commit -m "feat: critério de duplicados escolhível (primeira, completo, recente)"
```

---

### Task 10: Origem e hash dos arquivos no `Lote`

**Files:**
- Modify: `core/pipeline.py` (`Lote`, `processar_arquivo`)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Produces: `Lote.importacoes: list[dict]` com itens `{'arquivo': str, 'sha256': str, 'tipo': 'consulta'|'regime', 'n_registros': int}` (só para PDFs lidos com sucesso e de tipo conhecido); `Lote.origem: dict` que mapeia `('consulta', Ano, Nº da Consulta)` e `('regime', Nº DO REGIME ESPECIAL, CNPJ REQUERENTE)` ao nome do arquivo de origem (a primeira ocorrência). Os dicts de registro e as linhas de `lote.arquivos` **não mudam**.

- [ ] **Step 1: Escrever os testes que falham** (acrescentar a `tests/test_pipeline.py`; `import hashlib` no topo)

```python
def test_processar_arquivo_registra_hash_e_origem():
    lote = pipeline.Lote()
    pipeline.processar_arquivo(lote, CONSULTAS_PDF, "consultas.pdf")

    with open(CONSULTAS_PDF, "rb") as fh:
        esperado = hashlib.sha256(fh.read()).hexdigest()
    assert lote.importacoes == [{'arquivo': 'consultas.pdf', 'sha256': esperado,
                                 'tipo': 'consulta', 'n_registros': 3}]
    r = lote.consultas[0]
    assert lote.origem[('consulta', r['Ano'], r['Nº da Consulta'])] == 'consultas.pdf'


def test_origem_de_regime_usa_numero_e_cnpj():
    lote = pipeline.Lote()
    pipeline.processar_arquivo(lote, KRONA_PDF, "krona.pdf")
    r = lote.regimes[0]
    chave = ('regime', r['Nº DO REGIME ESPECIAL'], r['CNPJ REQUERENTE'])
    assert lote.origem[chave] == 'krona.pdf'
    assert lote.importacoes[0]['tipo'] == 'regime'
    assert lote.importacoes[0]['n_registros'] == 2


def test_arquivo_com_erro_nao_gera_importacao(tmp_path):
    ruim = tmp_path / "corrompido.pdf"
    ruim.write_bytes(b"isto nao e um pdf")
    lote = pipeline.Lote()
    pipeline.processar_arquivo(lote, str(ruim), "corrompido.pdf")
    assert lote.importacoes == []
    assert lote.origem == {}


def test_linha_do_arquivo_continua_com_as_seis_chaves():
    lote = pipeline.Lote()
    linha = pipeline.processar_arquivo(lote, CONSULTAS_PDF, "consultas.pdf")
    assert list(linha) == ['Arquivo', 'Tipo', 'Consultas', 'Regimes', 'Descartes', 'Erro']
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_pipeline.py -k "hash or origem or importacao or seis_chaves" -v`
Expected: FAIL (`AttributeError: 'Lote' object has no attribute 'importacoes'`).

- [ ] **Step 3: Implementar em `core/pipeline.py`**

Acrescentar `import hashlib` aos imports. Na dataclass `Lote`, acrescentar depois de `arquivos`:
```python
    # um item por PDF lido: {'arquivo', 'sha256', 'tipo', 'n_registros'}
    importacoes: list = field(default_factory=list)
    # ('consulta', Ano, Nº) / ('regime', Nº RE, CNPJ) -> nome do 1º arquivo de origem
    origem: dict = field(default_factory=dict)
```
Acrescentar a função:
```python
def _sha256(caminho: str) -> str:
    resumo = hashlib.sha256()
    with open(caminho, 'rb') as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b''):
            resumo.update(bloco)
    return resumo.hexdigest()
```
Substituir `processar_arquivo` por:
```python
def processar_arquivo(lote: Lote, caminho: str, nome: str,
                      forcar: str | None = None) -> dict:
    """Processa um PDF, acumula no `lote` e devolve a linha do arquivo.

    `forcar` é None (detecta pelo conteúdo), 'consulta' ou 'regime'.
    Exceções ao ler/parsear o PDF viram Tipo 'erro' com a mensagem em
    'Erro' — o lote segue. Só um `forcar` inválido levanta ValueError,
    porque é erro de quem chama, não do PDF.
    """
    if forcar is not None and forcar not in TIPOS_FORCAVEIS:
        raise ValueError(f"forcar deve ser None ou um de {TIPOS_FORCAVEIS}: {forcar!r}")

    linha = {'Arquivo': nome, 'Tipo': '', 'Consultas': 0, 'Regimes': 0,
             'Descartes': 0, 'Erro': ''}
    try:
        tipo = forcar or pdf_text.detecta_fonte(caminho)
        if tipo == 'consulta':
            regs = p_consultas.parse(pdf_text.texto_simples(caminho),
                                     _texto_com_paragrafos_ou_none(caminho))
            lote.consultas.extend(regs)
            linha['Consultas'] = len(regs)
            for r in regs:
                lote.origem.setdefault(
                    ('consulta', r.get('Ano', ''), r.get('Nº da Consulta', '')), nome)
            lote.importacoes.append({'arquivo': nome, 'sha256': _sha256(caminho),
                                     'tipo': tipo, 'n_registros': len(regs)})
        elif tipo == 'regime':
            regs, desc = p_regimes.parse(pdf_text.texto_por_colunas(caminho))
            for d in desc:
                d['Arquivo'] = nome
            lote.regimes.extend(regs)
            lote.descartes.extend(desc)
            linha['Regimes'] = len(regs)
            linha['Descartes'] = len(desc)
            for r in regs:
                lote.origem.setdefault(
                    ('regime', r.get('Nº DO REGIME ESPECIAL', ''),
                     r.get('CNPJ REQUERENTE', '')), nome)
            lote.importacoes.append({'arquivo': nome, 'sha256': _sha256(caminho),
                                     'tipo': tipo, 'n_registros': len(regs)})
        linha['Tipo'] = tipo
    except Exception as erro:  # noqa: BLE001 — um PDF ruim não pode matar o lote
        log.error('falha ao processar %s', nome, exc_info=True)
        linha['Tipo'] = 'erro'
        linha['Erro'] = f"{type(erro).__name__}: {erro}"
    lote.arquivos.append(linha)
    return linha
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa.

- [ ] **Step 5: Commit**

```bash
git add core/pipeline.py tests/test_pipeline.py
git commit -m "feat: lote registra hash e arquivo de origem de cada ato"
```

---

### Task 11: Histórico de alterações e registro de importações no banco

**Files:**
- Modify: `core/armazenamento.py` (`SCHEMA_VERSAO`, `criar_esquema`, `_upsert`, `persistir_lote`)
- Modify: `core/consulta.py`
- Test: `tests/test_armazenamento.py`, `tests/test_consulta.py`

**Interfaces:**
- Consumes: `core.versao.VERSAO_APP` (Tarefa 1), `Lote.importacoes` (Tarefa 10), `armazenamento.SCHEMA_VERSAO` (Tarefa 4).
- Produces:
  - `armazenamento.SCHEMA_VERSAO = 2`;
  - tabelas `historico(id, tabela, chave, registro_anterior, campos_alterados, alterado_em, versao_app)` e `importacoes(id, arquivo, sha256, tipo, n_registros, importado_em, versao_app)`;
  - `armazenamento.historico_de(conn, tabela: str, chave: dict) -> list[dict]` (mais recente primeiro; cada item `{'alterado_em', 'versao_app', 'campos_alterados': list, 'registro_anterior': dict}`);
  - `armazenamento.registrar_importacoes(conn, importacoes: list) -> None`;
  - `consulta.historico(conn, tipo, registro: dict) -> list[dict]`;
  - o retorno de `salvar_*` e `persistir_lote` **não muda**.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_armazenamento.py`:
```python
def test_reimportar_registro_identico_nao_cria_historico(tmp_path):
    conn = _conn(tmp_path)
    reg = _consulta(**{'Súmula': 'ICMS'})
    armazenamento.salvar_consultas(conn, [reg])
    armazenamento.salvar_consultas(conn, [reg])
    chave = {'Ano': '2026', 'Nº da Consulta': '001'}
    assert armazenamento.historico_de(conn, 'consultas', chave) == []


def test_reimportar_com_campo_diferente_cria_uma_linha_de_historico(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(Protocolo='')])
    resultado = armazenamento.salvar_consultas(conn, [_consulta(Protocolo='25.152.191-3')])

    assert resultado == {'novos': 0, 'atualizados': 1}  # contrato inalterado
    chave = {'Ano': '2026', 'Nº da Consulta': '001'}
    historico = armazenamento.historico_de(conn, 'consultas', chave)
    assert len(historico) == 1
    assert historico[0]['campos_alterados'] == ['Protocolo']
    assert historico[0]['registro_anterior']['Protocolo'] == ''
    assert historico[0]['versao_app']
    assert armazenamento.buscar_consultas(conn)[0]['Protocolo'] == '25.152.191-3'


def test_historico_vem_do_mais_recente_para_o_mais_antigo(tmp_path):
    conn = _conn(tmp_path)
    for protocolo in ('1', '2', '3'):
        armazenamento.salvar_consultas(conn, [_consulta(Protocolo=protocolo)])
    chave = {'Ano': '2026', 'Nº da Consulta': '001'}
    anteriores = [h['registro_anterior']['Protocolo']
                  for h in armazenamento.historico_de(conn, 'consultas', chave)]
    assert anteriores == ['2', '1']


def test_historico_de_regime_usa_a_chave_numero_mais_cnpj(tmp_path):
    conn = _conn(tmp_path)
    base = {'ANO': '2026', 'Nº DO REGIME ESPECIAL': '1/2026',
            'CNPJ REQUERENTE': '11', 'EMENTA': 'a'}
    armazenamento.salvar_regimes(conn, [base])
    armazenamento.salvar_regimes(conn, [{**base, 'EMENTA': 'b'}])
    chave = {'Nº DO REGIME ESPECIAL': '1/2026', 'CNPJ REQUERENTE': '11'}
    assert armazenamento.historico_de(conn, 'regimes', chave)[0]['campos_alterados'] == ['EMENTA']


def test_persistir_lote_registra_as_importacoes_sem_mudar_o_retorno(tmp_path):
    conn = _conn(tmp_path)
    lote = pipeline.Lote(
        consultas=[_consulta()],
        importacoes=[{'arquivo': 'c.pdf', 'sha256': 'abc', 'tipo': 'consulta',
                      'n_registros': 1}])
    resultado = armazenamento.persistir_lote(conn, lote)
    assert resultado == {'consultas': {'novos': 1, 'atualizados': 0},
                         'regimes': {'novos': 0, 'atualizados': 0}}
    linha = conn.execute("SELECT * FROM importacoes").fetchone()
    assert (linha['arquivo'], linha['sha256'], linha['tipo'], linha['n_registros']) == \
           ('c.pdf', 'abc', 'consulta', 1)
    assert linha['importado_em'] and linha['versao_app']


def test_schema_sobe_para_a_versao_2_e_banco_v1_e_migrado(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "v1.db"))
    armazenamento.criar_esquema(conn)
    conn.execute("DROP TABLE historico")
    conn.execute("DROP TABLE importacoes")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()

    armazenamento.criar_esquema(conn)

    assert armazenamento.versao_do_schema(conn) == 2
    conn.execute("SELECT COUNT(*) FROM historico")
    conn.execute("SELECT COUNT(*) FROM importacoes")
```
Em `tests/test_consulta.py`:
```python
def test_historico_do_registro_por_tipo(tmp_path):
    with armazenamento.sessao(str(tmp_path / "h.db")) as c:
        base = {'Ano': '2026', 'Nº da Consulta': '001', 'Protocolo': ''}
        armazenamento.salvar_consultas(c, [base])
        armazenamento.salvar_consultas(c, [{**base, 'Protocolo': 'x'}])
        itens = consulta.historico(c, 'consulta', base)
        assert len(itens) == 1
        assert itens[0]['campos_alterados'] == ['Protocolo']
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_armazenamento.py tests/test_consulta.py -k "historico or importacoes or versao_2" -v`
Expected: FAIL (`AttributeError: ... 'historico_de'`).

- [ ] **Step 3: Implementar em `core/armazenamento.py`**

Acrescentar aos imports: `import json`, `from datetime import datetime, timezone`, `from core.versao import VERSAO_APP`. Mudar `SCHEMA_VERSAO = 1` para `SCHEMA_VERSAO = 2`. Acrescentar:
```python
_DDL_HISTORICO = """
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabela TEXT NOT NULL,
    chave TEXT NOT NULL,
    registro_anterior TEXT NOT NULL,
    campos_alterados TEXT NOT NULL,
    alterado_em TEXT NOT NULL,
    versao_app TEXT NOT NULL
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
```
Em `criar_esquema`, antes do `if atual != SCHEMA_VERSAO:`, acrescentar:
```python
    conn.execute(_DDL_HISTORICO)
    conn.execute(_DDL_IMPORTACOES)
```
Substituir `_upsert` por:
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
                _guarda_historico(conn, tabela, chave, chave_valores,
                                  anterior, alterados)
        conn.execute(upsert_sql, tuple(reg.get(c, '') for c in colunas))
        novos += anterior is None
        atualizados += anterior is not None
    conn.commit()
    return {'novos': novos, 'atualizados': atualizados}
```
Acrescentar:
```python
def historico_de(conn: sqlite3.Connection, tabela: str, chave: dict) -> list:
    """Versões anteriores de um registro (a chave natural como dict), da mais
    recente para a mais antiga."""
    linhas = conn.execute(
        'SELECT * FROM historico WHERE tabela = ? AND chave = ? ORDER BY id DESC',
        (tabela, json.dumps(chave, ensure_ascii=False, sort_keys=True))).fetchall()
    return [{'alterado_em': l['alterado_em'], 'versao_app': l['versao_app'],
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
```
Substituir `persistir_lote` por:
```python
def persistir_lote(conn: sqlite3.Connection, lote: Lote) -> dict:
    """Persiste um core.pipeline.Lote inteiro (consultas + regimes) de uma vez."""
    resultado = {'consultas': salvar_consultas(conn, lote.consultas),
                 'regimes': salvar_regimes(conn, lote.regimes)}
    registrar_importacoes(conn, lote.importacoes)
    return resultado
```
Em `core/consulta.py`, acrescentar:
```python
def historico(conn, tipo: str, registro: dict) -> list:
    """Versões anteriores do ato (consulta ou regime), da mais recente para a
    mais antiga. `registro` precisa conter as colunas da chave natural."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}: {tipo!r}")
    chave = {c: registro.get(c, '') for c in CHAVES[tipo]}
    return armazenamento.historico_de(conn, _TABELAS[tipo], chave)
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa.

- [ ] **Step 5: Commit**

```bash
git add core/armazenamento.py core/consulta.py tests/test_armazenamento.py tests/test_consulta.py
git commit -m "feat: histórico de alterações e registro das importações (schema 2)"
```

---

### Task 12: Diagnóstico estruturado do lote

**Files:**
- Create: `core/diagnostico.py`
- Create: `tests/test_diagnostico.py`

**Interfaces:**
- Consumes: `pipeline.Lote` (com `arquivos`, `consultas`, `regimes`, `origem`).
- Produces: `diagnostico.cnpj_valido(cnpj) -> bool`; `diagnostico.diagnosticar(lote) -> dict` com `{'mensagens': [{'codigo','titulo','nivel','texto','arquivos'}], 'erros': int, 'avisos': int, 'pode_continuar': bool}`. Códigos: `E001` arquivo ilegível (nível `erro`, uma mensagem por arquivo); `A001` tipo não identificado; `A201` consulta sem resposta; `A202` consulta sem súmula; `A203` data da consulta fora do padrão; `A301` regime sem CNPJ; `A302` CNPJ inválido; `A303` regime sem vigência; `A304` data do regime fora do padrão; `A401` nenhum registro extraído (todos de nível `aviso`, exceto `E001`). `pode_continuar` = há ao menos um registro (consulta ou regime) para gravar; erro de arquivo **não** bloqueia.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_diagnostico.py`:
```python
from core import diagnostico, pipeline


def _arq(nome, tipo='consulta', erro=''):
    return {'Arquivo': nome, 'Tipo': tipo, 'Consultas': 0, 'Regimes': 0,
            'Descartes': 0, 'Erro': erro}


def _consulta(**campos):
    base = {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
            'Súmula': 'ICMS', 'Resposta': 'texto'}
    return {**base, **campos}


def _regime(**campos):
    base = {'Nº DO REGIME ESPECIAL': '1/2026', 'CNPJ REQUERENTE': '11.222.333/0001-81',
            'DATA': '2026-03-01', 'VIGÊNCIA DO RE': '12 meses'}
    return {**base, **campos}


def _codigos(diag):
    return [m['codigo'] for m in diag['mensagens']]


def test_cnpj_valido_confere_os_digitos_verificadores():
    assert diagnostico.cnpj_valido('11.222.333/0001-81')
    assert diagnostico.cnpj_valido('11222333000181')
    assert not diagnostico.cnpj_valido('11.222.333/0001-80')
    assert not diagnostico.cnpj_valido('11111111111111')
    assert not diagnostico.cnpj_valido('123')
    assert not diagnostico.cnpj_valido('')
    assert not diagnostico.cnpj_valido(None)


def test_lote_limpo_nao_tem_mensagens_e_pode_continuar():
    lote = pipeline.Lote(consultas=[_consulta()], regimes=[_regime()],
                         arquivos=[_arq('c.pdf')])
    diag = diagnostico.diagnosticar(lote)
    assert diag == {'mensagens': [], 'erros': 0, 'avisos': 0, 'pode_continuar': True}


def test_arquivo_ilegivel_vira_erro_com_nome_e_motivo_mas_nao_bloqueia():
    lote = pipeline.Lote(
        consultas=[_consulta()],
        arquivos=[_arq('ok.pdf'), _arq('ruim.pdf', tipo='erro',
                                        erro='PDFSyntaxError: arquivo inválido')])
    diag = diagnostico.diagnosticar(lote)
    erro = [m for m in diag['mensagens'] if m['codigo'] == 'E001'][0]
    assert erro['nivel'] == 'erro'
    assert 'ruim.pdf' in erro['texto'] and 'PDFSyntaxError' in erro['texto']
    assert erro['arquivos'] == ['ruim.pdf']
    assert diag['erros'] == 1
    assert diag['pode_continuar'] is True


def test_tipo_desconhecido_vira_aviso():
    lote = pipeline.Lote(consultas=[_consulta()],
                         arquivos=[_arq('x.pdf', tipo='desconhecido')])
    diag = diagnostico.diagnosticar(lote)
    assert _codigos(diag) == ['A001']
    assert diag['avisos'] == 1


def test_consulta_sem_resposta_sumula_e_com_data_ruim():
    lote = pipeline.Lote(
        consultas=[_consulta(Resposta='', Súmula='', **{'Data da Publicação': '19/01/2026'})],
        arquivos=[_arq('c.pdf')],
        origem={('consulta', '2026', '001'): 'c.pdf'})
    diag = diagnostico.diagnosticar(lote)
    assert _codigos(diag) == ['A201', 'A202', 'A203']
    assert diag['mensagens'][0]['arquivos'] == ['c.pdf']
    assert '001/2026' in diag['mensagens'][0]['texto']


def test_regime_com_cnpj_ausente_invalido_sem_vigencia_e_data_ruim():
    lote = pipeline.Lote(
        regimes=[_regime(**{'Nº DO REGIME ESPECIAL': '1/2026', 'CNPJ REQUERENTE': ''}),
                 _regime(**{'Nº DO REGIME ESPECIAL': '2/2026', 'CNPJ REQUERENTE': '11.222.333/0001-80'}),
                 _regime(**{'Nº DO REGIME ESPECIAL': '3/2026', 'VIGÊNCIA DO RE': '', 'DATA': ''})],
        arquivos=[_arq('r.pdf', tipo='regime')])
    diag = diagnostico.diagnosticar(lote)
    assert _codigos(diag) == ['A301', 'A302', 'A303', 'A304']


def test_lote_sem_registros_avisa_e_nao_pode_continuar():
    diag = diagnostico.diagnosticar(pipeline.Lote(arquivos=[_arq('c.pdf')]))
    assert _codigos(diag) == ['A401']
    assert diag['pode_continuar'] is False


def test_lote_totalmente_vazio_nao_quebra():
    diag = diagnostico.diagnosticar(pipeline.Lote())
    assert diag['pode_continuar'] is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_diagnostico.py -v`
Expected: FAIL com `ImportError: cannot import name 'diagnostico' from 'core'`.

- [ ] **Step 3: Implementar**

`core/diagnostico.py`:
```python
# core/diagnostico.py
"""Diagnóstico de um Lote ANTES de gravar no banco.

Mesmo formato de mensagem do hub: código, título, nível ('erro' | 'aviso'),
texto e os arquivos envolvidos. Arquivo ilegível é 'erro' mas não bloqueia os
demais; o que bloqueia a gravação é não haver nenhum registro."""
import re
from collections import defaultdict

_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')
_PESOS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_2 = [6] + _PESOS_1
_MAX_ITENS_NO_TEXTO = 5

_CATALOGO = {
    'A001': 'Tipo de arquivo não identificado',
    'A201': 'Consulta sem resposta',
    'A202': 'Consulta sem súmula',
    'A203': 'Data da consulta fora do padrão AAAA-MM-DD',
    'A301': 'Regime sem CNPJ do requerente',
    'A302': 'CNPJ do requerente inválido',
    'A303': 'Regime sem vigência',
    'A304': 'Data do regime fora do padrão AAAA-MM-DD',
    'A401': 'Nenhum registro extraído',
}


def cnpj_valido(cnpj) -> bool:
    """Confere os dois dígitos verificadores (aceita com ou sem pontuação)."""
    digitos = re.sub(r'\D', '', str(cnpj or ''))
    if len(digitos) != 14 or digitos == digitos[0] * 14:
        return False

    def digito(base: str, pesos: list) -> str:
        resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        return '0' if resto < 2 else str(11 - resto)

    return (digitos[12] == digito(digitos[:12], _PESOS_1)
            and digitos[13] == digito(digitos[:13], _PESOS_2))


def _mensagem(codigo, titulo, nivel, texto, arquivos) -> dict:
    return {'codigo': codigo, 'titulo': titulo, 'nivel': nivel, 'texto': texto,
            'arquivos': sorted(set(a for a in arquivos if a))}


def diagnosticar(lote) -> dict:
    mensagens = []
    achados = defaultdict(list)  # código -> [(referência, arquivo)]

    for linha in lote.arquivos:
        if linha.get('Tipo') == 'erro':
            mensagens.append(_mensagem(
                'E001', 'Arquivo ilegível', 'erro',
                f"{linha['Arquivo']}: {linha.get('Erro', '')}", [linha['Arquivo']]))
        elif linha.get('Tipo') == 'desconhecido':
            achados['A001'].append((linha['Arquivo'], linha['Arquivo']))

    for r in lote.consultas:
        ref = f"{r.get('Nº da Consulta', '')}/{r.get('Ano', '')}"
        arq = lote.origem.get(('consulta', r.get('Ano', ''), r.get('Nº da Consulta', '')), '')
        if not str(r.get('Resposta', '') or '').strip():
            achados['A201'].append((ref, arq))
        if not str(r.get('Súmula', '') or '').strip():
            achados['A202'].append((ref, arq))
        if not _ISO.fullmatch(str(r.get('Data da Publicação', '') or '')):
            achados['A203'].append((ref, arq))

    for r in lote.regimes:
        ref = f"RE {r.get('Nº DO REGIME ESPECIAL', '')}"
        arq = lote.origem.get(('regime', r.get('Nº DO REGIME ESPECIAL', ''),
                               r.get('CNPJ REQUERENTE', '')), '')
        cnpj = str(r.get('CNPJ REQUERENTE', '') or '').strip()
        if not cnpj:
            achados['A301'].append((ref, arq))
        elif not cnpj_valido(cnpj):
            achados['A302'].append((ref, arq))
        if not str(r.get('VIGÊNCIA DO RE', '') or '').strip():
            achados['A303'].append((ref, arq))
        if not _ISO.fullmatch(str(r.get('DATA', '') or '')):
            achados['A304'].append((ref, arq))

    tem_registros = bool(lote.consultas or lote.regimes)
    if not tem_registros:
        achados['A401'].append(('lote', ''))

    for codigo in sorted(achados):
        itens = achados[codigo]
        refs = [ref for ref, _ in itens]
        resumo = ', '.join(refs[:_MAX_ITENS_NO_TEXTO])
        if len(refs) > _MAX_ITENS_NO_TEXTO:
            resumo += f' … (+{len(refs) - _MAX_ITENS_NO_TEXTO})'
        texto = (f"{len(itens)} ocorrência(s): {resumo}" if codigo != 'A401'
                 else 'Nenhuma consulta ou regime foi extraído dos arquivos enviados.')
        mensagens.append(_mensagem(codigo, _CATALOGO[codigo], 'aviso', texto,
                                   [arq for _, arq in itens]))

    mensagens.sort(key=lambda m: m['codigo'])
    return {'mensagens': mensagens,
            'erros': sum(1 for m in mensagens if m['nivel'] == 'erro'),
            'avisos': sum(1 for m in mensagens if m['nivel'] == 'aviso'),
            'pode_continuar': tem_registros}
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa.

- [ ] **Step 5: Commit**

```bash
git add core/diagnostico.py tests/test_diagnostico.py
git commit -m "feat: diagnóstico estruturado do lote (erros, avisos e CNPJ inválido)"
```

---

### Task 13: Classe `Execucao` (motor único para CLI e interface)

**Files:**
- Create: `core/execucao.py`
- Create: `tests/test_execucao.py`

**Interfaces:**
- Consumes: `pipeline.Lote`, `pipeline.processar_arquivo`, `pipeline.finalizar`, `pipeline.CRITERIOS_DEDUP`, `pipeline.CRITERIO_PADRAO` (Tarefas 9–10); `diagnostico.diagnosticar` (Tarefa 12); `armazenamento.persistir_lote` (Tarefa 11).
- Produces: `core.execucao.Execucao(progresso=None, ao_arquivo=None, dedup='primeira')` com:
  - `.carregar(arquivos: list[tuple[str, str]], forcar=None) -> Lote` — `arquivos` = lista de `(caminho, nome)`; chama `progresso('leitura', i_concluidos, total, nome)` antes de cada arquivo e `progresso('leitura', total, total, '')` no fim; chama `ao_arquivo(linha)` depois de cada arquivo; deduplica pelo critério e preenche `.lote` e `.diagnostico`;
  - `.gravar(conn) -> dict` — `persistir_lote` (mesmo retorno de sempre), com `progresso('gravacao', 0, 1, '')` e `progresso('gravacao', 1, 1, '')`;
  - `.arquivos_com_erro() -> list[dict]` (linhas de `lote.arquivos` com `Tipo == 'erro'`);
  - `ValueError` no construtor se `dedup` for inválido.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_execucao.py`:
```python
import os

import pytest

from core import armazenamento
from core.execucao import Execucao

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
CONSULTAS_PDF = os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf")


def test_carregar_avisa_o_progresso_e_chama_ao_arquivo():
    eventos, linhas = [], []
    ex = Execucao(progresso=lambda *a: eventos.append(a), ao_arquivo=linhas.append)

    lote = ex.carregar([(CONSULTAS_PDF, "c.pdf")])

    assert eventos[0] == ('leitura', 0, 1, 'c.pdf')
    assert eventos[-1] == ('leitura', 1, 1, '')
    assert [l['Arquivo'] for l in linhas] == ['c.pdf']
    assert len(lote.consultas) == 3
    assert ex.lote is lote
    assert ex.diagnostico['pode_continuar'] is True


def test_carregar_lista_vazia_nao_quebra():
    ex = Execucao()
    lote = ex.carregar([])
    assert lote.consultas == [] and lote.regimes == []
    assert ex.diagnostico['pode_continuar'] is False


def test_pdf_corrompido_nao_derruba_o_lote_e_aparece_em_arquivos_com_erro(tmp_path):
    ruim = tmp_path / "corrompido.pdf"
    ruim.write_bytes(b"isto nao e um pdf")
    ex = Execucao()

    ex.carregar([(CONSULTAS_PDF, "c.pdf"), (str(ruim), "corrompido.pdf")])

    assert len(ex.lote.consultas) == 3
    erros = ex.arquivos_com_erro()
    assert [e['Arquivo'] for e in erros] == ['corrompido.pdf']
    assert erros[0]['Erro']


def test_gravar_persiste_e_avisa_o_progresso(tmp_path):
    eventos = []
    ex = Execucao(progresso=lambda *a: eventos.append(a))
    ex.carregar([(CONSULTAS_PDF, "c.pdf")])

    with armazenamento.sessao(str(tmp_path / "e.db")) as conn:
        resultado = ex.gravar(conn)
        assert len(armazenamento.buscar_consultas(conn)) == 3
        assert conn.execute("SELECT COUNT(*) FROM importacoes").fetchone()[0] == 1

    assert resultado['consultas'] == {'novos': 3, 'atualizados': 0}
    assert ('gravacao', 0, 1, '') in eventos and ('gravacao', 1, 1, '') in eventos


def test_criterio_de_dedup_invalido_e_recusado():
    with pytest.raises(ValueError):
        Execucao(dedup='aleatorio')


def test_forcar_invalido_continua_sendo_erro_de_programacao():
    with pytest.raises(ValueError):
        Execucao().carregar([(CONSULTAS_PDF, "c.pdf")], forcar='outro')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_execucao.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'core.execucao'`.

- [ ] **Step 3: Implementar**

`core/execucao.py`:
```python
# core/execucao.py
"""Uma execução completa: carregar -> (diagnosticar) -> gravar.

Usada pela CLI (processar.py) e pela interface (app.py). Fica ACIMA de
pipeline, diagnostico e armazenamento (armazenamento importa pipeline, então
a ordem inversa criaria dependência circular).

Callbacks, no mesmo formato do hub:
  progresso(fase, atual, total, texto)   fase: 'leitura' | 'gravacao'
  ao_arquivo(linha)                      depois de cada PDF (linha de lote.arquivos)
"""
from core import armazenamento, diagnostico, pipeline


class Execucao:
    def __init__(self, progresso=None, ao_arquivo=None,
                 dedup: str = pipeline.CRITERIO_PADRAO):
        if dedup not in pipeline.CRITERIOS_DEDUP:
            raise ValueError(
                f"dedup deve ser um de {pipeline.CRITERIOS_DEDUP}: {dedup!r}")
        self._progresso = progresso or (lambda *args: None)
        self._ao_arquivo = ao_arquivo
        self.dedup = dedup
        self.lote = None
        self.diagnostico = None

    def carregar(self, arquivos: list, forcar: str | None = None):
        """Lê os PDFs (`arquivos` = [(caminho, nome), ...]), deduplica pelo
        critério e diagnostica. Um PDF ruim não interrompe os demais."""
        lote = pipeline.Lote()
        total = len(arquivos)
        for i, (caminho, nome) in enumerate(arquivos):
            self._progresso('leitura', i, total, nome)
            linha = pipeline.processar_arquivo(lote, caminho, nome, forcar=forcar)
            if self._ao_arquivo:
                self._ao_arquivo(linha)
        self._progresso('leitura', total, total, '')
        self.lote = pipeline.finalizar(lote, self.dedup)
        self.diagnostico = diagnostico.diagnosticar(self.lote)
        return self.lote

    def gravar(self, conn) -> dict:
        """Persiste o lote carregado. Devolve o resumo de novos/atualizados."""
        self._progresso('gravacao', 0, 1, '')
        resultado = armazenamento.persistir_lote(conn, self.lote)
        self._progresso('gravacao', 1, 1, '')
        return resultado

    def arquivos_com_erro(self) -> list:
        return [l for l in self.lote.arquivos if l['Tipo'] == 'erro']
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa.

- [ ] **Step 5: Commit**

```bash
git add core/execucao.py tests/test_execucao.py
git commit -m "feat: classe Execucao com callback de progresso, usada por CLI e interface"
```

---

### Task 14: CLI — `--dedup`, `--simular`, código de saída 2 e erros por arquivo

**Files:**
- Modify: `processar.py`
- Test: `tests/test_processar.py`

**Interfaces:**
- Consumes: `Execucao` (Tarefa 13), `armazenamento.sessao`/`SchemaMaisNovo` (Tarefas 3–4), `log.configurar_log` (Tarefa 5).
- Produces: `processar.main(argv) -> int` com as opções `--banco`, `--xlsx`, `--dedup primeira|completo|recente`, `--simular`. Códigos: 0 = ok; 1 = uso incorreto, nenhum PDF, planilha aberta no Excel ou banco de versão mais nova; 2 = algum PDF falhou (os demais são gravados). Erros por arquivo vão para **stderr**; diagnóstico (avisos) para stdout.

- [ ] **Step 1: Escrever/ajustar os testes**

Em `tests/test_processar.py`:

(a) No teste `test_xlsx_gerado_quando_pedido_explicitamente`, trocar `assert codigo == 0` por `assert codigo == 2` (há um `corrompido.pdf` na pasta; a mudança é intencional, decisão 4 da spec).

(b) Acrescentar:
```python
def _pasta_com(tmp_path, *, corrompido=False):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")
    if corrompido:
        (pasta / "corrompido.pdf").write_bytes(b"isto nao e um pdf")
    return pasta


def test_pdf_com_erro_sai_com_2_grava_os_bons_e_nomeia_o_erro(tmp_path, capsys):
    pasta = _pasta_com(tmp_path, corrompido=True)
    banco = tmp_path / "m.db"

    codigo = processar.main([str(pasta), "--banco", str(banco)])

    assert codigo == 2
    conn = armazenamento.conectar(str(banco))
    assert len(armazenamento.buscar_consultas(conn)) == 3  # os bons foram gravados
    err = capsys.readouterr().err
    assert "corrompido.pdf" in err
    assert "Erro" in err or "erro" in err


def test_simular_nao_grava_e_mostra_o_diagnostico(tmp_path, capsys):
    pasta = _pasta_com(tmp_path)
    banco = tmp_path / "m.db"

    codigo = processar.main([str(pasta), "--banco", str(banco), "--simular"])

    assert codigo == 0
    assert not banco.exists()
    assert "nada foi gravado" in capsys.readouterr().out


def test_dedup_invalido_mostra_o_uso(tmp_path, capsys):
    pasta = _pasta_com(tmp_path)
    codigo = processar.main([str(pasta), "--dedup", "aleatorio"])
    assert codigo == 1
    assert "Uso:" in capsys.readouterr().out


def test_dedup_valido_e_aceito(tmp_path):
    pasta = _pasta_com(tmp_path)
    codigo = processar.main([str(pasta), "--banco", str(tmp_path / "m.db"),
                             "--dedup", "completo"])
    assert codigo == 0


def test_banco_de_versao_mais_nova_sai_com_1_e_mensagem(tmp_path, capsys):
    pasta = _pasta_com(tmp_path)
    banco = tmp_path / "m.db"
    conn = armazenamento.conectar(str(banco))
    conn.execute(f"PRAGMA user_version = {armazenamento.SCHEMA_VERSAO + 1}")
    conn.commit()
    conn.close()

    codigo = processar.main([str(pasta), "--banco", str(banco)])

    assert codigo == 1
    assert "mais nova" in capsys.readouterr().err
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_processar.py -v`
Expected: FAIL nos testes novos e no ajustado (`codigo == 2`).

- [ ] **Step 3: Implementar — reescrever `processar.py`**

Substituir o conteúdo inteiro por:
```python
# processar.py
"""CLI: python processar.py <pasta_com_pdfs> [--banco arquivo.db] [--xlsx saida.xlsx]
                            [--dedup primeira|completo|recente] [--simular]

Persiste no banco por padrão. A planilha é uma exportação opcional (--xlsx).
--simular lê e diagnostica os PDFs sem gravar nada.

Códigos de saída: 0 = tudo certo; 1 = uso incorreto, nenhum PDF, planilha
aberta no Excel ou banco de versão mais nova; 2 = algum PDF não pôde ser lido
(os demais foram processados e gravados normalmente).
"""
import glob
import os
import sys

from core.bootstrap import DEPS_CLI, garantir_dependencias, tolera_encoding_do_console

_USO = ("Uso: python processar.py <pasta_com_pdfs> [--banco arquivo.db] "
        "[--xlsx saida.xlsx] [--dedup primeira|completo|recente] [--simular]")


def main(argv=None) -> int:
    # Antes de qualquer print (inclusive os de uso/erro abaixo, que já podem
    # levar acento ou o nome de uma pasta acentuada): ver
    # core/bootstrap.tolera_encoding_do_console.
    tolera_encoding_do_console()

    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(_USO)
        return 1

    pasta = argv[0]
    try:
        banco = _opcao(argv, "--banco")
        xlsx = _opcao(argv, "--xlsx")
        dedup = _opcao(argv, "--dedup")
    except ValueError as erro:
        print(f"{_USO}\n({erro})")
        return 1
    simular = "--simular" in argv

    pdfs = sorted(glob.glob(os.path.join(pasta, "*.pdf")))
    if not pdfs:
        print(f"Nenhum PDF encontrado em {pasta}")
        return 1

    # dentro do main (e não no import) para que importar este módulo — nos
    # testes, por exemplo — nunca dispare um pip install.
    garantir_dependencias(DEPS_CLI)
    from core import armazenamento, log, pipeline, planilha  # noqa: E402
    from core.execucao import Execucao  # noqa: E402

    dedup = dedup or pipeline.CRITERIO_PADRAO
    if dedup not in pipeline.CRITERIOS_DEDUP:
        print(f"{_USO}\n(--dedup deve ser um de {', '.join(pipeline.CRITERIOS_DEDUP)})")
        return 1

    log.configurar_log(armazenamento.pasta_dados())

    execucao = Execucao(ao_arquivo=_imprime_linha, dedup=dedup)
    lote = execucao.carregar([(c, os.path.basename(c)) for c in pdfs])
    _imprime_diagnostico(execucao.diagnostico)
    erros = execucao.arquivos_com_erro()

    if simular:
        print("\nSimulação: nada foi gravado no banco.")
        return _finaliza(erros)

    try:
        with armazenamento.sessao(banco) as conn:
            resultado = execucao.gravar(conn)
    except armazenamento.SchemaMaisNovo as erro:
        print(f"\n{erro}", file=sys.stderr)
        return 1

    if xlsx:
        try:
            planilha.gerar_xlsx(xlsx, lote.consultas, lote.regimes,
                                lote.descartes, lote.arquivos)
        except PermissionError:
            print(f"\nNão foi possível gravar {xlsx}.\n"
                  "Se a planilha estiver aberta no Excel, feche-a e rode de novo.",
                  file=sys.stderr)
            return 1

    print(f"\n✓ Consultas: {resultado['consultas']['novos']} novas, "
          f"{resultado['consultas']['atualizados']} atualizadas")
    print(f"  Regimes:   {resultado['regimes']['novos']} novos, "
          f"{resultado['regimes']['atualizados']} atualizados")
    if xlsx:
        print(f"  Planilha:  {xlsx}")
    return _finaliza(erros)


def _finaliza(erros: list) -> int:
    """0 se todos os PDFs foram lidos; senão lista cada erro em stderr e devolve 2."""
    if not erros:
        return 0
    print("\nArquivos com erro (os demais foram processados):", file=sys.stderr)
    for linha in erros:
        print(f"  - {linha['Arquivo']}: {linha['Erro']}", file=sys.stderr)
    return 2


def _opcao(argv: list, nome: str) -> str | None:
    if nome not in argv:
        return None
    i = argv.index(nome)
    if i + 1 >= len(argv):
        raise ValueError(f"{nome} exige um valor")
    return argv[i + 1]


def _imprime_linha(linha: dict) -> None:
    nome, tipo = linha['Arquivo'], linha['Tipo']
    if tipo == 'consulta':
        print(f"[consulta] {nome}: {linha['Consultas']} extraídas")
    elif tipo == 'regime':
        print(f"[regime]   {nome}: {linha['Regimes']} extraídos, "
              f"{linha['Descartes']} descartados")
    elif tipo == 'erro':
        print(f"[ERRO]     {nome}: {linha['Erro']}")
    else:
        print(f"[?]        {nome}: tipo não identificado — pulado")


def _imprime_diagnostico(diag: dict) -> None:
    if not diag['mensagens']:
        return
    print("\nDiagnóstico:")
    for m in diag['mensagens']:
        print(f"  [{m['nivel'].upper()}] {m['codigo']} {m['titulo']}: {m['texto']}")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa (inclusive os testes de encoding ASCII e de planilha aberta no Excel, que não mudam).

- [ ] **Step 5: Commit**

```bash
git add processar.py tests/test_processar.py
git commit -m "feat: CLI com --dedup, --simular, código 2 para PDF com erro e erros por arquivo"
```

---

### Task 15: Interface — fluxo "Analisar → Gravar", critério de duplicados, erros nomeados e histórico

**Files:**
- Modify: `app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `Execucao` (Tarefa 13), `diagnostico.diagnosticar` (Tarefa 12), `consulta.historico` (Tarefa 11), `consulta.detalhe` (Tarefa 8), `_persistir` (Tarefa 3).
- Produces: estado de sessão `st.session_state["analise"] = {"lote": Lote, "diagnostico": dict}` (existe entre "Analisar" e "Gravar"); botões com `key="analisar"` e `key="gravar"`; `st.session_state["resultado"]` continua com as mesmas 6 chaves.

- [ ] **Step 1: Escrever os testes que falham** (acrescentar a `tests/test_app.py`)

```python
def _lote_com_uma_consulta():
    from core import pipeline
    return pipeline.Lote(
        consultas=[{'Ano': '2026', 'Nº da Consulta': '001',
                    'Data da Publicação': '2026-01-19', 'Protocolo': '',
                    'Súmula': 'ICMS', 'Problema da Consulta': 'a',
                    'CNAE Detectado': '', 'Resposta': 'r'}],
        arquivos=[{'Arquivo': 'c.pdf', 'Tipo': 'consulta', 'Consultas': 1,
                   'Regimes': 0, 'Descartes': 0, 'Erro': ''}])


def _com_analise(lote):
    from core import diagnostico
    at = _app()
    at.session_state["analise"] = {"lote": lote,
                                   "diagnostico": diagnostico.diagnosticar(lote)}
    return at


def test_analise_guardada_mostra_o_diagnostico_e_nao_grava_ainda():
    at = _com_analise(_lote_com_uma_consulta()).run(timeout=30)

    assert not at.exception
    assert any("nada foi gravado" in s.value for s in at.subheader)
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    armazenamento.criar_esquema(conn)
    assert armazenamento.buscar_consultas(conn) == []


def test_clicar_em_gravar_persiste_e_mostra_o_resultado():
    at = _com_analise(_lote_com_uma_consulta()).run(timeout=30)

    at.button(key="gravar").click().run(timeout=30)

    assert not at.exception
    conn = armazenamento.conectar(os.environ["MAPEADOR_BANCO"])
    assert len(armazenamento.buscar_consultas(conn)) == 1
    assert "analise" not in at.session_state
    assert at.session_state["resultado"]["mapeamento"]["consultas"]["novos"] == 1


def test_analise_nomeia_o_arquivo_com_erro_e_ainda_deixa_gravar_os_bons():
    lote = _lote_com_uma_consulta()
    lote.arquivos.append({'Arquivo': 'ruim.pdf', 'Tipo': 'erro', 'Consultas': 0,
                          'Regimes': 0, 'Descartes': 0,
                          'Erro': 'PDFSyntaxError: arquivo inválido'})

    at = _com_analise(lote).run(timeout=30)

    assert any("ruim.pdf" in e.value and "PDFSyntaxError" in e.value for e in at.error)
    assert at.button(key="gravar").disabled is False


def test_gravar_fica_desabilitado_quando_nao_ha_registros():
    from core import pipeline
    lote = pipeline.Lote(arquivos=[{'Arquivo': 'x.pdf', 'Tipo': 'desconhecido',
                                    'Consultas': 0, 'Regimes': 0,
                                    'Descartes': 0, 'Erro': ''}])
    at = _com_analise(lote).run(timeout=30)
    assert at.button(key="gravar").disabled is True


def test_trocar_perfil_descarta_a_analise_pendente():
    at = _com_analise(_lote_com_uma_consulta()).run(timeout=30)
    at.button(key="trocar-perfil").click().run(timeout=30)
    assert "analise" not in at.session_state
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_app.py -k "analise or gravar or trocar_perfil" -v`
Expected: FAIL (a interface ainda não conhece `analise` nem o botão `gravar`).

- [ ] **Step 3: Implementar em `app.py`**

(a) Imports: trocar a linha
```python
from core import acesso, armazenamento, consulta, log, pipeline, planilha  # noqa: E402
```
por:
```python
from core import acesso, armazenamento, consulta, log, planilha  # noqa: E402
from core.execucao import Execucao  # noqa: E402
```
(b) Logo abaixo de `_FORCAR = {...}`, acrescentar:
```python
_CRITERIOS = {"Primeira ocorrência": "primeira",
              "Mais completo": "completo",
              "Mais recente": "recente"}
```
(c) Substituir a função `_processar` inteira (de `def _processar(enviados, forcar):` até a linha anterior a `def _tela_inicial():`) por:
```python
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
        for arq in enviados:
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
    return {"lote": lote, "diagnostico": execucao.diagnostico}


def _gravar(analise):
    """Persiste o lote analisado e devolve o resultado a guardar na sessão
    (mesmas chaves de sempre)."""
    acesso.exige_admin(st.session_state.get("perfil"))
    lote = analise["lote"]
    mapeamento = _persistir(lote)

    # planilha em memória, exportação opcional: nada de cópia em disco
    buf = io.BytesIO()
    planilha.gerar_xlsx(buf, lote.consultas, lote.regimes, lote.descartes,
                        lote.arquivos)
    return {"arquivos": lote.arquivos, "consultas": lote.consultas,
            "regimes": lote.regimes, "descartes": lote.descartes,
            "mapeamento": mapeamento, "xlsx": buf.getvalue()}


def _mostra_analise(analise):
    lote, diag = analise["lote"], analise["diagnostico"]
    with st.container(border=True, key="card-analise"):
        st.subheader("Análise dos arquivos (nada foi gravado ainda)")
        st.dataframe(lote.arquivos, width="stretch", hide_index=True)
        for linha in lote.arquivos:
            if linha["Tipo"] == "erro":
                st.error(f"**{linha['Arquivo']}** não pôde ser lido: {linha['Erro']}")
        c1, c2 = st.columns(2)
        c1.metric("Consultas", len(lote.consultas))
        c2.metric("Regimes", len(lote.regimes))
        for m in diag["mensagens"]:
            if m["codigo"] == "E001":
                continue  # o erro do arquivo já foi mostrado acima, com o motivo
            aviso = f"**{m['codigo']} — {m['titulo']}.** {m['texto']}"
            (st.warning if m["nivel"] == "aviso" else st.error)(aviso)
        if not diag["pode_continuar"]:
            st.info("Não há nenhum registro para gravar.")
```
(d) Em `_mostra_detalhe`: trocar a assinatura
```python
def _mostra_detalhe(tipo: str, registro: dict, colunas: list):
```
por `def _mostra_detalhe(tipo: str, registro: dict, colunas: list, historico=()):` e, depois do trecho
```python
        else:
            st.write(valor)
```
(o último `else` do `for`), acrescentar no nível da função:
```python
    if historico:
        with st.expander(f"Histórico de alterações ({len(historico)})"):
            for h in historico:
                st.markdown(f"**{h['alterado_em']}** (versão {h['versao_app']}) — "
                            f"campos alterados: {', '.join(h['campos_alterados'])}")
```
(e) Em `_renderiza_consultar`, trocar
```python
                _mostra_detalhe(tipo, completo, cols_do_tipo)
```
por:
```python
                _mostra_detalhe(tipo, completo, cols_do_tipo,
                                consulta.historico(conn, tipo, completo))
```
(f) "Trocar perfil": trocar `for chave in ("perfil", "resultado"):` por `for chave in ("perfil", "resultado", "analise"):`.

(g) Na barra lateral, trocar o texto do passo 2
```python
              "2. A ferramenta detecta o tipo, extrai os campos e mapeia no "
              "banco local.\n"
```
por:
```python
              "2. A ferramenta detecta o tipo, extrai os campos e mostra uma "
              "análise para você conferir; só então grava no banco local.\n"
```
(h) Trocar este trecho **inteiro** (da linha do botão "Processar" até a linha `      if resultado:`, inclusive — são o botão, uma linha em branco, três linhas de comentário, `resultado = st.session_state.get("resultado")` e `if resultado:`):
```python
      if arquivos and st.button("▶️ Processar", type="primary"):
          st.session_state["resultado"] = _processar(arquivos, _FORCAR[escolha])

      # Exibido a partir da sessão, e não de dentro do `if st.button`: assim o
      # resultado continua na tela depois de qualquer reexecução do script
      # (por exemplo, o clique em "Baixar").
      resultado = st.session_state.get("resultado")
      if resultado:
```
por este (note que `resultado` é lido **antes** do `if analise:` e que o último `elif resultado:` fica colado ao bloco `if analise:`, senão a cadeia `if/elif/else` vira erro de sintaxe; o corpo do cartão de resumo e o `else: st.info(...)` que já existem logo abaixo **não mudam**):
```python
      criterio = st.selectbox(
          "Se o mesmo ato aparecer em mais de um arquivo", list(_CRITERIOS),
          help="Primeira ocorrência: a do primeiro arquivo (ordem alfabética). "
               "Mais completo: o registro com mais campos preenchidos. "
               "Mais recente: o de maior data de publicação.",
      )

      if arquivos and st.button("🔍 Analisar", type="primary", key="analisar"):
          st.session_state.pop("resultado", None)
          st.session_state["analise"] = _analisar(arquivos, _FORCAR[escolha],
                                                  _CRITERIOS[criterio])

      # Exibidos a partir da sessão, e não de dentro do `if st.button`: assim a
      # análise/o resultado continuam na tela depois de qualquer reexecução do
      # script (por exemplo, o clique em "Baixar").
      analise = st.session_state.get("analise")
      resultado = st.session_state.get("resultado")
      if analise:
          _mostra_analise(analise)
          if st.button("💾 Gravar no banco", type="primary", key="gravar",
                       disabled=not analise["diagnostico"]["pode_continuar"]):
              st.session_state["resultado"] = _gravar(analise)
              st.session_state.pop("analise", None)
              st.rerun()
      elif resultado:
```
O que vem depois (`with st.container(border=True, key="card-resumo"):` ... e o `else: st.info("Envie um ou mais PDFs ...")`) permanece como está.

(i) No cartão de resumo, trocar
```python
              if erros:
                  st.warning(f"{len(erros)} arquivo(s) não puderam ser lidos — veja a "
                             "coluna Erro acima.")
```
por:
```python
              for e in erros:
                  st.error(f"**{e['Arquivo']}** não pôde ser lido: {e['Erro']}")
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: tudo passa, inclusive `test_resultado_guardado_sobrevive_a_reexecucao` e `test_pagina_abre_sem_erro_e_pede_pdfs` (a mensagem "Envie um ou mais PDFs" continua aparecendo quando não há análise nem resultado).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: interface em duas etapas (analisar e gravar), critério de duplicados e erros nomeados"
```

---

### Task 16: `.venv` local, documentação e verificação final

**Files:**
- Modify: `Mapeador.bat`
- Modify: `README.md`
- Create: `CHANGELOG.md`

**Interfaces:** nenhuma nova; fecha o plano.

- [ ] **Step 1: `Mapeador.bat` — ambiente isolado**

No bloco `if not defined PY (... exit /b 1)`, logo **depois** dele (antes da linha `%PY% iniciar.py`), acrescentar:
```bat
REM Ambiente isolado: as dependencias ficam em .venv, sem mexer no Python global.
if not exist ".venv\Scripts\python.exe" (
    echo   Preparando o ambiente isolado ^(so na primeira vez^)...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo.
        echo   [ERRO] Nao foi possivel criar o ambiente .venv.
        echo.
        pause
        exit /b 1
    )
)
set "PY=.venv\Scripts\python.exe"
```
(`iniciar.py` e o bootstrap usam `sys.executable`, então passam a instalar dentro do `.venv`.)

- [ ] **Step 2: `CHANGELOG.md`**

```markdown
# Histórico de versões

## 0.7.0
- Interface em duas etapas: **Analisar** (diagnóstico, nada é gravado) e **Gravar**.
- Critério para o mesmo ato em vários arquivos: primeira ocorrência (padrão), mais completo ou mais recente (interface e `--dedup`).
- Histórico de alterações (tabela `historico`): reimportar um ato com dados diferentes guarda a versão anterior; aparece no detalhe.
- Registro das importações (nome, SHA-256, tipo, quantidade, data e versão) na tabela `importacoes`.
- Busca sem acento e sem diferença de maiúsculas; agora também na resposta, no CNPJ e no número do regime.
- Lista de resultados leve; o detalhe é buscado ao selecionar a linha. A planilha só é gerada ao clicar em baixar.
- CLI: `--dedup`, `--simular`; sai com código **2** se algum PDF falhar (os demais são gravados) e mostra cada erro por arquivo.
- Pasta de dados configurável (`MAPEADOR_DADOS`); `MAPEADOR_BANCO` vale também na CLI; log rotativo em `<dados>/logs/app.log`.
- Schema versionado (`PRAGMA user_version`); banco criado por versão mais nova é recusado com mensagem clara.
- `Mapeador.bat` cria um `.venv` local. Streamlit passa a exigir 1.63 ou superior.
```

- [ ] **Step 3: `README.md`**

(a) Substituir o bloco de uso da CLI
```
    python processar.py <pasta_com_pdfs> [--banco arquivo.db] [--xlsx saida.xlsx]
```
por:
```
    python processar.py <pasta_com_pdfs> [--banco arquivo.db] [--xlsx saida.xlsx]
                        [--dedup primeira|completo|recente] [--simular]

`--simular` lê e diagnostica os PDFs sem gravar nada. `--dedup` escolhe qual
registro fica quando o mesmo ato aparece em mais de um arquivo (padrão:
`primeira`). Códigos de saída: 0 = tudo certo; 1 = uso incorreto, nenhum PDF,
planilha aberta no Excel ou banco de versão mais nova; 2 = algum PDF falhou
(os demais foram gravados) — cada erro é listado, por arquivo, em stderr.
```
(b) Antes do título `## Testes`, inserir:
```markdown
## Dados, logs e histórico
- `MAPEADOR_DADOS` define a pasta do banco e dos logs (padrão: a raiz do projeto);
  `MAPEADOR_BANCO` aponta um arquivo de banco específico, na interface e na CLI.
- O log fica em `<dados>/logs/app.log` (rotativo, ~1 MB × 3) e traz o traceback das falhas.
- Reimportar um ato com dados diferentes **atualiza** o registro e guarda a versão
  anterior na tabela `historico` (aparece em "Histórico de alterações" no detalhe).
  Cada PDF importado é registrado em `importacoes` com o SHA-256 e a versão do app.
- O banco guarda a versão do schema (`PRAGMA user_version`). Um banco criado por
  versão mais nova é recusado, sem alteração, até a ferramenta ser atualizada.
- Na aba Processar, **Analisar** lê os PDFs e mostra o diagnóstico (erros por arquivo,
  CNPJ inválido, campos vazios, datas fora do padrão) sem gravar; **Gravar no banco**
  só grava depois. Os arquivos com erro não impedem a gravação dos demais.
```
(c) Na seção "Estrutura", acrescentar as linhas:
```
- core/execucao.py  — execução completa (carregar → diagnosticar → gravar), usada pela CLI e pela interface
- core/diagnostico.py — erros e avisos do lote antes de gravar
- core/texto.py     — normalização de texto para a busca
- core/log.py       — log em arquivo
- core/versao.py    — versão do app
```
(d) Na seção "Distribuição", acrescentar uma linha: `O Mapeador.bat cria um .venv na pasta da ferramenta na primeira execução (precisa de internet nessa vez).`

- [ ] **Step 4: Verificação automática final**

Run: `pytest -q`
Expected: toda a suíte passa. Confirme também que a execução **não** criou arquivos na raiz: `git status --short` não deve listar `mapeamento.db`, `logs/` nem `.venv/` (estão no `.gitignore`).

- [ ] **Step 5: Verificação manual (a interface não é totalmente coberta pelo `AppTest`, que não simula upload)**

Rodar `python iniciar.py` (ou `Mapeador.bat` numa pasta onde `.venv` ainda não exista — deve criá-lo) e conferir:
1. Perfil Administrador → enviar `tests/fixtures/Consultas_1_a_3_de_2026.pdf` e `Regime_Krona_2col.pdf` → **Analisar**: aparecem a tabela de arquivos, as métricas e os avisos; **nenhum** dado novo no banco.
2. Enviar também um arquivo qualquer renomeado para `.pdf` (texto solto): aparece um erro vermelho com o **nome do arquivo e o motivo**; **Gravar no banco** continua habilitado.
3. **Gravar no banco** → resumo com novos/atualizados e botão de baixar a planilha da sessão.
4. Analisar e gravar de novo os mesmos PDFs: tudo "atualizado", sem duplicar; escolher "Mais completo" e "Mais recente" no seletor e repetir sem erro.
5. Aba Consultar: buscar `substituicao` (sem acento) encontra "substituição"; selecionar uma linha abre o detalhe completo; "Baixar estes resultados" só gera o arquivo ao clicar.
6. CLI: `python processar.py tests/fixtures --simular` imprime o diagnóstico e termina sem gravar; numa pasta com um PDF corrompido, `echo %ERRORLEVEL%` mostra `2` e o erro aparece com o nome do arquivo.

- [ ] **Step 6: Commit**

```bash
git add Mapeador.bat README.md CHANGELOG.md
git commit -m "docs: .venv local no .bat, README e CHANGELOG da versão 0.7.0"
```

---

## Fora deste plano (decidido não fazer agora)

Pool de processos e botão Cancelar no Streamlit (Opções B/C) · `argparse` na CLI · correção dos campos vazios de regimes (vigência/data: bug de parser, plano próprio com PDFs reais) · fonte Urbanist local · escapar Markdown do texto dos regimes · remover `scripts/diag_consultas.py` · limpar `docs/superpowers/`.
