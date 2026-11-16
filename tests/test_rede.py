import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VBS = os.path.join(RAIZ, "scripts", "Mapeador.vbs")


def _vbs() -> str:
    with open(VBS, "rb") as arquivo:
        return arquivo.read().decode("ascii")      # falha se houver acento


def test_atalho_e_ascii_puro_e_roda_sem_janela():
    texto = _vbs()
    assert "pythonw.exe" in texto
    assert re.search(r"\.Run\b.*,\s*0\s*,\s*False", texto)    # estilo 0 = oculto


def test_atalho_define_o_ambiente_da_rede():
    texto = _vbs()
    for variavel in ("MAPEADOR_DADOS", "MAPEADOR_LOGS", "MAPEADOR_LOCAL",
                     "MAPEADOR_MODO_ATALHO", "MAPEADOR_SEM_AUTOINSTALL",
                     "PYTHONDONTWRITEBYTECODE"):
        assert variavel in texto


def test_script_de_montagem_existe_e_instala_do_requirements():
    caminho = os.path.join(RAIZ, "scripts", "montar_rede.ps1")
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert "requirements.txt" in texto
    assert "git" in texto and "archive" in texto
    assert "Mapeador.vbs" in texto


def test_script_de_montagem_recusa_atualizar_com_a_ferramenta_em_uso():
    caminho = os.path.join(RAIZ, "scripts", "montar_rede.ps1")
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert "Test-EmUso" in texto
    assert "$Forcar" in texto
