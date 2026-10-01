# scripts/diag_consultas.py
"""Diagnóstico temporário: por que a âncora de consultas.py perde registros.

Uso:
    python scripts/diag_consultas.py "<caminho_do_pdf>"

Não faz parte do pacote nem é chamado por nada além deste diagnóstico manual.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import pdf_text
from parsers.consultas import _ANCORA

_CONSULTA_LIVRE = re.compile(r'CONSULTA', re.IGNORECASE)


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/diag_consultas.py <caminho_do_pdf>")
        sys.exit(1)

    caminho = sys.argv[1]
    txt = pdf_text.texto_simples(caminho)
    print(f"Tamanho do texto extraído: {len(txt)} caracteres\n")

    ancoras = list(_ANCORA.finditer(txt))
    print(f"Âncoras casadas pela regex ATUAL: {len(ancoras)}")
    for a in ancoras[:5]:
        print(f"  -> nº {a.group(1)!r}  data {a.group(2)!r}")
    if len(ancoras) > 5:
        print(f"  ... (+{len(ancoras) - 5} outras)")
    print()

    todas_consulta = list(_CONSULTA_LIVRE.finditer(txt))
    print(f"Ocorrências da substring 'CONSULTA' (case-insensitive): {len(todas_consulta)}")

    intervalos_casados = [(a.start(), a.end()) for a in ancoras]

    def dentro_de_ancora(pos):
        return any(ini <= pos < fim for ini, fim in intervalos_casados)

    perdidas = [m for m in todas_consulta if not dentro_de_ancora(m.start())]
    print(f"Ocorrências de 'CONSULTA' que NÃO caíram dentro de uma âncora casada: {len(perdidas)}")
    print("(inclui referências dentro do corpo, tipo 'vide Consulta nº X' — não é 1:1 com consultas perdidas)")
    print()

    print("=" * 78)
    print("CONTEXTO (200 chars) DE CADA 'CONSULTA' NÃO CASADA PELA ÂNCORA ATUAL")
    print("=" * 78)
    for i, m in enumerate(perdidas, 1):
        ini = max(0, m.start() - 40)
        fim = min(len(txt), m.start() + 200)
        trecho = txt[ini:fim].replace('\n', ' \\n ')
        print(f"\n[{i}] pos={m.start()}")
        print(f"    ...{trecho}...")


if __name__ == "__main__":
    main()
