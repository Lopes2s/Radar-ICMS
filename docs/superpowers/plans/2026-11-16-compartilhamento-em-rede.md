# Compartilhamento em Rede Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar a equipe abrir a ferramenta por um atalho numa pasta de rede, sem janela de console e sem instalar nada, todos vendo o mesmo banco com segurança.

**Architecture:** Código, Python portátil e banco ficam numa pasta de rede; cada pessoa roda o servidor Streamlit localmente (`127.0.0.1`). O perfil Consulta lê o SQLite em modo somente leitura; a gravação do Administrador é protegida por trava de arquivo, espera de bloqueio e backup prévio. O launcher roda com `pythonw.exe`.

**Tech Stack:** Python 3.14 (stdlib: sqlite3, json, os, threading), Streamlit, pytest/AppTest, PowerShell e VBScript para montagem e atalho. Nenhuma dependência nova.

**Spec:** `docs/superpowers/specs/2026-11-16-compartilhamento-em-rede-design.md`

## Global Constraints

- Nenhuma dependência nova: só biblioteca padrão (`requirements.txt` não muda).
- O servidor continua escutando só em `127.0.0.1` (`--server.address 127.0.0.1` em `iniciar.py` não pode mudar).
- Não usar WAL: o modo de journal fica no padrão (`delete`), porque WAL não funciona em pasta de rede.
- Espera de bloqueio do SQLite: 30 s. Validade da trava de importação: 15 min. Backups mantidos: 10. Ociosidade: 600 s (após ter havido navegador), carência inicial 180 s.
- Quem encontra a trava ocupada ESPERA antes de desistir: `MAPEADOR_ESPERA_TRAVA_S` (padrão 60 s), checando a cada 2 s. Gravar a importação e as edições manuais (editar ato, aplicar CNAE, consultar CNPJ pelo detalhe) usam a trava.
- Nome da trava: `importando.lock`; backups em `<pasta do banco>/backups/mapeamento-AAAAMMDD-HHMMSS.db`.
- Variáveis de ambiente novas: `MAPEADOR_ESPERA_TRAVA_S`, `MAPEADOR_LOGS` (pasta dos logs), `MAPEADOR_LOCAL` (pasta local do usuário: marcador do servidor e log do servidor), `MAPEADOR_MODO_ATALHO=1` (liga botão Encerrar e vigia de ociosidade).
- Textos da interface em português do Brasil, no tom já usado no app.
- `scripts/Mapeador.vbs` só com caracteres ASCII (sem acentos).
- Windows 64 bits; Python embeddable `amd64`, versão padrão `3.14.6`.
- Versão do app: `0.10.0` (`core/versao.py`, README e CHANGELOG). Schema do banco não muda (`SCHEMA_VERSAO = 4`).
- Mensagens de commit sem linha `Co-Authored-By` (preferência do usuário neste projeto).

## Review Focus

Entradas e falhas que o spec implica, mas nenhuma tarefa testaria por acaso, da mais provável para a menos:

1. **Pasta de rede fora do ar / banco ainda inexistente para quem só consulta**: deve aparecer uma mensagem clara, sem traceback, e o SQLite **não** pode criar um arquivo de banco vazio no caminho (teste na Tarefa 1 e na Tarefa 4).
2. **Trava deixada por queda de energia ou de rede**: expira em 15 min e mostra quem a tinha; arquivo de trava ilegível (gravação pela metade) conta como ocupado, não como livre (Tarefa 2).
3. **Duas pessoas gravando juntas** (importação ou edição manual): a segunda espera até 60 s a vez e, se não vier, vê o nome de quem grava; "database is locked" e falhas de backup viram mensagem, a análise continua na tela, a trava só é liberada por quem a tem (Tarefas 2 e 4).
4. **Banco de schema antigo aberto primeiro por quem só consulta** (depois de atualizar a ferramenta): pede ao Administrador abrir a ferramenta, em vez de tentar migrar com um perfil somente leitura (Tarefa 1).
5. **Clicar no atalho duas vezes, ou falha antes de a interface abrir**: reabre o servidor já em execução em vez de subir outro; sem console, o erro de inicialização aparece numa caixa de mensagem e a saída do servidor vai para arquivo (Tarefa 7).

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `core/armazenamento.py` | modificar | espera de bloqueio de 30 s, `somente_leitura`, `sessao_leitura`, `BancoIndisponivel` |
| `core/consulta.py` | modificar | `exportar_busca` sempre somente leitura |
| `core/trava.py` | criar | trava de importação em arquivo, com validade |
| `core/backup.py` | criar | backup consistente do banco e poda dos antigos |
| `core/log.py` | modificar | `MAPEADOR_LOGS` leva o log para uma pasta local |
| `core/ocioso.py` | criar | vigia de ociosidade (lógica pura) e contagem de sessões do Streamlit |
| `app.py` | modificar | perfil Consulta lê só leitura; gravar com trava e backup; aviso de quem grava; Encerrar; vigia |
| `iniciar.py` | modificar | reaproveita servidor em execução, funciona sem console, avisa erros |
| `scripts/Mapeador.vbs` | criar | atalho de duplo clique, janela oculta |
| `scripts/montar_rede.ps1` | criar | monta/atualiza a pasta de rede |
| `tests/test_trava.py`, `tests/test_backup.py`, `tests/test_ocioso.py`, `tests/test_rede.py` | criar | testes dos módulos novos e do atalho |
| `tests/test_armazenamento.py`, `tests/test_log.py`, `tests/test_app.py`, `tests/test_iniciar.py`, `tests/conftest.py` | modificar | testes das mudanças |
| `README.md`, `CHANGELOG.md`, `core/versao.py` | modificar | documentação e versão |

---

### Task 1: Leitura somente leitura e espera de bloqueio

**Files:**
- Modify: `core/armazenamento.py` (classe `SchemaMaisNovo` ~linha 99, `conectar`/`aberta`/`sessao` ~linhas 121-150, `criar_esquema` ~linha 328)
- Modify: `core/consulta.py:65-72` (`exportar_busca`)
- Test: `tests/test_armazenamento.py`

**Interfaces:**
- Consumes: `armazenamento.caminho_do_banco(caminho_bd)`, `versao_do_schema(conn)`, `SCHEMA_VERSAO`, `SchemaMaisNovo`.
- Produces:
  - `armazenamento.BancoIndisponivel(RuntimeError)`
  - `armazenamento.conectar(caminho_bd=None, somente_leitura=False) -> sqlite3.Connection`
  - `armazenamento.aberta(caminho_bd=None, somente_leitura=False)` (context manager)
  - `armazenamento.sessao_leitura(caminho_bd=None)` (context manager que entrega a conexão; levanta `BancoIndisponivel` ou `SchemaMaisNovo`)

- [ ] **Step 1: Write the failing tests**

Acrescentar ao fim de `tests/test_armazenamento.py`:

```python
def test_sessao_leitura_nao_cria_o_arquivo_quando_o_banco_nao_existe(tmp_path):
    caminho = tmp_path / "nao_existe.db"
    with pytest.raises(armazenamento.BancoIndisponivel, match="ainda não existe"):
        with armazenamento.sessao_leitura(str(caminho)):
            pass
    assert not caminho.exists()


def test_sessao_leitura_le_um_banco_pronto(tmp_path):
    caminho = str(tmp_path / "pronto.db")
    with armazenamento.sessao(caminho):
        pass
    with armazenamento.sessao_leitura(caminho) as conn:
        assert conn.execute("SELECT COUNT(*) FROM consultas").fetchone()[0] == 0


def test_sessao_leitura_nao_deixa_gravar(tmp_path):
    caminho = str(tmp_path / "pronto.db")
    with armazenamento.sessao(caminho):
        pass
    with armazenamento.sessao_leitura(caminho) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE intruso (a)")


def test_sessao_leitura_pede_ao_administrador_quando_o_schema_e_antigo(tmp_path):
    caminho = tmp_path / "antigo.db"
    conn = sqlite3.connect(str(caminho))
    conn.execute("CREATE TABLE x (a)")           # só assim o arquivo existe; user_version 0
    conn.commit()
    conn.close()
    with pytest.raises(armazenamento.BancoIndisponivel, match="Administrador"):
        with armazenamento.sessao_leitura(str(caminho)):
            pass


def test_sessao_leitura_recusa_banco_de_versao_mais_nova(tmp_path):
    caminho = str(tmp_path / "novo.db")
    conn = sqlite3.connect(caminho)
    conn.execute("CREATE TABLE x (a)")
    conn.execute(f"PRAGMA user_version = {armazenamento.SCHEMA_VERSAO + 1}")
    conn.commit()
    conn.close()
    with pytest.raises(armazenamento.SchemaMaisNovo):
        with armazenamento.sessao_leitura(caminho):
            pass


def test_conexao_espera_trinta_segundos_por_bloqueio(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "t.db"))
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30_000


def test_banco_novo_usa_journal_delete_e_nao_wal(tmp_path):
    # WAL não funciona em pasta de rede: o padrão (delete) precisa ser mantido.
    conn = armazenamento.conectar(str(tmp_path / "t.db"))
    armazenamento.criar_esquema(conn)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_armazenamento.py -k "sessao_leitura or espera_trinta or journal_delete" -v`
Expected: FAIL (`AttributeError: ... has no attribute 'sessao_leitura'` / `BancoIndisponivel`; o de busy_timeout falha com 5000 != 30000).

