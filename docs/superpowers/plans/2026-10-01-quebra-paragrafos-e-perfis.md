# Quebra de parágrafos na Resposta e perfis de acesso — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruir automaticamente os parágrafos do campo Resposta das consultas (a partir da geometria do PDF) e separar o app em perfis Consulta (livre) e Administrador (senha), onde só o Administrador importa PDFs.

**Architecture:** Uma função nova em `core/pdf_text.py` lê as linhas do PDF com coordenadas e prefixa com um marcador (`\u2029`) cada linha que abre um parágrafo; o parser de consultas ganha um parâmetro opcional com esse texto e monta só a Resposta com `\n\n` entre parágrafos (com fallback para o texto achatado). A tela e a planilha passam a exibir esses parágrafos. Um módulo novo `core/acesso.py` guarda a lógica de senha/perfil e o `app.py` ganha uma tela inicial que bloqueia o resto até um perfil ser escolhido.

**Tech Stack:** Python 3.10+, pdfplumber (`extract_text_lines`), Streamlit (`AppTest` nos testes), openpyxl, pytest, SQLite.

**Spec:** `docs/superpowers/specs/2026-10-01-quebra-paragrafos-e-perfis-design.md`

## Global Constraints

- Mudança **só no campo Resposta das consultas**. `texto_simples`, `texto_por_colunas`, `detecta_fonte`, `parsers/regimes.py` e todo o ramo de regimes do `pipeline.py` ficam **sem nenhuma alteração**.
- Súmula, Problema da Consulta, CNAE Detectado e Protocolo continuam saindo do texto de `texto_simples`, byte a byte iguais aos de hoje.
- Sem mudança de schema no banco (`mapeamento.db`).
- Baseline antes de qualquer tarefa: `python -m pytest -q` → **136 passed**. Os testes existentes devem continuar passando; a única exceção permitida são os de `tests/test_app.py`, que passam a entrar como Administrador (Tarefa 5).
- Marcador de parágrafo: `MARCA_PARAGRAFO = "\u2029"`, definido uma vez em `core/pdf_text.py` e importado de lá.
- Limiares de parágrafo derivam da página (margem do corpo e espaçamento mediano), com apenas estes parâmetros fixos: recuo mínimo `10` pt, fator de salto `1.4`, teto de espaçamento considerado `30` pt.
- Senha só em `.streamlit/secrets.toml` (`[admin]` / `senha`), comparada com `hmac.compare_digest`. Arquivo, chave ou valor ausente/vazio/não-texto ⇒ Administrador **desabilitado** (nunca acesso aberto).
- Valores de perfil em `st.session_state["perfil"]`: `"consulta"` ou `"admin"`.
- Resposta exibida na tela: parágrafos separados em `\n\n`, cada um como `<p class="icms-resposta-paragrafo">` com o texto **escapado** (`html.escape`).
- `wrap_text=True` na planilha **apenas** na coluna Resposta das consultas.
- O projeto **não é um repositório git**: onde o modelo de plano diria "commit", cada tarefa termina com um **checkpoint** (suíte completa verde). Não rodar comandos `git`.
- Texto da interface em português do Brasil.

## Review Focus

Entradas que o spec implica mas que nenhum caminho feliz exercita; cada uma tem teste na tarefa indicada.

1. **Parágrafo que atravessa a quebra de página** (rodapé + cabeçalho no meio) deve continuar **um** parágrafo, e o primeiro parágrafo depois do cabeçalho não pode ser quebrado só por causa do salto vertical — Tarefas 1 e 2.
2. **Página vazia, sem linhas, ou só com cabeçalho/rodapé** não pode levantar exceção em `texto_com_paragrafos` — Tarefa 1.
3. **Texto da Resposta com cara de HTML/Markdown** (`<script>`, `a)`, `1.`, `*`, `$`, `&`) deve aparecer literalmente, nunca virar lista nem tag — Tarefa 3.
4. **Divergência entre os dois textos** (âncora ausente, ambígua, data diferente, conteúdo diferente) ⇒ Resposta achatada como hoje, nunca texto errado ou perdido — Tarefa 2.
5. **Senha atípica**: vazia, só espaços, acentuada, valor não-texto no TOML (`senha = 1234`), seção `[admin]` ausente ⇒ nunca autentica sem senha configurada; senha com acento autentica corretamente — Tarefa 4.
6. **Reimportar um PDF já mapeado** (registro antigo achatado no banco) atualiza a Resposta para a versão com parágrafos sem duplicar — Tarefa 2.

---

## Execução com sub-agents

Os arquivos de cada tarefa são disjuntos dentro de cada onda, então tarefas da mesma onda podem rodar em **paralelo** (uma chamada `Agent` por tarefa, todas na mesma mensagem). Sem git, não há worktree: os agentes trabalham no mesmo diretório, por isso **nunca** coloque na mesma onda duas tarefas que editem o mesmo arquivo.

| Onda | Tarefas (paralelas entre si) | Depende de | Arquivos tocados |
|---|---|---|---|
| A | **1** (extração) · **4** (acesso) | — | `core/pdf_text.py`, `tests/test_pdf_text.py` · `core/acesso.py`, `tests/test_acesso.py` |
| B | **2** (parser + pipeline) · **3** (planilha + detalhe na tela) | 2 ← 1 · 3 ← — | `parsers/consultas.py`, `core/pipeline.py`, testes · `core/planilha.py`, `app.py`, testes |
| C | **5** (tela inicial e perfis) | 3, 4 (ambas mexem em `app.py`/dependem de `acesso`) | `app.py`, `tests/test_app.py`, `.gitignore`, `.streamlit/secrets.toml.example` |
| D | **6** (docs + verificação final) | todas | `README.md`, verificação |

