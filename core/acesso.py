# core/acesso.py
"""Perfis de uso da interface e a senha do Administrador.

Sem dependência de streamlit: quem chama passa o `st.secrets` (ou um dict).
A senha fica em .streamlit/secrets.toml, seção [admin], chave `senha`. É
texto puro no disco: protege contra uso acidental da interface, não contra
quem tem acesso ao arquivo.
"""
import hmac

PERFIL_CONSULTA = "consulta"
PERFIL_ADMIN = "admin"


def senha_admin(secrets) -> str | None:
    """Senha configurada do Administrador, ou None se não houver uma válida.

    Falha fechada: qualquer problema ao ler (arquivo inexistente, seção
    ausente, valor vazio ou que não seja texto) vira None, e None desabilita
    o perfil Administrador — nunca vira acesso aberto. O `except Exception`
    é proposital pelo mesmo motivo: o st.secrets levanta tipos de erro
    diferentes conforme a versão e o estado do arquivo.
    """
    try:
        valor = secrets["admin"]["senha"]
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(valor, str) or not valor.strip():
        return None
    return valor


def confere(digitada: str | None, esperada: str | None) -> bool:
    if not digitada or not esperada:
        return False
    return hmac.compare_digest(digitada.encode("utf-8"), esperada.encode("utf-8"))


def exige_admin(perfil) -> None:
    if perfil != PERFIL_ADMIN:
        raise PermissionError("Ação restrita ao perfil Administrador.")