- [ ] **Step 3: Write the implementation**

Em `core/armazenamento.py`, logo depois da classe `SchemaMaisNovo`, acrescentar:

```python
class BancoIndisponivel(RuntimeError):
    """O banco não existe ou está num schema mais antigo do que esta versão lê.

    Quem só consulta não cria nem migra o banco: o Administrador precisa abrir a
    ferramenta antes (ver `sessao_leitura`)."""


def _msg_schema_mais_novo(atual: int) -> str:
    return (f"Este banco foi criado por uma versão mais nova da ferramenta "
            f"(schema {atual}; esta versão conhece até {SCHEMA_VERSAO}). "
            f"Atualize a ferramenta antes de abrir este banco.")
```

Em `criar_esquema`, trocar o `raise SchemaMaisNovo(...)` de várias linhas por:

```python
    if atual > SCHEMA_VERSAO:
        raise SchemaMaisNovo(_msg_schema_mais_novo(atual))
```

Substituir `conectar`, `aberta` e acrescentar `sessao_leitura` (mantendo `sessao` como está):

```python
# Em pasta de rede o bloqueio demora mais que os 5 s padrão do sqlite3.
_ESPERA_BLOQUEIO_S = 30


def conectar(caminho_bd: str | None = None,
             somente_leitura: bool = False) -> sqlite3.Connection:
    """Abre (ou cria) o banco (ver `caminho_do_banco` para a escolha do arquivo).

    `somente_leitura` usa PRAGMA query_only em vez de abrir o arquivo com
    `mode=ro`, porque a URI de leitura não funciona bem com caminhos de rede
    (`\\\\servidor\\pasta`)."""
    conn = sqlite3.connect(caminho_do_banco(caminho_bd), timeout=_ESPERA_BLOQUEIO_S)
    conn.row_factory = sqlite3.Row
    conn.create_function('norm', 1, normalizar, deterministic=True)
    if somente_leitura:
        conn.execute('PRAGMA query_only = ON')
    return conn


@contextmanager
def aberta(caminho_bd: str | None = None, somente_leitura: bool = False):
    """Conexão que é FECHADA ao sair do bloco, com ou sem erro."""
    conn = conectar(caminho_bd, somente_leitura)
    try:
        yield conn
    finally:
        conn.close()
```

E, depois de `sessao`:

```python
@contextmanager
def sessao_leitura(caminho_bd: str | None = None):
    """Conexão SOMENTE LEITURA para o perfil Consulta.

    Não cria o arquivo (o sqlite3 criaria um banco vazio no caminho) e não migra
    o esquema: se o banco não existe ou é de um schema mais antigo, quem tem
    permissão de gravar (o Administrador) precisa abrir a ferramenta primeiro."""
    caminho = caminho_do_banco(caminho_bd)
    if not os.path.exists(caminho):
        raise BancoIndisponivel(
            "O banco de dados ainda não existe nesta pasta. Peça ao Administrador "
            "para abrir a ferramenta e importar os PDFs, e confira se a pasta de "
            "rede está acessível.")
    with aberta(caminho_bd, somente_leitura=True) as conn:
        atual = versao_do_schema(conn)
        if atual > SCHEMA_VERSAO:
            raise SchemaMaisNovo(_msg_schema_mais_novo(atual))
        if atual < SCHEMA_VERSAO:
            raise BancoIndisponivel(
                "O banco está numa versão antiga. O Administrador precisa abrir a "
                "ferramenta uma vez para atualizá-lo; depois é só recarregar.")
        yield conn
```

Em `core/consulta.py`, trocar a linha `with armazenamento.aberta(caminho_bd) as conn:` de `exportar_busca` por:

```python
    with armazenamento.aberta(caminho_bd, somente_leitura=True) as conn:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_armazenamento.py tests/test_consulta.py tests/test_ajustes.py tests/test_receita_banco.py -v`
Expected: PASS (todos, inclusive os antigos).

- [ ] **Step 5: Commit**

```bash
git add core/armazenamento.py core/consulta.py tests/test_armazenamento.py
git commit -m "feat: leitura somente leitura do banco e espera de bloqueio de 30 s"
```

---

### Task 2: Trava de importação

**Files:**
- Create: `core/trava.py`
- Test: `tests/test_trava.py`

**Interfaces:**
- Consumes: nada de outras tarefas.
- Produces:
  - `trava.NOME_ARQUIVO = "importando.lock"`, `trava.VALIDADE_PADRAO = timedelta(minutes=15)`
  - `trava.Importacao` (NamedTuple: `quem: str`, `maquina: str`, `desde: datetime`, `renovado_em: datetime`) com método `texto() -> str` (ex.: `"maria (PC-02) está gravando desde 14:32"`)
  - `trava.ImportacaoEmAndamento(Exception)` com atributo `importacao`
  - `trava.quem_sou() -> tuple[str, str]` (usuário, máquina)
  - `trava.situacao(pasta, agora=None, validade=VALIDADE_PADRAO) -> Importacao | None`
  - `trava.adquirir(pasta, quem, maquina, agora=None, validade=VALIDADE_PADRAO) -> Importacao | None` (None = conseguiu; senão, quem está com a trava)
  - `trava.liberar(pasta, quem, maquina) -> bool`
  - `trava.importando(pasta, quem=None, maquina=None, esperar_s=0.0, intervalo_s=2.0, dormir=time.sleep, relogio=time.monotonic)` (context manager; espera até `esperar_s` segundos a trava ficar livre; levanta `ImportacaoEmAndamento` se não ficar)

- [ ] **Step 1: Write the failing tests**

Criar `tests/test_trava.py`:

```python
import os
from datetime import datetime, timedelta, timezone

import pytest

from core import trava

T0 = datetime(2026, 11, 16, 14, 0, tzinfo=timezone.utc)


def test_adquirir_com_a_pasta_livre_cria_a_trava(tmp_path):
    assert trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0) is None
    assert (tmp_path / trava.NOME_ARQUIVO).exists()
    atual = trava.situacao(str(tmp_path), agora=T0)
    assert (atual.quem, atual.maquina) == ("ana", "PC-01")


def test_segunda_pessoa_recebe_quem_esta_importando(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    outro = trava.adquirir(str(tmp_path), "bia", "PC-02", agora=T0 + timedelta(minutes=1))
    assert (outro.quem, outro.maquina) == ("ana", "PC-01")
    # a trava continua sendo da primeira pessoa
    assert trava.situacao(str(tmp_path), agora=T0).quem == "ana"


def test_trava_vencida_pode_ser_assumida(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    depois = T0 + trava.VALIDADE_PADRAO + timedelta(seconds=1)
    assert trava.situacao(str(tmp_path), agora=depois) is None
    assert trava.adquirir(str(tmp_path), "bia", "PC-02", agora=depois) is None
    assert trava.situacao(str(tmp_path), agora=depois).quem == "bia"


def test_trava_ilegivel_recente_conta_como_ocupada(tmp_path):
    # arquivo criado por outra máquina e ainda sendo escrito: não pode virar "livre"
    (tmp_path / trava.NOME_ARQUIVO).write_text("", encoding="utf-8")
    agora = datetime.now(timezone.utc)
    atual = trava.situacao(str(tmp_path), agora=agora)
    assert atual is not None
    assert trava.adquirir(str(tmp_path), "bia", "PC-02", agora=agora) is not None


def test_trava_ilegivel_antiga_vence_como_qualquer_outra(tmp_path):
    caminho = tmp_path / trava.NOME_ARQUIVO
    caminho.write_text("lixo", encoding="utf-8")
    antigo = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
    os.utime(caminho, (antigo, antigo))
    assert trava.situacao(str(tmp_path)) is None


def test_liberar_so_remove_a_propria_trava(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    assert trava.liberar(str(tmp_path), "bia", "PC-02") is False
    assert (tmp_path / trava.NOME_ARQUIVO).exists()
    assert trava.liberar(str(tmp_path), "ana", "PC-01") is True
    assert not (tmp_path / trava.NOME_ARQUIVO).exists()


def test_importando_libera_ao_sair_mesmo_com_erro(tmp_path):
    with pytest.raises(ValueError):
        with trava.importando(str(tmp_path), "ana", "PC-01"):
            raise ValueError("falhou no meio")
    assert not (tmp_path / trava.NOME_ARQUIVO).exists()


def test_importando_espera_a_trava_ser_liberada(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01")
    dormidas = []

    def dormir(segundos):
        dormidas.append(segundos)
        trava.liberar(str(tmp_path), "ana", "PC-01")      # a ana termina durante a espera

    with trava.importando(str(tmp_path), "bia", "PC-02", esperar_s=10,
                          intervalo_s=2, dormir=dormir):
        assert trava.situacao(str(tmp_path)).quem == "bia"
    assert dormidas == [2]


def test_importando_desiste_depois_do_tempo_de_espera(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01")
    t = [0.0]

    def dormir(segundos):
        t[0] += segundos

    with pytest.raises(trava.ImportacaoEmAndamento):
        with trava.importando(str(tmp_path), "bia", "PC-02", esperar_s=6, intervalo_s=2,
                              dormir=dormir, relogio=lambda: t[0]):
            pass
    assert t[0] == 6
    assert trava.situacao(str(tmp_path)).quem == "ana"    # a trava alheia segue intacta


def test_importando_com_trava_ocupada_levanta_com_o_nome(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01")
    with pytest.raises(trava.ImportacaoEmAndamento, match=r"ana \(PC-01\)") as erro:
        with trava.importando(str(tmp_path), "bia", "PC-02"):
            pass
    assert erro.value.importacao.quem == "ana"


def test_texto_mostra_quem_e_a_hora_local(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    texto = trava.situacao(str(tmp_path), agora=T0).texto()
    assert texto.startswith("ana (PC-01) está gravando desde ")
    hora = texto.rsplit(" ", 1)[1]
    assert len(hora) == 5 and hora[2] == ":"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_trava.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.trava'`).

