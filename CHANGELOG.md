# Histórico de versões

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
