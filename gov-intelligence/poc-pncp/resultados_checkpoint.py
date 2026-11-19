#!/usr/bin/env python3
"""POC-05: resultado PNCP com checkpoint por página/item, execução MANUAL.

Não consulta sistemas internos; não programa tarefas; dados só no arquivo local.
HTTP 429 interrompe imediatamente, preservando progresso e Retry-After.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from coletar_itens_neutros import parse_id

BASE = "https://pncp.gov.br/api/pncp/v1/orgaos"

def timestamp():
    return datetime.now(timezone.utc).isoformat()

def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)

def get_json(uri):
    req = Request(uri, headers={"Accept":"application/json", "User-Agent":"GOV-Intelligence-POC/0.5"})
    with urlopen(req, timeout=25) as res:
        return json.loads(res.read().decode("utf-8-sig"))

def result_rows(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "resultado", "resultados"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError("Estrutura inesperada no endpoint de resultados")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--saida", required=True)
    parser.add_argument("--max-requisicoes", type=int, default=3)
    parser.add_argument("--intervalo", type=float, default=4)
    args = parser.parse_args()
    if not 1 <= args.max_requisicoes <= 8 or args.intervalo < 4:
        parser.error("max-requisicoes: 1..8; intervalo: pelo menos 4 segundos")
    try:
        cnpj, ano, seq = parse_id(args.id)
    except ValueError as err:
        parser.error(str(err))
    root = f"{BASE}/{cnpj}/compras/{ano}/{seq}"
    dest = Path(args.saida)
    if dest.exists():
        state = json.loads(dest.read_text(encoding="utf-8-sig"))
        if state.get("numeroControlePNCP") != args.id or state.get("versao") != 1:
            parser.error("Checkpoint incompatível, não sobrescrever")
    else:
        state = {"versao":1, "numeroControlePNCP":args.id, "fonte":"PNCP",
                 "status":"ITENS_PARCIAL", "proximaPaginaItens":1, "itensCompletos":False,
                 "itens":[], "resultadosPorItem":{}, "erros":[],
                 "atualizadoEmUTC":timestamp()}
    if state.get("status") == "COMPLETO":
        print("COMPLETO: checkpoint já finalizado, nenhuma consulta.")
        return 0
    requests = 0
    while requests < args.max_requisicoes:
        if requests:
            time.sleep(args.intervalo)
        if not state["itensCompletos"]:
            pagina = state["proximaPaginaItens"]
            uri = root + "/itens?" + urlencode({"pagina":pagina, "tamanhoPagina":50})
            step = f"itens pagina {pagina}"
        else:
            pendentes = [i for i in state["itens"]
                        if str(i["numeroItem"]) not in state["resultadosPorItem"]]
            if not pendentes:
                state["status"] = "COMPLETO"
                atomic_write(dest, state)
                break
            item = pendentes[0]
            n = item["numeroItem"]
            uri = root + f"/itens/{n}/resultados"
            step = f"resultado item {n}"
        try:
            data = get_json(uri)
            requests += 1
            if not state["itensCompletos"]:
                if not isinstance(data, list):
                    raise ValueError("Endpoint de itens não retornou lista")
                existing = {str(r["numeroItem"]) for r in state["itens"]}
                for row in data:
                    if not isinstance(row, dict) or row.get("numeroItem") is None:
                        raise ValueError("Item inválido")
                    key = str(row["numeroItem"])
                    if key in existing:
                        raise ValueError("Item repetido entre páginas; coleta interrompida")
                    existing.add(key)
                for row in data:
                    state["itens"].append({
                        "numeroItem":row["numeroItem"], "descricao":row.get("descricao"),
                        "valorUnitarioEstimado":row.get("valorUnitarioEstimado"),
                        "quantidade":row.get("quantidade"), "valorTotal":row.get("valorTotal"),
                        "catalogoCodigoItem":row.get("catalogoCodigoItem"),
                        "temResultado":row.get("temResultado"),
                        "aderencia":"NEUTRO"
                    })
                state["proximaPaginaItens"] += 1
                state["itensCompletos"] = len(data) < 50
                state["status"] = "RESULTADOS_PARCIAL" if state["itensCompletos"] else "ITENS_PARCIAL"
                print(f"ITENS pagina {pagina}: +{len(data)} | total {len(state['itens'])}")
            else:
                rows = result_rows(data)
                state["resultadosPorItem"][str(n)] = {
                    "status":"CONSULTADO", "resultados":rows,
                    "fonteURL":uri, "consultadoEmUTC":timestamp()
                }
                print(f"RESULTADO item {n}: {len(rows)} registro(s)")
            state["atualizadoEmUTC"] = timestamp()
            atomic_write(dest, state)
        except HTTPError as exc:
            if exc.code == 404 and state["itensCompletos"]:
                state["resultadosPorItem"][str(n)] = {
                    "status":"HTTP_404_NAO_DISPONIVEL", "resultados":[],
                    "fonteURL":uri, "consultadoEmUTC":timestamp()
                }
                state["atualizadoEmUTC"] = timestamp()
                atomic_write(dest, state)
                requests += 1
                print(f"RESULTADO item {n}: HTTP 404; sem registro disponível")
                continue
            msg = f"{step}: HTTP {exc.code}"
            if exc.code == 429:
                msg += f" | Retry-After: {exc.headers.get('Retry-After', 'não informado')}"
            state["erros"].append({"em":timestamp(), "mensagem":msg})
            atomic_write(dest, state)
            print("PARADA SEGURA:", msg, file=sys.stderr)
            return 1
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            msg = f"{step}: {type(exc).__name__}: {exc}"
            state["erros"].append({"em":timestamp(), "mensagem":msg})
            atomic_write(dest, state)
            print("PARADA SEGURA:", msg, file=sys.stderr)
            return 1
    if state["itensCompletos"] and len(state["resultadosPorItem"]) == len(state["itens"]):
        state["status"] = "COMPLETO"
        state["atualizadoEmUTC"] = timestamp()
        atomic_write(dest, state)
    print("STATUS:",state["status"],"| ITENS:",len(state["itens"]),
          "| RESULTADOS CONSULTADOS:",len(state["resultadosPorItem"]),
          "| REQUISICOES NESTA EXECUCAO:",requests)
    print("CHECKPOINT:",dest)
    return 0

if __name__ == "__main__":
    sys.exit(main())
