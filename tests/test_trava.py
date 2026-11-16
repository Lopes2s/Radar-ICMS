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
