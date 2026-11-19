#!/usr/bin/env python3
"""POC-06: gerar fila histórica CE a partir de checkpoint local PNCP, sem rede.

Fatos PNCP ficam em dados locais; saída é planejamento técnico, não
classificação de aderência comercial. Não reescreve arquivo de origem.
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)

def positive(value):
    if value is None or value == "":
        return False
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False

def main():
    parser = argparse.ArgumentParser(description="Planejamento offline da coleta PNCP CE")
    parser.add_argument("--entrada", required=True)
    parser.add_argument("--saida", required=True)
    args = parser.parse_args()
    entrada, saida = Path(args.entrada), Path(args.saida)
    if entrada.resolve() == saida.resolve():
        parser.error("Entrada e saida precisam ser arquivos distintos")

    try:
        doc = json.loads(entrada.read_text(encoding="utf-8-sig"))
        if doc.get("status") != "COMPLETO":
            raise ValueError("Somente checkpoints COMPLETOS são aceitos")
        entries = doc["registros"]
        count = int(doc["totalRegistrosInformado"])
        if not isinstance(entries, list) or len(entries) != count:
            raise ValueError("Contagem de registros inconsistente")
        ids = [record["numeroControlePNCP"] for record in entries]
        if len(ids) != len(set(ids)):
            raise ValueError("Existem identificadores repetidos")
        scope = doc["config"]
        if scope.get("uf") != "CE":
            raise ValueError("A POC está configurada somente para o Ceará")
        fila = []
        for record in entries:
            estimated = record.get("valorTotalEstimado")
            homologated = record.get("valorTotalHomologado")
            has_homolog = positive(homologated)
            situacao = record.get("situacaoCompraNome") or "NAO_INFORMADA"
            fila.append({
                "numeroControlePNCP": record["numeroControlePNCP"],
                "uf": record.get("unidadeOrgao", {}).get("ufSigla"),
                "codigoMunicipioIbge": record.get("unidadeOrgao", {}).get("codigoIbge"),
                "municipio": record.get("unidadeOrgao", {}).get("municipioNome"),
                "orgaoCnpj": record.get("orgaoEntidade", {}).get("cnpj"),
                "situacaoCompraNome": situacao,
                "valorTotalEstimado": estimated,
                "valorTotalHomologado": homologated,
                "dataAtualizacaoGlobal": record.get("dataAtualizacaoGlobal"),
                "prioridadeColeta": "P1_HOMOLOGADO_POSITIVO" if has_homolog else "P2_VERIFICAR_RESULTADOS",
                "aderencia": "NEUTRO",
                "statusItens": "NAO_CONSULTADO_NESTA_FILA",
                "statusResultados": "NAO_CONSULTADO_NESTA_FILA",
            })
        fila.sort(key=lambda row: (row["prioridadeColeta"], row["numeroControlePNCP"]))
        groups = Counter(row["prioridadeColeta"] for row in fila)
        manifest = {
            "versao":1, "origem":"PNCP API oficial / checkpoint local",
            "geradoEmUTC":datetime.now(timezone.utc).isoformat(),
            "filtrosOrigem":scope,
            "totalPregoes":len(fila), "prioridades":dict(groups),
            "regra":"Prioridade técnica de coleta; não é aderência comercial",
            "aviso":"Valor homologado nulo/zero não demonstra ausência de resultado",
            "execucao":"Somente planejamento local; nenhuma chamada à API",
            "fila":fila,
        }
        atomic_json(saida, manifest)
        print("=== PLANO HISTORICO CE ===")
        print("Pregoes:", len(fila))
        print("Prioridade 1 - valor homologado positivo:",groups["P1_HOMOLOGADO_POSITIVO"])
        print("Prioridade 2 - verificar resultados:",groups["P2_VERIFICAR_RESULTADOS"])
        print("Aderencia comercial: NEUTRO em 100%")
        print("Fila salva:", saida)
        return 0
    except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as err:
        print("ERRO DE INTEGRIDADE:", err, file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
