#!/usr/bin/env python3
"""GOV POC-44: medicao MANUAL, sem persistencia, da carga diaria de publicacoes/atualizacoes CE.
Nao cria arquivos, nao importa SQLite, nao agenda. Usa apenas API PNCP oficial.
"""
import argparse
import json
import sys
import time
from datetime import datetime, date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = "https://pncp.gov.br/api/consulta/v1/contratacoes/"
def obter(tipo, inicio, fim):
    params = dict(dataInicial=inicio, dataFinal=fim, codigoModalidadeContratacao=6,
                  uf="CE", pagina=1, tamanhoPagina=50)
    uri = ROOT + tipo + "?" + urlencode(params)
    req = Request(uri, headers={"Accept":"application/json",
                                 "User-Agent":"GOV-Intelligence-POC/0.44"})
    inicio_t = time.perf_counter()
    with urlopen(req, timeout=30) as response:
        http = response.status
        bruto = response.read()
    duracao = time.perf_counter()-inicio_t
    dado = json.loads(bruto.decode("utf-8-sig"))
    rows = dado.get("data")
    if http != 200 or not isinstance(rows, list):
        raise ValueError(f"{tipo}: resposta sem dados validos")
    total = int(dado["totalRegistros"])
    paginas = int(dado["totalPaginas"])
    ids = [r.get("numeroControlePNCP") for r in rows]
    if len(rows) > 50 or len(ids) != len(set(ids)) or not all(ids):
        raise ValueError(f"{tipo}: pagina invalida ou IDs duplicados")
    if any((r.get("unidadeOrgao") or {}).get("ufSigla") != "CE" for r in rows):
        raise ValueError(f"{tipo}: UF inesperada")
    if paginas < 1 or total < len(rows):
        raise ValueError(f"{tipo}: metadados incoerentes")
    return dict(tipo=tipo,http=http,total=total,paginas=paginas,
                pagina1=len(rows),bytes=len(bruto),segundos=round(duracao,3))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dia", required=True, help="YYYYMMDD, dia encerrado")
    args=p.parse_args()
    dia=datetime.strptime(args.dia,"%Y%m%d").date()
    if not(date(2023,11,19)<=dia<date.today()):
        p.error("Somente dia encerrado a partir de 19/11/2023")
    print("=== GOV POC-44: PERFIL DIARIO CE ===",flush=True)
    print("DIA:",dia,"| MODALIDADE:6 | PAGINACAO:50",flush=True)
    resultados=[]
    for indice,tipo in enumerate(("publicacao","atualizacao")):
        if indice:
            print("PAUSA ENTRE CONSULTAS: 4 s",flush=True)
            time.sleep(4)
        try:
            resultado=obter(tipo,args.dia,args.dia)
        except (HTTPError,URLError,ValueError,TimeoutError,json.JSONDecodeError) as err:
            print("PARADA SEGURA:",tipo,type(err).__name__,str(err)[:300],file=sys.stderr)
            return 1
        resultados.append(resultado)
        print(json.dumps(resultado,ensure_ascii=False),flush=True)
    minimo=sum(max(0,r["paginas"]-1)*4 for r in resultados)
    print("PAGINAS TOTAIS ESTIMADAS:",sum(r["paginas"] for r in resultados))
    print("ESPERA ENTRE PAGINAS (SE COLETA COMPLETA):",minimo,"s")
    print("ATENCAO: apenas primeira pagina por rota, totais de API nao auditados integralmente")
    print("REDES: 2 CONSULTAS | SQLITE: INALTERADO | CHECKPOINTS: INALTERADOS | AGENDAMENTOS: ZERO")
    return 0
if __name__=="__main__":
    sys.exit(main())