- [ ] **Step 3: Write the implementation**

Criar `core/trava.py`:

```python
# core/trava.py
"""Trava de importação: um arquivo ao lado do banco que diz quem está gravando.

O SQLite em pasta de rede não tem bloqueio confiável contra escritas simultâneas;
como só uma ou duas pessoas importam, basta impedir que duas gravem ao mesmo
tempo e mostrar a quem está com a vez. A trava VENCE sozinha (queda de rede ou de
energia não pode travar ninguém para sempre) e só quem a criou a remove.

Só biblioteca padrão. `pasta` é a pasta do banco."""
import getpass
import json
import os
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

NOME_ARQUIVO = "importando.lock"
VALIDADE_PADRAO = timedelta(minutes=15)


class Importacao(NamedTuple):
    quem: str
    maquina: str
    desde: datetime
    renovado_em: datetime

    def texto(self) -> str:
        hora = self.desde.astimezone().strftime("%H:%M")
        return f"{self.quem} ({self.maquina}) está gravando desde {hora}"


class ImportacaoEmAndamento(Exception):
    """Outra pessoa está gravando: `importacao` diz quem."""

    def __init__(self, importacao: Importacao):
        super().__init__(f"{importacao.texto()}. Tente de novo em instantes.")
        self.importacao = importacao


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _caminho(pasta: str) -> str:
    return os.path.join(pasta, NOME_ARQUIVO)


def quem_sou() -> tuple[str, str]:
    """(usuário do Windows, nome da máquina)."""
    try:
        usuario = getpass.getuser()
    except Exception:  # noqa: BLE001 - sem usuário resolvível, o nome não é essencial
        usuario = "desconhecido"
    return usuario, socket.gethostname()


def situacao(pasta: str, agora: datetime | None = None,
             validade: timedelta = VALIDADE_PADRAO) -> Importacao | None:
    """Quem está importando agora, ou None se ninguém (trava ausente ou vencida).

    Arquivo ilegível (outra máquina ainda o escrevendo) vale como OCUPADO, com a
    validade contada pela data do arquivo, para nunca virar "livre" por engano."""
    agora = agora or _agora()
    caminho = _caminho(pasta)
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        atual = Importacao(dados["quem"], dados["maquina"],
                           datetime.fromisoformat(dados["desde"]),
                           datetime.fromisoformat(dados["renovado_em"]))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        try:
            modificado = datetime.fromtimestamp(os.path.getmtime(caminho), timezone.utc)
        except OSError:
            return None
        atual = Importacao("alguém", "outra máquina", modificado, modificado)
    return None if agora - atual.renovado_em > validade else atual


def adquirir(pasta: str, quem: str, maquina: str, agora: datetime | None = None,
             validade: timedelta = VALIDADE_PADRAO) -> Importacao | None:
    """Tenta assumir a trava. Devolve None se conseguiu; senão, quem a tem.

    A criação é atômica (O_EXCL): duas pessoas clicando juntas, só uma cria."""
    agora = agora or _agora()
    caminho = _caminho(pasta)
    for _ in range(2):
        try:
            fd = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            atual = situacao(pasta, agora, validade)
            if atual is not None:
                return atual
            try:                     # vencida: quem chegar primeiro a remove
                os.remove(caminho)
            except OSError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump({"quem": quem, "maquina": maquina,
                       "desde": agora.isoformat(),
                       "renovado_em": agora.isoformat()}, arquivo)
        return None
    return situacao(pasta, agora, validade) or Importacao(
        "alguém", "outra máquina", agora, agora)


def liberar(pasta: str, quem: str, maquina: str) -> bool:
    """Remove a trava SE for de `quem`/`maquina`. Devolve se removeu."""
    atual = situacao(pasta, validade=timedelta.max)
    if atual is None or (atual.quem, atual.maquina) != (quem, maquina):
        return False
    try:
        os.remove(_caminho(pasta))
    except OSError:
        return False
    return True


@contextmanager
def importando(pasta: str, quem: str | None = None, maquina: str | None = None,
               esperar_s: float = 0.0, intervalo_s: float = 2.0,
               dormir=time.sleep, relogio=time.monotonic):
    """Segura a trava durante o bloco. Se estiver ocupada, espera até `esperar_s`
    segundos (olhando a cada `intervalo_s`); `ImportacaoEmAndamento` se não ficar livre."""
    if quem is None or maquina is None:
        quem, maquina = quem_sou()
    limite = relogio() + esperar_s
    while True:
        outro = adquirir(pasta, quem, maquina)
        if outro is None:
            break
        if relogio() + intervalo_s > limite:
            raise ImportacaoEmAndamento(outro)
        dormir(intervalo_s)
    try:
        yield
    finally:
        liberar(pasta, quem, maquina)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_trava.py -v`
Expected: PASS (9 testes).

- [ ] **Step 5: Commit**

```bash
git add core/trava.py tests/test_trava.py
git commit -m "feat: trava de importacao em arquivo, com validade de 15 minutos"
```

---

### Task 3: Backup antes de gravar

**Files:**
- Create: `core/backup.py`
- Test: `tests/test_backup.py`

**Interfaces:**
- Consumes: nada de outras tarefas.
- Produces: `backup.PREFIXO = "mapeamento-"`, `backup.MANTER_PADRAO = 10`, `backup.fazer_backup(caminho_bd: str, pasta_backups: str, manter: int = 10, agora: datetime | None = None) -> str | None` (devolve o caminho da cópia, ou None se o banco ainda não existe).

- [ ] **Step 1: Write the failing tests**

Criar `tests/test_backup.py`:

```python
import sqlite3
from datetime import datetime, timedelta

from core import backup


def _banco(caminho, valor="x"):
    conn = sqlite3.connect(str(caminho))
    conn.execute("CREATE TABLE t (a)")
    conn.execute("INSERT INTO t VALUES (?)", (valor,))
    conn.commit()
    conn.close()


def test_backup_e_uma_copia_legivel_do_banco(tmp_path):
    origem = tmp_path / "mapeamento.db"
    _banco(origem, "dado importante")
    destino = backup.fazer_backup(str(origem), str(tmp_path / "backups"),
                                  agora=datetime(2026, 11, 16, 14, 30, 5))
    assert destino.endswith("mapeamento-20261116-143005.db")
    conn = sqlite3.connect(destino)
    assert conn.execute("SELECT a FROM t").fetchone()[0] == "dado importante"
    conn.close()


def test_sem_banco_nao_faz_nada(tmp_path):
    assert backup.fazer_backup(str(tmp_path / "nao_existe.db"),
                               str(tmp_path / "backups")) is None
    assert not (tmp_path / "backups").exists()


def test_mantem_so_os_mais_recentes_e_ignora_outros_arquivos(tmp_path):
    origem = tmp_path / "mapeamento.db"
    _banco(origem)
    pasta = tmp_path / "backups"
    base = datetime(2026, 11, 16, 8, 0, 0)
    for i in range(5):
        backup.fazer_backup(str(origem), str(pasta), manter=3,
                            agora=base + timedelta(minutes=i))
    (pasta / "anotacoes.txt").write_text("não mexa", encoding="utf-8")
    nomes = sorted(p.name for p in pasta.glob("mapeamento-*.db"))
    assert nomes == ["mapeamento-20261116-080200.db",
                     "mapeamento-20261116-080300.db",
                     "mapeamento-20261116-080400.db"]
    assert (pasta / "anotacoes.txt").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backup.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.backup'`).

- [ ] **Step 3: Write the implementation**

Criar `core/backup.py`:

```python
# core/backup.py
"""Backup do banco antes de cada gravação.

Usa a API de backup do SQLite (cópia consistente, mesmo com o banco em uso), não
uma cópia de arquivo. Só biblioteca padrão."""
import os
import sqlite3
from datetime import datetime

PREFIXO = "mapeamento-"
MANTER_PADRAO = 10


def fazer_backup(caminho_bd: str, pasta_backups: str, manter: int = MANTER_PADRAO,
                 agora: datetime | None = None) -> str | None:
    """Copia o banco para `<pasta_backups>/mapeamento-AAAAMMDD-HHMMSS.db`, apaga
    as cópias além das `manter` mais recentes e devolve o caminho da nova.
    Devolve None se o banco ainda não existe (primeira importação)."""
    if not os.path.exists(caminho_bd):
        return None
    os.makedirs(pasta_backups, exist_ok=True)
    carimbo = (agora or datetime.now()).strftime("%Y%m%d-%H%M%S")
    destino = os.path.join(pasta_backups, f"{PREFIXO}{carimbo}.db")
    origem = sqlite3.connect(caminho_bd)
    copia = sqlite3.connect(destino)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    _podar(pasta_backups, manter)
    return destino


def _podar(pasta_backups: str, manter: int) -> None:
    """O nome carrega a data, então ordenar por nome é ordenar por idade."""
    if manter <= 0:
        return
    antigos = sorted(n for n in os.listdir(pasta_backups)
                     if n.startswith(PREFIXO) and n.endswith(".db"))[:-manter]
    for nome in antigos:
        try:
            os.remove(os.path.join(pasta_backups, nome))
        except OSError:
            pass   # arquivo em uso: fica para a próxima poda
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_backup.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add core/backup.py tests/test_backup.py
git commit -m "feat: backup consistente do banco antes de cada gravacao"
```

