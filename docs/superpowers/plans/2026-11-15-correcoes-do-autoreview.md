# Correções do autoreview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir o defeito P1 do autoreview de 2026-11-15 (rótulo com espaço antes dos dois-pontos, ex.: `CAD/ICMS :`, corrompe EMPRESA e esvazia CAD/ICMS) e o PDF `Regime Especial nº 1.456_2026 - COOPERATIVA AGROINDUSTRIAL ALFA.pdf`, que hoje resulta em `A401 — Nenhum registro extraído` por ser de um layout que o parser não conhece (Tarefa 4), e os riscos menores que a mesma revisão apontou (rodapé com 3 dígitos; nenhum diagnóstico para nome de empresa contaminado nem para CAD/ICMS vazio).

**Architecture:** Três ajustes pequenos e independentes, um por tarefa. (1) Os regex de rótulo de `parsers/regimes.py` passam a aceitar `\s*:`. (2) O regex de rodapé de `parsers/consultas.py` passa a aceitar até 3 dígitos. (3) `core/diagnostico.py` ganha dois avisos: `A305` (rótulo dentro do nome da empresa) e `A306` (regime sem CAD/ICMS), que pegam o sintoma mesmo que outro layout futuro escape dos regex. Nenhum contrato de dados muda.

**Tech Stack:** Python 3.10+, `re`, pytest. Nenhuma dependência nova.

**Spec:** não há spec de design: o escopo é o relatório do autoreview (`review.md`, status `findings`, 1 achado P1 + 2 observações abaixo do limiar), reproduzido localmente antes deste plano. Reprodução: `regimes.parse(tests.test_regimes._JAGUAFRANGOS_REAL)` devolve `EMPRESA='JAGUAFRANGOS IND. E COM. DE ALIMENTOS LTDA CAD/ICMS :61700643-03'` e `CAD/ICMS=''`.

## Global Constraints

- Nenhuma dependência nova; `requirements.txt` não muda.
- Comando de testes: `python -m pytest -q` (o `pytest` puro não está no PATH; a suíte leva mais de 2 min, rode-a em segundo plano ou por arquivo durante o trabalho e inteira só no fim). **Antes da Tarefa 1, rode a suíte uma vez e anote o total N**; ao fim do plano o total deve ser N + 14 (4 + 2 + 4 + 4 testes novos).
- Os dicts dos parsers **não ganham nem perdem chaves** (`regimes.parse` continua devolvendo as 15 chaves de sempre).
- Layouts já suportados continuam idênticos: `CAD/ICMS:` colado nos dois-pontos, Krona, Agroantunes, e os PDFs reais em `tests/fixtures/` não podem mudar de resultado.
- Mensagens e rótulos em português; commits em português no estilo `fix: ...`; **sem linha `Co-Authored-By`** (preferência do projeto).
- `README.md` lista os códigos de diagnóstico (linha ~129) e `CHANGELOG.md` + `core/versao.py` carregam a versão: a Tarefa 3 atualiza os três (versão `0.9.1`).

## Review Focus

Entradas que a revisão e o código implicam, mas que nenhum teste atual exercita, da mais provável para a menos:

1. `CAD/ICMS :` com espaço antes dos dois-pontos (o achado): EMPRESA deve ser só o nome e CAD/ICMS deve vir preenchido. → Tarefa 1, teste do Jaguafrangos.
2. `CNPJ :` com espaço: o CNPJ deve ser extraído, não ficar vazio. → Tarefa 1.
3. `BENEFICIÁRIA :` / `EMENTA :` com espaço: o ato deve continuar `concessao_ou_alteracao`, não virar descarte `descartar` em silêncio. → Tarefa 1.
4. Regime sem nenhum CAD/ICMS no bloco: EMPRESA não pode engolir o texto seguinte, CAD/ICMS fica vazio (comportamento a preservar) e o diagnóstico `A306` avisa antes de gravar. → Tarefa 1 (parser) e Tarefa 3 (aviso).
5. Documento de consultas com 100+ páginas (rodapé com número de 3 dígitos): o rodapé não pode sobrar dentro do campo. E um ano de 4 dígitos que abre o parágrafo seguinte continua intacto. → Tarefa 2.
6. Nome de empresa contaminado por rótulo (qualquer layout novo que escape dos regex) deve gerar aviso antes de gravar. → Tarefa 3.
7. Regime de layout desconhecido some em silêncio (0 registros, 0 descartes) e só aparece como `A401`. O layout "Delegacia Regional" (Alfa) é resolvido na Tarefa 4; para layouts ainda desconhecidos A401 continua sendo o aviso (decisão registrada na Tarefa 4).

---

### Task 1: Rótulos do regime aceitam espaço antes dos dois-pontos

**Files:**
- Modify: `parsers/regimes.py` (`_campo` linha ~65, `_BENEFICIARIA` ~75, `_cnpj` ~85, `_cad_icms` ~89, `_ementa` ~94, `_classifica` ~114)
- Test: `tests/test_regimes.py` (acrescentar ao final)

