#!/usr/bin/env python3
"""POC81 diagnostico read-only da fonte do radar e cobertura para V1.5.
Nao modifica SQLite nem snapshots; nao toca nos agendamentos.
"""
import argparse,json,sqlite3,collections
from pathlib import Path
from datetime import datetime,timezone

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--base",required=True)
 a=p.parse_args();base=Path(a.base); db=base/"dados"/"gov_intelligence_ce_poc.sqlite3"
 print("=== GOV POC81 - AUDITORIA DE BASE E EXPORTACAO ===")
 with sqlite3.connect("file:"+db.resolve().as_posix()+"?mode=ro",uri=True) as con:
  names=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
  print("TABELAS:",", ".join(names))
  for name in names:
   if name not in ("contratacoes","contratacoes_detalhes","importacoes"):continue
   print("CAMPOS",name,":",", ".join(x[1] for x in con.execute("PRAGMA table_info("+name+")")))
  print("TOTAL_PREGOES:",con.execute("SELECT COUNT(*) FROM contratacoes").fetchone()[0])
  rows=con.execute("SELECT id,payload_json FROM contratacoes").fetchall()
 situacoes=collections.Counter();ufs=collections.Counter();modalidades=collections.Counter()
 prazos=collections.Counter();tipos=collections.Counter();semdata=0
 for ident,raw in rows:
  try:d=json.loads(raw)
  except Exception:continue
  situacoes[str(d.get("situacaoCompraNome") or "<nao informado>")]+=1
  modalidades[str(d.get("modalidadeNome") or "<nao informado>")]+=1
  unidade=d.get("unidadeOrgao") or {}
  ufs[str(unidade.get("ufSigla") or "<nao informado>")]+=1
  data=d.get("dataEncerramentoProposta")
  if data:
   prazos["futuro" if str(data)[:10]>=datetime.now().date().isoformat() else "passado"]+=1
  else:semdata+=1
 print("SITUACOES:",situacoes.most_common(12))
 print("UF (origem):",ufs.most_common(8))
 print("MODALIDADES:",modalidades.most_common(8))
 print("ENCERRAMENTO:",dict(prazos),"SEM DATA:",semdata)
 for f in sorted((base/"dados").glob("radar*.json")):
  print("ARQUIVO_RADAR:",f.name,"BYTES:",f.stat().st_size,"ALTERADO_UTC:",datetime.fromtimestamp(f.stat().st_mtime,timezone.utc).isoformat())
  try:
   doc=json.loads(f.read_text(encoding="utf-8-sig"))
   print("  SCHEMA:",doc.get("schema"),"BASE:",doc.get("contratacoesBase"),
         "CANDIDATOS:",len(doc.get("candidatos",[])) if isinstance(doc.get("candidatos"),list) else "n/a",
         "GERADO:",doc.get("geradoEm"))
  except Exception as exc:print("  ERRO_LECTURA:",type(exc).__name__,str(exc)[:100])
 for scope in (base,base/"scripts"):
  print("SCRIPTS",scope)
  if scope.is_dir():
   for f in sorted(scope.glob("*.py")):
    nm=f.name.lower()
    if any(k in nm for k in ("radar","export","candidat","apresent","item")):
     print(" ",f.name,"BYTES:",f.stat().st_size)
 print("SQLITE E PAINEL: SOMENTE LEITURA | NENHUMA ALTERACAO")
if __name__=="__main__":main()
