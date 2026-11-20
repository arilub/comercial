#!/usr/bin/env python3
"""POC-77: inspecao local dos resultados retornados na POC76 (somente leitura).
Apresenta campos reais e valores de resultado para homologacao do modelo.
Nao acessa API, nao modifica banco, nem snapshot e nao instala agendamentos.
"""
import argparse
import json
from pathlib import Path

def brief(value,limit=350):
    t=json.dumps(value,ensure_ascii=False,default=str)
    return t if len(t)<=limit else t[:limit]+"... [truncado]"

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    args=p.parse_args()
    path=Path(args.base)/"dados"/"poc76_pesquisa_resultados_historicos.json"
    doc=json.loads(path.read_text(encoding="utf-8-sig"))
    if doc.get("schema")!="gov-poc76-resultado-exploratorio":
        raise ValueError("Schema POC76 inesperado")
    print("=== GOV POC-77 - CAMPOS REAIS DE RESULTADOS PNCP ===")
    print("GERADO:",doc.get("geradoEmUTC"),"| RESULTADO:",doc.get("resultadoIdentificado"))
    processos=doc.get("processos",[])
    if not isinstance(processos,list):raise ValueError("Processos invalidos")
    for proc in processos[:5]:
        print("\nPROCESSO:",proc.get("id"))
        print("ORGAO:",proc.get("orgao"),"| MUNICIPIO:",proc.get("municipio"))
        print("SITUACAO:",proc.get("situacaoCompraNome"))
        for item in (proc.get("itensInspecionados") or [])[:5]:
            print("\n ITEM",item.get("numeroItem"),"HTTP",item.get("httpResultados"))
            print(" DESCRICAO:",str(item.get("descricao"))[:400])
            print(" QUANTIDADE:",item.get("quantidade"),"UNIDADE:",item.get("unidadeMedida"))
            print(" VALOR UNITARIO ESTIMADO:",item.get("valorUnitarioEstimado"))
            print(" CAMPOS DISPONIVEIS:",", ".join(item.get("camposResultado") or []))
            for n,row in enumerate(item.get("resultados") or [],1):
                print("  RESULTADO",n,brief(row,1600))
    print("\nPOC77: SOMENTE LEITURA | BANCO E AGENDADOR INALTERADOS")

if __name__=="__main__":
    main()
