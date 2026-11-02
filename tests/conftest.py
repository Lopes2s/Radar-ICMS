# tests/conftest.py
import logging

import pytest


@pytest.fixture(autouse=True)
def _dados_isolados(monkeypatch, tmp_path_factory):
    """Banco e logs de qualquer teste vão para uma pasta temporária, nunca
    para a raiz do projeto. Ao fim, solta o arquivo de log (no Windows um
    handler aberto impede apagar a pasta temporária)."""
    pasta = tmp_path_factory.mktemp("dados")
    monkeypatch.setenv("MAPEADOR_DADOS", str(pasta))
    yield
    logger = logging.getLogger("mapeador")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
