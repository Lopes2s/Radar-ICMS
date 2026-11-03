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
