# Edição manual de consultas e regimes — design

Data: 2026-11-02 · Escopo: `mapeador_pr` (interface Streamlit, motor e CLI).

## Problema
O administrador só consegue **importar** PDFs. Quando a importação aponta erros (vigência ou data de
regime vazias, CNPJ inválido, consulta sem resposta etc.) ou o parser extrai algo errado, não há como
corrigir o dado: só reimportar, o que devolve o mesmo erro.

## Decisões do usuário (fechadas)
1. **Escopo:** consultas **e** regimes.
2. **Onde editar:** nos dois momentos — no **detalhe** de um ato já gravado (aba Consultar) e na
   **análise**, antes de gravar.
3. **Reimportação de um ato editado:** **avisar e deixar escolher.** A análise destaca os atos com
   ajuste manual e o administrador decide, ato a ato, se o PDF sobrescreve. Padrão: manter o ajuste.
4. **Campos:** todos, **inclusive a chave** (nº e CNPJ do regime; ano e nº da consulta).

## Desenho
- **Quem edita:** só o perfil Administrador (a interface não oferece edição ao perfil Consulta e as
  funções que gravam exigem o perfil). Regras de edição em `core/edicao.py`, sem Streamlit.
- **Ajustes (`ajustes`):** cada edição marca os campos corrigidos à mão (por ato). A reimportação **não
  sobrescreve** esses campos, mas atualiza os demais. Para sobrescrever, o administrador marca o ato
  (interface) ou usa `--sobrescrever-ajustes` (CLI); aí o PDF vence e os ajustes do ato são apagados.
- **Chave corrigida (`chaves_substituidas`):** a chave antiga vira **apelido** da nova (cadeias
  achatadas). Reimportar o PDF original cai no ato corrigido em vez de criar um duplicado. Chave nova
  que já pertence a outro ato é **recusada**; chave em branco também.
- **Histórico:** cada edição guarda a versão anterior com `origem = 'manual'` (a reimportação continua
  `'importacao'`); a interface mostra qual foi qual.
- **Tudo ou nada:** a edição de um ato grava histórico, valores, ajustes, troca de chave e apelido numa
  transação só; se falhar, nada fica gravado.
- **Na análise** a edição só altera o `Lote` em memória (nada vai ao banco até **Gravar**); o
  diagnóstico é refeito na hora. Ao gravar, o que foi ajustado vira `ajustes` e as chaves corrigidas
  viram apelidos, então a reimportação seguinte já respeita a correção.
- **Schema 3:** tabelas `ajustes` e `chaves_substituidas` e coluna `historico.origem`. Migração aditiva:
  bancos do schema 2 abrem sem perder dados (linhas antigas do histórico ficam como `importacao`).

## Contratos que NÃO mudam
- `salvar_consultas`/`salvar_regimes` → `{'novos': N, 'atualizados': M}`; `persistir_lote` →
  `{'consultas': {...}, 'regimes': {...}}`.
- Linhas de `lote.arquivos` com as 6 chaves; dicts dos parsers sem chaves novas; `resultado` da sessão
  com as 6 chaves; `armazenamento._CAMINHO_PADRAO`.
- CLI: `Uso:` em stdout com código 1; códigos de saída 0/1/2 como hoje.

## Armadilhas conhecidas
- O Streamlit não deixa alterar o estado de um widget depois de desenhado na mesma execução. O
  salvamento do detalhe roda no `on_click` do formulário (executa antes do script) para poder fechar o
  detalhe zerando a seleção da tabela.
- No `AppTest` a seleção de linha injetada não persiste entre execuções; os testes reinjetam a linha.

## Fora do escopo
Excluir atos; editar em lote; restaurar uma versão anterior com um clique; registrar **quem** editou
(há um único perfil administrador com senha); bloquear valores fora do padrão na edição de um ato já
gravado.
