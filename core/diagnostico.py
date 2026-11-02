# core/diagnostico.py
"""Diagnóstico de um Lote ANTES de gravar no banco.

Mesmo formato de mensagem do hub: código, título, nível ('erro' | 'aviso'),
texto e os arquivos envolvidos. Arquivo ilegível é 'erro' mas não bloqueia os
demais; o que bloqueia a gravação é não haver nenhum registro."""
import re
from collections import defaultdict

_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')
_PESOS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_2 = [6] + _PESOS_1
_MAX_ITENS_NO_TEXTO = 5

_CATALOGO = {
    'A001': 'Tipo de arquivo não identificado',
    'A201': 'Consulta sem resposta',
    'A202': 'Consulta sem súmula',
    'A203': 'Data da consulta fora do padrão AAAA-MM-DD',
    'A301': 'Regime sem CNPJ do requerente',
    'A302': 'CNPJ do requerente inválido',
    'A303': 'Regime sem vigência',
    'A304': 'Data do regime fora do padrão AAAA-MM-DD',
    'A401': 'Nenhum registro extraído',
}


def cnpj_valido(cnpj) -> bool:
    """Confere os dois dígitos verificadores (aceita com ou sem pontuação)."""
    digitos = re.sub(r'\D', '', str(cnpj or ''))
    if len(digitos) != 14 or digitos == digitos[0] * 14:
        return False

    def digito(base: str, pesos: list) -> str:
        resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        return '0' if resto < 2 else str(11 - resto)

    return (digitos[12] == digito(digitos[:12], _PESOS_1)
            and digitos[13] == digito(digitos[:13], _PESOS_2))


def _mensagem(codigo, titulo, nivel, texto, arquivos) -> dict:
    return {'codigo': codigo, 'titulo': titulo, 'nivel': nivel, 'texto': texto,
            'arquivos': sorted(set(a for a in arquivos if a))}


def diagnosticar(lote) -> dict:
    mensagens = []
    achados = defaultdict(list)  # código -> [(referência, arquivo)]

    for linha in lote.arquivos:
        if linha.get('Tipo') == 'erro':
            mensagens.append(_mensagem(
                'E001', 'Arquivo ilegível', 'erro',
                f"{linha['Arquivo']}: {linha.get('Erro', '')}", [linha['Arquivo']]))
        elif linha.get('Tipo') == 'desconhecido':
            achados['A001'].append((linha['Arquivo'], linha['Arquivo']))

    for r in lote.consultas:
        ref = f"{r.get('Nº da Consulta', '')}/{r.get('Ano', '')}"
        arq = lote.origem.get(('consulta', r.get('Ano', ''), r.get('Nº da Consulta', '')), '')
        if not str(r.get('Resposta', '') or '').strip():
            achados['A201'].append((ref, arq))
        if not str(r.get('Súmula', '') or '').strip():
            achados['A202'].append((ref, arq))
        if not _ISO.fullmatch(str(r.get('Data da Publicação', '') or '')):
            achados['A203'].append((ref, arq))

    for r in lote.regimes:
        ref = f"RE {r.get('Nº DO REGIME ESPECIAL', '')}"
        arq = lote.origem.get(('regime', r.get('Nº DO REGIME ESPECIAL', ''),
                               r.get('CNPJ REQUERENTE', '')), '')
        cnpj = str(r.get('CNPJ REQUERENTE', '') or '').strip()
        if not cnpj:
            achados['A301'].append((ref, arq))
        elif not cnpj_valido(cnpj):
            achados['A302'].append((ref, arq))
        if not str(r.get('VIGÊNCIA DO RE', '') or '').strip():
            achados['A303'].append((ref, arq))
        if not _ISO.fullmatch(str(r.get('DATA', '') or '')):
            achados['A304'].append((ref, arq))

    tem_registros = bool(lote.consultas or lote.regimes)
    if not tem_registros:
        achados['A401'].append(('lote', ''))

    for codigo in sorted(achados):
        itens = achados[codigo]
        refs = [ref for ref, _ in itens]
        resumo = ', '.join(refs[:_MAX_ITENS_NO_TEXTO])
        if len(refs) > _MAX_ITENS_NO_TEXTO:
            resumo += f' … (+{len(refs) - _MAX_ITENS_NO_TEXTO})'
        texto = (f"{len(itens)} ocorrência(s): {resumo}" if codigo != 'A401'
                 else 'Nenhuma consulta ou regime foi extraído dos arquivos enviados.')
        mensagens.append(_mensagem(codigo, _CATALOGO[codigo], 'aviso', texto,
                                   [arq for _, arq in itens]))

    mensagens.sort(key=lambda m: m['codigo'])
    return {'mensagens': mensagens,
            'erros': sum(1 for m in mensagens if m['nivel'] == 'erro'),
            'avisos': sum(1 for m in mensagens if m['nivel'] == 'aviso'),
            'pode_continuar': tem_registros}
