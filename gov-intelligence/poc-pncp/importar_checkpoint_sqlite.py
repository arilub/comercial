#!/usr/bin/env python3
"""GOV POC-07: ingestão OFFLINE de checkpoint PNCP em SQLite local.
Nenhuma rede, agendamento, Shop9 ou publicação. Somente fonte oficial já coletada.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS contratacoes (
  id TEXT PRIMARY KEY,
  uf TEXT NOT NULL,
  data_publicacao TEXT,
  data_atualizacao TEXT,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  primeira_ingestao_utc TEXT NOT NULL,
  ultima_ingestao_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versoes (
  id TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  observado_utc TEXT NOT NULL,
  data_atualizacao TEXT,
  payload_json TEXT NOT NULL,
  PRIMARY KEY(id, payload_sha256)
);
CREATE TABLE IF NOT EXISTS importacoes (
  arquivo_sha256 TEXT PRIMARY KEY,
  nome_arquivo TEXT NOT NULL,
  importado_utc TEXT NOT NULL,
  registros INTEGER NOT NULL,
  inseridos INTEGER NOT NULL,
  alterados INTEGER NOT NULL,
  inalterados INTEGER NOT NULL,
  obsoletos INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contratacoes_uf_atualizacao
  ON contratacoes(uf, data_atualizacao);
"""
def now():
    return datetime.now(timezone.utc).isoformat()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def valid_date(v):
    if not v:
        return ""
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Data PNCP invalida: {str(v)[:100]}") from exc

def main():
    p = argparse.ArgumentParser(description="GOV: importar checkpoint CE sem acesso a rede")
    p.add_argument("--entrada", required=True)
    p.add_argument("--banco", required=True)
    args = p.parse_args()
    entrada = Path(args.entrada)
    banco = Path(args.banco)
    if not entrada.is_file():
        p.error("Checkpoint nao encontrado")
    if entrada.resolve() == banco.resolve():
        p.error("Banco e checkpoint devem ser arquivos diferentes")
    try:
        raw = entrada.read_bytes()
        if len(raw) > 100 * 1024 * 1024:
            raise ValueError("Checkpoint supera limite de 100 MB")
        doc = json.loads(raw.decode("utf-8-sig"))
        if doc.get("status") != "COMPLETO":
            raise ValueError("Somente checkpoint COMPLETO pode entrar na base")
        cfg = doc["config"]
        if cfg.get("uf") != "CE" or cfg.get("modalidade") != 6:
            raise ValueError("POC restrita a pregoes CE, modalidade 6")
        items = doc["registros"]
        if not isinstance(items, list) or len(items) != int(doc["totalRegistrosInformado"]):
            raise ValueError("Total de registros diverge do informado no checkpoint")
        if len(items) > 100000:
            raise ValueError("Mais de 100 mil registros num checkpoint; dividir lotes")
        seen = set()
        prepared = []
        for r in items:
            if not isinstance(r, dict):
                raise ValueError("Registro PNCP nao e objeto")
            key = r.get("numeroControlePNCP")
            if not isinstance(key, str) or not key or len(key) > 100 or key in seen:
                raise ValueError("ID PNCP ausente, repetido ou invalido")
            seen.add(key)
            uf = (r.get("unidadeOrgao") or {}).get("ufSigla")
            if uf != "CE":
                raise ValueError(f"UF do comprador diferente de CE: {key}")
            pub, upd = valid_date(r.get("dataPublicacaoPncp")), valid_date(r.get("dataAtualizacaoGlobal"))
            payload = canonical(r)
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            prepared.append((key, uf, pub, upd, payload, digest))
        banco.parent.mkdir(parents=True, exist_ok=True)
        arquivo_hash = hashlib.sha256(raw).hexdigest()
        counts = dict(inseridos=0, alterados=0, inalterados=0, obsoletos=0)
        with sqlite3.connect(banco, timeout=10) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.executescript(SCHEMA)
            db.execute("BEGIN IMMEDIATE")
            try:
                previous = db.execute("SELECT registros FROM importacoes WHERE arquivo_sha256=?", (arquivo_hash,)).fetchone()
                if previous:
                    print(f"JA_IMPORTADO: {previous[0]} registros | SHA256 {arquivo_hash[:16]}")
                    db.rollback()
                    return 0
                timestamp = now()
                for key, uf, pub, upd, payload, digest in prepared:
                    row = db.execute(
                        "SELECT payload_sha256, data_atualizacao FROM contratacoes WHERE id=?", (key,)
                    ).fetchone()
                    if row and row[0] == digest:
                        counts["inalterados"] += 1
                        continue
                    # Uma carga antiga nunca deve substituir um snapshot mais recente.
                    if row and row[1] and (not upd or upd < row[1]):
                        counts["obsoletos"] += 1
                        continue
                    db.execute(
                        "INSERT OR IGNORE INTO versoes(id,payload_sha256,observado_utc,data_atualizacao,payload_json) VALUES(?,?,?,?,?)",
                        (key, digest, timestamp, upd, payload),
                    )
                    if row:
                        db.execute(
                            "UPDATE contratacoes SET data_publicacao=?,data_atualizacao=?,payload_json=?,payload_sha256=?,ultima_ingestao_utc=? WHERE id=?",
                            (pub, upd, payload, digest, timestamp, key),
                        )
                        counts["alterados"] += 1
                    else:
                        db.execute(
                            "INSERT INTO contratacoes(id,uf,data_publicacao,data_atualizacao,payload_json,payload_sha256,primeira_ingestao_utc,ultima_ingestao_utc) VALUES(?,?,?,?,?,?,?,?)",
                            (key, uf, pub, upd, payload, digest, timestamp, timestamp),
                        )
                        counts["inseridos"] += 1
                db.execute(
                    "INSERT INTO importacoes VALUES(?,?,?,?,?,?,?,?)",
                    (arquivo_hash, entrada.name, timestamp, len(prepared), counts["inseridos"], counts["alterados"], counts["inalterados"], counts["obsoletos"]),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            total = db.execute("SELECT COUNT(*) FROM contratacoes").fetchone()[0]
            versions = db.execute("SELECT COUNT(*) FROM versoes").fetchone()[0]
        print("=== BASE LOCAL GOV — IMPORTACAO OFFLINE ===")
        print(f"Entrada: {len(prepared)} | Inseridos: {counts['inseridos']} | Alterados: {counts['alterados']} | Inalterados: {counts['inalterados']} | Obsoletos ignorados: {counts['obsoletos']}")
        print(f"Base: {total} pregoes | Versoes preservadas: {versions}")
        print(f"SQLite: {banco}")
        print("Rede: ZERO | Agendamentos: ZERO | Producao: INALTERADA")
        return 0
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, json.JSONDecodeError) as err:
        print(f"ERRO: {type(err).__name__}: {err}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