**Interfaces:**
- Consumes: `regimes.parse(texto) -> (registros, descartes)` e a constante de teste `_JAGUAFRANGOS_REAL` já definida em `tests/test_regimes.py`.
- Produces: nada novo; as funções privadas mantêm assinatura e retorno.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao final de `tests/test_regimes.py`:

```python
# Regressão (autoreview 2026-11-15): o Regime Especial nº 8.715/2025 real traz
# "CAD/ICMS :61700643-03" com espaço antes dos dois-pontos. Os regex exigiam
# "CAD/ICMS:" colado, então a EMPRESA saía com o rótulo grudado e o CAD/ICMS
# ficava vazio, sem nenhum diagnóstico.

def test_jaguafrangos_empresa_e_cad_icms_com_espaco_antes_dos_dois_pontos():
    r = regimes.parse(_JAGUAFRANGOS_REAL)[0][0]
    assert r["EMPRESA"] == "JAGUAFRANGOS IND. E COM. DE ALIMENTOS LTDA"
    assert r["CAD/ICMS"] == "61700643-03"
    assert r["CNPJ REQUERENTE"] == "85.090.033/0001-22"


def _bloco(cabecalho_dados: str) -> str:
    return (
        "INSPETORIA GERAL DE FISCALIZAÇÃO\n"
        "REGIME ESPECIAL Nº 1/2026\n"
        + cabecalho_dados +
        "EMENTA: Algo.\n"
        "Diante do previsto no Parecer, concede-se.\n"
    )


def test_cnpj_com_espaco_antes_dos_dois_pontos():
    texto = _bloco("BENEFICIÁRIA: ACME LTDA\n"
                   "CAD/ICMS: 12345678-90 CNPJ : 11.222.333/0001-81\n")
    r = regimes.parse(texto)[0][0]
    assert r["EMPRESA"] == "ACME LTDA"
    assert r["CNPJ REQUERENTE"] == "11.222.333/0001-81"


def test_beneficiaria_e_ementa_com_espaco_antes_dos_dois_pontos_nao_viram_descarte():
    texto = (
        "INSPETORIA GERAL DE FISCALIZAÇÃO\n"
        "REGIME ESPECIAL Nº 2/2026\n"
        "BENEFICIÁRIA : ACME LTDA\n"
        "CNPJ: 11.222.333/0001-81\n"
        "EMENTA : Algo.\n"
        "Diante do previsto no Parecer, concede-se.\n"
    )
    registros, descartes = regimes.parse(texto)
    assert len(registros) == 1 and descartes == []
    assert registros[0]["EMPRESA"] == "ACME LTDA"
    assert registros[0]["EMENTA"] == "Algo."


def test_regime_sem_cad_icms_mantem_empresa_limpa_e_cad_icms_vazio():
    texto = _bloco("BENEFICIÁRIA: ACME LTDA\n"
                   "CNPJ: 11.222.333/0001-81\n")
    r = regimes.parse(texto)[0][0]
    assert r["EMPRESA"] == "ACME LTDA"
    assert r["CAD/ICMS"] == ""
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_regimes.py -q`
Expected: FAIL em `test_jaguafrangos_empresa_e_cad_icms_com_espaco_antes_dos_dois_pontos`, `test_cnpj_com_espaco_antes_dos_dois_pontos` e `test_beneficiaria_e_ementa_com_espaco_antes_dos_dois_pontos_nao_viram_descarte`; o teste "sem CAD/ICMS" já passa (é a trava do comportamento atual).

- [ ] **Step 3: Implementar**

Em `parsers/regimes.py`, trocar cada rótulo `X:` por `X\s*:` (os `\s*` depois dos dois-pontos já existem):

```python
def _campo(fatia: str, rotulo: str) -> str:
    m = re.search(rf'{rotulo}\s*:\s*(.+)', fatia, re.IGNORECASE)
    return m.group(1).strip() if m else ""


_BENEFICIARIA = re.compile(
    r'BENEFICI[ÁA]RIA\s*:\s*(.{1,200}?)\s*'
    r'(?=CAD/ICMS\s*:|CNPJ\s*:|ENDERE[ÇC]O\s*:|EMENTA\s*:)',
    re.IGNORECASE | re.DOTALL,
)


def _cnpj(fatia: str) -> str:
    m = re.search(r'CNPJ\s*:\s*([\d\.\/-]+)', fatia, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _cad_icms(fatia: str) -> str:
    m = re.search(r'CAD/ICMS\s*:\s*([\d\.\-]+)', fatia, re.IGNORECASE)
    return m.group(1).strip() if m else ""
```

Em `_ementa`, trocar `r'EMENTA:\s*(.+?)(?:Diante do previsto|'` por `r'EMENTA\s*:\s*(.+?)(?:Diante do previsto|'` (o resto do padrão não muda).

Em `_classifica`, trocar os dois rótulos:

```python
    tem_beneficiaria = re.search(r'BENEFICI[ÁA]RIA\s*:', fatia, re.IGNORECASE)
    tem_ementa = re.search(r'EMENTA\s*:', fatia, re.IGNORECASE)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_regimes.py -q`
