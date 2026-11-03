# Consulta do CNPJ na BrasilAPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ao gravar um lote, consultar na BrasilAPI o CNPJ de cada regime (CNAE principal e situação cadastral), guardar o resultado à parte, mostrá-lo no detalhe do regime com aviso de divergência e deixar o administrador atualizar a consulta e aplicar o CNAE da Receita ao regime.

**Architecture:** Um módulo novo `core/cnpj.py` (sem Streamlit; único ponto que toca a rede, via `urllib`) consulta, reaproveita consultas recentes e tolera falha de rede. O banco ganha o schema 4 (`cnpj_receita`). `Execucao.gravar` (CLI) e `_gravar` (interface) chamam `cnpj.atualizar_do_lote` DEPOIS de `persistir_lote`. O detalhe do regime mostra o bloco da Receita; "Aplicar CNAE" reaproveita `edicao.editar_registro` (vira ajuste manual).

**Tech Stack:** Python 3.10+, SQLite, `urllib` da biblioteca padrão, Streamlit 1.63, pytest. Nenhuma dependência nova.

**Spec:** `docs/superpowers/specs/2026-11-03-consulta-cnpj-brasilapi-design.md`

## Global Constraints

- Nenhuma dependência de terceiros nova; nenhum pino de `requirements.txt` muda (usar só `urllib`).
- Comando de testes: `python -m pytest -q` (o `pytest` puro não está no PATH). Linha de base ao escrever este plano: **363 testes** passando; ao fim do plano: **416**.
- **Nenhum teste usa a rede.** `tests/conftest.py` fixa `MAPEADOR_CONSULTA_CNPJ=0`; todo teste que consulta liga a variável de propósito e injeta um `abrir` falso (`tests.test_cnpj.Rede`) — em `Execucao` por `abrir_cnpj=`, na CLI e no app por `monkeypatch.setattr('core.cnpj._abrir', ...)`.
- **Contratos que não podem mudar:** `salvar_consultas`/`salvar_regimes` → `{'novos': N, 'atualizados': M}`; `persistir_lote` → `{'consultas': {...}, 'regimes': {...}}` (a consulta de CNPJ roda DEPOIS, fora dele); cada linha de `lote.arquivos` tem as 6 chaves de sempre; os dicts dos parsers não ganham chaves; `st.session_state["resultado"]` mantém as 6 chaves (`arquivos`, `consultas`, `regimes`, `descartes`, `mapeamento`, `xlsx`); `armazenamento._CAMINHO_PADRAO`; CLI: `Uso:` em stdout com código 1 e códigos de saída 0/1/2.
- **Falha de rede NUNCA impede nem desfaz a gravação.** `cnpj.atualizar` não levanta por internet fora do ar, timeout, HTTP 4xx/5xx ou resposta ilegível; devolve o resumo. Duas falhas de conexão seguidas interrompem o resto do lote.
- **O CNAE da Receita não sobrescreve o regime sozinho** (é o CNAE ATUAL da empresa). Fica na tabela `cnpj_receita`; só o botão do administrador o grava no regime, como ajuste manual.
- **Só o administrador** consulta/atualiza/aplica pelo detalhe (os callbacks chamam `acesso.exige_admin`). O perfil Consulta vê os dados da Receita, nunca os botões.
- Só o CNPJ (dado público) sai da máquina; `User-Agent` genérico `mapeador-pr` (sem e-mail ou dado pessoal). CNPJ em branco ou com dígitos verificadores errados nunca vai para a rede.
- Textos da interface e mensagens em português, com acentuação correta; toda cor/estilo segue o Design System já aplicado (nada de cor fixa nova).
- **Commits: em português, no formato `tipo: descrição`, SEM linha `Co-Authored-By` e sem rodapé de geração** (o commit sai só em nome do usuário; é preferência explícita dele). Um commit por tarefa, na branch `consulta-cnpj-brasilapi`. **Não fazer push nem merge.**
- O Streamlit **não permite alterar `st.session_state[<chave de um widget>]` depois que o widget foi desenhado** na mesma execução: por isso os botões do detalhe rodam no `on_click`. Não troque isso por `if st.button(...)`.

## Review Focus

Condições que a spec implica mas que nenhuma tarefa exercitaria por acaso; cada uma tem seu teste na tarefa dona do código:

1. **Sem internet / API fora do ar / limite de uso / HTML de manutenção no lugar do JSON** — a gravação conclui e o aviso diz que a consulta falhou; nada quebra. → Tarefa 2 (`test_erros_de_rede_viram_as_excecoes_do_modulo`, `test_resposta_ilegivel_...`), Tarefa 3 (`test_falha_de_rede_nao_impede_a_gravacao`, `test_cli_sem_internet_grava_e_avisa`), Tarefa 4 (`test_gravar_sem_internet_grava_e_avisa`).
2. **Lote grande sem internet** — duas falhas de conexão seguidas interrompem o resto (nada de esperar 5 s × N consultas); os demais ficam `pendentes`. → Tarefa 2 (`test_duas_falhas_de_conexao_seguidas_interrompem_o_resto_do_lote`).
3. **CNPJ em branco, repetido ou inválido** — não vai para a rede; repetido no lote é consultado uma vez. → Tarefa 2.
4. **Reimportar o mesmo PDF** — consulta com menos de 30 dias é reaproveitada (nenhuma chamada nova); com mais de 30 dias, refeita. → Tarefa 2.
5. **CNAE da Receita vs. CNAE do regime** — CNAE em branco no regime não é divergência; CNAE diferente avisa; só "Aplicar" grava (como ajuste manual); o perfil Consulta nunca vê os botões. → Tarefa 2 (`test_divergencia_...`) e Tarefa 4.

## Verificação do plano

O código e os testes deste plano foram validados antes de serem escritos aqui: as operações de cada tarefa foram aplicadas, **literalmente e em ordem**, a uma cópia limpa do projeto, e a suíte inteira foi rodada **após cada tarefa**. Resultado (testes passando): T1 **368** · T2 **398** · T3 **406** · T4 **416** · T5 **416**. Se uma contagem diferir ao executar, algo foi aplicado fora de ordem ou com texto diferente do plano. A consulta real à BrasilAPI foi conferida à mão uma vez (HTTP 200 com `cnae_fiscal`, `cnae_fiscal_descricao` e `descricao_situacao_cadastral`; HTTP 400 para CNPJ inválido).

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `core/cnpj.py` | criar | cliente da BrasilAPI, reaproveitamento, tolerância a falha, mensagem e divergência |
| `core/armazenamento.py` | modificar | schema 4; `salvar_cnpj_receita`, `cnpj_receita_de` |
| `core/execucao.py` | modificar | `consultar_cnpj`, `abrir_cnpj`, `resumo_cnpj`; consulta depois de gravar |
| `core/consulta.py` | modificar | `receita(conn, registro)` |
| `processar.py` | modificar | `--sem-consulta-cnpj` e a linha `Receita:` |
| `app.py` | modificar | consulta ao gravar; bloco da Receita no detalhe; atualizar e aplicar CNAE |
| `tests/conftest.py` | modificar | fixa `MAPEADOR_CONSULTA_CNPJ=0` |
| `tests/test_receita_banco.py`, `tests/test_cnpj.py` | criar | testes novos |
| `tests/test_ajustes.py`, `test_execucao.py`, `test_processar.py`, `test_consulta.py`, `test_app.py` | modificar | testes novos / ajuste do número do schema |
| `README.md`, `CHANGELOG.md`, `core/versao.py` | modificar | documentação e versão 0.9.0 |

Dependências entre tarefas: 1 → 2 → 3; 4 depende de 1 e 2 (e das funções de edição já existentes); 5 por último.

## Fora deste plano

- CNAEs **secundários**, razão social na tela (a razão social é guardada, mas não exibida) e histórico das consultas à Receita.
- Preencher `CNAE REQUERENTE`/`DESCRIÇÃO CNAE` do regime automaticamente — o parser os deixa em branco hoje; o administrador decide aplicar.
- Consulta para **consultas** (elas não têm CNPJ) e inclusão do CNAE da Receita na planilha `.xlsx`.
- **CNPJ alfanumérico** (formato novo da Receita): o parser de regimes (`parsers/regimes.py`, só dígitos) e `diagnostico.cnpj_valido` não o reconhecem hoje; ele seria ignorado pela consulta. Não verificado se a BrasilAPI já o aceita — tratar em outro plano, junto com o parser.
- Proxy corporativo, fila/repetição automática de consultas pendentes e limite configurável de uso da API.

---

### Task 0: Preparação

- [ ] **Step 1: Criar a branch e conferir a linha de base**

```bash
git switch -c consulta-cnpj-brasilapi
python -m pytest -q
```

Expected: branch criada a partir de `main` e **363 testes passando**. Se algo falhar já aqui, **pare** e avise: o plano assume base verde.

---

