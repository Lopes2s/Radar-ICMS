# tests/test_armazenamento.py
from core import armazenamento, pipeline


def _conn(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "teste.db"))
    armazenamento.criar_esquema(conn)
    return conn


def test_criar_esquema_e_idempotente(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.criar_esquema(conn)  # chamar de novo não pode quebrar
    armazenamento.criar_esquema(conn)


# Regressão: um banco já existente (ex.: mapeamento.db já commitado no
# repositório, criado antes do campo Resposta existir) tem a tabela
# "consultas" sem essa coluna. CREATE TABLE IF NOT EXISTS não altera uma
# tabela já criada — sem uma migração aditiva, o próximo salvar_consultas()
# quebraria com "no such column: Resposta".

def test_criar_esquema_adiciona_coluna_nova_em_tabela_ja_existente(tmp_path):
    caminho = str(tmp_path / "antigo.db")
    conn = armazenamento.conectar(caminho)
    conn.execute(
        'CREATE TABLE consultas ("Ano" TEXT, "Nº da Consulta" TEXT, '
        'UNIQUE("Ano", "Nº da Consulta"))'
    )
    conn.commit()

    armazenamento.criar_esquema(conn)

    resultado = armazenamento.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Resposta': 'texto da resposta'},
    ])
    assert resultado == {'novos': 1, 'atualizados': 0}
    assert armazenamento.buscar_consultas(conn)[0]['Resposta'] == 'texto da resposta'


def test_salva_consulta_nova(tmp_path):
    conn = _conn(tmp_path)
    resultado = armazenamento.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
         'Protocolo': '25.152.191-3', 'Súmula': 'ICMS. X.',
         'Problema da Consulta': 'fabricante de embalagens de madeira',
         'CNAE Detectado': '1623-4/00'},
    ])
    assert resultado == {'novos': 1, 'atualizados': 0}
    linhas = armazenamento.buscar_consultas(conn)
    assert len(linhas) == 1
    assert linhas[0]['Súmula'] == 'ICMS. X.'


def test_reprocessar_a_mesma_consulta_atualiza_em_vez_de_duplicar(tmp_path):
    conn = _conn(tmp_path)
    base = {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
            'Protocolo': '', 'Súmula': 'ICMS. X.', 'Problema da Consulta': 'a',
            'CNAE Detectado': ''}
    armazenamento.salvar_consultas(conn, [base])
    corrigida = {**base, 'Protocolo': '25.152.191-3'}  # parser corrigido depois

    resultado = armazenamento.salvar_consultas(conn, [corrigida])

    assert resultado == {'novos': 0, 'atualizados': 1}
    linhas = armazenamento.buscar_consultas(conn)
    assert len(linhas) == 1  # não duplicou
    assert linhas[0]['Protocolo'] == '25.152.191-3'  # ficou com o dado mais novo


def test_ano_diferente_nao_conflita_com_a_chave(tmp_path):
    # numeração reinicia a cada ano (mesmo caso que pipeline.CHAVE_CONSULTAS
    # já trata na deduplicação em memória)
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [
        {'Ano': '2023', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'de 2023', 'Problema da Consulta': '',
         'CNAE Detectado': ''},
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'de 2026', 'Problema da Consulta': '',
         'CNAE Detectado': ''},
    ])
    assert len(armazenamento.buscar_consultas(conn)) == 2


def test_busca_por_texto_livre_no_problema_ou_na_sumula(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS. DIFERIMENTO.',
         'Problema da Consulta': 'fabricante de embalagens de madeira',
         'CNAE Detectado': ''},
        {'Ano': '2026', 'Nº da Consulta': '002', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': 'ICMS. ISENÇÃO.',
         'Problema da Consulta': 'produtor rural', 'CNAE Detectado': ''},
    ])
    achadas = armazenamento.buscar_consultas(conn, texto='madeira')
    assert [r['Nº da Consulta'] for r in achadas] == ['001']