**Como despachar cada tarefa** (`Agent`, `subagent_type: general-purpose`): o prompt deve conter o caminho deste plano, o caminho do spec e a frase *"Implemente apenas a Tarefa N, na ordem dos passos, sem tocar em arquivos fora da lista da tarefa. Ao final, rode a suíte completa e relate o resultado literal."* Ao fim de cada onda, despache **um revisor** (agente novo, só leitura) que confere o diff das tarefas da onda contra o spec e as Global Constraints antes de abrir a onda seguinte. Após a Tarefa 6, um revisor final olha o conjunto.

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `core/pdf_text.py` | modificar (só acrescentar) | `MARCA_PARAGRAFO`, `_marca_paragrafos_da_pagina`, `texto_com_paragrafos` |
| `parsers/consultas.py` | modificar | `parse(texto, texto_paragrafos=None)`; Resposta com parágrafos + salvaguarda |
| `core/pipeline.py` | modificar (1 linha, ramo de consultas) | passa o texto com parágrafos ao parser |
| `core/planilha.py` | modificar | `wrap_text` e largura só na coluna Resposta das consultas |
| `core/acesso.py` | criar | senha do admin, comparação, perfis, `exige_admin` |
| `app.py` | modificar | `_resposta_em_paragrafos`, CSS do parágrafo, tela inicial, abas por perfil, guarda em `_processar` |
| `.gitignore`, `.streamlit/secrets.toml.example` | modificar / criar | liberar o exemplo de segredo |
| `README.md` | modificar | perfis, senha, limites, parágrafos, reimportação |
| `tests/test_pdf_text.py`, `tests/test_consultas.py`, `tests/test_pipeline.py`, `tests/test_planilha.py`, `tests/test_acesso.py` (novo), `tests/test_app.py` | modificar / criar | cobertura de cada tarefa |

---

### Task 1: `texto_com_paragrafos` (extração com marcadores de parágrafo)

**Files:**
- Modify: `core/pdf_text.py` (acrescentar no fim do arquivo; **não alterar** nenhuma função existente)
- Test: `tests/test_pdf_text.py` (acrescentar no fim)

**Interfaces:**
- Consumes: `pdfplumber` (`page.extract_text_lines()` devolve dicts com `text`, `x0`, `top`), `_limpa_ruido_ocr` (já existe no módulo).
- Produces:
  - `MARCA_PARAGRAFO: str = "\u2029"`
  - `_marca_paragrafos_da_pagina(linhas: list[dict]) -> list[str]` — uma string por linha de entrada, prefixada com `MARCA_PARAGRAFO` quando a linha abre parágrafo.
  - `texto_com_paragrafos(caminho_pdf: str) -> str` — mesmo texto de `texto_simples`, com `MARCA_PARAGRAFO` no início das linhas que abrem parágrafo. **Invariante:** `texto_com_paragrafos(p).replace(MARCA_PARAGRAFO, "") == texto_simples(p)`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_pdf_text.py` (conferir os imports `os` e `pdf_text` já presentes no arquivo; se faltar algum, adicioná-lo no topo):

```python
# --- texto_com_paragrafos --------------------------------------------------
M = pdf_text.MARCA_PARAGRAFO
_PDF_CONSULTAS = os.path.join(os.path.dirname(__file__), "fixtures",
                              "Consultas_1_a_3_de_2026.pdf")


def _l(texto, x0, top):
    return {'text': texto, 'x0': x0, 'top': top}


def test_recuo_de_primeira_linha_abre_paragrafo():
    linhas = [_l('abertura', 108, 100), _l('cont 1', 36, 112.8),
              _l('cont 2', 36, 125.6), _l('outro', 108, 147.4),
              _l('cont 3', 36, 160.2), _l('cont 4', 36, 173.0)]
    assert pdf_text._marca_paragrafos_da_pagina(linhas) == [
        M + 'abertura', 'cont 1', 'cont 2', M + 'outro', 'cont 3', 'cont 4']


def test_salto_vertical_abre_paragrafo_mesmo_sem_recuo():
    linhas = [_l('a', 36, 100), _l('b', 36, 112.8), _l('c', 36, 125.6),
              _l('d', 36, 147.4), _l('e', 36, 160.2)]
    assert pdf_text._marca_paragrafos_da_pagina(linhas) == [
        'a', 'b', 'c', M + 'd', 'e']


def test_ruido_de_pagina_nunca_e_marcado_e_nao_gera_salto():
    linhas = [_l('SECRETARIA DE ESTADO DA FAZENDA DO PARANÁ - SEFA', 138, 37),
              _l('SETOR CONSULTIVO', 240, 61),
              _l('__________', 159, 84),
              _l('continua o paragrafo da pagina anterior', 36, 145),
              _l('segunda linha', 36, 157.8),
              _l('terceira linha', 36, 170.6)]
    saida = pdf_text._marca_paragrafos_da_pagina(linhas)
    assert M not in "".join(saida)


def test_pagina_sem_linhas_ou_so_com_ruido_nao_quebra():
    assert pdf_text._marca_paragrafos_da_pagina([]) == []
    so_ruido = [_l('__________', 36, 10), _l('3', 36, 20)]
    assert pdf_text._marca_paragrafos_da_pagina(so_ruido) == ['__________', '3']


def test_empate_de_margem_escolhe_a_menor():
    # 2 linhas a 108 e 2 a 36: a margem do corpo é 36, não 108
    linhas = [_l('a', 108, 100), _l('b', 36, 112.8),
              _l('c', 108, 134.6), _l('d', 36, 147.4)]
    assert pdf_text._marca_paragrafos_da_pagina(linhas) == [
        M + 'a', 'b', M + 'c', 'd']


def test_texto_com_paragrafos_so_acrescenta_marcas():
    com = pdf_text.texto_com_paragrafos(_PDF_CONSULTAS)
    assert M in com
    assert com.replace(M, "") == pdf_text.texto_simples(_PDF_CONSULTAS)


def test_paragrafos_da_resposta_da_consulta_001():
    com = pdf_text.texto_com_paragrafos(_PDF_CONSULTAS)
    assert M + 'Cabe transcrever' in com
    assert M + 'Art. 1' in com
    assert M + 'a) o in' in com
    assert M + 'II - a receita' in com
    # a frase que recomeça logo após o cabeçalho da página seguinte continua
    # o parágrafo anterior: está no texto, mas NÃO abre parágrafo
    assert 'do "caput", os estabelecimentos industriais' in com
    assert M + 'do "caput", os estabelecimentos industriais' not in com
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_pdf_text.py -q`
Expected: FAIL com `AttributeError: module 'core.pdf_text' has no attribute 'MARCA_PARAGRAFO'`.

- [ ] **Step 3: Implementar**

Em `core/pdf_text.py`, acrescentar `import statistics` e `from collections import Counter` junto aos imports do topo (sem remover nenhum) e, **no fim do arquivo**, acrescentar:

```python
# Marcador de início de parágrafo (U+2029, "separador de parágrafo").
# Prefixa a linha que abre um parágrafo. Não é uma linha em branco porque a
# limpeza de cabeçalho/rodapé do parser deixa linhas em branco no MEIO de
# parágrafos que atravessam a página; o marcador não tem essa ambiguidade.
# Removendo-o, o texto é idêntico ao de texto_simples().
MARCA_PARAGRAFO = "\u2029"

