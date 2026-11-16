# core/trava.py
"""Trava de importação: um arquivo ao lado do banco que diz quem está gravando.

O SQLite em pasta de rede não tem bloqueio confiável contra escritas simultâneas;
como só uma ou duas pessoas importam, basta impedir que duas gravem ao mesmo
tempo e mostrar a quem está com a vez. A trava VENCE sozinha (queda de rede ou de
energia não pode travar ninguém para sempre) e só quem a criou a remove.

Retomar uma trava vencida é serializado por um segundo arquivo, o mutex
`NOME_RETOMADA`, criado com O_EXCL e segurado só por instantes; assim duas
pessoas não removem e recriam a trava uma sobre a outra.

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
NOME_RETOMADA = "importando.lock.retomada"
VALIDADE_PADRAO = timedelta(minutes=15)
IDADE_MAX_RETOMADA = timedelta(seconds=30)


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


def _ocupado(agora: datetime) -> Importacao:
    return Importacao("alguém", "outra máquina", agora, agora)


def _remover(caminho: str, dormir=time.sleep, tentativas: int = 10,
             intervalo_s: float = 0.2) -> bool:
    """Remove o arquivo. No Windows, outro processo com o arquivo aberto (ex.: quem
    espera e consulta a trava) dá PermissionError por instantes: tenta de novo.
    Devolve se o arquivo já não existe."""
    for n in range(tentativas):
        try:
            os.remove(caminho)
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            if n < tentativas - 1:
                dormir(intervalo_s)
        except OSError:
            return False
    return False


def _mtime(caminho: str) -> datetime | None:
    try:
        return datetime.fromtimestamp(os.path.getmtime(caminho), timezone.utc)
    except OSError:
        return None


def quem_sou() -> tuple[str, str]:
    """(usuário do Windows, nome da máquina)."""
    try:
        usuario = getpass.getuser()
    except Exception:  # noqa: BLE001 - sem usuário resolvível, o nome não é essencial
        usuario = "desconhecido"
    return usuario, socket.gethostname()


def _ler(caminho: str, agora: datetime) -> Importacao | None:
    """O que o arquivo diz, ou None se não existe. Arquivo ilegível ou com datas
    incompatíveis (ex.: ISO sem fuso) vale como OCUPADO, com a data do arquivo."""
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        atual = Importacao(dados["quem"], dados["maquina"],
                           datetime.fromisoformat(dados["desde"]),
                           datetime.fromisoformat(dados["renovado_em"]))
        agora - atual.renovado_em  # levanta TypeError se os fusos não forem compatíveis
        return atual
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        modificado = _mtime(caminho)
        if modificado is None:
            return None
        return Importacao("alguém", "outra máquina", modificado, modificado)


def situacao(pasta: str, agora: datetime | None = None,
             validade: timedelta = VALIDADE_PADRAO) -> Importacao | None:
    """Quem está importando agora, ou None se ninguém (trava ausente ou vencida)."""
    agora = agora or _agora()
    atual = _ler(_caminho(pasta), agora)
    if atual is None:
        return None
    return None if agora - atual.renovado_em > validade else atual


def _criar(pasta: str, quem: str, maquina: str, agora: datetime) -> None:
    """Cria a trava de forma atômica (O_EXCL) e escreve. FileExistsError se já existe.
    Se a escrita falhar, o arquivo recém-criado é removido e o erro é relançado."""
    caminho = _caminho(pasta)
    fd = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump({"quem": quem, "maquina": maquina,
                       "desde": agora.isoformat(),
                       "renovado_em": agora.isoformat()}, arquivo)
    except BaseException:
        _remover(caminho)
        raise


def _criar_mutex(caminho: str) -> None:
    os.close(os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY))


def _retomar(pasta: str, quem: str, maquina: str, agora: datetime,
             validade: timedelta) -> Importacao | None:
    """Assume uma trava vencida ou ilegível, uma pessoa de cada vez (mutex `NOME_RETOMADA`)."""
    mutex = os.path.join(pasta, NOME_RETOMADA)
    ocupado = lambda: situacao(pasta, agora, validade) or _ocupado(agora)  # noqa: E731
    try:
        _criar_mutex(mutex)
    except FileExistsError:
        modificado = _mtime(mutex)
        # mutex antigo = quem o criou caiu no meio; remove e tenta uma vez
        if modificado is None or _agora() - modificado <= IDADE_MAX_RETOMADA:
            return ocupado()
        _remover(mutex)
        try:
            _criar_mutex(mutex)
        except FileExistsError:
            return ocupado()
    try:
        atual = situacao(pasta, agora, validade)   # reler: alguém pode ter retomado antes
        if atual is not None:
            return atual
        _remover(_caminho(pasta))
        try:
            _criar(pasta, quem, maquina, agora)
        except FileExistsError:
            return ocupado()
        return None
    finally:
        _remover(mutex)


def adquirir(pasta: str, quem: str, maquina: str, agora: datetime | None = None,
             validade: timedelta = VALIDADE_PADRAO) -> Importacao | None:
    """Tenta assumir a trava. Devolve None se conseguiu; senão, quem a tem."""
    agora = agora or _agora()
    try:
        _criar(pasta, quem, maquina, agora)
        return None
    except FileExistsError:
        pass
    atual = situacao(pasta, agora, validade)
    if atual is not None:
        return atual
    return _retomar(pasta, quem, maquina, agora, validade)


def liberar(pasta: str, quem: str, maquina: str, dormir=time.sleep) -> bool:
    """Remove a trava SE for de `quem`/`maquina`. Devolve se removeu."""
    atual = situacao(pasta, validade=timedelta.max)
    if atual is None or (atual.quem, atual.maquina) != (quem, maquina):
        return False
    return _remover(_caminho(pasta), dormir)


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
