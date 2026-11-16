# core/acesso.py
"""Perfis de uso da interface e a senha do Administrador.

A senha do Administrador e FIXA, definida aqui em SENHA_ADMIN: todo usuario recebe a
mesma senha com o programa, sem criar arquivo. Esta no codigo (e no pacote da rede):
protege contra uso acidental da interface, nao contra quem tem acesso ao codigo.
"""
import hmac

PERFIL_CONSULTA = "consulta"
PERFIL_ADMIN = "admin"

SENHA_ADMIN = "M@rtinelli"


def senha_admin() -> str:
    """Senha do Administrador (fixa)."""
    return SENHA_ADMIN


def confere(digitada: str | None, esperada: str | None) -> bool:
    if not digitada or not esperada:
        return False
    return hmac.compare_digest(digitada.encode("utf-8"), esperada.encode("utf-8"))


def exige_admin(perfil) -> None:
    if perfil != PERFIL_ADMIN:
        raise PermissionError("Ação restrita ao perfil Administrador.")