# Linhas que se repetem em toda página e que o parser descarta: traços,
# número de página (1-2 dígitos) e o cabeçalho "SECRETARIA ... / SETOR
# CONSULTIVO". Nunca abrem parágrafo e interrompem a referência de salto.
_RUIDO_DE_PAGINA = re.compile(
    r'^(?:_+|\d{1,2}|SECRETARIA DE ESTADO DA FAZENDA.*|SETOR CONSULTIVO)$',
    re.IGNORECASE,
)
_RECUO_MINIMO = 10          # pt acima da margem do corpo = recuo de 1ª linha
_FATOR_SALTO = 1.4          # salto > 1,4x o espaçamento mediano = novo parágrafo
_TETO_ESPACAMENTO = 30      # pt; saltos maiores não entram na mediana


def _marca_paragrafos_da_pagina(linhas: list[dict]) -> list[str]:
    """Devolve o texto de cada linha, prefixado com MARCA_PARAGRAFO quando a
    linha abre um parágrafo: recuo de primeira linha em relação à margem do
    corpo, ou salto vertical maior que o espaçamento normal da página.

    A margem do corpo é o x0 mais comum da página (empate: o menor), e o
    espaçamento normal é a mediana dos intervalos entre linhas do corpo —
    ambos derivados da própria página, não valores fixos.
    """
    corpo = [l for l in linhas if not _RUIDO_DE_PAGINA.match(l['text'].strip())]
    if not corpo:
        return [l['text'] for l in linhas]

    contagem = Counter(round(l['x0']) for l in corpo)
    maior = max(contagem.values())
    margem = min(x for x, n in contagem.items() if n == maior)
    intervalos = [b['top'] - a['top'] for a, b in zip(corpo, corpo[1:])
                  if 0 < b['top'] - a['top'] < _TETO_ESPACAMENTO]
    normal = statistics.median(intervalos) if intervalos else None

    saida, anterior = [], None
    for linha in linhas:
        if _RUIDO_DE_PAGINA.match(linha['text'].strip()):
            saida.append(linha['text'])
            anterior = None
            continue
        abre = linha['x0'] > margem + _RECUO_MINIMO
        if (not abre and anterior is not None and normal is not None
                and linha['top'] - anterior['top'] > normal * _FATOR_SALTO):
            abre = True
        saida.append((MARCA_PARAGRAFO if abre else '') + linha['text'])
        anterior = linha
    return saida


def texto_com_paragrafos(caminho_pdf: str) -> str:
    """Como texto_simples(), mas com MARCA_PARAGRAFO no início das linhas que
    abrem parágrafo (ver _marca_paragrafos_da_pagina). Usado só para o campo
    Resposta das consultas; o resto do parser segue lendo texto_simples()."""
    paginas = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            paginas.append("\n".join(
                _marca_paragrafos_da_pagina(pagina.extract_text_lines())))
    return _limpa_ruido_ocr("\n".join(paginas))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_pdf_text.py -q`
Expected: PASS (todos, incluindo os já existentes).

Se `test_texto_com_paragrafos_so_acrescenta_marcas` falhar, **não ajuste o teste**: a invariante é a garantia do design. Compare `texto_com_paragrafos(...).replace(M, "")` com `texto_simples(...)` linha a linha, ache a diferença (provavelmente `extract_text_lines` vs `extract_text` em espaços/ordem) e corrija a função, reportando o achado.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: todos passam (136 + os novos), nenhum teste existente alterado.

---

### Task 2: Parser da Resposta com parágrafos + pipeline

**Files:**
- Modify: `parsers/consultas.py` (acrescentar funções; alterar `parse` apenas conforme abaixo)
- Modify: `core/pipeline.py:55` (somente a linha do ramo de consultas)
- Test: `tests/test_consultas.py`, `tests/test_pipeline.py` (acrescentar)

**Interfaces:**
- Consumes (Tarefa 1): `core.pdf_text.MARCA_PARAGRAFO`, `core.pdf_text.texto_com_paragrafos(caminho) -> str`.
- Produces:
  - `parsers.consultas.parse(texto: str, texto_paragrafos: str | None = None) -> list[dict]` — mesma lista de dicts de hoje; só `'Resposta'` pode conter `\n\n`.
  - `_extrai_resposta_em_paragrafos(fatia_p: str) -> str`
  - `_fatias_por_consulta(texto_paragrafos: str) -> dict[tuple[str, str], str]` — chave `(número com 3 dígitos, data ISO)`; chaves repetidas são descartadas.
  - `_resposta_com_paragrafos(plana: str, fatia_p: str | None) -> str`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_consultas.py`:

```python
# --- Resposta com parágrafos ----------------------------------------------
from core.pdf_text import MARCA_PARAGRAFO as M  # noqa: E402

_CAB = "CONSULTA Nº 001, de 19 de janeiro de 2026.\nSÚMULA: ICMS. TESTE.\nA consulente expõe.\nRESPOSTA\n"
_RODAPE_E_CABECALHO = ("__________\n1\nSECRETARIA DE ESTADO DA FAZENDA DO PARANÁ - SEFA\n"
                       "SETOR CONSULTIVO\n__________\n")


def test_resposta_sai_com_paragrafos_separados_por_linha_em_branco():
    plano = _CAB + "Primeiro paragrafo linha um\nlinha dois.\nSegundo paragrafo.\n"
    com = _CAB + M + "Primeiro paragrafo linha um\nlinha dois.\n" + M + "Segundo paragrafo.\n"
    r = consultas.parse(plano, com)[0]
    assert r["Resposta"] == "Primeiro paragrafo linha um linha dois.\n\nSegundo paragrafo."


def test_paragrafo_que_atravessa_a_pagina_continua_um_so():
    corpo_plano = "Primeiro começa\n" + _RODAPE_E_CABECALHO + "continua aqui.\nSegundo.\n"
    corpo_com = M + "Primeiro começa\n" + _RODAPE_E_CABECALHO + "continua aqui.\n" + M + "Segundo.\n"
    r = consultas.parse(_CAB + corpo_plano, _CAB + corpo_com)[0]
    assert r["Resposta"] == "Primeiro começa continua aqui.\n\nSegundo."


def test_sem_texto_com_paragrafos_a_resposta_sai_achatada_como_antes():
    plano = _CAB + "Um.\nDois.\n"
    assert consultas.parse(plano)[0]["Resposta"] == "Um. Dois."
    assert consultas.parse(plano, None)[0]["Resposta"] == "Um. Dois."
    assert consultas.parse(plano, "")[0]["Resposta"] == "Um. Dois."


def test_texto_com_paragrafos_divergente_cai_no_achatado():
    plano = _CAB + "Um.\nDois.\n"
    # conteúdo diferente (falta uma palavra): a salvaguarda recusa
    assert consultas.parse(plano, _CAB + M + "Um.\n" + M + "Tres.\n")[0]["Resposta"] == "Um. Dois."
    # âncora com outra data: não casa, cai no achatado
    outra = _CAB.replace("19 de janeiro", "20 de janeiro") + M + "Um.\n" + M + "Dois.\n"
    assert consultas.parse(plano, outra)[0]["Resposta"] == "Um. Dois."


def test_ancora_repetida_no_texto_com_paragrafos_cai_no_achatado():
    plano = _CAB + "Um.\nDois.\n"
    duplicada = (_CAB + M + "Um.\n" + M + "Dois.\n") * 2
    assert consultas.parse(plano, duplicada)[0]["Resposta"] == "Um. Dois."


def test_resposta_vazia_continua_vazia_com_texto_de_paragrafos():
    plano = "CONSULTA Nº 001, de 19 de janeiro de 2026.\nSÚMULA: X.\nA consulente expõe.\n"
    assert consultas.parse(plano, plano)[0]["Resposta"] == ""


def test_fixture_real_so_a_resposta_muda_e_sem_perder_texto():
    pdf = os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf")
    base = consultas.parse(pdf_text.texto_simples(pdf))
    novo = consultas.parse(pdf_text.texto_simples(pdf), pdf_text.texto_com_paragrafos(pdf))
    assert len(novo) == len(base) == 3
    for b, n in zip(base, novo):
        assert {k: v for k, v in n.items() if k != "Resposta"} == \
               {k: v for k, v in b.items() if k != "Resposta"}
        assert " ".join(n["Resposta"].split()) == b["Resposta"]
    assert "\n\n" in novo[0]["Resposta"]
    assert "\n\n" in novo[1]["Resposta"]
    assert "\n\nCabe transcrever" in novo[0]["Resposta"]
```

Acrescentar ao fim de `tests/test_pipeline.py` (conferir/ajustar imports `os`, `pipeline`, `pdf_text`, `armazenamento`, `consulta` conforme o arquivo):

```python
# --- Resposta com parágrafos no pipeline ----------------------------------
def test_pipeline_entrega_resposta_com_paragrafos_e_demais_campos_iguais():
    import os
    from core import pdf_text
    from parsers import consultas as p_consultas
    pdf = os.path.join(os.path.dirname(__file__), "fixtures", "Consultas_1_a_3_de_2026.pdf")
    lote = pipeline.Lote()
    pipeline.processar_arquivo(lote, pdf, "c.pdf")
    base = p_consultas.parse(pdf_text.texto_simples(pdf))
    assert len(lote.consultas) == len(base) == 3
    assert "\n\n" in lote.consultas[0]["Resposta"]
    for b, n in zip(base, lote.consultas):
        assert {k: v for k, v in n.items() if k != "Resposta"} == \
               {k: v for k, v in b.items() if k != "Resposta"}


def test_pipeline_de_regime_nao_foi_tocado():
    import os
    from core import pdf_text
    from parsers import regimes as p_regimes
    pdf = os.path.join(os.path.dirname(__file__), "fixtures", "Regime_Krona_2col.pdf")
    lote = pipeline.Lote()
    pipeline.processar_arquivo(lote, pdf, "r.pdf")
    esperado, _ = p_regimes.parse(pdf_text.texto_por_colunas(pdf))
    assert lote.regimes == esperado


def test_reimportar_pdf_atualiza_resposta_achatada_do_banco_sem_duplicar(tmp_path):
    import os
    from core import armazenamento, consulta
    pdf = os.path.join(os.path.dirname(__file__), "fixtures", "Consultas_1_a_3_de_2026.pdf")
    conn = armazenamento.conectar(str(tmp_path / "t.db"))
    armazenamento.criar_esquema(conn)
    # registro antigo, achatado, com a mesma chave natural (Ano + Nº)
    armazenamento.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
         'Protocolo': '', 'Súmula': 'velha', 'Problema da Consulta': '',
         'CNAE Detectado': '', 'Resposta': 'antiga achatada'}])
    for _ in range(2):  # duas vezes: também prova idempotência
        lote = pipeline.Lote()
        pipeline.processar_arquivo(lote, pdf, "c.pdf")
        pipeline.finalizar(lote)
        armazenamento.persistir_lote(conn, lote)
    achados = consulta.buscar(conn, "consulta")
    assert len(achados) == 3
    r001 = next(r for r in achados if r["Nº da Consulta"] == "001")
    assert "\n\n" in r001["Resposta"]
    assert r001["Resposta"] != "antiga achatada"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_consultas.py tests/test_pipeline.py -q`
Expected: FAIL (`parse() takes 1 positional argument but 2 were given`).

- [ ] **Step 3: Implementar o parser**

Em `parsers/consultas.py`:

1. No topo, junto aos imports: `from core.pdf_text import MARCA_PARAGRAFO`.
2. Logo **abaixo** de `_extrai_resposta` (sem alterá-la), acrescentar:

```python
def _extrai_resposta_em_paragrafos(fatia_p: str) -> str:
    """Como _extrai_resposta(), mas parte da fatia do texto com
    MARCA_PARAGRAFO: junta as linhas de cada parágrafo com espaço e separa os
    parágrafos com linha em branco ("\\n\\n")."""
    m = re.search(r'\bRESPOSTA\b', fatia_p)
    if not m:
        return ""
    resto = fatia_p[m.end():]
    m_protocolo = _PROTOCOLO_DA_PROXIMA.search(resto)
    fim = m_protocolo.start() if m_protocolo else len(resto)
    paragrafos = (re.sub(r'\s+', ' ', p).strip()
                  for p in resto[:fim].split(MARCA_PARAGRAFO))
    return '\n\n'.join(p for p in paragrafos if p)


def _fatias_por_consulta(texto_paragrafos: str) -> dict:
    """Fatia o texto com marcadores pelas mesmas âncoras de parse() e indexa
    por (número, data ISO). Chave repetida é descartada: sem como saber qual
    fatia é de qual consulta, vale o texto achatado."""
    limpo = _CABECALHO.sub('\n', texto_paragrafos)
    ancoras = list(_ANCORA.finditer(limpo))
    fatias, repetidas = {}, set()
    for i, anc in enumerate(ancoras):
        fim = ancoras[i + 1].start() if i + 1 < len(ancoras) else len(limpo)
        chave = (anc.group(1).zfill(3), _data_extenso_para_iso(anc.group(2)))
        if chave in fatias:
            repetidas.add(chave)
        fatias[chave] = limpo[anc.start():fim]
    for chave in repetidas:
        del fatias[chave]
    return fatias


def _resposta_com_paragrafos(plana: str, fatia_p) -> str:
    """Troca a Resposta achatada pela versão com parágrafos só se ela tiver
    EXATAMENTE o mesmo texto (normalizada): parágrafos só acrescentam quebras,
    nunca alteram conteúdo. Qualquer divergência cai no achatado."""
    if fatia_p is None:
        return plana
    com = _extrai_resposta_em_paragrafos(fatia_p)
    return com if ' '.join(com.split()) == plana else plana
```

