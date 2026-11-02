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
