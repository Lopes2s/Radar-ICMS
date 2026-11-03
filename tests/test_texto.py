from core.pdf_text import MARCA_CITACAO, MARCA_PARAGRAFO
from core.texto import normalizar


def test_remove_acentos_e_ignora_caixa():
    assert normalizar("Substituição TRIBUTÁRIA") == "substituicao tributaria"


def test_colapsa_espacos_e_quebras_de_paragrafo():
    assert normalizar("a \n\n  b") == "a b"


def test_descarta_as_marcas_invisiveis():
    assert normalizar(f"a{MARCA_PARAGRAFO}{MARCA_CITACAO}b") == "a b"


def test_vazio_e_none_viram_texto_vazio():
    assert normalizar(None) == ""
    assert normalizar("   ") == ""
