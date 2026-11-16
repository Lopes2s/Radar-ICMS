from core import log


def test_configurar_log_cria_o_arquivo_e_registra(tmp_path):
    logger = log.configurar_log(str(tmp_path))
    logger.info("olá, log")
    for handler in logger.handlers:
        handler.flush()
    conteudo = (tmp_path / "logs" / "app.log").read_text(encoding="utf-8")
    assert "olá, log" in conteudo


def test_configurar_log_duas_vezes_nao_duplica_o_handler(tmp_path):
    log.configurar_log(str(tmp_path))
    logger = log.configurar_log(str(tmp_path))
    com_arquivo = [h for h in logger.handlers if getattr(h, "baseFilename", None)]
    assert len(com_arquivo) == 1


def test_mapeador_logs_leva_o_log_para_outra_pasta(tmp_path, monkeypatch):
    # Em pasta de rede a rotação do log quebra (vários processos no mesmo
    # arquivo): o atalho aponta MAPEADOR_LOGS para uma pasta local de cada usuário.
    local = tmp_path / "local" / "logs"
    monkeypatch.setenv("MAPEADOR_LOGS", str(local))
    logger = log.configurar_log(str(tmp_path / "rede"))
    logger.info("na máquina")
    for handler in logger.handlers:
        handler.flush()
    assert "na máquina" in (local / "app.log").read_text(encoding="utf-8")
    assert not (tmp_path / "rede" / "logs").exists()