3. Alterar a assinatura `def parse(texto: str) -> list[dict]:` para `def parse(texto: str, texto_paragrafos: str | None = None) -> list[dict]:`; logo depois de `ano_doc = ...` acrescentar `fatias_p = _fatias_por_consulta(texto_paragrafos) if texto_paragrafos else {}`; e trocar a linha `'Resposta': _extrai_resposta(fatia),` por `'Resposta': _resposta_com_paragrafos(_extrai_resposta(fatia), fatias_p.get((numero, data_iso))),`.

- [ ] **Step 4: Ligar no pipeline**

Em `core/pipeline.py`, trocar **somente** a linha 55:

```python
            regs = p_consultas.parse(pdf_text.texto_simples(caminho),
                                     pdf_text.texto_com_paragrafos(caminho))
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_consultas.py tests/test_pipeline.py -q`
Expected: PASS.

- [ ] **Step 6: Checkpoint**

Run: `python -m pytest -q`
Expected: todos passam. Conferir com `python -m pytest tests/test_regimes.py -q` que os testes de regime seguem verdes sem edição.

---

### Task 3: Exibição da Resposta em parágrafos (tela) e `wrap_text` (planilha)

**Files:**
- Modify: `core/planilha.py`
- Modify: `app.py` (import `html`; função nova `_resposta_em_paragrafos`; ramo em `_mostra_detalhe`; uma regra CSS no bloco `<style>` injetado, dentro do f-string — **chaves duplicadas `{{ }}`**)
- Test: `tests/test_planilha.py`, `tests/test_app.py` (acrescentar)

**Interfaces:**
- Consumes: formato da Resposta da Tarefa 2 (`\n\n` entre parágrafos). Não depende do código da Tarefa 2.
- Produces:
  - `core.planilha.COLUNAS_COM_QUEBRA = {'Resposta'}`; `_escreve_aba(ws, cols, linhas, colunas_quebra=())`.
  - `app._resposta_em_paragrafos(texto: str) -> str` (HTML com um `<p class="icms-resposta-paragrafo">` por parágrafo, texto escapado, tudo numa linha só, sem `\n`).

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_planilha.py`:

```python
def test_resposta_das_consultas_tem_wrap_text_e_coluna_larga_demais_colunas_nao():
    consultas = [{'Ano': '2026', 'Nº da Consulta': '001', 'Súmula': 'ICMS.',
                  'Resposta': 'Primeiro.\n\nSegundo.'}]
    regimes = [{'ANO': '2026', 'EMENTA': 'x\n\ny'}]
    with tempfile.TemporaryDirectory() as d:
        saida = os.path.join(d, "out.xlsx")
        planilha.gerar_xlsx(saida, consultas, regimes, [])
        wb = load_workbook(saida)
        ws = wb["Consultas — a revisar"]
        col = planilha.COLS_CONSULTAS.index('Resposta') + 1
        assert ws.cell(row=2, column=col).value == 'Primeiro.\n\nSegundo.'
        assert ws.cell(row=2, column=col).alignment.wrap_text is True
        letra = ws.cell(row=1, column=col).column_letter
        assert ws.column_dimensions[letra].width >= 60
        sumula = planilha.COLS_CONSULTAS.index('Súmula') + 1
        assert not ws.cell(row=2, column=sumula).alignment.wrap_text
        wr = wb["Regimes — a revisar"]
        assert not any(c.alignment.wrap_text for linha in wr.iter_rows(min_row=2) for c in linha)
```

Acrescentar ao fim de `tests/test_app.py` (reaproveitando a fixture `_isola_banco` e o padrão dos testes de modal; **nesta tarefa o app ainda não tem tela inicial**, então `AppTest.from_file(APP).run(...)` funciona direto):

```python
def test_resposta_do_modal_vira_um_p_por_paragrafo_com_texto_escapado():
    from core import armazenamento as arm
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS.', 'Problema da Consulta': 'p',
         'CNAE Detectado': '',
         'Resposta': 'a) primeiro item\n\n1. segundo <b>item</b> & $x$\n\n* terceiro'},
    ])
    at = AppTest.from_file(APP).run(timeout=30)
    at.tabs[1].selectbox[0].set_value("consulta").run(timeout=30)
    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}
    at.run(timeout=30)
    assert not at.exception
    campo = next(m.value for m in at.markdown if "icms-resposta-paragrafo" in m.value)
    assert campo.count('<p class="icms-resposta-paragrafo">') == 3
    assert '<p class="icms-resposta-paragrafo">a) primeiro item</p>' in campo
    assert '1. segundo &lt;b&gt;item&lt;/b&gt; &amp; $x$' in campo
    assert '<b>item</b>' not in campo
    assert '\n' not in campo   # uma linha só: sem linha em branco que encerre o bloco HTML


