# Mapeador de Consultas e Regimes Especiais — PR

Lê PDFs da SEFA-PR (consultas tributárias) e do Diário Oficial (regimes
especiais), extrai os campos objetivos e mapeia tudo num banco local
(`mapeamento.db`), consultável depois por uma interface Streamlit (busca
livre, por ano, por tipo). A planilha `.xlsx` continua disponível, mas como
exportação opcional — não é mais o produto final da ferramenta.

## Instalação
Requer Python 3.10+. A instalação manual é opcional:

    pip install -r requirements.txt

As dependências que faltarem são instaladas sozinhas no primeiro arranque
(veja *Bootstrap de dependências*).

## Uso (interface)
Clique duas vezes em **`Mapeador.bat`**. Ele prepara o ambiente e abre a
interface no navegador. A janela preta que aparece é o servidor: mantenha-a
aberta enquanto usar a ferramenta e feche-a para encerrar.

Pelo terminal, o equivalente é:

    python iniciar.py

O servidor escuta apenas em `127.0.0.1` — a ferramenta não fica exposta na rede
do escritório — e a telemetria do streamlit fica desligada. Se a porta 8501
estiver ocupada, a próxima livre é usada automaticamente.

Ao abrir, a interface mostra a **tela inicial** com dois perfis: **Consulta**
(entra direto; só a aba "🔎 Consultar") e **Administrador** (exige senha; abre
também a aba "📥 Processar e mapear", onde se importam PDFs). Na barra lateral
há o botão **Trocar perfil**, que volta à tela inicial. Atualizar a página
(F5) também volta à tela inicial, pois o perfil vive só na sessão.

## Perfis e senha do Administrador
A senha fica em `.streamlit/secrets.toml`, que não é versionado e precisa ser
criado em cada máquina onde a ferramenta for usada. Crie o arquivo com este
conteúdo, trocando a senha:

    [admin]
    senha = "troque-esta-senha"

Sem o arquivo (ou com a seção/chave ausente, vazia ou que não seja texto), o
perfil Administrador fica **desabilitado** — nunca cai em acesso aberto; o
perfil Consulta continua funcionando. A lógica está em `core/acesso.py`.

Limites, a rever na hospedagem multiusuário:
- a senha é texto puro no disco: protege contra uso acidental da interface,
  não contra quem tem acesso ao arquivo;
- `processar.py` (CLI) não tem restrição de perfil;
- não há bloqueio por tentativas erradas de senha.

## Uso (linha de comando)

    python processar.py <pasta_com_pdfs> [--banco arquivo.db] [--xlsx saida.xlsx]
                        [--dedup primeira|completo|recente] [--simular]

`--simular` lê e diagnostica os PDFs sem gravar nada. `--dedup` escolhe qual
registro fica quando o mesmo ato aparece em mais de um arquivo (padrão:
`primeira`). Códigos de saída: 0 = tudo certo; 1 = uso incorreto, nenhum PDF,
planilha aberta no Excel ou banco de versão mais nova; 2 = algum PDF falhou
(os demais foram gravados) — cada erro é listado, por arquivo, em stderr.

Sem `--banco`, usa `MAPEADOR_BANCO` se definido; senão `mapeamento.db` na pasta de dados (`MAPEADOR_DADOS`, padrão: a raiz do projeto). Reprocessar a mesma
pasta não duplica: cada consulta/regime já mapeado é atualizado (upsert pela
chave natural), não repetido. `--xlsx` é totalmente opcional — sem ele,
nenhuma planilha é gerada.

## Mapeamento e consulta (banco local)
Cada PDF processado (pela CLI ou pela interface) é mapeado num banco SQLite
local — `mapeamento.db` por padrão, na raiz do projeto. Não é dependência
nova: `sqlite3` é da biblioteca padrão do Python.

- A chave de cada tabela é a mesma chave natural que já evita duplicata
  dentro de um lote (`core/pipeline.CHAVE_CONSULTAS`/`CHAVE_REGIMES`):
  Ano + Nº da Consulta, e Nº do Regime Especial + CNPJ requerente.
- Reprocessar um PDF já mapeado **atualiza** o registro, não duplica — útil
  quando o parser é corrigido depois (já aconteceu mais de uma vez).
- O arquivo `mapeamento.db` não é versionado (está no `.gitignore`, como o
  `.xlsx` já estava). Trocar de máquina sem copiar esse arquivo perde o
  mapeamento acumulado.
- Na interface (`app.py`), a variável de ambiente `MAPEADOR_BANCO` aponta
  para um banco alternativo (usada pelos testes; sem ela, usa o padrão).
- A aba **Consultar** tem um botão para baixar os resultados da busca atual
  como `.xlsx` (`core/consulta.exportar_xlsx`) — a planilha continua no
  escopo, mas como extração a partir do que foi pesquisado, não mais como
  o produto de uma sessão de processamento.
- A **Resposta** das consultas é guardada com parágrafos (separados por
  `\n\n`), reconstruídos do layout do PDF; o detalhe na interface mostra um
  bloco por parágrafo e a planilha quebra linha na coluna Resposta.
  As **citações legais** (trechos de lei/decreto transcritos pelo fisco, em
  itálico e corpo menor no PDF) aparecem com recuo à esquerda na interface,
  para diferenciá-las do texto do fisco. A marcação usa um caractere
  invisível (`MARCA_CITACAO`, em `core/pdf_text.py`) no início do parágrafo:
  não há prefixo legível no texto guardado, e a planilha o descarta.
  Sem itálico nem fonte menor no PDF, nenhum parágrafo é tratado como citação.
