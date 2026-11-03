# core/execucao.py
"""Uma execução completa: carregar -> (diagnosticar) -> gravar.

Usada pela CLI (processar.py) e pela interface (app.py). Fica ACIMA de
pipeline, diagnostico e armazenamento (armazenamento importa pipeline, então
a ordem inversa criaria dependência circular).

Callbacks, no mesmo formato do hub:
  progresso(fase, atual, total, texto)   fase: 'leitura' | 'gravacao'
  ao_arquivo(linha)                      depois de cada PDF (linha de lote.arquivos)
"""
from core import armazenamento, cnpj, diagnostico, pipeline


class Execucao:
    def __init__(self, progresso=None, ao_arquivo=None,
                 dedup: str = pipeline.CRITERIO_PADRAO,
                 consultar_cnpj: bool = True, abrir_cnpj=None):
        if dedup not in pipeline.CRITERIOS_DEDUP:
            raise ValueError(
                f"dedup deve ser um de {pipeline.CRITERIOS_DEDUP}: {dedup!r}")
        self._progresso = progresso or (lambda *args: None)
        self._ao_arquivo = ao_arquivo
        self.dedup = dedup
        self.consultar_cnpj = consultar_cnpj
        self._abrir_cnpj = abrir_cnpj   # só para testes: `abrir(url) -> bytes`
        self.lote = None
        self.diagnostico = None
        self.resumo_cnpj = None   # resultado da consulta de CNPJ do último `gravar`

    def carregar(self, arquivos: list, forcar: str | None = None):
        """Lê os PDFs (`arquivos` = [(caminho, nome), ...]), deduplica pelo
        critério e diagnostica. Um PDF ruim não interrompe os demais."""
        lote = pipeline.Lote()
        total = len(arquivos)
        for i, (caminho, nome) in enumerate(arquivos):
            self._progresso('leitura', i, total, nome)
            linha = pipeline.processar_arquivo(lote, caminho, nome, forcar=forcar)
            if self._ao_arquivo:
                self._ao_arquivo(linha)
        self._progresso('leitura', total, total, '')
        self.lote = pipeline.finalizar(lote, self.dedup)
        self.diagnostico = diagnostico.diagnosticar(self.lote)
        return self.lote

    def gravar(self, conn, sobrescrever=()) -> dict:
        """Persiste o lote carregado. Devolve o resumo de novos/atualizados.

        Depois de gravar, consulta na BrasilAPI o CNPJ dos regimes (CNAE e situação
        cadastral; ver core/cnpj.py). Falha de rede NÃO impede a gravação: o que
        aconteceu fica em `self.resumo_cnpj` (None se a consulta está desligada:
        `consultar_cnpj=False` ou MAPEADOR_CONSULTA_CNPJ=0).

        `sobrescrever`: itens ('consulta'|'regime', *chave) cujos ajustes manuais o
        PDF deve vencer (ver edicao.ajustes_em_conflito); os demais ajustes são mantidos."""
        self._progresso('gravacao', 0, 1, '')
        resultado = armazenamento.persistir_lote(conn, self.lote, sobrescrever)
        if self.consultar_cnpj and cnpj.habilitada():
            self.resumo_cnpj = cnpj.atualizar_do_lote(conn, self.lote,
                                                      abrir=self._abrir_cnpj)
        self._progresso('gravacao', 1, 1, '')
        return resultado

    def arquivos_com_erro(self) -> list:
        return [l for l in self.lote.arquivos if l['Tipo'] == 'erro']
