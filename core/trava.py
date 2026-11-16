# core/trava.py
"""Trava de importação: um arquivo ao lado do banco que diz quem está gravando.

O SQLite em pasta de rede não tem bloqueio confiável contra escritas simultâneas;
como só uma ou duas pessoas importam, basta impedir que duas gravem ao mesmo
tempo e mostrar a quem está com a vez. A trava VENCE sozinha (queda de rede ou de
energia não pode travar ninguém para sempre) e só quem a criou a remove.

Só biblioteca padrão. `pasta` é a pasta do banco."""
import getpass
import json
import os
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

NOME_ARQUIVO = "importando.lock"
VALIDADE_PADRAO = timedelta(minutes=15)


class Importacao(NamedTuple):
    quem: str
    maquina: str
    desde: datetime
    renovado_em: datetime

    def texto(self) -> str:
        hora = self.desde.astimezone().strftime("%H:%M")
        return f"{self.quem} ({self.maquina}) está gravando desde {hora}"


class ImportacaoEmAndamento(Exception):
    """Outra pessoa está gravando: `importacao` diz quem."""

    def __init__(self, importacao: Importacao):
        super().__init__(f"{importacao.texto()}. Tente de novo em instantes.")
        self.importacao = importacao


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _caminho(pasta: str) -> str:
    return os.path.join(pasta, NOME_ARQUIVO)


def quem_sou() -> tuple[str, str]:
    """(usuário do Windows, nome da máquina)."""
    try:
        usuario = getpass.getuser()
    except Exception:  # noqa: BLE001 - sem usuário resolvível, o nome não é essencial
        usuario = "desconhecido"
    return usuario, socket.gethostname()


def situacao(pasta: str, agora: datetime | None = None,
             validade: timedelta = VALIDADE_PADRAO) -> Importacao | None:
    """Quem está importando agora, ou None se ninguém (trava ausente ou vencida).

    Arquivo ilegível (outra máquina ainda o escrevendo) vale como OCUPADO, com a
    validade contada pela data do arquivo, para nunca virar "livre" por engano."""
    agora = agora or _agora()
    caminho = _caminho(pasta)
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        atual = Importacao(dados["quem"], dados["maquina"],
                           datetime.fromisoformat(dados["desde"]),
                           datetime.fromisoformat(dados["renovado_em"]))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        try:
            modificado = datetime.fromtimestamp(os.path.getmtime(caminho), timezone.utc)
        except OSError:
            return None
        atual = Importacao("alguém", "outra máquina", modificado, modificado)
    return None if agora - atual.renovado_em > validade else atual


def adquirir(pasta: str, quem: str, maquina: str, agora: datetime | None = None,
             validade: timedelta = VALIDADE_PADRAO) -> Importacao | None:
    """Tenta assumir a trava. Devolve None se conseguiu; senão, quem a tem.

    A criação é atômica (O_EXCL): duas pessoas clicando juntas, só uma cria."""
    agora = agora or _agora()
    caminho = _caminho(pasta)
    for _ in range(2):
        try:
            fd = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            atual = situacao(pasta, agora, validade)
            if atual is not None:
                return atual
            try:                     # vencida: quem chegar primeiro a remove
                os.remove(caminho)
            except OSError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump({"quem": quem, "maquina": maquina,
                       "desde": agora.isoformat(),
                       "renovado_em": agora.isoformat()}, arquivo)
        return None
    return situacao(pasta, agora, validade) or Importacao(
        "alguém", "outra máquina", agora, agora)


def liberar(pasta: str, quem: str, maquina: str) -> bool:
    """Remove a trava SE for de `quem`/`maquina`. Devolve se removeu."""
    atual = situacao(pasta, validade=timedelta.max)
    if atual is None or (atual.quem, atual.maquina) != (quem, maquina):
        return False
    try:
        os.remove(_caminho(pasta))
    except OSError:
        return False
    return True


@contextmanager
def importando(pasta: str, quem: str | None = None, maquina: str | None = None,
               esperar_s: float = 0.0, intervalo_s: float = 2.0,
               dormir=time.sleep, relogio=time.monotonic):
    """Segura a trava durante o bloco. Se estiver ocupada, espera até `esperar_s`
    segundos (olhando a cada `intervalo_s`); `ImportacaoEmAndamento` se não ficar livre."""
    if quem is None or maquina is None:
        quem, maquina = quem_sou()
    limite = relogio() + esperar_s
    while True:
        outro = adquirir(pasta, quem, maquina)
        if outro is None:
            break
        if relogio() + intervalo_s > limite:
            raise ImportacaoEmAndamento(outro)
        dormir(intervalo_s)
    try:
        yield
    finally:
        liberar(pasta, quem, maquina)
