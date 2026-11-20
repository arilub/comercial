#!/usr/bin/env python3
"""GOV POC-65: auditoria offline da janela movel de 90 dias.

Sem alteracoes no SQLite, sem coleta e sem agenda. A cobertura significa:
checkpoint COMPLETO, com faixa de datas identificavel, e hash registrado
como importado. Datas de atualizacao nao equivalem a datas de publicacao.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, date
from pathlib import Path

def intervalo(dias):
    if not dias:
        return "nenhum"
    d = sorted(dias)
    out=[]; ini=ant=d[0]
    for atual in d[1:]:
        if atual != ant + timedelta(days=1):
            out.append((ini,ant));ini=atual
        ant=atual
    out.append((ini,ant))
    return "; ".join(f"{a:%d/%m/%Y}"+(f" a {b:%d/%m/%Y}" if a!=b else "") for a,b in out)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    p.add_argument("--fim",default=None,help="YYYYMMDD, padrao data local do servidor")
    a=p.parse_args()
    base=Path(a.base); dados=base/"dados"; banco=dados/"gov_intelligence_ce_poc.sqlite3"
    fim=datetime.strptime(a.fim,"%Y%m%d").date() if a.fim else date.today()
    inicio=fim-timedelta(days=89)
    universo=set(inicio+timedelta(days=i) for i in range(90))
    if not banco.is_file():raise FileNotFoundError("SQLite ausente")
    with sqlite3.connect(f"file:{banco.resolve().as_posix()}?mode=ro",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise RuntimeError("integridade SQLite reprovada")
        colunas=[row[1] for row in db.execute("PRAGMA table_info(importacoes)")]
        if "arquivo_sha256" not in colunas:
            raise RuntimeError("schema de importacoes nao reconhecido")
        importados={r[0] for r in db.execute("SELECT arquivo_sha256 FROM importacoes")}
        qtd_base=db.execute("SELECT COUNT(*) FROM contratacoes").fetchone()[0]
        versoes=db.execute("SELECT COUNT(*) FROM versoes").fetchone()[0]
    cob={x:set() for x in ("publicacao","atualizacao")}
    completos_sem_importar={x:set() for x in cob}
    arquivos=Counter()
    status=Counter()
    nao_reconhecidos=[]
    for path in sorted(dados.glob("pncp*.json")):
        try:
            bruto=path.read_bytes();doc=json.loads(bruto.decode("utf-8-sig"))
            if not isinstance(doc, dict):
                nao_reconhecidos.append(path.name + " (JSON raiz nao e objeto)")
                continue
            cfg=doc.get("config") or {}
            if not isinstance(cfg, dict):
                nao_reconhecidos.append(path.name + " (config nao e objeto)")
                continue
            first=cfg.get("inicio");last=cfg.get("fim")
            if not (isinstance(first,str) and isinstance(last,str) and
                    len(first)==8 and len(last)==8):
                nao_reconhecidos.append(path.name);continue
            a0=datetime.strptime(first,"%Y%m%d").date()
            b0=datetime.strptime(last,"%Y%m%d").date()
            if a0>b0 or cfg.get("uf")!="CE" or cfg.get("modalidade")!=6:
                nao_reconhecidos.append(path.name);continue
            if cfg.get("municipio") is not None:
                continue
            tipo="atualizacao" if cfg.get("tipoConsulta")=="atualizacao" else "publicacao"
            if cfg.get("tipoConsulta") not in (None,"atualizacao"):
                nao_reconhecidos.append(path.name);continue
            dias={a0+timedelta(days=n) for n in range((b0-a0).days+1)} & universo
            if not dias:continue
            arquivos[tipo]+=1
            estado=doc.get("status","DESCONHECIDO")
            status[tipo+"_"+estado]+=1
            if estado!="COMPLETO":continue
            regs=doc.get("registros")
            if not isinstance(regs,list) or len(regs)!=doc.get("totalRegistrosInformado"):
                status[tipo+"_INCONSISTENTE"]+=1;continue
            ids=[x.get("numeroControlePNCP") for x in regs if isinstance(x,dict)]
            if len(ids)!=len(regs) or len(ids)!=len(set(ids)) or not all(ids):
                status[tipo+"_INCONSISTENTE"]+=1;continue
            digest=hashlib.sha256(bruto).hexdigest()
            (cob if digest in importados else completos_sem_importar)[tipo].update(dias)
        except (OSError,TypeError,ValueError,json.JSONDecodeError) as e:
            nao_reconhecidos.append(path.name+" ("+str(e)[:60]+")")
    print("=== GOV POC-65 — AUDITORIA 90 DIAS ===")
    print("JANELA:",inicio.isoformat(),"ate",fim.isoformat(),"(90 dias inclusivos)")
    print("BASE SQLITE:",qtd_base,"contratacoes |",versoes,"versoes")
    for tipo in ("publicacao","atualizacao"):
        faltantes=universo-cob[tipo]
        completas=cob[tipo]
        pendentes_importar=completos_sem_importar[tipo]-completas
        print("\nTIPO:",tipo.upper())
        print("DIAS COM CHECKPOINT COMPLETO E IMPORTADO:",len(completas),"/90")
        print("DIAS SEM COBERTURA COMPROVADA:",len(faltantes))
        print("LACUNAS:",intervalo(faltantes))
        print("DIAS COM CHECKPOINT COMPLETO MAS SEM IMPORTACAO:",len(pendentes_importar))
        if pendentes_importar:print("PENDENTE IMPORTACAO:",intervalo(pendentes_importar))
        print("ARQUIVOS SOBREPOSTOS NA JANELA:",arquivos[tipo])
    print("\nSTATUS DE CHECKPOINTS:",dict(status))
    if nao_reconhecidos:
        print("ARQUIVOS PNCP NAO RECONHECIDOS:",len(nao_reconhecidos))
        for x in nao_reconhecidos[:15]:print(" -",x)
    print("\nIMPORTANTE: checkpoint completo nao significa que dados do dia corrente estao finalizados.")
    print("DIA CORRENTE: exige coletor provisório com revisita; nao reutilizar checkpoint completo ate o encerramento.")
    print("SQLITE: SOMENTE LEITURA | API: ZERO | NENHUM AGENDAMENTO")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except (ValueError,RuntimeError,OSError,sqlite3.Error) as exc:
        print("PARADA SEGURA:",type(exc).__name__,str(exc),file=sys.stderr);sys.exit(1)
