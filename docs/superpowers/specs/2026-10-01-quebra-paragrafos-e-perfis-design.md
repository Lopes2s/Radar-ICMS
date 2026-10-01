# Quebra de parágrafos na Resposta e perfis de acesso — design

Data: 2026-10-01

## 1. Problema e objetivo

Ao abrir uma consulta tributária (ex.: Consulta 001/2026), o campo **RESPOSTA** aparece como um bloco único de texto, sem quebras de linha, enquanto o PDF original da SEFA-PR tem parágrafos, citações legais recuadas e
linhas em branco. A leitura fica difícil.

Objetivos:

1. Reconstruir **automaticamente** os parágrafos da Resposta a partir do PDF.
2. Criar dois perfis de uso: **Consulta** (livre, sem senha) e
   **Administrador** (com senha), onde só o Administrador importa PDFs e
   reprocessa o banco.

Fora do escopo: edição manual de texto pelo Administrador (descartada; a
reconstrução automática resolve o problema), mudanças em Súmula, Problema da
Consulta, CNAE, Protocolo e em qualquer campo de Regime Especial.

## 2. Causa raiz

- `parsers/consultas.py::_extrai_resposta` faz `re.sub(r'\s+', ' ', ...)`,
  que achata o texto em um parágrafo único (feito para caber em célula de
  planilha).
- Além disso, `pdfplumber.extract_text()` descarta a geometria do PDF, então o
  texto que chega ao parser já não tem linhas em branco.
- A informação de parágrafo existe no PDF em coordenadas. Medido na página 4
  do fixture `Consultas_1_a_3_de_2026.pdf`:
  - primeira linha de parágrafo: x0 = 108; continuação: x0 = 36;
  - espaçamento entre parágrafos: cerca de 21,8 pt; entre linhas do mesmo
    parágrafo: cerca de 12,8 pt.

## 3. Restrições de design

- **Mudança só no campo Resposta das consultas.** `texto_simples`,
  `texto_por_colunas`, `detecta_fonte` e todo o ramo de regimes ficam sem
  alteração.
- Os testes existentes continuam passando sem modificação, exceto os de
  `test_app.py`, que precisam entrar como Administrador (seção 6).
- Sem mudança de schema no banco.

## 4. Reconstrução de parágrafos (só Resposta)

### 4.1 `core/pdf_text.py`

Função **nova**: `texto_com_paragrafos(caminho_pdf) -> str`.

- Lê as linhas de cada página com coordenadas (`extract_text_lines`).
- Marca início de parágrafo quando a linha tem recuo de primeira linha em
  relação à margem do corpo, ou quando há salto vertical maior que o
  espaçamento normal entre linhas.
- Linha de início de parágrafo recebe como prefixo um **marcador explícito**
  (`MARCA_PARAGRAFO = "\u2029"`), e não uma linha em branco. Motivo: a
  limpeza de cabeçalho/rodapé do parser (`_CABECALHO.sub('\n', ...)`) deixa
  linhas em branco no meio de um parágrafo que atravessa a página; uma linha
  em branco seria, portanto, ambígua. Removendo-se o marcador, o texto é
  **idêntico** ao de `texto_simples` (verificado no fixture), de modo que a
  limpeza de cabeçalho/rodapé e as âncoras do parser continuam funcionando.
