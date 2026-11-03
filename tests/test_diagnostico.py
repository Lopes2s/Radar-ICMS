from core import diagnostico, pipeline


def _arq(nome, tipo='consulta', erro=''):
    return {'Arquivo': nome, 'Tipo': tipo, 'Consultas': 0, 'Regimes': 0,
            'Descartes': 0, 'Erro': erro}


def _consulta(**campos):
    base = {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
            'Súmula': 'ICMS', 'Resposta': 'texto'}
    return {**base, **campos}


def _regime(**campos):
    base = {'Nº DO REGIME ESPECIAL': '1/2026', 'CNPJ REQUERENTE': '11.222.333/0001-81',
            'DATA': '2026-03-01', 'VIGÊNCIA DO RE': '12 meses'}
    return {**base, **campos}


def _codigos(diag):
    return [m['codigo'] for m in diag['mensagens']]


def test_cnpj_valido_confere_os_digitos_verificadores():
    assert diagnostico.cnpj_valido('11.222.333/0001-81')
    assert diagnostico.cnpj_valido('11222333000181')
    assert not diagnostico.cnpj_valido('11.222.333/0001-80')
    assert not diagnostico.cnpj_valido('11111111111111')
    assert not diagnostico.cnpj_valido('123')
    assert not diagnostico.cnpj_valido('')
    assert not diagnostico.cnpj_valido(None)


def test_lote_limpo_nao_tem_mensagens_e_pode_continuar():
    lote = pipeline.Lote(consultas=[_consulta()], regimes=[_regime()],
                         arquivos=[_arq('c.pdf')])
    diag = diagnostico.diagnosticar(lote)
    assert diag == {'mensagens': [], 'erros': 0, 'avisos': 0, 'pode_continuar': True}


def test_arquivo_ilegivel_vira_erro_com_nome_e_motivo_mas_nao_bloqueia():
    lote = pipeline.Lote(
        consultas=[_consulta()],
        arquivos=[_arq('ok.pdf'), _arq('ruim.pdf', tipo='erro',
                                        erro='PDFSyntaxError: arquivo inválido')])
    diag = diagnostico.diagnosticar(lote)
    erro = [m for m in diag['mensagens'] if m['codigo'] == 'E001'][0]
    assert erro['nivel'] == 'erro'
    assert 'ruim.pdf' in erro['texto'] and 'PDFSyntaxError' in erro['texto']
    assert erro['arquivos'] == ['ruim.pdf']
    assert diag['erros'] == 1
    assert diag['pode_continuar'] is True


def test_tipo_desconhecido_vira_aviso():
    lote = pipeline.Lote(consultas=[_consulta()],
                         arquivos=[_arq('x.pdf', tipo='desconhecido')])
    diag = diagnostico.diagnosticar(lote)
    assert _codigos(diag) == ['A001']
    assert diag['avisos'] == 1


def test_consulta_sem_resposta_sumula_e_com_data_ruim():
    lote = pipeline.Lote(
        consultas=[_consulta(Resposta='', Súmula='', **{'Data da Publicação': '19/01/2026'})],
        arquivos=[_arq('c.pdf')],
        origem={('consulta', '2026', '001'): 'c.pdf'})
    diag = diagnostico.diagnosticar(lote)
    assert _codigos(diag) == ['A201', 'A202', 'A203']
    assert diag['mensagens'][0]['arquivos'] == ['c.pdf']
    assert '001/2026' in diag['mensagens'][0]['texto']


def test_regime_com_cnpj_ausente_invalido_sem_vigencia_e_data_ruim():
    lote = pipeline.Lote(
        regimes=[_regime(**{'Nº DO REGIME ESPECIAL': '1/2026', 'CNPJ REQUERENTE': ''}),
                 _regime(**{'Nº DO REGIME ESPECIAL': '2/2026', 'CNPJ REQUERENTE': '11.222.333/0001-80'}),
                 _regime(**{'Nº DO REGIME ESPECIAL': '3/2026', 'VIGÊNCIA DO RE': '', 'DATA': ''})],
        arquivos=[_arq('r.pdf', tipo='regime')])
    diag = diagnostico.diagnosticar(lote)
    assert _codigos(diag) == ['A301', 'A302', 'A303', 'A304']


def test_lote_sem_registros_avisa_e_nao_pode_continuar():
    diag = diagnostico.diagnosticar(pipeline.Lote(arquivos=[_arq('c.pdf')]))
    assert _codigos(diag) == ['A401']
    assert diag['pode_continuar'] is False


def test_lote_totalmente_vazio_nao_quebra():
    diag = diagnostico.diagnosticar(pipeline.Lote())
    assert diag['pode_continuar'] is False