### Task 1: Schema 4: tabela `cnpj_receita` e armazenamento da consulta

**Files:**
- Modificar: `core/armazenamento.py`
- Modificar: `tests/conftest.py`
- Modificar: `tests/test_ajustes.py`
- Criar: `tests/test_receita_banco.py`

**Interfaces:**
- Consumes: nada de tarefas anteriores (só o código atual).
- Produces: `armazenamento.SCHEMA_VERSAO == 4`; tabela `cnpj_receita(cnpj PK só dígitos, razao_social, cnae_codigo, cnae_descricao, situacao, consultado_em)`; `salvar_cnpj_receita(conn, dados: dict, consultado_em: str | None = None) -> None` (substitui a consulta anterior do mesmo CNPJ); `cnpj_receita_de(conn, cnpj) -> dict | None` (aceita CNPJ com ou sem pontuação; devolve as 6 colunas); a variável de ambiente `MAPEADOR_CONSULTA_CNPJ=0` fica fixada em todos os testes (nenhum teste usa a rede).

> O `conftest.py` passa a definir `MAPEADOR_CONSULTA_CNPJ=0` para **todo** teste. Isso garante, desde já, que nenhum teste (nem os de tarefas futuras que esqueçam o `abrir` falso) fale com a internet. Os testes que precisam da consulta ligam a variável de propósito.

- [ ] **Step 1: Escrever os testes (que ainda falham)**

**Em `tests/conftest.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    monkeypatch.setenv("MAPEADOR_DADOS", str(pasta))
```

por:

```python
    monkeypatch.setenv("MAPEADOR_DADOS", str(pasta))
    # nenhum teste usa a rede: a consulta de CNPJ fica desligada, salvo nos testes
    # que a ligam de propósito (sempre com um `abrir` falso)
    monkeypatch.setenv("MAPEADOR_CONSULTA_CNPJ", "0")
```

**Em `tests/test_ajustes.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    assert armazenamento.SCHEMA_VERSAO == 3
```

por:

```python
    assert armazenamento.SCHEMA_VERSAO >= 3
```

**Em `tests/test_ajustes.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    assert armazenamento.versao_do_schema(conn) == 3
```

por:

```python
    assert armazenamento.versao_do_schema(conn) == armazenamento.SCHEMA_VERSAO
```

**Criar `tests/test_receita_banco.py`** com exatamente este conteúdo:

```python
# tests/test_receita_banco.py
"""Tabela cnpj_receita (schema 4): dados da Receita Federal guardados à parte do regime."""
from core import armazenamento

BB = '00.000.000/0001-91'
DADOS = {'cnpj': '00000000000191', 'razao_social': 'BANCO DO BRASIL SA',
         'cnae_codigo': '6422100', 'cnae_descricao': 'Bancos múltiplos, com carteira comercial',
         'situacao': 'ATIVA'}


def _conn(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / 'r.db'))
    armazenamento.criar_esquema(conn)
    return conn


def test_esquema_4_cria_a_tabela_da_receita_vazia(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.SCHEMA_VERSAO >= 4
    assert conn.execute('SELECT COUNT(*) FROM cnpj_receita').fetchone()[0] == 0
    assert armazenamento.cnpj_receita_de(conn, BB) is None


def test_banco_do_schema_3_ganha_a_tabela_sem_perder_os_atos(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [{'ANO': '2026', 'Nº DO REGIME ESPECIAL': '1/2026',
                                         'CNPJ REQUERENTE': '11.222.333/0001-81'}])
    conn.execute('DROP TABLE cnpj_receita')
    conn.execute('PRAGMA user_version = 3')
    armazenamento.criar_esquema(conn)
    assert armazenamento.versao_do_schema(conn) == armazenamento.SCHEMA_VERSAO
    assert conn.execute('SELECT COUNT(*) FROM cnpj_receita').fetchone()[0] == 0
    assert len(armazenamento.buscar_regimes(conn)) == 1


def test_salvar_e_ler_a_receita_aceita_cnpj_com_pontuacao(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_cnpj_receita(conn, DADOS, consultado_em='2026-11-03T12:00:00+00:00')
    lido = armazenamento.cnpj_receita_de(conn, BB)
    assert lido == {**DADOS, 'consultado_em': '2026-11-03T12:00:00+00:00'}
    assert armazenamento.cnpj_receita_de(conn, '00000000000191') == lido


def test_salvar_de_novo_substitui_a_consulta_anterior(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_cnpj_receita(conn, DADOS, consultado_em='2026-11-03T12:00:00+00:00')
    armazenamento.salvar_cnpj_receita(conn, {**DADOS, 'situacao': 'BAIXADA'},
                                      consultado_em='2026-12-03T12:00:00+00:00')
    assert armazenamento.cnpj_receita_de(conn, BB)['situacao'] == 'BAIXADA'
    assert conn.execute('SELECT COUNT(*) FROM cnpj_receita').fetchone()[0] == 1


def test_consultar_sem_cnpj_devolve_none(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.cnpj_receita_de(conn, '') is None
    assert armazenamento.cnpj_receita_de(conn, None) is None
```

- [ ] **Step 2: Rodar e ver FALHAR**

Run: `python -m pytest tests/test_receita_banco.py -q` — Expected: FAIL: os testes novos falham (`cnpj_receita` não existe / `SCHEMA_VERSAO` ainda é 3).

- [ ] **Step 3: Implementar**

**Em `core/armazenamento.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
SCHEMA_VERSAO = 3
```

por:

```python
SCHEMA_VERSAO = 4
```

**Em `core/armazenamento.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
def _agora() -> str:
```

por:

```python
# o que a Receita Federal (BrasilAPI) disse de cada CNPJ; à parte do regime (ver core/cnpj.py)
_DDL_CNPJ_RECEITA = """
CREATE TABLE IF NOT EXISTS cnpj_receita (
    cnpj TEXT PRIMARY KEY,
    razao_social TEXT NOT NULL DEFAULT '',
    cnae_codigo TEXT NOT NULL DEFAULT '',
    cnae_descricao TEXT NOT NULL DEFAULT '',
    situacao TEXT NOT NULL DEFAULT '',
    consultado_em TEXT NOT NULL
)"""


def _agora() -> str:
```

**Em `core/armazenamento.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    conn.execute(_DDL_SUBSTITUICOES)
```

por:

```python
    conn.execute(_DDL_SUBSTITUICOES)
    conn.execute(_DDL_CNPJ_RECEITA)
```

**Acrescentar ao FIM de `core/armazenamento.py`** (depois de uma linha em branco) exatamente:

```python
def salvar_cnpj_receita(conn: sqlite3.Connection, dados: dict,
                        consultado_em: str | None = None) -> None:
    """Grava (ou substitui) a consulta de um CNPJ na Receita Federal.
    `dados` vem de cnpj.consultar: {'cnpj' (só dígitos), 'razao_social',
    'cnae_codigo', 'cnae_descricao', 'situacao'}."""
    conn.execute(
        'INSERT OR REPLACE INTO cnpj_receita '
        '(cnpj, razao_social, cnae_codigo, cnae_descricao, situacao, consultado_em) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        (dados['cnpj'], dados.get('razao_social', ''), dados.get('cnae_codigo', ''),
         dados.get('cnae_descricao', ''), dados.get('situacao', ''),
         consultado_em or _agora()))
    conn.commit()


def cnpj_receita_de(conn: sqlite3.Connection, cnpj) -> dict | None:
    """Última consulta guardada do CNPJ (com ou sem pontuação), ou None."""
    digitos = ''.join(c for c in str(cnpj or '') if c.isdigit())
    linha = conn.execute('SELECT * FROM cnpj_receita WHERE cnpj = ?', (digitos,)).fetchone()
    return dict(linha) if linha else None
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_receita_banco.py -q` — Expected: PASS.

