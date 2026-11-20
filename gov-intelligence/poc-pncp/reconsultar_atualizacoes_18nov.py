#!/usr/bin/env python3
"""POC-67: reconsulta integral e segura de atualizacoes 18/11/2026.
Conserva checkpoint anterior parcial. Tentativa nova com arquivo exclusivo.
Importa somente COMPLETO, com backup SQLite online antes de qualquer escrita.
Sem agendamento nem exclusao. Caso PNCP mude totais novamente, parada segura.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from recuperar_lote_90d import db_status,status_cp,already,make_backup,call

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    p.add_argument("--python",default=sys.executable)
    a=p.parse_args()
    base=Path(a.base);dados=base/"dados";scripts=base/"scripts"
    db=dados/"gov_intelligence_ce_poc.sqlite3"
    co=scripts/"coleta_atualizacoes_checkpoint_p50.py"
    imp=scripts/"importar_checkpoint_sqlite.py"
    if not all(x.is_file() for x in (db,co,imp)):
        raise FileNotFoundError("Banco ou scripts obrigatorios ausentes")
    prior=dados/"pncp_ce_atualizacoes_20261118_p50.json"
    if not prior.is_file():
        raise FileNotFoundError("Checkpoint parcial original nao encontrado")
    previous,_,oldn=status_cp(prior,"20261118","atualizacoes")
    print("=== GOV POC-67 — RETENTATIVA INTEGRAL 18/11 ===",flush=True)
    print("CHECKPOINT ANTERIOR PRESERVADO:",previous,oldn,prior.name,flush=True)
    if previous=="COMPLETO":
        raise RuntimeError("Checkpoint original agora completo; auditar antes de reconsultar")
    fresh=dados/("pncp_ce_atualizacoes_20261118_p50_nova_"+
                 datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")+".json")
    print("ARQUIVO NOVO:",fresh.name,flush=True)
    before=db_status(db)
    print("BANCO ANTES:",before,flush=True)
    try:
        call([a.python,co,"--inicio","20261118","--fim","20261118",
              "--uf","CE","--saida",fresh,"--max-paginas",8,
              "--intervalo",4,"--tamanho-pagina",50])
    except RuntimeError:
        print("COLETA NAO CONCLUIDA. Preservados ambos checkpoints. SQLite inalterado.",flush=True)
        return 2
    state,digest,n=status_cp(fresh,"20261118","atualizacoes")
    if state!="COMPLETO":
        print("COLETA PARCIAL:",n,"registros. SQLite inalterado.",flush=True)
        return 2
    print("NOVO CHECKPOINT COMPLETO:",n,"registros",flush=True)
    if already(db,digest):
        print("JA IMPORTADO: hash presente no SQLite. Nenhuma escrita.",flush=True)
        return 0
    make_backup(db,dados/"backups_operacionais")
    call([a.python,imp,"--entrada",fresh,"--banco",db])
    after=db_status(db)
    if after["importacoes"]!=before["importacoes"]+1 or not already(db,digest):
        raise RuntimeError("Auditoria de importacao reprovada")
    for table in ("contratacoes_detalhes","contratacoes_detalhes_versoes"):
        if after[table]!=before[table]:
            raise RuntimeError("Enriquecimento indevidamente alterado")
    print("IMPORTACAO HOMOLOGADA:",before,"=>",after,flush=True)
    print("AGENDAMENTOS: ZERO | ARQUIVOS EXCLUIDOS: ZERO",flush=True)
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception as err:
        print("PARADA SEGURA:",type(err).__name__,str(err),file=sys.stderr)
        sys.exit(1)