Expected: PASS (todos, inclusive os antigos de Krona/Agroantunes/fixtures reais).

- [ ] **Step 5: Commit**

```bash
git add parsers/regimes.py tests/test_regimes.py
git commit -m "fix: rótulos do regime aceitam espaço antes dos dois-pontos (CAD/ICMS :)"
```

---

### Task 2: Rodapé de consultas aceita número de página de 3 dígitos

**Files:**
- Modify: `parsers/consultas.py` (`_CABECALHO`, linha ~29, e o comentário acima dele, linhas ~21-26)
- Test: `tests/test_consultas.py` (logo após `test_rodape_com_numero_de_pagina_de_dois_digitos_nao_vaza`, ~linha 360)

**Interfaces:**
- Consumes: `consultas.parse(texto) -> list[dict]`; no arquivo de teste já existe `_CABECALHO_PAGINA` (cabeçalho de página usado pelo teste de dois dígitos).
- Produces: nada novo.

- [ ] **Step 1: Escrever os testes que falham**

Inserir após o teste de dois dígitos em `tests/test_consultas.py`:

```python
def test_rodape_com_numero_de_pagina_de_tres_digitos_nao_vaza():
    # documentos de 100+ páginas (o de 2023 tem 226) têm rodapé de 3 dígitos
    texto = (
        "ANO: 2026\n"
        "PROTOCOLOS: 25.152.191-3\n"
        "CONSULTA Nº 001, de 19 de janeiro de 2026.\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente informa que o texto continua na página seguinte a\n"
        "__________________________________________________\n"
        "120\n"
        + _CABECALHO_PAGINA
        + "sem qualquer ruído no meio da frase.\n"
        "RESPOSTA\n"
        "Resposta.\n"
    )
    problema = consultas.parse(texto)[0]["Problema da Consulta"]
    assert "continua na página seguinte a sem qualquer ruído" in problema
    assert "120" not in problema


def test_ano_de_quatro_digitos_apos_o_rodape_continua_no_texto():
    # a trava do (?!\d): "2023" abre o parágrafo seguinte e não é rodapé
    texto = (
        "ANO: 2026\n"
        "PROTOCOLOS: 25.152.191-3\n"
        "CONSULTA Nº 001, de 19 de janeiro de 2026.\n"
        "SÚMULA: ICMS. X.\n"
        "A consulente informa que\n"
        "__________________________________________________\n"
        "2023 foi o ano em que ocorreu o fato.\n"
        "RESPOSTA\n"
        "Resposta.\n"
    )
    problema = consultas.parse(texto)[0]["Problema da Consulta"]
    assert "2023 foi o ano" in problema
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_consultas.py -q -k "tres_digitos or quatro_digitos"`
Expected: `tres_digitos` FAIL (o "120" sobra no texto); `quatro_digitos` PASS (trava do comportamento atual).

- [ ] **Step 3: Implementar**

Em `parsers/consultas.py`, em `_CABECALHO`, trocar o primeiro `\d{1,2}(?!\d)` por `\d{1,3}(?!\d)` (a alternativa sem rodapé, depois do `|`, não tem número e não muda). Atualizar o comentário acima: onde diz "com 1 ou 2 dígitos" e "`\d{1,2}(?!\d)`", escrever "com 1 a 3 dígitos" e "`\d{1,3}(?!\d)`", mantendo a explicação do ano de 4 dígitos.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_consultas.py -q`
Expected: PASS (todos, inclusive os de rodapé de 1 e 2 dígitos e o PDF real de 2026).

- [ ] **Step 5: Commit**

```bash
git add parsers/consultas.py tests/test_consultas.py
git commit -m "fix: rodapé de consulta com número de página de 3 dígitos não vaza para o campo"
```

---

### Task 3: Avisos A305 (empresa com rótulo) e A306 (sem CAD/ICMS) + versão 0.9.1

**Files:**
- Modify: `core/diagnostico.py` (`_CATALOGO` linha ~14 e laço dos regimes ~linha 66-82)
- Modify: `README.md` (tabela de códigos, linha ~129), `CHANGELOG.md` (nova seção no topo), `core/versao.py` (`VERSAO_APP`)
- Test: `tests/test_diagnostico.py` (ao final)

**Interfaces:**
- Consumes: `diagnostico.diagnosticar(lote) -> {'mensagens', 'erros', 'avisos', 'pode_continuar'}`; helpers de teste `_regime(**campos)`, `_arq(nome, tipo=...)` e `_codigos(diag)` já existentes em `tests/test_diagnostico.py`; `pipeline.Lote`.
- Produces: códigos de diagnóstico `A305` (nível `aviso`, título `'Nome da empresa contém rótulo do cabeçalho'`) e `A306` (nível `aviso`, título `'Regime sem CAD/ICMS'`).

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao final de `tests/test_diagnostico.py`:

```python
def test_empresa_com_rotulo_do_cabecalho_gera_aviso_a305():
    lote = pipeline.Lote(
        regimes=[
            _regime(**{'Nº DO REGIME ESPECIAL': '1/2026',
                       'EMPRESA': 'ACME LTDA CAD/ICMS :123'}),
            _regime(**{'Nº DO REGIME ESPECIAL': '2/2026',
                       'EMPRESA': 'BETA S.A. CNPJ: 11.222.333/0001-81'}),
            _regime(**{'Nº DO REGIME ESPECIAL': '3/2026',
                       'EMPRESA': 'GAMA LTDA'}),
        ],
        arquivos=[_arq('r.pdf', tipo='regime')])
    diag = diagnostico.diagnosticar(lote)
    assert _codigos(diag) == ['A305']
    msg = diag['mensagens'][0]
    assert msg['nivel'] == 'aviso'
    assert '1/2026' in msg['texto'] and '2/2026' in msg['texto']
    assert '3/2026' not in msg['texto']
    assert diag['pode_continuar'] is True


