# Histórico de versões

## 0.10.1
- **Cópia local automática**: rodar o Python pela pasta de rede levava minutos para abrir. Agora `montar_rede.ps1` monta o programa numa pasta local, empacota num `.zip` versionado (`programa\`) e o `Radar ICMS.vbs` copia/atualiza o programa em `%LOCALAPPDATA%\RadarICMS` na primeira abertura e a cada versão nova. Só o banco, a trava e os backups continuam na rede.
- `montar_rede.ps1` não recusa mais atualizar com a ferramenta em uso (`-Forcar` removido) e pode rodar a qualquer hora.
- Nome visível da ferramenta: **Radar ICMS** (atalho `Radar ICMS.vbs`).

## 0.10.0
- **Compartilhamento pela rede**: código, Python portátil e banco ficam numa pasta de rede; cada pessoa abre por `Radar ICMS.vbs` (sem janela de console, sem instalar nada) e vê o mesmo banco. `scripts/montar_rede.ps1` monta e atualiza a pasta.
- O perfil **Consulta** abre o banco **somente leitura** (nunca cria nem migra o arquivo); se o banco não existe ou é de versão antiga, a tela pede ao Administrador abrir a ferramenta.
- **Gravar** passa a usar uma **trava de importação** (`importando.lock`, vence em 15 min): quem tenta gravar enquanto outra pessoa grava vê o nome e o horário. Antes de cada gravação é feito um **backup** em `backups/` (10 mais recentes). Conexões esperam até 30 s por bloqueio.
- Botão **Encerrar ferramenta** e desligamento automático do servidor local após 10 min sem navegador (só no atalho).
- Gravar (importação ou edição manual) **espera até 60 s** a vez quando outra pessoa está gravando (`MAPEADOR_ESPERA_TRAVA_S`). `montar_rede.ps1` recusa atualizar com a ferramenta em uso.
- Um segundo clique no atalho reabre o servidor já aberto; falhas de inicialização sem console aparecem numa caixa de mensagem. O log do atalho fica na máquina de cada usuário (`MAPEADOR_LOGS`).
- Robustez: pasta de rede fora do ar vira mensagem (não mais erro técnico), inclusive nas edições do detalhe; a trava tenta de novo ao ser removida quando o Windows a mantém aberta; clique duplo durante a partida espera o servidor em vez de subir outro. O backup cobre a importação (Gravar); edições manuais ficam no histórico por ato; `processar.py` grava sem a trava. Atalho com `python -B` (sem `.pyc` na pasta de rede).
- Schema do banco inalterado (4).

## 0.9.1
- **Correção no parser de regimes**: rótulos com espaço antes dos dois-pontos (ex.: `CAD/ICMS :61700643-03`, presente no Regime Especial nº 8.715/2025) não corrompem mais a EMPRESA nem deixam o CAD/ICMS vazio. Vale também para `CNPJ :`, `BENEFICIÁRIA :` e `EMENTA :`.
- **Correção no parser de consultas**: o rodapé de página com número de 3 dígitos (documentos de 100+ páginas) deixa de sobrar dentro dos campos.
- Novos avisos de diagnóstico: `A305` (nome da empresa que traz um rótulo do cabeçalho, como `CAD/ICMS:` ou `CNPJ:`) e `A306` (regime sem CAD/ICMS). Ambos aparecem antes de gravar e não bloqueiam.
- **Novo layout de regime**: o Regime Especial de Recolhimento do ICMS de Delegacia Regional (título sem ano, `CONTRIBUINTE:`/`Súmula`) passa a ser importado; antes o PDF resultava em `A401 — Nenhum registro extraído`. A vigência fica vazia quando o ato não declara prazo (aviso `A303`).
- Regimes já gravados com o defeito só se corrigem reimportando o PDF; os campos ajustados à mão são preservados pela reimportação.

## 0.9.0
- **Consulta do CNPJ na BrasilAPI**: ao gravar, o CNPJ de cada regime é consultado (CNAE principal e situação cadastral). O resultado fica à parte do regime e aparece no detalhe, para qualquer perfil.
- O CNAE da Receita é o **atual** da empresa, então nunca sobrescreve o regime sozinho: se o regime já tem um CNAE diferente, o detalhe avisa; o administrador pode **aplicar** o CNAE da Receita ao regime (fica no histórico como ajuste manual) e **atualizar** a consulta quando quiser.
- Falha de rede não impede a gravação: a consulta é refeita pelo botão do detalhe. Consultas com menos de 30 dias são reaproveitadas.
- Consulta desligável: `--sem-consulta-cnpj` na CLI ou `MAPEADOR_CONSULTA_CNPJ=0`. Só o CNPJ (dado público) sai da máquina; nenhuma dependência nova.
- Schema 4 (tabela `cnpj_receita`); bancos do schema 3 migram sozinhos.

## 0.8.0
- **Edição manual** pelo administrador, de consultas e regimes: no detalhe do ato (aba Consultar) e na análise, antes de gravar. Todos os campos podem ser editados, inclusive a chave (número e CNPJ).
- Na análise, a troca de chave confere o banco: é recusada se a chave nova já pertence a outro ato gravado ou se o ato já está gravado (nesse caso, corrija pelo detalhe em Consultar).
- Corrigir a chave não duplica o ato: a chave antiga vira apelido, então reimportar o PDF original cai no ato corrigido.
- Campos ajustados à mão **não são sobrescritos** pela reimportação. A análise lista os atos em conflito e o administrador marca quais sobrescrever com o PDF; na CLI, `--sobrescrever-ajustes`.
- O histórico do ato diz se a alteração veio de **importação** ou de **ajuste manual**.
- Schema 3 (`ajustes`, `chaves_substituidas` e `origem` no histórico); bancos do schema 2 migram sozinhos.

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
