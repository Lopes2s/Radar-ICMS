# iniciar.py
"""Sobe a interface garantindo as dependências antes.

`streamlit run app.py` exige que o streamlit JÁ exista — se ele falta, o comando
nem chega a executar o app.py, e um bootstrap lá dentro nunca rodaria. Este
launcher fecha essa lacuna: instala o que faltar e só então chama o streamlit.

Roda em modo headless de propósito. Fora dele, o streamlit faz uma pergunta
interativa de e-mail na primeira execução, que trava quem abre por duplo-clique
no .bat. Em troca, somos nós que abrimos o navegador.

    python iniciar.py
"""
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from core.bootstrap import (DEPS_APP, DependenciaAusente, garantir_dependencias,
                            tolera_encoding_do_console)

PORTA_PADRAO = 8501
_TENTATIVAS_PORTA = 20
_ESPERA_SERVIDOR = 60  # segundos até desistir de abrir o navegador


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
    try:
        garantir_dependencias(DEPS_APP)
    except DependenciaAusente as erro:
        print(f"\n{erro}", file=sys.stderr)
        return 1

    app = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
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
    return subprocess.call([sys.executable, '-m', 'streamlit', 'run', app,
                            '--server.port', str(porta),
                            '--server.address', '127.0.0.1',
                            '--server.headless', 'true',
                            '--browser.gatherUsageStats', 'false',
                            *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
