#!/usr/bin/env python3
"""GOV POC-29: executor MANUAL e limitado de semanas PNCP CE.

Padrao --planejar: somente leitura, sem rede. --executar faz ate 2 semanas
com coletor existente e importa somente checkpoints COMPLETOS apos backup.
Nao ativa agendamentos ou acessa sistemas de producao.
"""
import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MIN_DATA = date(2023, 11, 19)
MAX_DATA = date(2026, 11, 19)
ORIGINAIS = ("contratacoes", "versoes", "importacoes")
DETALHES = ("contratacoes_detalhes", "contratacoes_detalhes_versoes")


def execucao(cmd):
    print("COMANDO:", " ".join(map(str, cmd)), flush=True)
    return subprocess.run([str(x) for x in cmd], check=False).returncode


def analisar_checkpoint(arquivo, inicio, fim):
    if not arquivo.exists():
        return "AUSENTE", None
    bruto = arquivo.read_bytes()
    doc = json.loads(bruto.decode("utf-8-sig"))
    esperado = {"inicio": inicio.strftime("%Y%m%d"), "fim": fim.strftime("%Y%m%d"),
                "uf": "CE", "municipio": None, "modalidade": 6, "tamanhoPagina": 10}
    if doc.get("config") != esperado:
        raise ValueError("Configuracao de checkpoint divergente: " + str(arquivo))
    itens = doc.get("registros")
    if not isinstance(itens, list):
        raise ValueError("Checkpoint sem registros em lista")
    ids = [r.get("numeroControlePNCP") if isinstance(r, dict) else None for r in itens]
    if len(set(ids)) != len(ids) or not all(ids):
        raise ValueError("Checkpoint com IDs invalidos ou duplicados")
    estado = doc.get("status")
    if estado == "COMPLETO" and len(itens) != doc.get("totalRegistrosInformado"):
        raise ValueError("Checkpoint completo com total divergente")
    if estado not in ("COMPLETO", "PARCIAL"):
        raise ValueError("Checkpoint invalido ou inconsistente: " + str(estado))
    return estado, hashlib.sha256(bruto).hexdigest()


def estado_banco(banco):
    with closing(sqlite3.connect(f"file:{banco.resolve().as_posix()}?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Banco SQLite com integridade comprometida")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Banco com erro de chaves estrangeiras")
        return {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ORIGINAIS + DETALHES}


def fazer_backup(banco):
    nome = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    destino = banco.with_name(f"gov_intelligence_pre_lote_{nome}.sqlite3")
    with closing(sqlite3.connect(f"file:{banco.resolve().as_posix()}?mode=ro", uri=True)) as origem:
        with closing(sqlite3.connect(destino)) as copia:
            origem.backup(copia)
            if copia.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Falha de integridade no backup")
    print("BACKUP VALIDADO:", destino, flush=True)
    return destino


def importado(banco, digest):
    with closing(sqlite3.connect(f"file:{banco.resolve().as_posix()}?mode=ro", uri=True)) as db:
        return db.execute("SELECT 1 FROM importacoes WHERE arquivo_sha256=?", (digest,)).fetchone() is not None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True)
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--inicio", required=True, help="YYYYMMDD")
    p.add_argument("--semanas", type=int, default=1, choices=(1, 2))
    p.add_argument("--max-paginas", type=int, default=10, choices=range(1, 11))
    p.add_argument("--intervalo", type=float, default=4.0)
    p.add_argument("--executar", action="store_true", help="Coletar e importar; sem flag apenas planeja")
    args = p.parse_args()
    if args.intervalo < 4:
        p.error("Intervalo minimo por politica da POC: 4 segundos")
    base = Path(args.base)
    dados, scripts = base / "dados", base / "scripts"
    banco = dados / "gov_intelligence_ce_poc.sqlite3"
    coletor = scripts / "coleta_publicacoes_checkpoint.py"
    importador = scripts / "importar_checkpoint_sqlite.py"
    if not banco.is_file() or not coletor.is_file() or not importador.is_file():
        raise ValueError("Banco ou scripts homologados nao encontrados")
    primeira = datetime.strptime(args.inicio, "%Y%m%d").date()
    if primeira < MIN_DATA or primeira > MAX_DATA:
        raise ValueError("Data inicial fora do horizonte da POC")
    if primeira + timedelta(days=7 * args.semanas - 1) > MAX_DATA:
        raise ValueError("Lote ultrapassa horizonte de 36 meses")

    print("=== GOV POC-29 — LOTE HISTORICO MANUAL ===", flush=True)
    print("MODO:", "EXECUTAR" if args.executar else "PLANEJAR (SEM REDE)", flush=True)
    antes = estado_banco(banco)
    print("CONTAGENS INICIAIS:", antes, flush=True)
    for n in range(args.semanas):
        inicio = primeira + timedelta(days=7*n)
        fim = inicio + timedelta(days=6)
        saida = dados / f"pncp_ce_publicacoes_{inicio:%Y%m%d}_{fim:%Y%m%d}.json"
        estado, digest = analisar_checkpoint(saida, inicio, fim)
        print(f"\nSEMANA {n+1}: {inicio} a {fim} | {estado} | {saida.name}", flush=True)
        if not args.executar:
            continue
        if estado != "COMPLETO":
            rc = execucao([args.python, coletor, "--inicio", inicio.strftime("%Y%m%d"),
                           "--fim", fim.strftime("%Y%m%d"), "--uf", "CE",
                           "--saida", saida, "--max-paginas", args.max_paginas,
                           "--intervalo", args.intervalo])
            if rc:
                raise ValueError(f"Coletor parou com codigo {rc}; preserve checkpoint e revise")
            estado, digest = analisar_checkpoint(saida, inicio, fim)
            if estado != "COMPLETO":
                print("PARCIAL: checkpoint preservado; nenhuma importacao; encerrar lote", flush=True)
                return 2
        if importado(banco, digest):
            print("JA IMPORTADO: hash do checkpoint localizado no SQLite", flush=True)
            continue
        anterior = estado_banco(banco)
        fazer_backup(banco)
        rc = execucao([args.python, importador, "--entrada", saida, "--banco", banco])
        if rc:
            raise ValueError(f"Importacao falhou (codigo {rc}); NAO REPETIR sem auditoria")
        posterior = estado_banco(banco)
        if posterior["importacoes"] != anterior["importacoes"]+1:
            raise ValueError("Contagem de importacoes inesperada")
        for t in DETALHES:
            if posterior[t] != anterior[t]:
                raise ValueError("Enriquecimentos alterados indevidamente")
        if not importado(banco, digest):
            raise ValueError("Hash do arquivo nao apareceu em importacoes")
        print("SEMANA AUDITADA:", anterior, "=>", posterior, flush=True)
        if n+1 < args.semanas:
            time.sleep(args.intervalo)
    print("\nLOTE CONCLUIDO | SQLite:", estado_banco(banco))
    print("Agendamentos: ZERO | Producao: INALTERADA")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erro:
        print("PARADA SEGURA:", erro, file=sys.stderr)
        sys.exit(1)
