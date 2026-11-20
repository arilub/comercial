#!/usr/bin/env python3
"""POC-18: testes isolados do importador em copia SQLite; banco original somente leitura."""
import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ID = "07954480000179-1-025554/2026"
TABLES = ("contratacoes", "versoes", "importacoes")

def readcounts(db):
    return {t: db.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in TABLES}

def status(db):
    current = db.execute(
        "SELECT codigo_sigilo,data_atualizacao_fonte FROM contratacoes_detalhes WHERE id=?", (ID,)
    ).fetchone()
    return (current, db.execute("SELECT COUNT(*) FROM contratacoes_detalhes_versoes WHERE id=?", (ID,)).fetchone()[0])

def run(py, script, bank, f, apply=True):
    cmd = [py, str(script), "--banco", str(bank), "--arquivo", str(f)]
    if apply:
        cmd.append("--aplicar")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
    print("  retorno:", result.returncode)
    for line in (result.stdout + "\n" + result.stderr).splitlines():
        if line.startswith(("Estado:", "Versoes inseridas:", "Atuais inseridos/atualizados:", "ERRO:", "MODO:")):
            print(" ", line)
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--importador", required=True)
    args = ap.parse_args()
    source, importer = Path(args.banco), Path(args.importador)
    if not source.is_file() or not importer.is_file():
        raise ValueError("Banco ou importador nao localizado")

    with sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True) as original:
        initial = readcounts(original)
        if initial["contratacoes"] != 540:
            raise ValueError("Quantidade original inesperada")
        if original.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Integridade inicial reprovada")
        seeded = original.execute(
            "SELECT payload_json FROM contratacoes_detalhes WHERE id=?", (ID,)
        ).fetchone()
        if not seeded:
            raise ValueError("Primeiro enriquecimento nao encontrado")
        payload = json.loads(seeded[0])

        with tempfile.TemporaryDirectory(prefix="gov_poc18_") as td:
            work = Path(td)
            clone = work / "copia_isolada.sqlite3"
            with sqlite3.connect(clone) as copy:
                original.backup(copy)
            print("Copia isolada:", clone.name, "| Banco original somente leitura")

            def fixture(name, codigo, data):
                obj = dict(payload)
                obj["orcamentoSigilosoCodigo"] = codigo
                obj["dataAtualizacaoGlobal"] = data
                f = work / (name + ".json")
                f.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
                return f

            same = work / "identico.json"
            same.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            base_date = payload["dataAtualizacaoGlobal"]
            with sqlite3.connect(clone) as db:
                base_status = status(db)
            print("BASE:", base_status)

            print("\nCASO 1: IDENTICO (repeticao)")
            r = run(sys.executable, importer, clone, same)
            assert r.returncode == 0 and "Estado: IDENTICO" in r.stdout
            with sqlite3.connect(clone) as db:
                assert status(db) == base_status

            print("\nCASO 2: CONFLITO MESMA DATA")
            conflict = fixture("conflito", 2, base_date)
            r = run(sys.executable, importer, clone, conflict)
            assert r.returncode == 0 and "Estado: CONFLITO_MESMA_DATA" in r.stdout
            with sqlite3.connect(clone) as db:
                assert status(db) == (base_status[0], base_status[1] + 1)

            print("\nCASO 3: MAIS RECENTE")
            future = fixture("recente", 1, "2026-11-10T10:00:00")
            r = run(sys.executable, importer, clone, future)
            assert r.returncode == 0 and "Estado: MAIS_RECENTE" in r.stdout
            with sqlite3.connect(clone) as db:
                assert status(db) == ((1, "2026-11-10T10:00:00"), base_status[1] + 2)

            print("\nCASO 4: OBSOLETO, SEM TROCAR REGISTRO ATUAL")
            older = fixture("obsoleto", 2, "2026-11-09T20:00:00")
            r = run(sys.executable, importer, clone, older)
            assert r.returncode == 0 and "Estado: OBSOLETO" in r.stdout
            with sqlite3.connect(clone) as db:
                assert status(db) == ((1, "2026-11-10T10:00:00"), base_status[1] + 3)

            print("\nCASO 5: REPROCESSAMENTO DE VERSAO HISTORICA")
            r = run(sys.executable, importer, clone, conflict)
            print("  resultado atual:", "BLOQUEADO" if r.returncode else "ACEITO")
            # Retorna falha conhecida: importador bloqueia hash historico quando nao e ativo.
            historical_replay = r.returncode == 0

            with sqlite3.connect(clone) as db:
                assert readcounts(db) == initial
                assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert db.execute("PRAGMA foreign_key_check").fetchall() == []
                assert status(db) == ((1, "2026-11-10T10:00:00"), base_status[1] + 3)

            print("\nCONCLUSOES:")
            print("Quatro cenarios principais: APROVADOS NA COPIA")
            print("Reprocessar versao historica:", "APROVADO" if historical_replay else "PENDENTE DE CORRECAO")
            print("Banco principal: SOMENTE LEITURA")
            print("API: ZERO | AGENDAMENTOS: ZERO")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("TESTE REPROVADO:", exc, file=sys.stderr)
        sys.exit(1)
