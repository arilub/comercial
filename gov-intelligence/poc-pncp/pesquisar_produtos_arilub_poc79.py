#!/usr/bin/env python3
"""GOV POC-79: pesquisa orientada a produtos ARILUB, sem inferir aderencia.

Amostra de pregoes historicos com objetos ligados a lubrificantes, graxas,
filtros e pneus. Confirma termos na descricao dos itens PNCP e consulta
resultados oficiais quando disponiveis.

Leitura SQLite; escreve apenas JSON diagnostico. Nao altera agendamentos,
painel, base operacional ou backups.
"""
import argparse
import json
import re
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

from pesquisar_resultados_historicos_poc76 import fetch, parsed_id, unpack_items, unpack_results, API

TERMOS = (
    "lubrificant", "oleo", "graxa", "fluido hidraulico",
    "fluido de freio", "filtro", "pneu", "aditivo", "arrefecimento"
)

def normalizar(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "").casefold())
                   if unicodedata.category(c) != "Mn")

def matches(s):
    t = normalizar(s)
    return [k for k in TERMOS if k in t]

def selecionar(dbpath):
    with sqlite3.connect("file:" + dbpath.resolve().as_posix() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("SQLite inconsistente")
        rows = db.execute("SELECT id,payload_json FROM contratacoes").fetchall()
    out = []
    for pid, raw in rows:
        parts = parsed_id(pid)
        if not parts:
            continue
        try:
            obj = json.loads(raw)
        except (TypeError, ValueError):
            continue
        ano, seq = parts[1], parts[2]
        if str(obj.get("anoCompra") or ano) != ano:
            continue
        if str(obj.get("sequencialCompra") or seq).lstrip("0") != str(int(seq)):
            continue
        termo = matches(obj.get("objetoCompra"))
        if not termo:
            continue
        encerramento = str(obj.get("dataEncerramentoProposta") or "")
        if not encerramento or encerramento[:10] >= datetime.now().date().isoformat():
            continue
        sit = normalizar(obj.get("situacaoCompraNome"))
        score = (10 if obj.get("valorTotalHomologado") else 0)
        score += 4 if any(w in sit for w in ("homolog", "conclu", "encerr")) else 0
        score += min(3,len(termo))
        out.append((score, pid, obj, parts, termo))
    return sorted(out, key=lambda x: (-x[0], x[1]))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    p.add_argument("--consultas",type=int,default=6)
    p.add_argument("--itens",type=int,default=4)
    a = p.parse_args()
    if not (1<=a.consultas<=10 and 1<=a.itens<=8):
        p.error("Limites: ate 10 processos e 8 itens por processo")
    base=Path(a.base)
    dbpath=base/"dados"/"gov_intelligence_ce_poc.sqlite3"
    if not dbpath.exists():raise FileNotFoundError(str(dbpath))
    cand=selecionar(dbpath)
    print("=== GOV POC-79 - PRODUTOS ARILUB ===",flush=True)
    print("PREGOES HISTORICOS COM TERMOS NO OBJETO:",len(cand),flush=True)
    report={"schema":"gov-poc79-amostra-produtos","geradoEmUTC":datetime.now(timezone.utc).isoformat(),
            "termos":list(TERMOS),"regra":"Coincidencia de texto nao comprova equivalencia tecnica nem aderencia comercial",
            "candidatosNoObjeto":len(cand),"processos":[]}
    encontrados=0
    for _,pid,obj,(cnpj,ano,seq),termo in cand[:a.consultas]:
        u=f"{API}/{cnpj}/compras/{ano}/{int(seq)}/itens?pagina=1&tamanhoPagina=50"
        r={"id":pid,"orgao":(obj.get("orgaoEntidade") or {}).get("razaoSocial"),
           "municipio":(obj.get("unidadeOrgao") or {}).get("municipioNome"),
           "situacao":obj.get("situacaoCompraNome"),"palavrasObjeto":termo,
           "objeto":obj.get("objetoCompra"),"urlItens":u,
           "itensCorrespondentes":[]}
        report["processos"].append(r)
        try:
            status, doc=fetch(u)
        except (URLError,TimeoutError,ValueError) as exc:
            r["erro"]=type(exc).__name__ + ": " + str(exc)[:160]
            print("FALHA NA CONSULTA:",pid,r["erro"],flush=True)
            continue
        r["httpItens"]=status
        if status != 200:
            print("ITENS HTTP",status,"|",pid,flush=True)
            if status==429:break
            time.sleep(2)
            continue
        items=unpack_items(doc)
        r["itensPagina1"]=len(items)
        selecionados=[item for item in items if isinstance(item,dict)
                      and matches(item.get("descricao"))]
        r["totalItensCorrespondentesPagina1"]=len(selecionados)
        print("PROCESSO:",pid,"| correspondentes na pagina 1:",len(selecionados),flush=True)
        for item in selecionados[:a.itens]:
            n=item.get("numeroItem")
            if not isinstance(n,int) or n<1:continue
            registro={"numeroItem":n,"descricao":item.get("descricao"),
                      "palavrasDescricao":matches(item.get("descricao")),
                      "quantidade":item.get("quantidade"),"unidadeMedida":item.get("unidadeMedida"),
                      "valorUnitarioEstimado":item.get("valorUnitarioEstimado"),
                      "temResultado":item.get("temResultado"),"resultados":[]}
            r["itensCorrespondentes"].append(registro)
            if item.get("temResultado") is False:
                print(" ITEM",n,"| sem resultado indicado",flush=True)
                continue
            time.sleep(3)
            resurl=f"{API}/{cnpj}/compras/{ano}/{int(seq)}/itens/{n}/resultados"
            registro["urlResultados"]=resurl
            try:
                codigo, val=fetch(resurl)
            except (URLError,TimeoutError,ValueError) as exc:
                registro["erro"]=type(exc).__name__ + ": " + str(exc)[:160]
                print(" ITEM",n,"| erro de rede",flush=True)
                continue
            registro["httpResultados"]=codigo
            resultados=unpack_results(val)
            registro["resultados"]=resultados[:10]
            registro["amostraResultadosTruncada"]=len(resultados)>10
            print(" ITEM",n,"| HTTP",codigo,"| resultados",len(resultados),flush=True)
            if codigo==200 and resultados:encontrados+=1
            if codigo==429:break
        time.sleep(2)
    report["itensComResultado"]=encontrados
    saida=base/"dados"/"poc79_pesquisa_produtos_arilub.json"
    tmp=saida.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    tmp.replace(saida)
    print("PROCESSOS CONSULTADOS:",len(report["processos"]),flush=True)
    print("ITENS DE PRODUTO COM RESULTADOS:",encontrados,flush=True)
    print("ARQUIVO:",saida,flush=True)
    print("SQLITE SOMENTE LEITURA | NENHUMA MODIFICACAO NO PAINEL OU AGENDAMENTOS",flush=True)
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except (OSError,ValueError,RuntimeError,sqlite3.Error) as exc:
        print("PARADA SEGURA:",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(1)
