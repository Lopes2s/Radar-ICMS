# tests/test_processar.py
import io
import os
import shutil
import sys

from openpyxl import load_workbook

import processar
from core import armazenamento

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _stdout_ascii_estrito(monkeypatch):
    """Substitui sys.stdout por um stream que só aceita ASCII — o mesmo
    comportamento de um console/pipe sem suporte a UTF-8 (redirecionamento,
    Git Bash/mintty, tarefa agendada) que causava UnicodeEncodeError antes
    da correção em processar.main()."""
    buf = io.BytesIO()
    fake = io.TextIOWrapper(buf, encoding='ascii', errors='strict')
    monkeypatch.setattr(sys, 'stdout', fake)
    return fake, buf


def _aba_arquivos(saida):
    ws = load_workbook(saida)["Arquivos processados"]
    linhas = list(ws.iter_rows(values_only=True))
    cab = linhas[0]
    return [dict(zip(cab, lin)) for lin in linhas[1:]]


def test_importar_processar_nao_roda_o_bootstrap(monkeypatch):
    import importlib
    chamou = []
    monkeypatch.setattr('core.bootstrap.garantir_dependencias',
                        lambda *a, **k: chamou.append(a))
    importlib.reload(processar)
    assert chamou == []


def test_persiste_no_banco_por_padrao(tmp_path):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")
    banco = tmp_path / "m.db"

    codigo = processar.main([str(pasta), "--banco", str(banco)])

    assert codigo == 0
    conn = armazenamento.conectar(str(banco))
    assert len(armazenamento.buscar_consultas(conn)) == 3


def test_xlsx_e_opcional_e_nao_obrigatorio(tmp_path):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")

    codigo = processar.main([str(pasta), "--banco", str(tmp_path / "m.db")])

    assert codigo == 0
    assert not (tmp_path / "saida.xlsx").exists()  # nada gerado sem --xlsx


def test_xlsx_gerado_quando_pedido_explicitamente(tmp_path):
    pasta = tmp_path / "Consultas São José"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"),
                pasta / "Consultas de março.pdf")
    (pasta / "corrompido.pdf").write_bytes(b"isto nao e um pdf")
    xlsx = tmp_path / "saida.xlsx"

    codigo = processar.main([str(pasta), "--banco", str(tmp_path / "m.db"),
                             "--xlsx", str(xlsx)])

    assert codigo == 2
    wb = load_workbook(xlsx)
    assert "Consultas — a revisar" in wb.sheetnames
    arquivos = {a['Arquivo']: a for a in _aba_arquivos(xlsx)}
    assert arquivos["Consultas de março.pdf"]['Tipo'] == 'consulta'
    assert arquivos["Consultas de março.pdf"]['Consultas'] == 3
    assert arquivos["corrompido.pdf"]['Tipo'] == 'erro'
    assert arquivos["corrompido.pdf"]['Erro']


