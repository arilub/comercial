#!/usr/bin/env python3
"""GOV POC-59: lote congelado de enriquecimento de itens oficiais PNCP.

Planejamento grava SOMENTE manifesto de lote. Execucao necessita --executar,
reusa o manifesto e coleta checkpoints sem alterar SQLite nem o painel.
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

PAT_ID = re.compile(r"^\d{14}-1-\d{6}/\d{4}$")
GOODS = re.compile(
    r"\b(aquisic(?:ao|oes)|fornecimento|compra|materiais?|produtos?|"
    r"equipamentos?|insumos?|pecas?|pneus?|lubrificantes?|combustiveis?|"
    r"ferramentas?|reles|medicamentos?|mobiliario|veiculos?)\b")
STRONG_SERVICE = re.compile(
    r"\b(prestacao de servicos|servicos? terceirizad|terceirizacao|"
    r"mao de obra|locacao de|licenca de uso|consultoria|"
    r"telefonia movel|servicos? de limpeza|servicos? de vigilancia)\b")

def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value).lower())
                   if not unicodedata.combining(c))

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def atomic(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as out:
        json.dump(obj,out,indent=2,ensure_ascii=False)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp,path)

def cp_path(base, ident):
    return base/"dados"/"itens_poc56"/("pncp_itens_"+ident.replace("/","_")+".json")

def state_checkpoint(path, ident):
    if not path.exists():
        return "AUSENTE",0
    d=read(path)
    if d.get("fonte")!="PNCP-ITENS-v1" or d.get("id")!=ident:
        raise ValueError("Checkpoint incompatível: "+path.name)
    if d.get("status") not in ("COMPLETO","PARCIAL"):
        raise ValueError("Status invalido de checkpoint: "+path.name)
    itens=d.get("itens")
    if not isinstance(itens,list):
        raise ValueError("Itens nao sao lista: "+path.name)
    nums=[i.get("numeroItem") if isinstance(i,dict) else None for i in itens]
    if any(type(n)!=int or n<1 for n in nums) or len(set(nums))!=len(nums):
        raise ValueError("Numeracao invalida ou duplicada em "+path.name)
    return d["status"],len(itens)

def new_manifest(base, snap, limit, batch, dbfile):
    rows=snap.get("candidatos")
    if snap.get("schema") not in ("gov-intelligence-radar-v1-poc52",
                                 "gov-intelligence-radar-v1-poc57") or not isinstance(rows,list):
        raise ValueError("Snapshot de Radar nao reconhecido")
    ordered=sorted(rows,key=lambda d:(str(d.get("encerramentoProposta") or ""),str(d.get("id") or "")))
    possible=[]
    with sqlite3.connect(f"file:{dbfile.resolve().as_posix()}?mode=ro",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("SQLite reprovado")
        for d in ordered:
            ident=d.get("id")
            if not isinstance(ident,str) or not PAT_ID.fullmatch(ident):
                continue
            if d.get("statusRadar")!="CANDIDATO_PRELIMINAR" or d.get("aderenciaComercial")!="NEUTRO":
                continue
            txt=normalized(d.get("objeto") or "")
            if not GOODS.search(txt) or STRONG_SERVICE.search(txt):
                continue
            if db.execute("SELECT uf FROM contratacoes WHERE id=?",(ident,)).fetchone()!=("CE",):
                raise ValueError("ID nao confere com banco CE: "+ident)
            state,n=state_checkpoint(cp_path(base,ident),ident)
            if state=="COMPLETO":
                continue
            possible.append({"id":ident,"objeto":str(d.get("objeto") or "")[:260],
                             "encerramentoProposta":d.get("encerramentoProposta"),
                             "checkpointInicial":state,"itensConhecidos":n})
            if len(possible)==limit:break
    return {"schema":"gov-intelligence-lote-itens-poc59",
            "lote":batch,
            "criadoEmUTC":datetime.now(timezone.utc).isoformat(),
            "snapshotArquivo":"radar_v1_candidatos.json",
            "snapshotSha256":hashlib.sha256((base/"dados"/"radar_v1_candidatos.json").read_bytes()).hexdigest(),
            "limite":limit,"selecionados":possible,
            "instrucao":"Lote congelado; execucao nao seleciona processos novos.",
            "aderenciaComercial":"NEUTRO"}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    p.add_argument("--python",default=sys.executable)
    p.add_argument("--lote",default="lote01",help="ID explicito, ex. lote01")
    p.add_argument("--limite",type=int,default=5)
    p.add_argument("--max-paginas",type=int,default=3)
    p.add_argument("--intervalo",type=float,default=4.0)
    p.add_argument("--executar",action="store_true")
    args=p.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,30}",args.lote):
        p.error("Identificador de lote invalido")
    if not 1<=args.limite<=10 or not 1<=args.max_paginas<=4 or args.intervalo<4:
        p.error("limite 1..10, max-paginas 1..4, intervalo >=4")
    base=Path(args.base)
    radar=base/"dados"/"radar_v1_candidatos.json"
    dbfile=base/"dados"/"gov_intelligence_ce_poc.sqlite3"
    collector=base/"scripts"/"coletar_itens_radar_checkpoint.py"
    manifest=base/"dados"/"itens_poc59"/(args.lote+".json")
    if not all(x.is_file() for x in (radar,dbfile,collector)):
        raise FileNotFoundError("Snapshot, SQLite ou coletor ausente")
    print("=== GOV POC-59 - LOTE ITENS PNCP ===",flush=True)
    print("MODO:","EXECUTAR" if args.executar else "PLANEJAR",flush=True)
    print("LOTE:",args.lote,flush=True)
    if manifest.is_file():
        doc=read(manifest)
        print("MANIFESTO EXISTENTE, SEM NOVA SELECAO",flush=True)
    elif args.executar:
        raise ValueError("Execute primeiro o planejamento para congelar a selecao")
    else:
        doc=new_manifest(base,read(radar),args.limite,args.lote,dbfile)
        atomic(manifest,doc)
        print("MANIFESTO CRIADO:",manifest,flush=True)
    if doc.get("schema")!="gov-intelligence-lote-itens-poc59" or doc.get("lote")!=args.lote:
        raise ValueError("Manifesto incompatível")
    if not isinstance(doc.get("selecionados"),list) or len(doc["selecionados"])>10:
        raise ValueError("Lista de processos invalida")
    if doc.get("snapshotSha256")!=hashlib.sha256(radar.read_bytes()).hexdigest():
        raise ValueError("Snapshot foi alterado desde planejamento; revisar manifesto")
    ids=[x.get("id") for x in doc["selecionados"]]
    if len(ids)!=len(set(ids)) or any(not isinstance(x,str) or not PAT_ID.fullmatch(x) for x in ids):
        raise ValueError("IDs invalidos/duplicados no manifesto")
    print("PROCESSOS CONGELADOS:",len(ids),flush=True)
    fetched=False
    for i,d in enumerate(doc["selecionados"],1):
        ident=d["id"];path=cp_path(base,ident)
        state,count=state_checkpoint(path,ident)
        print("\n"+str(i)+"/"+str(len(ids))+" | "+ident+
              " | checkpoint="+state+" | itens="+str(count),flush=True)
        print("OBJETO:",d.get("objeto"),flush=True)
        if state=="COMPLETO":
            print("PRESERVADO: sem consulta",flush=True)
            continue
        if not args.executar:
            print("PENDENTE: coleta manual autorizada somente com --executar",flush=True)
            continue
        if fetched:
            print("PAUSA ENTRE PROCESSOS:",args.intervalo,"s",flush=True)
            time.sleep(args.intervalo)
        cmd=[str(args.python),"-u",str(collector),"--id",ident,
             "--banco",str(dbfile),"--saida",str(path),
             "--max-paginas",str(args.max_paginas),
             "--intervalo",str(args.intervalo)]
        print("CONSULTA OFICIAL PNCP",flush=True)
        status=subprocess.run(cmd,check=False)
        fetched=True
        if status.returncode:
            print("PARADA SEGURA: coletor falhou; checkpoint preservado",file=sys.stderr)
            return status.returncode
        final,n=state_checkpoint(path,ident)
        print("RESULTADO:",final,"|",n,"itens",flush=True)
        if final=="PARCIAL":
            print("LIMITE DE PAGINAS: retomar este lote antes de prosseguir",flush=True)
            return 2
    print("\nLOTE PROCESSADO | SQLITE SOMENTE LEITURA | ADERENCIA NEUTRO | SEM AGENDAMENTOS",flush=True)
    print("MANIFESTO:",manifest,flush=True)
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except (ValueError,RuntimeError,OSError,sqlite3.Error,TypeError,json.JSONDecodeError) as e:
        print("PARADA SEGURA:",type(e).__name__,str(e),file=sys.stderr)
        sys.exit(1)
