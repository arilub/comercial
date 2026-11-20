#!/usr/bin/env python3
"""GOV POC-57: integrar checkpoints completos de itens a snapshot Radar V1 (offline).

Nao sobrescreve snapshot de origem, nao altera SQLite e nao consulta rede.
Nao atribui aderencia comercial; mantem NEUTRO.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ID = re.compile(r"^\d{14}-1-\d{6}/\d{4}$")
TIPOS = {"M": "MATERIAL", "S": "SERVICO"}

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def valid_checkpoint(path, ident):
    cp = read_json(path)
    if cp.get("fonte") != "PNCP-ITENS-v1" or cp.get("id") != ident:
        raise ValueError(f"Checkpoint de outra fonte ou processo: {path.name}")
    if cp.get("status") != "COMPLETO":
        raise ValueError(f"Checkpoint nao completo: {path.name}")
    itens = cp.get("itens")
    if not isinstance(itens, list):
        raise ValueError(f"Itens nao sao lista: {path.name}")
    numeros = []
    reduzidos = []
    for r in itens:
        if not isinstance(r, dict) or type(r.get("numeroItem")) is not int or r["numeroItem"] < 1:
            raise ValueError(f"Item invalido em {path.name}")
        numeros.append(r["numeroItem"])
        tipo = r.get("materialOuServico")
        # Nao converter codigos desconhecidos em material/servico presumido.
        estado = TIPOS.get(tipo, "NAO_CLASSIFICADO")
        reduzidos.append({
            "numeroItem": r["numeroItem"],
            "descricao": r.get("descricao") if isinstance(r.get("descricao"), str) else None,
            "materialOuServico": tipo,
            "naturezaPNCP": estado,
            "quantidade": r.get("quantidade") if isinstance(r.get("quantidade"), (int, float)) and type(r.get("quantidade")) is not bool else None,
            "unidadeMedida": r.get("unidadeMedida") if isinstance(r.get("unidadeMedida"), str) else None,
            "valorUnitarioEstimado": r.get("valorUnitarioEstimado") if type(r.get("valorUnitarioEstimado")) in (int, float) else None,
            "valorTotal": r.get("valorTotal") if type(r.get("valorTotal")) in (int, float) else None,
        })
    if len(set(numeros)) != len(numeros):
        raise ValueError(f"NumeroItem duplicado: {path.name}")
    cont = Counter(i["naturezaPNCP"] for i in reduzidos)
    return reduzidos, dict(cont)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True)
    p.add_argument("--saida", default=None, help="JSON enriquecido (novo arquivo)")
    args = p.parse_args()
    base = Path(args.base)
    origem = base / "dados" / "radar_v1_candidatos.json"
    destino = Path(args.saida) if args.saida else base / "dados" / "radar_v1_candidatos_itens_poc57.json"
    banco = base / "dados" / "gov_intelligence_ce_poc.sqlite3"
    pasta = base / "dados" / "itens_poc56"
    if destino.resolve() == origem.resolve():
        raise ValueError("Nao sobrescrever o snapshot original")
    if destino.resolve() == banco.resolve():
        raise ValueError("Nao sobrescrever SQLite")
    if not origem.is_file() or not banco.is_file() or not pasta.is_dir():
        raise FileNotFoundError("Snapshot, SQLite ou pasta itens_poc56 ausente")
    doc = read_json(origem)
    if doc.get("schema") != "gov-intelligence-radar-v1-poc52":
        raise ValueError("Schema do radar incompatível")
    candidatos = doc.get("candidatos")
    if not isinstance(candidatos, list):
        raise ValueError("Lista de candidatos ausente")
    enriquecidos = 0
    itens_total = 0
    globais = Counter()
    with sqlite3.connect(f"file:{banco.resolve().as_posix()}?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Falha integridade SQLite")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Falha FK SQLite")
        for d in candidatos:
            ident = d.get("id")
            if not isinstance(ident, str) or not ID.fullmatch(ident):
                raise ValueError("ID candidato invalido")
            if d.get("aderenciaComercial") != "NEUTRO":
                raise ValueError("Aderencia nao neutra no snapshot original")
            d["statusEnriquecimentoItens"] = "NAO_COLETADO"
            d["resumoItensPNCP"] = None
            d["itensPNCP"] = []
            cp = pasta / ("pncp_itens_" + ident.replace("/", "_") + ".json")
            if not cp.is_file():
                continue
            row = db.execute("SELECT uf FROM contratacoes WHERE id=?", (ident,)).fetchone()
            if row != ("CE",):
                raise ValueError("Item vinculado a ID nao cadastrado em CE")
            itens, cont = valid_checkpoint(cp, ident)
            d["statusEnriquecimentoItens"] = "COMPLETO"
            d["resumoItensPNCP"] = {"totalItens": len(itens),
                "materiais": cont.get("MATERIAL", 0),
                "servicos": cont.get("SERVICO", 0),
                "naoClassificados": cont.get("NAO_CLASSIFICADO", 0)}
            d["itensPNCP"] = itens
            enriquecidos += 1
            itens_total += len(itens)
            globais.update(cont)
            print("PROCESSO:", ident, "| ITENS:", len(itens),
                  "| M:", cont.get("MATERIAL", 0),
                  "| S:", cont.get("SERVICO", 0),
                  "| INDEFINIDOS:", cont.get("NAO_CLASSIFICADO", 0), flush=True)
    doc["schema"] = "gov-intelligence-radar-v1-poc57"
    doc["enriquecidoEmUTC"] = datetime.now(timezone.utc).isoformat()
    doc["enriquecimento"] = {
        "fonte": "Checkpoints oficiais PNCP-ITENS-v1 previamente coletados",
        "processosComItensCompletos": enriquecidos,
        "processosSemItensColetados": len(candidatos) - enriquecidos,
        "itensTotais": itens_total,
        "tipos": dict(globais),
        "aderencia": "NEUTRO",
        "observacao": "Classificacao M/S informada pelo PNCP. Itens nao comprovam aderencia comercial."
    }
    if len({d["id"] for d in candidatos}) != len(candidatos):
        raise ValueError("IDs duplicados")
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, destino)
    print("\n=== GOV POC-57 — CONSOLIDACAO ITENS ===")
    print("CANDIDATOS:", len(candidatos))
    print("PROCESSOS ENRIQUECIDOS:", enriquecidos)
    print("ITENS OFICIAIS:", itens_total)
    print("TIPOS OFICIAIS:", dict(globais))
    print("ARQUIVO:", destino)
    print("ORIGINAL PRESERVADO:", origem)
    print("SQLite somente leitura | API zero | agendamentos zero")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError, sqlite3.Error, TypeError) as err:
        print("PARADA SEGURA:", type(err).__name__, str(err), file=sys.stderr)
        sys.exit(1)
