#!/usr/bin/env python3
"""POC-76.1 — auditoria offline da seleção histórica, somente leitura."""
import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import date, datetime
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    a = p.parse_args()
    banco = Path(a.base) / "dados" / "gov_intelligence_ce_poc.sqlite3"
    if not banco.is_file():
        raise FileNotFoundError(str(banco))
    with sqlite3.connect("file:" + banco.resolve().as_posix() + "?mode=ro", uri=True) as db:
        total = db.execute("SELECT count(*) FROM contratacoes").fetchone()[0]
        sample = db.execute("SELECT id, data_publicacao, data_atualizacao, payload_json FROM contratacoes ORDER BY data_publicacao DESC LIMIT 5").fetchall()
        ids = db.execute("SELECT id FROM contratacoes").fetchall()
        recent = db.execute("SELECT id, data_publicacao, payload_json FROM contratacoes ORDER BY data_publicacao DESC LIMIT 5000").fetchall()
    padrao_atual = re.compile(r"\d{14}-1-\d{4}-\d+")
    padrao_alternativo = re.compile(r"\d{14}-\d+-\d{4}-\d+")
    print("=== GOV POC-76.1 — DIAGNOSTICO HISTORICO ===")
    print("PREGÕES NO SQLITE:", total)
    print("IDS COMPATIVEIS COM PADRAO POC76:", sum(bool(padrao_atual.fullmatch(x[0])) for x in ids))
    print("IDS COMPATIVEIS COM PADRAO ALTERNATIVO:", sum(bool(padrao_alternativo.fullmatch(x[0])) for x in ids))
    print("AMOSTRA DE CINCO REGISTROS:")
    for i, (ident, pub, upd, raw) in enumerate(sample, 1):
        doc = json.loads(raw)
        print("\nREGISTRO:", i)
        print(" ID:", ident)
        print(" DATA PUBLICACAO:", pub)
        print(" DATA ATUALIZACAO:", upd)
        print(" ID PADRAO POC76:", bool(padrao_atual.fullmatch(ident)))
        print(" SITUACAO:", doc.get("situacaoCompraNome"))
        print(" ENCERRAMENTO:", doc.get("dataEncerramentoProposta"))
        print(" CAMPOS:", ", ".join(sorted(doc)))
    motivos = Counter()
    hoje = date.today().isoformat()
    aptos = []
    for ident, pub, raw in recent:
        if not padrao_atual.fullmatch(ident):
            motivos["id_incompativel"] += 1
            continue
        doc = json.loads(raw)
        fim = str(doc.get("dataEncerramentoProposta") or "")
        if fim and fim[:10] >= hoje:
            motivos["encerramento_futuro"] += 1
            continue
        if not fim and str(pub or "")[:10] >= hoje:
            motivos["sem_encerramento_e_publicacao_recente"] += 1
            continue
        aptos.append((ident, doc.get("situacaoCompraNome"), fim))
    print("\nTRIAGEM POC-76 NOS 5000 MAIS RECENTES:")
    print("MOTIVOS DE EXCLUSAO:", dict(motivos))
    print("ELEGIVEIS:", len(aptos))
    for ident, situacao, fim in aptos[:5]:
        print(" EXEMPLO:", ident, "| SITUACAO:", situacao, "| ENCERRAMENTO:", fim)
    print("\nSQLITE: SOMENTE LEITURA | API: ZERO | AGENDAMENTOS: ZERO")
if __name__ == "__main__":
    main()
