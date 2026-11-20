#!/usr/bin/env python3
"""GOV POC-66: recuperacao manual de ate 7 dias PNCP CE, publicacao+atualizacao.
Sem --executar, somente planejamento, sem leitura de API e sem escrita.
Com --executar: checkpoint por dia/tipo, importacao sequencial auditada,
um backup consistente por invocacao antes da primeira escrita, lock exclusivo.
Nao instala agendador, nao limpa backups, nao altera outros sistemas.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from contextlib import closing

TABLES=("contratacoes","versoes","importacoes","contratacoes_detalhes","contratacoes_detalhes_versoes")

def conexao_ro(path):
    return sqlite3.connect("file:"+path.resolve().as_posix()+"?mode=ro",uri=True,timeout=15)

def db_status(path):
    with closing(conexao_ro(path)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise RuntimeError("SQLite integrity_check reprovado")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("SQLite foreign_key_check reprovado")
        return {t:db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in TABLES}

def status_cp(path,day,kind):
    if not path.is_file():
        return "AUSENTE",None,0
    raw=path.read_bytes()
    doc=json.loads(raw.decode("utf-8-sig"))
    if not isinstance(doc,dict):
        raise ValueError("Checkpoint nao e objeto "+path.name)
    cfg={"inicio":day,"fim":day,"uf":"CE","municipio":None,
         "modalidade":6,"tamanhoPagina":50}
    if kind=="atualizacoes":cfg["tipoConsulta"]="atualizacao"
    if doc.get("config")!=cfg:
        raise ValueError("Checkpoint config divergente: "+path.name)
    items=doc.get("registros")
    if not isinstance(items,list):
        raise ValueError("Checkpoint sem lista de registros: "+path.name)
    ids=[x.get("numeroControlePNCP") if isinstance(x,dict) else None for x in items]
    if len(ids)!=len(set(ids)) or not all(isinstance(x,str) and x for x in ids):
        raise ValueError("IDs ausentes ou repetidos: "+path.name)
    if any((x.get("unidadeOrgao") or {}).get("ufSigla")!="CE" for x in items):
        raise ValueError("UF divergente: "+path.name)
    state=doc.get("status")
    if state not in ("COMPLETO","PARCIAL"):
        raise ValueError("Checkpoint nao recuperavel: "+path.name+"="+str(state))
    if state=="COMPLETO" and len(items)!=doc.get("totalRegistrosInformado"):
        raise ValueError("Checkpoint completo com total divergente: "+path.name)
    return state,hashlib.sha256(raw).hexdigest(),len(items)

def already(dbfile,digest):
    with closing(conexao_ro(dbfile)) as db:
        return db.execute("SELECT 1 FROM importacoes WHERE arquivo_sha256=?",(digest,)).fetchone() is not None

def make_backup(dbfile,backupdir):
    backupdir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    dest=backupdir/("gov_pre_poc66_"+stamp+".sqlite3")
    with closing(conexao_ro(dbfile)) as src,closing(sqlite3.connect(dest)) as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise RuntimeError("Backup invalido")
        if dst.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Backup com FK invalida")
    print("BACKUP UNICO DA EXECUCAO:",dest,flush=True)
    return dest

def call(argv):
    print("EXEC:",Path(str(argv[1])).name,flush=True)
    rc=subprocess.run([str(x) for x in argv],check=False).returncode
    if rc:raise RuntimeError("Comando interrompido, codigo "+str(rc))
    return rc

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    p.add_argument("--python",default=sys.executable)
    p.add_argument("--inicio",required=True,help="YYYYMMDD")
    p.add_argument("--dias",type=int,default=7)
    p.add_argument("--max-paginas",type=int,default=8)
    p.add_argument("--intervalo",type=float,default=4.0)
    p.add_argument("--executar",action="store_true")
    a=p.parse_args()
    if not 1<=a.dias<=7 or not 1<=a.max_paginas<=8 or a.intervalo<4:
        p.error("dias 1..7, max-paginas 1..8, intervalo >=4s")
    start=datetime.strptime(a.inicio,"%Y%m%d").date()
    if start<datetime(2026,8,23).date() or start+timedelta(days=a.dias)>datetime.now().date():
        p.error("Lote deve estar nos ultimos 90 dias e conter apenas dias encerrados")
    base=Path(a.base);dados=base/"dados";scripts=base/"scripts"
    dbfile=dados/"gov_intelligence_ce_poc.sqlite3"
    imp=scripts/"importar_checkpoint_sqlite.py"
    collectors={
       "publicacoes":scripts/"coleta_publicacoes_checkpoint_p50.py",
       "atualizacoes":scripts/"coleta_atualizacoes_checkpoint_p50.py"}
    if not all(f.is_file() for f in [dbfile,imp,*collectors.values()]):
        raise FileNotFoundError("Scripts ou SQLite nao encontrados")
    tasks=[]
    for offset in range(a.dias):
        day=(start+timedelta(days=offset)).strftime("%Y%m%d")
        for kind,script in collectors.items():
            path=dados/("pncp_ce_"+kind+"_"+day+"_p50.json")
            tasks.append((day,kind,script,path))
    print("=== GOV POC-66 — RECUPERACAO SEMANAL CE ===",flush=True)
    print("JANELA:",a.inicio,"-",(start+timedelta(days=a.dias-1)).strftime("%Y%m%d"),flush=True)
    print("MODO:","EXECUTAR" if a.executar else "PLANEJAR",flush=True)
    print("BANCO INICIAL:",db_status(dbfile),flush=True)
    for day,kind,_,path in tasks:
        st,digest,n=status_cp(path,day,kind)
        imported=bool(digest and already(dbfile,digest))
        print(day,kind,st,n,"registros","IMPORTADO" if imported else "PENDENTE",flush=True)
    if not a.executar:
        print("SOMENTE LEITURA | REDE ZERO | AGENDAMENTOS ZERO",flush=True)
        return 0
    lockpath=base/"poc66_execucao.lock"
    try:
        fd=os.open(str(lockpath),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError("Outra execucao ou lock residual; verificar antes de remover "+str(lockpath))
    with os.fdopen(fd,"w",encoding="utf-8") as lock:
        lock.write("PID="+str(os.getpid())+" INICIO_UTC="+datetime.now(timezone.utc).isoformat())
    did_backup=False
    requests_performed=False
    try:
        for day,kind,script,path in tasks:
            st,digest,n=status_cp(path,day,kind)
            if st!="COMPLETO":
                if requests_performed:
                    time.sleep(a.intervalo)
                call([a.python,script,"--inicio",day,"--fim",day,"--uf","CE",
                      "--saida",path,"--tamanho-pagina",50,
                      "--max-paginas",a.max_paginas,"--intervalo",a.intervalo])
                requests_performed=True
                st,digest,n=status_cp(path,day,kind)
                if st!="COMPLETO":
                    print("PARCIAL:",path.name,"| retomar a mesma semana",flush=True)
                    return 2
            if already(dbfile,digest):
                print("JA IMPORTADO:",path.name,flush=True)
                continue
            if not did_backup:
                make_backup(dbfile,dados/"backups_operacionais")
                did_backup=True
            before=db_status(dbfile)
            call([a.python,imp,"--entrada",path,"--banco",dbfile])
            after=db_status(dbfile)
            if after["importacoes"]!=before["importacoes"]+1:
                raise RuntimeError("Contagem de importacoes incorreta")
            if not already(dbfile,digest):
                raise RuntimeError("Hash de checkpoint nao consta no SQLite")
            if any(after[x]!=before[x] for x in ("contratacoes_detalhes","contratacoes_detalhes_versoes")):
                raise RuntimeError("Tabelas de detalhes alteradas")
            print("IMPORTACAO OK:",day,kind,"|","contratacoes",after["contratacoes"],flush=True)
        print("LOTE COMPLETO | SQLITE FINAL:",db_status(dbfile),flush=True)
        print("BACKUP NOVO:",int(did_backup),"| AGENDA ZERO",flush=True)
        return 0
    finally:
        lockpath.unlink(missing_ok=True)

if __name__=="__main__":
    try:sys.exit(main())
    except (ValueError,RuntimeError,OSError,sqlite3.Error,TypeError,KeyError,json.JSONDecodeError) as e:
        print("PARADA SEGURA:",type(e).__name__,str(e),file=sys.stderr)
        sys.exit(1)
