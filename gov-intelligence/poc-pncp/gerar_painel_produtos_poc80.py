#!/usr/bin/env python3
"""POC-80: painel offline experimental de pesquisa de produtos ARILUB.
Apenas leitura do JSON POC79; gera HTML isolado. Nao altera radar nem SQLite.
"""
import argparse
import html
import json
import os
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

TEMPLATE = r'''<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ARILUB GOV Intelligence | Pesquisa histórica POC-80</title>
<style>
:root{font-family:Segoe UI,Arial,sans-serif;color:#162d42;background:#f3f6fa}
*{box-sizing:border-box}body{margin:0}header{background:#16324d;color:white;padding:23px max(20px,calc((100vw - 1220px)/2))}header h1{font-size:23px;margin:5px 0}header p{color:#cee0f0;margin:7px 0;font-size:13px}
main{max-width:1220px;margin:22px auto;padding:0 18px}section{background:white;border:1px solid #d8e3ed;border-radius:12px;margin-bottom:16px;padding:18px}
h2{font-size:18px;margin:0 0 12px}.meta{font-size:12px;color:#5b7187;line-height:1.5}.warning{border-left:4px solid #b57720;padding:10px 12px;background:#fff8ed;line-height:1.5}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.kpi{background:#f7fafc;border:1px solid #e1eaf0;border-radius:8px;padding:13px}.kpi strong{font-size:23px;display:block}.kpi span{font-size:12px;color:#52697c}
nav{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}button{border:1px solid #b8c9d9;background:#f1f5f9;border-radius:7px;color:#1a405c;padding:9px 13px;cursor:pointer}button[aria-selected=true]{background:#173d60;color:white}
.controls{display:grid;grid-template-columns:2fr 1fr 1fr;gap:9px;margin:12px 0}input,select{font:inherit;padding:10px;border:1px solid #aebfce;border-radius:8px;width:100%;color:inherit;background:white}
.scroll{max-height:600px;overflow:auto}table{width:100%;min-width:1050px;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #e6edf3;padding:10px 9px;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#e9f0f6;z-index:1}td.item{min-width:220px;max-width:320px}td.org{min-width:190px}
.pill{padding:3px 7px;display:inline-block;border-radius:30px;font-size:11px;border:1px solid #a9c4d0}.pill.cancel{color:#a04a24;border-color:#e4b9a5;background:#fff2ed}.pill.unknown{color:#78623d;background:#fff9e8}.pill.ok{color:#2b6559;background:#ebf9f2}
a{color:#13689a}footer{color:#667a8b;font-size:12px;margin:22px 0}.none{color:#67788a;padding:10px}
@media(max-width:780px){.kpis{grid-template-columns:repeat(2,1fr)}.controls{grid-template-columns:1fr}}
</style></head><body>
<header><small>ARILUB • GOV INTELLIGENCE</small><h1>Inteligência de Produtos — POC-80</h1><p>Pesquisa histórica experimental • Fonte oficial PNCP • Ceará</p></header>
<main>
<section><p class="warning"><strong>AMOSTRA EXPLORATÓRIA.</strong> Consultados até 6 pregões, apenas a primeira página de itens e até 4 itens correspondentes por pregão. Não representa cobertura integral de mercado, equivalência técnica, aderência ao catálogo da ARILUB nem todas as participações de fornecedores. Resultados cancelados não são vitórias vigentes. Os dados podem ter mudado.</p>
<p class="meta" id="metadados"></p></section>
<section><div class="kpis">
<div class="kpi"><strong id="kPregoes">—</strong><span>Pregões consultados</span></div>
<div class="kpi"><strong id="kItens">—</strong><span>Itens de produto pesquisados</span></div>
<div class="kpi"><strong id="kResultados">—</strong><span>Registros de resultados</span></div>
<div class="kpi"><strong id="kHistorico">—</strong><span>Pregões com termos no objeto (base)</span></div>
</div></section>
<section>
<h2>Investigar histórico de compras</h2>
<nav role="tablist" aria-label="Áreas de análise">
<button type="button" role="tab" id="tabProdutos" aria-selected="true">Produtos</button>
<button type="button" role="tab" id="tabOrgaos" aria-selected="false">Órgãos</button>
<button type="button" role="tab" id="tabConcorrencia" aria-selected="false">Concorrência</button>
</nav>
<div class="controls"><input type="search" id="busca" placeholder="Pesquisar descrição, órgão, município, fornecedor ou CNPJ" aria-label="Pesquisa textual">
<select id="situacao"><option value="">Todas as situações</option><option value="informado">Resultados informados e não cancelados</option><option value="cancelado">Resultados cancelados</option><option value="outro">Outras situações</option><option value="sem">Sem resultado recuperado</option></select>
<select id="ordem"><option value="data">Data do resultado (mais recente)</option><option value="produto">Produto A–Z</option><option value="preco">Maior valor unitário homologado</option></select></div>
<p class="meta" id="sum"></p>
<div class="scroll"><table><thead id="head"></thead><tbody id="body"></tbody></table></div>
<p class="none" id="vazio" hidden>Nenhum registro para os filtros selecionados.</p>
</section>
<footer>POC-80 • Leitura local. Não conectado ao SQLite em tempo real. Valide qualquer decisão no edital e resultado oficial do PNCP.</footer>
</main>
<script id="dadosIncorporados" type="application/json">__JSON_EMBED__</script>
<script>
"use strict";
const payload=JSON.parse(document.getElementById("dadosIncorporados").textContent);
let active="Produtos";
const $=id=>document.getElementById(id);
const brl=new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"});
const fmt=new Intl.NumberFormat("pt-BR");
const registros=payload.registros;
const clean=v=>String(v??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const val=v=>v==null?"Não informado":String(v);
const money=v=>typeof v==="number"&&Number.isFinite(v)?brl.format(v):"Não informado";
function state(r){let s=clean(r.situacao);if(r.dataCancelamento||s==="cancelado")return"cancelado";if(s==="informado")return"informado";if(!r.temResultado)return"sem";return"outro"}
function td(tr,t,cls){const c=document.createElement("td");c.textContent=val(t);if(cls)c.className=cls;tr.appendChild(c);return c}
function link(tr,url){const cell=td(tr,"");try{const u=new URL(url);if(u.protocol==="https:"&&u.hostname==="pncp.gov.br"){const a=document.createElement("a");a.href=u.href;a.target="_blank";a.rel="noopener noreferrer";a.textContent="PNCP";cell.appendChild(a)}}catch{}return cell}
function draw(){
  for(const name of ["Produtos","Orgaos","Concorrencia"])$("tab"+name).setAttribute("aria-selected",String(active===({Orgaos:"Órgãos",Concorrencia:"Concorrência"}[name]||name)));
  const q=clean($("busca").value),s=$("situacao").value,ord=$("ordem").value;
  let list=registros.filter(r=>(!s||state(r)===s)&&(!q||clean([r.descricao,r.orgao,r.municipio,r.fornecedor,r.identificacaoFornecedor,r.processo].join(" ")).includes(q)));
  if(ord==="preco")list.sort((a,b)=>(b.valorUnitarioHomologado??-1)-(a.valorUnitarioHomologado??-1));
  else if(ord==="produto")list.sort((a,b)=>String(a.descricao||"").localeCompare(String(b.descricao||""),"pt-BR"));
  else list.sort((a,b)=>String(b.dataResultado||"").localeCompare(String(a.dataResultado||"")));
  const head=$("head"),body=$("body");head.replaceChildren();body.replaceChildren();
  const cols=active==="Produtos"?["Produto / item","Órgão / Município","Fornecedor","Situação","Valor estimado / un.","Valor homologado / un.","Data resultado","Fonte"]:
    active==="Órgãos"?["Órgão / Município","Produto / item","Fornecedor","Situação","Data resultado","Valor total homologado","Fonte"]:
    ["Fornecedor / CNPJ","Produto / item","Órgão","Situação","Data resultado","Valor homologado / un.","Fonte"];
  const hr=document.createElement("tr");for(const c of cols){const th=document.createElement("th");th.textContent=c;hr.appendChild(th)}head.appendChild(hr);
  for(const r of list.slice(0,400)){
    const tr=document.createElement("tr");
    const produto=(r.descricao||"Descrição não informada")+" · item "+r.item;
    const org=(r.orgao||"Órgão não informado")+" · "+(r.municipio||"município não informado");
    const fornecedor=(r.fornecedor||"Fornecedor não informado")+" · "+(r.identificacaoFornecedor||"CNPJ/CPF não informado");
    if(active==="Produtos"){td(tr,produto,"item");td(tr,org,"org");td(tr,r.fornecedor);td(tr,r.situacao||"Sem resultado");td(tr,money(r.valorUnitarioEstimado));td(tr,money(r.valorUnitarioHomologado));td(tr,r.dataResultado||"Não informada");link(tr,r.urlResultados||r.urlItens)}
    else if(active==="Órgãos"){td(tr,org,"org");td(tr,produto,"item");td(tr,r.fornecedor);td(tr,r.situacao||"Sem resultado");td(tr,r.dataResultado||"Não informada");td(tr,money(r.valorTotalHomologado));link(tr,r.urlResultados||r.urlItens)}
    else{td(tr,fornecedor);td(tr,produto,"item");td(tr,r.orgao);td(tr,r.situacao||"Sem resultado");td(tr,r.dataResultado||"Não informada");td(tr,money(r.valorUnitarioHomologado));link(tr,r.urlResultados||r.urlItens)}
    body.appendChild(tr);
  }
  $("sum").textContent="Exibindo "+fmt.format(Math.min(list.length,400))+" de "+fmt.format(list.length)+" registros na amostra. Linhas representam resultados por item, não necessariamente licitações distintas. Não somar valores sem validação.";
  $("vazio").hidden=list.length>0;
}
for(const name of ["Produtos","Orgaos","Concorrencia"])$("tab"+name).addEventListener("click",()=>{active={Orgaos:"Órgãos",Concorrencia:"Concorrência"}[name]||name;draw()});
$("busca").addEventListener("input",draw);
$("situacao").addEventListener("change",draw);
$("ordem").addEventListener("change",draw);
$("kPregoes").textContent=fmt.format(payload.totalConsultados);
$("kItens").textContent=fmt.format(payload.totalItens);
$("kResultados").textContent=fmt.format(payload.totalResultados);
$("kHistorico").textContent=fmt.format(payload.candidatosNoObjeto);
$("metadados").textContent="Fonte: POC-79 gerada em "+payload.dataFonte+" • HTML gerado em "+payload.geradoEmUTC+". Índice de produtos sem equivalência técnica ou aderência comercial homologada.";
draw();
</script></body></html>'''

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base",required=True)
    a=ap.parse_args()
    base=Path(a.base)
    src=base/"dados"/"poc79_pesquisa_produtos_arilub.json"
    doc=json.loads(src.read_text(encoding="utf-8-sig"))
    if doc.get("schema")!="gov-poc79-amostra-produtos":
        raise ValueError("Schema POC79 invalido")
    processos=doc.get("processos")
    if not isinstance(processos,list):raise ValueError("Processos invalidos")
    reg=[]
    vistos=set()
    for proc in processos:
        pid=proc.get("id")
        if not isinstance(pid,str):raise ValueError("Processo invalido")
        for item in proc.get("itensCorrespondentes",[]):
            no=item.get("numeroItem")
            if not isinstance(no,int):raise ValueError("Item invalido")
            base_row={"processo":pid,"orgao":proc.get("orgao"),"municipio":proc.get("municipio"),
                "item":no,"descricao":item.get("descricao"),"unidade":item.get("unidadeMedida"),
                "quantidade":item.get("quantidade"),"valorUnitarioEstimado":item.get("valorUnitarioEstimado"),
                "urlItens":proc.get("urlItens"),"urlResultados":item.get("urlResultados"),"temResultado":bool(item.get("resultados"))}
            for r in item.get("resultados",[]):
                if r.get("numeroControlePNCPCompra")!=pid or r.get("numeroItem")!=no:raise ValueError("Divergencia vinculo processo/item")
                seq=r.get("sequencialResultado")
                chave=(pid,no,seq)
                if chave in vistos:raise ValueError("Resultado duplicado")
                vistos.add(chave)
                reg.append({**base_row,"situacao":r.get("situacaoCompraItemResultadoNome"),
                    "dataCancelamento":r.get("dataCancelamento"),"dataResultado":r.get("dataResultado"),
                    "fornecedor":r.get("nomeRazaoSocialFornecedor"),"identificacaoFornecedor":r.get("niFornecedor"),
                    "valorUnitarioHomologado":r.get("valorUnitarioHomologado"),
                    "quantidadeHomologada":r.get("quantidadeHomologada"),
                    "valorTotalHomologado":r.get("valorTotalHomologado")})
            if not item.get("resultados"):
                reg.append({**base_row,"situacao":None,"dataCancelamento":None,
                    "dataResultado":None,"fornecedor":None,"identificacaoFornecedor":None,
                    "valorUnitarioHomologado":None,"quantidadeHomologada":None,
                    "valorTotalHomologado":None})
    data={"schema":"gov-poc80-dashboard-amostra","dataFonte":doc.get("geradoEmUTC"),
        "geradoEmUTC":datetime.now(timezone.utc).isoformat(),
        "candidatosNoObjeto":doc.get("candidatosNoObjeto"),
        "totalConsultados":len(processos),
        "totalItens":sum(len(p.get("itensCorrespondentes",[])) for p in processos),
        "totalResultados":sum(bool(r.get("fornecedor")) for r in reg),
        "registros":reg}
    blob=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(",",":")).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    rendered=TEMPLATE.replace("__JSON_EMBED__",blob)
    if "__JSON_EMBED__" in rendered:raise RuntimeError("Falha incorporacao")
    out=base/"GOV_INTELLIGENCE_PRODUTOS_POC80.html"
    tmp=out.with_suffix(".html.tmp")
    try:
        tmp.write_text(rendered,encoding="utf-8")
        os.replace(tmp,out)
    finally:tmp.unlink(missing_ok=True)
    print("=== GOV POC-80 - PAINEL EXPERIMENTAL DE PRODUTOS ===")
    print("PROCESSOS CONSULTADOS:",len(processos))
    print("ITENS CORRESPONDENTES NA AMOSTRA:",data["totalItens"])
    print("LINHAS DE RESULTADOS OU SEM RESULTADO:",len(reg))
    print("PAINEL:",out)
    print("RADAR PRINCIPAL, SQLITE E AGENDAMENTO: INALTERADOS")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except (OSError,ValueError,TypeError,KeyError,RuntimeError) as exc:
        print("PARADA SEGURA:",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(1)