def test_resposta_antiga_sem_quebras_aparece_como_um_paragrafo():
    from core import armazenamento as arm
    conn = arm.conectar(os.environ["MAPEADOR_BANCO"])
    arm.criar_esquema(conn)
    arm.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '002', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS.', 'Problema da Consulta': '',
         'CNAE Detectado': '', 'Resposta': 'texto achatado antigo'}])
    at = AppTest.from_file(APP).run(timeout=30)
    at.tabs[1].selectbox[0].set_value("consulta").run(timeout=30)
    at.session_state["tabela-resultados"] = {"selection": {"rows": [0], "columns": []}}
    at.run(timeout=30)
    campo = next(m.value for m in at.markdown if "texto achatado antigo" in m.value)
    assert campo.count('<p class="icms-resposta-paragrafo">') == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_planilha.py tests/test_app.py -q`
Expected: os 3 testes novos FALHAM; os demais passam.

- [ ] **Step 3: Implementar a planilha**

Em `core/planilha.py`:

```python
COLUNAS_COM_QUEBRA = {'Resposta'}
_LARGURA_COLUNA_QUEBRA = 80
```

Alterar `_escreve_aba(ws, cols, linhas)` para `_escreve_aba(ws, cols, linhas, colunas_quebra=())`. No laço de células, depois de criar `cell`: `if campo in colunas_quebra: cell.alignment = Alignment(wrap_text=True, vertical='top')`. No laço de larguras, `ws.column_dimensions[letra].width = _LARGURA_COLUNA_QUEBRA if col in colunas_quebra else min(max(len(col) + 2, 14), 55)`. Na chamada da aba de consultas em `gerar_xlsx`, passar `colunas_quebra=COLUNAS_COM_QUEBRA`. As demais abas **não** passam o argumento.

- [ ] **Step 4: Implementar a tela**

Em `app.py`:
1. `import html` junto aos imports da biblioteca padrão.
2. Antes de `_mostra_detalhe`, acrescentar:

```python
def _resposta_em_paragrafos(texto: str) -> str:
    """Resposta da consulta como HTML: um <p> por parágrafo ("\\n\\n"), com o
    texto escapado — assim "a)", "1." ou "*" no início de um parágrafo não
    viram lista em Markdown e "<" ou "&" aparecem literalmente. Tudo numa
    linha só: uma linha em branco encerraria o bloco HTML no Markdown."""
    paragrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    return "".join(
        f'<p class="icms-resposta-paragrafo">{html.escape(p)}</p>'
        for p in paragrafos
    )
```

3. Em `_mostra_detalhe`, trocar o `if tipo == "regime": ... else:` por:

```python
        if tipo == "regime":
            st.markdown(_com_quebras_por_topico(valor))
        elif tipo == "consulta" and campo == "Resposta":
            st.markdown(_resposta_em_paragrafos(valor), unsafe_allow_html=True)
        else:
            st.write(valor)
```

4. No bloco `<style>` do f-string (antes do `</style>`), acrescentar (chaves duplicadas):

```css
.icms-resposta-paragrafo {{
    margin: 0 0 0.9em 0;
    line-height: 1.55;
    text-align: justify;
}}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_planilha.py tests/test_app.py -q`
Expected: PASS.

- [ ] **Step 6: Checkpoint**

Run: `python -m pytest -q`
Expected: todos passam.

---

### Task 4: `core/acesso.py` (senha e perfis)

**Files:**
- Create: `core/acesso.py`
- Test: `tests/test_acesso.py` (novo)

**Interfaces:**
- Consumes: nada (módulo puro, **sem importar streamlit**).
- Produces:
  - `PERFIL_CONSULTA = "consulta"`, `PERFIL_ADMIN = "admin"`
  - `senha_admin(secrets) -> str | None` — `secrets` é qualquer objeto com `secrets["admin"]["senha"]` (o `st.secrets` ou um dict). `None` se ausente, vazia/só espaços ou não for `str`. Qualquer exceção ao ler (inclusive `st.secrets` sem arquivo) ⇒ `None` (falha fechada).
  - `confere(digitada: str | None, esperada: str | None) -> bool` — `False` se algum dos dois for vazio/`None`; senão `hmac.compare_digest` sobre UTF-8.
  - `exige_admin(perfil) -> None` — levanta `PermissionError` se `perfil != PERFIL_ADMIN`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_acesso.py`:

```python
import pytest

from core import acesso


def test_senha_admin_le_do_mapeamento():
    assert acesso.senha_admin({"admin": {"senha": "segredo"}}) == "segredo"


@pytest.mark.parametrize("secrets", [
    {}, {"admin": {}}, {"admin": {"senha": ""}}, {"admin": {"senha": "   "}},
    {"admin": {"senha": 1234}}, {"admin": "texto"}, {"admin": None}, None,
])
def test_senha_ausente_vazia_ou_nao_texto_e_none(secrets):
    assert acesso.senha_admin(secrets) is None


def test_erro_ao_ler_secrets_e_none_nunca_acesso_aberto():
    class SemArquivo:
        def __getitem__(self, chave):
            raise FileNotFoundError("No secrets found")
    assert acesso.senha_admin(SemArquivo()) is None


def test_confere_senha_correta_e_errada():
    assert acesso.confere("segredo", "segredo") is True
    assert acesso.confere("errada", "segredo") is False
    assert acesso.confere("Segredo", "segredo") is False


def test_confere_aceita_acentos():
    assert acesso.confere("sênha-çãõ", "sênha-çãõ") is True
    assert acesso.confere("senha-cao", "sênha-çãõ") is False


@pytest.mark.parametrize("digitada,esperada", [
    ("", "segredo"), (None, "segredo"), ("segredo", None), ("segredo", ""),
    ("", ""), (None, None),
])
def test_confere_nunca_autentica_com_vazio_ou_sem_senha_configurada(digitada, esperada):
    assert acesso.confere(digitada, esperada) is False


def test_exige_admin():
    acesso.exige_admin(acesso.PERFIL_ADMIN)
    for perfil in (acesso.PERFIL_CONSULTA, None, "", "ADMIN", "qualquer"):
        with pytest.raises(PermissionError):
            acesso.exige_admin(perfil)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_acesso.py -q`
Expected: FAIL (`ImportError: cannot import name 'acesso'`).

- [ ] **Step 3: Implementar**

`core/acesso.py`:

```python
# core/acesso.py
"""Perfis de uso da interface e a senha do Administrador.

Sem dependência de streamlit: quem chama passa o `st.secrets` (ou um dict).
A senha fica em .streamlit/secrets.toml, seção [admin], chave `senha`. É
texto puro no disco: protege contra uso acidental da interface, não contra
quem tem acesso ao arquivo.
"""
import hmac

PERFIL_CONSULTA = "consulta"
PERFIL_ADMIN = "admin"


def senha_admin(secrets) -> str | None:
    """Senha configurada do Administrador, ou None se não houver uma válida.

    Falha fechada: qualquer problema ao ler (arquivo inexistente, seção
    ausente, valor vazio ou que não seja texto) vira None, e None desabilita
    o perfil Administrador — nunca vira acesso aberto. O `except Exception`
    é proposital pelo mesmo motivo: o st.secrets levanta tipos de erro
    diferentes conforme a versão e o estado do arquivo.
    """
    try:
        valor = secrets["admin"]["senha"]
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(valor, str) or not valor.strip():
        return None
    return valor


def confere(digitada: str | None, esperada: str | None) -> bool:
    if not digitada or not esperada:
        return False
    return hmac.compare_digest(digitada.encode("utf-8"), esperada.encode("utf-8"))


def exige_admin(perfil) -> None:
    if perfil != PERFIL_ADMIN:
        raise PermissionError("Ação restrita ao perfil Administrador.")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_acesso.py -q`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: todos passam.

