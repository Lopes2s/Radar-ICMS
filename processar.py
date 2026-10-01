# processar.py
"""CLI: python processar.py <pasta_com_pdfs> [--banco arquivo.db] [--xlsx saida.xlsx]

Persiste no banco por padrão. A planilha é uma exportação opcional (--xlsx).
"""
import glob
import os
import sys

from core.bootstrap import DEPS_CLI, garantir_dependencias, tolera_encoding_do_console


def main(argv=None) -> int:
    # Antes de qualquer print (inclusive os de uso/erro abaixo, que já podem
    # levar acento ou o nome de uma pasta acentuada): ver
    # core/bootstrap.tolera_encoding_do_console.
    tolera_encoding_do_console()

    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Uso: python processar.py <pasta_com_pdfs> [--banco arquivo.db] "
              "[--xlsx saida.xlsx]")
        return 1

    pasta = argv[0]
    try:
        banco = _opcao(argv, "--banco")
        xlsx = _opcao(argv, "--xlsx")
    except ValueError as erro:
        print(f"Uso: python processar.py <pasta_com_pdfs> [--banco arquivo.db] "
              f"[--xlsx saida.xlsx]\n({erro})")
        return 1

    pdfs = sorted(glob.glob(os.path.join(pasta, "*.pdf")))
    if not pdfs:
        print(f"Nenhum PDF encontrado em {pasta}")
        return 1

    # dentro do main (e não no import) para que importar este módulo — nos
    # testes, por exemplo — nunca dispare um pip install.
    garantir_dependencias(DEPS_CLI)
    from core import armazenamento, pipeline, planilha  # noqa: E402

    lote = pipeline.Lote()
    for caminho in pdfs:
        linha = pipeline.processar_arquivo(lote, caminho, os.path.basename(caminho))
        _imprime_linha(linha)
    pipeline.finalizar(lote)

    conn = armazenamento.conectar(banco)
    armazenamento.criar_esquema(conn)
    resultado = armazenamento.persistir_lote(conn, lote)

    if xlsx:
        try:
            planilha.gerar_xlsx(xlsx, lote.consultas, lote.regimes,
                                lote.descartes, lote.arquivos)
        except PermissionError:
            print(f"\nNão foi possível gravar {xlsx}.\n"
                  "Se a planilha estiver aberta no Excel, feche-a e rode de novo.",
                  file=sys.stderr)
            return 1

    print(f"\n✓ Consultas: {resultado['consultas']['novos']} novas, "
          f"{resultado['consultas']['atualizados']} atualizadas")
    print(f"  Regimes:   {resultado['regimes']['novos']} novos, "
          f"{resultado['regimes']['atualizados']} atualizados")
    if xlsx:
        print(f"  Planilha:  {xlsx}")
    return 0


def _opcao(argv: list, nome: str) -> str | None:
    if nome not in argv:
        return None
    i = argv.index(nome)
    if i + 1 >= len(argv):
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


if __name__ == "__main__":
    sys.exit(main())
