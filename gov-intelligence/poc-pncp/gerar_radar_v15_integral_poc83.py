#!/usr/bin/env python3
"""POC-83: constroi Radar V1.5 INTEGRAL preservando a interface V1.4 original.

Leitura template V1.4 + exportacao integral POC82. Gera novo HTML offline,
nunca sobrescreve original, SQLite, PIF, Comercial ou agendamentos.
"""
import argparse,json,os,sys
from pathlib import Path

def trocar(s,antes,depois,exato=1):
 n=s.count(antes)
 if n!=exato:raise ValueError(f"Template inesperado: esperado {exato} ocorrencias, encontrado {n}: {antes[:90]}")
 return s.replace(antes,depois)

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument("--base",required=True)
 args=ap.parse_args()
 base=Path(args.base)
 source=base/"dados"/"radar_v15_integral_poc82.json"
 template=base/"radar_v1_local.html"
 dest=base/"GOV_INTELLIGENCE_RADAR_V15_INTEGRAL.html"
 if not template.is_file() or not source.is_file():raise FileNotFoundError("Template V1.4 ou JSON POC82 nao encontrado")
 data=json.loads(source.read_text(encoding="utf-8-sig"))
 if data.get("schema")!="gov-intelligence-radar-v15-integral":raise ValueError("Schema POC82 inesperado")
 rows=data.get("candidatos")
 if not isinstance(rows,list) or len(rows)!=data.get("contratacoesBase") or len({r.get("id") for r in rows})!=len(rows):
  raise ValueError("Exportacao integral com contagem ou IDs inconsistentes")
 s=template.read_text(encoding="utf-8-sig")
 s=trocar(s,"Radar V1.4","Radar V1.5",2)
 s=trocar(s,"Consulta local de dados oficiais PNCP • abrangência CE • modalidade pregão","Pesquisa integral dos pregões armazenados • Ceará • dados oficiais PNCP")
 s=trocar(s,"Na apresentação, os dados podem ser incorporados ao HTML. Para atualizar manualmente, selecione preferencialmente <code>radar_v1_candidatos_itens_poc57.json</code> (POC-57). A versão POC-52 continua compatível, mas não contém itens. O arquivo é lido no próprio navegador: esta interface não transmite informações pela internet.",
 "Base integral do SQLite incorporada ao HTML. Para atualizar manualmente, carregue <code>radar_v15_integral_poc82.json</code>. A base local não comprova cobertura de todos os pregões publicados no PNCP, pois o histórico de 90 dias ainda está sendo recuperado. Este HTML não se atualiza sozinho.")
 s=trocar(s,"cada resultado é um <strong>candidato preliminar</strong>, não uma oportunidade comercial aprovada.",
 "cada registro é um <strong>pregão armazenado no SQLite</strong>, não uma oportunidade comercial aprovada.")
 s=trocar(s,"<strong id=\"ncand\">—</strong><span>Candidatos no snapshot</span>",
 "<strong id=\"ncand\">—</strong><span>Pregões carregados para consulta</span>")
 s=trocar(s,"<strong id=\"nvis\">—</strong><span>Resultados filtrados</span>",
 "<strong id=\"nvis\">—</strong><span>Pregões encontrados nos filtros</span>")
 s=trocar(s,"<h2>Pesquisar candidatos</h2>","<h2>Pesquisar pregões na base</h2>")
 s=trocar(s,'<option value="vencido">Vencido desde a extração</option>',
 '<option value="vencido">Prazo encerrado</option><option value="indeterminado">Prazo indeterminado</option>')
 s=trocar(s,'<option value="orgao">Órgão A–Z</option>',
 '<option value="orgao">Órgão A–Z</option><option value="publicacao">Publicação mais recente</option><option value="prazo_ultimo">Encerramento mais distante</option>')
 s=trocar(s,'<select id="municipio" aria-label="Município"><option value="">Todos os municípios</option></select>',
 '<select id="municipio" aria-label="Município"><option value="">Todos os municípios</option></select>\n'
 '<select id="orgaoFiltro" aria-label="Órgão"><option value="">Todos os órgãos</option></select>\n'
 '<select id="ufFiltro" aria-label="Estado"><option value="">Todas as UFs da base</option></select>\n'
 '<select id="situacaoFiltro" aria-label="Situação oficial"><option value="">Todas as situações oficiais</option></select>\n'
 '<select id="escopo" aria-label="Visão dos processos"><option value="oportunidades">Oportunidades com prazo futuro (padrão)</option><option value="todos">Todos os pregões na base</option><option value="historico">Pregões com prazo encerrado</option><option value="sem_prazo">Prazo não informado</option></select>\n'
 '<input type="date" id="pubInicio" aria-label="Publicação desde" title="Publicação desde">\n'
 '<input type="date" id="pubFim" aria-label="Publicação até" title="Publicação até">')
 s=trocar(s,"<p class=\"muted\" id=\"metadados\"></p>",
 '<p class="muted" id="metadados"></p><p class="notice" id="coberturaAviso">Aguardando carregamento.</p>')
 s=trocar(s,"<section id=\"results\" hidden>",'<section id="results" hidden>')
 s=trocar(s,"grid-template-columns:minmax(200px,2fr) repeat(3,minmax(140px,1fr))","grid-template-columns:repeat(4,minmax(0,1fr))")
 s=trocar(s,'<input type="search" id="busca" placeholder="Objeto, órgão, município ou ID PNCP" aria-label="Pesquisar">',
 '<input type="search" id="busca" placeholder="Objeto, produto, órgão, município ou ID PNCP" aria-label="Pesquisar">')
 s=trocar(s,"<th>Etapa</th>","<th>Etapa / situação</th>")
 s=trocar(s,"<p id=\"pagina\" class=\"muted\"></p>","<p id=\"pagina\" class=\"muted\"></p>")
 s=trocar(s,'if(d.statusEnriquecimentoItens!=="COMPLETO")','if(d.statusEnriquecimentoItens!=="COMPLETO")') if False else s
 # Validacao da origem: todos os registros, inclusive aqueles sem data de encerramento.
 s=trocar(s,'if(!["gov-intelligence-radar-v1-poc52","gov-intelligence-radar-v1-poc57"].includes(d.schema)',
 'if(!["gov-intelligence-radar-v1-poc52","gov-intelligence-radar-v1-poc57","gov-intelligence-radar-v15-integral"].includes(d.schema)')
 s=trocar(s,'||!x.encerramentoProposta||x.statusRadar!=="CANDIDATO_PRELIMINAR"',
 '||(!x.encerramentoProposta&&d.schema!=="gov-intelligence-radar-v15-integral")||x.statusRadar!=="CANDIDATO_PRELIMINAR"')
 s=trocar(s,'if(d.schema==="gov-intelligence-radar-v1-poc57"){',
 'if(d.schema==="gov-intelligence-radar-v1-poc57"||d.schema==="gov-intelligence-radar-v15-integral"){')
 s=trocar(s,'meta?.schema==="gov-intelligence-radar-v1-poc57"','["gov-intelligence-radar-v1-poc57","gov-intelligence-radar-v15-integral"].includes(meta?.schema)')
 s=trocar(s,'el("status").textContent="Radar V1.4 · Base validada: "',
 'el("status").textContent="Radar V1.5 · Base validada: "')
 s=trocar(s,'el("metadados").textContent="Extração: "+formatData(d.geradoEm)+" · Dados podem ter mudado desde a extração · "+d.abrangencia;',
 'el("metadados").textContent="Extração: "+formatData(d.geradoEm)+" · "+d.abrangencia+" · 1 linha por pregão";\n'
 ' el("coberturaAviso").textContent="Base local: "+fmt.format(d.contratacoesBase)+" pregões. O histórico ainda pode ter lacunas; nem todos os itens foram coletados ("+fmt.format(d.enriquecimento?.processosComItensCompletos||0)+" pregões enriquecidos). Situações oficiais e prazos são informações distintas. Aderência comercial: NEUTRO.";')
 s=trocar(s,'el("results").hidden=false;preencherMunicipios();el("municipio").value="";filtrar();',
 'el("results").hidden=false;preencherMunicipios();preencherFiltrosExtras();el("municipio").value="";filtrar();')
 s=trocar(s,'["busca","fase","valor","ordem","municipio","prazo","natureza","itensFiltro"]',
 '["busca","fase","valor","ordem","municipio","prazo","natureza","itensFiltro","orgaoFiltro","ufFiltro","situacaoFiltro","escopo","pubInicio","pubFim"]')
 s=trocar(s,'const q=texto(el("busca").value),fase=el("fase").value,valor=el("valor").value,municipio=el("municipio").value,prazo=el("prazo").value,natureza=el("natureza").value,itensFiltro=el("itensFiltro").value;',
 'const q=texto(el("busca").value),fase=el("fase").value,valor=el("valor").value,municipio=el("municipio").value,prazo=el("prazo").value,natureza=el("natureza").value,itensFiltro=el("itensFiltro").value;\n'
 ' const uf=el("ufFiltro").value,orgao=el("orgaoFiltro").value,situacao=el("situacaoFiltro").value,escopo=el("escopo").value,pubInicio=el("pubInicio").value,pubFim=el("pubFim").value;')
 s=trocar(s,'const valido=Number.isFinite(fim)&&fim>agora;','const valido=Number.isFinite(fim)&&fim>agora;\n'
 ' const atendeEscopo=escopo==="todos"||(escopo==="oportunidades"&&valido&&d.situacaoPNCP==="Divulgada no PNCP")||(escopo==="historico"&&Number.isFinite(fim)&&fim<=agora)||(escopo==="sem_prazo"&&!Number.isFinite(fim));\n'
 ' const publicado=String(d.dataPublicacao||"").slice(0,10);\n'
 ' const atendePublicacao=(!pubInicio||publicado>=pubInicio)&&(!pubFim||publicado<=pubFim);')
 s=trocar(s,'(prazo==="vencido"&&!valido)',
 '(prazo==="vencido"&&Number.isFinite(fim)&&!valido)||(prazo==="indeterminado"&&!Number.isFinite(fim))')
 s=trocar(s,'return atendeItens&&atendeNatureza&&atendePrazo&&(!municipio||d.municipio===municipio)',
 'return atendeEscopo&&atendePublicacao&&atendeItens&&atendeNatureza&&atendePrazo&&(!uf||d.uf===uf)&&(!orgao||d.orgao===orgao)&&(!situacao||d.situacaoPNCP===situacao)&&(!municipio||d.municipio===municipio)')
 s=trocar(s,'case"orgao":visiveis.sort((a,b)=>String(a.orgao||"").localeCompare(String(b.orgao||""),"pt-BR"));break;',
 'case"orgao":visiveis.sort((a,b)=>String(a.orgao||"").localeCompare(String(b.orgao||""),"pt-BR"));break;\n'
 ' case"publicacao":visiveis.sort((a,b)=>String(b.dataPublicacao||"").localeCompare(String(a.dataPublicacao||"")));break;\n'
 ' case"prazo_ultimo":visiveis.sort((a,b)=>String(b.encerramentoProposta||"").localeCompare(String(a.encerramentoProposta||"")));break;')
 s=trocar(s,'default:visiveis.sort((a,b)=>String(a.encerramentoProposta).localeCompare(String(b.encerramentoProposta)));',
 'default:visiveis.sort((a,b)=>String(a.encerramentoProposta||"9999").localeCompare(String(b.encerramentoProposta||"9999")));')
 s=trocar(s,'const etapa=textCell(tr,d.faseTemporal==="PRAZO_EM_CURSO"?"Propostas iniciadas":d.faseTemporal==="ABERTURA_FUTURA"?"Abertura futura":"Indeterminada");',
 'const etapa=textCell(tr,d.faseTemporal==="PRAZO_EM_CURSO"?"Propostas em curso":d.faseTemporal==="ABERTURA_FUTURA"?"Abertura futura":d.faseTemporal==="PRAZO_ENCERRADO"?"Prazo encerrado":"Prazo não determinado");\n'
 ' const situ=document.createElement("small");situ.className="muted";situ.textContent=" · "+(d.situacaoPNCP||"Situação não informada");etapa.appendChild(situ);')
 s=trocar(s,'el("pagina").textContent="Exibindo "+fmt.format(Math.min(limite,visiveis.length))+" de "+fmt.format(visiveis.length)+" candidatos filtrados.";',
 'el("pagina").textContent="Exibindo "+fmt.format(Math.min(limite,visiveis.length))+" de "+fmt.format(visiveis.length)+" pregões filtrados em uma base de "+fmt.format(dados.length)+" pregões. Carregamento em blocos de 50 para desempenho; nenhum pregão é excluído do filtro.";')
 s=trocar(s,'el("avisoTempo").textContent=vencidos?fmt.format(vencidos)+" candidatos com prazo vencido desde a extração; recarregue um snapshot atualizado.":"Prazos comparados ao relógio do computador.";',
 'el("avisoTempo").textContent=fmt.format(vencidos)+" pregões com prazo encerrado na base (independentemente do status oficial). Datas comparadas ao relógio local.";')
 s=trocar(s,'["Órgão",d.orgao],["Triagem por objeto"',
 '["Órgão",d.orgao],["Situação PNCP",d.situacaoPNCP],["Data de publicação",formatData(d.dataPublicacao)],["Triagem por objeto"')
 s=trocar(s,'const fim=Date.parse(d.encerramentoProposta);return Number.isFinite(fim)&&fim<=Date.now()?"VENCIDO_DESDE_SNAPSHOT":"AINDA_NAO_ENCERRADO"',
 'const fim=Date.parse(d.encerramentoProposta);return !Number.isFinite(fim)?"INDETERMINADO":fim<=Date.now()?"VENCIDO_DESDE_SNAPSHOT":"AINDA_NAO_ENCERRADO"')
 s=trocar(s,'const vencidos=dados.filter(x=>estadoTempo(x)==="VENCIDO_DESDE_SNAPSHOT").length;',
 'const vencidos=dados.filter(x=>estadoTempo(x)==="VENCIDO_DESDE_SNAPSHOT").length;')
 s=trocar(s,'const href=linkValido(d.linkPNCP);if(href){','const href=linkValido(d.linkPNCP);if(href){',2) if False else s
 s=trocar(s,'const embeddedNode=document.getElementById("embeddedData");',
 '''function preencherFiltrosExtras(){
 const opcoes=(id,lista,inicial)=>{const e=el(id);e.replaceChildren(new Option(inicial,""));for(const v of [...new Set(lista.filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b),"pt-BR")))e.add(new Option(v,v));};
 opcoes("orgaoFiltro",dados.map(d=>d.orgao),"Todos os órgãos");
 opcoes("ufFiltro",dados.map(d=>d.uf),"Todas as UFs da base");
 opcoes("situacaoFiltro",dados.map(d=>d.situacaoPNCP),"Todas as situações oficiais");
}
const embeddedNode=document.getElementById("embeddedData");''')
 # Corrigir DOM: payload JSON precisa aparecer ANTES do script principal.
 marcador="<!-- GOV_RADAR_EMBEDDED_JSON_V14 -->"
 if s.count(marcador)!=1:raise ValueError("Marcador incorporacao ausente")
 s=trocar(s,marcador,"")
 blob=json.dumps(data,ensure_ascii=False,separators=(",",":"),allow_nan=False)
 blob=blob.replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
 s=trocar(s,'<script>\n"use strict";',
 '<script id="embeddedData" type="application/json">'+blob+'</script>\n<script>\n"use strict";')
 # Arquivo .html separado: auditoria e revisao visual antes de considerar V1.5 homologada.
 out_tmp=dest.with_name(dest.name+".tmp")
 try:
  with out_tmp.open("w",encoding="utf-8") as f:
   f.write(s);f.flush();os.fsync(f.fileno())
  os.replace(out_tmp,dest)
 finally:out_tmp.unlink(missing_ok=True)
 print("=== GOV POC83 - RADAR V1.5 INTEGRAL OFFLINE ===")
 print("PREGÕES INTEGRADOS:",len(rows))
 print("PROCESSOS COM ITENS PNCP:",data["enriquecimento"]["processosComItensCompletos"])
 print("ITENS PNCP:",data["enriquecimento"]["itensTotais"])
 print("HTML:",dest)
 print("BYTES:",dest.stat().st_size)
 print("BASE DE DADOS, RADAR V1.4 E AGENDAMENTO: INALTERADOS")
 print("AVISO: Este HTML e um snapshot; nao atualiza automaticamente apos a geracao.")
 return 0

if __name__=="__main__":
 try:sys.exit(main())
 except (OSError,ValueError,TypeError,RuntimeError) as e:
  print("PARADA SEGURA:",type(e).__name__,str(e),file=sys.stderr)
  sys.exit(1)
