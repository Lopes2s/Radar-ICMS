# Melhorias alinhadas ao padrão do hub — design

Data: 2026-11-02 · Escopo: `mapeador_pr` (a ferramenta **não** será indexada no hub; só adota os
padrões dele para ficar pronta caso isso aconteça).

## Objetivo
Dar à ferramenta o mesmo desenho do hub Martinelli Ferramentas: motor sem interface com callback de
progresso, diagnóstico antes de gravar, proveniência dos dados, logging, schema versionado e CLI com
códigos de saída significativos — sem quebrar o comportamento testado hoje (184 testes).

## Decisões do usuário (fechadas)
1. **Reimportação:** sempre atualiza o registro e guarda a versão anterior numa tabela `historico`
   quando algum campo mudar. Não há bloqueio de sobrescrita com valor vazio.
2. **Duplicados no lote:** o usuário escolhe o critério — `primeira` (padrão, comportamento atual),
   `completo` (mais campos preenchidos) ou `recente` (maior data; empate: o último processado).
   Na interface é um seletor; na CLI, `--dedup`.
3. **Cancelamento (Opção A):** só progresso (callback + barra) e Ctrl+C na CLI. Não há botão
   Cancelar no Streamlit. É seguro porque a gravação só acontece depois da leitura de todo o lote.
4. **Erros de PDF:** a CLI sai com código **2** se algum PDF falhar (os demais continuam sendo
   gravados) e cada erro é mostrado por arquivo, com o motivo, em stderr (CLI) e em destaque (UI).

## Dentro do escopo
Pasta de dados configurável · conexão aberta e fechada a cada uso · `PRAGMA user_version` ·
logging rotativo · exportação `.xlsx` só ao clicar · busca sem acento/caixa e em mais campos ·
listagem leve com detalhe sob demanda · critério de dedup · proveniência (`importacoes`) e
`historico` · diagnóstico estruturado · classe `Execucao` · CLI (`--dedup`, `--simular`, código 2) ·
fluxo "Analisar → Gravar" na interface · `.venv` local no `.bat` · versão do app.

## Fora do escopo (decidido não fazer agora)
- Pool de processos e botão Cancelar (Opções B/C).
- `argparse` na CLI (o parser manual preserva "Uso:" em stdout e código 1, que os testes fixam).
- Correção dos campos vazios de regimes (vigência/data): bug de parser, tratar em plano próprio com
  PDFs reais.
- Fonte Urbanist local (exige baixar arquivos e confirmar a sintaxe do tema do Streamlit 1.63).
- Escapar Markdown do texto dos regimes; remover `scripts/diag_consultas.py`; limpar `docs/`.

## Contratos que NÃO podem mudar (fixados pelos testes atuais)
- `salvar_*` devolve exatamente `{'novos': N, 'atualizados': M}`; `persistir_lote` devolve
  `{'consultas': {...}, 'regimes': {...}}`.
- Cada linha de `lote.arquivos` tem exatamente 6 chaves: `Arquivo, Tipo, Consultas, Regimes,
  Descartes, Erro`.
- Os dicts de registro dos parsers não ganham chaves (o teste de pipeline compara campo a campo).
- `st.session_state["resultado"]` mantém as chaves `arquivos, consultas, regimes, descartes,
  mapeamento, xlsx`.
- `armazenamento._CAMINHO_PADRAO` continua existindo e terminando em `mapeamento.db`.
- A CLI mantém `Uso:` em stdout com código 1 para uso incorreto, e código 1 para planilha aberta.
