# core/backup.py
"""Backup do banco antes de cada gravação.

Usa a API de backup do SQLite (cópia consistente, mesmo com o banco em uso), não
uma cópia de arquivo. Só biblioteca padrão."""
import os
import sqlite3
from datetime import datetime

PREFIXO = "mapeamento-"
MANTER_PADRAO = 10


def fazer_backup(caminho_bd: str, pasta_backups: str, manter: int = MANTER_PADRAO,
                 agora: datetime | None = None) -> str | None:
    """Copia o banco para `<pasta_backups>/mapeamento-AAAAMMDD-HHMMSS.db`, apaga
    as cópias além das `manter` mais recentes e devolve o caminho da nova.
    Devolve None se o banco ainda não existe (primeira importação)."""
    if not os.path.exists(caminho_bd):
        return None
    os.makedirs(pasta_backups, exist_ok=True)
    carimbo = (agora or datetime.now()).strftime("%Y%m%d-%H%M%S")
    destino = os.path.join(pasta_backups, f"{PREFIXO}{carimbo}.db")
    origem = sqlite3.connect(caminho_bd)
    copia = sqlite3.connect(destino)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    _podar(pasta_backups, manter)
    return destino


def _podar(pasta_backups: str, manter: int) -> None:
    """O nome carrega a data, então ordenar por nome é ordenar por idade."""
    if manter <= 0:
        return
    antigos = sorted(n for n in os.listdir(pasta_backups)
                     if n.startswith(PREFIXO) and n.endswith(".db"))[:-manter]
    for nome in antigos:
        try:
            os.remove(os.path.join(pasta_backups, nome))
        except OSError:
            pass   # arquivo em uso: fica para a próxima poda
