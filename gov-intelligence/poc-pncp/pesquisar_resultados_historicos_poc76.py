#!/usr/bin/env python3
"""GOV POC-76: prova read-only PNCP de item -> resultado -> fornecedor -> orgao.

Seleciona ate cinco pregoes encerrados no SQLite (preferencia por situacao
homologada/encerrada), consulta itens e resultados de no maximo 3 itens.
Grava apenas JSON de diagnostico POC76, sem modificar banco/painel.
Retornos vazios, dados indisponiveis ou HTTP 429 nao viram vencedores ficticios.
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request,urlopen

API="https://pncp.gov.br/api/pncp/v1/orgaos"
def fetch(url):
    req=Request(url,headers={"Accept":"application/json","User-Agent":"ARILUB-GOV-POC76/1.0"})
    try:
        with urlopen(req,timeout=30) as resp:
            raw=resp.read()
            if resp.status==204:return 204,None
            if not raw:return resp.status,None
            return resp.status,json.loads(raw.decode("utf-8-sig"))
    except HTTPError as e:
        return e.code,{"erroHTTP":str(e.reason)}
def parsed_id(s):
    m=re.fullmatch(r"(\d{14})-1-(\d+)/(\d{4})",str(s))
    return (m.group(1),m.group(3),m.group(2)) if m else None
def candidates(dbfile):
    with sqlite3.connect("file:"+dbfile.resolve().as_posix()+"?mode=ro",uri=True) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":raise RuntimeError("SQLite inconsistente")
        rows=db.execute("SELECT id,payload_json,data_publicacao FROM contratacoes WHERE data_publicacao IS NOT NULL ORDER BY data_publicacao DESC").fetchall()
    opts=[]
    for id,raw,pub in rows:
        try:payload=json.loads(raw)
        except (TypeError,ValueError):continue
        parts=parsed_id(id)
        if not parts:continue
        cnpj,ano,seq=parts
        anoCampo=payload.get("anoCompra")
        seqCampo=payload.get("sequencialCompra")
        cnpjCampo=(payload.get("orgaoEntidade") or {}).get("cnpj")
        if str(anoCampo or ano)!=ano or str(seqCampo or seq).lstrip("0")!=str(int(seq)):
            continue
        if cnpjCampo and str(cnpjCampo)!=cnpj:
            continue
        st=str(payload.get("situacaoCompraNome") or "")
        termino=str(payload.get("dataEncerramentoProposta") or "")
        if termino and termino[:10]>=datetime.now().strftime("%Y-%m-%d"):continue
        if not termino and str(pub or "")[:10]>=datetime.now().strftime("%Y-%m-%d"):continue
        score=4 if any(w in st.lower() for w in ("homolog","conclu","encerr")) else 0
        score+=2 if payload.get("valorTotalHomologado") else 0
        score+=1 if "2025" in id else 0
        opts.append((score,id,payload,parts))
    return sorted(opts,key=lambda x:(-x[0],x[1]))
def unpack_items(doc):
    if isinstance(doc,list):return doc
    if isinstance(doc,dict):
        for k in ("data","itens"):
            if isinstance(doc.get(k),list):return doc[k]
    return []
def unpack_results(doc):
    if isinstance(doc,list):return doc
    if isinstance(doc,dict):
        for k in ("data","resultados"):
            if isinstance(doc.get(k),list):return doc[k]
    return []
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    p.add_argument("--id",default="",help="ID PNCP exato, se desejar fixar pregao")
    p.add_argument("--consultas",type=int,default=5)
    p.add_argument("--itens",type=int,default=3)
    a=p.parse_args()
    if not 1<=a.consultas<=8 or not 1<=a.itens<=5:
        p.error("Limite: ate 8 pregoes e 5 itens por pregao")
    base=Path(a.base); dbfile=base/"dados"/"gov_intelligence_ce_poc.sqlite3"
    if not dbfile.is_file():raise FileNotFoundError("Banco nao encontrado")
    opts=candidates(dbfile)
    if a.id:
        opts=[o for o in opts if o[1]==a.id]
        if not opts:raise ValueError("ID nao encontrado entre candidatos encerrados")
    print("=== GOV POC-76 — RESULTADOS DOS ITENS PNCP ===",flush=True)
    print("CANDIDATOS HISTORICOS ENCONTRADOS:",len(opts),flush=True)
    output={"schema":"gov-poc76-resultado-exploratorio","geradoEmUTC":datetime.now(timezone.utc).isoformat(),
            "fonte":"API PNCP oficial","limitePregoes":a.consultas,"limiteItens":a.itens,
            "processos":[],"observacoes":[]}
    found=False
    for _,id,payload,(cnpj,ano,seq) in opts[:a.consultas]:
        url=f"{API}/{cnpj}/compras/{ano}/{int(seq)}/itens?"+urlencode({"pagina":1,"tamanhoPagina":50})
        try:status,body=fetch(url)
        except (URLError,TimeoutError,ValueError) as e:
            print("FALHA REDE:",id,type(e).__name__,str(e)[:160],flush=True);continue
        row={"id":id,"orgao":(payload.get("orgaoEntidade") or {}).get("razaoSocial"),
             "municipio":(payload.get("unidadeOrgao") or {}).get("municipioNome"),
             "situacaoCompraNome":payload.get("situacaoCompraNome"),
             "urlItens":url,"httpItens":status,"itensInspecionados":[]}
        output["processos"].append(row)
        if status!=200:
            print("ITENS HTTP:",status,id,flush=True)
            if status==429:break
            time.sleep(2);continue
        items=unpack_items(body)
        if not items:
            print("SEM ITENS:",id,"| formato",type(body).__name__,flush=True)
            time.sleep(2);continue
        selected=[x for x in items if isinstance(x,dict) and x.get("temResultado") is True]
        # Se o atributo nao for fornecido pelo PNCP, investigar pequena
        # amostra sem presumir que existe resultado.
        if not selected:
            selected=[x for x in items if isinstance(x,dict) and x.get("temResultado") is not False]
        print("PROCESSO:",id,"| itens pagina 1:",len(items),"| itens para verificacao:",len(selected),flush=True)
        for item in selected[:a.itens]:
            num=item.get("numeroItem")
            if not isinstance(num,int):continue
            resurl=f"{API}/{cnpj}/compras/{ano}/{int(seq)}/itens/{num}/resultados"
            time.sleep(3)
            try:rs,rd=fetch(resurl)
            except (URLError,TimeoutError,ValueError) as e:
                print("ERRO RESULTADO:",type(e).__name__,str(e)[:120],flush=True);continue
            results=unpack_results(rd)
            entry={"numeroItem":num,"descricao":item.get("descricao"),
                   "quantidade":item.get("quantidade"),
                   "unidadeMedida":item.get("unidadeMedida"),
                   "valorUnitarioEstimado":item.get("valorUnitarioEstimado"),
                   "catalogoCodigoItem":item.get("catalogoCodigoItem"),
                   "ncmNbsCodigo":item.get("ncmNbsCodigo"),"urlResultados":resurl,
                   "httpResultados":rs,"resultados":results[:10],
                   "camposResultado":sorted({k for r in results if isinstance(r,dict) for k in r.keys()})}
            row["itensInspecionados"].append(entry)
            print(" ITEM:",num,"| HTTP",rs,"| resultados",len(results),flush=True)
            if rs==200 and results:found=True
            if rs==429:break
        if found:break
        time.sleep(3)
    output["resultadoIdentificado"]=found
    out=base/"dados"/"poc76_pesquisa_resultados_historicos.json"
    tmp=out.with_suffix(out.suffix+".tmp")
    tmp.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    tmp.replace(out)
    print("PROCESSOS CONSULTADOS:",len(output["processos"]),flush=True)
    print("RESULTADOS ENCONTRADOS:",found,flush=True)
    print("ARQUIVO DE EVIDENCIAS:",out,flush=True)
    print("SQLITE SOMENTE LEITURA | SEM AGENDA | SEM ALTERAR PAINEL",flush=True)
    if not found:
        print("NAO HOMOLOGADO: nenhuma cadeia completa encontrada neste lote; ampliar amostra apos auditoria",flush=True)
    return 0
if __name__=="__main__":
    try:sys.exit(main())
    except (ValueError,OSError,RuntimeError,sqlite3.Error) as e:
        print("PARADA SEGURA:",type(e).__name__,str(e),file=sys.stderr);sys.exit(1)
