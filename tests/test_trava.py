import os
from datetime import datetime, timedelta, timezone

import pytest

from core import trava

T0 = datetime(2026, 11, 16, 14, 0, tzinfo=timezone.utc)


def test_adquirir_com_a_pasta_livre_cria_a_trava(tmp_path):
    assert trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0) is None
    assert (tmp_path / trava.NOME_ARQUIVO).exists()
    atual = trava.situacao(str(tmp_path), agora=T0)
    assert (atual.quem, atual.maquina) == ("ana", "PC-01")


def test_segunda_pessoa_recebe_quem_esta_importando(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    outro = trava.adquirir(str(tmp_path), "bia", "PC-02", agora=T0 + timedelta(minutes=1))
    assert (outro.quem, outro.maquina) == ("ana", "PC-01")
    # a trava continua sendo da primeira pessoa
    assert trava.situacao(str(tmp_path), agora=T0).quem == "ana"


def test_trava_vencida_pode_ser_assumida(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    depois = T0 + trava.VALIDADE_PADRAO + timedelta(seconds=1)
    assert trava.situacao(str(tmp_path), agora=depois) is None
    assert trava.adquirir(str(tmp_path), "bia", "PC-02", agora=depois) is None
    assert trava.situacao(str(tmp_path), agora=depois).quem == "bia"


def test_trava_ilegivel_recente_conta_como_ocupada(tmp_path):
    # arquivo criado por outra máquina e ainda sendo escrito: não pode virar "livre"
    (tmp_path / trava.NOME_ARQUIVO).write_text("", encoding="utf-8")
    agora = datetime.now(timezone.utc)
    atual = trava.situacao(str(tmp_path), agora=agora)
    assert atual is not None
    assert trava.adquirir(str(tmp_path), "bia", "PC-02", agora=agora) is not None


def test_trava_ilegivel_antiga_vence_como_qualquer_outra(tmp_path):
    caminho = tmp_path / trava.NOME_ARQUIVO
    caminho.write_text("lixo", encoding="utf-8")
    antigo = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
    os.utime(caminho, (antigo, antigo))
    assert trava.situacao(str(tmp_path)) is None


def test_liberar_so_remove_a_propria_trava(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    assert trava.liberar(str(tmp_path), "bia", "PC-02") is False
    assert (tmp_path / trava.NOME_ARQUIVO).exists()
    assert trava.liberar(str(tmp_path), "ana", "PC-01") is True
    assert not (tmp_path / trava.NOME_ARQUIVO).exists()


def test_importando_libera_ao_sair_mesmo_com_erro(tmp_path):
    with pytest.raises(ValueError):
        with trava.importando(str(tmp_path), "ana", "PC-01"):
            raise ValueError("falhou no meio")
    assert not (tmp_path / trava.NOME_ARQUIVO).exists()


def test_importando_espera_a_trava_ser_liberada(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01")
    dormidas = []

    def dormir(segundos):
        dormidas.append(segundos)
        trava.liberar(str(tmp_path), "ana", "PC-01")      # a ana termina durante a espera

    with trava.importando(str(tmp_path), "bia", "PC-02", esperar_s=10,
                          intervalo_s=2, dormir=dormir):
        assert trava.situacao(str(tmp_path)).quem == "bia"
    assert dormidas == [2]


def test_importando_desiste_depois_do_tempo_de_espera(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01")
    t = [0.0]

    def dormir(segundos):
        t[0] += segundos

    with pytest.raises(trava.ImportacaoEmAndamento):
        with trava.importando(str(tmp_path), "bia", "PC-02", esperar_s=6, intervalo_s=2,
                              dormir=dormir, relogio=lambda: t[0]):
            pass
    assert t[0] == 6
    assert trava.situacao(str(tmp_path)).quem == "ana"    # a trava alheia segue intacta


def test_importando_com_trava_ocupada_levanta_com_o_nome(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01")
    with pytest.raises(trava.ImportacaoEmAndamento, match=r"ana \(PC-01\)") as erro:
        with trava.importando(str(tmp_path), "bia", "PC-02"):
            pass
    assert erro.value.importacao.quem == "ana"


def test_texto_mostra_quem_e_a_hora_local(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    texto = trava.situacao(str(tmp_path), agora=T0).texto()
    assert texto.startswith("ana (PC-01) está gravando desde ")
    hora = texto.rsplit(" ", 1)[1]
    assert len(hora) == 5 and hora[2] == ":"


def _ana_vencida(tmp_path):
    trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    return T0 + trava.VALIDADE_PADRAO + timedelta(seconds=1)


def test_retomada_de_trava_vencida_nao_deixa_mutex(tmp_path):
    depois = _ana_vencida(tmp_path)
    assert trava.adquirir(str(tmp_path), "bia", "PC-02", agora=depois) is None
    assert trava.situacao(str(tmp_path), agora=depois).quem == "bia"
    assert not (tmp_path / trava.NOME_RETOMADA).exists()


def test_mutex_recente_torna_a_retomada_ocupada_sem_mexer_na_trava(tmp_path):
    depois = _ana_vencida(tmp_path)
    (tmp_path / trava.NOME_RETOMADA).write_text("", encoding="utf-8")
    outro = trava.adquirir(str(tmp_path), "bia", "PC-02", agora=depois)
    assert outro is not None
    assert (tmp_path / trava.NOME_ARQUIVO).exists()
    assert (tmp_path / trava.NOME_ARQUIVO).read_text(encoding="utf-8").count('"ana"') == 1
    assert (tmp_path / trava.NOME_RETOMADA).exists()    # não é nosso: intacto


def test_mutex_antigo_e_removido_e_a_retomada_funciona(tmp_path):
    depois = _ana_vencida(tmp_path)
    mutex = tmp_path / trava.NOME_RETOMADA
    mutex.write_text("", encoding="utf-8")
    antigo = (datetime.now(timezone.utc) - timedelta(seconds=60)).timestamp()
    os.utime(mutex, (antigo, antigo))
    assert trava.adquirir(str(tmp_path), "bia", "PC-02", agora=depois) is None
    assert trava.situacao(str(tmp_path), agora=depois).quem == "bia"
    assert not mutex.exists()


def test_corrida_na_retomada_devolve_quem_ganhou(tmp_path, monkeypatch):
    depois = _ana_vencida(tmp_path)
    vivo = trava.Importacao("carlos", "PC-03", depois, depois)
    respostas = iter([None, vivo])        # 1ª leitura: vencida; releitura no mutex: já retomada
    monkeypatch.setattr(trava, "situacao", lambda *a, **k: next(respostas))
    outro = trava.adquirir(str(tmp_path), "bia", "PC-02", agora=depois)
    assert outro == vivo
    assert (tmp_path / trava.NOME_ARQUIVO).exists()     # não foi removida
    assert not (tmp_path / trava.NOME_RETOMADA).exists()


def test_trava_com_datas_sem_fuso_conta_como_ocupada(tmp_path):
    caminho = tmp_path / trava.NOME_ARQUIVO
    caminho.write_text(
        '{"quem": "ana", "maquina": "PC-01", "desde": "2026-11-16T14:00:00", '
        '"renovado_em": "2026-11-16T14:00:00"}', encoding="utf-8")
    assert trava.situacao(str(tmp_path)) is not None      # sem TypeError
    assert trava.adquirir(str(tmp_path), "bia", "PC-02") is not None


def test_falha_na_escrita_nao_deixa_trava_vazia(tmp_path, monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError("disco cheio")
    monkeypatch.setattr(trava.json, "dump", quebra)
    with pytest.raises(RuntimeError):
        trava.adquirir(str(tmp_path), "ana", "PC-01", agora=T0)
    assert not (tmp_path / trava.NOME_ARQUIVO).exists()


def test_liberar_tenta_de_novo_em_permission_error(tmp_path, monkeypatch):
    trava.adquirir(str(tmp_path), "ana", "PC-01")
    real = os.remove
    falhas = {"n": 2}

    def remove(caminho):
        if falhas["n"]:
            falhas["n"] -= 1
            raise PermissionError(32, "em uso")
        real(caminho)

    monkeypatch.setattr(trava.os, "remove", remove)
    esperas = []
    assert trava.liberar(str(tmp_path), "ana", "PC-01", dormir=esperas.append) is True
    assert len(esperas) == 2
    assert trava.situacao(str(tmp_path)) is None


def test_liberar_desiste_depois_das_tentativas(tmp_path, monkeypatch):
    trava.adquirir(str(tmp_path), "ana", "PC-01")
    chamadas = []

    def remove(caminho):
        chamadas.append(caminho)
        raise PermissionError(32, "em uso")

    monkeypatch.setattr(trava.os, "remove", remove)
    assert trava.liberar(str(tmp_path), "ana", "PC-01", dormir=lambda s: None) is False
    assert len(chamadas) == 10
