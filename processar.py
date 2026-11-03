# processar.py
"""CLI: python processar.py <pasta_com_pdfs> [--banco arquivo.db] [--xlsx saida.xlsx]
                            [--dedup primeira|completo|recente] [--simular]
                            [--sobrescrever-ajustes]

Persiste no banco por padrão. A planilha é uma exportação opcional (--xlsx).
--simular lê e diagnostica os PDFs sem gravar nada.
Atos que o administrador ajustou à mão na interface MANTÊM o valor ajustado ao
reimportar; --sobrescrever-ajustes faz o valor do PDF vencer em todos eles.

Códigos de saída: 0 = tudo certo; 1 = uso incorreto, nenhum PDF, planilha
aberta no Excel ou banco de versão mais nova; 2 = algum PDF não pôde ser lido
(os demais foram processados e gravados normalmente).
"""
import glob
import os
import sys

from core.bootstrap import DEPS_CLI, garantir_dependencias, tolera_encoding_do_console

_USO = ("Uso: python processar.py <pasta_com_pdfs> [--banco arquivo.db] "
        "[--xlsx saida.xlsx] [--dedup primeira|completo|recente] [--simular] "
        "[--sobrescrever-ajustes]")


def main(argv=None) -> int:
    # Antes de qualquer print (inclusive os de uso/erro abaixo, que já podem
    # levar acento ou o nome de uma pasta acentuada): ver
    # core/bootstrap.tolera_encoding_do_console.
    tolera_encoding_do_console()

    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(_USO)
        return 1

    pasta = argv[0]
    try:
        banco = _opcao(argv, "--banco")
        xlsx = _opcao(argv, "--xlsx")
        dedup = _opcao(argv, "--dedup")
    except ValueError as erro:
        print(f"{_USO}\n({erro})")
        return 1
    simular = "--simular" in argv
    sobrescrever_ajustes = "--sobrescrever-ajustes" in argv

    pdfs = sorted(glob.glob(os.path.join(pasta, "*.pdf")))
    if not pdfs:
        print(f"Nenhum PDF encontrado em {pasta}")
        return 1

    # dentro do main (e não no import) para que importar este módulo — nos
    # testes, por exemplo — nunca dispare um pip install.
    garantir_dependencias(DEPS_CLI)
    from core import armazenamento, edicao, log, pipeline, planilha  # noqa: E402
    from core.execucao import Execucao  # noqa: E402

    dedup = dedup or pipeline.CRITERIO_PADRAO
    if dedup not in pipeline.CRITERIOS_DEDUP:
        print(f"{_USO}\n(--dedup deve ser um de {', '.join(pipeline.CRITERIOS_DEDUP)})")
        return 1

    log.configurar_log(armazenamento.pasta_dados())

    execucao = Execucao(ao_arquivo=_imprime_linha, dedup=dedup)
    lote = execucao.carregar([(c, os.path.basename(c)) for c in pdfs])
    _imprime_diagnostico(execucao.diagnostico)
    erros = execucao.arquivos_com_erro()

    if simular:
        _conflitos_na_simulacao(armazenamento, edicao, banco, lote)
        print("\nSimulação: nada foi gravado no banco.")
        return _finaliza(erros)

    try:
        with armazenamento.sessao(banco) as conn:
            conflitos = edicao.ajustes_em_conflito(conn, lote)
            _imprime_conflitos(conflitos, sobrescrever_ajustes)
            sobrescrever = ([edicao.chave_do_item(i) for i in conflitos]
                            if sobrescrever_ajustes else ())
            resultado = execucao.gravar(conn, sobrescrever)
    except armazenamento.SchemaMaisNovo as erro:
        print(f"\n{erro}", file=sys.stderr)
        _imprime_erros(erros)
        return 1

    if xlsx:
        try:
            planilha.gerar_xlsx(xlsx, lote.consultas, lote.regimes,
                                lote.descartes, lote.arquivos)
        except PermissionError:
            print(f"\nNão foi possível gravar {xlsx}.\n"
                  "Se a planilha estiver aberta no Excel, feche-a e rode de novo.",
                  file=sys.stderr)
            _imprime_erros(erros)
            return 1

    print(f"\n✓ Consultas: {resultado['consultas']['novos']} novas, "
          f"{resultado['consultas']['atualizados']} atualizadas")
    print(f"  Regimes:   {resultado['regimes']['novos']} novos, "
          f"{resultado['regimes']['atualizados']} atualizados")
    if xlsx:
        print(f"  Planilha:  {xlsx}")
    return _finaliza(erros)


def _imprime_conflitos(conflitos: list, sobrescrevendo: bool) -> None:
    """Atos com ajuste manual cujo valor difere do PDF."""
    if not conflitos:
        return
    print(f"\nAjustes manuais encontrados em {len(conflitos)} ato(s):")
    for item in conflitos:
        for c in item['campos']:
            print(f"  - {item['rotulo']} · {c['campo']}: ajustado {c['atual']!r} | PDF {c['pdf']!r}")
    print("Valor do PDF aplicado (--sobrescrever-ajustes)." if sobrescrevendo else
          "Valores ajustados mantidos. Use --sobrescrever-ajustes para aplicar o PDF.")


def _conflitos_na_simulacao(armazenamento, edicao, banco, lote) -> None:
    """Na simulação só LÊ: se o banco já existe e está no schema atual, mostra os
    ajustes que seriam mantidos; nunca cria nem migra o banco."""
    if not os.path.exists(armazenamento.caminho_do_banco(banco)):
        return
    with armazenamento.aberta(banco) as conn:
        if armazenamento.versao_do_schema(conn) < armazenamento.SCHEMA_VERSAO:
            return
        _imprime_conflitos(edicao.ajustes_em_conflito(conn, lote), False)


def _finaliza(erros: list) -> int:
    """0 se todos os PDFs foram lidos; senão lista cada erro em stderr e devolve 2."""
    if not erros:
        return 0
    _imprime_erros(erros)
    return 2


def _imprime_erros(erros: list) -> None:
    """Lista cada arquivo com erro em stderr (nada se não houver)."""
    if not erros:
        return
    print("\nArquivos com erro (os demais foram processados):", file=sys.stderr)
    for linha in erros:
        print(f"  - {linha['Arquivo']}: {linha['Erro']}", file=sys.stderr)


def _opcao(argv: list, nome: str) -> str | None:
    if nome not in argv:
        return None
    i = argv.index(nome)
    if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
        raise ValueError(f"{nome} exige um valor")
    return argv[i + 1]


def _imprime_linha(linha: dict) -> None:
    nome, tipo = linha['Arquivo'], linha['Tipo']
    if tipo == 'consulta':
        print(f"[consulta] {nome}: {linha['Consultas']} extraídas")
    elif tipo == 'regime':
        print(f"[regime]   {nome}: {linha['Regimes']} extraídos, "
              f"{linha['Descartes']} descartados")
    elif tipo == 'erro':
        print(f"[ERRO]     {nome}: {linha['Erro']}")
    else:
        print(f"[?]        {nome}: tipo não identificado — pulado")


def _imprime_diagnostico(diag: dict) -> None:
    if not diag['mensagens']:
        return
    print("\nDiagnóstico:")
    for m in diag['mensagens']:
        print(f"  [{m['nivel'].upper()}] {m['codigo']} {m['titulo']}: {m['texto']}")


if __name__ == "__main__":
    sys.exit(main())
