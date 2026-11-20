#!/usr/bin/env python3
"""POC-10: coleta MANUAL e conservadora de itens oficiais PNCP para um processo.
O checkpoint persiste paginas completas; nenhuma gravacao no SQLite; sem tarefas.
"""
import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PATTERN = re.compile(r"^(\d{14})-1-(\d{6})/(\d{4})$")

def now():
    return datetime.now(timezone.utc).isoformat()

def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as h:
        json.dump(data, h, indent=2, ensure_ascii=False)
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)

def retry_wait(header):
    if not header:
        return 30 + random.random() * 5
    try:
        return max(0.0, float(header))
    except ValueError:
        try:
            return max(0.0, (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 30 + random.random() * 5

def fetch(url):
    for attempt in range(2):
        try:
            req = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'GOV-Intelligence-POC/0.4'})
            with urlopen(req, timeout=30) as response:
                raw = response.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    raise ValueError('Resposta excede 5 MB')
                return json.loads(raw.decode('utf-8-sig'))
        except HTTPError as err:
            if err.code != 429 or attempt:
                raise
            wait = retry_wait(err.headers.get('Retry-After'))
            if wait > 180:
                raise RuntimeError('Retry-After excede 180 segundos') from err
            print(f'HTTP 429: pausa {wait:.1f}s antes de unica retentativa', flush=True)
            time.sleep(wait)

def main():
    parser = argparse.ArgumentParser(description='POC-10: checkpoint de itens PNCP, manual, CE')
    parser.add_argument('--id', required=True, help='numeroControlePNCP')
    parser.add_argument('--banco', required=True, help='SQLite local somente leitura')
    parser.add_argument('--saida', required=True)
    parser.add_argument('--max-paginas', type=int, default=3)
    parser.add_argument('--intervalo', type=float, default=4.0)
    args = parser.parse_args()
    if not 1 <= args.max_paginas <= 4 or args.intervalo < 4:
        parser.error('max-paginas 1..4, intervalo >=4 segundos')
    match = PATTERN.fullmatch(args.id)
    if not match:
        parser.error('ID PNCP fora do padrao esperado para pregao')
    cnpj, seq, year = match.groups()
    output = Path(args.saida)
    if output.exists():
        state = json.loads(output.read_text(encoding='utf-8-sig'))
        if state.get('id') != args.id or state.get('fonte') != 'PNCP-ITENS-v1':
            parser.error('Checkpoint de outro processo ou versao')
        if state['status'] == 'COMPLETO':
            print(f'JA_COMPLETO | {len(state["itens"])} itens | rede zero')
            return 0
    else:
        import sqlite3
        db_path = Path(args.banco)
        if not db_path.is_file():
            parser.error('SQLite nao encontrado')
        with sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True) as db:
            row = db.execute('SELECT uf FROM contratacoes WHERE id=?', (args.id,)).fetchone()
        if not row or row[0] != 'CE':
            parser.error('ID nao cadastrado na base CE')
        state = {'fonte':'PNCP-ITENS-v1', 'id':args.id, 'status':'PARCIAL',
                 'proximaPagina':1, 'itens':[], 'observacoes':[], 'atualizadoEmUTC':now()}
    processed = 0
    while processed < args.max_paginas:
        page = state['proximaPagina']
        url = (f'https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{year}/'
               f'{int(seq)}/itens?pagina={page}&tamanhoPagina=50')
        try:
            data = fetch(url)
            if not isinstance(data, list) or len(data) > 50 or not data:
                raise ValueError('Pagina vazia, invalida ou maior que limite; revisar')
            observed = {x.get('numeroItem') for x in state['itens']}
            for item in data:
                if not isinstance(item, dict):
                    raise ValueError('Item nao e objeto')
                key = item.get('numeroItem')
                if not isinstance(key, int) or key < 1 or key in observed:
                    raise ValueError(f'Item sem chave unica valida: {key}')
                observed.add(key)
            state['itens'].extend(data)
            state['proximaPagina'] = page + 1
            state['status'] = 'COMPLETO' if len(data) < 50 else 'PARCIAL'
            state['atualizadoEmUTC'] = now()
            atomic(output, state)
            processed += 1
            print(f'Pagina {page} | itens {len(data)} | acumulado {len(state["itens"])} | {state["status"]}',flush=True)
            if state['status'] == 'COMPLETO':
                break
            if processed < args.max_paginas:
                time.sleep(args.intervalo)
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, json.JSONDecodeError, OSError) as err:
            state['observacoes'].append(f'Pagina {page}: {type(err).__name__}: {str(err)[:180]}')
            state['atualizadoEmUTC'] = now()
            atomic(output, state)
            print(f'PARADA SEGURA pagina {page}: {err}', file=sys.stderr)
            return 1
    print(f'STATUS: {state["status"]} | ITENS: {len(state["itens"])} | ARQUIVO: {output}')
    print('SQLite inalterado | Classificacao comercial NEUTRO | Agendamento ZERO')
    return 0

if __name__ == '__main__':
    sys.exit(main())