def test_planilha_aberta_no_excel_da_mensagem_clara(tmp_path, monkeypatch, capsys):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")

    def _bloqueado(*a, **k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr('core.planilha.gerar_xlsx', _bloqueado)

    codigo = processar.main([str(pasta), "--banco", str(tmp_path / "m.db"),
                             "--xlsx", str(tmp_path / "saida.xlsx")])

    assert codigo == 1
    err = capsys.readouterr().err
    assert "Não foi possível gravar" in err
    assert "aberta" in err


def test_sem_argumentos_mostra_uso(capsys):
    assert processar.main([]) == 1
    assert "Uso:" in capsys.readouterr().out


def test_pasta_sem_pdf(tmp_path, capsys):
    assert processar.main([str(tmp_path)]) == 1
    assert "Nenhum PDF" in capsys.readouterr().out


def test_flag_sem_valor_nao_quebra_com_traceback(tmp_path, capsys):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")

    codigo = processar.main([str(pasta), "--banco"])

    assert codigo == 1
    assert "Uso:" in capsys.readouterr().out


def test_saida_com_acento_nao_quebra_em_console_ascii(tmp_path, monkeypatch):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")
    fake, buf = _stdout_ascii_estrito(monkeypatch)

    codigo = processar.main([str(pasta), "--banco", str(tmp_path / "m.db")])

    fake.flush()
    assert codigo == 0  # sucesso não pode virar código 1 só por causa do print
    saida = buf.getvalue().decode('ascii')
    assert "Consultas" in saida  # os acentos viraram '?', mas não travou


def test_processar_grava_o_log_na_pasta_de_dados(tmp_path):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")

    processar.main([str(pasta), "--banco", str(tmp_path / "m.db")])

    assert os.path.exists(os.path.join(os.environ["MAPEADOR_DADOS"], "logs", "app.log"))


def _pasta_com(tmp_path, *, corrompido=False):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")
    if corrompido:
        (pasta / "corrompido.pdf").write_bytes(b"isto nao e um pdf")
    return pasta


def test_pdf_com_erro_sai_com_2_grava_os_bons_e_nomeia_o_erro(tmp_path, capsys):
    pasta = _pasta_com(tmp_path, corrompido=True)
    banco = tmp_path / "m.db"

    codigo = processar.main([str(pasta), "--banco", str(banco)])

    assert codigo == 2
    conn = armazenamento.conectar(str(banco))
    assert len(armazenamento.buscar_consultas(conn)) == 3  # os bons foram gravados
    err = capsys.readouterr().err
    assert "corrompido.pdf" in err
    assert "Erro" in err or "erro" in err


def test_simular_nao_grava_e_mostra_o_diagnostico(tmp_path, capsys):
    pasta = _pasta_com(tmp_path)
    banco = tmp_path / "m.db"

    codigo = processar.main([str(pasta), "--banco", str(banco), "--simular"])

    assert codigo == 0
    assert not banco.exists()
    assert "nada foi gravado" in capsys.readouterr().out


def test_dedup_invalido_mostra_o_uso(tmp_path, capsys):
    pasta = _pasta_com(tmp_path)
    codigo = processar.main([str(pasta), "--dedup", "aleatorio"])
    assert codigo == 1
    assert "Uso:" in capsys.readouterr().out


def test_dedup_valido_e_aceito(tmp_path):
    pasta = _pasta_com(tmp_path)
    codigo = processar.main([str(pasta), "--banco", str(tmp_path / "m.db"),
                             "--dedup", "completo"])
    assert codigo == 0


def test_banco_de_versao_mais_nova_sai_com_1_e_mensagem(tmp_path, capsys):
    pasta = _pasta_com(tmp_path)
    banco = tmp_path / "m.db"
    conn = armazenamento.conectar(str(banco))
    conn.execute(f"PRAGMA user_version = {armazenamento.SCHEMA_VERSAO + 1}")
    conn.commit()
    conn.close()

    codigo = processar.main([str(pasta), "--banco", str(banco)])

    assert codigo == 1
    assert "mais nova" in capsys.readouterr().err


def test_schema_mais_novo_tambem_lista_o_arquivo_com_erro(tmp_path, capsys):
    pasta = _pasta_com(tmp_path, corrompido=True)
    banco = tmp_path / "m.db"
    conn = armazenamento.conectar(str(banco))
    conn.execute(f"PRAGMA user_version = {armazenamento.SCHEMA_VERSAO + 1}")
    conn.commit()
    conn.close()

    codigo = processar.main([str(pasta), "--banco", str(banco)])

    assert codigo == 1
    err = capsys.readouterr().err
    assert "mais nova" in err
    assert "corrompido.pdf" in err


def test_opcao_nao_aceita_outra_flag_como_valor(tmp_path, capsys, monkeypatch):
    pasta = _pasta_com(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    codigo = processar.main([str(pasta), "--banco", "--dedup", "completo"])

    assert codigo == 1
    assert "Uso:" in capsys.readouterr().out
    assert not (cwd / "--dedup").exists()


# --- ajustes manuais x reimportação ----------------------------------------
def _importa_e_ajusta_o_protocolo(tmp_path):
    """Importa o PDF de consultas e, como o administrador faria na interface, ajusta o
    Protocolo da consulta 001/2026. Devolve (pasta, banco)."""
    from core import edicao
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")
    banco = tmp_path / "m.db"
    assert processar.main([str(pasta), "--banco", str(banco)]) == 0
    conn = armazenamento.conectar(str(banco))
    edicao.editar_registro(conn, 'consulta', {'Ano': '2026', 'Nº da Consulta': '001'},
                           {'Protocolo': 'AJUSTADO'})
    conn.close()
    return pasta, banco


def _protocolo(banco):
    conn = armazenamento.conectar(str(banco))
    try:
        achado = [r for r in armazenamento.buscar_consultas(conn) if r['Nº da Consulta'] == '001']
        return achado[0]['Protocolo']
    finally:
        conn.close()


def test_reimportar_mantem_o_ajuste_manual_e_avisa(tmp_path, capsys):
    pasta, banco = _importa_e_ajusta_o_protocolo(tmp_path)
    capsys.readouterr()

    codigo = processar.main([str(pasta), "--banco", str(banco)])

    assert codigo == 0
    assert _protocolo(banco) == 'AJUSTADO'
    saida = capsys.readouterr().out
    assert "Ajustes manuais encontrados" in saida and "Consulta 001/2026" in saida
    assert "mantidos" in saida


def test_sobrescrever_ajustes_aplica_o_valor_do_pdf(tmp_path, capsys):
    pasta, banco = _importa_e_ajusta_o_protocolo(tmp_path)
    capsys.readouterr()

    codigo = processar.main([str(pasta), "--banco", str(banco), "--sobrescrever-ajustes"])

    assert codigo == 0
    assert _protocolo(banco) == '25.152.191-3'
    assert "Valor do PDF aplicado" in capsys.readouterr().out


def test_simular_mostra_os_ajustes_sem_alterar_o_banco(tmp_path, capsys):
    pasta, banco = _importa_e_ajusta_o_protocolo(tmp_path)
    capsys.readouterr()
    conn = armazenamento.conectar(str(banco))
    antes = conn.execute("SELECT COUNT(*) FROM historico").fetchone()[0]
    conn.close()

    codigo = processar.main([str(pasta), "--banco", str(banco), "--simular"])

    assert codigo == 0
    assert "Ajustes manuais encontrados" in capsys.readouterr().out
    assert _protocolo(banco) == 'AJUSTADO'
    conn = armazenamento.conectar(str(banco))
    assert conn.execute("SELECT COUNT(*) FROM historico").fetchone()[0] == antes
    conn.close()


def test_simular_em_banco_do_schema_antigo_nao_o_migra(tmp_path):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Consultas_1_a_3_de_2026.pdf"), pasta / "c.pdf")
    banco = tmp_path / "antigo.db"
    conn = armazenamento.conectar(str(banco))
    armazenamento.criar_esquema(conn)
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()

    assert processar.main([str(pasta), "--banco", str(banco), "--simular"]) == 0

    conn = armazenamento.conectar(str(banco))
    assert armazenamento.versao_do_schema(conn) == 2      # continua como estava
    conn.close()

# --- consulta do CNPJ ao gravar (BrasilAPI) ----------------------------------
def _pasta_com_regime(tmp_path):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(os.path.join(FIX, "Regime_Agroantunes.pdf"), pasta / "r.pdf")
    return pasta


def _com_rede(monkeypatch):
    from tests.test_cnpj import Rede
    rede = Rede()
    monkeypatch.setenv("MAPEADOR_CONSULTA_CNPJ", "1")
    monkeypatch.setattr("core.cnpj._abrir", rede)
    return rede


def test_cli_consulta_o_cnpj_do_regime_ao_gravar(tmp_path, monkeypatch, capsys):
    rede = _com_rede(monkeypatch)
    banco = tmp_path / "b.db"
    codigo = processar.main([str(_pasta_com_regime(tmp_path)), "--banco", str(banco)])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert len(rede.urls) == 1
    assert "Receita:   1 CNPJ(s) consultado(s)" in saida
    conn = armazenamento.conectar(str(banco))
    assert conn.execute("SELECT COUNT(*) FROM cnpj_receita").fetchone()[0] == 1
    conn.close()


def test_cli_sem_consulta_cnpj_nao_chama_a_rede(tmp_path, monkeypatch, capsys):
    rede = _com_rede(monkeypatch)
    codigo = processar.main([str(_pasta_com_regime(tmp_path)), "--banco", str(tmp_path / "b.db"),
                             "--sem-consulta-cnpj"])
    assert codigo == 0 and rede.urls == []
    assert "Receita:" not in capsys.readouterr().out


def test_cli_simular_nao_consulta_o_cnpj(tmp_path, monkeypatch, capsys):
    rede = _com_rede(monkeypatch)
    codigo = processar.main([str(_pasta_com_regime(tmp_path)), "--banco", str(tmp_path / "b.db"),
                             "--simular"])
    assert codigo == 0 and rede.urls == []
    assert not os.path.exists(tmp_path / "b.db")


def test_cli_sem_internet_grava_e_avisa(tmp_path, monkeypatch, capsys):
    import urllib.error
    from tests.test_cnpj import Rede
    monkeypatch.setenv("MAPEADOR_CONSULTA_CNPJ", "1")
    monkeypatch.setattr("core.cnpj._abrir", Rede(erro=urllib.error.URLError("sem rede")))
    banco = tmp_path / "b.db"
    codigo = processar.main([str(_pasta_com_regime(tmp_path)), "--banco", str(banco)])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "Regimes:   1 novos" in saida
    assert "Receita:   1 sem resposta" in saida
    conn = armazenamento.conectar(str(banco))
    assert len(armazenamento.buscar_regimes(conn)) == 1
    conn.close()