Depois a suíte inteira: `python -m pytest -q` — Expected: **368 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/armazenamento.py tests/conftest.py tests/test_ajustes.py tests/test_receita_banco.py
git commit -m "feat: schema 4 com a tabela da consulta de CNPJ na Receita"
```

(sem `Co-Authored-By`).

---

### Task 2: `core/cnpj.py`: cliente da BrasilAPI, reaproveitamento e tolerância a falha

**Files:**
- Criar: `core/cnpj.py`
- Criar: `tests/test_cnpj.py`

**Interfaces:**
- Consumes: Tarefa 1: `armazenamento.cnpj_receita_de`, `armazenamento.salvar_cnpj_receita`; `core.diagnostico.cnpj_valido(cnpj) -> bool` (já existe).
- Produces: `cnpj.consultar(cnpj, abrir=None) -> dict` (`{'cnpj','razao_social','cnae_codigo' (7 dígitos),'cnae_descricao','situacao'}`; levanta `CnpjInvalido`, `CnpjNaoEncontrado`, `ConsultaIndisponivel`); `cnpj.atualizar(conn, cnpjs, abrir=None, agora=None, dormir=time.sleep, forcar=False) -> dict` (`{'consultados','do_cache','ignorados','falhas': [(cnpj, motivo)],'interrompido','pendentes'}`; nunca levanta por falha de rede); `cnpj.atualizar_do_lote(conn, lote, **opcoes) -> dict`; `cnpj.mensagem_do_resumo(resumo) -> str | None`; `cnpj.divergencia(regime, receita) -> dict | None`; `cnpj.formatar_cnae('6422100') -> '6422-1/00'`; `cnpj.so_digitos`; `cnpj.habilitada() -> bool`; `cnpj._abrir(url, timeout)` (o único ponto que toca a rede); constantes `URL`, `TIMEOUT=5`, `CACHE_DIAS=30`, `PAUSA=0.3`, `MAX_FALHAS_SEGUIDAS=2`; a classe de teste `tests.test_cnpj.Rede` (`abrir` falso que anota as URLs) que as Tarefas 3 e 4 reutilizam.

> `core/cnpj.py` é o **único** módulo que fala com a rede, e só por `_abrir`. Todos os testes passam um `abrir` falso; nenhuma tarefa deste plano deve chamar `urllib` em teste. O `User-Agent` é genérico (`mapeador-pr`): não coloque e-mail nem dado pessoal.

- [ ] **Step 1: Escrever os testes (que ainda falham)**

**Criar `tests/test_cnpj.py`** com exatamente este conteúdo:

```python
# tests/test_cnpj.py
"""Consulta do CNPJ na BrasilAPI. NENHUM teste aqui usa a rede: a abertura da URL é
sempre um `abrir` falso."""
import io
import json
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from core import armazenamento, cnpj
from core.pipeline import Lote

BB = '00.000.000/0001-91'
ALFA = '11.222.333/0001-81'
CNPJS_VALIDOS = ['00000000000191', '11222333000181', '33000167000101', '60746948000112']
AGORA = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def _resposta(cnae=6422100, situacao='ATIVA', razao='BANCO DO BRASIL SA'):
    return json.dumps({
        'cnpj': '00000000000191', 'razao_social': razao, 'cnae_fiscal': cnae,
        'cnae_fiscal_descricao': 'Bancos múltiplos, com carteira comercial',
        'descricao_situacao_cadastral': situacao,
        'cnaes_secundarios': [{'codigo': 6499999, 'descricao': 'Outras'}],
    }).encode('utf-8')


class Rede:
    """`abrir` falso: devolve uma resposta pronta (ou levanta o erro dado) e anota as URLs."""
    def __init__(self, resposta=None, erro=None):
        self.resposta = _resposta() if resposta is None else resposta
        self.erro, self.urls = erro, []

    def __call__(self, url, *args, **kw):
        self.urls.append(url)
        if self.erro is not None:
            raise self.erro
        return self.resposta


def _http(codigo):
    return urllib.error.HTTPError('u', codigo, 'x', {}, io.BytesIO(b''))


def _conn(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / 'c.db'))
    armazenamento.criar_esquema(conn)
    return conn


# --- consultar --------------------------------------------------------------
def test_consultar_devolve_cnae_e_situacao_e_pede_so_os_digitos():
    rede = Rede()
    dados = cnpj.consultar(BB, rede)
    assert rede.urls == ['https://brasilapi.com.br/api/cnpj/v1/00000000000191']
    assert dados == {'cnpj': '00000000000191', 'razao_social': 'BANCO DO BRASIL SA',
                     'cnae_codigo': '6422100',
                     'cnae_descricao': 'Bancos múltiplos, com carteira comercial',
                     'situacao': 'ATIVA'}


def test_cnae_com_zero_a_esquerda_volta_com_sete_digitos():
    assert cnpj.consultar(BB, Rede(_resposta(cnae=111301)))['cnae_codigo'] == '0111301'


def test_cnpj_invalido_nem_chama_a_rede():
    rede = Rede()
    with pytest.raises(cnpj.CnpjInvalido):
        cnpj.consultar('11.111.111/1111-11', rede)
    with pytest.raises(cnpj.CnpjInvalido):
        cnpj.consultar('', rede)
    assert rede.urls == []


@pytest.mark.parametrize('erro,esperado', [
    (_http(404), cnpj.CnpjNaoEncontrado),
    (_http(400), cnpj.CnpjInvalido),
    (_http(429), cnpj.ConsultaIndisponivel),
    (_http(503), cnpj.ConsultaIndisponivel),
    (urllib.error.URLError('sem rede'), cnpj.ConsultaIndisponivel),
    (TimeoutError('demorou'), cnpj.ConsultaIndisponivel),
    (ConnectionResetError('caiu'), cnpj.ConsultaIndisponivel),
])
def test_erros_de_rede_viram_as_excecoes_do_modulo(erro, esperado):
    with pytest.raises(esperado):
        cnpj.consultar(BB, Rede(erro=erro))


@pytest.mark.parametrize('corpo', [b'<html>manutencao</html>', b'[1, 2]', b''])
def test_resposta_ilegivel_e_consulta_indisponivel(corpo):
    with pytest.raises(cnpj.ConsultaIndisponivel):
        cnpj.consultar(BB, Rede(corpo))


def test_formatar_cnae():
    assert cnpj.formatar_cnae('6422100') == '6422-1/00'
    assert cnpj.formatar_cnae('4930-2/02') == '4930-2/02'
    assert cnpj.formatar_cnae('') == ''
    assert cnpj.formatar_cnae('123') == '123'


@pytest.mark.parametrize('valor,esperado', [
    (None, True), ('1', True), ('0', False), ('não', False), ('OFF', False), ('false', False)])
def test_habilitada_le_a_variavel_de_ambiente(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv('MAPEADOR_CONSULTA_CNPJ', raising=False)
    else:
        monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', valor)
    assert cnpj.habilitada() is esperado


# --- atualizar ---------------------------------------------------------------
def test_atualizar_consulta_grava_e_reaproveita_a_consulta_recente(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    r1 = cnpj.atualizar(conn, [BB, '00000000000191'], abrir=rede, agora=AGORA,
                        dormir=lambda s: None)
    assert (r1['consultados'], r1['do_cache']) == (1, 0)       # repetido na lista: uma vez
    assert armazenamento.cnpj_receita_de(conn, BB)['cnae_codigo'] == '6422100'
    r2 = cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA + timedelta(days=29),
                        dormir=lambda s: None)
    assert (r2['consultados'], r2['do_cache']) == (0, 1)
    assert len(rede.urls) == 1


def test_consulta_com_mais_de_30_dias_e_refeita(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA, dormir=lambda s: None)
    r = cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA + timedelta(days=31),
                       dormir=lambda s: None)
    assert r['consultados'] == 1 and len(rede.urls) == 2


def test_forcar_ignora_a_consulta_guardada(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA, dormir=lambda s: None)
    r = cnpj.atualizar(conn, [BB], abrir=rede, agora=AGORA, dormir=lambda s: None, forcar=True)
    assert r['consultados'] == 1 and len(rede.urls) == 2


