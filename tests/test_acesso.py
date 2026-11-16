import pytest

from core import acesso


def test_senha_admin_e_fixa_e_nao_depende_de_secrets_toml():
    assert acesso.senha_admin() == "M@rtinelli"
    assert acesso.senha_admin() == acesso.SENHA_ADMIN


def test_confere_senha_correta_e_errada():
    assert acesso.confere("segredo", "segredo") is True
    assert acesso.confere("errada", "segredo") is False
    assert acesso.confere("Segredo", "segredo") is False


def test_confere_aceita_acentos():
    assert acesso.confere("sênha-çãõ", "sênha-çãõ") is True
    assert acesso.confere("senha-cao", "sênha-çãõ") is False


@pytest.mark.parametrize("digitada,esperada", [
    ("", "segredo"), (None, "segredo"), ("segredo", None), ("segredo", ""),
    ("", ""), (None, None),
])
def test_confere_nunca_autentica_com_vazio_ou_sem_senha_configurada(digitada, esperada):
    assert acesso.confere(digitada, esperada) is False


def test_exige_admin():
    acesso.exige_admin(acesso.PERFIL_ADMIN)
    for perfil in (acesso.PERFIL_CONSULTA, None, "", "ADMIN", "qualquer"):
        with pytest.raises(PermissionError):
            acesso.exige_admin(perfil)
