#!/usr/bin/env python3
"""POC-02: coleta paginada de itens PNCP, sem inferir aderência comercial.

Leitura pública; entrada PNCP (JSON da POC-01); saída local com status NEUTRO.
Nenhum dado interno de catálogo, CRM ou Shop9 é consultado.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from pncp_radar import fetch_json

ID_RE = re.compile(r"^(\d{14})-(\d+)-(\d+)/(\d{4})$")
API = "https://pncp.gov.br/api/pncp/v1/orgaos"

def parse_id(value):
    m = ID_RE.fullmatch(str(value or ""))
    if not m:
        raise ValueError("numeroControlePNCP inválido: " + str(value))
    cnpj, _modalidade_ordenador, seq, ano = m.groups()
    return cnpj, int(ano), int(seq)

def url_itens(id_pncp, page, size):
    cnpj, ano, seq = parse_id(id_pncp)
    return f"{API}/{cnpj}/compras/{ano}/{seq}/itens?" + urlencode(
        {"pagina": page, "tamanhoPagina": size})

def extract_items(payload):
    if isinstance(payload, list):
        return payload, None
    if isinstance(payload, dict):
        items = payload.get("data", payload.get("itens", payload.get("resultado")))
        if isinstance(items, list):
            total = payload.get("totalPaginas")
            return items, int(total) if total is not None else None
    raise ValueError("Formato de resposta de itens desconhecido")

def collect_one(id_pncp, max_pages=5, page_size=50, getter=fetch_json, pause=0.25):
    all_items, seen, requests = [], set(), []
    for page in range(1, max_pages + 1):
        uri = url_itens(id_pncp, page, page_size)
        response = getter(uri)
        chunk, total_pages = extract_items(response)
        requests.append({"pagina": page, "recebidos": len(chunk), "url": uri})
        for item in chunk:
            if not isinstance(item, dict) or item.get("numeroItem") is None:
                raise ValueError("Item sem numeroItem / formato inválido")
            key = str(item["numeroItem"])
            if key not in seen:
                seen.add(key)
                all_items.append({
                    "numeroControlePNCP": id_pncp,
                    "numeroItem": item["numeroItem"],
                    "descricao": item.get("descricao"),
                    "quantidade": item.get("quantidade"),
                    "unidadeMedida": item.get("unidadeMedida"),
                    "valorUnitarioEstimado": item.get("valorUnitarioEstimado"),
                    "valorTotal": item.get("valorTotal"),
                    "catalogoCodigoItem": item.get("catalogoCodigoItem"),
                    "situacaoCompraItemNome": item.get("situacaoCompraItemNome"),
                    "temResultado": item.get("temResultado"),
                    "aderencia": "NEUTRO",
                    "classificacaoStatus": "AGUARDANDO_VALIDACAO_GESTAO",
                    "classificacaoOrigem": "REGRA_PADRAO",
                    "fonte": "PNCP_API_OFICIAL",
                    "fonteURL": uri,
                })
        if not chunk:
            return all_items, requests, "COMPLETA_POR_PAGINA_VAZIA"
        if total_pages is not None and page >= total_pages:
            return all_items, requests, "COMPLETA_POR_TOTAL_PAGINAS"
        if len(chunk) < page_size:
            return all_items, requests, "COMPLETA_POR_PAGINA_CURTA"
        if page < max_pages:
            time.sleep(pause)
    return all_items, requests, "PARCIAL_LIMITE_PAGINAS"

def main():
    ap = argparse.ArgumentParser(description="POC-02 — itens PNCP neutros")
    ap.add_argument("--entrada", required=True, help="JSON da POC-01 no servidor")
    ap.add_argument("--saida", required=True, help="JSON de saída local")
    ap.add_argument("--limite-pregoes", type=int, default=1)
    ap.add_argument("--max-paginas", type=int, default=5)
    ap.add_argument("--tamanho-pagina", type=int, default=50)
    args = ap.parse_args()
    if not 1 <= args.limite_pregoes <= 20:
        ap.error("limite-pregoes deve ser de 1 a 20")
    if not 1 <= args.max_paginas <= 20 or not 10 <= args.tamanho_pagina <= 100:
        ap.error("max-paginas 1–20 e tamanho-pagina 10–100")

    entrada = Path(args.entrada)
    saida = Path(args.saida)
    if entrada.resolve() == saida.resolve():
        ap.error("O arquivo de saída não pode substituir a entrada")
    try:
        base = json.loads(entrada.read_text(encoding="utf-8-sig"))
        preg = base.get("oportunidades")
        if not isinstance(preg, list) or not preg:
            raise ValueError("Entrada sem oportunidades no formato esperado")
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print("ERRO de entrada: " + str(e), file=sys.stderr)
        return 1

    selecionados = []
    ids = set()
    for p in preg:
        identifier = p.get("numeroControlePNCP") if isinstance(p, dict) else None
        if identifier and identifier not in ids:
            parse_id(identifier)
            ids.add(identifier)
            selecionados.append(identifier)
        if len(selecionados) >= args.limite_pregoes:
            break

    itens, auditoria = [], []
    now = datetime.now(timezone.utc).isoformat()
    for identifier in selecionados:
        try:
            results, requests, state = collect_one(
                identifier, args.max_paginas, args.tamanho_pagina)
            itens.extend(results)
            auditoria.append({"numeroControlePNCP": identifier,
                             "status": state, "quantidadeItens": len(results),
                             "consultas": requests})
            print(f"PNCP {identifier}: {len(results)} itens; {state}")
        except Exception as e:
            auditoria.append({"numeroControlePNCP": identifier,
                             "status": "FALHA", "erro": str(e)})
            print(f"FALHA PNCP {identifier}: {e}", file=sys.stderr)
        time.sleep(0.3)

    doc = {
        "fonte": "PNCP", "consultadoEmUTC": now,
        "regra": "Itens retornados pela API oficial; aderencia sempre NEUTRO",
        "aviso": "Amostra limitada: não representa cobertura total de pregões.",
        "pregoesSolicitados": len(selecionados),
        "pregoesCompletos": sum(a["status"].startswith("COMPLETA") for a in auditoria),
        "pregoesComFalha": sum(a["status"] == "FALHA" for a in auditoria),
        "pregoesParciais": sum(a["status"].startswith("PARCIAL") for a in auditoria),
        "quantidadeItens": len(itens),
        "auditoria": auditoria,
        "itens": itens,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    tmp = saida.with_suffix(saida.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(saida)
    print("RESULTADO: " + str(saida))
    print("ITENS: " + str(len(itens)) + " | COMPLETOS: " + str(doc["pregoesCompletos"])
          + " | PARCIAIS: " + str(doc["pregoesParciais"])
          + " | FALHAS: " + str(doc["pregoesComFalha"]))
    return 1 if doc["pregoesComFalha"] else 0

if __name__ == "__main__":
    sys.exit(main())