def test_cnpj_invalido_ou_em_branco_e_ignorado_sem_chamar_a_rede(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    r = cnpj.atualizar(conn, ['', '11.111.111/1111-11', None], abrir=rede, agora=AGORA)
    assert r['ignorados'] == 2 and r['consultados'] == 0 and rede.urls == []  # '' e None contam uma vez


def test_duas_falhas_de_conexao_seguidas_interrompem_o_resto_do_lote(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede(erro=urllib.error.URLError('sem rede'))
    r = cnpj.atualizar(conn, CNPJS_VALIDOS, abrir=rede, agora=AGORA, dormir=lambda s: None)
    assert len(rede.urls) == 2                                  # parou na segunda falha
    assert r['interrompido'] is True and r['pendentes'] == 2 and len(r['falhas']) == 2
    assert r['consultados'] == 0
    assert armazenamento.cnpj_receita_de(conn, BB) is None      # nada gravado


def test_cnpj_nao_encontrado_nao_interrompe_o_lote(tmp_path):
    conn = _conn(tmp_path)
    respostas = iter([_http(404), _http(404), _http(404), None])

    def abrir(url):
        r = next(respostas)
        if r is not None:
            raise r
        return _resposta()

    r = cnpj.atualizar(conn, CNPJS_VALIDOS, abrir=abrir, agora=AGORA, dormir=lambda s: None)
    assert r['interrompido'] is False and len(r['falhas']) == 3 and r['consultados'] == 1


def test_pausa_entre_consultas_reais_mas_nao_antes_da_primeira(tmp_path):
    conn = _conn(tmp_path)
    pausas = []
    cnpj.atualizar(conn, CNPJS_VALIDOS[:3], abrir=Rede(), agora=AGORA, dormir=pausas.append)
    assert pausas == [cnpj.PAUSA, cnpj.PAUSA]


def test_atualizar_do_lote_usa_so_os_cnpjs_dos_regimes(tmp_path):
    conn = _conn(tmp_path)
    rede = Rede()
    lote = Lote(regimes=[{'CNPJ REQUERENTE': ALFA}, {'CNPJ REQUERENTE': ''}],
                consultas=[{'CNPJ REQUERENTE': BB}])
    r = cnpj.atualizar_do_lote(conn, lote, abrir=rede, agora=AGORA, dormir=lambda s: None)
    assert rede.urls == ['https://brasilapi.com.br/api/cnpj/v1/11222333000181']
    assert r['consultados'] == 1 and r['ignorados'] == 1


# --- mensagem e divergência --------------------------------------------------
def test_mensagem_do_resumo():
    base = {'consultados': 0, 'do_cache': 0, 'ignorados': 0, 'falhas': [],
            'interrompido': False, 'pendentes': 0}
    assert cnpj.mensagem_do_resumo(None) is None
    assert cnpj.mensagem_do_resumo(base) is None
    assert cnpj.mensagem_do_resumo({**base, 'do_cache': 4, 'ignorados': 1}) is None
    msg = cnpj.mensagem_do_resumo({**base, 'consultados': 3,
                                   'falhas': [('x', 'sem acesso à BrasilAPI (timeout)')],
                                   'pendentes': 2})
    assert '3 CNPJ(s) consultado(s)' in msg
    assert '1 sem resposta (sem acesso à BrasilAPI (timeout))' in msg
    assert '2 ficaram pendentes' in msg


def test_divergencia_so_existe_quando_o_regime_tem_cnae_diferente():
    receita = {'cnae_codigo': '6422100'}
    assert cnpj.divergencia({'CNAE REQUERENTE': ''}, receita) is None          # em branco
    assert cnpj.divergencia({'CNAE REQUERENTE': '6422-1/00'}, receita) is None  # igual
    assert cnpj.divergencia({'CNAE REQUERENTE': '4930202'}, receita) == {
        'regime': '4930-2/02', 'receita': '6422-1/00'}
    assert cnpj.divergencia({'CNAE REQUERENTE': '4930202'}, None) is None
```

- [ ] **Step 2: Rodar e ver FALHAR**

Run: `python -m pytest tests/test_cnpj.py -q` — Expected: FAIL: `ImportError: cannot import name 'cnpj' from 'core'`.

- [ ] **Step 3: Implementar**

**Criar `core/cnpj.py`** com exatamente este conteúdo:

```python
# core/cnpj.py
"""Consulta do CNPJ do requerente na BrasilAPI: CNAE principal e situação cadastral.

A consulta roda sozinha ao GRAVAR um lote (Execucao.gravar na CLI; app.py na
interface) e, sob demanda, pelo botão do detalhe do regime. O resultado fica na
tabela `cnpj_receita`, À PARTE do regime: o CNAE da Receita é o CNAE ATUAL da
empresa e pode diferir do vigente na data do regime, então ele nunca sobrescreve
os campos do regime sozinho (o administrador decide aplicá-lo; ver app.py).

Falha de rede nunca impede a gravação: `atualizar` não levanta por causa de
internet fora do ar ou da API; devolve o que aconteceu num resumo. Só o CNPJ sai
da máquina (dado público); a consulta pode ser desligada com
MAPEADOR_CONSULTA_CNPJ=0 (e, na CLI, com --sem-consulta-cnpj).

Sem Streamlit; sem dependência de terceiros (só `urllib`).
"""
import http.client
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from core import armazenamento
from core.diagnostico import cnpj_valido

URL = 'https://brasilapi.com.br/api/cnpj/v1/{cnpj}'
TIMEOUT = 5              # segundos por consulta
CACHE_DIAS = 30          # consulta mais nova que isso é reaproveitada
PAUSA = 0.3              # segundos entre duas consultas reais (gentileza com a API pública)
MAX_FALHAS_SEGUIDAS = 2  # sem internet: para de tentar o resto do lote


class CnpjInvalido(ValueError):
    """CNPJ mal formado ou com dígitos verificadores errados."""


class CnpjNaoEncontrado(LookupError):
    """A Receita não conhece esse CNPJ."""


class ConsultaIndisponivel(RuntimeError):
    """Sem internet, API fora do ar, limite de uso ou resposta ilegível."""


def so_digitos(cnpj) -> str:
    return ''.join(c for c in str(cnpj or '') if c.isdigit())


def formatar_cnae(codigo) -> str:
    """'6422100' -> '6422-1/00'; qualquer outra coisa volta como veio."""
    digitos = so_digitos(codigo)
    return f'{digitos[:4]}-{digitos[4]}/{digitos[5:]}' if len(digitos) == 7 else str(codigo or '')


def habilitada() -> bool:
    """MAPEADOR_CONSULTA_CNPJ=0 desliga a consulta automática (máquina sem internet)."""
    valor = os.environ.get('MAPEADOR_CONSULTA_CNPJ', '1').strip().lower()
    return valor not in ('0', 'nao', 'não', 'false', 'off')


def _abrir(url: str, timeout: float = TIMEOUT) -> bytes:
    pedido = urllib.request.Request(
        url, headers={'User-Agent': 'mapeador-pr', 'Accept': 'application/json'})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return resposta.read()


def consultar(cnpj, abrir=None) -> dict:
    """Consulta UM CNPJ. `abrir(url) -> bytes` é injetável (os testes nunca usam a rede).

    Devolve {'cnpj', 'razao_social', 'cnae_codigo', 'cnae_descricao', 'situacao'}.
    Levanta CnpjInvalido (sem chamar a rede se os dígitos não conferem),
    CnpjNaoEncontrado ou ConsultaIndisponivel."""
    digitos = so_digitos(cnpj)
    if not cnpj_valido(digitos):
        raise CnpjInvalido(f'CNPJ inválido: {cnpj!r}')
    abrir = abrir or _abrir
    try:
        bruto = abrir(URL.format(cnpj=digitos))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            raise CnpjNaoEncontrado(f'CNPJ {digitos} não encontrado na Receita') from erro
        if erro.code == 400:
            raise CnpjInvalido(f'A BrasilAPI recusou o CNPJ {digitos}') from erro
        raise ConsultaIndisponivel(f'BrasilAPI respondeu HTTP {erro.code}') from erro
    except (OSError, http.client.HTTPException) as erro:   # URLError e timeout são OSError
        raise ConsultaIndisponivel(f'sem acesso à BrasilAPI ({erro})') from erro
    try:
        dados = json.loads(bruto)
    except ValueError as erro:
        raise ConsultaIndisponivel('resposta da BrasilAPI ilegível') from erro
    if not isinstance(dados, dict):
        raise ConsultaIndisponivel('resposta da BrasilAPI ilegível')
    codigo = so_digitos(dados.get('cnae_fiscal'))
    return {'cnpj': digitos,
            'razao_social': str(dados.get('razao_social') or ''),
            'cnae_codigo': codigo.zfill(7) if codigo else '',
            'cnae_descricao': str(dados.get('cnae_fiscal_descricao') or ''),
            'situacao': str(dados.get('descricao_situacao_cadastral') or '')}


def _recente(consultado_em, agora) -> bool:
    try:
        return agora - datetime.fromisoformat(consultado_em) < timedelta(days=CACHE_DIAS)
    except (TypeError, ValueError):
        return False


def atualizar(conn, cnpjs, abrir=None, agora=None, dormir=time.sleep, forcar=False) -> dict:
    """Consulta e grava em `cnpj_receita` os CNPJs sem consulta recente.

    `forcar` ignora a consulta guardada. Não levanta por falha de rede: duas
    falhas de conexão seguidas interrompem o resto do lote (ficam `pendentes`).
    Devolve {'consultados', 'do_cache', 'ignorados' (inválidos/em branco),
    'falhas': [(cnpj, motivo)], 'interrompido': bool, 'pendentes'}."""
    agora = agora or datetime.now(timezone.utc)
    resumo = {'consultados': 0, 'do_cache': 0, 'ignorados': 0, 'falhas': [],
              'interrompido': False, 'pendentes': 0}
    vistos, seguidas, ja_consultou = set(), 0, False
    for bruto in cnpjs:
        digitos = so_digitos(bruto)
        if digitos in vistos:
            continue
        vistos.add(digitos)
        if not cnpj_valido(digitos):
            resumo['ignorados'] += 1
            continue
        guardado = armazenamento.cnpj_receita_de(conn, digitos)
        if not forcar and guardado and _recente(guardado['consultado_em'], agora):
            resumo['do_cache'] += 1
            continue
        if resumo['interrompido']:
            resumo['pendentes'] += 1
            continue
        if ja_consultou:
            dormir(PAUSA)
        ja_consultou = True
        try:
            dados = consultar(digitos, abrir)
        except ConsultaIndisponivel as erro:
            resumo['falhas'].append((digitos, str(erro)))
            seguidas += 1
            resumo['interrompido'] = seguidas >= MAX_FALHAS_SEGUIDAS
            continue
        except (CnpjNaoEncontrado, CnpjInvalido) as erro:
            resumo['falhas'].append((digitos, str(erro)))
            seguidas = 0
            continue
        seguidas = 0
        armazenamento.salvar_cnpj_receita(conn, dados,
                                          consultado_em=agora.isoformat(timespec='seconds'))
        resumo['consultados'] += 1
    return resumo


def atualizar_do_lote(conn, lote, **opcoes) -> dict:
    """`atualizar` para os CNPJs dos regimes do lote (as consultas não têm CNPJ)."""
    return atualizar(conn, [r.get('CNPJ REQUERENTE', '') for r in lote.regimes], **opcoes)


def mensagem_do_resumo(resumo) -> str | None:
    """Uma frase para a tela/CLI; None quando não houve nada a dizer."""
    if not resumo:
        return None
    partes = []
    if resumo['consultados']:
        partes.append(f"{resumo['consultados']} CNPJ(s) consultado(s)")
    if resumo['falhas']:
        partes.append(f"{len(resumo['falhas'])} sem resposta ({resumo['falhas'][0][1]})")
    if resumo['pendentes']:
        partes.append(f"{resumo['pendentes']} ficaram pendentes "
                      "(consulte pelo detalhe do regime)")
    return '; '.join(partes) or None


def divergencia(regime: dict, receita: dict | None) -> dict | None:
    """Se o regime TEM um CNAE informado e ele difere do da Receita, devolve os dois
    já formatados; senão None (CNAE em branco não é divergência)."""
    do_regime = so_digitos(regime.get('CNAE REQUERENTE'))
    da_receita = so_digitos((receita or {}).get('cnae_codigo'))
    if do_regime and da_receita and do_regime != da_receita:
        return {'regime': formatar_cnae(do_regime), 'receita': formatar_cnae(da_receita)}
    return None
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_cnpj.py -q` — Expected: PASS.

Depois a suíte inteira: `python -m pytest -q` — Expected: **398 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/cnpj.py tests/test_cnpj.py
git commit -m "feat: consulta do CNPJ na BrasilAPI com reaproveitamento e tolerância a falha de rede"
```

(sem `Co-Authored-By`).

---

### Task 3: Consulta automática ao gravar: `Execucao` e CLI

**Files:**
- Modificar: `core/execucao.py`
- Modificar: `processar.py`
- Modificar: `tests/test_execucao.py`
- Modificar: `tests/test_processar.py`

**Interfaces:**
- Consumes: Tarefa 2: `cnpj.atualizar_do_lote`, `cnpj.habilitada`, `cnpj.mensagem_do_resumo`, `tests.test_cnpj.Rede`.
- Produces: `Execucao(..., consultar_cnpj: bool = True, abrir_cnpj=None)`; `Execucao.resumo_cnpj` (dict de `cnpj.atualizar`, ou `None` se a consulta está desligada); `Execucao.gravar` mantém o retorno `{'consultas','regimes'}`; CLI: `--sem-consulta-cnpj` e a linha `  Receita:   ...`; `--simular` nunca consulta.

> A consulta roda **depois** de `persistir_lote` e fora dele: o retorno de `persistir_lote` e de `gravar` não muda, e uma falha de rede nunca desfaz nem impede a gravação.

- [ ] **Step 1: Escrever os testes (que ainda falham)**

**Em `tests/test_execucao.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
import os

import pytest

from core import armazenamento
from core.execucao import Execucao
```

por:

```python
import os
import urllib.error

import pytest

from core import armazenamento, pipeline
from core.execucao import Execucao
from tests.test_cnpj import Rede
```

**Acrescentar ao FIM de `tests/test_execucao.py`** (depois de uma linha em branco) exatamente:

```python
# --- consulta do CNPJ ao gravar ----------------------------------------------
REGIME = {'ANO': '2026', 'DATA': '2026-03-01', 'Nº DO REGIME ESPECIAL': '9.053/2026',
          'EMPRESA': 'Alfa Ltda', 'CNPJ REQUERENTE': '11.222.333/0001-81',
          'VIGÊNCIA DO RE': '12 meses', 'EMENTA': 'ementa'}


def _execucao_com_regime(**opcoes):
    ex = Execucao(**opcoes)
    ex.lote = pipeline.Lote(regimes=[dict(REGIME)])
    return ex


def test_gravar_consulta_o_cnpj_dos_regimes_e_guarda_o_resumo(tmp_path, monkeypatch):
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '1')
    rede = Rede()
    ex = _execucao_com_regime(abrir_cnpj=rede)
    with armazenamento.sessao(str(tmp_path / 'g.db')) as conn:
        resultado = ex.gravar(conn)
        receita = armazenamento.cnpj_receita_de(conn, REGIME['CNPJ REQUERENTE'])
    assert set(resultado) == {'consultas', 'regimes'} and resultado['regimes']['novos'] == 1
    assert receita['cnae_codigo'] == '6422100'
    assert ex.resumo_cnpj['consultados'] == 1


def test_falha_de_rede_nao_impede_a_gravacao(tmp_path, monkeypatch):
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '1')
    ex = _execucao_com_regime(abrir_cnpj=Rede(erro=urllib.error.URLError('sem rede')))
    with armazenamento.sessao(str(tmp_path / 'g.db')) as conn:
        resultado = ex.gravar(conn)
        assert len(armazenamento.buscar_regimes(conn)) == 1
    assert resultado['regimes']['novos'] == 1
    assert len(ex.resumo_cnpj['falhas']) == 1 and ex.resumo_cnpj['consultados'] == 0


@pytest.mark.parametrize('consultar_cnpj,variavel', [(False, '1'), (True, '0')])
def test_consulta_desligada_nao_chama_a_rede(tmp_path, monkeypatch, consultar_cnpj, variavel):
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', variavel)
    rede = Rede()
    ex = _execucao_com_regime(abrir_cnpj=rede, consultar_cnpj=consultar_cnpj)
    with armazenamento.sessao(str(tmp_path / 'g.db')) as conn:
        resultado = ex.gravar(conn)
    assert resultado['regimes']['novos'] == 1
    assert rede.urls == [] and ex.resumo_cnpj is None
```

**Acrescentar ao FIM de `tests/test_processar.py`** (depois de uma linha em branco) exatamente:

```python
# --- consulta do CNPJ ao gravar (BrasilAPI) ----------------------------------
def _pasta_com_regime(tmp_path):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Regime_Agroantunes.pdf"), pasta / "r.pdf")
    return pasta


def _com_rede(monkeypatch):
    from tests.test_cnpj import Rede
    rede = Rede()
    monkeypatch.setenv("MAPEADOR_CONSULTA_CNPJ", "1")
    monkeypatch.setattr("core.cnpj._abrir", rede)
    return rede


def test_cli_consulta_o_cnpj_do_regime_ao_gravar(tmp_path, monkeypatch, capsys):
    rede = _com_rede(monkeypatch)
    banco = tmp_path / "b.db"
    codigo = processar.main([str(_pasta_com_regime(tmp_path)), "--banco", str(banco)])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert len(rede.urls) == 1
    assert "Receita:   1 CNPJ(s) consultado(s)" in saida
    conn = armazenamento.conectar(str(banco))
    assert conn.execute("SELECT COUNT(*) FROM cnpj_receita").fetchone()[0] == 1
    conn.close()


def test_cli_sem_consulta_cnpj_nao_chama_a_rede(tmp_path, monkeypatch, capsys):
    rede = _com_rede(monkeypatch)
    codigo = processar.main([str(_pasta_com_regime(tmp_path)), "--banco", str(tmp_path / "b.db"),
                             "--sem-consulta-cnpj"])
    assert codigo == 0 and rede.urls == []
    assert "Receita:" not in capsys.readouterr().out


def test_cli_simular_nao_consulta_o_cnpj(tmp_path, monkeypatch, capsys):
    rede = _com_rede(monkeypatch)
    codigo = processar.main([str(_pasta_com_regime(tmp_path)), "--banco", str(tmp_path / "b.db"),
                             "--simular"])
    assert codigo == 0 and rede.urls == []
    assert not os.path.exists(tmp_path / "b.db")


def test_cli_sem_internet_grava_e_avisa(tmp_path, monkeypatch, capsys):
    import urllib.error
    from tests.test_cnpj import Rede
    monkeypatch.setenv("MAPEADOR_CONSULTA_CNPJ", "1")
    monkeypatch.setattr("core.cnpj._abrir", Rede(erro=urllib.error.URLError("sem rede")))
    banco = tmp_path / "b.db"
    codigo = processar.main([str(_pasta_com_regime(tmp_path)), "--banco", str(banco)])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "Regimes:   1 novos" in saida
    assert "Receita:   1 sem resposta" in saida
    conn = armazenamento.conectar(str(banco))
    assert len(armazenamento.buscar_regimes(conn)) == 1
    conn.close()
```

- [ ] **Step 2: Rodar e ver FALHAR**

Run: `python -m pytest tests/test_execucao.py tests/test_processar.py -q` — Expected: FAIL: `TypeError` (argumento `abrir_cnpj` desconhecido) e `Receita:` ausente da saída da CLI.

- [ ] **Step 3: Implementar**

**Em `core/execucao.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
from core import armazenamento, diagnostico, pipeline
```

por:

```python
from core import armazenamento, cnpj, diagnostico, pipeline
```

**Em `core/execucao.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    def __init__(self, progresso=None, ao_arquivo=None,
                 dedup: str = pipeline.CRITERIO_PADRAO):
```

por:

```python
    def __init__(self, progresso=None, ao_arquivo=None,
                 dedup: str = pipeline.CRITERIO_PADRAO,
                 consultar_cnpj: bool = True, abrir_cnpj=None):
```

**Em `core/execucao.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
        self.lote = None
        self.diagnostico = None
```

por:

```python
        self.consultar_cnpj = consultar_cnpj
        self._abrir_cnpj = abrir_cnpj   # só para testes: `abrir(url) -> bytes`
        self.lote = None
        self.diagnostico = None
        self.resumo_cnpj = None   # resultado da consulta de CNPJ do último `gravar`
```

**Em `core/execucao.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
        """Persiste o lote carregado. Devolve o resumo de novos/atualizados.
```

por:

```python
        """Persiste o lote carregado. Devolve o resumo de novos/atualizados.

        Depois de gravar, consulta na BrasilAPI o CNPJ dos regimes (CNAE e situação
        cadastral; ver core/cnpj.py). Falha de rede NÃO impede a gravação: o que
        aconteceu fica em `self.resumo_cnpj` (None se a consulta está desligada:
        `consultar_cnpj=False` ou MAPEADOR_CONSULTA_CNPJ=0).
```

**Em `core/execucao.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
        resultado = armazenamento.persistir_lote(conn, self.lote, sobrescrever)
        self._progresso('gravacao', 1, 1, '')
```

por:

```python
        resultado = armazenamento.persistir_lote(conn, self.lote, sobrescrever)
        if self.consultar_cnpj and cnpj.habilitada():
            self.resumo_cnpj = cnpj.atualizar_do_lote(conn, self.lote,
                                                      abrir=self._abrir_cnpj)
        self._progresso('gravacao', 1, 1, '')
```

**Em `processar.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
                            [--sobrescrever-ajustes]

Persiste no banco
```

por:

```python
                            [--sobrescrever-ajustes] [--sem-consulta-cnpj]

Persiste no banco
```

**Em `processar.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
reimportar; --sobrescrever-ajustes faz o valor do PDF vencer em todos eles.
```

por:

```python
reimportar; --sobrescrever-ajustes faz o valor do PDF vencer em todos eles.
Ao gravar, consulta o CNPJ dos regimes na BrasilAPI (CNAE e situação cadastral);
--sem-consulta-cnpj ou MAPEADOR_CONSULTA_CNPJ=0 desligam a consulta. Sem internet
a gravação segue normalmente e a CLI avisa que a consulta falhou.
```

**Em `processar.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
        "[--sobrescrever-ajustes]")
```

por:

```python
        "[--sobrescrever-ajustes] [--sem-consulta-cnpj]")
```

**Em `processar.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    sobrescrever_ajustes = "--sobrescrever-ajustes" in argv
```

por:

```python
    sobrescrever_ajustes = "--sobrescrever-ajustes" in argv
    sem_consulta_cnpj = "--sem-consulta-cnpj" in argv
```

**Em `processar.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    from core import armazenamento, edicao, log, pipeline, planilha  # noqa: E402
```

por:

```python
    from core import armazenamento, cnpj, edicao, log, pipeline, planilha  # noqa: E402
```

**Em `processar.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    execucao = Execucao(ao_arquivo=_imprime_linha, dedup=dedup)
```

por:

```python
    execucao = Execucao(ao_arquivo=_imprime_linha, dedup=dedup,
                        consultar_cnpj=not sem_consulta_cnpj)
```

**Em `processar.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
          f"{resultado['regimes']['atualizados']} atualizados")
    if xlsx:
```

por:

```python
          f"{resultado['regimes']['atualizados']} atualizados")
    mensagem = cnpj.mensagem_do_resumo(execucao.resumo_cnpj)
    if mensagem:
        print(f"  Receita:   {mensagem}")
    if xlsx:
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_execucao.py tests/test_processar.py -q` — Expected: PASS.

Depois a suíte inteira: `python -m pytest -q` — Expected: **406 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/execucao.py processar.py tests/test_execucao.py tests/test_processar.py
git commit -m "feat: gravar consulta o CNPJ dos regimes na Receita (CLI com --sem-consulta-cnpj)"
```

(sem `Co-Authored-By`).

---

### Task 4: Interface: consulta ao gravar, bloco da Receita no detalhe, atualizar e aplicar o CNAE

**Files:**
- Modificar: `core/consulta.py`
- Modificar: `app.py`
- Modificar: `tests/test_consulta.py`
- Modificar: `tests/test_app.py`

**Interfaces:**
- Consumes: Tarefas 1–2: `cnpj.atualizar_do_lote`, `cnpj.atualizar(..., forcar=True)`, `cnpj.mensagem_do_resumo`, `cnpj.divergencia`, `cnpj.formatar_cnae`, `cnpj.so_digitos`, `cnpj.habilitada`; da edição manual (0.8.0): `edicao.editar_registro`, `edicao.TIPOS`, `_avisar`, `_fecha_selecao_da_tabela`, `_data_br`, `acesso.exige_admin` (todos já em `app.py`).
- Produces: `consulta.receita(conn, registro) -> dict | None`; em `app.py`: `_avisar_receita`, `_consultar_cnpj`, `_aplicar_cnae`, `_bloco_receita`; botões com as chaves `consultar-cnpj` e `aplicar-cnae`; `_mostra_detalhe(..., receita=None)`; as 6 chaves de `st.session_state["resultado"]` continuam as mesmas.

> Os dois botões rodam no `on_click` (mesma razão do formulário de edição: o Streamlit não deixa mexer no estado de um widget já desenhado). O perfil Consulta **vê** o bloco da Receita, mas nenhum botão. O CNAE da Receita **nunca** é gravado no regime sozinho: só por `Aplicar CNAE da Receita ao regime`.

- [ ] **Step 1: Escrever os testes (que ainda falham)**

**Acrescentar ao FIM de `tests/test_consulta.py`** (depois de uma linha em branco) exatamente:

```python
def test_receita_devolve_a_consulta_do_cnpj_do_regime(conn):
    regime = {'CNPJ REQUERENTE': '00.000.000/0001-91'}
    assert consulta.receita(conn, regime) is None
    armazenamento.salvar_cnpj_receita(
        conn, {'cnpj': '00000000000191', 'cnae_codigo': '6422100',
               'cnae_descricao': 'Bancos múltiplos', 'situacao': 'ATIVA'})
    assert consulta.receita(conn, regime)['cnae_codigo'] == '6422100'
    assert consulta.receita(conn, {'CNPJ REQUERENTE': ''}) is None
```

**Acrescentar ao FIM de `tests/test_app.py`** (depois de uma linha em branco) exatamente:

```python
# --- consulta do CNPJ (Receita Federal) --------------------------------------
CNPJ_DO_REGIME = '11222333000181'


def _com_rede(monkeypatch):
    from tests.test_cnpj import Rede
    rede = Rede()
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '1')
    monkeypatch.setattr('core.cnpj._abrir', rede)
    return rede


def _guarda_receita(cnae_codigo='6422100'):
    conn = _banco_do_teste()
    armazenamento.salvar_cnpj_receita(
        conn, {'cnpj': CNPJ_DO_REGIME, 'razao_social': 'Alfa Ltda', 'cnae_codigo': cnae_codigo,
               'cnae_descricao': 'Bancos múltiplos', 'situacao': 'ATIVA'},
        consultado_em='2026-11-03T12:00:00+00:00')
    conn.close()


def _textos(at):
    return [m.value for m in at.markdown] + [c.value for c in at.caption]


def test_detalhe_do_regime_sem_consulta_avisa_e_so_o_admin_ve_o_botao():
    at = _abre_o_detalhe_do_regime("consulta")
    assert any("ainda não consultado" in t for t in _textos(at))
    assert "consultar-cnpj" not in {b.key for b in at.button}
    at = _abre_o_detalhe_do_regime("admin")
    assert any("ainda não consultado" in t for t in _textos(at))
    assert "consultar-cnpj" in {b.key for b in at.button}


def test_detalhe_mostra_o_cnae_e_a_situacao_da_receita_para_qualquer_perfil():
    _guarda_receita()
    at = _abre_o_detalhe_do_regime("consulta")
    textos = " ".join(_textos(at))
    assert "6422-1/00" in textos and "Bancos múltiplos" in textos and "ATIVA" in textos
    assert "03/11/2026" in textos
    assert not {"consultar-cnpj", "aplicar-cnae"} & {b.key for b in at.button}


def test_admin_consulta_o_cnpj_pelo_detalhe(monkeypatch):
    rede = _com_rede(monkeypatch)
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="consultar-cnpj").click().run(timeout=30)
    assert not at.exception
    assert rede.urls == [f'https://brasilapi.com.br/api/cnpj/v1/{CNPJ_DO_REGIME}']
    assert any("CNPJ consultado" in t.value for t in at.toast)
    _linha_0(at)
    at.run(timeout=30)
    assert "6422-1/00" in " ".join(_textos(at))
    assert "aplicar-cnae" in {b.key for b in at.button}


