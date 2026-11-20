#!/usr/bin/env python3
"""POC-45: coleta incremental PNCP por data de atualizacao global, checkpoint e protecao 429.

Executar MANUALMENTE. Não consulta Shop9, não publica dados ou agenda tarefas.
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://pncp.gov.br/api/consulta/v1/contratacoes/atualizacao"

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def atomic_json(file, payload):
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(file.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(file)

def retry_after_seconds(raw):
    if not raw:
        return None
    try:
        return max(0, float(raw))
    except (TypeError, ValueError):
        try:
            return max(0.0, (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None

def fetch(uri, tries=2):
    for attempt in range(tries):
        try:
            req = Request(uri, headers={"Accept": "application/json", "User-Agent": "GOV-Intelligence-POC/0.45"})
            with urlopen(req, timeout=25) as response:
                if response.status == 204:
                    return {"_http204": True}
                return json.loads(response.read().decode("utf-8-sig"))
        except HTTPError as exc:
            if exc.code != 429 or attempt + 1 == tries:
                raise
            wait = retry_after_seconds(exc.headers.get("Retry-After"))
            if wait is None:
                wait = 30 + random.random() * 5
            if wait > 180:
                raise RuntimeError("Retry-After superior a 180s; interrompido para proteção") from exc
            print(f"HTTP 429: aguardando {wait:.1f}s antes de uma única retentativa", flush=True)
            time.sleep(wait)

def main():
    p = argparse.ArgumentParser(description="PNCP CE: atualizacoes por janela, checkpoint, sem automacao")
    p.add_argument("--inicio", default="20261118")
    p.add_argument("--fim", default="20261119")
    p.add_argument("--uf", default="CE")
    p.add_argument("--municipio", default=None, help="codigo IBGE (ex. 2304400)")
    p.add_argument("--saida", required=True)
    p.add_argument("--tamanho-pagina", type=int, default=50, choices=(50,))
    p.add_argument("--max-paginas", type=int, default=8)
    p.add_argument("--intervalo", type=float, default=4.0)
    args = p.parse_args()
    if args.max_paginas < 1 or args.max_paginas > 8 or args.intervalo < 4:
        p.error("max-paginas: 1 a 8; intervalo minimo: 4 segundos")
    if not (len(args.inicio)==8 and args.inicio.isdigit() and len(args.fim)==8 and args.fim.isdigit()):
        p.error("datas exigidas no formato YYYYMMDD")
    try:
        start_date = datetime.strptime(args.inicio, "%Y%m%d").date()
        end_date = datetime.strptime(args.fim, "%Y%m%d").date()
        if end_date < start_date or (end_date - start_date).days > 7:
            p.error("janela incremental deve ter no maximo 8 dias e fim >= inicio")
    except ValueError:
        p.error("datas de calendario invalidas")
    if args.uf.upper() != "CE":
        p.error("POC restrita a UF CE")
    if args.municipio and (not args.municipio.isdigit() or len(args.municipio)!=7):
        p.error("municipio deve ser codigo IBGE de 7 digitos")
    out = Path(args.saida)
    config = dict(inicio=args.inicio, fim=args.fim, uf=args.uf.upper(), tipoConsulta="atualizacao",
                  municipio=args.municipio, modalidade=6, tamanhoPagina=args.tamanho_pagina)
    if out.exists():
        state = json.loads(out.read_text(encoding="utf-8-sig"))
        if state.get("config") != config:
            p.error("Checkpoint existente possui configuracao diferente; use outro nome de arquivo")
        if state.get("status") == "COMPLETO":
            print("Checkpoint ja completo; nenhuma requisicao realizada")
            return 0
    else:
        state = {"versao":1, "fonte":"PNCP API oficial",
                 "config":config, "status":"PARCIAL", "proximaPagina":1,
                 "totalRegistrosInformado":None, "totalPaginasInformado":None,
                 "registros":[], "observacoes":[], "atualizadoEmUTC":utcnow()}
    pages_done = 0
    while pages_done < args.max_paginas:
        pagina = state["proximaPagina"]
        params = {
            "dataInicial":args.inicio, "dataFinal":args.fim,
            "codigoModalidadeContratacao":6, "uf":args.uf.upper(),
            "pagina":pagina, "tamanhoPagina":args.tamanho_pagina,
        }
        if args.municipio:
            params["codigoMunicipioIbge"] = args.municipio
        url = ENDPOINT + "?" + urlencode(params)
        try:
            response = fetch(url)
            if response.get("_http204"):
                if pagina != 1 or state["registros"] or state["totalRegistrosInformado"] not in (None, 0):
                    raise ValueError("HTTP 204 inesperado apos inicio de paginacao; interromper")
                state["totalRegistrosInformado"] = 0
                state["totalPaginasInformado"] = 0
                state["status"] = "COMPLETO"
                state["proximaPagina"] = 2
                state["atualizadoEmUTC"] = utcnow()
                state["observacoes"].append("HTTP 204 No Content na pagina 1: consulta sem registros")
                atomic_json(out, state)
                print("HTTP 204 | 0 registros | COMPLETO", flush=True)
                break
            items = response.get("data")
            if not isinstance(items, list):
                raise ValueError("Resposta sem array data")
            total = int(response["totalRegistros"])
            pages = int(response["totalPaginas"])
            if state["totalRegistrosInformado"] is None:
                state["totalRegistrosInformado"] = total
                state["totalPaginasInformado"] = pages
            elif total != state["totalRegistrosInformado"] or pages != state["totalPaginasInformado"]:
                raise ValueError("Totais da API alterados entre paginas; interromper e revisar consistencia")
            seen = {row.get("numeroControlePNCP") for row in state["registros"]}
            for item in items:
                code = item.get("numeroControlePNCP")
                if not code:
                    raise ValueError("Item sem numeroControlePNCP")
                if code in seen:
                    raise ValueError("Identificador repetido entre paginas; nao avancar checkpoint")
                seen.add(code)
            for item in items:
                if (item.get("unidadeOrgao") or {}).get("ufSigla") != "CE":
                    raise ValueError("Resposta inclui UF diferente de CE; nao avancar")
            state["registros"].extend(items)
            state["proximaPagina"] = pagina + 1
            state["atualizadoEmUTC"] = utcnow()
            state["status"] = "COMPLETO" if pagina >= pages else "PARCIAL"
            atomic_json(out, state)
            pages_done += 1
            print(f"Pagina {pagina}/{pages} | recebidos {len(items)} | acumulados {len(state['registros'])} | {state['status']}", flush=True)
            if state["status"] == "COMPLETO":
                if len(state["registros"]) != total:
                    state["status"] = "INCONSISTENTE"
                    state["observacoes"].append("Contagem final difere do total informado")
                    atomic_json(out, state)
                    return 2
                break
            if pages_done < args.max_paginas:
                time.sleep(args.intervalo)
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            state["observacoes"].append(f"Pagina {pagina}: {type(exc).__name__}: {exc}")
            state["atualizadoEmUTC"] = utcnow()
            atomic_json(out, state)
            print(f"PARADA SEGURA na pagina {pagina}: {exc}", file=sys.stderr)
            return 1
    print("STATUS:", state["status"], "| PROXIMA PAGINA:", state["proximaPagina"],
          "| REGISTROS:", len(state["registros"]), "| ARQUIVO:", out)
    return 0

if __name__ == "__main__":
    sys.exit(main())
