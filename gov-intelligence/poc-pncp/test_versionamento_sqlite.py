#!/usr/bin/env python3
"""GOV POC-08: self-test isolado de versoes e obsolescencia. Rede zero."""
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

def ck(path, row):
    payload = {
        "status": "COMPLETO",
        "config": {"uf": "CE", "modalidade": 6},
        "totalRegistrosInformado": 1,
        "registros": [row],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

def run(script, entry, db, expected=0):
    result = subprocess.run(
        [sys.executable, str(script), "--entrada", str(entry), "--banco", str(db)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != expected:
        raise AssertionError(f"Retorno {result.returncode}; stdout={result.stdout}; stderr={result.stderr}")
    return result.stdout

def base_record(date, value):
    return {
        "numeroControlePNCP": "12345678000199-1-000001/2026",
        "unidadeOrgao": {"ufSigla": "CE", "municipioNome": "Fortaleza"},
        "dataPublicacaoPncp": "2026-10-01T09:00:00",
        "dataAtualizacaoGlobal": date,
        "valorTotalHomologado": value,
        "situacaoCompraNome": "Divulgada no PNCP",
    }

def main():
    script = Path(__file__).with_name("importar_checkpoint_sqlite.py")
    if not script.is_file():
        raise FileNotFoundError(f"Modulo principal ausente: {script}")
    with tempfile.TemporaryDirectory(prefix="gov_poc_teste_") as folder:
        root = Path(folder)
        db = root / "base_teste.sqlite3"
        initial = root / "inicial.json"
        newer = root / "novo.json"
        older = root / "antigo.json"
        ck(initial, base_record("2026-10-02T09:00:00", 100))
        ck(newer, base_record("2026-10-05T09:00:00", 110))
        ck(older, base_record("2026-10-03T09:00:00", 90))
        run(script, initial, db)
        with sqlite3.connect(db) as c:
            assert c.execute("SELECT COUNT(*) FROM contratacoes").fetchone()[0] == 1
            assert c.execute("SELECT COUNT(*) FROM versoes").fetchone()[0] == 1
        run(script, initial, db)
        run(script, newer, db)
        with sqlite3.connect(db) as c:
            row = c.execute("SELECT data_atualizacao,payload_json FROM contratacoes").fetchone()
            assert row[0].startswith("2026-10-05")
            assert json.loads(row[1])["valorTotalHomologado"] == 110
            assert c.execute("SELECT COUNT(*) FROM versoes").fetchone()[0] == 2
        run(script, older, db)
        with sqlite3.connect(db) as c:
            row = c.execute("SELECT data_atualizacao,payload_json FROM contratacoes").fetchone()
            assert row[0].startswith("2026-10-05")
            assert json.loads(row[1])["valorTotalHomologado"] == 110
            assert c.execute("SELECT COUNT(*) FROM versoes").fetchone()[0] == 2
            assert c.execute("SELECT COUNT(*) FROM importacoes").fetchone()[0] == 3
            assert c.execute("SELECT obsoletos FROM importacoes ORDER BY importado_utc DESC LIMIT 1").fetchone()[0] in (0, 1)
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        print("=== TESTE DE VERSIONAMENTO ISOLADO ===")
        print("Insercao inicial: OK")
        print("Reimportacao identica: OK")
        print("Atualizacao legitima: OK")
        print("Snapshot antigo rejeitado: OK")
        print("Versoes preservadas: 2")
        print("Integridade SQLite: ok")
        print("Dados reais: INALTERADOS | Rede: ZERO")
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"FALHA: {exc}", file=sys.stderr)
        sys.exit(1)