def test_consulta_pelo_detalhe_mostra_o_motivo_quando_a_rede_falha(monkeypatch):
    import urllib.error
    from tests.test_cnpj import Rede
    monkeypatch.setattr('core.cnpj._abrir', Rede(erro=urllib.error.URLError('sem rede')))
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="consultar-cnpj").click().run(timeout=30)
    assert not at.exception
    assert any("sem acesso à BrasilAPI" in t.value for t in at.toast)


def test_admin_aplica_o_cnae_da_receita_ao_regime():
    _guarda_receita()
    at = _abre_o_detalhe_do_regime("admin")
    _linha_0(at)
    at.button(key="aplicar-cnae").click().run(timeout=30)
    assert not at.exception
    linha = _regimes_no_banco()[0]
    assert linha['CNAE REQUERENTE'] == '6422-1/00'
    assert linha['DESCRIÇÃO CNAE'] == 'Bancos múltiplos'
    from core import consulta
    conn = _banco_do_teste()
    assert set(consulta.ajustes(conn, 'regime', REGIME)) == {'CNAE REQUERENTE', 'DESCRIÇÃO CNAE'}
    conn.close()
    assert any("CNAE aplicado" in t.value for t in at.toast)


def test_divergencia_de_cnae_aparece_so_quando_o_regime_ja_tem_outro_cnae():
    _guarda_receita()
    at = _abre_o_detalhe_do_regime("admin", regimes=({**REGIME, 'CNAE REQUERENTE': '4930-2/02'},))
    assert any("difere" in w.value and "4930-2/02" in w.value and "6422-1/00" in w.value
               for w in at.warning)
    at = _abre_o_detalhe_do_regime("admin")           # CNAE em branco: sem divergência
    assert not any("difere" in w.value for w in at.warning)