def test_empresa_sem_rotulo_ou_ausente_nao_gera_a305():
    lote = pipeline.Lote(
        regimes=[_regime(**{'EMPRESA': 'INDÚSTRIA E COMÉRCIO DE ENDERECOS LTDA'}),
                 _regime(**{'Nº DO REGIME ESPECIAL': '2/2026'})],
        arquivos=[_arq('r.pdf', tipo='regime')])
    assert _codigos(diagnostico.diagnosticar(lote)) == []
```

E o `_regime` base do arquivo ganha CAD/ICMS válido, para que os testes antigos continuem sem `A306`:

```python
def _regime(**campos):
    base = {'Nº DO REGIME ESPECIAL': '1/2026', 'CNPJ REQUERENTE': '11.222.333/0001-81',
            'CAD/ICMS': '12345678-90', 'DATA': '2026-03-01', 'VIGÊNCIA DO RE': '12 meses'}
    return {**base, **campos}
```

(Substituir a definição existente de `_regime`, no topo do arquivo.) Testes do `A306`:

```python
def test_regime_sem_cad_icms_gera_aviso_a306():
    lote = pipeline.Lote(
        regimes=[_regime(**{'Nº DO REGIME ESPECIAL': '1/2026', 'CAD/ICMS': ''}),
                 _regime(**{'Nº DO REGIME ESPECIAL': '2/2026', 'CAD/ICMS': '   '}),
                 _regime(**{'Nº DO REGIME ESPECIAL': '3/2026'})],
        arquivos=[_arq('r.pdf', tipo='regime')])
    diag = diagnostico.diagnosticar(lote)
    assert _codigos(diag) == ['A306']
    msg = diag['mensagens'][0]
    assert msg['nivel'] == 'aviso'
    assert '1/2026' in msg['texto'] and '2/2026' in msg['texto']
    assert '3/2026' not in msg['texto']
    assert diag['pode_continuar'] is True


def test_regime_sem_a_chave_cad_icms_tambem_gera_a306():
    regime = _regime()
    del regime['CAD/ICMS']
    lote = pipeline.Lote(regimes=[regime], arquivos=[_arq('r.pdf', tipo='regime')])
    assert _codigos(diagnostico.diagnosticar(lote)) == ['A306']
```

(A 1ª linha do segundo teste do A305 usa uma palavra que contém "ENDERECOS" sem o `Ç` e sem dois-pontos: prova que só o rótulo seguido de `:` conta. A 2ª linha não tem a chave `EMPRESA`.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_diagnostico.py -q`
Expected: FAIL em `test_empresa_com_rotulo_do_cabecalho_gera_aviso_a305` (`A305` não existe; `_codigos` devolve `[]`). O segundo teste já passa.

- [ ] **Step 3: Implementar**

Em `core/diagnostico.py`, junto das outras constantes (após `_ISO`):

```python
_ROTULO_NO_NOME = re.compile(
    r'\b(?:CAD/ICMS|CNPJ|ENDERE[ÇC]O|EMENTA|BENEFICI[ÁA]RIA)\s*:', re.IGNORECASE)
```

No `_CATALOGO`, após `'A304'`:

```python
    'A305': 'Nome da empresa contém rótulo do cabeçalho',
    'A306': 'Regime sem CAD/ICMS',
```

No laço `for r in lote.regimes:`, após o bloco do `A304`:

```python
        if _ROTULO_NO_NOME.search(str(r.get('EMPRESA', '') or '')):
            achados['A305'].append((ref, arq))
        if not str(r.get('CAD/ICMS', '') or '').strip():
            achados['A306'].append((ref, arq))
```

Em `core/versao.py`: `VERSAO_APP = "0.9.1"`.

Em `CHANGELOG.md`, nova seção acima de `## 0.9.0`:

```markdown
## 0.9.1
- **Correção no parser de regimes**: rótulos com espaço antes dos dois-pontos (ex.: `CAD/ICMS :61700643-03`, presente no Regime Especial nº 8.715/2025) não corrompem mais a EMPRESA nem deixam o CAD/ICMS vazio. Vale também para `CNPJ :`, `BENEFICIÁRIA :` e `EMENTA :`.
- **Correção no parser de consultas**: o rodapé de página com número de 3 dígitos (documentos de 100+ páginas) deixa de sobrar dentro dos campos.
- Novos avisos de diagnóstico: `A305` (nome da empresa que traz um rótulo do cabeçalho, como `CAD/ICMS:` ou `CNPJ:`) e `A306` (regime sem CAD/ICMS). Ambos aparecem antes de gravar e não bloqueiam.
- Regimes já gravados com o defeito só se corrigem reimportando o PDF; os campos ajustados à mão são preservados pela reimportação.
```

Em `README.md`, na tabela da linha ~129, acrescentar uma linha depois de `A303` / `A304`:

```markdown
| `A305` / `A306` | aviso | nome da empresa contém rótulo do cabeçalho (`CAD/ICMS:`, `CNPJ:` …) / regime sem CAD/ICMS |
```

- [ ] **Step 4: Rodar e ver passar; suíte inteira**

Run: `python -m pytest tests/test_diagnostico.py -q` → Expected: PASS.
Run: `python -m pytest -q` (em segundo plano; leva > 2 min) → Expected: tudo passa, total N + 14. Testes de `tests/test_app.py` e outros que montam regimes com `'CAD/ICMS': ''` e checam a contagem/lista de avisos do diagnóstico passam a ver também o `A306`: ajustar a expectativa (ou dar CAD/ICMS ao regime de teste) caso a caso, sem enfraquecer o que o teste verifica. Se algum teste de versão ou de README falhar por causa de `0.9.1`, atualizar a expectativa no teste (grep por `0.9.0` em `tests/`).

- [ ] **Step 5: Commit**

```bash
git add core/diagnostico.py core/versao.py README.md CHANGELOG.md tests/test_diagnostico.py
git commit -m "feat: avisos A305 (empresa com rótulo) e A306 (regime sem CAD/ICMS); versão 0.9.1"
```

---

### Task 4: Regime no layout "Delegacia Regional" (Regime Especial de Recolhimento do ICMS)

**Por que o PDF da Alfa não importa (causa validada no texto real):** o PDF é detectado corretamente como `regime` (a 1ª página tem "REGIME ESPECIAL"), mas `regimes.parse` devolve **0 registros e 0 descartes**, daí o `A401`. O parser só conhece o layout da Inspetoria/Coordenação de Fiscalização, e este regime é de **Delegacia Regional** (14ª DRR, Pato Branco) e difere em quatro pontos:

| | layout conhecido | layout da Alfa |
|---|---|---|
| âncora | `COORDENAÇÃO/INSPETORIA … DE FISCALIZAÇÃO` + `REGIME ESPECIAL Nº 8.715/2025` | `REGIME ESPECIAL\nDE RECOLHIMENTO DO ICMS Nº1.456` (sem ano, "Nº" colado no número) + `PROTOCOLO` na linha seguinte |
| rótulos | `BENEFICIÁRIA:` / `EMENTA:` | `CONTRIBUINTE:` / `Súmula -` (por isso `_classifica` também descartaria) |
| corpo | seções numeradas com título (`1. DA ABRANGÊNCIA` …) | lista numerada 1–6 sem títulos, depois de "autoriza os seguintes procedimentos:" |
| fim da matéria | próxima âncora | a página do Diário traz **outras matérias depois** (`Protocolo 120349/2026` fecha esta): sem recorte, `_vigencia` leria "eficácia se encerra em…" de matéria alheia |

Reprodução: `regimes.parse(pdf_text.texto_por_colunas(<pdf>))` → `([], [])`. O ano não está no título: vem da data da edição do Diário (`09/SET/2026`), e o "Nº DO REGIME ESPECIAL" fica `1.456/2026`, igual ao nome do arquivo e ao formato dos demais.

**Decisões já tomadas (revise se discordar):**
- **VIGÊNCIA fica vazia.** O regime só diz "entrará em vigor na data de sua publicação", sem prazo; não se inventa data. O aviso `A303` (regime sem vigência) vai aparecer para ele, o que é o comportamento correto.
- **ABRANGÊNCIA e DISPOSIÇÕES GERAIS ficam vazias** (o layout não tem essas seções); o miolo numerado vai para `BENEFÍCIOS/PROCEDIMENTOS`, até a linha de assinatura.
- **Não há alarme genérico para layout totalmente desconhecido** (um título "REGIME ESPECIAL DE …" sem a linha `PROTOCOLO` seguinte continua sem registro e sem descarte). Listá-lo como `titulo_sem_ancora` geraria falso descarte para a citação entre aspas do próprio regime (“REGIME ESPECIAL DE RECOLHIMENTO DO ICMS Nº 1.456”) que a nota fiscal deve conter.

**Files:**
- Modify: `parsers/regimes.py` (constantes novas junto de `_ANCORA_RE`; `_BENEFICIARIA`, `_ementa`, `_classifica`; funções novas antes de `_pr_competitivo`; `parse` e a chamada a `_titulos_sem_ancora`)
- Modify: `CHANGELOG.md` (seção `## 0.9.1`)
- Test: `tests/test_regimes.py` (acrescentar ao final)