- Linhas de ruído de página (traços, número de página, cabeçalho "SECRETARIA…
  SETOR CONSULTIVO") nunca recebem marcador e zeram a referência de espaçamento
  vertical, para que o primeiro parágrafo após o cabeçalho não pareça um novo
  parágrafo por causa do salto.
- Parágrafo que atravessa a quebra de página continua colado, salvo se a
  primeira linha da página seguinte tiver recuo ou salto.
- Citações legais (ex.: "Art. 31...") são separadas pelo mesmo critério. O
  recuo maior das citações é um sinal adicional, usado só se a calibração
  mostrar que ajuda.
- Os limiares não são valores fixos: derivam da margem do corpo e do
  espaçamento mediano de cada página, e são calibrados nos PDFs de teste.

### 4.2 `parsers/consultas.py`

- `parse(texto, texto_paragrafos=None)`: segundo parâmetro **opcional**.
- Todos os campos, exceto Resposta, continuam saindo de `texto`.
- A Resposta sai de `texto_paragrafos`: o parser fatia esse texto pelas mesmas
  âncoras (número e data da consulta), divide a Resposta em `MARCA_PARAGRAFO`,
  junta as linhas de cada parágrafo com espaço e separa os parágrafos com
  `\n\n`.
- Fallback: sem `texto_paragrafos`, se a âncora não for encontrada (ou for
  ambígua) no texto novo, ou se o texto com parágrafos, normalizado, não for
  **exatamente** igual à Resposta achatada, a Resposta sai achatada, como hoje.
  Essa igualdade é a salvaguarda de integridade: parágrafos só acrescentam
  quebras, nunca alteram conteúdo.

### 4.3 `core/pipeline.py`

- No ramo de consultas (linha 55), chama também `texto_com_paragrafos` e
  entrega o resultado ao parser. O PDF é aberto duas vezes (custo desprezível).
- O ramo de regimes não é tocado.

### 4.4 Banco

- Sem mudança de schema. A Resposta passa a conter `\n\n`.
- Consultas já mapeadas só ganham parágrafos quando o PDF for **reimportado**
  (o upsert atual atualiza sem duplicar).

### 4.5 Script de diagnóstico

`scripts/diag_consultas.py` usa `texto_simples`, que não muda. Nenhum efeito.

## 5. Exibição e exportação (só Resposta)

### 5.1 Tela de detalhe (`app.py::_mostra_detalhe`)

- Para a Resposta, o texto é dividido em `\n\n` e cada parágrafo é renderizado
  como `<p>` com o texto **escapado** (HTML-escape), evitando que o Markdown
  interprete `a)`, `50.` ou `I -` como lista.
- Recuo visual para citações via classe CSS: só se a detecção de citação se
  mostrar confiável na calibração; caso contrário, todos os parágrafos ficam
  iguais.
- Demais campos continuam com `st.write`; regimes não mudam.
- Registros antigos (sem `\n\n`) aparecem como um parágrafo só, sem tratamento
  especial.

### 5.2 Exportação .xlsx (`core/planilha.py`)

- O texto com `\n\n` entra na célula como está.
- `wrap_text=True` aplicado **apenas à coluna Resposta** das consultas.
- O limite de 32.767 caracteres por célula continua valendo.

## 6. Perfis de acesso

### 6.1 Fluxo

- O app abre numa **tela inicial** com duas opções: **Consulta** e
  **Administrador**. Logo e tema continuam visíveis.
- **Consulta**: entra sem login e vê apenas a aba "🔎 Consultar". A aba
  "Processar e mapear" e o bloco "Como funciona" da sidebar não aparecem.
- **Administrador**: pede senha. Correta: vê as duas abas, como hoje. Errada:
  aviso e permanece na tela inicial.
- Sidebar ganha o botão **Trocar perfil**.
- O perfil fica em `st.session_state`; atualizar a página volta à tela
  inicial.

### 6.2 Senha

- Arquivo `.streamlit/secrets.toml`:

  ```toml
  [admin]
  senha = "..."
  ```

- O `.gitignore` já ignora `.streamlit/*` exceto `config.toml`. Será liberado
  também `.streamlit/secrets.toml.example` (senha fictícia, só o formato).
- Arquivo ou chave ausente: o botão Administrador fica **desabilitado**, com a
  mensagem "senha do administrador não configurada". Nunca cai em acesso
  aberto.
- Comparação com `hmac.compare_digest`.

### 6.3 Código

- Módulo novo `core/acesso.py`: leitura da senha e verificação (testável sem
  interface).
- `app.py`: portão logo após o logo da sidebar e antes das abas; sem perfil
  escolhido, desenha a tela inicial e chama `st.stop()`.
- Defesa em profundidade: `_processar` também confere que o perfil é
  Administrador antes de gravar no banco.

### 6.4 Limites (documentar no README)

- Senha em texto puro no arquivo: protege contra uso acidental na interface,
  não contra quem tem acesso ao disco.
- `processar.py` (CLI) continua sem restrição; quem o executa já tem acesso à
  máquina.
- Sem bloqueio por tentativas erradas (ferramenta local em `127.0.0.1`).
- Na futura hospedagem multiusuário, armazenamento da senha e limite de
  tentativas devem ser revistos. O item "Autenticação/controle de acesso" da
  seção "Fora deste escopo" do README é atualizado para refletir o que passa a
  existir e o que continua pendente.

## 7. Testes

**Extração e parser**
- Resposta da Consulta 001/2026 sai com os parágrafos esperados (incluindo as
  citações do art. 31 e dos artigos do Decreto 11.003/2025).
- Regressão: nos PDFs de teste, Súmula, Problema, CNAE, Protocolo e o número
  de âncoras/registros são idênticos aos de antes da mudança.
- Regressão: registros de regime idênticos aos de antes.
- Fallback: `parse` sem `texto_paragrafos` devolve a Resposta achatada.
- Parágrafo que atravessa quebra de página não é partido indevidamente.

**Exibição e planilha**
- Célula Resposta contém `\n\n` e tem `wrap_text`; demais colunas e aba de
  regimes iguais.
- Tela: parágrafos separados; parágrafo iniciando com `a)` ou `1.` não vira
  lista.

**Perfis**
- `core/acesso.py`: senha correta, errada, vazia e ausente.
- `AppTest`: abre na tela inicial; perfil Consulta mostra só a aba Consultar;
  Administrador com senha errada é recusado; com senha certa mostra as duas
  abas; sem senha configurada o botão fica desabilitado.
- Testes atuais de `test_app.py` ajustados para entrar como Administrador.

## 8. Riscos

- Layouts de PDF diferentes dos três fixtures podem exigir ajuste dos
  limiares; por isso derivam da página e não são fixos.
- Parágrafo que começa no topo de uma página pode ser ambíguo; o recuo de
  primeira linha resolve a maioria dos casos.
- Consultas já mapeadas permanecem achatadas até a reimportação do PDF.
