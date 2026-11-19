#!/usr/bin/env python3
"""Consulta exploratória, somente leitura, à API de Dados Abertos do Compras.gov.br.

Não cruza PNCP e Compras automaticamente: chaves e cobertura precisam ser homologadas.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from pncp_radar import fetch_json

BASE = "https://dadosabertos.compras.gov.br/modulo-contratacoes/"
ENDPOINTS = {
    "contratacoes": "1_consultarContratacoes_PNCP_14133",
    "itens": "2_consultarItensContratacoes_PNCP_14133",
    "resultados": "3_consultarResultadoItensContratacoes_PNCP_14133",
}

def build_url(tipo, pagina=1, tamanho=10):
    if tipo not in ENDPOINTS:
        raise ValueError("Tipo de consulta não suportado.")
    if pagina < 1 or not 1 <= tamanho <= 100:
        raise ValueError("Paginação fora dos limites da POC.")
    return BASE + ENDPOINTS[tipo] + "?" + urlencode({
        "pagina": pagina, "tamanhoPagina": tamanho
    })

def main():
    ap = argparse.ArgumentParser(description="Diagnóstico de API Compras.gov.br")
    ap.add_argument("--tipo", choices=list(ENDPOINTS), default="contratacoes")
    ap.add_argument("--pagina", type=int, default=1)
    ap.add_argument("--tamanho", type=int, default=10)
    ap.add_argument("--saida", default="saida/compras_diagnostico.json")
    args = ap.parse_args()
    url = build_url(args.tipo, args.pagina, args.tamanho)
    try:
        response = fetch_json(url)
    except Exception as exc:
        print("FALHA consulta Compras.gov.br: " + str(exc), file=sys.stderr)
        return 1
    doc = {"fonte": "Compras.gov.br Dados Abertos", "endpoint": url,
           "consultadoEmUTC": datetime.now(timezone.utc).isoformat(),
           "estado": "resposta_recebida_sem_homologacao_do_schema",
           "dados": response}
    file = Path(args.saida)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK — resposta armazenada: {file}; validar esquema/cobertura manualmente.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
