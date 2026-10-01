# tests/test_bootstrap.py
import sys

import pytest

from core import bootstrap


def test_le_specs_do_requirements():
    specs = bootstrap._specs_do_requirements()
    assert specs['pdfplumber'] == 'pdfplumber>=0.11.9,<0.12'
    assert specs['streamlit'] == 'streamlit>=1.50,<2'
    assert 'pytest' not in specs  # dependência de desenvolvimento


def test_faltando_detecta_apenas_o_ausente():
    ausentes = bootstrap.faltando(['openpyxl', 'modulo_que_nao_existe_xyz'])
    assert ausentes == ['modulo_que_nao_existe_xyz']


def test_nao_cria_subprocesso_quando_tudo_presente(monkeypatch):
    chamou = []
    monkeypatch.setattr(bootstrap.subprocess, 'run',
                        lambda *a, **k: chamou.append(a))
    # pdfplumber e openpyxl são dependências reais do projeto, já instaladas
    assert bootstrap.garantir_dependencias(['pdfplumber', 'openpyxl']) == []
    assert chamou == []


def test_instala_o_que_falta_com_a_versao_do_requirements(monkeypatch):
    chamadas = []
    estado = {'streamlit': False}

    class _Ok:
        returncode = 0

    def _fake_run(cmd, **kwargs):
        chamadas.append(cmd)
        estado['streamlit'] = True  # pip "instalou"
        return _Ok()

    monkeypatch.setattr(bootstrap, '_instalado', lambda m: estado.get(m, True))
    monkeypatch.setattr(bootstrap.subprocess, 'run', _fake_run)
    monkeypatch.delenv(bootstrap._VAR_DESLIGA, raising=False)

    instalados = bootstrap.garantir_dependencias(['openpyxl', 'streamlit'],
                                                 silencioso=True)

    # só o ausente é instalado, e com o pino declarado no requirements.txt
    assert instalados == ['streamlit>=1.50,<2']
    assert len(chamadas) == 1
    assert chamadas[0][:4] == [sys.executable, '-m', 'pip', 'install']
    assert chamadas[0][-1] == 'streamlit>=1.50,<2'


def test_variavel_de_ambiente_desliga_instalacao(monkeypatch):
    chamou = []
    monkeypatch.setattr(bootstrap, '_instalado', lambda m: False)
    monkeypatch.setattr(bootstrap.subprocess, 'run',
                        lambda *a, **k: chamou.append(a))
    monkeypatch.setenv(bootstrap._VAR_DESLIGA, '1')

    with pytest.raises(bootstrap.DependenciaAusente) as erro:
        bootstrap.garantir_dependencias(['streamlit'], silencioso=True)

    assert 'streamlit>=1.50,<2' in str(erro.value)
    assert chamou == []  # nada foi instalado


def test_falha_do_pip_vira_erro_acionavel(monkeypatch):
    class _Falha:
        returncode = 1

    monkeypatch.setattr(bootstrap, '_instalado', lambda m: False)
    monkeypatch.setattr(bootstrap.subprocess, 'run', lambda cmd, **k: _Falha())
    monkeypatch.delenv(bootstrap._VAR_DESLIGA, raising=False)

    with pytest.raises(bootstrap.DependenciaAusente) as erro:
        bootstrap.garantir_dependencias(['streamlit'], silencioso=True)

    # a mensagem precisa dizer o que instalar na mão
    assert 'pip install streamlit>=1.50,<2' in str(erro.value)


def test_pip_que_nao_instala_de_fato_e_detectado(monkeypatch):
    """pip retorna 0 mas o módulo continua ausente -> não passa batido."""
    class _Ok:
        returncode = 0

    monkeypatch.setattr(bootstrap, '_instalado', lambda m: False)
    monkeypatch.setattr(bootstrap.subprocess, 'run', lambda cmd, **k: _Ok())
    monkeypatch.delenv(bootstrap._VAR_DESLIGA, raising=False)

    with pytest.raises(bootstrap.DependenciaAusente):
        bootstrap.garantir_dependencias(['streamlit'], silencioso=True)


# ---- versão instalada abaixo do piso do requirements.txt conta como ausente ----

