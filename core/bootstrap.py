# core/bootstrap.py
"""Verificação e instalação automática das dependências.

Roda nos pontos de entrada ANTES dos imports pesados (pdfplumber, openpyxl,
streamlit). Quando tudo já está instalado o custo é um `find_spec` por pacote
e nenhum subprocesso — é seguro chamar a cada início.

Este módulo não importa nada de terceiros: se importasse, não teria como
consertar a ausência daquilo que ele mesmo precisa.
"""
import importlib
import importlib.util
import os
from importlib import metadata
import re
import subprocess
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REQUIREMENTS = os.path.join(_RAIZ, 'requirements.txt')

# módulo importável -> nome do projeto no PyPI (nem sempre coincidem)
_PACOTE_POR_MODULO = {
    'pdfplumber': 'pdfplumber',
    'openpyxl': 'openpyxl',
    'streamlit': 'streamlit',
    'pytest': 'pytest',
}

# o que cada ponto de entrada precisa: o CLI não carrega a interface, então
# não faz sentido baixar o streamlit para gerar uma planilha em lote.
DEPS_CLI = ['pdfplumber', 'openpyxl']
DEPS_APP = ['pdfplumber', 'openpyxl', 'streamlit']

# defina como 1 para exigir ambiente já preparado (CI, imagem congelada):
# em vez de instalar, a função falha dizendo o que falta.
_VAR_DESLIGA = 'MAPEADOR_SEM_AUTOINSTALL'


class DependenciaAusente(RuntimeError):
    """Falta dependência e não foi possível (ou não se quis) instalar."""


def _specs_do_requirements():
    """Lê requirements.txt e devolve {pacote_minusculo: linha com a versão}.

    Mantém o requirements.txt como fonte única das versões — o bootstrap não
    repete os pinos.
    """
    specs = {}
    try:
        with open(_REQUIREMENTS, encoding='utf-8') as fh:
            for linha in fh:
                linha = linha.split('#', 1)[0].strip()
                if not linha:
                    continue
                nome = re.split(r'[<>=!~\[;\s]', linha, maxsplit=1)[0].strip()
                if nome:
                    specs[nome.lower()] = linha
    except OSError:
        pass  # sem requirements.txt, instala sem pino
    return specs


def _instalado(modulo: str) -> bool:
    try:
        return importlib.util.find_spec(modulo) is not None
    except (ImportError, ValueError):
        return False


def _versao_instalada(pacote: str):
    """Versão instalada do projeto `pacote` no PyPI, ou None se não houver
    metadados (ex.: módulo vindo de fora do pip)."""
    try:
        return metadata.version(pacote)
    except metadata.PackageNotFoundError:
        return None


def _numeros(versao: str) -> tuple:
    """'1.50.0rc1' -> (1, 50, 0). Só a parte numérica; basta para os pinos
    deste projeto sem depender do pacote `packaging`."""
    partes = []
    for pedaco in versao.split('.'):
        m = re.match(r'\d+', pedaco)
        if not m:
            break
        partes.append(int(m.group()))
    return tuple(partes)


def _compara(a: tuple, b: tuple) -> int:
    tamanho = max(len(a), len(b))
    a, b = a + (0,) * (tamanho - len(a)), b + (0,) * (tamanho - len(b))
    return (a > b) - (a < b)


_OPERADORES = {
    '>=': lambda c: c >= 0, '>': lambda c: c > 0,
    '<=': lambda c: c <= 0, '<': lambda c: c < 0, '==': lambda c: c == 0,
}


def _versao_atende(versao: str, spec: str) -> bool:
    """`versao` satisfaz as restrições de uma linha do requirements.txt?

    Entende >=, >, <=, < e ==. Operadores fora disso (~=, !=) não bloqueiam:
    na dúvida, não força reinstalação.
    """
    atual = _numeros(versao)
    for op, alvo in re.findall(r'(>=|<=|==|>|<)\s*([\w.]+)', spec):
        if not _OPERADORES[op](_compara(atual, _numeros(alvo))):
            return False
    return True


def _versao_ok(modulo: str, specs: dict) -> bool:
    pacote = _PACOTE_POR_MODULO.get(modulo, modulo)
    spec = specs.get(pacote.lower())
    versao = _versao_instalada(pacote)
    if not spec or versao is None:
        return True
    return _versao_atende(versao, spec)


def faltando(modulos) -> list:
    """Quais dos `modulos` não estão importáveis agora ou estão numa versão
    fora da faixa declarada no requirements.txt."""
    specs = _specs_do_requirements()
    return [m for m in modulos if not _instalado(m) or not _versao_ok(m, specs)]


def _alvo_pip(modulo: str, specs: dict) -> str:
    pacote = _PACOTE_POR_MODULO.get(modulo, modulo)
    return specs.get(pacote.lower(), pacote)


def tolera_encoding_do_console() -> None:
    """Evita UnicodeEncodeError ao imprimir acentos num console/pipe que não
    suporta UTF-8 (redirecionamento, Git Bash/mintty, tarefa agendada).

    Chamada aqui, no ponto comum aos três pontos de entrada, e também no
    início de cada `main()` que imprime antes de chegar a este ponto (ver
    processar.py e iniciar.py): sem isso, uma execução bem-sucedida podia
    sair com código de erro só por causa do print() em si.
    """
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
        sys.stderr.reconfigure(errors='replace')


def garantir_dependencias(modulos=None, *, silencioso: bool = False) -> list:
    """Instala o que faltar entre `modulos`; devolve o que foi instalado agora.

    Devolve `[]` (sem efeito colateral) quando nada falta. Levanta
    DependenciaAusente se a instalação for desligada, falhar, ou não resolver.
    """
    tolera_encoding_do_console()
    modulos = list(modulos if modulos is not None else DEPS_CLI)
    ausentes = faltando(modulos)
    if not ausentes:
        return []

    specs = _specs_do_requirements()
    alvos = [_alvo_pip(m, specs) for m in ausentes]
    manual = 'pip install ' + ' '.join(alvos)

    if os.environ.get(_VAR_DESLIGA, '').strip() not in ('', '0'):
        raise DependenciaAusente(
            f"Dependências ausentes: {', '.join(alvos)}.\n"
            f"Instalação automática desligada por {_VAR_DESLIGA}.\n"
            f"Instale com: {manual}"
        )

    if not silencioso:
        print(f"[setup] instalando dependências ausentes: {', '.join(alvos)}",
              flush=True)
        print("[setup] isso pode levar alguns minutos na primeira vez.",
              flush=True)

    # sem capture_output: o progresso do pip aparece ao vivo, que numa
    # instalação de minutos vale mais do que guardar a saída.
    resultado = subprocess.run([sys.executable, '-m', 'pip', 'install', *alvos])
    if resultado.returncode != 0:
        raise DependenciaAusente(
            f"Falha ao instalar: {', '.join(alvos)} "
            f"(pip saiu com código {resultado.returncode}).\n"
            f"Veja a saída do pip acima e instale manualmente: {manual}"
        )

    importlib.invalidate_caches()
    ainda_faltam = faltando(ausentes)
    if ainda_faltam:
        raise DependenciaAusente(
            f"O pip terminou sem erro, mas ainda não consigo importar: "
            f"{', '.join(ainda_faltam)}.\n"
            f"Provável instalação em outro Python. Este é: {sys.executable}\n"
            f"Instale com: {manual}"
        )

    if not silencioso:
        print(f"[setup] pronto: {', '.join(alvos)}", flush=True)
    return alvos
