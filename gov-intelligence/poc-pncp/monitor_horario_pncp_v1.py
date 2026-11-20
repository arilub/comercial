#!/usr/bin/env python3
"""GOV POC-72: monitor horario MANUAL de publicacoes+atualizacoes PNCP CE.
Dia corrente e sempre provisório: novas consultas em TODA execucao.
Nao agenda tarefas, nao toca PIF/Comercial, nao exclui backups antigos.
Checkpoint novo temporario por consulta; preserva apenas ultimo snapshot
validado de cada endpoint. Um backup diario consistente antes de escrever.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path

KINDS={"publicacoes":"coleta_publicacoes_checkpoint_p50.py",
       "atualizacoes":"coleta_atualizacoes_checkpoint_p50.py"}

def load(path):
    if not path.exists():return None
    obj=json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj,dict):raise ValueError("JSON nao objeto: "+str(path))
    return obj

def semantic(doc):
    rows=doc.get("registros")
    if doc.get("status")!="COMPLETO" or not isinstance(rows,list):
        raise ValueError("Checkpoint nao COMPLETO")
    if len(rows)!=doc.get("totalRegistrosInformado"):
        raise ValueError("Total divergente")
    ids=[r.get("numeroControlePNCP") for r in rows]
    if not all(isinstance(x,str) and x for x in ids) or len(set(ids))!=len(ids):
        raise ValueError("IDs invalidos ou duplicados")
    if any((r.get("unidadeOrgao") or {}).get("ufSigla")!="CE" for r in rows):
        raise ValueError("UF inesperada")
    byid=sorted(rows,key=lambda r:r["numeroControlePNCP"])
    raw=json.dumps(byid,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest(),len(rows)

def audit(dbfile):
    with closing(sqlite3.connect("file:"+dbfile.resolve().as_posix()+"?mode=ro",uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise RuntimeError("SQLite quick_check falhou")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("SQLite FK falhou")
        return {t:db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0]
                for t in ("contratacoes","versoes","importacoes",
                          "contratacoes_detalhes","contratacoes_detalhes_versoes")}

def backup_once(dbfile,dir,datekey):
    dir.mkdir(parents=True,exist_ok=True)
    dest=dir/("gov_pre_horario_"+datekey+".sqlite3")
    if dest.exists():
        with closing(sqlite3.connect("file:"+dest.resolve().as_posix()+"?mode=ro",uri=True)) as chk:
            if chk.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or chk.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Backup diario existente invalido: "+str(dest))
        print("BACKUP DIARIO REUTILIZADO:",dest.name,flush=True)
        return
    tmp=dest.with_name(dest.name+".tmp")
    try:
        with closing(sqlite3.connect("file:"+dbfile.resolve().as_posix()+"?mode=ro",uri=True)) as src,closing(sqlite3.connect(tmp)) as target:
            src.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or target.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Backup criado invalido")
        os.replace(tmp,dest)
    finally:
        tmp.unlink(missing_ok=True)
    print("BACKUP DIARIO CRIADO:",dest.name,flush=True)

def run(cmd):
    code=subprocess.run([str(x) for x in cmd],check=False).returncode
    if code:raise RuntimeError("Subprocesso falhou codigo="+str(code)+" script="+str(cmd[1]))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    p.add_argument("--python",default=sys.executable)
    p.add_argument("--max-paginas",type=int,default=8)
    p.add_argument("--intervalo",type=float,default=4)
    p.add_argument("--executar",action="store_true")
    a=p.parse_args()
    if not 1<=a.max_paginas<=8 or a.intervalo<4:
        p.error("max paginas: 1 a 8; intervalo >= 4")
    base=Path(a.base);dados=base/"dados";scripts=base/"scripts"
    banco=dados/"gov_intelligence_ce_poc.sqlite3"
    importador=scripts/"importar_checkpoint_sqlite.py"
    if not all(x.is_file() for x in (banco,importador,*[scripts/n for n in KINDS.values()])):
        raise FileNotFoundError("Banco ou scripts ausentes")
    # Use a single lock compatible with the manual 90d loader.
    lock=base/"poc66_execucao.lock"
    hoje=datetime.now().strftime("%Y%m%d")
    print("=== GOV POC-72 — MONITOR HORARIO MANUAL ===",flush=True)
    print("DIA LOCAL:",hoje,"| MODO:","EXECUTAR" if a.executar else "PLANEJAR",flush=True)
    print("SQLITE ANTES:",audit(banco),flush=True)
    if not a.executar:
        print("AGENDA ZERO | API ZERO | SQLITE SOMENTE LEITURA",flush=True)
        return 0
    try:
        fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError("Rotina GOV ja executando ou lock residual: "+str(lock))
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        f.write("POC72 pid="+str(os.getpid())+" inicio="+datetime.now(timezone.utc).isoformat())
    started=time.monotonic()
    tempfiles=[]
    try:
        for idx,(kind,collector) in enumerate(KINDS.items()):
            now=datetime.now()
            if now.strftime("%Y%m%d")!=hoje:
                raise RuntimeError("Virada de dia durante execucao: interromper sem reutilizar data")
            suffix=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            staged=dados/("gov_hourly_"+kind+"_"+hoje+"_"+suffix+".json")
            tempfiles.append(staged)
            if idx:time.sleep(a.intervalo)
            print("COLETANDO:",kind,"| snapshot novo",flush=True)
            run([a.python,scripts/collector,"--inicio",hoje,"--fim",hoje,
                 "--uf","CE","--saida",staged,"--max-paginas",
                 a.max_paginas,"--intervalo",a.intervalo])
            doc=load(staged)
            cfg=doc.get("config",{})
            if cfg.get("inicio")!=hoje or cfg.get("fim")!=hoje or cfg.get("uf")!="CE":
                raise ValueError("Configuracao de snapshot divergente")
            digest,n=semantic(doc)
            snapshot=dados/("gov_hourly_"+kind+"_ultimo.json")
            previous=load(snapshot)
            unchanged=False
            if previous and (previous.get("config") or {}).get("inicio")==hoje:
                old_digest,_=semantic(previous)
                unchanged=(old_digest==digest)
            if unchanged:
                print("SEM MUDANCA:",kind,"|",n,"registros | SQLite sem escrita",flush=True)
            else:
                print("SNAPSHOT NOVO:",kind,"|",n,"registros | preparar importacao",flush=True)
                backup_once(banco,dados/"backups_operacionais",hoje)
                before=audit(banco)
                run([a.python,importador,"--entrada",staged,"--banco",banco])
                after=audit(banco)
                if after["importacoes"]!=before["importacoes"]+1:
                    raise RuntimeError("Importacao nao registrada")
                for t in ("contratacoes_detalhes","contratacoes_detalhes_versoes"):
                    if after[t]!=before[t]:
                        raise RuntimeError("Detalhamento alterado sem autorizacao")
                print("IMPORTADO:",kind,"| total:",after["contratacoes"],flush=True)
            # Preserve only most recent validated checkpoint per endpoint.
            os.replace(staged,snapshot)
            tempfiles.remove(staged)
        print("SQLITE FINAL:",audit(banco),flush=True)
        print("DURACAO:",round(time.monotonic()-started,1),"s | AGENDAMENTO ZERO",flush=True)
        print("STATUS: CONCLUIDO | DIA CORRENTE PROVISORIO",flush=True)
        return 0
    finally:
        for t in tempfiles:
            # Preserve partial and inconsistent snapshots for diagnosis instead of
            # treating them as successful runs.
            if t.exists():print("CHECKPOINT DIAGNOSTICO PRESERVADO:",t,flush=True)
        lock.unlink(missing_ok=True)

if __name__=="__main__":
    try:sys.exit(main())
    except Exception as e:
        print("PARADA SEGURA:",type(e).__name__,str(e),file=sys.stderr)
        sys.exit(1)