---

### Task 4: Interface — leitura segura, gravar com trava e backup

**Files:**
- Modify: `app.py` (imports ~linhas 1-22; `_persistir` ~linha 44; `_gravar` ~linha 325; sidebar/banco ~linhas 539-543; botão Gravar ~linhas 608-616; `with aba_consultar` ~linha 692)
- Modify: `tests/test_app.py` (fixture `_isola_banco`; testes novos)
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `armazenamento.sessao_leitura`, `armazenamento.BancoIndisponivel`, `armazenamento.SchemaMaisNovo`, `armazenamento.caminho_do_banco`, `trava.importando`, `trava.situacao`, `trava.ImportacaoEmAndamento`, `backup.fazer_backup`.
- Produces: em `app.py`, `_pasta_do_banco() -> str`, `_sessao_do_perfil(perfil)`, `_espera_da_trava() -> float` e `_escrevendo()` (context manager: segura a trava esperando `_espera_da_trava()` s; usadas só dentro do app).

- [ ] **Step 1: Write the failing tests**

Em `tests/test_app.py`, trocar a fixture `_isola_banco` por esta (o banco já existe, como existiria depois de o Administrador abrir a ferramenta uma vez):

```python
@pytest.fixture(autouse=True)
def _isola_banco(monkeypatch, tmp_path):
    """(docstring existente mantida)

    O banco é criado aqui, como o Administrador faria ao abrir a ferramenta:
    o perfil Consulta só lê e não cria o arquivo."""
    caminho = tmp_path / "app_teste.db"
    monkeypatch.setenv("MAPEADOR_BANCO", str(caminho))
    with armazenamento.sessao(str(caminho)):
        pass
```

Acrescentar ao fim do arquivo (o `import sqlite3` e `from core import ... backup, trava` ficam no topo: ajustar a linha `from core import acesso, armazenamento, diagnostico, edicao, pipeline` para `from core import acesso, armazenamento, backup, diagnostico, edicao, pipeline, trava` e acrescentar `import sqlite3`):

```python
def test_consulta_sem_banco_avisa_sem_criar_o_arquivo(tmp_path):
    caminho = tmp_path / "app_teste.db"
    caminho.unlink()                     # a fixture criou; aqui a rede está sem banco
    at = _app("consulta").run(timeout=30)
    assert not at.exception
    assert any("ainda não existe" in e.value for e in at.error)
    assert not caminho.exists()


def test_consulta_com_banco_de_schema_antigo_pede_ao_administrador(tmp_path):
    caminho = tmp_path / "app_teste.db"
    conn = sqlite3.connect(str(caminho))
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    at = _app("consulta").run(timeout=30)
    assert not at.exception
    assert any("Administrador" in e.value for e in at.error)


def test_gravar_avisa_quem_esta_gravando_e_desiste_depois_da_espera(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPEADOR_ESPERA_TRAVA_S", "0")
    assert trava.adquirir(str(tmp_path), "maria", "PC-02") is None
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    assert not at.exception
    assert not at.button(key="gravar").disabled          # o botão espera a vez, não bloqueia
    assert any("maria (PC-02) está gravando" in w.value for w in at.warning)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert any("maria (PC-02) está gravando" in e.value for e in at.error)
    assert at.session_state["analise"]                   # a análise continua na tela
    assert _regimes_no_banco() == []
    assert trava.situacao(str(tmp_path)).quem == "maria"  # não soltou a trava alheia


def test_edicao_manual_espera_a_trava_e_avisa_quem_grava(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPEADOR_ESPERA_TRAVA_S", "0")
    at = _abre_o_detalhe_do_regime("admin")
    trava.adquirir(str(tmp_path), "maria", "PC-02")
    _linha_0(at)
    at.button(key="editar-registro").click().run(timeout=30)
    at.text_input(key=f"{PREFIXO}|VIGÊNCIA DO RE").input("12 meses")
    _linha_0(at)
    at.button(key=f"{PREFIXO}|enviar").click().run(timeout=30)
    assert not at.exception
    assert _regimes_no_banco()[0]['VIGÊNCIA DO RE'] != '12 meses'
    assert "maria (PC-02) está gravando" in at.session_state["erro_edicao"]


def test_edicao_manual_sem_ninguem_gravando_edita_e_solta_a_trava(tmp_path):
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="editar-registro").click().run(timeout=30)
    at.text_input(key=f"{PREFIXO}|VIGÊNCIA DO RE").input("12 meses")
    _linha_0(at)
    at.button(key=f"{PREFIXO}|enviar").click().run(timeout=30)
    assert not at.exception
    assert _regimes_no_banco()[0]['VIGÊNCIA DO RE'] == '12 meses'
    assert trava.situacao(str(tmp_path)) is None


def test_aplicar_cnae_espera_a_trava_e_avisa_quem_grava(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPEADOR_ESPERA_TRAVA_S", "0")
    _guarda_receita()
    at = _abre_o_detalhe_do_regime("admin")
    trava.adquirir(str(tmp_path), "maria", "PC-02")
    _linha_0(at)
    at.button(key="aplicar-cnae").click().run(timeout=30)
    assert not at.exception
    assert _regimes_no_banco()[0]['CNAE REQUERENTE'] != '6422-1/00'
    assert any("maria (PC-02) está gravando" in t.value for t in at.toast)


def test_consultar_cnpj_espera_a_trava_e_nao_chama_a_rede(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPEADOR_ESPERA_TRAVA_S", "0")
    rede = _com_rede(monkeypatch)
    at = _abre_o_detalhe_do_regime("admin")
    trava.adquirir(str(tmp_path), "maria", "PC-02")
    _linha_0(at)
    at.button(key="consultar-cnpj").click().run(timeout=30)
    assert not at.exception
    assert rede.urls == []
    assert any("maria (PC-02) está gravando" in t.value for t in at.toast)


def test_gravar_faz_backup_antes_e_libera_a_trava(tmp_path):
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert len(list((tmp_path / "backups").glob("mapeamento-*.db"))) == 1
    assert trava.situacao(str(tmp_path)) is None
    assert len(_regimes_no_banco()) == 1


def test_gravar_com_falha_no_banco_avisa_mantem_a_analise_e_libera_a_trava(
        monkeypatch, tmp_path):
    def estoura(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(backup, "fazer_backup", estoura)
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert any("Não foi possível gravar" in e.value for e in at.error)
    assert at.session_state["analise"]
    assert trava.situacao(str(tmp_path)) is None
    assert _regimes_no_banco() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app.py -k "sem_banco or schema_antigo or bloqueado or faz_backup or falha_no_banco" -v`
Expected: FAIL (consulta sem banco cria o arquivo e não mostra erro; sem trava nem backup no `_gravar`).

- [ ] **Step 3: Write the implementation**

Em `app.py`:

1. Imports: `import sqlite3` junto dos demais `import` do topo, e trocar
```python
from core import (acesso, armazenamento, cnpj, consulta, diagnostico, edicao,  # noqa: E402
                  log, planilha)
```
por
```python
from core import (acesso, armazenamento, backup, cnpj, consulta, diagnostico,  # noqa: E402
                  edicao, log, planilha, trava)
```

2. Depois de `_CAMINHO_BANCO = ...`, acrescentar:
```python
def _pasta_do_banco() -> str:
    """Pasta onde moram o banco, a trava de importação e os backups."""
    return os.path.dirname(os.path.abspath(
        armazenamento.caminho_do_banco(_CAMINHO_BANCO)))


def _espera_da_trava() -> float:
    """Quantos segundos uma gravação espera a vez quando outra pessoa está gravando."""
    try:
        return float(os.environ.get("MAPEADOR_ESPERA_TRAVA_S", "60"))
    except ValueError:
        return 60.0


def _escrevendo():
    """Segura a trava de gravação durante uma escrita (importação ou edição manual).
    `trava.ImportacaoEmAndamento` se, passada a espera, outra pessoa ainda estiver gravando."""
    return trava.importando(_pasta_do_banco(), esperar_s=_espera_da_trava())


def _sessao_do_perfil(perfil_atual):
    """Administrador abre (e, se preciso, migra) o banco; Consulta só lê."""
    if perfil_atual == acesso.PERFIL_ADMIN:
        return armazenamento.sessao(_CAMINHO_BANCO)
    return armazenamento.sessao_leitura(_CAMINHO_BANCO)
```

3. Em `_gravar`, trocar o corpo de `lote = analise["lote"]` até a geração do `buf` por (a planilha em memória e o `return` ficam como estão):
```python
    lote = analise["lote"]
    pasta = _pasta_do_banco()
    # a trava segura só uma gravação por vez (esperando a vez, se preciso); o backup
    # vem ANTES de qualquer escrita
    with _escrevendo():
        backup.fazer_backup(armazenamento.caminho_do_banco(_CAMINHO_BANCO),
                            os.path.join(pasta, "backups"))
        mapeamento = _persistir(lote, sobrescrever)
        if cnpj.habilitada():
            with st.spinner("Consultando os CNPJs na Receita Federal…"):
                with armazenamento.sessao(_CAMINHO_BANCO) as conn:
                    _avisar_receita(cnpj.atualizar_do_lote(conn, lote))
```

