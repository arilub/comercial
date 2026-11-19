#!/usr/bin/env python3
"""POC de leitura de pregões publicados no PNCP. Somente dados públicos."""
import argparse
import csv
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
MODALIDADE_PREGAO = 6
FIELDS = [
    "id", "numeroControlePNCP", "objetoCompra", "orgao", "uf",
    "municipio", "modalidade", "situacao", "valorEstimado",
    "publicacao", "aberturaPropostas", "encerramentoPropostas",
    "linkSistemaOrigem", "fonteConsultadaEm", "fonteURL"
]

def pick(record):
    orgao = record.get("orgaoEntidade") or {}
    unidade = record.get("unidadeOrgao") or {}
    return {
        "id": record.get("numeroControlePNCP") or (
            str(orgao.get("cnpj", "")) + "-" +
            str(record.get("anoCompra", "")) + "-" +
            str(record.get("sequencialCompra", ""))
        ),
        "numeroControlePNCP": record.get("numeroControlePNCP"),
        "objetoCompra": record.get("objetoCompra", ""),
        "orgao": orgao.get("razaoSocial") or orgao.get("nome") or "",
        "uf": unidade.get("ufSigla") or unidade.get("uf") or "",
        "municipio": unidade.get("municipioNome") or unidade.get("nomeMunicipio") or "",
        "modalidade": record.get("modalidadeNome", ""),
        "situacao": record.get("situacaoCompraNome", ""),
        "valorEstimado": record.get("valorTotalEstimado"),
        "publicacao": record.get("dataPublicacaoPncp"),
        "aberturaPropostas": record.get("dataAberturaProposta"),
        "encerramentoPropostas": record.get("dataEncerramentoProposta"),
        "linkSistemaOrigem": record.get("linkSistemaOrigem", ""),
    }

def fetch_json(url, retries=3, pause=1.0):
    for attempt in range(retries):
        try:
            request = Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "GOVIntelligence-POC/0.1 (consulta-publica)"
            })
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise
        except (URLError, TimeoutError):
            if attempt == retries - 1:
                raise
        time.sleep(pause * (attempt + 1))
    raise RuntimeError("Sem resposta da API.")

def build_url(start, end, page=1, page_size=10, uf=None):
    params = {
        "dataInicial": start.strftime("%Y%m%d"),
        "dataFinal": end.strftime("%Y%m%d"),
        "codigoModalidadeContratacao": MODALIDADE_PREGAO,
        "pagina": page,
        "tamanhoPagina": page_size
    }
    if uf:
        params["uf"] = uf.upper()
    return BASE + "?" + urlencode(params)

def scan(start, end, uf=None, keywords=(), max_pages=2, page_size=10, getter=fetch_json):
    now = datetime.now(timezone.utc).isoformat()
    seen = set()
    results = []
    logs = []
    for page in range(1, max_pages + 1):
        url = build_url(start, end, page, page_size, uf)
        payload = getter(url)
        raw = payload.get("data", []) if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            raise ValueError("Formato inesperado da API; nenhuma saída foi gerada.")
        logs.append({"url": url, "recebidos": len(raw)})
        for item in raw:
            if not isinstance(item, dict):
                continue
            rec = pick(item)
            if uf and rec["uf"].upper() != uf.upper():
                continue
            text = (rec["objetoCompra"] + " " + rec["orgao"]).casefold()
            if keywords and not any(k.casefold() in text for k in keywords):
                continue
            if not rec["id"] or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            rec["fonteConsultadaEm"] = now
            rec["fonteURL"] = url
            results.append(rec)
        if len(raw) < page_size:
            break
        if isinstance(payload, dict) and payload.get("totalPaginas"):
            if page >= int(payload["totalPaginas"]):
                break
        time.sleep(0.35)
    return results, logs

def main():
    parser = argparse.ArgumentParser(description="Radar inicial PNCP - pregões publicados")
    parser.add_argument("--inicio", type=date.fromisoformat, default=date.today()-timedelta(days=1))
    parser.add_argument("--fim", type=date.fromisoformat, default=date.today())
    parser.add_argument("--uf", default="CE", help="UF ou vazio para Brasil")
    parser.add_argument("--palavras", default="", help="Palavras separadas por vírgula")
    parser.add_argument("--paginas", type=int, default=2)
    parser.add_argument("--itens-por-pagina", type=int, default=10)
    parser.add_argument("--saida", default="saida/pncp_pregoes.json")
    args = parser.parse_args()
    if args.fim < args.inicio or (args.fim - args.inicio).days > 7:
        parser.error("Intervalo deve ter entre 1 e 8 datas consecutivas.")
    if not 1 <= args.paginas <= 10 or not 10 <= args.itens_por_pagina <= 100:
        parser.error("Limites POC: paginas 1–10; itens-por-pagina 10–100.")
    words = [k.strip() for k in args.palavras.split(",") if k.strip()]
    try:
        rows, logs = scan(args.inicio, args.fim, uf=args.uf or None, keywords=words,
                          max_pages=args.paginas, page_size=args.itens_por_pagina)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print("ERRO: consulta não validada: " + str(exc), file=sys.stderr)
        return 1
    out = Path(args.saida)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "status": "consultado", "fonte": "PNCP API Consulta",
        "modo": "dados publicos", "aviso": "POC: não significa cobertura exaustiva.",
        "filtros": {"inicio": str(args.inicio), "fim": str(args.fim), "uf": args.uf,
                    "palavras": words, "paginas": args.paginas},
        "consultas": logs, "quantidade": len(rows), "oportunidades": rows
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_out = out.with_suffix(".csv")
    with csv_out.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"OK: {len(rows)} registros filtrados; {len(logs)} consultas; {out}; {csv_out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
