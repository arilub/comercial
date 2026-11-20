#!/usr/bin/env python3
"""GOV POC-52: snapshot JSON OFFLINE do Radar V1 a partir de SQLite PNCP CE.

Nao consulta rede e nao altera o SQLite. Nao e painel de producao.
Aderencia permanece NEUTRO; sigilo nao e inferido pelo valor estimado.
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

FUSO_CE = timezone(timedelta(hours=-3))
SITUACAO_CANDIDATA = "Divulgada no PNCP"

def data_dt(valor):
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z","+00:00"))
    except (ValueError,TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=FUSO_CE)
    return dt

def valor_resumo(d):
    v = d.get("valorTotalEstimado")
    if type(v) in (int,float) and v > 0:
        return {"estado":"VALOR_POSITIVO_INFORMADO","valor":v}
    if v == 0:
        return {"estado":"ZERO_SIGILO_NAO_VERIFICADO","valor":None}
    return {"estado":"NAO_INFORMADO","valor":None}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--banco",required=True)
    ap.add_argument("--saida",required=True)
    args=ap.parse_args()
    banco,saida=Path(args.banco),Path(args.saida)
    if not banco.is_file():
        ap.error("Banco inexistente")
    if saida.resolve()==banco.resolve():
        ap.error("Saida nao pode sobrescrever SQLite")
    agora=datetime.now(FUSO_CE)
    contagens=Counter()
    candidatos=[]
    with sqlite3.connect(f"file:{banco.resolve().as_posix()}?mode=ro",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise RuntimeError("Integridade reprovada")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Chaves estrangeiras invalidas")
        total=db.execute("SELECT COUNT(*) FROM contratacoes").fetchone()[0]
        for ident,texto in db.execute("SELECT id,payload_json FROM contratacoes"):
            d=json.loads(texto)
            if d.get("numeroControlePNCP")!=ident:
                raise RuntimeError("ID PNCP divergente")
            if (d.get("unidadeOrgao") or {}).get("ufSigla")!="CE":
                raise RuntimeError("UF fora da abrangencia")
            fim=data_dt(d.get("dataEncerramentoProposta"))
            if fim is None:
                contagens["PRAZO_AUSENTE_OU_INVALIDO"]+=1
                continue
            if fim<=agora:
                contagens["PRAZO_ENCERRADO"]+=1
                continue
            situacao=str(d.get("situacaoCompraNome") or "NAO_INFORMADA")
            contagens["PRAZO_FUTURO"]+=1
            contagens["FUTURO_"+situacao]+=1
            if situacao!=SITUACAO_CANDIDATA:
                continue
            org=d.get("orgaoEntidade") or {}
            unidade=d.get("unidadeOrgao") or {}
            abertura=data_dt(d.get("dataAberturaProposta"))
            ano=d.get("anoCompra")
            seq=d.get("sequencialCompra")
            cnpj=org.get("cnpj") if isinstance(org,dict) else None
            # Link oficial so quando a chave puder ser reconstruida com dados validados.
            url=f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (
                isinstance(cnpj,str) and cnpj.isdigit() and len(cnpj)==14
                and isinstance(ano,int) and isinstance(seq,int)
            ) else None
            candidatos.append({
                "id":ident,
                "anoCompra":ano,
                "numeroCompra":d.get("numeroCompra"),
                "objeto":d.get("objetoCompra"),
                "orgao":org.get("razaoSocial") if isinstance(org,dict) else None,
                "cnpjOrgao":cnpj,
                "municipio":unidade.get("municipioNome") if isinstance(unidade,dict) else None,
                "uf":"CE",
                "situacaoPNCP":situacao,
                "dataPublicacao":d.get("dataPublicacaoPncp"),
                "aberturaProposta":abertura.isoformat() if abertura else None,
                "encerramentoProposta":fim.isoformat(),
                "faseTemporal":"ABERTURA_FUTURA" if abertura and abertura>agora else (
                    "PRAZO_EM_CURSO" if abertura else "ABERTURA_INDETERMINADA"),
                "valorEstimado":valor_resumo(d),
                "valorHomologadoInformado":d.get("valorTotalHomologado"),
                "linkSistemaOrigem":d.get("linkSistemaOrigem"),
                "linkPNCP":url,
                "aderenciaComercial":"NEUTRO",
                "classificacaoItens":"NAO_VERIFICADA",
                "orcamentoSigiloso":"NAO_VERIFICADO",
                "statusRadar":"CANDIDATO_PRELIMINAR"
            })
    candidatos.sort(key=lambda x:(x["encerramentoProposta"],x["id"]))
    assert len({x["id"] for x in candidatos})==len(candidatos), "IDs repetidos"
    if len(candidatos)!=contagens["FUTURO_"+SITUACAO_CANDIDATA]:
        raise RuntimeError("Contagem de candidatos divergente")
    documento={
        "schema":"gov-intelligence-radar-v1-poc52",
        "geradoEm":agora.isoformat(),
        "timezone":"America/Fortaleza (UTC-03)",
        "fonte":"SQLite local com snapshots oficiais PNCP",
        "abrangencia":"Comprador CE, modalidade 6 (pregao)",
        "carater":"COBERTURA PARCIAL; classificacao comercial nao homologada",
        "nota":"Candidato preliminar nao representa edital vigente confirmado nem aderencia ARILUB. Valores zero nao comprovam sigilo.",
        "contratacoesBase":total,
        "contagens":dict(contagens),
        "candidatos":candidatos
    }
    saida.parent.mkdir(parents=True,exist_ok=True)
    temporario=saida.with_name(saida.name+".tmp")
    with temporario.open("w",encoding="utf-8") as f:
        json.dump(documento,f,indent=2,ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporario,saida)
    print("=== GOV POC-52 - SNAPSHOT RADAR V1 ===")
    print("DATA:",agora.isoformat())
    print("BASE:",total)
    print("PRAZO FUTURO:",contagens["PRAZO_FUTURO"])
    print("CANDIDATOS PRELIMINARES:",len(candidatos))
    print("VALOR ZERO / SIGILO NAO VERIFICADO:",sum(x["valorEstimado"]["estado"]=="ZERO_SIGILO_NAO_VERIFICADO" for x in candidatos))
    print("ARQUIVO:",saida)
    print("SQLite: SOMENTE LEITURA | API: ZERO | AGENDAMENTOS: ZERO")
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except (ValueError,OSError,sqlite3.Error,RuntimeError,TypeError) as e:
        print("PARADA SEGURA:",str(e),file=sys.stderr)
        sys.exit(1)
