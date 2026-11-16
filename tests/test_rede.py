import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VBS = os.path.join(RAIZ, "scripts", "Radar ICMS.vbs")


def _vbs() -> str:
    with open(VBS, "rb") as arquivo:
        return arquivo.read().decode("ascii")      # falha se houver acento


def test_atalho_e_ascii_puro_e_roda_sem_janela():
    texto = _vbs()
    assert "pythonw.exe" in texto
    assert re.search(r"\.Run\b.*,\s*0\s*,\s*False", texto)    # estilo 0 = oculto
    assert r'localApp & "\iniciar.py' in texto            # roda da copia LOCAL


def test_atalho_define_o_ambiente_da_rede():
    texto = _vbs()
    for variavel in ("MAPEADOR_DADOS", "MAPEADOR_LOGS", "MAPEADOR_LOCAL",
                     "MAPEADOR_MODO_ATALHO", "MAPEADOR_SEM_AUTOINSTALL"):
        assert variavel in texto


def test_script_de_montagem_existe_e_instala_do_requirements():
    caminho = os.path.join(RAIZ, "scripts", "montar_rede.ps1")
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert "requirements.txt" in texto
    assert "git" in texto and "archive" in texto
    assert "Radar ICMS.vbs" in texto


def test_atalho_instala_a_copia_local_quando_a_versao_difere():
    texto = _vbs()
    assert "versao.txt" in texto and "LOCALAPPDATA" in texto
    assert "atualizar_local.ps1" in texto
    assert "VersaoDe(base" in texto            # compara a versao local com a da rede


def test_script_de_montagem_publica_um_pacote_zip_versionado():
    caminho = os.path.join(RAIZ, "scripts", "montar_rede.ps1")
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert "programa-$versao.zip" in texto
    assert "versao.txt" in texto and "atualizar_local.ps1" in texto
    assert "LOCALAPPDATA" in texto             # monta numa pasta local, nao na rede
    assert texto.index("Move-Item") < texto.index('Set-Content (Join-Path $programa "versao.txt")')
    assert "Test-EmUso" not in texto           # ninguem roda arquivos da rede


def test_atualizador_local_troca_a_pasta_sem_apagar_pela_metade():
    caminho = os.path.join(RAIZ, "scripts", "atualizar_local.ps1")
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert "tar.exe" in texto and "Mutex" in texto
    assert "app.velho" in texto and "exit 3" in texto


def test_script_de_montagem_aborta_em_falha_de_comando_nativo():
    caminho = os.path.join(RAIZ, "scripts", "montar_rede.ps1")
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert texto.count("$LASTEXITCODE") >= 4
    assert texto.index("Remove-Item") < texto.index("archive")