def test_versao_atende_faixa():
    spec = 'streamlit>=1.50,<2'
    assert bootstrap._versao_atende('1.64.0', spec)
    assert bootstrap._versao_atende('1.50', spec)
    assert not bootstrap._versao_atende('1.30.0', spec)
    assert not bootstrap._versao_atende('2.0.0', spec)
    assert bootstrap._versao_atende('0.11.9', 'pdfplumber>=0.11.9,<0.12')
    assert not bootstrap._versao_atende('0.12.0', 'pdfplumber>=0.11.9,<0.12')


def test_versao_atende_sem_pino_ou_operador_desconhecido():
    assert bootstrap._versao_atende('0.1', 'pdfplumber')
    assert bootstrap._versao_atende('0.1', 'pdfplumber~=1.0')  # não bloqueia


def test_versao_com_sufixo_pre_release_compara_pela_parte_numerica():
    assert bootstrap._versao_atende('1.50.0rc1', 'streamlit>=1.50,<2')


def test_streamlit_desatualizado_conta_como_faltando(monkeypatch):
    monkeypatch.setattr(bootstrap, '_instalado', lambda m: True)
    monkeypatch.setattr(bootstrap, '_versao_instalada',
                        lambda pacote: '1.30.0' if pacote == 'streamlit' else '3.1.5')
    monkeypatch.setattr(bootstrap, '_specs_do_requirements',
                        lambda: {'streamlit': 'streamlit>=1.50,<2',
                                 'openpyxl': 'openpyxl>=3.1.5,<3.2'})
    assert bootstrap.faltando(['openpyxl', 'streamlit']) == ['streamlit']


def test_sem_metadados_de_versao_nao_bloqueia(monkeypatch):
    monkeypatch.setattr(bootstrap, '_instalado', lambda m: True)
    monkeypatch.setattr(bootstrap, '_versao_instalada', lambda pacote: None)
    assert bootstrap.faltando(['streamlit']) == []


def test_tolera_encoding_do_console_reconfigura_stdout_e_stderr(monkeypatch):
    chamadas = []

    class _StreamFalso:
        def reconfigure(self, **kwargs):
            chamadas.append(kwargs)

    monkeypatch.setattr(bootstrap.sys, 'stdout', _StreamFalso())
    monkeypatch.setattr(bootstrap.sys, 'stderr', _StreamFalso())
    bootstrap.tolera_encoding_do_console()
    assert chamadas == [{'errors': 'replace'}, {'errors': 'replace'}]


def test_tolera_encoding_do_console_nao_quebra_sem_reconfigure(monkeypatch):
    # streams sem o método (raro, mas mais seguro não presumir) não travam.
    class _StreamSemReconfigure:
        pass

    monkeypatch.setattr(bootstrap.sys, 'stdout', _StreamSemReconfigure())
    monkeypatch.setattr(bootstrap.sys, 'stderr', _StreamSemReconfigure())
    bootstrap.tolera_encoding_do_console()  # não deve levantar


def test_garantir_dependencias_tolera_encoding_antes_de_qualquer_coisa(monkeypatch):
    # Precisa rodar mesmo quando nada falta: é o caminho comum aos três
    # pontos de entrada (processar.py, iniciar.py e app.py via bootstrap),
    # e o print acentuado de "[setup] instalando..." só existe quando algo
    # falta — mas quem chama depois (iniciar.py) imprime acento de qualquer
    # forma, então a tolerância não pode depender de haver instalação.
    chamou = []
    monkeypatch.setattr(bootstrap, 'tolera_encoding_do_console',
                        lambda: chamou.append(True))
    assert bootstrap.garantir_dependencias(['pdfplumber', 'openpyxl']) == []
    assert chamou == [True]


def test_desatualizado_e_atualizado_com_o_pino_do_requirements(monkeypatch):
    chamadas = []
    versao = {'streamlit': '1.30.0'}

    class _Ok:
        returncode = 0

    def _fake_run(cmd, **kwargs):
        chamadas.append(cmd)
        versao['streamlit'] = '1.64.0'  # pip atualizou
        return _Ok()

    monkeypatch.setattr(bootstrap, '_instalado', lambda m: True)
    monkeypatch.setattr(bootstrap, '_versao_instalada', lambda p: versao.get(p))
    monkeypatch.setattr(bootstrap.subprocess, 'run', _fake_run)
    monkeypatch.delenv(bootstrap._VAR_DESLIGA, raising=False)

    assert bootstrap.garantir_dependencias(['streamlit'], silencioso=True) == [
        'streamlit>=1.50,<2']
    assert chamadas[0][-1] == 'streamlit>=1.50,<2'
