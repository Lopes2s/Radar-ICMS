# Consulta do CNPJ na BrasilAPI — design

Data: 2026-11-03 · Escopo: `mapeador_pr` (motor, CLI e interface Streamlit).

## Problema
O regime especial identifica a empresa beneficiária só pelo CNPJ. O parser deixa `CNAE REQUERENTE` e
`DESCRIÇÃO CNAE` **sempre em branco** (o PDF não traz o CNAE), então a base não diz em que atividade a
empresa atua. A BrasilAPI (`GET https://brasilapi.com.br/api/cnpj/v1/{cnpj}`, pública, sem chave) devolve o
CNAE principal (`cnae_fiscal`, `cnae_fiscal_descricao`), a lista de secundários e a situação cadastral
(`descricao_situacao_cadastral`). Conferido em 2026-11-03: HTTP 200 para um CNPJ válido, HTTP 400 para um inválido.

## Decisões do usuário (fechadas)
1. **Quando consultar:** automaticamente **ao gravar** (CLI e interface).
2. **O que fazer com o resultado:** **mostrar e apontar divergência** (não sobrescrever o regime).
3. **O que guardar:** CNAE principal (código e descrição) + situação cadastral + data da consulta.
4. **Privacidade:** enviar os CNPJs a um serviço público de terceiros é aceitável (dados públicos).

## Decisões de desenho (rulings deste plano)
- **Guardar à parte.** O resultado vai para a tabela `cnpj_receita` (chave: CNPJ só dígitos), não para as
  colunas do regime. O CNAE da Receita é o **atual** da empresa e pode diferir do vigente na data do regime.
- **Divergência só com CNAE informado.** Como o PDF não traz CNAE, a coluna do regime costuma estar vazia; vazio
  **não** é divergência. Há aviso quando o regime tem um CNAE (por edição manual) diferente do da Receita.
- **Aplicar é decisão do administrador.** Botão "Aplicar CNAE da Receita ao regime" grava `CNAE REQUERENTE` e
  `DESCRIÇÃO CNAE` por `edicao.editar_registro` (histórico `manual`, campos marcados como ajustados — a
  reimportação não os desfaz).
- **Botão "Consultar CNPJ / Atualizar consulta"** no detalhe (só administrador): é a saída quando a consulta
  automática falhou (sem internet) ou quando se quer dados novos.
- **Falha de rede nunca bloqueia a gravação.** A consulta roda DEPOIS de `persistir_lote`; não levanta por
  internet fora do ar, timeout, HTTP 4xx/5xx ou resposta ilegível; o resumo diz o que aconteceu (aviso na tela,
  linha `Receita:` na CLI). Duas falhas de conexão seguidas interrompem o resto do lote.
- **Reaproveitamento:** consulta com menos de 30 dias não se repete; CNPJ repetido no lote é consultado uma vez;
  CNPJ em branco ou inválido (dígitos verificadores) não vai para a rede. Pausa de 0,3 s entre consultas reais.
- **Desligável:** `--sem-consulta-cnpj` (CLI) e `MAPEADOR_CONSULTA_CNPJ=0` (ambiente). `--simular` nunca consulta.
- **Sem dependência nova:** `urllib` da biblioteca padrão; `User-Agent` genérico `mapeador-pr`.
- **Testes sem rede:** `conftest` fixa `MAPEADOR_CONSULTA_CNPJ=0`; os testes que consultam ligam a variável e
  injetam um `abrir` falso. `core/cnpj._abrir` é o único ponto que toca a rede.
- **Schema 4:** migração aditiva (só cria `cnpj_receita`); bancos do schema 3 abrem sem perder dados.

## Contratos que NÃO mudam
`salvar_*` → `{'novos','atualizados'}`; `persistir_lote` → `{'consultas','regimes'}`; 6 chaves em
`lote.arquivos`; dicts dos parsers; 6 chaves de `st.session_state["resultado"]`; `_CAMINHO_PADRAO`; CLI
(`Uso:` em stdout código 1; saídas 0/1/2).

## Armadilhas conhecidas
- Os botões do detalhe rodam no `on_click` (Streamlit não permite alterar estado de widget já desenhado).
- A API pública não documenta limite fixo de uso nem garante disponibilidade.

## Fora do escopo
CNAEs secundários; razão social na tela; histórico das consultas; preencher o CNAE do regime automaticamente;
CNPJ alfanumérico (formato novo da Receita — parser e validador atuais só leem dígitos); consultas (não têm
CNPJ); CNAE da Receita na planilha; proxy corporativo; repetição automática das consultas pendentes.