**Interfaces:**
- Consumes: `regimes.parse(texto) -> (registros, descartes)`; `_titulos_sem_ancora(texto, ancoras)` continua recebendo uma lista de objetos `re.Match` (só `.start()`/`.end()` são usados); depende da Tarefa 1 (rótulos com `\s*:`), cujas versões de `_BENEFICIARIA`, `_ementa` e `_classifica` esta tarefa estende.
- Produces: `regimes.parse` passa a reconhecer o layout "delegacia"; os dicts continuam com as mesmas 15 chaves.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao final de `tests/test_regimes.py`:

```python
# Layout "Delegacia Regional" (Regime Especial de Recolhimento do ICMS, nº
# 1.456 de 2026, Cooperativa Agroindustrial Alfa, DOE nº 12.212): o título é
# "REGIME ESPECIAL DE RECOLHIMENTO DO ICMS Nº1.456" (sem "/ano"), o cabeçalho
# usa CONTRIBUINTE/Súmula em vez de BENEFICIÁRIA/EMENTA e não há seções
# numeradas com título. A página do Diário traz outras matérias antes e depois.
_ALFA_REAL = (
    "28 4ª FEIRA |09/SET/2026 - EDIÇÃO N° 12.212\n"
    "Protocolo 120923/2026\n"
    "Receita Estadual do Paraná\n"
    "<#E.G.B#120349/2026#28#2113543>\n"
    "ESTADO DO PARANÁ SECRETARIA DE ESTADO DA\n"
    "FAZENDA\n"
    "RECEITA ESTADUAL DO PARANÁ\n"
    "14ª DELEGACIA REGIONAL DA RECEITA - DRR REGIME ESPECIAL\n"
    "DE RECOLHIMENTO DO ICMS Nº1.456\n"
    "PROTOCOLO Nº 261332744 CONTRIBUINTE:COOPERATIVA\n"
    "AGROINDUSTRIAL ALFA CAD/ICMS:91154823-24\n"
    "CNPJ:83.305.235/0227-83\n"
    "ENDEREÇO:ROD PRT 280 KM 224 42, SN - BL 1; - INTERIOR\n"
    "MUNICIPIO:VITORINO\n"
    "Súmula - Concede apuração e recolhimento do ICMS na forma do inciso XIX do\n"
    "art. 74 do RICMS/2017.\n"
    "O Delegado Regional da Receita, após examinar o pedido constante no\n"
    "29 4ª FEIRA |09/SET/2026 - EDIÇÃO N° 12.212\n"
    "protocolo acima e considerando atendidos os requisitos, resolve CONCEDER\n"
    "REGIME ESPECIAL DE\n"
    "RECOLHIMENTO DO ICMS ao contribuinte acima identificado. Este Regime\n"
    "Especial autoriza os seguintes procedimentos:\n"
    "1. Dispensa o contribuinte de recolher o valor do ICMS devido por\n"
    "ocasião do fato gerador e lhe autoriza a apurar e recolher esse valor.\n"
    "2. A nota fiscal que documentar a operação deverá conter a seguinte\n"
    "observação:\n"
    "“REGIME ESPECIAL DE RECOLHIMENTO DO ICMS Nº 1.456” .\n"
    "6. Este Regime Especial entrará em vigor na data de sua publicação no\n"
    "Diário Oficial - Comércio Indústria e Serviços.\n"
    "Pato Branco/PR, 11 de Agosto de 2026 José Antonio Sarturi\n"
    "Delegado Regional da Receita\n"
    "<#E.G.B#120349/2026#29#2113543/>\n"
    "Protocolo 120349/2026\n"
    "Autarquias\n"
    "ADAPAR\n"
    "Outra matéria sem relação, cuja eficácia se encerra em 31/12/2030.\n"
)


def test_alfa_delegacia_vira_um_registro_com_os_campos_do_cabecalho():
    registros, descartes = regimes.parse(_ALFA_REAL)
    assert descartes == []
    assert len(registros) == 1          # a citação entre aspas não é 2º título
    r = registros[0]
    assert r["Nº DO REGIME ESPECIAL"] == "1.456/2026"
    assert r["ANO"] == "2026"
    assert r["DATA"] == "2026-09-09"
    assert r["Nº DOE"] == "12.212"
    assert r["EMPRESA"] == "COOPERATIVA AGROINDUSTRIAL ALFA"
    assert r["CNPJ REQUERENTE"] == "83.305.235/0227-83"
    assert r["CAD/ICMS"] == "91154823-24"
    assert r["EMENTA"] == ("Concede apuração e recolhimento do ICMS na forma do "
                           "inciso XIX do art. 74 do RICMS/2017.")


def test_alfa_procedimentos_vao_ate_a_assinatura_sem_ruido():
    r = regimes.parse(_ALFA_REAL)[0][0]
    proc = r["BENEFÍCIOS/PROCEDIMENTOS"]
    assert proc.startswith("1. Dispensa o contribuinte")
    assert "6. Este Regime Especial entrará em vigor" in proc
    assert "Pato Branco" not in proc and "Sarturi" not in proc
    assert "FEIRA" not in proc


def test_alfa_nao_herda_vigencia_de_materia_vizinha_da_mesma_pagina():
    # o regime não declara vigência; "eficácia se encerra em 31/12/2030" é de
    # OUTRA matéria do mesmo Diário e não pode vazar para este registro
    r = regimes.parse(_ALFA_REAL)[0][0]
    assert r["VIGÊNCIA DO RE"] == ""
    assert r["ABRANGÊNCIA"] == "" and r["DISPOSIÇÕES GERAIS"] == ""


def test_regime_de_recolhimento_convive_com_regime_da_fiscalizacao_no_mesmo_texto():
    registros, descartes = regimes.parse(_JAGUAFRANGOS_REAL + "\n" + _ALFA_REAL)
    assert descartes == []
    assert [x["Nº DO REGIME ESPECIAL"] for x in registros] == ["8.715/2025", "1.456/2026"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_regimes.py -q -k "alfa or convive"`