def test_gravar_na_analise_consulta_os_cnpjs_e_avisa(monkeypatch):
    rede = _com_rede(monkeypatch)
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert rede.urls == [f'https://brasilapi.com.br/api/cnpj/v1/{CNPJ_DO_REGIME}']
    assert any("Receita Federal: 1 CNPJ(s) consultado(s)" in t.value for t in at.toast)
    assert set(at.session_state["resultado"]) == {
        "arquivos", "consultas", "regimes", "descartes", "mapeamento", "xlsx"}
    conn = _banco_do_teste()
    assert armazenamento.cnpj_receita_de(conn, CNPJ_DO_REGIME)['cnae_codigo'] == '6422100'
    conn.close()


def test_gravar_sem_internet_grava_e_avisa(monkeypatch):
    import urllib.error
    from tests.test_cnpj import Rede
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '1')
    monkeypatch.setattr('core.cnpj._abrir', Rede(erro=urllib.error.URLError('sem rede')))
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert len(_regimes_no_banco()) == 1
    assert any("Receita Federal:" in t.value and "sem resposta" in t.value for t in at.toast)


def test_gravar_com_a_consulta_desligada_nao_chama_a_rede(monkeypatch):
    rede = _com_rede(monkeypatch)
    monkeypatch.setenv('MAPEADOR_CONSULTA_CNPJ', '0')
    at = _app("admin")
    at.session_state["analise"] = _analise_com(_lote_sem_vigencia())
    at.run(timeout=30)
    at.button(key="gravar").click().run(timeout=30)
    assert not at.exception
    assert rede.urls == [] and len(_regimes_no_banco()) == 1
