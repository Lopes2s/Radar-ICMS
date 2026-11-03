# tests/test_formularios.py
from interface import formularios


def test_prefixo_e_unico_por_ato():
    a = formularios.prefixo_de('regime', ['9.053/2026', '11'])
    b = formularios.prefixo_de('regime', ['9.053/2026', '22'])
    c = formularios.prefixo_de('consulta', ['2026', '001'])
    assert a == "edit|regime|9.053/2026|11"
    assert len({a, b, c}) == 3


def test_prefixo_da_analise_tem_espaco_proprio():
    assert (formularios.prefixo_de('regime', ['1', '2'], contexto="analise")
            != formularios.prefixo_de('regime', ['1', '2']))


def test_campos_de_texto_corrido_viram_area_de_texto():
    assert formularios.campo_longo('EMENTA', '')
    assert formularios.campo_longo('Resposta', 'curta')
    assert not formularios.campo_longo('EMPRESA', 'Alfa Ltda')
    assert formularios.campo_longo('EMPRESA', 'x' * 81)      # valor longo também vira área


def test_altura_da_area_cresce_com_o_texto_dentro_de_limites():
    assert formularios.altura_da_area('') == 110
    assert formularios.altura_da_area('linha\n' * 5) > formularios.altura_da_area('curta')
    assert formularios.altura_da_area('x\n' * 500) == 360


def test_campos_alterados_ignora_espacos_das_pontas_e_none():
    original = {'EMPRESA': 'Alfa', 'EMENTA': None, 'DATA': '2026-01-01'}
    novos = {'EMPRESA': '  Alfa  ', 'EMENTA': '', 'DATA': '2026-02-01'}
    assert formularios.campos_alterados(original, novos) == ['DATA']