---

### Task 5: Tela inicial, abas por perfil e guarda do processamento

**Files:**
- Modify: `app.py`
- Modify: `.gitignore`
- Create: `.streamlit/secrets.toml.example`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes (Tarefa 4): `core.acesso` — `PERFIL_CONSULTA`, `PERFIL_ADMIN`, `senha_admin(secrets)`, `confere(digitada, esperada)`, `exige_admin(perfil)`.
- Produces: `st.session_state["perfil"]` ∈ `{"consulta","admin"}`; widgets com chaves estáveis `entrar-consulta` (botão), `senha-admin` (text_input), `entrar-admin` (botão), `trocar-perfil` (botão, sidebar).

- [ ] **Step 1: Ajustar os testes existentes e escrever os novos (falham)**

Em `tests/test_app.py`:

1. Acrescentar, depois da fixture `_isola_banco`:

```python
def _app(perfil="admin"):
    """AppTest já 'logado'. O portão de perfil é testado nos testes próprios
    mais abaixo; os demais testes só precisam do app aberto."""
    at = AppTest.from_file(APP)
    if perfil:
        at.session_state["perfil"] = perfil
    return at
```

2. Substituir **todas** as ocorrências de `AppTest.from_file(APP)` nos testes **já existentes** por `_app()` (não nos testes novos abaixo, e não dentro da própria `_app`).

3. Acrescentar ao fim:

```python
# --- perfis ----------------------------------------------------------------
def _tela_inicial(secrets=None):
    at = AppTest.from_file(APP)
    if secrets is not None:
        at.secrets["admin"] = secrets
    return at.run(timeout=30)


def test_abre_na_tela_inicial_sem_abas_nem_uploader():
    at = _tela_inicial({"senha": "segredo"})
    assert not at.exception
    assert len(at.tabs) == 0
    assert len(at.get("file_uploader")) == 0
    assert {b.key for b in at.button} >= {"entrar-consulta", "entrar-admin"}


def test_perfil_consulta_ve_so_a_aba_consultar():
    at = _tela_inicial({"senha": "segredo"})
    at.button(key="entrar-consulta").click().run(timeout=30)
    assert not at.exception
    assert len(at.tabs) == 1 and "Consultar" in at.tabs[0].label
    assert len(at.get("file_uploader")) == 0
    assert "Trocar perfil" in [b.label for b in at.button]


def test_admin_com_senha_errada_e_recusado():
    at = _tela_inicial({"senha": "segredo"})
    at.text_input(key="senha-admin").input("errada")
    at.button(key="entrar-admin").click().run(timeout=30)
    assert not at.exception
    assert len(at.error) == 1
    assert len(at.tabs) == 0
    assert at.session_state.filtered_state.get("perfil") is None


def test_admin_com_senha_certa_ve_as_duas_abas():
    at = _tela_inicial({"senha": "segredo"})
    at.text_input(key="senha-admin").input("segredo")
    at.button(key="entrar-admin").click().run(timeout=30)
    assert not at.exception
    assert [t.label for t in at.tabs][0].endswith("Processar e mapear")
    assert len(at.tabs) == 2
    assert len(at.get("file_uploader")) == 1


def test_sem_senha_configurada_o_botao_admin_fica_desabilitado():
    at = _tela_inicial()          # nenhum secret definido
    assert at.button(key="entrar-admin").disabled is True
    assert at.text_input(key="senha-admin").disabled is True
    assert any("não configurada" in w.value for w in at.warning)
    # e o perfil Consulta continua disponível
    assert at.button(key="entrar-consulta").disabled is False


def test_trocar_perfil_volta_para_a_tela_inicial():
    at = _app("consulta").run(timeout=30)
    at.button(key="trocar-perfil").click().run(timeout=30)
    assert not at.exception
    assert len(at.tabs) == 0
    assert "entrar-consulta" in {b.key for b in at.button}
```

Observações para o implementador: (a) se `at.secrets["admin"] = {...}` não aceitar dict aninhado nesta versão do Streamlit, use `at.secrets["admin"] = {"senha": "segredo"}` via a API documentada de `AppTest.secrets`, ou monkeypatche `st.secrets` — o contrato testado é só "`senha_admin(st.secrets)` enxerga a senha"; (b) confirme que, sem `at.secrets`, o `AppTest` **não** lê um `.streamlit/secrets.toml` real da máquina; se ler, o teste "sem senha configurada" deve isolar isso (ex.: `monkeypatch.chdir(tmp_path)` antes de criar o `AppTest`); (c) `at.get("file_uploader")` é a forma genérica de buscar o widget; ajuste se a versão instalada expuser outro acessor.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_app.py -q`
Expected: os testes de perfis FALHAM (não há tela inicial); os antigos passam (o `perfil` extra na sessão é ignorado por ora).

- [ ] **Step 3: Implementar o portão e as abas**

Em `app.py`:

1. Import: `from core import acesso, armazenamento, consulta, pipeline, planilha  # noqa: E402`.

2. Antes da linha `aba_processar, aba_consultar = st.tabs([...])` (e depois de `_processar`), acrescentar:

```python
def _tela_inicial():
    """Escolha de perfil. Consulta entra direto; Administrador exige a senha
    de .streamlit/secrets.toml e fica desabilitado se ela não estiver
    configurada (nunca cai em acesso aberto)."""
    st.markdown("### Como deseja entrar?")
    esperada = acesso.senha_admin(st.secrets)
    col_consulta, col_admin = st.columns(2)

    with col_consulta, st.container(border=True, key="perfil-consulta"):
        st.subheader("Consulta")
        st.caption("Pesquisar as consultas e os regimes já mapeados. Sem senha.")
        if st.button("Entrar para consulta", key="entrar-consulta", type="primary"):
            st.session_state["perfil"] = acesso.PERFIL_CONSULTA
            st.rerun()

    with col_admin, st.container(border=True, key="perfil-admin"):
        st.subheader("Administrador")
        st.caption("Importar PDFs e reprocessar o banco. Exige senha.")
        if esperada is None:
            st.warning("Senha do administrador não configurada. Crie "
                       ".streamlit/secrets.toml (veja secrets.toml.example).")
        senha = st.text_input("Senha", type="password", key="senha-admin",
                              disabled=esperada is None)
        if st.button("Entrar como administrador", key="entrar-admin",
                     disabled=esperada is None):
            if acesso.confere(senha, esperada):
                st.session_state["perfil"] = acesso.PERFIL_ADMIN
                st.rerun()
            else:
                st.error("Senha incorreta.")


perfil = st.session_state.get("perfil")
if perfil not in (acesso.PERFIL_CONSULTA, acesso.PERFIL_ADMIN):
    _tela_inicial()
    st.stop()

with st.sidebar:
    if st.button("Trocar perfil", key="trocar-perfil"):
        for chave in ("perfil", "resultado"):
            st.session_state.pop(chave, None)
        st.rerun()
```

