#!/usr/bin/env python3
"""GOV POC-48: rotina diaria MANUAL PNCP CE, sem agendamento nem sistemas de producao.

Sem --executar: planejamento somente leitura. Com --executar: checkpoints p50
independentes, importacao apenas de arquivos completos, backup SQLite por
arquivo e auditoria. Executar para DIA ENCERRADO.
"""
import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

TABLES = ("contratacoes","versoes","importacoes",
          "contratacoes_detalhes","contratacoes_detalhes_versoes")

def readonly(dbfile):
    return sqlite3.connect(f"file:{dbfile.resolve().as_posix()}?mode=ro", uri=True)

def auditar(dbfile):
    with closing(readonly(dbfile)) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "Integridade SQLite"
        assert not db.execute("PRAGMA foreign_key_check").fetchall(), "Chaves estrangeiras"
        return {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}

def status_arquivo(path, day, tipo):
    if not path.exists():
        return "AUSENTE", None, 0
    bruto = path.read_bytes()
    obj = json.loads(bruto.decode("utf-8-sig"))
    cfg = obj.get("config", {})
    esperado = dict(inicio=day, fim=day, uf="CE", municipio=None,
                    modalidade=6, tamanhoPagina=50)
    if tipo == "atualizacoes":
        esperado["tipoConsulta"] = "atualizacao"
    assert cfg == esperado, f"Checkpoint com configuracao divergente: {path.name}"
    rows = obj.get("registros")
    assert isinstance(rows,list), "Registros invalidos"
    ids = [r.get("numeroControlePNCP") if isinstance(r,dict) else None for r in rows]
    assert len(ids)==len(set(ids)) and all(ids), "IDs invalidos ou repetidos"
    assert all((r.get("unidadeOrgao") or {}).get("ufSigla")=="CE" for r in rows), "UF incorreta"
    estado = obj.get("status")
    assert estado in ("PARCIAL","COMPLETO"), f"Estado invalido: {estado}"
    if estado == "COMPLETO":
        assert len(rows)==obj.get("totalRegistrosInformado"), "Total inconsistente"
    return estado,hashlib.sha256(bruto).hexdigest(),len(rows)

def importado(dbfile, digest):
    with closing(readonly(dbfile)) as db:
        return db.execute("SELECT 1 FROM importacoes WHERE arquivo_sha256=?", (digest,)).fetchone() is not None

def backup(dbfile, destino):
    with closing(readonly(dbfile)) as origem, closing(sqlite3.connect(destino)) as copia:
        origem.backup(copia)
        assert copia.execute("PRAGMA integrity_check").fetchone()[0]=="ok", "Backup invalido"
        assert not copia.execute("PRAGMA foreign_key_check").fetchall(), "Backup com FK invalida"
    print("BACKUP VALIDADO:",destino,flush=True)

def chamar(args):
    print("EXECUTANDO:", " ".join(str(x) for x in args),flush=True)
    ret=subprocess.run([str(x) for x in args],check=False)
    if ret.returncode:
        raise RuntimeError(f"Processo interrompido com codigo {ret.returncode}")
    return ret.returncode

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    p.add_argument("--python",default=sys.executable)
    p.add_argument("--dia",required=True,help="YYYYMMDD, dia encerrado")
    p.add_argument("--max-paginas",type=int,default=10)
    p.add_argument("--intervalo",type=float,default=4)
    p.add_argument("--executar",action="store_true")
    args=p.parse_args()
    if args.max_paginas not in range(1,9) or args.intervalo<4:
        p.error("max-paginas de 1 a 8; intervalo de 4 segundos ou mais")
    dia=datetime.strptime(args.dia,"%Y%m%d").date()
    if not date(2023,11,19)<=dia<date.today():
        p.error("Dia encerrado dentro do horizonte PNCP requerido")
    base=Path(args.base)
    dados=base/"dados"
    scripts=base/"scripts"
    dbfile=dados/"gov_intelligence_ce_poc.sqlite3"
    assert dbfile.is_file(), "SQLite nao encontrado"
    arquivos=[
       ("publicacoes",scripts/"coleta_publicacoes_checkpoint_p50.py",
        dados/f"pncp_ce_publicacoes_{args.dia}_p50.json"),
       ("atualizacoes",scripts/"coleta_atualizacoes_checkpoint_p50.py",
        dados/f"pncp_ce_atualizacoes_{args.dia}_p50.json")]
    assert (scripts/"importar_checkpoint_sqlite.py").is_file(), "Importador nao encontrado"
    assert all(s.is_file() for _,s,_ in arquivos), "Coletores p50 nao encontrados"
    inicio=time.perf_counter()
    print("=== GOV POC-48 — ROTINA DIARIA MANUAL ===",flush=True)
    print("DIA:",args.dia,"| MODO:","EXECUTAR" if args.executar else "PLANEJAR SEM REDE",flush=True)
    print("SQLITE INICIAL:",auditar(dbfile),flush=True)
    for i,(tipo,coletor,arquivo) in enumerate(arquivos):
        estado,digest,n=status_arquivo(arquivo,args.dia,tipo)
        print(f"\n{tipo.upper()} | {estado} | registros: {n} | {arquivo.name}",flush=True)
        if not args.executar:
            continue
        if estado!="COMPLETO":
            # Rate pacing between endpoints only when a request is needed
            if i:
                print("PAUSA ENTRE ENDPOINTS: 4 segundos",flush=True)
                time.sleep(args.intervalo)
            chamar([args.python,coletor,"--inicio",args.dia,"--fim",args.dia,
                    "--uf","CE","--saida",arquivo,"--tamanho-pagina",50,
                    "--max-paginas",args.max_paginas,"--intervalo",args.intervalo])
            estado,digest,n=status_arquivo(arquivo,args.dia,tipo)
            if estado!="COMPLETO":
                print("CHECKPOINT PARCIAL: importacao nao realizada; retomar em outro acionamento",flush=True)
                return 2
        if importado(dbfile,digest):
            print("HASH JA IMPORTADO: ignorando importacao",flush=True)
            continue
        antes=auditar(dbfile)
        nome="gov_intelligence_pre_diario48_"+datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")+".sqlite3"
        backup(dbfile,dados/nome)
        chamar([args.python,scripts/"importar_checkpoint_sqlite.py",
                "--entrada",arquivo,"--banco",dbfile])
        depois=auditar(dbfile)
        assert depois["importacoes"]==antes["importacoes"]+1, "Numero de importacoes divergente"
        for t in ("contratacoes_detalhes","contratacoes_detalhes_versoes"):
            assert depois[t]==antes[t], "Enriquecimentos alterados"
        assert importado(dbfile,digest), "Hash nao registrado"
        print("IMPORTACAO AUDITADA:",n,"registros |",antes,"=>",depois,flush=True)
    print("\nSQLITE FINAL:",auditar(dbfile),flush=True)
    print("TEMPO TOTAL:",round(time.perf_counter()-inicio,2),"segundos",flush=True)
    print("AGENDAMENTOS: ZERO | PRODUCAO: INALTERADA",flush=True)
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except (AssertionError, ValueError, OSError, sqlite3.Error, RuntimeError, json.JSONDecodeError) as err:
        print("PARADA SEGURA:",type(err).__name__,str(err),file=sys.stderr)
        sys.exit(1)
