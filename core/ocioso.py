# core/ocioso.py
"""Desligar o servidor local quando ninguém o está usando.

Cada usuário roda o próprio servidor pelo atalho; sem isto, fechar a aba do
navegador deixaria um processo esquecido na máquina. `VigiaOciosidade` é lógica
pura (relógio e contador injetados); só `contar_sessoes_streamlit` toca o
Streamlit, e de forma tolerante: se a API interna mudar, devolve None e o vigia
passa a nunca encerrar, em vez de derrubar o servidor por engano."""
import time


class VigiaOciosidade:
    def __init__(self, contar_sessoes, limite_s: float = 600,
                 carencia_s: float = 180, relogio=time.monotonic):
        self._contar = contar_sessoes
        self._limite = limite_s
        self._carencia = carencia_s
        self._relogio = relogio
        self._visto = False                 # algum navegador já se conectou?
        self._zero_desde = relogio()        # desde quando não há navegador

    def deve_encerrar(self) -> bool:
        sessoes = self._contar()
        if sessoes is None:
            return False
        agora = self._relogio()
        if sessoes > 0:
            self._visto = True
            self._zero_desde = None
            return False
        if self._zero_desde is None:
            self._zero_desde = agora
        espera = self._limite if self._visto else self._carencia
        return agora - self._zero_desde >= espera


def contar_sessoes_streamlit() -> int | None:
    """Quantos navegadores estão conectados agora, ou None se não der para saber."""
    try:
        from streamlit.runtime import get_instance
        return len(get_instance()._session_mgr.list_active_sessions())
    except Exception:  # noqa: BLE001 - API interna: qualquer falha desliga o vigia
        return None
