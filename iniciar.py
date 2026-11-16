# iniciar.py
"""Sobe a interface garantindo as dependências antes.

`streamlit run app.py` exige que o streamlit JÁ exista — se ele falta, o comando
nem chega a executar o app.py, e um bootstrap lá dentro nunca rodaria. Este
launcher fecha essa lacuna: instala o que faltar e só então chama o streamlit.

Roda em modo headless de propósito. Fora dele, o streamlit faz uma pergunta
interativa de e-mail na primeira execução, que trava quem abre por duplo-clique
no .bat. Em troca, somos nós que abrimos o navegador.

Sem console (pythonw.exe, pelo Radar ICMS.vbs): a saída do servidor vai para um
arquivo e erros de inicialização aparecem numa caixa de mensagem.

    python iniciar.py
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser

from core.bootstrap import (DEPS_APP, DependenciaAusente, garantir_dependencias,
                            tolera_encoding_do_console)

PORTA_PADRAO = 8501
_TENTATIVAS_PORTA = 20
_ESPERA_SERVIDOR = 60  # segundos até desistir de abrir o navegador
_RAIZ = os.path.dirname(os.path.abspath(__file__))


def _pasta_local() -> str:
    """Pasta da máquina do usuário (marcador do servidor e log do servidor).
    No atalho de rede é `%LOCALAPPDATA%\\MapeadorPR` (MAPEADOR_LOCAL)."""
    pasta = (os.environ.get('MAPEADOR_LOCAL')
             or os.path.join(os.path.expanduser('~'), '.mapeador'))
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _arquivo_servidor() -> str:
    return os.path.join(_pasta_local(), 'servidor.json')


def _saudavel(porta: int) -> bool:
    try:
        with urllib.request.urlopen(
                f'http://127.0.0.1:{porta}/_stcore/health', timeout=1) as resposta:
            return resposta.read().strip() == b'ok'
    except Exception:  # noqa: BLE001 - qualquer falha = não há servidor ali
        return False


def _porta_em_execucao() -> int | None:
    """Porta do servidor desta ferramenta já em execução nesta máquina, ou None.
    O marcador evita confundir com outro app Streamlit que esteja na 8501."""
    try:
        with open(_arquivo_servidor(), encoding='utf-8') as arquivo:
            porta = int(json.load(arquivo)['porta'])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return porta if _saudavel(porta) else None


def _registrar_servidor(porta: int) -> None:
    with open(_arquivo_servidor(), 'w', encoding='utf-8') as arquivo:
        json.dump({'porta': porta}, arquivo)


def _esquecer_servidor(porta: int | None = None) -> None:
    """Apaga o marcador; com `porta`, só se ele ainda nomeia essa porta (outro
    servidor pode tê-lo reescrito)."""
    try:
        if porta is not None:
            with open(_arquivo_servidor(), encoding='utf-8') as arquivo:
                if int(json.load(arquivo)['porta']) != porta:
                    return
        os.remove(_arquivo_servidor())
    except (OSError, ValueError, KeyError, TypeError):
        pass


def _marcador_recente() -> int | None:
    """Porta do marcador, se ele é mais novo que `_ESPERA_SERVIDOR`: um servidor
    pode estar subindo (da pasta de rede, sem janela, leva segundos)."""
    try:
        caminho = _arquivo_servidor()
        if time.time() - os.path.getmtime(caminho) > _ESPERA_SERVIDOR:
            return None
        with open(caminho, encoding='utf-8') as arquivo:
            return int(json.load(arquivo)['porta'])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _esperar_servidor_subindo() -> int | None:
    """Se há um marcador recente, espera o servidor ficar saudável. Devolve a porta
    ou None (sem marcador recente, ou nunca ficou saudável)."""
    porta = _marcador_recente()
    if porta is None:
        return None
    for _ in range(int(_ESPERA_SERVIDOR / _INTERVALO)):
        if _saudavel(porta):
            return porta
        time.sleep(_INTERVALO)
    return None


def _destino_da_saida() -> dict:
    """Sem console (pythonw.exe) não há stdout/stderr e o subprocess falha com
    'handle inválido': manda a saída do servidor para um arquivo local."""
    if sys.stdout is not None and sys.stderr is not None:
        return {}
    pasta = os.path.join(_pasta_local(), 'logs')
    os.makedirs(pasta, exist_ok=True)
    arquivo = open(os.path.join(pasta, 'servidor.log'), 'a', encoding='utf-8')
    return {'stdin': subprocess.DEVNULL, 'stdout': arquivo,
            'stderr': subprocess.STDOUT}


def _caixa_de_mensagem(texto: str) -> None:
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, texto, 'Radar ICMS', 0x10)


def _avisar_erro(texto: str) -> None:
    """Sem console o erro some: no Windows vira caixa de mensagem."""
    if sys.stderr is None and sys.platform == 'win32':
        _caixa_de_mensagem(texto)
    else:
        print(f"\n{texto}", file=sys.stderr)


def _porta_livre(preferida: int = PORTA_PADRAO) -> int:
    """Primeira porta livre a partir de `preferida`."""
    for porta in range(preferida, preferida + _TENTATIVAS_PORTA):
        with socket.socket() as s:
            try:
                s.bind(('127.0.0.1', porta))
                return porta
            except OSError:
                continue
    return preferida


_INTERVALO = 0.5  # segundos entre tentativas


def _abrir_quando_subir(url: str, porta: int) -> None:
    """Espera a porta aceitar conexão e só então abre o navegador.

    A pausa entre tentativas é obrigatória: "connection refused" volta na
    hora no Linux/macOS, e sem ela o laço inteiro durava milissegundos.
    """
    for _ in range(int(_ESPERA_SERVIDOR / _INTERVALO)):
        with socket.socket() as s:
            s.settimeout(_INTERVALO)
            if s.connect_ex(('127.0.0.1', porta)) == 0:
                webbrowser.open(url)
                return
        time.sleep(_INTERVALO)
    # não abriu sozinho: o endereço já foi impresso, o usuário clica nele


def main():
    # Antes do primeiro print ("Endereço: ...", com "ç"): mesma correção de
    # processar.py. Sem isto, "python iniciar.py" direto do terminal — uso
    # documentado no README — quebra num console/pipe sem suporte a UTF-8,
    # mesmo tendo aberto a interface com sucesso. Mapeador.bat já mitiga
    # isto por outro caminho (chcp 65001 + PYTHONIOENCODING=utf-8), mas
    # quem chama iniciar.py direto não passa por ele.
    tolera_encoding_do_console()
    os.chdir(_RAIZ)        # .streamlit/config.toml e secrets.toml são lidos daqui

    em_execucao = _porta_em_execucao()
    if not em_execucao:    # clique duplo durante a partida: espera em vez de subir outro
        em_execucao = _esperar_servidor_subindo()
    if em_execucao:        # segundo clique no atalho: reabre em vez de subir outro
        webbrowser.open(f"http://localhost:{em_execucao}")
        return 0

    try:
        garantir_dependencias(DEPS_APP)
    except DependenciaAusente as erro:
        _avisar_erro(str(erro))
        return 1

    app = os.path.join(_RAIZ, 'app.py')
    porta = _porta_livre()
    url = f"http://localhost:{porta}"

    print(f"  Endereço: {url}")
    print("  Para encerrar: feche esta janela ou tecle Ctrl+C.\n", flush=True)

    threading.Thread(target=_abrir_quando_subir, args=(url, porta),
                     daemon=True).start()

    # via `-m` porque o streamlit.exe pode não estar no PATH.
    # address=127.0.0.1: sem isso o streamlit escuta em todas as interfaces e
    # publica a ferramenta na rede local — os PDFs são de clientes.
    # gatherUsageStats=false: nada de telemetria saindo da máquina.
    _registrar_servidor(porta)
    try:
        return subprocess.call([sys.executable, '-m', 'streamlit', 'run', app,
                                '--server.port', str(porta),
                                '--server.address', '127.0.0.1',
                                '--server.headless', 'true',
                                '--browser.gatherUsageStats', 'false',
                                *sys.argv[1:]], **_destino_da_saida())
    finally:
        _esquecer_servidor(porta)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - sem console, a falha precisa aparecer
        _avisar_erro(traceback.format_exc())
        sys.exit(1)
