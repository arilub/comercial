#!/usr/bin/env python3
"""POC-03: resultados por item de contratação PNCP. Somente leitura pública."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from pncp_radar import fetch_json
from coletar_itens_neutros import parse_id, extract_items

BASE = "https://pncp.gov.br/api/pncp/v1/orgaos"

def endpoint(identifier, suffix):
    cnpj, year, seq = parse_id(identifier)
    return f"{BASE}/{cnpj}/compras/{year}/{seq}/{suffix}"

def get_optional(url):
    try:
        return fetch_json(url, retries=2)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise

def normalize_results(payload):
    if payload is None:
        return [], "NAO_ENCONTRADO"
    if isinstance(payload, list):
        return payload, "CONSULTADO"
    if isinstance(payload, dict):
        for key in ("data", "resultados", "resultado"):
            if isinstance(payload.get(key), list):
                return payload[key], "CONSULTADO"
    raise ValueError("Formato inesperado dos resultados")

def consultar(identifier, limite=5, getter=get_optional):
    url = endpoint(identifier, "itens") + "?" + urlencode(
        {"pagina": 1, "tamanhoPagina": 50})
    itens_raw = getter(url)
    if itens_raw is None:
        raise ValueError("Itens não encontrados na API para o processo")
    itens, total_paginas = extract_items(itens_raw)
    linhas = []
    for item in itens[:limite]:
        n = item.get("numeroItem")
        if n is None:
            raise ValueError("Item sem numeroItem")
        resultado_url = endpoint(identifier, f"itens/{n}/resultados")
        try:
            resultados, estado = normalize_results(getter(resultado_url))
            erro = None
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            resultados, estado, erro = [], "ERRO", str(exc)
        linhas.append({
            "numeroControlePNCP": identifier, "numeroItem": n,
            "descricao": item.get("descricao"),
            "valorUnitarioEstimado": item.get("valorUnitarioEstimado"),
            "temResultado": item.get("temResultado"),
            "aderencia": "NEUTRO",
            "resultadoStatus": estado,
            "resultados": resultados,
            "erro": erro,
            "fonteURL": resultado_url
        })
    return {
        "fonte": "PNCP API", "consultadoEmUTC": datetime.now(timezone.utc).isoformat(),
        "numeroControlePNCP": identifier, "paginacaoItens": "AMOSTRA_PRIMEIRA_PAGINA",
        "totalPaginasItens": total_paginas, "itensDisponiveisNaPagina": len(itens),
        "quantidadeItensConsultados": len(linhas), "itens": linhas
    }

def main():
    ap = argparse.ArgumentParser(description="POC-03 PNCP - resultados históricos")
    ap.add_argument("--id", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--limite-itens", type=int, default=5)
    args = ap.parse_args()
    if not 1 <= args.limite_itens <= 20:
        ap.error("limite-itens deve estar entre 1 e 20")
    try:
        doc = consultar(args.id, args.limite_itens)
        output = Path(args.saida)
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp = output.with_suffix(output.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(output)
        print("ID:", args.id, "| ITENS:", doc["quantidadeItensConsultados"])
        print("RESULTADOS:", sum(len(i["resultados"]) for i in doc["itens"]))
        print("ERROS:", sum(i["resultadoStatus"] == "ERRO" for i in doc["itens"]))
        for i in doc["itens"]:
            print("ITEM", i["numeroItem"], "| TEM_RESULTADO", i["temResultado"],
                  "| CONSULTA", i["resultadoStatus"], "| RESULTADOS", len(i["resultados"]))
        print("ARQUIVO:", output)
        return int(any(i["resultadoStatus"] == "ERRO" for i in doc["itens"]))
    except (ValueError, HTTPError, URLError, TimeoutError) as exc:
        print("FALHA:", exc, file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
