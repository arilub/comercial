#!/usr/bin/env python3
"""Diagnóstico do Compras.gov.br — dados públicos, sem cruzamento implícito com PNCP.

Consulta de contratações exige dataPublicacaoPncpInicial, dataPublicacaoPncpFinal
e codigoModalidade. Código de pregão no Compras Dados Abertos = 5 (PNCP = 6).
"""
import argparse
import json
import sys
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from pncp_radar import fetch_json

BASE = "https://dadosabertos.compras.gov.br/modulo-contratacoes/"
ENDPOINTS = {
    "contratacoes": "1_consultarContratacoes_PNCP_14133",
    "itens": "2_consultarItensContratacoes_PNCP_14133",
    "resultados": "3_consultarResultadoItensContratacoes_PNCP_14133",
}
MODALIDADE_PREGAO_COMPRAS = 5

def build_url(tipo, pagina=1, tamanho=10, inicio=None, fim=None, modalidade=5, uf=None):
    if tipo not in ENDPOINTS:
        raise ValueError("Tipo de consulta não suportado.")
    if pagina < 1 or not 1 <= tamanho <= 100:
        raise ValueError("Paginação fora dos limites da POC.")
    params = {"pagina": pagina, "tamanhoPagina": tamanho}
    if tipo == "contratacoes":
        if inicio is None or fim is None:
            raise ValueError("Datas são obrigatórias para consulta de contratações.")
        if fim < inicio:
            raise ValueError("Data final anterior à inicial.")
        params.update({
            "dataPublicacaoPncpInicial": inicio.isoformat(),
            "dataPublicacaoPncpFinal": fim.isoformat(),
            "codigoModalidade": modalidade,
        })
        if uf:
            params["unidadeOrgaoUfSigla"] = uf.upper()
    return BASE + ENDPOINTS[tipo] + "?" + urlencode(params)

def main():
    ap = argparse.ArgumentParser(description="Diagnóstico da API Compras.gov.br")
    ap.add_argument("--tipo", choices=list(ENDPOINTS), default="contratacoes")
    ap.add_argument("--pagina", type=int, default=1)
    ap.add_argument("--tamanho", type=int, default=10)
    ap.add_argument("--inicio", type=date.fromisoformat, default=date.today()-timedelta(days=1))
    ap.add_argument("--fim", type=date.fromisoformat, default=date.today())
    ap.add_argument("--modalidade", type=int, default=MODALIDADE_PREGAO_COMPRAS)
    ap.add_argument("--uf", default="CE")
    ap.add_argument("--saida", default="saida/compras_diagnostico.json")
    args = ap.parse_args()
    try:
        url = build_url(args.tipo, args.pagina, args.tamanho, args.inicio,
                        args.fim, args.modalidade, args.uf)
        response = fetch_json(url)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print("FALHA consulta Compras.gov.br: " + str(exc), file=sys.stderr)
        return 1
    doc = {
        "fonte": "Compras.gov.br Dados Abertos",
        "endpoint": url,
        "consultadoEmUTC": datetime.now(timezone.utc).isoformat(),
        "estado": "resposta_recebida_sem_homologacao_do_schema",
        "filtros": {
            "tipo": args.tipo, "inicio": str(args.inicio), "fim": str(args.fim),
            "modalidade_compras": args.modalidade if args.tipo == "contratacoes" else None,
            "uf": args.uf if args.tipo == "contratacoes" else None
        },
        "dados": response
    }
    file = Path(args.saida)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK — resposta salva em " + str(file) + "; schema e vínculo com PNCP ainda pendentes.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
