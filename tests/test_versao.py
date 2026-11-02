import re

from core.versao import VERSAO_APP


def test_versao_segue_o_formato_semantico():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSAO_APP)