```

- [ ] **Step 2: Rodar e ver FALHAR**

Run: `python -m pytest tests/test_consulta.py tests/test_app.py -q` — Expected: FAIL: `KeyError` nos botões `consultar-cnpj`/`aplicar-cnae` e `AttributeError: ... 'receita'`.

- [ ] **Step 3: Implementar**

**Acrescentar ao FIM de `core/consulta.py`** (depois de uma linha em branco) exatamente:

```python
def receita(conn, registro: dict):
    """Dados do CNPJ do regime na Receita Federal (CNAE e situação), guardados em
    cnpj_receita; None se o CNPJ ainda não foi consultado."""
    return armazenamento.cnpj_receita_de(conn, registro.get('CNPJ REQUERENTE'))
```

**Em `app.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
from core import acesso, armazenamento, consulta, diagnostico, edicao, log, planilha  # noqa: E402
```

por:

```python
from core import (acesso, armazenamento, cnpj, consulta, diagnostico, edicao,  # noqa: E402
                  log, planilha)
```

**Em `app.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    mapeamento = _persistir(lote, sobrescrever)
```

por:

```python
    mapeamento = _persistir(lote, sobrescrever)
    if cnpj.habilitada():
        with st.spinner("Consultando os CNPJs na Receita Federal…"):
            with armazenamento.sessao(_CAMINHO_BANCO) as conn:
                _avisar_receita(cnpj.atualizar_do_lote(conn, lote))
```

**Em `app.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
@st.dialog("Detalhes", width="large", on_dismiss=_fecha_selecao_da_tabela)
```

por:

```python
def _avisar_receita(resumo):
    """Deixa para o toast o resultado da consulta de CNPJs feita ao gravar."""
    mensagem = cnpj.mensagem_do_resumo(resumo)
    if mensagem:
        st.session_state["aviso"] = f"Receita Federal: {mensagem}"


def _consultar_cnpj(cnpj_do_regime: str):
    """Consulta (ou refaz a consulta de) um CNPJ pelo detalhe do regime. Roda no
    on_click do botão: o toast sai na reexecução seguinte e o detalhe continua aberto."""
    acesso.exige_admin(st.session_state.get("perfil"))
    with armazenamento.sessao(_CAMINHO_BANCO) as conn:
        resumo = cnpj.atualizar(conn, [cnpj_do_regime], forcar=True)
    if resumo["consultados"]:
        st.session_state["aviso"] = "Receita Federal: CNPJ consultado."
    elif resumo["falhas"]:
        st.session_state["aviso"] = f"Receita Federal: {resumo['falhas'][0][1]}."
    else:
        st.session_state["aviso"] = "Receita Federal: CNPJ em branco ou inválido, nada a consultar."


def _aplicar_cnae(registro: dict, receita: dict):
    """Grava no regime o CNAE da Receita (vira ajuste manual, com histórico)."""
    acesso.exige_admin(st.session_state.get("perfil"))
    chave_atual = {c: registro[c] for c in edicao.TIPOS["regime"][2]}
    novos = {"CNAE REQUERENTE": cnpj.formatar_cnae(receita["cnae_codigo"]),
             "DESCRIÇÃO CNAE": receita["cnae_descricao"]}
    try:
        with armazenamento.sessao(_CAMINHO_BANCO) as conn:
            r = edicao.editar_registro(conn, "regime", chave_atual, novos)
    except edicao.RegistroInexistente as erro:
        st.session_state["aviso"] = str(erro)
        return
    _avisar(r, "CNAE aplicado")
    _fecha_selecao_da_tabela()


def _bloco_receita(registro: dict, receita, pode_editar: bool):
    """CNAE e situação do CNPJ na Receita Federal (BrasilAPI), guardados à parte do regime."""
    st.markdown('<div class="icms-campo-detalhe-rotulo">Receita Federal (BrasilAPI)</div>',
                unsafe_allow_html=True)
    if not receita:
        st.caption("CNPJ ainda não consultado.")
    else:
        st.write(f"CNAE principal: {cnpj.formatar_cnae(receita['cnae_codigo'])}"
                 f" — {receita['cnae_descricao']}")
        st.write(f"Situação cadastral: {receita['situacao'] or '—'}")
        st.caption(f"Consultado em {_data_br(receita['consultado_em'])}. É o CNAE atual da "
                   "empresa, que pode diferir do vigente na data do regime.")
        divergente = cnpj.divergencia(registro, receita)
        if divergente:
            st.warning(f"O CNAE informado no regime ({divergente['regime']}) difere do "
                       f"da Receita ({divergente['receita']}).")
    if not pode_editar:
        return
    st.button("Atualizar consulta" if receita else "Consultar CNPJ", key="consultar-cnpj",
              icon=":material/search:", on_click=_consultar_cnpj,
              args=(registro.get("CNPJ REQUERENTE", ""),))
    if (receita and receita["cnae_codigo"]
            and cnpj.so_digitos(registro.get("CNAE REQUERENTE")) != receita["cnae_codigo"]):
        st.button("Aplicar CNAE da Receita ao regime", key="aplicar-cnae",
                  icon=":material/check:", on_click=_aplicar_cnae, args=(registro, receita))


