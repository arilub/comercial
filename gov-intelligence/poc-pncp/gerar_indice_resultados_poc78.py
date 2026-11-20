#!/usr/bin/env python3
"""POC-78: indice historico de produtos/orgaos/fornecedores a partir da POC-76.

Nao usa API, nem modifica o SQLite, agendador ou painel.
Distingue resultados informados dos cancelados. Mantem historico integral
por numero de resultado; nao chama participantes de perdedores.
Nao agrupa descricoes iguais como produtos equivalentes.
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone

def num(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool)

def output_json(path,obj):
    tmp=path.with_suffix(path.suffix+".tmp")
    try:
        with tmp.open("w",encoding="utf-8") as f:
            json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",required=True)
    a=p.parse_args()
    base=Path(a.base)
    src=base/"dados"/"poc76_pesquisa_resultados_historicos.json"
    obj=json.loads(src.read_text(encoding="utf-8-sig"))
    if obj.get("schema")!="gov-poc76-resultado-exploratorio":
        raise ValueError("Schema de entrada inesperado")
    records=[]
    for proc in obj.get("processos",[]):
        pid=proc.get("id")
        if not isinstance(pid,str) or not pid:raise ValueError("Processo sem ID")
        for item in proc.get("itensInspecionados",[]):
            n=item.get("numeroItem")
            if not isinstance(n,int) or n<1:raise ValueError("Numero de item invalido")
            results=item.get("resultados") or []
            # Fonte POC76 contem apenas os primeiros 10 resultados: nunca supor completude.
            for result in results:
                if not isinstance(result,dict):raise ValueError("Resultado nao objeto")
                if result.get("numeroControlePNCPCompra")!=pid or result.get("numeroItem")!=n:
                    raise ValueError("Vinculo de resultado ao item divergente")
                status=str(result.get("situacaoCompraItemResultadoNome") or "").strip()
                canceled=(status.casefold()=="cancelado" or result.get("dataCancelamento") is not None)
                informed=(status.casefold()=="informado" and not canceled)
                total=result.get("valorTotalHomologado")
                unit=result.get("valorUnitarioHomologado")
                qty=result.get("quantidadeHomologada")
                seq=result.get("sequencialResultado")
                if not isinstance(seq,int):raise ValueError("Sequencial de resultado ausente")
                if num(total) and num(unit) and num(qty):
                    expected=round(float(unit)*float(qty),2)
                    # Valores podem variar por arredondamento; alerta, nao inventar ajuste.
                    diverge=abs(expected-float(total))>max(0.05,abs(float(total))*0.00001)
                else:diverge=None
                records.append({
                    "processoPNCP":pid,"orgao":proc.get("orgao"),"municipio":proc.get("municipio"),
                    "item":n,"descricaoOficial":item.get("descricao"),"unidade":item.get("unidadeMedida"),
                    "quantidadeEstimada":item.get("quantidade"),"valorUnitarioEstimado":item.get("valorUnitarioEstimado"),
                    "sequencialResultado":seq,"statusOficial":status,
                    "resultadoInformadoNaoCancelado":informed,
                    "resultadoCancelado":canceled,
                    "dataResultado":result.get("dataResultado"),
                    "dataCancelamento":result.get("dataCancelamento"),
                    "dataAtualizacao":result.get("dataAtualizacao"),
                    "cnpjCpfFornecedor":result.get("niFornecedor"),
                    "tipoPessoa":result.get("tipoPessoa"),
                    "fornecedor":result.get("nomeRazaoSocialFornecedor"),
                    "quantidadeHomologada":qty,
                    "valorUnitarioHomologado":unit,
                    "valorTotalHomologado":total,
                    "conferenciaMultiplicacaoDivergente":diverge,
                    "fonte":item.get("urlResultados")
                })
    keys=[(r["processoPNCP"],r["item"],r["sequencialResultado"]) for r in records]
    if len(keys)!=len(set(keys)):raise ValueError("Resultado duplicado no indice")
    informed=[r for r in records if r["resultadoInformadoNaoCancelado"]]
    canceled=[r for r in records if r["resultadoCancelado"]]
    # Evitar somar indiscriminadamente mais de um resultado ativo por item.
    active_groups=Counter((r["processoPNCP"],r["item"]) for r in informed)
    ambiguous=[{"processoPNCP":k[0],"item":k[1],"resultadosAtivos":v} for k,v in active_groups.items() if v>1]
    data={
        "schema":"gov-poc78-indice-resultados-amostra",
        "geradoEmUTC":datetime.now(timezone.utc).isoformat(),
        "fonteArquivo":src.name,
        "escopo":"Amostra exploratoria POC76: nao corresponde a todos os resultados do processo",
        "regras":{"cancelados":"Preservados como historico, excluidos do conjunto informado nao cancelado",
                  "informados":"Registros de resultado informado sem cancelamento conhecido, nao comprovacao de contrato executado",
                  "lances":"Nao inferidos da API de resultados",
                  "equivalencia":"Nao inferida de descricao textual igual",
                  "totais":"Nao agregar automaticamente resultados de um mesmo item"},
        "resumo":{"resultadosTotal":len(records),"informadosNaoCancelados":len(informed),
                  "cancelados":len(canceled),"outros":len(records)-len(informed)-len(canceled),
                  "itensComVariosResultadosInformados":len(ambiguous)},
        "gruposAmbiguos":ambiguous,
        "registros":records
    }
    out=base/"dados"/"poc78_indice_historico_amostra.json"
    output_json(out,data)
    print("=== GOV POC-78 — INDICE HISTORICO DE RESULTADOS ===")
    print("RESULTADOS TOTAIS:",len(records))
    print("INFORMADOS NAO CANCELADOS:",len(informed))
    print("CANCELADOS:",len(canceled))
    print("OUTROS:",len(records)-len(informed)-len(canceled))
    print("ITENS COM MULTIPLOS RESULTADOS ATIVOS:",len(ambiguous))
    for r in records[:20]:
        print("ITEM:",r["item"],"|",str(r["descricaoOficial"])[:45],
              "|",r["statusOficial"],"| FORNECEDOR:",r["fornecedor"],
              "| UNITARIO:",r["valorUnitarioHomologado"],
              "| DATA:",r["dataResultado"])
        if r["conferenciaMultiplicacaoDivergente"]:
            print("  ALERTA: VALOR TOTAL DIVERGENTE DA MULTIPLICACAO")
    print("INDICE:",out)
    print("ALCANCE: somente amostra consultada, nao historico consolidado")
    print("SQLITE/AGENDADOR/PAINEL: INALTERADOS")
    return 0
if __name__=="__main__":
    try:sys.exit(main())
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as e:
        print("PARADA SEGURA:",type(e).__name__,str(e),file=sys.stderr)
        sys.exit(1)
