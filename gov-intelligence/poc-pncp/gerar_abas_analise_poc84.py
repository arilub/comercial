#!/usr/bin/env python3
"""POC-84: abas analiticas sobre o radar V1.5 sem substitui-lo.

Gera HTML adicional, de forma nao destrutiva, partindo do V1.5 homologando.
Abas: Radar intacto / Produtos / Orgaos / Concorrencia / Pesquisa.
Dados de compras: snapshot integral POC82; concorrencia: amostra POC79.
"""
import argparse,json,os,sys
from pathlib import Path

CSS=r'''
<style id="gov84Style">
#gov84Tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px;padding:12px;background:#fff;border:1px solid #dce5ec;border-radius:13px}
#gov84Tabs button{border:1px solid #b8c9d9;padding:10px 15px;border-radius:8px;background:#f4f8fb;font:inherit;color:#184669;cursor:pointer}
#gov84Tabs button[aria-selected=true]{background:#153a59;color:white;border-color:#153a59}
#gov84Research[hidden],#gov84Radar[hidden]{display:none!important}
.gov84Controls{display:grid;grid-template-columns:minmax(180px,2fr) repeat(2,minmax(150px,1fr));gap:10px;margin:14px 0}
.gov84Controls input,.gov84Controls select{min-width:0;width:100%;border:1px solid #b6c6d3;border-radius:8px;padding:11px;font:inherit;background:white}
.gov84Kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}
.gov84Kpi{padding:13px;border:1px solid #dce5ec;border-radius:9px;background:#f8fafc}
.gov84Kpi strong{display:block;font-size:22px}.gov84Kpi span{font-size:12px;color:#667c90}
.gov84Nav{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:12px 0}
.gov84Nav button{border:1px solid #abbfce;background:#f0f5f9;border-radius:8px;padding:8px 12px;cursor:pointer;color:#143d5d}
.gov84TableWrap{max-height:600px;overflow:auto}
#gov84Table{min-width:980px}#gov84Table td{overflow-wrap:anywhere}
.gov84Pill{font-size:11px;border-radius:20px;padding:3px 7px;border:1px solid #b9c9d7;display:inline-block}
.gov84Notice{border-left:3px solid #8b9baa;padding-left:12px;color:#425970;line-height:1.5}
@media(max-width:680px){.gov84Controls{grid-template-columns:1fr}.gov84Kpis{grid-template-columns:1fr 1fr}}
</style>
'''

