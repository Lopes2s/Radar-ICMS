# core/log.py
"""Log do app: <pasta de dados>/logs/app.log (rotativo, ~1 MB × 3 arquivos).

Se `MAPEADOR_LOGS` estiver definida, os logs vão para essa pasta. O atalho de rede
usa isso para guardar o log na máquina de cada usuário: a rotação não funciona
com vários processos escrevendo o mesmo arquivo numa pasta de rede.

Só biblioteca padrão e sem dependência de `armazenamento`: quem chama passa a
pasta (ver `armazenamento.pasta_dados`)."""
import logging
import os
from logging.handlers import RotatingFileHandler

NOME = "mapeador"


def configurar_log(pasta: str) -> logging.Logger:
    """Liga o log em arquivo. Idempotente: chamar de novo com a mesma pasta
    não duplica o handler."""
    logger = logging.getLogger(NOME)
    destino = os.environ.get("MAPEADOR_LOGS") or os.path.join(pasta, "logs")
    os.makedirs(destino, exist_ok=True)
    arquivo = os.path.abspath(os.path.join(destino, "app.log"))
    for handler in logger.handlers:
        if getattr(handler, "baseFilename", None) == arquivo:
            return logger
    handler = RotatingFileHandler(arquivo, maxBytes=1_000_000, backupCount=3,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