4. Trocar a verificação do banco logo depois da marca lateral por:
```python
try:
    with _sessao_do_perfil(perfil):
        pass
except (armazenamento.SchemaMaisNovo, armazenamento.BancoIndisponivel) as erro:
    st.error(str(erro))
    st.stop()
```

5. No bloco `if analise:` da aba Processar, trocar o botão Gravar por:
```python
        if analise:
            _mostra_analise(analise)
            outro = trava.situacao(_pasta_do_banco())
            if outro is not None:
                st.warning(f"{outro.texto()}. Ao gravar, a ferramenta espera até "
                           f"{int(_espera_da_trava())} s pela sua vez.")
            if st.button("Gravar no banco", type="primary", key="gravar",
                         icon=":material/save:",
                         disabled=not analise["diagnostico"]["pode_continuar"]):
                try:
                    st.session_state["resultado"] = _gravar(
                        analise, _sobrescrever_marcados(analise))
                except trava.ImportacaoEmAndamento as erro:
                    st.error(str(erro))
                except (OSError, sqlite3.Error) as erro:
                    st.error(f"Não foi possível gravar no banco ({erro}). Confira se a "
                             "pasta de rede está acessível e tente de novo; a análise "
                             "continua na tela.")
                else:
                    st.session_state.pop("analise", None)
                    st.rerun()
```

6. No fim do arquivo, trocar `with armazenamento.sessao(_CAMINHO_BANCO) as conn:` (dentro de `with aba_consultar:`) por `with _sessao_do_perfil(perfil) as conn:`.

7. As três escritas pelo detalhe passam pela trava (a edição no editor da análise só LÊ o banco e fica como está). São callbacks `on_click`, então o aviso vai para o `session_state`:

   - `_salvar_edicao`: trocar `with armazenamento.sessao(_CAMINHO_BANCO) as conn:` por `with _escrevendo(), armazenamento.sessao(_CAMINHO_BANCO) as conn:` e acrescentar, depois do `except (edicao.ChaveEmConflito, ...)` existente:
     ```python
     except trava.ImportacaoEmAndamento as erro:
         st.session_state["erro_edicao"] = str(erro)
         return
     ```
   - `_aplicar_cnae`: o mesmo `with _escrevendo(), armazenamento.sessao(...)` e, junto do `except edicao.RegistroInexistente` existente (dois `except` no mesmo `try`):
     ```python
     except trava.ImportacaoEmAndamento as erro:
         st.session_state["aviso"] = str(erro)
         return
     ```
   - `_consultar_cnpj`: envolver o bloco inteiro com `try:` / `except trava.ImportacaoEmAndamento as erro:` guardando `st.session_state["aviso"] = str(erro)`, chamando `_fecha_selecao_da_tabela()` e retornando; usar `with _escrevendo(), armazenamento.sessao(_CAMINHO_BANCO) as conn:` no lugar do `with armazenamento.sessao(...)` atual (a consulta à rede só acontece com a trava na mão).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS (todos; se algum teste antigo de perfil Consulta falhar por banco inexistente, ele não usa a fixture `_isola_banco` — corrija o teste, não o app).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: perfil Consulta so le; gravar com trava, backup e aviso de quem grava"
```

---

### Task 5: Log por máquina

**Files:**
- Modify: `core/log.py`
- Test: `tests/test_log.py`

**Interfaces:**
- Consumes: nada de outras tarefas.
- Produces: `log.configurar_log(pasta)` passa a respeitar `MAPEADOR_LOGS` (pasta dos logs); sem a variável, o comportamento de hoje (`<pasta>/logs/app.log`).

- [ ] **Step 1: Write the failing test**

Acrescentar ao fim de `tests/test_log.py`:

```python
def test_mapeador_logs_leva_o_log_para_outra_pasta(tmp_path, monkeypatch):
    # Em pasta de rede a rotação do log quebra (vários processos no mesmo
    # arquivo): o atalho aponta MAPEADOR_LOGS para uma pasta local de cada usuário.
    local = tmp_path / "local" / "logs"
    monkeypatch.setenv("MAPEADOR_LOGS", str(local))
    logger = log.configurar_log(str(tmp_path / "rede"))
    logger.info("na máquina")
    for handler in logger.handlers:
        handler.flush()
    assert "na máquina" in (local / "app.log").read_text(encoding="utf-8")
    assert not (tmp_path / "rede" / "logs").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_log.py -v`
Expected: FAIL (`app.log` não existe em `local/logs`).

- [ ] **Step 3: Write the implementation**

Em `core/log.py`, trocar o docstring do módulo e a linha de `destino`:

```python
"""Log do app: <pasta de dados>/logs/app.log (rotativo, ~1 MB × 3 arquivos).

Se `MAPEADOR_LOGS` estiver definida, os logs vão para essa pasta. O atalho de rede
usa isso para guardar o log na máquina de cada usuário: a rotação não funciona
com vários processos escrevendo o mesmo arquivo numa pasta de rede.

Só biblioteca padrão e sem dependência de `armazenamento`: quem chama passa a
pasta (ver `armazenamento.pasta_dados`)."""
```
e, dentro de `configurar_log`:
```python
    destino = os.environ.get("MAPEADOR_LOGS") or os.path.join(pasta, "logs")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_log.py tests/test_processar.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/log.py tests/test_log.py
git commit -m "feat: MAPEADOR_LOGS leva o log para uma pasta local de cada usuario"
```

---

### Task 6: Encerrar a ferramenta e desligar quando ociosa

**Files:**
- Create: `core/ocioso.py`
- Modify: `app.py` (imports, vigia antes do portão de login, botão na barra lateral)
- Test: `tests/test_ocioso.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: nada de outras tarefas.
- Produces:
  - `ocioso.VigiaOciosidade(contar_sessoes, limite_s=600, carencia_s=180, relogio=time.monotonic)` com `deve_encerrar() -> bool`
  - `ocioso.contar_sessoes_streamlit() -> int | None` (None = não foi possível contar: o vigia nunca encerra)
  - em `app.py`: `_MODO_ATALHO`, `_vigiar_ociosidade()`, `_encerrar_servidor()`

- [ ] **Step 1: Write the failing tests**

Criar `tests/test_ocioso.py`:

```python
from core.ocioso import VigiaOciosidade


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _vigia(sessoes, relogio, **kw):
    return VigiaOciosidade(lambda: sessoes[0], relogio=relogio,
                           limite_s=600, carencia_s=180, **kw)


def test_nao_encerra_enquanto_houver_navegador():
    rel, sessoes = Relogio(), [1]
    v = _vigia(sessoes, rel)
    rel.t = 10_000
    assert v.deve_encerrar() is False


def test_encerra_depois_do_limite_sem_navegador():
    rel, sessoes = Relogio(), [1]
    v = _vigia(sessoes, rel)
    assert v.deve_encerrar() is False       # viu o navegador
    sessoes[0] = 0
    rel.t = 100
    assert v.deve_encerrar() is False       # começou a contar
    rel.t = 100 + 599
    assert v.deve_encerrar() is False
    rel.t = 100 + 600
    assert v.deve_encerrar() is True


def test_voltar_o_navegador_zera_a_contagem():
    rel, sessoes = Relogio(), [1]
    v = _vigia(sessoes, rel)
    v.deve_encerrar()
    sessoes[0] = 0
    rel.t = 500
    v.deve_encerrar()
    sessoes[0] = 1
    rel.t = 900
    v.deve_encerrar()
    sessoes[0] = 0
    rel.t = 1000
    assert v.deve_encerrar() is False
    rel.t = 1599
    assert v.deve_encerrar() is False
    rel.t = 1600
    assert v.deve_encerrar() is True


def test_carencia_inicial_quando_nunca_apareceu_navegador():
    rel, sessoes = Relogio(), [0]
    v = _vigia(sessoes, rel)
    rel.t = 179
    assert v.deve_encerrar() is False
    rel.t = 180
    assert v.deve_encerrar() is True


def test_sem_como_contar_nunca_encerra():
    rel = Relogio()
    v = VigiaOciosidade(lambda: None, relogio=rel)
    rel.t = 10**9
    assert v.deve_encerrar() is False
```

Acrescentar ao fim de `tests/test_app.py`:

```python
def test_sem_modo_atalho_nao_ha_botao_encerrar():
    at = _app("consulta").run(timeout=30)
    assert not at.exception
    assert not any(b.key == "encerrar" for b in at.button)


def test_botao_encerrar_agenda_o_desligamento(monkeypatch):
    monkeypatch.setenv("MAPEADOR_MODO_ATALHO", "1")
    agendados = []

    class TimerFalso:
        def __init__(self, intervalo, funcao, args=()):
            agendados.append((intervalo, funcao, args))

        def start(self):
            pass

    monkeypatch.setattr("threading.Timer", TimerFalso)
    monkeypatch.setattr("core.ocioso.contar_sessoes_streamlit", lambda: None)
    at = _app("consulta").run(timeout=30)
    assert not at.exception
    at.button(key="encerrar").click().run(timeout=30)
    assert not at.exception
    assert len(agendados) == 1
    assert any("Pode fechar esta aba" in s.value for s in at.success)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ocioso.py tests/test_app.py -k "ocioso or encerrar or vigia or navegador or carencia or contar" -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.ocioso'`; sem botão `encerrar`).

