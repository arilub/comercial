#!/usr/bin/env python3
"""POC82: exportacao integral do SQLite para Radar V1.5, sem alterar V1.4.

Inclui TODOS os pregoes presentes no banco, inclusive historico, cancelados,
suspensos, revogados. Enriquecimentos antigos por ID sao preservados apenas se
validos, com marcador de coleta e data. Nenhum corte por paginas, status ou data.

ATENCAO: base SQLite pode ter cobertura historica parcial; total local nao e
total do PNCP. Nao inferir aderencia a ARILUB nem situacao de resultado de item.
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path

FUSO=timezone(timedelta(hours=-3))

def data(v):
 if not v:return None
 try:
  d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
  return d.replace(tzinfo=FUSO) if d.tzinfo is None else d.astimezone(FUSO)
 except (TypeError,ValueError):return None

def valor(v):
 if type(v) in (int,float) and v>0:return {"estado":"VALOR_POSITIVO_INFORMADO","valor":v}
 if type(v) in (int,float) and v==0:return {"estado":"ZERO_SIGILO_NAO_VERIFICADO","valor":None}
 return {"estado":"NAO_INFORMADO","valor":None}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--base",required=True)
 p.add_argument("--saida")
 a=p.parse_args()
 base=Path(a.base)
 banco=base/"dados"/"gov_intelligence_ce_poc.sqlite3"
 saida=Path(a.saida) if a.saida else base/"dados"/"radar_v15_integral_poc82.json"
 legado=base/"dados"/"radar_v1_candidatos_itens_poc57.json"
 if not banco.is_file():raise FileNotFoundError(str(banco))
 if saida.resolve() in (banco.resolve(),legado.resolve()):raise ValueError("Saida protegida")
 enrich={}
 if legado.is_file():
  d=json.loads(legado.read_text(encoding="utf-8-sig"))
  if d.get("schema")!="gov-intelligence-radar-v1-poc57":
   raise ValueError("Schema legado inesperado; preservacao exige revisao")
  for r in d.get("candidatos",[]):
   if r.get("statusEnriquecimentoItens")!="COMPLETO":continue
   itens=r.get("itensPNCP")
   resumo=r.get("resumoItensPNCP")
   if not isinstance(itens,list) or not isinstance(resumo,dict) or len(itens)!=resumo.get("totalItens"):
    raise ValueError("Enriquecimento legado inconsistente")
   if r["id"] in enrich:raise ValueError("ID duplicado no enriquecimento")
   enrich[r["id"]]=(itens,resumo)
 agora=datetime.now(FUSO)
 contas=Counter()
 rows=[]
 with sqlite3.connect("file:"+banco.resolve().as_posix()+"?mode=ro",uri=True) as db:
  if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":raise RuntimeError("SQLite inconsistente")
  total=db.execute("SELECT COUNT(*) FROM contratacoes").fetchone()[0]
  for ident,uf,pub,updated,payload in db.execute("SELECT id,uf,data_publicacao,data_atualizacao,payload_json FROM contratacoes ORDER BY data_publicacao DESC,id"):
   d=json.loads(payload)
   if d.get("numeroControlePNCP")!=ident:raise RuntimeError("ID divergente "+ident)
   org=d.get("orgaoEntidade") or {};unidade=d.get("unidadeOrgao") or {}
   if not isinstance(org,dict) or not isinstance(unidade,dict):raise RuntimeError("Orgao/unidade invalido "+ident)
   sigla=unidade.get("ufSigla") or uf
   if sigla != uf:raise RuntimeError("UF divergente "+ident)
   fim=data(d.get("dataEncerramentoProposta"));abertura=data(d.get("dataAberturaProposta"))
   status=d.get("situacaoCompraNome") or "NAO_INFORMADO"
   if fim and fim<=agora:temporal="PRAZO_ENCERRADO"
   elif fim and abertura and abertura>agora:temporal="ABERTURA_FUTURA"
   elif fim and abertura and abertura<=agora:temporal="PRAZO_EM_CURSO"
   elif fim:temporal="ABERTURA_INDETERMINADA"
   else:temporal="PRAZO_INDETERMINADO"
   contas["fase_"+temporal]+=1
   contas["status_"+status]+=1
   contas["uf_"+sigla]+=1
   ano=d.get("anoCompra");seq=d.get("sequencialCompra");cnpj=org.get("cnpj")
   link=("https://pncp.gov.br/app/editais/"+cnpj+"/"+str(ano)+"/"+str(seq)
     if isinstance(cnpj,str) and len(cnpj)==14 and cnpj.isdigit()
     and type(ano) is int and type(seq) is int else None)
   complete=ident in enrich
   itens,resumo=enrich[ident] if complete else ([],None)
   rows.append({
    "id":ident,"anoCompra":ano,"numeroCompra":d.get("numeroCompra"),"objeto":d.get("objetoCompra"),
    "orgao":org.get("razaoSocial"),"cnpjOrgao":cnpj,"municipio":unidade.get("municipioNome"),
    "uf":sigla,"situacaoPNCP":status,"dataPublicacao":d.get("dataPublicacaoPncp") or pub,
    "dataAtualizacao":d.get("dataAtualizacao") or updated,
    "aberturaProposta":abertura.isoformat() if abertura else None,
    "encerramentoProposta":fim.isoformat() if fim else None,
    "faseTemporal":temporal,"valorEstimado":valor(d.get("valorTotalEstimado")),
    "valorHomologadoInformado":d.get("valorTotalHomologado"),"linkPNCP":link,
    "linkSistemaOrigem":d.get("linkSistemaOrigem"),
    "aderenciaComercial":"NEUTRO","classificacaoItens":"PNCP_CONSULTADO" if complete else "NAO_VERIFICADA",
    "orcamentoSigiloso":"NAO_VERIFICADO","statusRadar":"CANDIDATO_PRELIMINAR",
    "statusEnriquecimentoItens":"COMPLETO" if complete else "NAO_COLETADO",
    "resumoItensPNCP":resumo,"itensPNCP":itens})
 if len(rows)!=total:raise RuntimeError("Exportacao integral incompleta")
 if len({r["id"] for r in rows})!=total:raise RuntimeError("IDs repetidos")
 usados=sum(r["statusEnriquecimentoItens"]=="COMPLETO" for r in rows)
 doc={
  "schema":"gov-intelligence-radar-v15-integral",
  "geradoEm":agora.isoformat(),"timezone":"America/Fortaleza (UTC-03)",
  "fonte":"SQLite local com snapshots oficiais PNCP",
  "abrangencia":"CE (na base atual), modalidade pregao eletronico",
  "carater":"COBERTURA HISTORICA PARCIAL; ADERENCIA NAO HOMOLOGADA; RESULTADOS DE ITENS NAO INTEGRADOS",
  "nota":"Todos os registros do SQLite sem filtro previo de fase, status ou tipo de objeto. Nao equivale a todos os pregoes existentes no PNCP.",
  "contratacoesBase":total,"contagens":dict(contas),
  "enriquecimento":{"processosComItensCompletos":usados,
    "itensTotais":sum(len(r["itensPNCP"]) for r in rows)},
  "candidatos":rows}
 saida.parent.mkdir(parents=True,exist_ok=True)
 tmp=saida.with_name(saida.name+".tmp")
 try:
  with tmp.open("w",encoding="utf-8") as f:
   json.dump(doc,f,ensure_ascii=False,separators=(",",":"),allow_nan=False)
   f.flush();os.fsync(f.fileno())
  os.replace(tmp,saida)
 finally:tmp.unlink(missing_ok=True)
 print("=== GOV POC82 - EXPORTACAO INTEGRAL V1.5 ===")
 print("SQLITE:",total)
 print("EXPORTADOS:",len(rows))
 print("FUTUROS E EM CURSO:",sum(v for k,v in contas.items() if k in ("fase_PRAZO_EM_CURSO","fase_ABERTURA_FUTURA","fase_ABERTURA_INDETERMINADA")))
 print("PRAZO ENCERRADO:",contas["fase_PRAZO_ENCERRADO"])
 print("PRAZO INDETERMINADO:",contas["fase_PRAZO_INDETERMINADO"])
 print("ENRIQUECIMENTOS PRESERVADOS:",usados)
 print("ITENS PRESERVADOS:",doc["enriquecimento"]["itensTotais"])
 print("JSON V1.5:",saida)
 print("V1.4, SQLITE E AGENDAMENTO: INALTERADOS")
 return 0
if __name__=="__main__":
 try:sys.exit(main())
 except (OSError,RuntimeError,TypeError,ValueError,sqlite3.Error) as e:
  print("PARADA SEGURA:",type(e).__name__,str(e),file=sys.stderr);sys.exit(1)