3. Trocar o bloco `aba_processar, aba_consultar = st.tabs([...])` + `with aba_processar:` por:

```python
if perfil == acesso.PERFIL_ADMIN:
    aba_processar, aba_consultar = st.tabs(["📥 Processar e mapear", "🔎 Consultar"])
else:
    aba_processar = None
    (aba_consultar,) = st.tabs(["🔎 Consultar"])

if aba_processar is not None:
  with aba_processar:
    ... (todo o conteúdo atual do bloco, reindentado em um nível)
```

Reindente o conteúdo do bloco `with aba_processar:` (hoje linhas ~265-331) mantendo-o **inalterado** fora da indentação. O bloco `with aba_consultar:` fica como está.

4. Guarda de defesa em profundidade: na primeira linha de `_processar`, antes de qualquer outra coisa: `acesso.exige_admin(st.session_state.get("perfil"))`.

- [ ] **Step 4: `.gitignore` e exemplo de segredo**

`.gitignore`: logo abaixo de `!.streamlit/config.toml` acrescentar a linha `!.streamlit/secrets.toml.example`. **Não** liberar `secrets.toml`.

Criar `.streamlit/secrets.toml.example`:

```toml
# Copie este arquivo para ".streamlit/secrets.toml" e troque a senha.
# O secrets.toml real NÃO é versionado. Sem ele, o perfil Administrador
# fica desabilitado (o perfil Consulta continua funcionando).
[admin]
senha = "troque-esta-senha"
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_app.py -q`
Expected: PASS (antigos e novos).

- [ ] **Step 6: Checkpoint**

Run: `python -m pytest -q`
Expected: todos passam.

---

### Task 6: Documentação e verificação final

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-01-quebra-paragrafos-e-perfis-design.md` (só se a implementação divergir dele; senão não tocar)

**Interfaces:**
- Consumes: tudo das Tarefas 1–5.
- Produces: README coerente com o comportamento real.

- [ ] **Step 1: Atualizar o README**

- Em **Uso (interface)**: descrever a tela inicial (perfis Consulta e Administrador), o botão "Trocar perfil" e que atualizar a página volta à tela inicial.
- Nova seção **Perfis e senha do Administrador**: formato do `.streamlit/secrets.toml` (`[admin]` / `senha`), referência ao `secrets.toml.example`, o que acontece sem o arquivo (Administrador desabilitado), e os limites: senha em texto puro no disco; `processar.py` (CLI) sem restrição; sem bloqueio por tentativas erradas; rever tudo isso na hospedagem multiusuário.
- Em **Mapeamento e consulta**: a Resposta das consultas agora é guardada com parágrafos (`\n\n`); consultas já mapeadas só ganham parágrafos ao **reimportar o PDF** (o upsert atualiza sem duplicar); a planilha quebra linha na coluna Resposta.
- Em **Estrutura**: acrescentar `core/acesso.py` e mencionar `texto_com_paragrafos` em `core/pdf_text.py`.
- Em **Fora deste escopo (fase 2)**: reescrever o item "Autenticação/controle de acesso na interface…" para refletir que existe um perfil Administrador com senha local, e que continuam pendentes: usuários individuais, hospedagem fora da rede interna e banco em rede (PostgreSQL).
- Em **Limitações conhecidas**: layouts de PDF muito diferentes dos fixtures podem exigir ajuste dos limiares de `_marca_paragrafos_da_pagina`; se a detecção falhar, a Resposta cai no texto achatado de sempre.

- [ ] **Step 2: Suíte completa**

Run: `python -m pytest -q`
Expected: todos passam; relatar o total (baseline era 136, agora 136 + novos), sem testes desabilitados.

- [ ] **Step 3: Verificação ponta a ponta com o PDF real**

Run (a partir da raiz do projeto, usando banco temporário — **nunca** o `mapeamento.db` real):

```bash
python - <<'EOF'
import os, tempfile
from core import armazenamento, pipeline, consulta
d = tempfile.mkdtemp()
conn = armazenamento.conectar(os.path.join(d, "t.db")); armazenamento.criar_esquema(conn)
lote = pipeline.Lote()
pipeline.processar_arquivo(lote, "tests/fixtures/Consultas_1_a_3_de_2026.pdf", "c.pdf")
pipeline.finalizar(lote); armazenamento.persistir_lote(conn, lote)
r = next(x for x in consulta.buscar(conn, "consulta") if x["Nº da Consulta"] == "001")
for p in r["Resposta"].split("\n\n"):
    print("--", p[:90].encode("ascii", "replace").decode())
EOF
```

Expected: ~20 ou mais parágrafos para a Consulta 001, entre eles "Cabe transcrever…", "Art. 1…", "Parágrafo único…", "Art. 3…", "Nos termos do…", "Registre-se…", "Quanto à responsabilidade…", "Na hipótese…" — cada um começando onde começa no PDF.

- [ ] **Step 4: Verificação manual da interface**

Subir com `python iniciar.py` (com um `.streamlit/secrets.toml` temporário contendo `[admin]` / `senha = "teste"`), e conferir: (a) tela inicial com os dois cartões; (b) Consulta mostra só "🔎 Consultar"; (c) Administrador com senha errada é recusado e com `teste` abre as duas abas; (d) importar o PDF `Consultas_1_a_3_de_2026.pdf` e abrir a Consulta 001/2026 → RESPOSTA em parágrafos como nas imagens do PDF original; (e) baixar o .xlsx e ver as quebras na célula Resposta. **Apagar o `secrets.toml` temporário depois.** Se não for possível abrir o navegador no ambiente, dizer isso explicitamente no relatório em vez de declarar verificado.

- [ ] **Step 5: Checkpoint final**

Run: `python -m pytest -q`
Expected: verde. Relatar: total de testes, resultado do passo 3, e o que do passo 4 foi ou não verificado.
