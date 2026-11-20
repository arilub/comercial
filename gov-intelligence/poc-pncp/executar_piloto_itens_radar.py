#!/usr/bin/env python3
"""POC-56: lote piloto MANUAL de itens PNCP, selecionados do Radar V1.

Reutiliza coletor homologado; grava apenas checkpoints JSON de itens.
Sem alteracao SQLite, sem atualizacao do radar, sem classificacao comercial.
"""
import argparse
import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ID = re.compile(r"^\d{14}-1-\d{6}/\d{4}$")
BENS = re.compile(r"\b(aquisic(?:ao|oes)|fornecimento|compra|materiais?|produtos?|equipamentos?|pneus?|lubrificantes?|pecas?|ferramentas?|reles|insumos?)\b")
SERV = re.compile(r"\b(servicos?|terceirizac(?:ao|oes)|consultoria|telefonia|licenca|locacao|mao de obra|obra|manutencao)\b")
SINAL = re.compile(r"\b(aquisic(?:ao|oes)|fornecimento|compra|materiais?|produtos?|equipamentos?|pneus?|lubrificantes?|pecas?|ferramentas?|reles|insumos?)\b")

def norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD",str(s).lower()) if not unicodedata.combining(c))

def escolher(rows,limite,db):
    escolhidos=[]
    for row in sorted(rows,key=lambda x:(x.get("encerramentoProposta") or "",x.get("id") or "")):
        ident=row.get("id")
        if not isinstance(ident,str) or not ID.fullmatch(ident):
            continue
        obj=norm(row.get("objeto") or "")
        if not BENS.search(obj) or SERV.search(obj):
            continue
        if row.get("aderenciaComercial")!="NEUTRO" or row.get("statusRadar")!="CANDIDATO_PRELIMINAR":
            continue
        real=db.execute("SELECT uf FROM contratacoes WHERE id=?",(ident,)).fetchone()
        if real!=("CE",):
            raise ValueError("ID de candidato fora da base CE")
        escolhidos.append(row)
        if len(escolhidos)>=limite:
            break
    return escolhidos

def resumo(path,ident):
    doc=json.loads(path.read_text(encoding="utf-8-sig"))
    if doc.get("fonte")!="PNCP-ITENS-v1" or doc.get("id")!=ident:
        raise ValueError("Checkpoint de itens incompatível")
    if doc.get("status") not in ("COMPLETO","PARCIAL"):
        raise ValueError("Status invalido no checkpoint")
    itens=doc.get("itens")
    if not isinstance(itens,list):
        raise ValueError("Itens invalidos")
    nums=[item.get("numeroItem") if isinstance(item,dict) else None for item in itens]
    if any(type(n)!=int or n<1 for n in nums) or len(nums)!=len(set(nums)):
        raise ValueError("NumeroItem ausente ou duplicado")
    amostra=[]
    for item in itens[:3]:
        amostra.append({"numeroItem":item.get("numeroItem"),
                        "descricao":str(item.get("descricao") or "")[:180],
                        "materialOuServico":item.get("materialOuServico"),
                        "tipoBeneficio":item.get("tipoBeneficio")})
    return doc["status"],len(itens),amostra

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--base",required=True)
    a.add_argument("--python",default=sys.executable)
    a.add_argument("--limite",type=int,default=3)
    a.add_argument("--max-paginas",type=int,default=2)
    a.add_argument("--executar",action="store_true",help="Autoriza consulta PNCP e criacao dos checkpoints")
    args=a.parse_args()
    if not 1<=args.limite<=5 or not 1<=args.max_paginas<=3:
        a.error("limite 1..5, max-paginas 1..3")
    base=Path(args.base)
    dbfile=base/"dados"/"gov_intelligence_ce_poc.sqlite3"
    radar=base/"dados"/"radar_v1_candidatos.json"
    coletor=base/"scripts"/"coletar_itens_radar_checkpoint.py"
    if not all(p.is_file() for p in (dbfile,radar,coletor)):
        raise FileNotFoundError("Banco, snapshot ou coletor nao encontrado")
    data=json.loads(radar.read_text(encoding="utf-8-sig"))
    if data.get("schema")!="gov-intelligence-radar-v1-poc52" or not isinstance(data.get("candidatos"),list):
        raise ValueError("Snapshot nao reconhecido")
    with sqlite3.connect(f"file:{dbfile.resolve().as_posix()}?mode=ro",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("SQLite sem integridade")
        selecionados=escolher(data["candidatos"],args.limite,db)
    print("=== GOV POC-56 — PILOTO ITENS OFICIAIS ===",flush=True)
    print("MODO:","EXECUTAR" if args.executar else "PLANEJAR SEM REDE",flush=True)
    print("SNAPSHOT:",data.get("geradoEm"),"| selecionados:",len(selecionados),flush=True)
    if not selecionados:
        print("NENHUM OBJETO COM INDICIO EXPLICITO DE BENS E SEM TERMO DE SERVICO",flush=True)
        return 2
    pasta=base/"dados"/"itens_poc56"
    ultima_chamada=False
    for n,row in enumerate(selecionados,1):
        ident=row["id"]
        path=pasta/("pncp_itens_"+ident.replace("/","_")+".json")
        print(f"\n{n}/{len(selecionados)} | {ident}",flush=True)
        print("OBJETO:",str(row.get("objeto") or "")[:220],flush=True)
        if path.exists():
            status,num,amostra=resumo(path,ident)
            print("CHECKPOINT EXISTENTE:",status,"| itens:",num,flush=True)
            if status=="COMPLETO":
                print("SEM NOVA CONSULTA",flush=True)
                print("AMOSTRA:",json.dumps(amostra,ensure_ascii=False),flush=True)
                continue
        if not args.executar:
            print("PLANEJADO | SEM CONSULTA | CAMINHO:",path,flush=True)
            continue
        if ultima_chamada:
            print("PAUSA ENTRE PROCESSOS: 4s",flush=True)
            time.sleep(4)
        pasta.mkdir(parents=True,exist_ok=True)
        cmd=[str(args.python),"-u",str(coletor),"--id",ident,"--banco",str(dbfile),
             "--saida",str(path),"--max-paginas",str(args.max_paginas),"--intervalo","4"]
        print("COLETANDO ITENS...",flush=True)
        resultado=subprocess.run(cmd,check=False)
        ultima_chamada=True
        if resultado.returncode:
            print("PARADA SEGURA: coletor retornou",resultado.returncode,flush=True)
            return resultado.returncode
        status,num,amostra=resumo(path,ident)
        print("RESULTADO:",status,"| itens:",num,flush=True)
        print("AMOSTRA:",json.dumps(amostra,ensure_ascii=False),flush=True)
        if status=="PARCIAL":
            print("PARCIAL: requer retomada; nao tratar como total de itens",flush=True)
    print("\nFIM. SQLite somente leitura | Aderencia NEUTRO | Sem agendamentos",flush=True)
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except (ValueError,RuntimeError,OSError,sqlite3.Error,json.JSONDecodeError) as err:
        print("PARADA SEGURA:",type(err).__name__,str(err),file=sys.stderr)
        sys.exit(1)