- [ ] **Step 3: Write the implementation**

Criar `core/ocioso.py`:

```python
# core/ocioso.py
"""Desligar o servidor local quando ninguém o está usando.

Cada usuário roda o próprio servidor pelo atalho; sem isto, fechar a aba do
navegador deixaria um processo esquecido na máquina. `VigiaOciosidade` é lógica
pura (relógio e contador injetados); só `contar_sessoes_streamlit` toca o
Streamlit, e de forma tolerante: se a API interna mudar, devolve None e o vigia
passa a nunca encerrar, em vez de derrubar o servidor por engano."""
import time


class VigiaOciosidade:
    def __init__(self, contar_sessoes, limite_s: float = 600,
                 carencia_s: float = 180, relogio=time.monotonic):
        self._contar = contar_sessoes
        self._limite = limite_s
        self._carencia = carencia_s
        self._relogio = relogio
        self._visto = False                 # algum navegador já se conectou?
        self._zero_desde = relogio()        # desde quando não há navegador

    def deve_encerrar(self) -> bool:
        sessoes = self._contar()
        if sessoes is None:
            return False
        agora = self._relogio()
        if sessoes > 0:
            self._visto = True
            self._zero_desde = None
            return False
        if self._zero_desde is None:
            self._zero_desde = agora
        espera = self._limite if self._visto else self._carencia
        return agora - self._zero_desde >= espera


def contar_sessoes_streamlit() -> int | None:
    """Quantos navegadores estão conectados agora, ou None se não der para saber."""
    try:
        from streamlit.runtime import get_instance
        return len(get_instance()._session_mgr.list_active_sessions())
    except Exception:  # noqa: BLE001 - API interna: qualquer falha desliga o vigia
        return None
```

Em `app.py`: acrescentar `import threading` e `import time` aos imports do topo, `ocioso` à lista `from core import (...)`, e logo depois de `log.configurar_log(armazenamento.pasta_dados())`:

```python
# Modo atalho: aberto por Mapeador.vbs (MAPEADOR_MODO_ATALHO=1). Liga o botão
# Encerrar e o desligamento por ociosidade; fora dele (streamlit run, testes) nada disso existe.
_MODO_ATALHO = os.environ.get("MAPEADOR_MODO_ATALHO") == "1"


def _encerrar_servidor():
    """Desliga o servidor um instante depois, para a página mostrar o aviso antes."""
    threading.Timer(1.0, os._exit, args=(0,)).start()


@st.cache_resource
def _vigiar_ociosidade():
    vigia = ocioso.VigiaOciosidade(ocioso.contar_sessoes_streamlit)

    def laco():
        while True:
            time.sleep(30)
            if vigia.deve_encerrar():
                logging.getLogger(log.NOME).info(
                    "Sem navegador conectado: encerrando o servidor.")
                os._exit(0)

    threading.Thread(target=laco, daemon=True).start()
    return True


if _MODO_ATALHO:
    _vigiar_ociosidade()
```

No bloco final da barra lateral (depois do botão "Trocar perfil", ainda dentro do `with st.sidebar:`), acrescentar:

```python
    if _MODO_ATALHO and st.button("Encerrar ferramenta", key="encerrar",
                                  icon=":material/power_settings_new:", width="stretch"):
        st.success("Ferramenta encerrada. Pode fechar esta aba.")
        _encerrar_servidor()
        st.stop()
```

Acrescentar também `import logging` aos imports do topo de `app.py` (usado pelo vigia).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ocioso.py tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/ocioso.py app.py tests/test_ocioso.py tests/test_app.py
git commit -m "feat: botao Encerrar e desligamento do servidor local por ociosidade"
```

---

### Task 7: Launcher sem janela, reaproveitando o servidor

**Files:**
- Modify: `iniciar.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_iniciar.py`

**Interfaces:**
- Consumes: `core.bootstrap` (inalterado).
- Produces em `iniciar.py`: `_pasta_local() -> str`, `_saudavel(porta: int) -> bool`, `_porta_em_execucao() -> int | None`, `_registrar_servidor(porta)`, `_esquecer_servidor()`, `_destino_da_saida() -> dict`, `_caixa_de_mensagem(texto)`, `_avisar_erro(texto)`.

- [ ] **Step 1: Write the failing tests**

Em `tests/conftest.py`, acrescentar dentro de `_dados_isolados`, junto do `setenv("MAPEADOR_DADOS", ...)`:

```python
    monkeypatch.setenv("MAPEADOR_LOCAL", str(tmp_path_factory.mktemp("local")))
```

Acrescentar ao fim de `tests/test_iniciar.py`:

```python
import json
import os


def test_segundo_clique_reabre_o_servidor_em_execucao(monkeypatch):
    abertos, chamadas = [], []
    monkeypatch.setattr(iniciar, '_porta_em_execucao', lambda: 8503)
    monkeypatch.setattr(iniciar.webbrowser, 'open', lambda url: abertos.append(url))
    monkeypatch.setattr(iniciar.subprocess, 'call', lambda *a, **k: chamadas.append(a) or 0)

    assert iniciar.main() == 0
    assert abertos == ["http://localhost:8503"]
    assert chamadas == []          # não subiu um segundo servidor


def test_porta_em_execucao_exige_marcador_e_servidor_saudavel(monkeypatch):
    assert iniciar._porta_em_execucao() is None          # sem marcador
    iniciar._registrar_servidor(8502)
    monkeypatch.setattr(iniciar, '_saudavel', lambda porta: False)
    assert iniciar._porta_em_execucao() is None          # marcador velho (servidor caiu)
    monkeypatch.setattr(iniciar, '_saudavel', lambda porta: porta == 8502)
    assert iniciar._porta_em_execucao() == 8502
    iniciar._esquecer_servidor()
    assert iniciar._porta_em_execucao() is None


def test_marcador_existe_durante_o_servidor_e_some_depois(monkeypatch):
    visto = {}

    def servidor_falso(*a, **k):
        with open(iniciar._arquivo_servidor(), encoding='utf-8') as f:
            visto['porta'] = json.load(f)['porta']
        return 0

    monkeypatch.setattr(iniciar, '_abrir_quando_subir', lambda *a, **k: None)
    monkeypatch.setattr(iniciar.subprocess, 'call', servidor_falso)
    assert iniciar.main() == 0
    assert isinstance(visto['porta'], int)
    assert not os.path.exists(iniciar._arquivo_servidor())


def test_sem_console_a_saida_do_servidor_vai_para_arquivo(monkeypatch):
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)
    destino = iniciar._destino_da_saida()
    assert destino['stdin'] == iniciar.subprocess.DEVNULL
    assert destino['stderr'] == iniciar.subprocess.STDOUT
    assert destino['stdout'].name.endswith(os.path.join('logs', 'servidor.log'))
    destino['stdout'].close()


def test_com_console_nao_redireciona_nada():
    assert iniciar._destino_da_saida() == {}


def test_erro_de_inicializacao_sem_console_vira_caixa_de_mensagem(monkeypatch):
    caixas = []
    monkeypatch.setattr(sys, 'stderr', None)
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(iniciar, '_caixa_de_mensagem', lambda t: caixas.append(t))
    iniciar._avisar_erro("falta o streamlit")
    assert caixas == ["falta o streamlit"]


def test_erro_de_inicializacao_com_console_vai_para_stderr(capsys):
    iniciar._avisar_erro("falta o streamlit")
    assert "falta o streamlit" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_iniciar.py -v`
Expected: FAIL (`AttributeError: module 'iniciar' has no attribute '_porta_em_execucao'` etc.).

- [ ] **Step 3: Write the implementation**

Em `iniciar.py`: acrescentar `import json`, `import traceback` e `import urllib.request` aos imports; mudar a docstring do módulo para acrescentar o parágrafo `Sem console (pythonw.exe, pelo Mapeador.vbs): a saída do servidor vai para um arquivo e erros de inicialização aparecem numa caixa de mensagem.`; e, depois de `_ESPERA_SERVIDOR`:

```python
_RAIZ = os.path.dirname(os.path.abspath(__file__))


def _pasta_local() -> str:
    """Pasta da máquina do usuário (marcador do servidor e log do servidor).
    No atalho de rede é `%LOCALAPPDATA%\\MapeadorPR` (MAPEADOR_LOCAL)."""
    pasta = (os.environ.get('MAPEADOR_LOCAL')
             or os.path.join(os.path.expanduser('~'), '.mapeador'))
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _arquivo_servidor() -> str:
    return os.path.join(_pasta_local(), 'servidor.json')


def _saudavel(porta: int) -> bool:
    try:
        with urllib.request.urlopen(
                f'http://127.0.0.1:{porta}/_stcore/health', timeout=1) as resposta:
            return resposta.read().strip() == b'ok'
    except Exception:  # noqa: BLE001 - qualquer falha = não há servidor ali
        return False


def _porta_em_execucao() -> int | None:
    """Porta do servidor desta ferramenta já em execução nesta máquina, ou None.
    O marcador evita confundir com outro app Streamlit que esteja na 8501."""
    try:
        with open(_arquivo_servidor(), encoding='utf-8') as arquivo:
            porta = int(json.load(arquivo)['porta'])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return porta if _saudavel(porta) else None