- Consultas **já mapeadas** só ganham parágrafos ao **reimportar o PDF**
  (o upsert atualiza o registro, sem duplicar).

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

## Testes
As dependências de desenvolvimento ficam separadas das de uso:

    pip install -r requirements-dev.txt
    pytest -v

## Bootstrap de dependências
Cada ponto de entrada confere as bibliotecas de que precisa e instala as que
faltarem, usando as versões declaradas no `requirements.txt` — que segue sendo
a fonte única dos pinos.

- `processar.py` (CLI) instala apenas `pdfplumber` e `openpyxl`; não baixa a
  interface para gerar uma planilha em lote.
- `iniciar.py` instala também o `streamlit`. Ele existe porque
  `streamlit run app.py` exige que o streamlit já esteja presente: sem ele o
  comando nem chega a executar o `app.py`.

Uma biblioteca instalada numa versão fora da faixa do `requirements.txt`
(ex.: `streamlit` 1.30 quando o piso é 1.50) conta como ausente e é
atualizada. As faixas têm teto (`<0.12`, `<3.2`, `<2`) porque o resultado da
extração depende do comportamento do `pdfplumber`: uma versão nova poderia
mudar o texto extraído sem erro nenhum. Para subir um teto, rode a suíte de
testes com a versão nova antes de alterar o `requirements.txt`.

Quando nada falta, a verificação é um `find_spec` e uma leitura de metadados
por pacote, sem subprocesso — não há custo perceptível nem saída na tela.

Para exigir um ambiente já preparado (CI, imagem congelada), defina
`MAPEADOR_SEM_AUTOINSTALL=1`: em vez de instalar, a ferramenta falha dizendo o
que falta e qual comando resolve.

## Distribuição
Para entregar a ferramenta a outra máquina, gere o pacote pelo git — ele
leva só os arquivos versionados, sem a pasta `.git` (que contém dados do
autor) nem caches:

    git archive --format=zip -o mapeador_pr.zip HEAD

O Mapeador.bat cria um .venv na pasta da ferramenta na primeira execução (precisa de internet nessa vez).

## Estrutura
- core/pdf_text.py  — extração de texto (1 coluna, 2 colunas, detecção de fonte);
  `texto_com_paragrafos` reconstrói os parágrafos da Resposta
- core/acesso.py    — perfis (Consulta/Administrador) e conferência da senha
- parsers/consultas.py — parser das consultas
- parsers/regimes.py   — parser dos regimes (filtra concessões/alterações)
- core/pipeline.py  — processamento por arquivo e lote, comum à CLI e à interface
- core/armazenamento.py — persistência SQLite (upsert por chave natural)
- core/consulta.py  — busca unificada por tipo, para a interface
- core/planilha.py  — geração do .xlsx (exportação opcional)
- core/bootstrap.py — verificação e instalação das dependências
- app.py / processar.py — interface e CLI
- iniciar.py — abre a interface preparando o ambiente antes
- core/execucao.py  — execução completa (carregar → diagnosticar → gravar), usada pela CLI e pela interface
- core/diagnostico.py — erros e avisos do lote antes de gravar
- core/texto.py     — normalização de texto para a busca
- core/log.py       — log em arquivo
- core/versao.py    — versão do app
- Mapeador.bat — atalho de duplo-clique para o iniciar.py

## Fora deste escopo (fase 2)
- Camada de IA: tema/segmento, favorável/desfavorável, potencial, resumo.
  Os campos-placeholder que existiam para isso foram removidos dos parsers
  (não apenas deixados vazios) — reintroduzi-los, se um dia fizer sentido,
  exige adicionar campo e coluna de novo, não só implementar a análise.
- Enriquecimento de CNAE via CNPJ (BrasilAPI) com cache local. Os campos
  `CNAE REQUERENTE`/`DESCRIÇÃO CNAE` (regimes) continuam reservados, vazios,
  para isso — confirmado: uma base com CNPJ/CNAE será encaminhada depois
  para preencher essas colunas.
- Vínculo com a carteira de clientes.
- Controle de acesso além do perfil Administrador com senha local (ver
  *Perfis e senha do Administrador*). Continuam pendentes: usuários
  individuais, hospedagem fora da rede interna (o servidor continua só em
  `127.0.0.1`) e banco em rede — os dados mapeados são públicos
  (SEFA-PR/Diário Oficial), mas essa mudança não foi decidida.
  **Planejado para depois:** hospedar a ferramenta para uso simultâneo por
  vários usuários, com banco de dados em rede. Isso implica trocar o SQLite
  local (`core/armazenamento.py`) por um banco cliente-servidor (o caminho
  natural é PostgreSQL) — ver explicação detalhada na conversa de
  implantação; não implementado nesta rodada.

## Limitações conhecidas
- Padrões de vigência cobrem os casos vistos; podem existir outros no histórico.
- Layouts de PDF muito diferentes dos fixtures podem exigir ajuste dos
  limiares de `_marca_paragrafos_da_pagina` (`core/pdf_text.py`); se a
  detecção falhar, a Resposta cai no texto achatado de sempre.