JS=r'''<script id="gov84Controller">
(function(){
"use strict";
const $=id=>document.getElementById(id);
const main=document.querySelector("main");
const fonte=$("embeddedData");
if(!main||!fonte||!$("results"))return;
let dataset;
try{dataset=JSON.parse(fonte.textContent)}catch(e){console.error("GOV84: fonte invalida",e);return}
if(!Array.isArray(dataset.candidatos)||dataset.schema!=="gov-intelligence-radar-v15-integral")return;
const pregoes=dataset.candidatos;
const historico=JSON.parse($("gov84Historico").textContent);
const norm=s=>String(s??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const fmt=new Intl.NumberFormat("pt-BR");
const brl=new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"});
const money=v=>typeof v==="number"&&Number.isFinite(v)?brl.format(v):"Não informado";
const safeUrl=v=>{try{const x=new URL(v);return x.protocol==="https:"&&x.hostname==="pncp.gov.br"&&x.pathname.startsWith("/app/editais/")?x.href:null}catch{return null}};
const hoje=Date.now();
const futuro=d=>{const v=Date.parse(d.encerramentoProposta);return Number.isFinite(v)&&v>hoje&&d.situacaoPNCP==="Divulgada no PNCP"};
const productKind=d=>{
 const t=norm(d.objeto);
 const terms=[["Lubrificantes e fluidos",/(lubrificant|oleo|graxa|fluido|aditivo|arrefecimento)/],
 ["Pneus e borrachas",/(pneu|camara de ar|borracha)/],
 ["Filtros",/(filtro|elemento filtrante)/],
 ["Peças e componentes",/(pecas|peca |autopecas|componentes|rolamento)/],
 ["Combustíveis",/(combustivel|diesel|gasolina|etanol)/],
 ["Equipamentos e ferramentas",/(equipamento|ferramenta|maquina)/],
 ["Materiais diversos",/(material|insumo|fornecimento|aquisicao|registro de precos)/]];
 const hit=terms.filter(x=>x[1].test(t)).map(x=>x[0]);
 return hit.length?hit:["Não classificado pelo objeto"];
};
const servicoExclusivo=d=>{
 // Dado sem itens PNCP: triagem conservadora; nunca descartar mistos/duvidosos.
 const t=norm(d.objeto);
 const isS=/(prestacao de servicos|contratacao de servicos|servicos de (limpeza|consultoria|vigilancia|locacao)|mao de obra|terceirizacao de)/.test(t);
 const bens=/(aquisicao de|fornecimento de|compra de|material|equipamento|insumo|pecas|pneus|oleo|graxa|lubrificant)/.test(t);
 return isS&&!bens;
};
const tabs=["Radar de Pregões","Produtos","Órgãos","Concorrência","Pesquisa"];
const nav=document.createElement("nav");nav.id="gov84Tabs";nav.setAttribute("aria-label","Áreas do GOV Intelligence");
for(const t of tabs){const b=document.createElement("button");b.type="button";b.textContent=t;b.dataset.tab=t;nav.appendChild(b)}
main.insertBefore(nav,main.firstChild);
const radar=document.createElement("div");radar.id="gov84Radar";
for(const c of [...main.children].filter(x=>x.tagName==="SECTION"&&x.id!=="gov84Research"))radar.appendChild(c);
main.insertBefore(radar,nav.nextSibling);
const panel=document.createElement("section");panel.id="gov84Research";panel.className="panel";panel.hidden=true;
panel.innerHTML=
 '<div class="close-row"><h2 id="gov84Title">Pesquisa</h2><span class="muted" id="gov84ScopeNote"></span></div>'+
 '<p class="gov84Notice" id="gov84Description"></p>'+
 '<div class="gov84Controls">'+
 '<input id="gov84Query" type="search" placeholder="Produto, descrição, órgão, município ou ID PNCP" aria-label="Busca na análise">'+
 '<select id="gov84Scope" aria-label="Escopo da análise"><option value="abertos">Pregões com prazo futuro e divulgados</option><option value="filtros">Resultados filtrados no radar</option><option value="todos">Todos os pregões armazenados</option><option value="encerrados">Pregões com prazo encerrado</option></select>'+
 '<select id="gov84Class" aria-label="Linha de produtos"><option value="">Todas as linhas / não classificados</option></select></div>'+
 '<div class="gov84Kpis"><div class="gov84Kpi"><strong id="gov84Count">—</strong><span>Pregões no escopo</span></div><div class="gov84Kpi"><strong id="gov84Matched">—</strong><span>Pregões correspondentes</span></div><div class="gov84Kpi"><strong id="gov84Verified">—</strong><span>Pregões com itens PNCP coletados</span></div></div>'+
 '<div class="gov84Nav"><button id="gov84Clear" type="button">Limpar busca</button><button id="gov84Back" type="button">Voltar ao radar</button><span class="muted" id="gov84Status"></span></div>'+
 '<div class="gov84TableWrap"><table id="gov84Table"><thead id="gov84Head"></thead><tbody id="gov84Body"></tbody></table></div>'+
 '<p class="muted" id="gov84Footer"></p><button class="action" id="gov84More" type="button" hidden>Mostrar mais 50</button>';
main.insertBefore(panel,radar.nextSibling);
let aba=tabs[0],limit=50,orgSelected="";
const classEl=$("gov84Class");
for(const x of ["Lubrificantes e fluidos","Pneus e borrachas","Filtros","Peças e componentes","Combustíveis","Equipamentos e ferramentas","Materiais diversos","Não classificado pelo objeto"])classEl.add(new Option(x,x));
function scopeList(){
 const scope=$("gov84Scope").value;
 if(scope==="todos")return pregoes;
 if(scope==="encerrados")return pregoes.filter(d=>{const v=Date.parse(d.encerramentoProposta);return Number.isFinite(v)&&v<=hoje});
 if(scope==="filtros"){try{return visiveis.slice()}catch{return []}}
 return pregoes.filter(futuro);
}
function filteredRows(){
 const query=norm($("gov84Query").value),cat=$("gov84Class").value;
 return scopeList().filter(d=>{
  if(servicoExclusivo(d))return false;
  if(cat&&!productKind(d).includes(cat))return false;
  if(orgSelected&&d.orgao!==orgSelected)return false;
  if(!query)return true;
  const itens=d.statusEnriquecimentoItens==="COMPLETO"?(d.itensPNCP||[]).map(i=>i.descricao).join(" "):"";
  return norm([d.id,d.objeto,d.orgao,d.municipio,itens].join(" ")).includes(query);
 });
}
function cell(tr,value){const td=document.createElement("td");td.textContent=value==null?"—":String(value);tr.appendChild(td);return td}
function action(tr,label,cb){const td=document.createElement("td");const b=document.createElement("button");b.type="button";b.className="action";b.textContent=label;b.addEventListener("click",cb);td.appendChild(b);tr.appendChild(td)}
function setHead(names){const h=$("gov84Head"),row=document.createElement("tr");h.replaceChildren();for(const name of names){const th=document.createElement("th");th.textContent=name;row.appendChild(th)}h.appendChild(row)}
function renderPregoes(rows){
 setHead(["Pregão / Produto","Órgão / Município","Prazo","Valor estimado","Situação","Itens oficiais","Ação"]);
 for(const d of rows.slice(0,limit)){
  const tr=document.createElement("tr");
  cell(tr,(d.objeto||"Objeto não informado")+" · "+d.id);
  cell(tr,(d.orgao||"Não informado")+" · "+(d.municipio||"CE"));
  cell(tr,d.encerramentoProposta?String(d.encerramentoProposta).slice(0,16).replace("T"," "):"Não informado");
  cell(tr,money(d.valorEstimado?.valor));
  cell(tr,d.situacaoPNCP);
  cell(tr,d.statusEnriquecimentoItens==="COMPLETO"?(d.resumoItensPNCP?.totalItens||0)+" itens coletados":"Não coletados");
  action(tr,"Ver no radar",()=>openPregao(d.id));
  $("gov84Body").appendChild(tr);
 }
}
function openPregao(id){
 setTab(tabs[0]);
 const busca=$("busca"),scope=$("escopo"),natureza=$("natureza");
 if(scope)scope.value="todos";
 if(natureza)natureza.value="";
 if(busca)busca.value=id;
 if(typeof filtrar==="function")filtrar();
 const results=$("results");if(results)results.scrollIntoView({behavior:"smooth",block:"start"});
}
function renderOrgaos(list){
 const agg=new Map();
 for(const d of list){const k=(d.cnpjOrgao||d.orgao||"Não informado");
  let x=agg.get(k);if(!x){x={nome:d.orgao||"Não informado",cnpj:d.cnpjOrgao,mun:new Set(),total:0,enriq:0};agg.set(k,x)}
  x.total++;if(d.municipio)x.mun.add(d.municipio);
  if(d.statusEnriquecimentoItens==="COMPLETO")x.enriq++;
 }
 setHead(["Órgão / CNPJ","Municípios","Pregões no escopo","Com itens coletados","Ação"]);
 const groups=[...agg.values()].sort((a,b)=>b.total-a.total);
 for(const x of groups.slice(0,limit)){
  const tr=document.createElement("tr");cell(tr,x.nome+" · "+(x.cnpj||"CNPJ não informado"));
  cell(tr,[...x.mun].slice(0,4).join(", ")+(x.mun.size>4?"…":""));
  cell(tr,fmt.format(x.total));cell(tr,fmt.format(x.enriq));
  action(tr,"Ver pregões",()=>{orgSelected=x.nome;aba="Produtos";$("gov84Query").value="";setTab("Produtos",true)});
  $("gov84Body").appendChild(tr);
 }
 return groups.length;
}
function renderConcorrencia(){
 // Esta amostra historica nao pode ser contabilizada como universo do radar.
 const q=norm($("gov84Query").value);
 const rs=historico.registros.filter(r=>!q||norm([r.produto,r.fornecedor,r.orgao,r.processo].join(" ")).includes(q));
 setHead(["Produto / Pregão histórico","Órgão","Fornecedor","Resultado oficial","Valor homologado / un.","Data resultado"]);
 for(const r of rs.slice(0,limit)){
  const tr=document.createElement("tr");cell(tr,(r.produto||"Produto não informado")+" · "+r.processo);
  cell(tr,r.orgao);cell(tr,r.fornecedor||"Não informado");
  cell(tr,r.situacao||"Não informada");cell(tr,money(r.valor));cell(tr,r.data||"Não informada");
  $("gov84Body").appendChild(tr);
 }
 return rs.length;
}
function render(){
 if(aba===tabs[0])return;
 const base=scopeList(),list=filteredRows();
 $("gov84Count").textContent=fmt.format(base.length);
 $("gov84Matched").textContent=fmt.format(list.length);
 $("gov84Verified").textContent=fmt.format(list.filter(x=>x.statusEnriquecimentoItens==="COMPLETO").length);
 $("gov84Body").replaceChildren();
 let count=list.length;
 if(aba==="Órgãos")count=renderOrgaos(list);
 else if(aba==="Concorrência")count=renderConcorrencia();
 else renderPregoes(list);
 $("gov84More").hidden=limit>=count;
 $("gov84Status").textContent=fmt.format(Math.min(limit,count))+" de "+fmt.format(count)+" registros exibidos";
 $("gov84ScopeNote").textContent="Fonte principal: "+fmt.format(pregoes.length)+" pregões locais";
 $("gov84Description").textContent=aba==="Produtos"?
  "Pesquise linhas de produtos e processos. A classificação por palavras do objeto é preliminar; somente os itens PNCP coletados comprovam o conteúdo. Cada linha é um pregão.":
 aba==="Órgãos"?
  "Órgãos compradores agrupados por identificador dentro do escopo selecionado. Clique em Ver pregões para examinar os processos vinculados.":
 aba==="Concorrência"?
  "Resultados oficiais HISTÓRICOS recuperados na amostra POC-79; cobertura parcial, independente do filtro temporal do radar. Não representa todos os concorrentes nem os lances da disputa.":
  "Pesquisa textual nos pregões locais, com correspondência por objeto, órgão, município, ID e itens oficiais já coletados. Não há integração de IA externa nesta versão.";
 $("gov84Footer").textContent=aba==="Concorrência"?
  "Amostra POC-79: "+fmt.format(historico.registros.length)+" resultados identificados. Não somar registros cancelados como vitórias vigentes.":
  "Uma linha por pregão. Exibição paginada sem limitar o universo de pesquisa; cobertura histórica PNCP ainda parcial.";
 // Na concorrencia os KPIs da base refletem o escopo do radar, nao a amostra histórica.
}
function setTab(t,preserve=false){
 if(!tabs.includes(t))return;
 if(!preserve){orgSelected="";$("gov84Query").value="";limit=50}
 aba=t;for(const b of nav.querySelectorAll("button"))b.setAttribute("aria-selected",String(b.dataset.tab===t));
 const isRadar=t===tabs[0];radar.hidden=!isRadar;panel.hidden=isRadar;
 if(!isRadar){$("gov84Title").textContent=t==="Pesquisa"?"Pesquisa de licitações":t;render()}
}
for(const b of nav.querySelectorAll("button"))b.addEventListener("click",()=>setTab(b.dataset.tab));
for(const id of ["gov84Query","gov84Scope","gov84Class"])$(id).addEventListener(id==="gov84Query"?"input":"change",()=>{limit=50;orgSelected="";render()});
$("gov84More").addEventListener("click",()=>{limit+=50;render()});
$("gov84Clear").addEventListener("click",()=>{$("gov84Query").value="";$("gov84Class").value="";orgSelected="";limit=50;render()});
$("gov84Back").addEventListener("click",()=>setTab(tabs[0]));
setTab(tabs[0]);
})();
</script>'''

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--base",required=True)
 a=p.parse_args()
 base=Path(a.base)
 source=base/"GOV_INTELLIGENCE_RADAR_V15_INTEGRAL.html"
 historico=base/"dados"/"poc79_pesquisa_produtos_arilub.json"
 output=base/"GOV_INTELLIGENCE_RADAR_V15_ABAS_POC84.html"
 if not source.is_file():raise FileNotFoundError("Radar V1.5 integral nao encontrado")
 s=source.read_text(encoding="utf-8-sig")
 if "gov84Controller" in s:raise ValueError("HTML de entrada ja possui POC84")
 if 'id="embeddedData"' not in s or "gov-intelligence-radar-v15-integral" not in s:
  raise ValueError("Entrada nao corresponde ao Radar V1.5 integral")
 if s.count("</head>")!=1 or s.count("</body>")!=1:
  raise ValueError("HTML nao reconhecido")
 rs=[]
 if historico.is_file():
  doc=json.loads(historico.read_text(encoding="utf-8-sig"))
  if doc.get("schema")!="gov-poc79-amostra-produtos":raise ValueError("Amostra POC79 inesperada")
  for proc in doc.get("processos",[]):
   for item in proc.get("itensCorrespondentes",[]):
    for r in item.get("resultados",[]):
     rs.append({"processo":proc.get("id"),"orgao":proc.get("orgao"),
       "produto":item.get("descricao"),"fornecedor":r.get("nomeRazaoSocialFornecedor"),
       "situacao":r.get("situacaoCompraItemResultadoNome"),"valor":r.get("valorUnitarioHomologado"),
       "data":r.get("dataResultado")})
 blob=json.dumps({"registros":rs},ensure_ascii=False,separators=(",",":"),allow_nan=False)
 blob=blob.replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
 s=s.replace("</head>",CSS+"</head>")
 s=s.replace("</body>",'<script type="application/json" id="gov84Historico">'+blob+"</script>\n"+JS+"\n</body>")
 tmp=output.with_suffix(".html.tmp")
 try:
  with tmp.open("w",encoding="utf-8") as f:
   f.write(s);f.flush();os.fsync(f.fileno())
  os.replace(tmp,output)
 finally:tmp.unlink(missing_ok=True)
 print("=== GOV POC84 - ABAS SEM ALTERAR RADAR ORIGINAL ===")
 print("ENTRADA:",source)
 print("REGISTROS HISTORICOS DE RESULTADOS DA AMOSTRA:",len(rs))
 print("NOVO HTML:",output)
 print("RADAR V1.4/V1.5 ORIGINAL, SQLITE E TAREFA: INALTERADOS")
 print("IMPORTANTE: ANALISES SOBRE SNAPSHOT; IA EXTERNA E RESULTADOS HISTORICOS INTEGRAIS AINDA NAO DISPONIVEIS")
 return 0

if __name__=="__main__":
 try:sys.exit(main())
 except (OSError,ValueError,TypeError,RuntimeError) as e:
  print("PARADA SEGURA:",type(e).__name__,str(e),file=sys.stderr)
  sys.exit(1)