def _registrar_servidor(porta: int) -> None:
    with open(_arquivo_servidor(), 'w', encoding='utf-8') as arquivo:
        json.dump({'porta': porta}, arquivo)


def _esquecer_servidor() -> None:
    try:
        os.remove(_arquivo_servidor())
    except OSError:
        pass


def _destino_da_saida() -> dict:
    """Sem console (pythonw.exe) não há stdout/stderr e o subprocess falha com
    'handle inválido': manda a saída do servidor para um arquivo local."""
    if sys.stdout is not None and sys.stderr is not None:
        return {}
    pasta = os.path.join(_pasta_local(), 'logs')
    os.makedirs(pasta, exist_ok=True)
    arquivo = open(os.path.join(pasta, 'servidor.log'), 'a', encoding='utf-8')
    return {'stdin': subprocess.DEVNULL, 'stdout': arquivo,
            'stderr': subprocess.STDOUT}


def _caixa_de_mensagem(texto: str) -> None:
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, texto, 'Mapeador Tributário PR', 0x10)


def _avisar_erro(texto: str) -> None:
    """Sem console o erro some: no Windows vira caixa de mensagem."""
    if sys.stderr is None and sys.platform == 'win32':
        _caixa_de_mensagem(texto)
    else:
        print(f"\n{texto}", file=sys.stderr)
```

Substituir `main()` por:

```python
def main():
    # (comentário existente sobre tolera_encoding_do_console mantido)
    tolera_encoding_do_console()
    os.chdir(_RAIZ)        # .streamlit/config.toml e secrets.toml são lidos daqui

    em_execucao = _porta_em_execucao()
    if em_execucao:        # segundo clique no atalho: reabre em vez de subir outro
        webbrowser.open(f"http://localhost:{em_execucao}")
        return 0

    try:
        garantir_dependencias(DEPS_APP)
    except DependenciaAusente as erro:
        _avisar_erro(str(erro))
        return 1

    app = os.path.join(_RAIZ, 'app.py')
    porta = _porta_livre()
    url = f"http://localhost:{porta}"

    print(f"  Endereço: {url}")
    print("  Para encerrar: feche esta janela ou tecle Ctrl+C.\n", flush=True)

    threading.Thread(target=_abrir_quando_subir, args=(url, porta),
                     daemon=True).start()

    # (comentários existentes sobre -m, address e gatherUsageStats mantidos)
    _registrar_servidor(porta)
    try:
        return subprocess.call([sys.executable, '-m', 'streamlit', 'run', app,
                                '--server.port', str(porta),
                                '--server.address', '127.0.0.1',
                                '--server.headless', 'true',
                                '--browser.gatherUsageStats', 'false',
                                *sys.argv[1:]], **_destino_da_saida())
    finally:
        _esquecer_servidor()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - sem console, a falha precisa aparecer
        _avisar_erro(traceback.format_exc())
        sys.exit(1)
```

(`sys.exit` dentro do `try` levanta `SystemExit`, que não é `Exception` e passa direto.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_iniciar.py tests/test_bootstrap.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add iniciar.py tests/test_iniciar.py tests/conftest.py
git commit -m "feat: iniciar.py roda sem console, reabre o servidor em execucao e avisa erros"
```

---

### Task 8: Atalho, montagem da pasta de rede, documentação e versão

**Files:**
- Create: `scripts/Mapeador.vbs`
- Create: `scripts/montar_rede.ps1`
- Create: `tests/test_rede.py`
- Modify: `core/versao.py`, `README.md`, `CHANGELOG.md`

**Interfaces:**
- Consumes: variáveis `MAPEADOR_DADOS`, `MAPEADOR_LOGS`, `MAPEADOR_LOCAL`, `MAPEADOR_MODO_ATALHO`, `MAPEADOR_SEM_AUTOINSTALL` (esta última já existe em `core/bootstrap.py`); `iniciar.py` como ponto de entrada.
- Produces: `Mapeador.vbs` na raiz da pasta de rede (copiado por `montar_rede.ps1` a partir de `scripts/Mapeador.vbs`).

- [ ] **Step 1: Write the failing tests**

Criar `tests/test_rede.py`:

```python
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VBS = os.path.join(RAIZ, "scripts", "Mapeador.vbs")


def _vbs() -> str:
    with open(VBS, "rb") as arquivo:
        return arquivo.read().decode("ascii")      # falha se houver acento


def test_atalho_e_ascii_puro_e_roda_sem_janela():
    texto = _vbs()
    assert "pythonw.exe" in texto
    assert re.search(r"\.Run\b.*,\s*0\s*,\s*False", texto)    # estilo 0 = oculto


def test_atalho_define_o_ambiente_da_rede():
    texto = _vbs()
    for variavel in ("MAPEADOR_DADOS", "MAPEADOR_LOGS", "MAPEADOR_LOCAL",
                     "MAPEADOR_MODO_ATALHO", "MAPEADOR_SEM_AUTOINSTALL",
                     "PYTHONDONTWRITEBYTECODE"):
        assert variavel in texto


def test_script_de_montagem_existe_e_instala_do_requirements():
    caminho = os.path.join(RAIZ, "scripts", "montar_rede.ps1")
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert "requirements.txt" in texto
    assert "git" in texto and "archive" in texto
    assert "Mapeador.vbs" in texto


def test_script_de_montagem_recusa_atualizar_com_a_ferramenta_em_uso():
    caminho = os.path.join(RAIZ, "scripts", "montar_rede.ps1")
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert "Test-EmUso" in texto
    assert "$Forcar" in texto
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rede.py -v`
Expected: FAIL (`FileNotFoundError: ... Mapeador.vbs`).

- [ ] **Step 3: Write the files**

Criar `scripts/Mapeador.vbs` (ASCII puro, sem acentos):

```vbscript
' Mapeador Tributario PR - atalho de duplo clique, sem janela de console.
' Fica na raiz da pasta de rede:  Mapeador.vbs, app\ (codigo + python\), dados\
Option Explicit

Dim sh, fso, raiz, python, local, ambiente
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

raiz = fso.GetParentFolderName(WScript.ScriptFullName)
python = raiz & "\app\python\pythonw.exe"

If Not fso.FileExists(python) Then
    MsgBox "Python portatil nao encontrado em:" & vbCrLf & python & vbCrLf & vbCrLf & _
           "Peca a quem mantem a ferramenta para rodar scripts\montar_rede.ps1.", 16, _
           "Mapeador Tributario PR"
    WScript.Quit 1
End If

local = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\MapeadorPR"
Set ambiente = sh.Environment("Process")
ambiente("MAPEADOR_DADOS") = raiz & "\dados"           ' banco e backups: na rede
ambiente("MAPEADOR_LOCAL") = local                      ' marcador do servidor: nesta maquina
ambiente("MAPEADOR_LOGS") = local & "\logs"             ' logs: nesta maquina
ambiente("MAPEADOR_MODO_ATALHO") = "1"                  ' botao Encerrar + desliga se ociosa
ambiente("MAPEADOR_SEM_AUTOINSTALL") = "1"              ' nunca tenta instalar pelo pip
ambiente("PYTHONDONTWRITEBYTECODE") = "1"               ' varios usuarios, uma pasta: sem .pyc

' 0 = janela oculta; False = nao espera terminar
sh.Run """" & python & """ """ & raiz & "\app\iniciar.py""", 0, False
```

Criar `scripts/montar_rede.ps1`:

```powershell
<#
.SYNOPSIS
  Monta (ou atualiza) a pasta de rede do Mapeador.

.EXAMPLE
  .\scripts\montar_rede.ps1 -Destino \\servidor\arquivos\Mapeador

  Cria Destino\app (codigo + Python portatil com as dependencias), Destino\dados e
  Destino\Mapeador.vbs. Rodar de novo atualiza o codigo e as dependencias e
  preserva dados\, app\python\ e app\.streamlit\secrets.toml.
  Requer internet na maquina de quem monta (Python, pip e dependencias).
  Recusa atualizar se a ferramenta estiver em uso em qualquer maquina (o Windows trava
  python.exe/pythonw.exe enquanto alguem os usa): peca para todos clicarem em
  "Encerrar ferramenta". -Forcar ignora a checagem.
#>
param(
    [Parameter(Mandatory = $true)][string]$Destino,
    [string]$VersaoPython = "3.14.6",
    [switch]$Forcar          # atualiza mesmo com a ferramenta em uso (nao recomendado)
)
$ErrorActionPreference = "Stop"

$raizRepo = Split-Path -Parent $PSScriptRoot
$app = Join-Path $Destino "app"
$py = Join-Path $app "python"
$tmp = Join-Path $env:TEMP "mapeador_montagem"
New-Item -ItemType Directory -Force $app, (Join-Path $Destino "dados"), $tmp | Out-Null

# 0. Ferramenta em uso? Abrir o executavel para escrita falha se QUALQUER maquina o
#    estiver rodando a partir da rede.
function Test-EmUso($arquivo) {
    try {
        $f = [IO.File]::Open($arquivo, 'Open', 'ReadWrite', 'None')
        $f.Close()
        return $false
    } catch [IO.IOException] {
        return $true
    }
}
if (-not $Forcar) {
    foreach ($exe in "python.exe", "pythonw.exe") {
        $caminho = Join-Path $py $exe
        if ((Test-Path $caminho) -and (Test-EmUso $caminho)) {
            throw "A ferramenta esta em uso. Peca a todos para clicarem em 'Encerrar ferramenta' e rode de novo."
        }
    }
}

# 1. Codigo versionado (HEAD): sem .git, sem banco, sem cache.
if (git -C $raizRepo status --porcelain) {
    Write-Warning "Ha alteracoes nao commitadas: so o que esta em HEAD vai para a rede."
}
$zipCodigo = Join-Path $tmp "codigo.zip"
git -C $raizRepo archive --format=zip -o $zipCodigo HEAD
Expand-Archive $zipCodigo -DestinationPath $app -Force

# 2. Python portatil (embeddable), so na primeira vez.
if (-not (Test-Path (Join-Path $py "python.exe"))) {
    $zipPython = Join-Path $tmp "python-embed.zip"
    Invoke-WebRequest "https://www.python.org/ftp/python/$VersaoPython/python-$VersaoPython-embed-amd64.zip" -OutFile $zipPython
    Expand-Archive $zipPython -DestinationPath $py -Force

    # O ._pth restringe o sys.path: inclui a pasta do codigo (..), o site-packages e o site.
    $pth = Get-ChildItem $py -Filter "python*._pth" | Select-Object -First 1
    Set-Content $pth.FullName -Encoding ascii -Value @(
        "$($pth.BaseName).zip", ".", "..", "Lib\site-packages", "import site")

    $getPip = Join-Path $tmp "get-pip.py"
    Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip
    & (Join-Path $py "python.exe") $getPip --no-warn-script-location
}

# 3. Dependencias, sempre pelo requirements.txt (fonte unica das versoes).
& (Join-Path $py "python.exe") -m pip install -r (Join-Path $app "requirements.txt") --no-warn-script-location

# 4. Atalho na raiz da pasta de rede.
Copy-Item (Join-Path $raizRepo "scripts\Mapeador.vbs") (Join-Path $Destino "Mapeador.vbs") -Force

# 5. Teste de fumaca: as bibliotecas importam no Python portatil.
& (Join-Path $py "python.exe") -c "import streamlit, pdfplumber, openpyxl; print('Python portatil OK')"
Write-Host "Pronto: $Destino. Peca aos usuarios para criarem um atalho para Mapeador.vbs na area de trabalho."
```

Em `core/versao.py`: `VERSAO_APP = "0.10.0"`.

Em `CHANGELOG.md`, acrescentar no topo (antes de `## 0.9.1`):

```markdown
## 0.10.0
- **Compartilhamento pela rede**: código, Python portátil e banco ficam numa pasta de rede; cada pessoa abre por `Mapeador.vbs` (sem janela de console, sem instalar nada) e vê o mesmo banco. `scripts/montar_rede.ps1` monta e atualiza a pasta.
- O perfil **Consulta** abre o banco **somente leitura** (nunca cria nem migra o arquivo); se o banco não existe ou é de versão antiga, a tela pede ao Administrador abrir a ferramenta.
- **Gravar** passa a usar uma **trava de importação** (`importando.lock`, vence em 15 min): quem tenta gravar enquanto outra pessoa grava vê o nome e o horário. Antes de cada gravação é feito um **backup** em `backups/` (10 mais recentes). Conexões esperam até 30 s por bloqueio.
- Botão **Encerrar ferramenta** e desligamento automático do servidor local após 10 min sem navegador (só no atalho).
- Gravar (importação ou edição manual) **espera até 60 s** a vez quando outra pessoa está gravando (`MAPEADOR_ESPERA_TRAVA_S`). `montar_rede.ps1` recusa atualizar com a ferramenta em uso.
- Um segundo clique no atalho reabre o servidor já aberto; falhas de inicialização sem console aparecem numa caixa de mensagem. O log do atalho fica na máquina de cada usuário (`MAPEADOR_LOGS`).
- Schema do banco inalterado (4).
```

No `README.md`: trocar `Versão atual: **0.9.0**` por `**0.10.0**`; no sumário da seção 10 e no corpo, substituir o texto da seção `## 10. Distribuição` por:

```markdown
## 10. Distribuição
### Pela rede (recomendado)
Uma pasta de rede acessível a todos guarda tudo; cada pessoa roda o servidor na
própria máquina (`127.0.0.1`) e lê/grava o mesmo banco.

```
\\rede\Mapeador\
  Mapeador.vbs      duplo clique, sem janela de console
  app\              código + python\ (Python portátil com as dependências)
  dados\            mapeamento.db e backups\
```

**Montar ou atualizar** (por quem mantém a ferramenta, com internet, na raiz do repositório):

```powershell
.\scripts\montar_rede.ps1 -Destino \\servidor\pasta\Mapeador
```

Cada usuário cria um atalho para `Mapeador.vbs` na área de trabalho. A janela do
navegador abre sozinha; **Encerrar ferramenta** (barra lateral) ou 10 minutos sem
navegador desligam o servidor local. Um segundo clique no atalho reabre o que já está aberto.

- **Quem grava:** só o Administrador. Uma **trava de importação** (`dados\importando.lock`)
  impede duas gravações ao mesmo tempo e mostra quem está gravando; ela vence em 15 min
  se a máquina cair. Antes de cada gravação é feito um **backup** (`dados\backups\`, 10 mais recentes).
  Para restaurar, feche a ferramenta em todas as máquinas e substitua `mapeamento.db` por uma cópia.
- **Perfil Consulta:** abre o banco somente leitura. Se o banco ainda não existe ou foi
  atualizado por uma versão nova, a tela pede ao Administrador abrir a ferramenta primeiro.
- **Senha do Administrador:** não deixe `secrets.toml` em `app\.streamlit\` (todos leriam).
  Crie `%USERPROFILE%\.streamlit\secrets.toml` no computador do Administrador, com a seção
  `[admin]` e a chave `senha`; o Streamlit lê esse arquivo também.
- **Atualizar a ferramenta:** peça a todos para clicarem em **Encerrar ferramenta** e rode o script;
  ele recusa atualizar se detectar a ferramenta em uso (o Windows trava o Python portátil
  enquanto alguém o usa). `-Forcar` ignora a checagem.
- **Logs:** ficam em `%LOCALAPPDATA%\MapeadorPR\logs` de cada usuário.
- **Duas pessoas importando ao mesmo tempo não é suportado**: a trava só impede, não enfileira.

### Por arquivo zip (uma cópia por máquina)
Entrega só os arquivos versionados, sem a pasta `.git` nem caches:

```bash
git archive --format=zip -o mapeador_pr.zip HEAD
```

Na máquina de destino, `Mapeador.bat` cria o `.venv` na primeira execução (precisa
de internet nessa vez). O `.streamlit/secrets.toml` e o `mapeamento.db` precisam
ser criados/copiados à parte (não são versionados).
```

Na tabela da seção 7 do README, acrescentar as linhas (antes de `| `app.py` |`):

```markdown
| `core/trava.py` | trava de importação em arquivo (quem grava, desde quando, validade de 15 min) |
| `core/backup.py` | backup consistente do banco antes de cada gravação |
| `core/ocioso.py` | desligamento do servidor local sem navegador conectado |
```
e, junto de `Mapeador.bat`, as linhas:
```markdown
| `scripts/Mapeador.vbs` | atalho de rede, sem janela de console |
| `scripts/montar_rede.ps1` | monta e atualiza a pasta de rede (Python portátil + dependências) |
```

Em `README.md` seção 12, trocar o texto por: `O único item planejado é a **criação de um executável em binário** da ferramenta, se a distribuição pela rede deixar de bastar.`

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (suíte inteira, incluindo `tests/test_versao.py` e `tests/test_rede.py`).

- [ ] **Step 5: Verificação manual em duas máquinas** (não automatizável; registrar o resultado no commit ou na PR)

1. `.\scripts\montar_rede.ps1 -Destino <pasta de rede de teste>` termina com `Python portatil OK`.
2. Na máquina A, duplo clique em `Mapeador.vbs`: não aparece janela preta; o navegador abre; entrar como Administrador (senha em `%USERPROFILE%\.streamlit\secrets.toml`); importar um PDF; `dados\backups\` ganha um `.db` e `dados\importando.lock` some depois.
3. Na máquina B, abrir como Consulta: vê o que A gravou depois de recarregar a página.
4. Na máquina A, clicar de novo em `Mapeador.vbs`: abre outra aba no servidor existente e `Get-Process pythonw` não mostra um segundo `streamlit`.
5. Criar `dados\importando.lock` à mão (JSON com `renovado_em` de agora) e tentar Gravar: aviso com o nome e, após ~60 s, mensagem de que a vez não veio; apagar o arquivo durante a espera deixa a gravação seguir. Repetir editando um ato pelo detalhe.
5b. Com a ferramenta aberta numa máquina, rodar `montar_rede.ps1` em outra: deve recusar com "A ferramenta esta em uso"; depois de **Encerrar ferramenta**, deve atualizar.
6. Renomear `dados\mapeamento.db` temporariamente e abrir como Consulta: mensagem "ainda não existe", e nenhum `mapeamento.db` vazio é criado.
7. **Encerrar ferramenta**: a aba mostra "Pode fechar esta aba" e o `pythonw` some.

- [ ] **Step 6: Commit**

```bash
git add scripts/Mapeador.vbs scripts/montar_rede.ps1 tests/test_rede.py core/versao.py README.md CHANGELOG.md
git commit -m "feat: atalho de rede, script de montagem e documentacao; versao 0.10.0"
```
