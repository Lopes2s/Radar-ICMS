import sqlite3
from datetime import datetime, timedelta

from core import backup


def _banco(caminho, valor="x"):
    conn = sqlite3.connect(str(caminho))
    conn.execute("CREATE TABLE t (a)")
    conn.execute("INSERT INTO t VALUES (?)", (valor,))
    conn.commit()
    conn.close()


def test_backup_e_uma_copia_legivel_do_banco(tmp_path):
    origem = tmp_path / "mapeamento.db"
    _banco(origem, "dado importante")
    destino = backup.fazer_backup(str(origem), str(tmp_path / "backups"),
                                  agora=datetime(2026, 11, 16, 14, 30, 5))
    assert destino.endswith("mapeamento-20261116-143005.db")
    conn = sqlite3.connect(destino)
    assert conn.execute("SELECT a FROM t").fetchone()[0] == "dado importante"
    conn.close()


def test_sem_banco_nao_faz_nada(tmp_path):
    assert backup.fazer_backup(str(tmp_path / "nao_existe.db"),
                               str(tmp_path / "backups")) is None
    assert not (tmp_path / "backups").exists()


def test_mantem_so_os_mais_recentes_e_ignora_outros_arquivos(tmp_path):
    origem = tmp_path / "mapeamento.db"
    _banco(origem)
    pasta = tmp_path / "backups"
    base = datetime(2026, 11, 16, 8, 0, 0)
    for i in range(5):
        backup.fazer_backup(str(origem), str(pasta), manter=3,
                            agora=base + timedelta(minutes=i))
    (pasta / "anotacoes.txt").write_text("não mexa", encoding="utf-8")
    nomes = sorted(p.name for p in pasta.glob("mapeamento-*.db"))
    assert nomes == ["mapeamento-20261116-080200.db",
                     "mapeamento-20261116-080300.db",
                     "mapeamento-20261116-080400.db"]
    assert (pasta / "anotacoes.txt").exists()