Expected: FAIL nos 4 testes (`regimes.parse(_ALFA_REAL)` devolve `([], [])`; no teste de convivência só o Jaguafrangos aparece).

- [ ] **Step 3: Implementar**

Em `parsers/regimes.py`, logo depois de `_ANCORA_RE`, acrescentar as constantes:

```python
# Layout de Delegacia Regional ("REGIME ESPECIAL DE RECOLHIMENTO DO ICMS
# Nº1.456"): sem "/ano" no título e com "PROTOCOLO" na linha seguinte. Esse
# "PROTOCOLO" é o que distingue o título da CITAÇÃO do regime que a própria
# nota fiscal deve conter (“REGIME ESPECIAL DE RECOLHIMENTO DO ICMS Nº 1.456”),
# que vem entre aspas e seguida de ponto. Case-sensitive de propósito.
_ANCORA_DELEGACIA = re.compile(
    r'REGIME\s+ESPECIAL\s+DE(?:\s+[A-ZÀ-Ü]+){1,8}?\s+N[ºo°]\s*([\d\.]+)\s*\n\s*PROTOCOLO'
)

# O Diário traz várias matérias por página; a deste layout termina na linha
# "Protocolo NNNNNN/AAAA". Sem esse recorte a fatia iria até o fim do texto e
# _vigencia leria "eficácia se encerra em…" de outra matéria.
_FIM_DA_MATERIA = re.compile(r'\n\s*Protocolo\s+\d+/\d{4}')

# Linha de assinatura ("Pato Branco/PR, 11 de Agosto de 2026 José Antonio
# Sarturi"): fecha a lista de procedimentos e traz o ano como último recurso.
_ASSINATURA_DELEGACIA = re.compile(
    r'\n[^\n]*/[A-Z]{2},\s*\d{1,2}\s+de\s+\w+\s+de\s+\d{4}')

_PROCEDIMENTOS_DELEGACIA = re.compile(
    r'autoriza\s+os\s+seguintes\s+procedimentos\s*:\s*\n', re.IGNORECASE)
```

Trocar `_BENEFICIARIA` (versão da Tarefa 1) por:

```python
_BENEFICIARIA = re.compile(
    r'(?:BENEFICI[ÁA]RIA|CONTRIBUINTE)\s*:\s*(.{1,200}?)\s*'
    r'(?=CAD/ICMS\s*:|CNPJ\s*:|ENDERE[ÇC]O\s*:|EMENTA\s*:|S[úu]mula\s*[-–])',
    re.IGNORECASE | re.DOTALL,
)
```

Em `_ementa`, trocar a primeira linha do padrão (a que começa em `r'EMENTA\s*:\s*(.+?)(?:Diante do previsto|…`) por esta, que aceita `Súmula -` e acrescenta o terminador `O Delegado` (o restante do padrão não muda):

```python
        r'(?:EMENTA\s*:|S[úu]mula\s*[-–])\s*(.+?)(?:Diante do previsto|A Diretora|O Diretor|O Delegado|'
```

Em `_classifica`:

```python
    tem_beneficiaria = re.search(r'(?:BENEFICI[ÁA]RIA|CONTRIBUINTE)\s*:', fatia, re.IGNORECASE)
    tem_ementa = re.search(r'EMENTA\s*:|S[úu]mula\s*[-–]', fatia, re.IGNORECASE)
```

Antes de `_pr_competitivo`, acrescentar:

```python
def _extrai_procedimentos_delegacia(fatia: str) -> str:
    """Lista numerada que segue "autoriza os seguintes procedimentos:", até a
    linha de assinatura. Vazio se o layout não for o de Delegacia."""
    m_inicio = _PROCEDIMENTOS_DELEGACIA.search(fatia)
    if not m_inicio:
        return ""
    resto = fatia[m_inicio.end():]
    m_fim = _ASSINATURA_DELEGACIA.search(resto)
    return re.sub(r'\s+', ' ', resto[:m_fim.start() if m_fim else len(resto)]).strip()


def _ano_do_regime(data_ed: str, fatia: str) -> str:
    """O título deste layout não traz o ano: usa o da edição do Diário e, sem
    ela, o da linha de assinatura."""
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', data_ed):
        return data_ed[:4]
    m = _ASSINATURA_DELEGACIA.search(fatia)
    return re.search(r'(\d{4})\s*$', m.group(0)).group(1) if m else ""
```