def test_busca_por_ano_filtra_corretamente(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [
        {'Ano': '2023', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': '', 'Problema da Consulta': '', 'CNAE Detectado': ''},
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': '', 'Problema da Consulta': '', 'CNAE Detectado': ''},
    ])
    achadas = armazenamento.buscar_consultas(conn, ano='2026')
    assert [r['Ano'] for r in achadas] == ['2026']


def test_busca_por_texto_e_ano_combinados_usa_and(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [
        {'Ano': '2023', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': '', 'Problema da Consulta': 'madeira',
         'CNAE Detectado': ''},
        {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
         'Protocolo': '', 'Súmula': '', 'Problema da Consulta': 'madeira',
         'CNAE Detectado': ''},
    ])
    achadas = armazenamento.buscar_consultas(conn, texto='madeira', ano='2026')
    assert len(achadas) == 1 and achadas[0]['Ano'] == '2026'


def test_conectar_sem_caminho_usa_arquivo_na_raiz_do_projeto():
    assert armazenamento._CAMINHO_PADRAO.endswith('mapeamento.db')


def test_criar_esquema_adiciona_colunas_novas_de_regimes_em_tabela_ja_existente(tmp_path):
    caminho = str(tmp_path / "antigo_regimes.db")
    conn = armazenamento.conectar(caminho)
    conn.execute(
        'CREATE TABLE regimes ("Nº DO REGIME ESPECIAL" TEXT, '
        '"CNPJ REQUERENTE" TEXT, '
        'UNIQUE("Nº DO REGIME ESPECIAL", "CNPJ REQUERENTE"))'
    )
    conn.commit()

    armazenamento.criar_esquema(conn)

    resultado = armazenamento.salvar_regimes(conn, [
        {'Nº DO REGIME ESPECIAL': '8.715/2025', 'CNPJ REQUERENTE': '85.090.033/0001-22',
         'ABRANGÊNCIA': 'texto'},
    ])
    assert resultado == {'novos': 1, 'atualizados': 0}
    assert armazenamento.buscar_regimes(conn)[0]['ABRANGÊNCIA'] == 'texto'


def test_salva_e_busca_regime(tmp_path):
    conn = _conn(tmp_path)
    resultado = armazenamento.salvar_regimes(conn, [
        {'ANO': '2026', 'DATA': '2026-08-14', 'Nº DOE': '12.196',
         'RE PR COMPETITIVO': 'Não', 'Nº DO REGIME ESPECIAL': '9.055/2026',
         'EMPRESA': 'KRONA TUBOS E CONEXÕES LTDA',
         'CNPJ REQUERENTE': '00.145.602/0001-37', 'CAD/ICMS': '09903134-40',
         'CNAE REQUERENTE': '', 'DESCRIÇÃO CNAE': '', 'VIGÊNCIA DO RE': '',
         'EMENTA': 'Alteração do Regime Especial nº 6.247/2019'},
    ])
    assert resultado == {'novos': 1, 'atualizados': 0}
    achados = armazenamento.buscar_regimes(conn, texto='KRONA')
    assert len(achados) == 1


def test_chave_de_regime_e_re_mais_cnpj_nao_so_re(tmp_path):
    # o mesmo Nº DO REGIME ESPECIAL com CNPJ diferente é outro registro --
    # suposição sobre o domínio já embutida em pipeline.CHAVE_REGIMES
    # (core/pipeline.py:14); este teste só documenta a consequência no banco.
    conn = _conn(tmp_path)
    base = {'ANO': '2026', 'DATA': '', 'Nº DOE': '', 'RE PR COMPETITIVO': '',
            'Nº DO REGIME ESPECIAL': '9.055/2026', 'EMPRESA': 'A',
            'CNPJ REQUERENTE': '11.111.111/0001-11', 'CAD/ICMS': '',
            'CNAE REQUERENTE': '', 'DESCRIÇÃO CNAE': '', 'VIGÊNCIA DO RE': '',
            'EMENTA': ''}
    armazenamento.salvar_regimes(conn, [base, {**base, 'CNPJ REQUERENTE': '22.222.222/0001-22'}])
    assert len(armazenamento.buscar_regimes(conn)) == 2


def test_persistir_lote_grava_consultas_e_regimes_de_uma_vez(tmp_path):
    conn = _conn(tmp_path)
    lote = pipeline.Lote(
        consultas=[{'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '',
                   'Protocolo': '', 'Súmula': '', 'Problema da Consulta': '',
                   'CNAE Detectado': ''}],
        regimes=[{'ANO': '2026', 'DATA': '', 'Nº DOE': '', 'RE PR COMPETITIVO': '',
                 'Nº DO REGIME ESPECIAL': '1/2026', 'EMPRESA': '', 'CNPJ REQUERENTE': '',
                 'CAD/ICMS': '', 'CNAE REQUERENTE': '', 'DESCRIÇÃO CNAE': '',
                 'VIGÊNCIA DO RE': '', 'EMENTA': ''}],
    )
    resultado = armazenamento.persistir_lote(conn, lote)
    assert resultado == {'consultas': {'novos': 1, 'atualizados': 0},
                         'regimes': {'novos': 1, 'atualizados': 0}}
    assert len(armazenamento.buscar_consultas(conn)) == 1
    assert len(armazenamento.buscar_regimes(conn)) == 1
