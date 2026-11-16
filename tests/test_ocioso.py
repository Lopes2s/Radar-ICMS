from core.ocioso import VigiaOciosidade


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _vigia(sessoes, relogio, **kw):
    return VigiaOciosidade(lambda: sessoes[0], relogio=relogio,
                           limite_s=600, carencia_s=180, **kw)


def test_nao_encerra_enquanto_houver_navegador():
    rel, sessoes = Relogio(), [1]
    v = _vigia(sessoes, rel)
    rel.t = 10_000
    assert v.deve_encerrar() is False


def test_encerra_depois_do_limite_sem_navegador():
    rel, sessoes = Relogio(), [1]
    v = _vigia(sessoes, rel)
    assert v.deve_encerrar() is False       # viu o navegador
    sessoes[0] = 0
    rel.t = 100
    assert v.deve_encerrar() is False       # começou a contar
    rel.t = 100 + 599
    assert v.deve_encerrar() is False
    rel.t = 100 + 600
    assert v.deve_encerrar() is True


def test_voltar_o_navegador_zera_a_contagem():
    rel, sessoes = Relogio(), [1]
    v = _vigia(sessoes, rel)
    v.deve_encerrar()
    sessoes[0] = 0
    rel.t = 500
    v.deve_encerrar()
    sessoes[0] = 1
    rel.t = 900
    v.deve_encerrar()
    sessoes[0] = 0
    rel.t = 1000
    assert v.deve_encerrar() is False
    rel.t = 1599
    assert v.deve_encerrar() is False
    rel.t = 1600
    assert v.deve_encerrar() is True


def test_carencia_inicial_quando_nunca_apareceu_navegador():
    rel, sessoes = Relogio(), [0]
    v = _vigia(sessoes, rel)
    rel.t = 179
    assert v.deve_encerrar() is False
    rel.t = 180
    assert v.deve_encerrar() is True


def test_sem_como_contar_nunca_encerra():
    rel = Relogio()
    v = VigiaOciosidade(lambda: None, relogio=rel)
    rel.t = 10**9
    assert v.deve_encerrar() is False