Em `parse`, substituir o trecho que vai da linha `ancoras = list(_ANCORA_RE.finditer(texto))` até a linha `num_re = f"{anc.group(1)}/{anc.group(2)}"` (inclusive) por:

```python
    ancoras = sorted(
        [(m, 'fiscalizacao') for m in _ANCORA_RE.finditer(texto)]
        + [(m, 'delegacia') for m in _ANCORA_DELEGACIA.finditer(texto)],
        key=lambda par: par[0].start())
    registros, descartes = [], []

    for i, (anc, layout) in enumerate(ancoras):
        inicio = anc.start()
        fim = ancoras[i + 1][0].start() if i + 1 < len(ancoras) else len(texto)
        if layout == 'delegacia':
            m_fim = _FIM_DA_MATERIA.search(texto, anc.end(), fim)
            if m_fim:
                fim = m_fim.start()
        fatia = texto[inicio:fim]
        tipo = _classifica(fatia)
        ano = (anc.group(2) if layout == 'fiscalizacao'
               else _ano_do_regime(data_ed, fatia))
        num_re = f"{anc.group(1)}/{ano}"
```

No dict do registro: `'ANO': ano,` (em vez de `anc.group(2)`) e

```python
            'BENEFÍCIOS/PROCEDIMENTOS': (_extrai_beneficios_procedimentos(fatia)
                                         or _extrai_procedimentos_delegacia(fatia)),
```

E a chamada final passa a ser `descartes.extend(_titulos_sem_ancora(texto, [a for a, _ in ancoras]))`.

- [ ] **Step 4: Rodar e ver passar; conferir o PDF real**

Run: `python -m pytest tests/test_regimes.py tests/test_pipeline.py -q`
Expected: PASS (inclui os testes antigos de Krona, Agroantunes, Jaguafrangos e os PDFs reais de `tests/fixtures/`).

Conferência manual com o PDF da Alfa (o arquivo não vai para o repositório; ajuste o caminho se necessário):

```bash
python -c "
import glob
from core import pdf_text; from parsers import regimes
f = glob.glob(r'C:\Users\jvlsantos\Desktop\Regime Especial*456*ALFA*.pdf')[0]
r, d = regimes.parse(pdf_text.texto_por_colunas(f))
print(len(r), d); print(r[0]['Nº DO REGIME ESPECIAL'], r[0]['EMPRESA'], r[0]['CNPJ REQUERENTE'], r[0]['CAD/ICMS'])"
```

Expected: `1 []` e `1.456/2026 COOPERATIVA AGROINDUSTRIAL ALFA 83.305.235/0227-83 91154823-24`. Depois, importar o PDF no app: o lote deve gravar 1 regime, com aviso `A303` (sem vigência) e sem `A401`.

- [ ] **Step 5: Commit**

Antes do commit, acrescentar à seção `## 0.9.1` do `CHANGELOG.md`:

```markdown
- **Novo layout de regime**: o Regime Especial de Recolhimento do ICMS de Delegacia Regional (título sem ano, `CONTRIBUINTE:`/`Súmula`) passa a ser importado; antes o PDF resultava em `A401 — Nenhum registro extraído`. A vigência fica vazia quando o ato não declara prazo (aviso `A303`).
```

```bash
git add parsers/regimes.py tests/test_regimes.py CHANGELOG.md
git commit -m "feat: parser de regimes reconhece o layout de Delegacia Regional (Recolhimento do ICMS)"
```

---

## Self-Review

1. **Spec coverage:** o PDF da Alfa → Tarefa 4; o achado P1 → Tarefa 1; observação do rodapé de 3 dígitos → Tarefa 2; "diagnóstico não tem check de EMPRESA/CAD/ICMS" (parágrafo do próprio achado) → Tarefa 3 (A305 cobre EMPRESA contaminada; A306 cobre CAD/ICMS vazio, por decisão do usuário). A observação sobre alias permanente de chave corrigida é decisão de design, fora do escopo (YAGNI) — se o usuário quiser tratá-la, vira plano à parte.
2. **Placeholders:** nenhum; todo passo de código traz o código.
3. **Consistência:** `_regime`, `_arq`, `_codigos`, `_CABECALHO_PAGINA` e `_JAGUAFRANGOS_REAL` existem nos arquivos de teste citados; o código `A305` e o título são iguais em catálogo, testes, README e CHANGELOG.
4. **Review Focus:** itens 1-3 → Tarefa 1; 4 → Tarefas 1 e 3; 5 → Tarefa 2; 6 → Tarefa 3; 7 → Tarefa 4.
5. **Contagem:** N + 14 testes novos (4 + 2 + 4 + 4).