@st.dialog("Detalhes", width="large", on_dismiss=_fecha_selecao_da_tabela)
```

**Em `app.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
                    pode_editar: bool = False, ajustes=()):
```

por:

```python
                    pode_editar: bool = False, ajustes=(), receita=None):
```

**Em `app.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
    if pode_editar:
        st.button("Editar", key="editar-registro",
```

por:

```python
    if tipo == "regime":
        _bloco_receita(registro, receita, pode_editar)
    if pode_editar:
        st.button("Editar", key="editar-registro",
```

**Em `app.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
                                ajustes=consulta.ajustes(conn, tipo, completo))
```

por:

```python
                                ajustes=consulta.ajustes(conn, tipo, completo),
                                receita=(consulta.receita(conn, completo)
                                         if tipo == "regime" else None))
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_consulta.py tests/test_app.py -q` — Expected: PASS.

Depois a suíte inteira: `python -m pytest -q` — Expected: **416 testes passando**.

- [ ] **Step 5: Commit**

```bash
git add core/consulta.py app.py tests/test_consulta.py tests/test_app.py
git commit -m "feat: detalhe do regime mostra o CNAE da Receita; administrador consulta e aplica"
```

(sem `Co-Authored-By`).

---

### Task 5: Documentação, versão 0.9.0 e verificação final

**Files:**
- Modificar: `core/versao.py`
- Modificar: `CHANGELOG.md`
- Modificar: `README.md`

**Interfaces:**
- Consumes: Tarefas 1–4.
- Produces: `VERSAO_APP = "0.9.0"`; README e CHANGELOG descrevendo o comportamento real.

- [ ] **Step 1: Implementar**

**Em `core/versao.py`**, trocar este trecho (único no arquivo, copiado como está):

```python
VERSAO_APP = "0.8.0"
```

por:

```python
VERSAO_APP = "0.9.0"
```

**Em `CHANGELOG.md`**, trocar este trecho (único no arquivo, copiado como está):

```markdown
# Histórico de versões

## 0.8.0
```

por:

```markdown
# Histórico de versões

## 0.9.0
- **Consulta do CNPJ na BrasilAPI**: ao gravar, o CNPJ de cada regime é consultado (CNAE principal e situação cadastral). O resultado fica à parte do regime e aparece no detalhe, para qualquer perfil.
- O CNAE da Receita é o **atual** da empresa, então nunca sobrescreve o regime sozinho: se o regime já tem um CNAE diferente, o detalhe avisa; o administrador pode **aplicar** o CNAE da Receita ao regime (fica no histórico como ajuste manual) e **atualizar** a consulta quando quiser.
- Falha de rede não impede a gravação: a consulta é refeita pelo botão do detalhe. Consultas com menos de 30 dias são reaproveitadas.
- Consulta desligável: `--sem-consulta-cnpj` na CLI ou `MAPEADOR_CONSULTA_CNPJ=0`. Só o CNPJ (dado público) sai da máquina; nenhuma dependência nova.
- Schema 4 (tabela `cnpj_receita`); bancos do schema 3 migram sozinhos.

## 0.8.0
```

**Em `README.md`**, trocar este trecho (único no arquivo, copiado como está):

```markdown
Versão atual: **0.8.0**
```

por:

```markdown
Versão atual: **0.9.0**
```

**Em `README.md`**, trocar este trecho (único no arquivo, copiado como está):

````markdown
## 4. Linha de comando

```bash
````

por:

````markdown
### Consulta do CNPJ (Receita Federal)
Ao **gravar**, o CNPJ de cada regime é consultado na [BrasilAPI](https://brasilapi.com.br/), que devolve o **CNAE principal** e a **situação cadastral** da empresa. O resultado fica na tabela `cnpj_receita`, **à parte do regime**, e aparece no detalhe do regime (aba Consultar) para qualquer perfil.

- O CNAE da Receita é o **atual** da empresa e pode diferir do vigente na data do regime; por isso ele não sobrescreve nada sozinho. Se o regime já tiver um CNAE diferente, o detalhe mostra um aviso de divergência.
- O administrador pode **Consultar CNPJ / Atualizar consulta** pelo detalhe e **Aplicar CNAE da Receita ao regime** (preenche *CNAE REQUERENTE* e *DESCRIÇÃO CNAE*; fica no histórico como ajuste manual e a reimportação não o desfaz).
- Consultas com menos de 30 dias são reaproveitadas. Sem internet, a gravação segue normalmente e a tela (ou a CLI) avisa que a consulta falhou; duas falhas de conexão seguidas interrompem o resto do lote.
- Só o CNPJ (dado público) sai da máquina. Para desligar: `--sem-consulta-cnpj` na CLI ou a variável de ambiente `MAPEADOR_CONSULTA_CNPJ=0`.

## 4. Linha de comando

```bash
````

**Em `README.md`**, trocar este trecho (único no arquivo, copiado como está):

````markdown
                    [--sobrescrever-ajustes]
```
````

por:

````markdown
                    [--sobrescrever-ajustes] [--sem-consulta-cnpj]
```
````

**Em `README.md`**, trocar este trecho (único no arquivo, copiado como está):

```markdown
(por padrão o ajuste é mantido e a CLI avisa) |
```

por:

```markdown
(por padrão o ajuste é mantido e a CLI avisa) |
| `--sem-consulta-cnpj` | não consulta o CNPJ dos regimes na BrasilAPI ao gravar (também desligável com `MAPEADOR_CONSULTA_CNPJ=0`) |
```

**Em `README.md`**, trocar este trecho (único no arquivo, copiado como está):

```markdown
(atual: 3)
```

por:

```markdown
(atual: 4)
```

**Em `README.md`**, trocar este trecho (único no arquivo, copiado como está):

```markdown
| `core/consulta.py` | busca por tipo, lista leve, detalhe, histórico e exportação |
```

por:

```markdown
| `core/consulta.py` | busca por tipo, lista leve, detalhe, histórico e exportação |
| `core/cnpj.py` | consulta do CNPJ na BrasilAPI (CNAE e situação), com reaproveitamento e tolerância a falha de rede |
```

**Em `README.md`**, trocar este trecho (único no arquivo, copiado como está):

```markdown
A suíte tem 357 testes
```

por:

```markdown
A suíte tem 416 testes
```

**Em `README.md`**, trocar este trecho (único no arquivo, copiado como está):

```markdown
  puro no disco (ver [Perfis e senha](#perfis-e-senha-do-administrador)).
```

por:

```markdown
  puro no disco (ver [Perfis e senha](#perfis-e-senha-do-administrador)).
- A consulta de CNPJ depende de internet e de um serviço público de terceiros
  (BrasilAPI), sem garantia de disponibilidade; sem ela, o CNAE da Receita fica
  "não consultado" até uma nova consulta.
```

- [ ] **Step 2: Conferir**

Run: `python -m pytest -q` — Expected: **416 testes passando**, saída limpa.

- [ ] **Step 3: Verificação manual (usuário)**

Estes itens exigem navegador e internet de verdade (o AppTest e os testes usam um `abrir` falso). **Não os
marque como feitos sem executar**; liste no relatório o que ficou pendente para o usuário:

1. Com internet, grave PDFs com regimes: aparece o aviso *Receita Federal: N CNPJ(s) consultado(s)* e, no
   detalhe de um regime (aba Consultar), CNAE principal, situação e data da consulta.
2. Sem internet (modo avião), grave de novo: a gravação conclui e o aviso diz *sem resposta*; com a internet de
   volta, o botão **Consultar CNPJ** do detalhe preenche o bloco.
3. Regime que já tem outro CNAE: o detalhe mostra o aviso de divergência. **Aplicar CNAE da Receita ao regime**
   preenche *CNAE REQUERENTE* e *DESCRIÇÃO CNAE*, o histórico mostra *ajuste manual* e reimportar o PDF não desfaz.
4. Perfil Consulta: vê os dados da Receita, mas nenhum dos dois botões.
5. Visual claro e escuro do bloco *Receita Federal (BrasilAPI)* (rótulo, legenda, aviso, botões).
6. CLI: `python processar.py <pasta>` mostra a linha `Receita:`; com `--sem-consulta-cnpj` não consulta.

- [ ] **Step 4: Commit**

```bash
git add core/versao.py CHANGELOG.md README.md
git commit -m "docs: consulta do CNPJ na BrasilAPI (README, changelog e versão 0.9.0)"
```

(sem `Co-Authored-By`).

---
