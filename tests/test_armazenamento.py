# tests/test_armazenamento.py
import pytest

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


import os


def test_pasta_dados_usa_a_variavel_e_cria_a_pasta(tmp_path, monkeypatch):
    alvo = tmp_path / "dados" / "fundo"
    monkeypatch.setenv("MAPEADOR_DADOS", str(alvo))
    assert armazenamento.pasta_dados() == str(alvo)
    assert alvo.is_dir()


def test_pasta_dados_sem_variavel_e_a_raiz_do_projeto(monkeypatch):
    monkeypatch.delenv("MAPEADOR_DADOS", raising=False)
    assert armazenamento.pasta_dados() == armazenamento._RAIZ


def test_caminho_do_banco_respeita_a_precedencia(tmp_path, monkeypatch):
    monkeypatch.setenv("MAPEADOR_DADOS", str(tmp_path))
    monkeypatch.delenv("MAPEADOR_BANCO", raising=False)
    assert armazenamento.caminho_do_banco() == os.path.join(str(tmp_path), "mapeamento.db")
    monkeypatch.setenv("MAPEADOR_BANCO", str(tmp_path / "x.db"))
    assert armazenamento.caminho_do_banco() == str(tmp_path / "x.db")
    assert armazenamento.caminho_do_banco("explicito.db") == "explicito.db"


def test_conectar_sem_caminho_cai_na_pasta_de_dados(tmp_path, monkeypatch):
    monkeypatch.setenv("MAPEADOR_DADOS", str(tmp_path))
    monkeypatch.delenv("MAPEADOR_BANCO", raising=False)
    conn = armazenamento.conectar()
    conn.execute("CREATE TABLE t (x)")
    conn.commit()
    conn.close()
    assert (tmp_path / "mapeamento.db").exists()


import sqlite3

import pytest


def test_aberta_fecha_a_conexao_ao_sair(tmp_path):
    with armazenamento.aberta(str(tmp_path / "a.db")) as conn:
        conn.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_sessao_cria_o_esquema_e_fecha_mesmo_com_erro(tmp_path):
    caminho = str(tmp_path / "s.db")
    with pytest.raises(RuntimeError):
        with armazenamento.sessao(caminho) as conn:
            assert armazenamento.buscar_consultas(conn) == []
            raise RuntimeError("falha")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_criar_esquema_grava_a_versao_do_schema(tmp_path):
    conn = _conn(tmp_path)
    assert armazenamento.versao_do_schema(conn) == armazenamento.SCHEMA_VERSAO


def test_banco_antigo_sem_versao_e_atualizado_sem_perder_dados(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "antigo.db"))
    conn.execute('CREATE TABLE consultas ("Ano" TEXT, "Nº da Consulta" TEXT, '
                 'UNIQUE("Ano", "Nº da Consulta"))')
    conn.execute("INSERT INTO consultas VALUES (?, ?)", ("2025", "007"))
    conn.commit()
    assert armazenamento.versao_do_schema(conn) == 0

    armazenamento.criar_esquema(conn)

    assert armazenamento.versao_do_schema(conn) == armazenamento.SCHEMA_VERSAO
    assert armazenamento.buscar_consultas(conn)[0]["Nº da Consulta"] == "007"


def test_banco_de_versao_mais_nova_e_recusado_sem_ser_alterado(tmp_path):
    conn = armazenamento.conectar(str(tmp_path / "novo.db"))
    conn.execute(f"PRAGMA user_version = {armazenamento.SCHEMA_VERSAO + 1}")
    conn.commit()

    with pytest.raises(armazenamento.SchemaMaisNovo) as exc:
        armazenamento.criar_esquema(conn)

    assert str(armazenamento.SCHEMA_VERSAO + 1) in str(exc.value)
    criou = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'consultas'").fetchone()
    assert criou is None


def _consulta(**campos):
    base = {'Ano': '2026', 'Nº da Consulta': '001', 'Data da Publicação': '2026-01-19',
            'Protocolo': '', 'Súmula': '', 'Problema da Consulta': '',
            'CNAE Detectado': '', 'Resposta': ''}
    return {**base, **campos}


