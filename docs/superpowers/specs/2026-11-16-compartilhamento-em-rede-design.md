# Compartilhamento pela rede do escritório — Design

Data: 2026-11-16 · Versão alvo: 0.10.0

## Problema
A ferramenta roda por `Mapeador.bat` (cria `.venv`, abre uma janela de console, um
banco por cópia). A equipe precisa usá-la com o mínimo de passos, vendo todos os
mesmos dados, e o escritório não tem servidor nem IP fixo — só uma pasta de rede
compartilhada, acessível por todos no mesmo caminho (letra de unidade ou
`\\servidor\pasta`), em Windows 64 bits, sem bloqueio de executar programas da rede.

## Decisões já tomadas
- **Cada pessoa roda o servidor na própria máquina** (`127.0.0.1`), com código,
  Python portátil e banco **na pasta de rede**. Nada é exposto na rede.
- **Só uma ou duas pessoas importam.** Escrita simultânea é tratada com trava e
  espera, não com um servidor de banco.
- Perfil Consulta lê o banco em modo somente leitura; só o Administrador grava.

## Estrutura na rede
```
\\rede\Mapeador\
  Mapeador.vbs      atalho de duplo clique (janela oculta)
  app\              código versionado + python\ (Python embeddable com as dependências)
  dados\            mapeamento.db, backups\
```
Logs e o registro do servidor ficam **na máquina de cada usuário**
(`%LOCALAPPDATA%\MapeadorPR`), porque a rotação de log não funciona com vários
processos escrevendo o mesmo arquivo em rede.

## Componentes
1. **Leitura segura** (`core/armazenamento.py`): `sessao_leitura()` abre com
   `PRAGMA query_only`, nunca cria o arquivo e nunca migra o esquema; erra com
   mensagem clara se o banco não existe ou é de schema mais antigo. Conexões
   esperam até 30 s por bloqueio (em rede o padrão de 5 s é curto). Não se usa WAL
   (não funciona em pasta de rede).
2. **Trava de importação** (`core/trava.py`): arquivo `importando.lock` ao lado do
   banco, criado de forma atômica, com usuário, máquina e hora. Vence em 15 min
   (queda de rede ou de energia não trava ninguém para sempre). Quem tenta gravar
   com a trava ocupada vê quem está importando e desde quando e **espera até 60 s**
   a vez. A trava vale para a importação e para as edições manuais pelo detalhe
   (editar ato, aplicar CNAE, consultar CNPJ).
3. **Backup** (`core/backup.py`): antes de cada gravação, cópia consistente (API de
   backup do SQLite) em `dados\backups\`, mantendo as 10 mais recentes.
4. **Encerramento** (`core/ocioso.py` + `app.py`): botão **Encerrar ferramenta** e
   desligamento automático depois de 10 min sem nenhum navegador conectado
   (3 min de carência no início). Só no modo atalho (`MAPEADOR_MODO_ATALHO=1`).
5. **Launcher sem janela** (`iniciar.py`, `scripts/Mapeador.vbs`): roda com
   `pythonw.exe`; saída do servidor vai para arquivo; erros de inicialização viram
   caixa de mensagem; um segundo clique reabre o servidor já em execução em vez de
   subir outro.
6. **Montagem** (`scripts/montar_rede.ps1`): baixa o Python embeddable, instala as
   dependências e copia o código (`git archive HEAD`) para a pasta de rede; serve
   também para atualizar. Antes de atualizar, testa se o Python portátil está em uso
   em qualquer máquina (o Windows o trava) e recusa, salvo `-Forcar`.

## Fora do escopo
Login individual por usuário, hash da senha do Administrador, servidor central e
executável binário. Escritas realmente simultâneas não são suportadas: a trava as
serializa (cada gravação dura segundos), com espera de 60 s. Analisar PDFs não usa a
trava e pode ser feito por várias pessoas ao mesmo tempo.

## Riscos aceitos
- A senha do Administrador é texto puro em `secrets.toml`. Na rede, qualquer um
  com acesso à pasta a leria; por isso a documentação manda guardá-la em
  `%USERPROFILE%\.streamlit\secrets.toml` do computador do Administrador, que o
  Streamlit também lê, e não em `app\.streamlit\`.
- O script de montagem recusa atualizar com a ferramenta em uso; com `-Forcar`, sessões
  abertas podem ver arquivos pela metade durante a cópia.
- Se a conexão cair no meio de uma gravação, o journal do SQLite pode ficar
  pendente; o próximo Administrador a abrir o banco o recupera. Por isso o backup
  vem antes de cada gravação.
