# tests/test_iniciar.py
import io
import sys

import iniciar


def _stdout_ascii_estrito(monkeypatch):
    """Ver tests/test_processar.py: simula um console/pipe sem suporte a
    UTF-8. iniciar.py imprime "Endereço" ('ç' incluso) antes de abrir o
    navegador — o mesmo padrão que quebrava em processar.py."""
    buf = io.BytesIO()
    fake = io.TextIOWrapper(buf, encoding='ascii', errors='strict')
    monkeypatch.setattr(sys, 'stdout', fake)
    return fake, buf


class _SocketFalso:
    """Recusa as `recusas` primeiras conexões e aceita a seguinte."""
    tentativas = 0
    recusas = 0

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def settimeout(self, t):
        pass

    def connect_ex(self, endereco):
        _SocketFalso.tentativas += 1
        return 0 if _SocketFalso.tentativas > _SocketFalso.recusas else 111


def _prepara(monkeypatch, recusas):
    _SocketFalso.tentativas, _SocketFalso.recusas = 0, recusas
    esperas, abertos = [], []
    monkeypatch.setattr(iniciar.socket, 'socket', _SocketFalso)
    monkeypatch.setattr(iniciar.time, 'sleep', lambda s: esperas.append(s))
    monkeypatch.setattr(iniciar.webbrowser, 'open', lambda url: abertos.append(url))
    return esperas, abertos


def test_espera_entre_tentativas_ate_o_servidor_subir(monkeypatch):
    # connection refused volta na hora (Linux/macOS): sem pausa entre
    # tentativas, as 120 acabavam em milissegundos e o navegador não abria.
    esperas, abertos = _prepara(monkeypatch, recusas=3)
    iniciar._abrir_quando_subir("http://localhost:8501", 8501)
    assert abertos == ["http://localhost:8501"]
    assert esperas == [0.5, 0.5, 0.5]


def test_desiste_depois_do_tempo_limite_sem_abrir(monkeypatch):
    esperas, abertos = _prepara(monkeypatch, recusas=10_000)
    iniciar._abrir_quando_subir("http://localhost:8501", 8501)
    assert abertos == []
    assert sum(esperas) == iniciar._ESPERA_SERVIDOR


def test_endereco_com_acento_nao_quebra_em_console_ascii(monkeypatch):
    # main() chega a imprimir "Endereço" antes de subir o servidor de
    # verdade; substituímos as duas partes pesadas (não abrir navegador
    # nem chamar o streamlit de verdade) para isolar só o print.
    monkeypatch.setattr(iniciar, '_abrir_quando_subir', lambda *a, **k: None)
    monkeypatch.setattr(iniciar.subprocess, 'call', lambda *a, **k: 0)
    fake, buf = _stdout_ascii_estrito(monkeypatch)

    codigo = iniciar.main()

    fake.flush()
    assert codigo == 0
    saida = buf.getvalue().decode('ascii')
    assert "Endere" in saida  # o 'ç' virou '?', mas não travou