def test_busca_ignora_acentos_e_caixa(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(**{'Súmula': 'Substituição Tributária'})])
    assert len(armazenamento.buscar_consultas(conn, texto='SUBSTITUICAO')) == 1
    assert len(armazenamento.buscar_consultas(conn, texto='substituição tributária')) == 1


def test_busca_alcanca_a_resposta_mesmo_atravessando_paragrafos(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [
        _consulta(Resposta='primeiro trecho\n\nsegundo trecho do fisco')])
    # a frase atravessa a quebra de parágrafo ("\n\n" vira um espaço na comparação)
    assert len(armazenamento.buscar_consultas(conn, texto='trecho segundo')) == 1
    assert len(armazenamento.buscar_consultas(conn, texto='segundo   trecho')) == 1
    assert len(armazenamento.buscar_consultas(conn, texto='segundo primeiro')) == 0


def test_percentual_e_sublinhado_valem_como_texto_literal(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [
        _consulta(**{'Nº da Consulta': '001', 'Súmula': 'desconto de 10% no preço'}),
        _consulta(**{'Nº da Consulta': '002', 'Súmula': 'prazo de 10 dias'}),
        _consulta(**{'Nº da Consulta': '003', 'Súmula': 'campo_um'}),
        _consulta(**{'Nº da Consulta': '004', 'Súmula': 'campoXum'}),
    ])
    achadas = armazenamento.buscar_consultas(conn, texto='10%')
    assert [r['Nº da Consulta'] for r in achadas] == ['001']
    achadas = armazenamento.buscar_consultas(conn, texto='campo_um')
    assert [r['Nº da Consulta'] for r in achadas] == ['003']


def test_texto_so_com_espacos_equivale_a_sem_filtro(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(), _consulta(**{'Nº da Consulta': '002'})])
    assert len(armazenamento.buscar_consultas(conn, texto='   ')) == 2


def test_busca_de_regime_por_cnpj_e_por_numero(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_regimes(conn, [
        {'ANO': '2026', 'Nº DO REGIME ESPECIAL': '10.001/2026',
         'CNPJ REQUERENTE': '11.222.333/0001-81', 'EMPRESA': 'Alfa'},
        {'ANO': '2026', 'Nº DO REGIME ESPECIAL': '10.002/2026',
         'CNPJ REQUERENTE': '44.555.666/0001-00', 'EMPRESA': 'Beta'},
    ])
    assert [r['EMPRESA'] for r in armazenamento.buscar_regimes(conn, texto='0001-81')] == ['Alfa']
    assert [r['EMPRESA'] for r in armazenamento.buscar_regimes(conn, texto='10.002')] == ['Beta']


def test_buscar_com_colunas_devolve_so_as_pedidas(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(Resposta='texto longo')])
    linhas = armazenamento.buscar_consultas(conn, colunas=['Ano', 'Nº da Consulta'])
    assert list(linhas[0]) == ['Ano', 'Nº da Consulta']


def test_buscar_detalhe_pela_chave_natural(tmp_path):
    conn = _conn(tmp_path)
    armazenamento.salvar_consultas(conn, [_consulta(Resposta='texto longo')])
    achado = armazenamento.buscar_detalhe(
        conn, 'consultas', pipeline.CHAVE_CONSULTAS,
        {'Ano': '2026', 'Nº da Consulta': '001'})
    assert achado['Resposta'] == 'texto longo'
    ausente = armazenamento.buscar_detalhe(
        conn, 'consultas', pipeline.CHAVE_CONSULTAS,
        {'Ano': '1999', 'Nº da Consulta': '9'})
    assert ausente is None


def test_colunas_da_lista_incluem_a_chave_natural():
    assert set(pipeline.CHAVE_CONSULTAS) <= set(armazenamento.COLUNAS_LISTA_CONSULTAS)
    assert set(pipeline.CHAVE_REGIMES) <= set(armazenamento.COLUNAS_LISTA_REGIMES)
