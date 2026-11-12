"""Testes de navegador com Chromium + Playwright. API interceptada; sem acesso a produção."""
from pathlib import Path
import json, time
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).parent
qs=[{'id':i,'bloco':f'BLOCO {(i-1)//10+1}','tipo':'multipla' if i%2 else 'aberta','texto':f'Questão fictícia {i}','alternativas':{'A':'Opção A','B':'Opção B'}} for i in range(1,31)]
class Mock:
    def __init__(self, seconds=1500, timeout_fail=False):
        self.answers={};self.seconds=seconds;self.calls=[];self.timeout_fail=timeout_fail;self.timeout_calls=0
    def response(self,url,method,body):
        if method=='GET':
            if 'action=validate' in url:d={'ok':True,'candidato':{'nome':'Candidato fictício'}}
            elif 'action=start' in url:d={'ok':True,'candidato':{'nome':'Candidato fictício'},'questoes':qs,'respostasExistentes':self.answers,'tempo':{'restanteSeg':self.seconds,'expirado':False}}
            elif 'action=painel' in url:
                h=['ID','CANDIDATO','GRUPO','STATUS DO FLUXO','RESULTADO ASSESSMENT','ÍNDICE EVIDÊNCIA*','PONTOS A VALIDAR','FICHA','ENTREVISTA','RESULTADO ENTREVISTA','PARECER PRÉVIO','DECISÃO HUMANA']
                d={'ok':True,'headers':h,'candidatos':[dict(zip(h,['ARI-9001','Fictício A','','ASSESSMENT CONCLUÍDO','E3: 1',80,1,'ANÁLISE PRONTA','','','',''])),dict(zip(h,['ARI-9002','Fictício B','','ASSESSMENT EXPIRADO — INCOMPLETO','10/30','','','INCOMPLETO — NÃO CLASSIFICAR','','','',''])),dict(zip(h,['ARI-9003','Fictício C','','CONVITE ENVIADO','','','','PENDENTE','','','',''])),dict(zip(h,['ARI-9004','Fictício D','','ASSESSMENT INICIADO','','','','PENDENTE','','','','']))]}
            else:d={'ok':False}
        else:
            p=json.loads(body);a=p['action'];self.calls.append(a)
            if a in ('saveProgress','saveBlock'):
                for x in p['respostas']:
                    if x.get('clear'):self.answers.pop(str(x['idQuestao']),None)
                    else:self.answers[str(x['idQuestao'])]=x
                d={'ok':True,'respondidas':len(self.answers),'total':30}
            elif a=='finish':d={'ok':len(self.answers)==30,'completo':len(self.answers)==30,'respondidas':len(self.answers),'total':30}
            elif a=='timeout':
                self.timeout_calls+=1
                if self.timeout_fail and self.timeout_calls==1:
                    return {"mockNetworkError":True}
                d={'ok':True,'expirado':len(self.answers)!=30,'completo':len(self.answers)==30,'respondidas':len(self.answers),'total':30}
            else:d={'ok':False,'codigo':'ACAO_INVALIDA'}
        return d

def page_mock(b,m,name='index.html'):
    p=b.new_page();p.expose_function('mockApi',m.response)
    html=(ROOT/name).read_text().replace("const token = new URLSearchParams(location.search).get('t') || '';","const token = 'TESTE-FICTICIO';")
    mock_script="""<script>Object.defineProperty(window,'sessionStorage',{value:{_:{},getItem(k){return this._[k]||null},setItem(k,v){this._[k]=v},removeItem(k){delete this._[k]}}});window.fetch=async(url,opts={})=>{const d=await window.mockApi(url,opts.method||'GET',opts.body||'');if(d.mockNetworkError)throw new Error('Falha de rede simulada');return {json:async()=>d,text:async()=>JSON.stringify(d)}};</script>"""
    html=html.replace('<script>',mock_script+'<script>',1)
    p.set_content(html,wait_until='domcontentloaded');return p

def launch(b,m):
    p=page_mock(b,m);p.locator('#startBtn').click();p.locator('#assessment').wait_for(state='visible');return p

def wait_count(p,n):p.wait_for_function(f"document.querySelector('#saveStatus').textContent.includes('{n}/30')")
def answer_block(p,first):
    for i in range(first,first+10):
        if i%2:p.locator(f'input[name=q{i}][value=A]').check()
        else:p.locator(f'textarea[name=q{i}]').fill('Resposta fictícia completa')

with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    m=Mock();p=launch(b,m);p.locator('input[name=q1][value=A]').check();wait_count(p,1);assert m.answers['1']['alternativa']=='A';print('OK — salvamento automático por questão e confirmação real')
    p.locator('textarea[name=q2]').fill('Texto inicial');wait_count(p,2);p.locator('textarea[name=q2]').fill('');wait_count(p,1);assert '2' not in m.answers;print('OK — edição/limpeza refletida na contagem')
    answer_block(p,1);p.locator('#nextBtn').click();p.locator('#blockTitle').get_by_text('Bloco 2 de 3').wait_for();assert len(m.answers)==10
    p.close();p=launch(b,m);p.locator('#blockTitle').get_by_text('Bloco 2 de 3').wait_for();print('OK — retomada após recarregar sem perder bloco confirmado')
    answer_block(p,11);p.locator('#nextBtn').click();p.locator('#blockTitle').get_by_text('Bloco 3 de 3').wait_for();answer_block(p,21);p.locator('#nextBtn').click();p.locator('#done').wait_for(state='visible');assert len(m.answers)==30 and '30/30' in p.locator('#done').inner_text();print('OK — navegação e conclusão de 30 questões')
    p.close()
    m=Mock(seconds=4,timeout_fail=True);p=launch(b,m);p.locator('input[name=q1][value=A]').check();wait_count(p,1);p.locator('#retryTimeout').wait_for(timeout=10000);assert not p.locator('#done').is_visible();p.locator('#retryTimeout').click();p.locator('#done').wait_for(state='visible');assert '1/30' in p.locator('#done').inner_text() and 'parcialmente' in p.locator('#done').inner_text();print('OK — falha de rede no timeout não exibe falso sucesso; nova tentativa confirma parcial')
    p.close()
    m=Mock();p=page_mock(b,m,'painel.html');p.locator('#key').fill('chave fictícia');p.locator('#enter').click();p.locator('#app').wait_for(state='visible');assert p.locator('#mConc').inner_text()=='1' and p.locator('#mExp').inner_text()=='1' and p.locator('#mNao').inner_text()=='1' and p.locator('#mAnd').inner_text()=='1';print('OK — painel distingue completo, expirado, em andamento e não iniciado')
    b.close()
print('TOTAL: 6 testes de navegador aprovados')
