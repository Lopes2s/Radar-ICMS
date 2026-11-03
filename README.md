# Mapeador de Consultas e Regimes Especiais — PR

Ferramenta local que lê PDFs da SEFA-PR (consultas tributárias) e do Diário
Oficial (regimes especiais), extrai os campos objetivos, mapeia tudo num banco
SQLite e permite consultar o que foi mapeado por uma interface web (Streamlit).

Versão atual: **0.8.0** (histórico em [`CHANGELOG.md`](CHANGELOG.md)).

## Sumário
1. [O que a ferramenta faz](#1-o-que-a-ferramenta-faz)
2. [Início rápido](#2-início-rápido)
3. [Interface](#3-interface)
4. [Linha de comando](#4-linha-de-comando)
5. [Dados, banco e histórico](#5-dados-banco-e-histórico)
6. [O que é extraído](#6-o-que-é-extraído)
7. [Arquitetura](#7-arquitetura)
8. [Dependências e bootstrap](#8-dependências-e-bootstrap)
9. [Testes](#9-testes)
10. [Distribuição](#10-distribuição)
11. [Limitações conhecidas](#11-limitações-conhecidas)
12. [Desenvolvimento futuro](#12-desenvolvimento-futuro)

---

## 1. O que a ferramenta faz
- **Importa** PDFs de consultas e de regimes especiais (detecta o tipo pelo
  conteúdo; é possível forçar o tipo na interface).
- **Analisa antes de gravar**: mostra, por arquivo, erros de leitura, CNPJ
  inválido, campos vazios e datas fora do padrão, sem alterar o banco.
- **Mapeia** os atos num banco SQLite local, sem duplicar: reimportar atualiza o
  registro e guarda a versão anterior num histórico.
- **Consulta** o banco por tipo, ano e texto livre (sem diferenciar acentos nem
  maiúsculas), com o detalhe completo de cada ato.
- **Exporta** para `.xlsx` (planilha da sessão de importação ou resultados da
  busca atual) — exportação opcional, o produto é o banco.

## 2. Início rápido
Requer **Python 3.10+** e Windows para o atalho `.bat`.

1. Clique duas vezes em **`Mapeador.bat`**. Na primeira execução ele cria um
   ambiente isolado (`.venv`, precisa de internet nessa vez), instala as
   dependências que faltarem e abre a interface no navegador.
2. A janela preta que aparece é o servidor: mantenha-a aberta enquanto usar a
   ferramenta e feche-a para encerrar.
3. Para o perfil **Administrador** (importar PDFs), crie a senha — ver
   [Perfis e senha](#perfis-e-senha-do-administrador).

Pelo terminal, o equivalente é `python iniciar.py`. O servidor escuta apenas em
`127.0.0.1` (a ferramenta não fica exposta na rede do escritório), a telemetria
do Streamlit fica desligada e, se a porta 8501 estiver ocupada, a próxima livre
é usada.

Instalação manual das dependências (opcional):

```bash
pip install -r requirements.txt
```

## 3. Interface
O visual segue o **Design System Martinelli** (`showcase-design-martinelli.html`):
logo Martinelli na lateral, fonte Urbanist, cartões, indicadores e abas no
mesmo padrão dos demais artefatos do escritório.

- **Tema claro e escuro**: o Streamlit escolhe pelo sistema; também dá para
  trocar em ⋮ → *Settings*. O logo muda sozinho (escuro no tema claro, branco
  no escuro).
- **Cores com função**: azul é a ação principal; verde indica conclusão, âmbar
  indica aviso e vermelho indica erro — nunca só enfeite.
- Botões e campos mostram anel de foco azul ao navegar pelo teclado.
- O menu ⋮ mostra só opções de visualização (tema, imprimir); as de
  desenvolvedor (Deploy, Rerun, Clear cache) ficam ocultas.

O **login** aparece centralizado na tela, em duas etapas:

1. **Escolha do perfil**: *Consulta* entra direto; *Administrador* segue para a
   senha (fica desabilitado enquanto a senha não estiver configurada).
2. **Senha** (só do Administrador): Enter ou **Entrar** confirma; **Voltar**
   retorna à escolha do perfil.

O botão **Trocar perfil**, na barra lateral, volta à escolha do perfil;
atualizar a página (F5) também, pois o perfil vive só na sessão.

| Perfil | Acesso | Abas |
|---|---|---|
| **Consulta** | direto, sem senha | Consultar |
| **Administrador** | exige senha | Processar e mapear + Consultar |

### Perfis e senha do Administrador
A senha fica em `.streamlit/secrets.toml`, que não é versionado e precisa ser
criado em cada máquina onde a ferramenta for usada:

```toml
[admin]
senha = "troque-esta-senha"
```

Sem o arquivo (ou com a seção/chave ausente, vazia ou que não seja texto), o
perfil Administrador fica **desabilitado** — nunca cai em acesso aberto; o
perfil Consulta continua funcionando. A lógica está em `core/acesso.py`.

Limites conhecidos:
- a senha é texto puro no disco: protege contra uso acidental da interface, não
  contra quem tem acesso ao arquivo;
- a CLI (`processar.py`) não tem restrição de perfil;
- não há bloqueio por tentativas erradas de senha.

### Aba "Processar e mapear" (Administrador)
1. Envie os PDFs. Na barra lateral, **Tipo do PDF** permite *detectar
   automaticamente* ou forçar *Consulta* / *Regime*.
2. Escolha o critério para **o mesmo ato aparecer em mais de um arquivo**:
   *Primeira ocorrência* (padrão; a do primeiro arquivo, em ordem alfabética),
   *Mais completo* (o registro com mais campos preenchidos) ou *Mais recente*
   (a maior data de publicação; empate: o último processado).
3. **Analisar** lê os PDFs e mostra o diagnóstico. **Nada é gravado ainda.**
   Cada arquivo com erro aparece com o nome e o motivo, e não impede os demais.
   Se os arquivos enviados mudarem depois da análise, ela é descartada.
4. **Gravar no banco** (habilitado quando há ao menos um registro) persiste o
   lote e mostra o resumo: quantos atos são novos e quantos foram atualizados.
   Daí é possível baixar a planilha da sessão.

Códigos do diagnóstico:

| Código | Nível | Significado |
|---|---|---|
| `E001` | erro | arquivo ilegível (mostra o motivo; não bloqueia a gravação dos demais) |
| `A001` | aviso | tipo de arquivo não identificado |
| `A201` / `A202` / `A203` | aviso | consulta sem resposta / sem súmula / data fora de AAAA-MM-DD |
| `A301` / `A302` | aviso | regime sem CNPJ do requerente / CNPJ inválido (dígitos verificadores) |
| `A303` / `A304` | aviso | regime sem vigência / data fora de AAAA-MM-DD |
| `A401` | aviso | nenhum registro extraído (bloqueia a gravação) |

### Aba "Consultar"
- No topo, quatro **indicadores**: consultas mapeadas, regimes mapeados, anos
  cobertos e data da última importação.
- Filtros: **tipo de ato**, **busca textual** e **ano**. A busca ignora acentos e
  maiúsculas e trata `%` e `_` como texto comum.
  - Consultas: nº da consulta, súmula, problema, CNAE e resposta.
  - Regimes: nº do regime, empresa, CNPJ, ementa e benefícios/procedimentos.
- A tabela mostra só colunas curtas. **Selecione uma linha** para abrir o
  detalhe completo (campo a campo) e, se houver, o **histórico de alterações**.
- Sem resultados, aparece um aviso explicando o motivo (filtros sem retorno ou
  banco ainda vazio).
- **Baixar estes resultados (.xlsx)** gera a planilha só quando você clica.

### Edição manual (Administrador)
O administrador corrige consultas e regimes em dois momentos:

- **Depois de gravado**: na aba Consultar, abra o detalhe do ato e use **Editar**. Todos os campos são editáveis, inclusive a chave (número e CNPJ do regime; ano e número da consulta). Se a chave nova já pertencer a outro ato, a edição é recusada e nada muda.
- **Na análise, antes de gravar**: em *Ajustar um ato antes de gravar*, escolha o ato apontado nos avisos e corrija os campos. O diagnóstico é refeito na hora e nada vai ao banco até **Gravar**. Aqui a chave só pode ser corrigida em ato que ainda não está gravado; uma chave que já pertence a outro ato gravado é recusada, e para corrigir a chave de um ato já gravado use o detalhe na aba Consultar.

Cada edição guarda a versão anterior no histórico do ato (origem *ajuste manual*) e marca os campos editados como **ajustados**. Ao reimportar o PDF:

- os campos ajustados **não são sobrescritos** — a análise lista os atos em conflito e você marca *Sobrescrever com o PDF* só nos que quiser (por padrão, nenhum);
- se a chave foi corrigida, o PDF original **cai no ato corrigido** em vez de criar um duplicado.

## 4. Linha de comando

```bash
python processar.py <pasta_com_pdfs> [--banco arquivo.db] [--xlsx saida.xlsx]
                    [--dedup primeira|completo|recente] [--simular]
                    [--sobrescrever-ajustes]
```

| Opção | Efeito |
|---|---|
| `--banco` | banco a usar; sem ela: `MAPEADOR_BANCO`, senão `mapeamento.db` na pasta de dados |
| `--xlsx` | grava também uma planilha (sem ela, nenhuma planilha é gerada) |
| `--dedup` | critério para o mesmo ato em mais de um arquivo (padrão: `primeira`) |
| `--simular` | lê e diagnostica os PDFs **sem gravar nada** |
| `--sobrescrever-ajustes` | o valor do PDF vence também nos campos que o administrador ajustou à mão (por padrão o ajuste é mantido e a CLI avisa) |

A pasta é a primeira informação da linha de comando. Os PDFs são processados em
ordem alfabética.

| Código | Quando |
|---|---|
| `0` | tudo certo |
| `1` | uso incorreto, nenhum PDF na pasta, planilha aberta no Excel ou banco de versão mais nova |
| `2` | algum PDF falhou — os demais foram gravados; cada erro é listado, por arquivo, em stderr |

Reprocessar a mesma pasta não duplica: cada consulta/regime já mapeado é
atualizado (ver [seção 5](#5-dados-banco-e-histórico)).

## 5. Dados, banco e histórico
O banco é um SQLite local (`sqlite3` da biblioteca padrão).

### Onde ficam os arquivos
| Variável | Efeito |
|---|---|
| `MAPEADOR_DADOS` | pasta do banco e dos logs (padrão: a raiz do projeto; criada se não existir) |
| `MAPEADOR_BANCO` | caminho de um banco específico (vale na interface e na CLI) |
| `MAPEADOR_SEM_AUTOINSTALL` | `1` = não instala dependências; falha dizendo o que falta |

O banco (`mapeamento.db`) e os logs não são versionados. **Trocar de máquina sem
copiar o `mapeamento.db` perde o mapeamento acumulado.**

Log: `<dados>/logs/app.log` (rotativo, ~1 MB × 3), com o traceback das falhas de
PDF.

### Chave natural e reimportação
- Consultas: **Ano + Nº da Consulta**. Regimes: **Nº do Regime Especial + CNPJ
  do requerente**.
- Reimportar um ato **atualiza** o registro, não duplica — útil quando o parser é
  corrigido depois. O valor novo sempre vence, exceto nos campos ajustados à mão
  (ver [Edição manual](#edição-manual-administrador)).
- Se algum campo mudar, a linha anterior é guardada na tabela **`historico`**
  (campos alterados, valor anterior, data UTC, versão do app e a **origem**: *importação* ou *ajuste manual*) e aparece em
  "Histórico de alterações" no detalhe. Reimportar um registro idêntico não gera
  histórico.
- Cada PDF importado é registrado em **`importacoes`** (nome, SHA-256, tipo,
  quantidade de atos, data e versão do app).

### Versão do schema
O banco guarda a versão do schema em `PRAGMA user_version` (atual: 3). Bancos
antigos são atualizados sem perder dados (só se acrescentam tabelas/colunas). Um
banco criado por uma versão **mais nova** é recusado, sem nenhuma alteração, com
uma mensagem pedindo para atualizar a ferramenta.

## 6. O que é extraído
**Consultas** (tabela `consultas`): Ano, Nº da Consulta, Data da Publicação,
Protocolo, Súmula, Problema da Consulta, CNAE Detectado e Resposta.

**Regimes especiais** (tabela `regimes`): Ano, Data, Nº DOE, RE PR Competitivo,
Nº do Regime Especial, Empresa, CNPJ e CAD/ICMS do requerente, Vigência, Ementa,
Abrangência, Benefícios/Procedimentos e Disposições Gerais. O parser considera
concessões e alterações e registra o motivo dos descartes. As colunas `CNAE
REQUERENTE` e `DESCRIÇÃO CNAE` existem no banco, mas **não são preenchidas**.

### Resposta em parágrafos e citações legais
A Resposta das consultas é guardada com parágrafos (separados por `\n\n`),
reconstruídos do layout do PDF; o detalhe mostra um bloco por parágrafo e a
planilha quebra linha na coluna. As **citações legais** (trechos de lei/decreto
transcritos pelo fisco, em itálico e corpo menor) aparecem com recuo na
interface. A marcação usa um caractere invisível (`MARCA_CITACAO`, em
`core/pdf_text.py`) no início do parágrafo: não há prefixo legível no texto
guardado e a planilha o descarta. Sem itálico nem fonte menor no PDF, nenhum
parágrafo é tratado como citação. Consultas já mapeadas só ganham parágrafos ao
**reimportar o PDF**.

### Planilha `.xlsx`
A planilha da sessão tem as abas *Consultas — a revisar*, *Regimes — a revisar*,
*Log de descartes* e *Arquivos processados* (só as que tiverem conteúdo). A
exportação da aba Consultar traz apenas a aba do tipo pesquisado.

## 7. Arquitetura
O motor (`core/`, `parsers/`) não depende do Streamlit: a CLI e a interface usam
o mesmo caminho — `Execucao` → `pipeline` → `armazenamento`.

| Arquivo | Responsabilidade |
|---|---|
| `core/pdf_text.py` | extração de texto (1 e 2 colunas, detecção de fonte); `texto_com_paragrafos` reconstrói os parágrafos |
| `parsers/consultas.py` | parser das consultas |
| `parsers/regimes.py` | parser dos regimes (filtra concessões/alterações) |
| `core/pipeline.py` | processamento por arquivo e lote; critério de duplicados; hash e origem de cada ato |
| `core/diagnostico.py` | erros e avisos do lote antes de gravar |
| `core/execucao.py` | execução completa (carregar → diagnosticar → gravar) com callback de progresso |
| `core/armazenamento.py` | SQLite: upsert pela chave natural, histórico, importações, schema versionado, busca |
| `core/consulta.py` | busca por tipo, lista leve, detalhe, histórico e exportação |
| `core/texto.py` | normalização de texto para a busca |
| `core/planilha.py` | geração do `.xlsx` |
| `core/acesso.py` | perfis (Consulta/Administrador) e conferência da senha |
| `core/log.py` | log em arquivo |
| `core/versao.py` | versão do app (`VERSAO_APP`) |
| `core/bootstrap.py` | verificação e instalação das dependências |
| `app.py` | interface Streamlit |
| `processar.py` | linha de comando |
| `iniciar.py` | abre a interface preparando o ambiente antes |
| `Mapeador.bat` | atalho de duplo clique para `iniciar.py` |
| `interface/design.py` | Design System Martinelli: tokens claro/escuro, CSS dos componentes e blocos de HTML (marca, cabeçalho, estado vazio) |
| `interface/icones.py` | ícones do showcase usados nos indicadores e cartões |
| `.streamlit/config.toml` | tema nativo do Streamlit (claro e escuro), fonte Urbanist e barra de ferramentas |
| `assets/` | logos Martinelli (escuro e branco) |
| `scripts/diag_consultas.py` | diagnóstico manual do parser de consultas |

## 8. Dependências e bootstrap
Faixas declaradas em `requirements.txt` (fonte única dos pinos):

| Pacote | Faixa |
|---|---|
| `pdfplumber` | `>=0.11.9,<0.12` |
| `openpyxl` | `>=3.1.5,<3.2` |
| `streamlit` | `>=1.63,<2` |

As faixas têm teto porque o resultado da extração depende do comportamento do
`pdfplumber`: uma versão nova poderia mudar o texto extraído sem erro nenhum.
Para subir um teto, rode a suíte de testes com a versão nova antes de alterar o
`requirements.txt`.

Cada ponto de entrada confere as bibliotecas de que precisa e instala as que
faltarem:
- `processar.py` (CLI) instala apenas `pdfplumber` e `openpyxl`;
- `iniciar.py` instala também o `streamlit` (sem ele, `streamlit run app.py` nem
  chegaria a executar o `app.py`).

Uma biblioteca instalada fora da faixa (ex.: `streamlit` 1.30 quando o piso é
1.63) conta como ausente e é atualizada. Quando nada falta, a verificação é um
`find_spec` e uma leitura de metadados por pacote, sem subprocesso. Para exigir
um ambiente já preparado (CI, imagem congelada), use
`MAPEADOR_SEM_AUTOINSTALL=1`.

## 9. Testes
As dependências de desenvolvimento ficam separadas das de uso:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

A suíte tem 357 testes e leva cerca de um minuto. Os testes usam uma pasta de
dados temporária (`tests/conftest.py`), nunca o banco real do projeto.

## 10. Distribuição
Hoje a entrega é pelo git — só os arquivos versionados, sem a pasta `.git` (que
contém dados do autor) nem caches:

```bash
git archive --format=zip -o mapeador_pr.zip HEAD
```

Na máquina de destino, `Mapeador.bat` cria o `.venv` na primeira execução (precisa
de internet nessa vez). O `.streamlit/secrets.toml` e o `mapeamento.db` precisam
ser criados/copiados à parte (não são versionados).

## 11. Limitações conhecidas
- Os padrões de vigência dos regimes cobrem os casos vistos; podem existir
  outros no histórico do Diário Oficial.
- Layouts de PDF muito diferentes dos fixtures podem exigir ajuste dos limiares
  de `_marca_paragrafos_da_pagina` (`core/pdf_text.py`); se a detecção falhar, a
  Resposta cai no texto achatado de sempre.
- O banco é local (SQLite, um usuário por vez); a senha do Administrador é texto
  puro no disco (ver [Perfis e senha](#perfis-e-senha-do-administrador)).

## 12. Desenvolvimento futuro
O único item planejado é a **criação de um executável em binário** da
ferramenta, a ser feita depois de concluídas as otimizações. Até lá, a
distribuição segue como descrito na [seção 10](#10-distribuição).
