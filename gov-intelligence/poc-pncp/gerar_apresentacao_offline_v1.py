#!/usr/bin/env python3
"""GOV POC-64: gera HTML unico de apresentacao com snapshot oficial incorporado.

Somente leitura de JSON/template; grava apenas HTML de saida.
Sem APIs, sem alterar SQLite, sem agendamentos.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

MARCADOR="<!-- GOV_RADAR_EMBEDDED_JSON_V14 -->"
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    p.add_argument("--saida",default=None)
    a=p.parse_args()
    base=Path(a.base)
    template=base/"radar_v1_local.html"
    fonte=base/"dados"/"radar_v1_candidatos_itens_poc57.json"
    saida=Path(a.saida) if a.saida else base/"GOV_INTELLIGENCE_APRESENTACAO_V1.html"
    if not template.is_file() or not fonte.is_file():
        raise FileNotFoundError("HTML V1.4 ou JSON enriquecido nao encontrado")
    if saida.resolve() in (template.resolve(),fonte.resolve()):
        raise ValueError("Saida nao pode sobrescrever entrada")
    obj=json.loads(fonte.read_text(encoding="utf-8-sig"))
    if obj.get("schema")!="gov-intelligence-radar-v1-poc57":
        raise ValueError("Schema enriquecido esperado: poc57")
    rows=obj.get("candidatos")
    if not isinstance(rows,list) or not isinstance(obj.get("contratacoesBase"),int) or obj["contratacoesBase"]<=0:
        raise ValueError("Snapshot invalido")
    if any(d.get("aderenciaComercial")!="NEUTRO" for d in rows):
        raise ValueError("Aderencia nao neutra: revisar antes da apresentacao")
    completos=[d for d in rows if d.get("statusEnriquecimentoItens")=="COMPLETO"]
    itens=sum(len(d.get("itensPNCP") or []) for d in completos)
    if len(completos)!=obj.get("enriquecimento",{}).get("processosComItensCompletos") or itens!=obj.get("enriquecimento",{}).get("itensTotais"):
        raise ValueError("Totais de itens inconsistentes")
    if len({d.get("id") for d in rows})!=len(rows):
        raise ValueError("IDs repetidos")
    html=template.read_text(encoding="utf-8-sig")
    if html.count(MARCADOR)!=1 or "function carregarDados(d,nome)" not in html:
        raise ValueError("Template V1.4 nao encontrado")
    blob=json.dumps(obj,ensure_ascii=False,separators=(",",":"),allow_nan=False)
    blob=re.sub(r"</",r"<\\/",blob)
    # O script JSON e passivo e usado apenas como texto.
    insercao='<script id="embeddedData" type="application/json">'+blob+"</script>"
    resultado=html.replace(MARCADOR,insercao)
    saida.parent.mkdir(parents=True,exist_ok=True)
    tmp=saida.with_name(saida.name+".tmp")
    with tmp.open("w",encoding="utf-8") as f:
        f.write(resultado)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp,saida)
    print("=== GOV POC-64 — APRESENTACAO OFFLINE ===")
    print("PREGÕES NA BASE:",obj["contratacoesBase"])
    print("CANDIDATOS:",len(rows))
    print("PREGÕES COM ITENS:",len(completos))
    print("ITENS OFICIAIS:",itens)
    print("SNAPSHOT:",obj.get("geradoEm"))
    print("ARQUIVO:",saida)
    print("MODO: 1 HTML offline, classificacao NEUTRO, sem rede, SQLite inalterado")
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except (OSError,ValueError,TypeError,RuntimeError) as exc:
        print("PARADA SEGURA:",str(exc),file=sys.stderr)
        sys.exit(1)
