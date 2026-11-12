/**

 * ============================================================

 * ARILUB — PROCESSO SELETIVO | ASSESSMENT v2.0

 * Vaga: Assistente Comercial — Fortaleza/CE

 * ============================================================

 *

 * Responsabilidades:

 * - Gerar tokens individuais

 * - Montar links individuais

 * - Validar acesso

 * - Registrar início

 * - Salvar respostas progressivamente

 * - Concluir assessment

 * - Bloquear duplicidade

 * - Registrar eventos no LOG

 *

 * IMPORTANTE:

 * A decisão de contratação permanece humana.

 * O tempo de realização é registrado para controle, não para

 * decisão automática.

 * ============================================================

 */

const ARILUB = {

  VERSION: 'v2.1',

  SHEETS: {

    CONFIG: 'CONFIG',

    CANDIDATOS: 'CANDIDATOS',

    AVALIACAO: 'AVALIACAO',

    RESPOSTAS: 'RESPOSTAS',

    ANALISE: 'ANALISE',

    CONTRAPROVAS: 'CONTRAPROVAS',

    ENTREVISTAS: 'ENTREVISTAS',

    LOG: 'LOG',

    MATRIZ_ADERENCIA: 'MATRIZ_ADERENCIA',

    REGRAS_MOTOR: 'REGRAS_MOTOR',

    PAINEL: 'PAINEL'

  },

  STATUS: {

    CONVIDAR: 'CONVIDAR',

    CONVITE_ENVIADO: 'CONVITE ENVIADO',

    INICIADO: 'ASSESSMENT INICIADO',

    CONCLUIDO: 'ASSESSMENT CONCLUÍDO',
    EXPIRADO: 'ASSESSMENT EXPIRADO — INCOMPLETO',

    ANALISE: 'ANÁLISE CONCLUÍDA',

    ENTREVISTA: 'ENTREVISTA',

    FINALISTA: 'FINALISTA',

    RESERVA: 'RESERVA',

    ENCERRADO: 'ENCERRADO'

  }

};

/* ============================================================

   1. UTILIDADES

   ============================================================ */

function getSS_() {

  const ativa = SpreadsheetApp.getActiveSpreadsheet();
  if (ativa) return ativa;
  const id = PropertiesService.getScriptProperties().getProperty('ARILUB_PLANILHA_V22');
  if (!id) throw new Error('PLANILHA_NAO_CONFIGURADA_V22');
  return SpreadsheetApp.openById(id);

}

function getSheet_(name) {

  const sheet = getSS_().getSheetByName(name);

  if (!sheet) {

    throw new Error('Aba não encontrada: ' + name);

  }

  return sheet;

}

function getHeaders_(sheet) {

  if (sheet.getLastColumn() === 0) return [];

  return sheet

    .getRange(1, 1, 1, sheet.getLastColumn())

    .getValues()[0]

    .map(v => String(v).trim());

}

function headerMap_(sheet) {

  const headers = getHeaders_(sheet);

  const map = {};

  headers.forEach((h, i) => {

    if (h) map[h] = i + 1;

  });

  return map;

}

function normalize_(value) {

  return String(value == null ? '' : value)

    .trim()

    .toUpperCase();

}

function json_(obj) {

  return ContentService

    .createTextOutput(JSON.stringify(obj))

    .setMimeType(ContentService.MimeType.JSON);

}

function now_() {

  return new Date();

}

function isoDate_(date) {

  if (!date) return '';

  return Utilities.formatDate(

    new Date(date),

    Session.getScriptTimeZone(),

    "yyyy-MM-dd'T'HH:mm:ss"

  );

}

/* ============================================================

   2. CONFIGURAÇÃO

   ============================================================ */

function getConfig_() {

  const sheet = getSheet_(ARILUB.SHEETS.CONFIG);

  const values = sheet

    .getDataRange()

    .getValues();

  const config = {};

  values.forEach(row => {

    const parametro = String(row[1] || '').trim();

    if (parametro) {

      config[parametro] = row[2];

    }

  });

  return config;

}

function validarConfiguracao() {

  const config = getConfig_();

  const obrigatorios = [

    'TOTAL_QUESTOES',

    'NOME_VAGA',

    'NOME_EMPRESA',

    'VERSAO_ASSESSMENT',

    'STATUS_SISTEMA',

    'BLOQUEAR_DUPLICIDADE'

  ];

  const faltando = obrigatorios.filter(k =>

    config[k] === '' ||

    config[k] === null ||

    typeof config[k] === 'undefined'

  );

  if (faltando.length) {

    throw new Error(

      'Parâmetros ausentes em CONFIG: ' +

      faltando.join(', ')

    );

  }

  return {

    ok: true,

    versao: config.VERSAO_ASSESSMENT,

    status: config.STATUS_SISTEMA,

    totalQuestoes: Number(config.TOTAL_QUESTOES)

  };

}

/* ============================================================

   3. TOKEN

   ============================================================ */

function gerarToken_() {

  return Utilities

    .getUuid()

    .replace(/-/g, '')

    .substring(0, 16)

    .toUpperCase();

}

function gerarTokens() {

  const sheet = getSheet_(ARILUB.SHEETS.CANDIDATOS);

  const map = headerMap_(sheet);

  if (!map.ID_CANDIDATO) {

    throw new Error('Coluna ID_CANDIDATO não encontrada.');

  }

  if (!map.TOKEN) {

    throw new Error('Coluna TOKEN não encontrada.');

  }

  const lastRow = sheet.getLastRow();

  if (lastRow < 2) {

    return 'Nenhum candidato encontrado.';

  }

  const tokensExistentes = new Set();

  const tokenValues = sheet

    .getRange(2, map.TOKEN, lastRow - 1, 1)

    .getValues();

  tokenValues.forEach(r => {

    if (r[0]) tokensExistentes.add(String(r[0]));

  });

  let gerados = 0;

  for (let row = 2; row <= lastRow; row++) {

    const id = sheet

      .getRange(row, map.ID_CANDIDATO)

      .getValue();

    if (!id) continue;

    let token = sheet

      .getRange(row, map.TOKEN)

      .getValue();

    if (!token) {

      do {

        token = gerarToken_();

      } while (tokensExistentes.has(token));

      tokensExistentes.add(token);

      sheet

        .getRange(row, map.TOKEN)

        .setValue(token);

      gerados++;

      log_(

        id,

        'TOKEN_GERADO',

        'Token individual criado.',

        '',

        token

      );

    }

  }

  return gerados + ' token(s) gerado(s).';

}

/* ============================================================

   4. LINKS INDIVIDUAIS

   ============================================================ */

function prepararLinks() {

  const config = getConfig_();

  const baseUrl =

    String(config.GITHUB_PAGES_URL || '').trim();

  if (!baseUrl) {

    throw new Error(

      'GITHUB_PAGES_URL ainda não foi preenchida na CONFIG.'

    );

  }

  const sheet = getSheet_(ARILUB.SHEETS.CANDIDATOS);

  const map = headerMap_(sheet);

  if (!map.TOKEN || !map.LINK_AVALIACAO) {

    throw new Error(

      'As colunas TOKEN e LINK_AVALIACAO são obrigatórias.'

    );

  }

  const lastRow = sheet.getLastRow();

  let criados = 0;

  for (let row = 2; row <= lastRow; row++) {

    const token =

      sheet.getRange(row, map.TOKEN).getValue();

    if (!token) continue;

    const link =

      baseUrl.replace(/\/$/, '') +

      '/?t=' +

      encodeURIComponent(token);

    sheet

      .getRange(row, map.LINK_AVALIACAO)

      .setValue(link);

    criados++;

  }

  return criados + ' link(s) preparado(s).';

}

/* ============================================================

   5. LOCALIZAR CANDIDATO

   ============================================================ */

function findCandidateByToken_(token) {

  if (!token) return null;

  const sheet =

    getSheet_(ARILUB.SHEETS.CANDIDATOS);

  const map = headerMap_(sheet);

  if (!map.TOKEN) {

    throw new Error(

      'Coluna TOKEN não encontrada em CANDIDATOS.'

    );

  }

  const lastRow = sheet.getLastRow();

  if (lastRow < 2) return null;

  const values =

    sheet.getRange(

      2,

      1,

      lastRow - 1,

      sheet.getLastColumn()

    ).getValues();

  for (let i = 0; i < values.length; i++) {

    const candidateToken =

      String(values[i][map.TOKEN - 1] || '').trim();

    if (candidateToken === String(token).trim()) {

      const obj = {

        row: i + 2

      };

      Object.keys(map).forEach(header => {

        obj[header] =

          values[i][map[header] - 1];

      });

      return obj;

    }

  }

  return null;

}

/* ============================================================

   6. VALIDAÇÃO DE TOKEN

   ============================================================ */

function validarToken(token) {

  try {

    const config = getConfig_();

    const candidato =

      findCandidateByToken_(token);

    if (!candidato) {

      return {

        ok: false,

        codigo: 'TOKEN_INVALIDO',

        mensagem:

          'Este link de participação não é válido.'

      };

    }

    const status =

      normalize_(candidato.STATUS);

    if (status === normalize_(ARILUB.STATUS.EXPIRADO)) return {ok:false,codigo:'TEMPO_ESGOTADO',mensagem:'Sua avaliação foi encerrada por tempo. Contate a equipe de seleção.'};

    const bloquear =

      normalize_(config.BLOQUEAR_DUPLICIDADE) === 'SIM';

    if (

      bloquear &&

      (

        status === normalize_(ARILUB.STATUS.CONCLUIDO) ||
          status === normalize_(ARILUB.STATUS.EXPIRADO) ||

        status === normalize_(ARILUB.STATUS.ANALISE) ||

        status === normalize_(ARILUB.STATUS.ENTREVISTA) ||

        status === normalize_(ARILUB.STATUS.FINALISTA) ||

        status === normalize_(ARILUB.STATUS.RESERVA) ||

        status === normalize_(ARILUB.STATUS.ENCERRADO)

      )

    ) {

      return {

        ok: false,

        codigo: 'JA_CONCLUIDO',

        mensagem:

          'Sua participação já foi registrada.'

      };

    }

    return {

      ok: true,

      candidato: {

        id: candidato.ID_CANDIDATO,

        nome: candidato.NOME

      },

      vaga: config.NOME_VAGA,

      empresa: config.NOME_EMPRESA,

      introducao: config.TEXTO_INTRO,

      totalQuestoes:

        Number(config.TOTAL_QUESTOES || 30),

      tempoReferencia:

        Number(config.TEMPO_LIMITE_MIN || 20),

      versao:

        config.VERSAO_ASSESSMENT || ARILUB.VERSION,

      status: candidato.STATUS

    };

  } catch (e) {

    return {

      ok: false,

      codigo: 'ERRO_INTERNO',

      mensagem:

        'Não foi possível validar o acesso.'

    };

  }

}

/* ============================================================

   7. CARREGAR QUESTÕES

   ============================================================ */

function carregarQuestoes_() {

  const sheet =

    getSheet_(ARILUB.SHEETS.AVALIACAO);

  const values =

    sheet.getDataRange().getValues();

  if (values.length < 2) return [];

  const headers =

    values[0].map(v => String(v).trim());

  return values

    .slice(1)

    .filter(row => row[0] !== '')

    .map(row => {

      const q = {};

      headers.forEach((h, i) => {

        q[h] = row[i];

      });

      return {

        id: q.ID_QUESTAO,

        bloco: q.BLOCO,

        ordem: q.ORDEM,

        tipo: q.TIPO,

        texto: q.TEXTO_QUESTAO,

        alternativas: {

          A: q.ALT_A || '',

          B: q.ALT_B || '',

          C: q.ALT_C || '',

          D: q.ALT_D || ''

        }

      };

    });

}

/* ============================================================

   8. INICIAR ASSESSMENT

   ============================================================ */

function iniciarAssessment_(token) {

  const lock =

    LockService.getScriptLock();

  lock.waitLock(10000);

  try {

    const candidato =

      findCandidateByToken_(token);

    if (!candidato) {

      throw new Error('TOKEN_INVALIDO');

    }

    const sheet =

      getSheet_(ARILUB.SHEETS.CANDIDATOS);

    const map = headerMap_(sheet);

    const status =

      normalize_(candidato.STATUS);

    const concluido = Boolean(candidato.DATA_FIM) ||

      status === normalize_(ARILUB.STATUS.CONCLUIDO) ||
          status === normalize_(ARILUB.STATUS.EXPIRADO) ||

      status === normalize_(ARILUB.STATUS.ANALISE) ||

      status === normalize_(ARILUB.STATUS.ENTREVISTA) ||

      status === normalize_(ARILUB.STATUS.FINALISTA) ||

      status === normalize_(ARILUB.STATUS.RESERVA) ||

      status === normalize_(ARILUB.STATUS.ENCERRADO);

    if (concluido) {

      throw new Error('JA_CONCLUIDO');

    }

    if (

      map.DATA_INICIO &&

      !candidato.DATA_INICIO

    ) {

      sheet

        .getRange(

          candidato.row,

          map.DATA_INICIO

        )

        .setValue(now_());

    }

    if (

      status !== normalize_(ARILUB.STATUS.INICIADO)

    ) {

      sheet

        .getRange(

          candidato.row,

          map.STATUS

        )

        .setValue(ARILUB.STATUS.INICIADO);

    }

    if (status !== normalize_(ARILUB.STATUS.INICIADO)) {

      log_(

        candidato.ID_CANDIDATO,

        'ASSESSMENT_INICIADO',

        'Avaliação iniciada.',

        '',

        token

      );

    }

    const candidatoAtualizado = findCandidateByToken_(token);

    const tempo = tempoAssessment_(candidatoAtualizado);

    return {

      ok: true,

      candidato: {

        id: candidato.ID_CANDIDATO,

        nome: candidato.NOME

      },

      questoes: carregarQuestoes_(),

      respostasExistentes:

        getExistingResponses_(candidato.ID_CANDIDATO),

      tempo: tempo

    };

  } finally {

    lock.releaseLock();

  }

}

function tempoAssessment_(candidato) {

  const config = getConfig_();

  const limiteMin = Math.max(1, Number(config.TEMPO_LIMITE_MIN || 25));

  const inicio = candidato.DATA_INICIO ? new Date(candidato.DATA_INICIO) : null;

  const agora = new Date();

  const decorridoSeg = inicio

    ? Math.max(0, Math.floor((agora.getTime() - inicio.getTime()) / 1000))

    : 0;

  const limiteSeg = limiteMin * 60;

  return {

    limiteMin: limiteMin,

    inicioIso: inicio ? inicio.toISOString() : null,

    servidorIso: agora.toISOString(),

    decorridoSeg: decorridoSeg,

    restanteSeg: Math.max(0, limiteSeg - decorridoSeg),

    expirado: !!inicio && decorridoSeg >= limiteSeg

  };

}

function encerrarPorTempo_(token) {
  const lock = LockService.getScriptLock(); lock.waitLock(15000);
  try {
    const c = findCandidateByToken_(token);
    if (!c) throw new Error('TOKEN_INVALIDO');
    const n = contarRespostas_(c.ID_CANDIDATO), total = totalOficialV22_();
    if (terminalV22_(c)) return reciboTerminalV22_(c,n,total);
    if (!c.DATA_INICIO || normalize_(c.STATUS)!==normalize_(ARILUB.STATUS.INICIADO)) return {ok:false,codigo:'NAO_INICIADO'};
    const tempo = tempoAssessment_(c);
    if (!tempo.expirado) return {ok:false,codigo:'TEMPO_AINDA_ATIVO',restanteSeg:tempo.restanteSeg};
    return finalizarV22_(c,n,total,true);
  } finally { lock.releaseLock(); }
}

/* ============================================================

   9. RESPOSTAS EXISTENTES

   ============================================================ */

function getExistingResponses_(idCandidato) {

  const sheet =

    getSheet_(ARILUB.SHEETS.RESPOSTAS);

  const map = headerMap_(sheet);

  const result = {};

  const lastRow = sheet.getLastRow();

  if (lastRow < 2) return result;

  const data =

    sheet

      .getRange(

        2,

        1,

        lastRow - 1,

        sheet.getLastColumn()

      )

      .getValues();

  data.forEach((r, index) => {

    const id =

      String(r[map.ID_CANDIDATO - 1] || '').trim();

    if (id !== String(idCandidato).trim()) return;

    const q =

      String(r[map.ID_QUESTAO - 1] || '').trim();

    if (!q) return;

    result[q] = {

      row: index + 2,

      resposta:

        map.RESPOSTA_BRUTA

          ? r[map.RESPOSTA_BRUTA - 1]

          : '',

      alternativa:

        map.VALOR_ALTERNATIVA

          ? r[map.VALOR_ALTERNATIVA - 1]

          : '',

      tipo:

        map.TIPO

          ? r[map.TIPO - 1]

          : '',

      bloco:

        map.BLOCO

          ? r[map.BLOCO - 1]

          : ''

    };

  });

  return result;

}

/* ============================================================

   10. SALVAR BLOCO

   ============================================================ */

function validarRespostasBloco_(bloco, respostas) {

  if (!Array.isArray(respostas)) {

    throw new Error('RESPOSTAS_INVALIDAS');

  }

  const questoesBloco =

    carregarQuestoes_()

      .filter(q =>

        normalize_(q.bloco) === normalize_(bloco)

      );

  if (!questoesBloco.length) {

    throw new Error('BLOCO_INVALIDO');

  }

  const porId = {};

  respostas.forEach(resp => {

    const id = String(resp.idQuestao || '').trim();

    if (!id) {

      throw new Error('QUESTAO_INVALIDA');

    }

    if (porId[id]) {

      throw new Error('QUESTAO_DUPLICADA_' + id);

    }

    porId[id] = resp;

  });

  questoesBloco.forEach(q => {

    const id = String(q.id);

    const resp = porId[id];

    if (!resp) {

      throw new Error('QUESTAO_NAO_RESPONDIDA_' + id);

    }

    const resposta =

      String(

        resp.resposta == null ? '' : resp.resposta

      ).trim();

    if (!resposta) {

      throw new Error('QUESTAO_NAO_RESPONDIDA_' + id);

    }

    const tipo =

      normalize_(q.tipo);

    if (tipo.indexOf('MULTIPLA') !== -1) {

      const alternativa =

        String(resp.alternativa || '')

          .trim()

          .toUpperCase();

      const permitidas =

        Object.keys(q.alternativas || {})

          .filter(letra =>

            String(q.alternativas[letra] || '').trim() !== ''

          );

      if (!permitidas.includes(alternativa)) {

        throw new Error('ALTERNATIVA_INVALIDA_' + id);

      }

    }

  });

  if (Object.keys(porId).length !== questoesBloco.length) {

    throw new Error('QUANTIDADE_RESPOSTAS_INVALIDA');

  }

  return true;

}

function salvarBloco_(token, bloco, respostas) {
  return salvarProgressoV22_(token,bloco,respostas,true);
}

/* ============================================================

   11. CONTAR RESPOSTAS

   ============================================================ */

function contarRespostas_(idCandidato) {
  const existentes = getExistingResponses_(idCandidato);
  return carregarQuestoes_().filter(q => {
    const r=existentes[String(q.id)];
    if(!r || !String(r.resposta||'').trim()) return false;
    if(normalize_(q.tipo).includes('MULTIPLA')) return Boolean(String((q.alternativas||{})[normalize_(r.alternativa)]||'').trim());
    return true;
  }).length;
}

/* ============================================================

   12. CONCLUIR ASSESSMENT

   ============================================================ */

function concluirAssessment_(token) {
  const lock=LockService.getScriptLock(); lock.waitLock(15000);
  try {
    const c=findCandidateByToken_(token); if(!c) throw new Error('TOKEN_INVALIDO');
    const n=contarRespostas_(c.ID_CANDIDATO),total=totalOficialV22_();
    if(terminalV22_(c)) return reciboTerminalV22_(c,n,total);
    if(!c.DATA_INICIO || normalize_(c.STATUS)!==normalize_(ARILUB.STATUS.INICIADO)) return {ok:false,codigo:'NAO_INICIADO'};
    if(n===total) return finalizarV22_(c,n,total,tempoAssessment_(c).expirado);
    if(tempoAssessment_(c).expirado) return finalizarV22_(c,n,total,true);
    return {ok:false,codigo:'INCOMPLETO',respondidas:n,total:total,mensagem:'Ainda existem questões sem resposta.'};
  } finally { lock.releaseLock(); }
}

/* ============================================================

   12.1 MOTOR AUTOMÁTICO PÓS-ASSESSMENT — v2.1

   ============================================================ */

function getMatrizDimensoes_() {

  const DIMENSOES_OFICIAIS = [

    'Organização', 'Método', 'Interpretação', 'Priorização', 'Comunicação',

    'Interação', 'Potencial comercial', 'Raciocínio', 'Pesquisa', 'Iniciativa',

    'Aprendizagem', 'Adaptabilidade', 'CRM', 'Disciplina de processo',

    'Qualidade de registro'

  ];

  const sheet = getSheet_('DIMENSOES');

  const values = sheet.getDataRange().getValues();

  if (values.length < 2) throw new Error('A aba DIMENSOES não possui dados suficientes.');

  const headers = values[0].map(v => String(v).trim());

  const ix = {};

  headers.forEach((h, i) => ix[h] = i);

  if (typeof ix.DIMENSAO === 'undefined') {

    throw new Error('Coluna DIMENSAO não encontrada na aba DIMENSOES.');

  }

  const porNome = {};

  values.slice(1).forEach(r => {

    const nome = String(r[ix.DIMENSAO] || '').trim();

    // Somente estas 15 dimensões entram no motor.

    // E0, E1, E2, E3, EV e linhas de legenda/escala ficam excluídos.

    if (!DIMENSOES_OFICIAIS.includes(nome)) return;

    porNome[nome] = {

      dimensao: nome,

      questoes: typeof ix.QUESTOES !== 'undefined'

        ? String(r[ix.QUESTOES] || '').trim()

        : '',

      observar: typeof ix.O_QUE_OBSERVAR !== 'undefined'

        ? String(r[ix.O_QUE_OBSERVAR] || '').trim()

        : ''

    };

  });

  const faltantes = DIMENSOES_OFICIAIS.filter(nome => !porNome[nome]);

  if (faltantes.length) {

    throw new Error(

      'Dimensões oficiais ausentes na aba DIMENSOES: ' +

      faltantes.join(', ')

    );

  }

  return DIMENSOES_OFICIAIS.map(nome => porNome[nome]);

}

function removerLinhasCandidato_(sn,id){const s=getSheet_(sn),v=s.getDataRange().getValues();if(v.length<2)return;const c=v[0].map(x=>String(x).trim()).indexOf('ID_CANDIDATO');for(let r=v.length-1;r>0;r--)if(String(v[r][c]).trim()===String(id))s.deleteRow(r+1);}

function respostasCandidato_(id){const s=getSheet_(ARILUB.SHEETS.RESPOSTAS),m=headerMap_(s),o={};if(s.getLastRow()<2)return o;s.getRange(2,1,s.getLastRow()-1,s.getLastColumn()).getValues().forEach(r=>{if(String(r[m.ID_CANDIDATO-1]).trim()!==String(id))return;const q=+r[m.ID_QUESTAO-1];o[q]={tipo:String(r[m.TIPO-1]||'').toLowerCase(),texto:String(r[m.RESPOSTA_BRUTA-1]||''),alt:String(r[m.VALOR_ALTERNATIVA-1]||'').toUpperCase()};});return o;}

function matrizFechadas_(){const s=getSheet_('MATRIZ_ADERENCIA'),v=s.getDataRange().getValues(),h=v[0].map(x=>String(x).trim()),i={};h.forEach((x,n)=>i[x]=n);const o={};v.slice(1).forEach(r=>{const q=+r[i.ID_QUESTAO],a=String(r[i.ALTERNATIVA]||'').toUpperCase();if(q&&a)o[q+'|'+a]={v:+r[i.ADERENCIA_0_3],p:String(r[i.DIMENSAO_PRINCIPAL]||''),pp:+String(r[i.PESO_PRINCIPAL]||1).replace(',','.'),s:String(r[i.DIMENSAO_SECUNDARIA]||''),ps:+String(r[i.PESO_SECUNDARIO]||0).replace(',','.'),l:String(r[i.LEITURA]||'')};});return o;}

function nt_(s){return String(s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9:\s]/g,' ').replace(/\s+/g,' ').trim();}

function hit_(t,g){return g.some(x=>t.indexOf(x)>=0)}

function rubricaAberta_(q,txt){const C={

3:['Organização','Qualidade de registro',[['crm','excel','agenda','planilha','sistema'],['data','prazo','retorno','tarefa'],['acompan','controle','historico']]],

6:['Método','Organização',[['checklist','lista','confer'],['penden','etapa','passo'],['revis','valid','finaliz']]],

8:['Priorização','Raciocínio',[['ontem','atras','retorno'],['proposta','vence hoje','prazo'],['pesquisa','sem prazo'],['impact','urgenc','prior']]],

10:['Organização','Método',[['prior','prazo','urgenc'],['agenda','lista','crm','planej'],['acompan','revis','controle']]],

12:['Comunicação','Iniciativa',[['cliente','retorno','avis','inform'],['prazo','horario','posicao','previs'],['intern','cobr','acompan','penden']]],

14:['Potencial comercial','Pesquisa',[['site','google','linkedin','instagram'],['segment','porte','produto','mercado','perfil'],['necess','potencial','capacidade','qualific']]],

16:['Qualidade de registro','Comunicação',[['context','assunto','necess','interesse'],['comprom','prazo','data','hora','retorno'],['proximo','acao','passo','penden'],['contato','nome','canal']]],

17:['Pesquisa','Iniciativa',[['material','intern','manual'],['internet','google','site','fonte'],['colega','gestor','especialista'],['confirm','valid','segur','confi']]],

19:['Priorização','Interação',[['problema','negociacao','impact','risco'],['informacao simples','rapido','breve'],['avis','esper','retorno','cliente'],['prior','urgenc']]],

20:['Comunicação','Potencial comercial',[['ouvir','escuta','empatia'],['necess','entender','context'],['solucao','recomend','orient'],['retorno','acompan','relacion']]],

22:['CRM','Interpretação',[['historico','ultima','registro'],['responsavel','etapa','status'],['motivo','context','penden'],['prior','segment','proximo']]],

24:['Aprendizagem','Adaptabilidade',[['trein','tutorial','manual','material'],['pratic','test','usar'],['duvida','pergunt','ajuda'],['anot','revis','valid','dominio']]],

25:['Método','Aprendizagem',[['causa','motivo','erro'],['orient','revis','trein','duvida'],['checklist','passo','proced','anot'],['confer','valid','preven']]],

26:['Pesquisa','Raciocínio',[['site','google','linkedin','instagram'],['cnpj','receita','maps'],['noticia','reclam','avaliacao'],['confirm','cruz','valid','fonte']]],

29:['Qualidade de registro','CRM',[['interesse','interessado'],['informacao','duvida','adicional','penden'],['10h','10 h','10:00','10 horas'],['retorno','ligar','contato'],['proximo','acao','tarefa','agend']]],

30:['Aprendizagem','Adaptabilidade',[['process','produto','ferrament'],['estud','material','trein'],['pratic','execut','test'],['duvida','pergunt','feedback'],['autonom','rotina','planej']]]};const c=C[q];if(!c)return null;const t=nt_(txt),n=c[2].reduce((z,g)=>z+(hit_(t,g)?1:0),0),v=!t?0:n<=1?n:n===2?2:3;return{v:v,p:c[0],s:c[1],pp:1.5,ps:.75,ev:v>=2&&t.split(' ').length<5,l:'Q'+q+': '+n+' grupos de evidência.'};}

function nivel_(x){return x<.75?'E0':x<1.5?'E1':x<2.4?'E2':'E3';}

function analisarCandidato_(id){const R=respostasCandidato_(id),M=matrizFechadas_(),D=getMatrizDimensoes_(),A={};D.forEach(d=>A[d.dimensao]={s:0,p:0,e:[],ev:false});function add(d,v,p,ev,e){if(!A[d])return;A[d].s+=v*p;A[d].p+=p;A[d].e.push(e);A[d].ev=A[d].ev||ev;}Object.keys(R).forEach(k=>{const q=+k,r=R[q];if(r.tipo==='multipla'){const m=M[q+'|'+r.alt];if(m){add(m.p,m.v,m.pp,false,'Q'+q+' '+r.alt+': '+m.l);if(m.s)add(m.s,m.v,m.ps,false,'Q'+q+' '+r.alt+' (sec.)');}}else{const a=rubricaAberta_(q,r.texto);if(a){add(a.p,a.v,a.pp,a.ev,a.l);add(a.s,a.v,a.ps,a.ev,a.l+' (sec.)');}}});const crit={'Método':[6,25],'CRM':[22,29],'Qualidade de registro':[16,29],'Aprendizagem':[24,25,30],'Pesquisa':[14,17,26],'Comunicação':[12,20,29],'Priorização':[8,19],'Interpretação':[22]};Object.keys(crit).forEach(d=>{if(!A[d])return;const vv=crit[d].map(q=>R[q]&&R[q].tipo!=='multipla'?rubricaAberta_(q,R[q].texto):null).filter(Boolean).map(x=>x.v);if(vv.length&&Math.min.apply(null,vv)<=1&&A[d].p&&A[d].s/A[d].p>=2)A[d].ev=true;});let soma=0;const dims=D.map(d=>{const a=A[d.dimensao],x=a.p?Math.min(3,a.s/a.p):0;soma+=x;return{dimensao:d.dimensao,indice:x,nivel:nivel_(x),ev:a.ev,evid:a.e.join(' | '),questoes:d.questoes,validar:d.observar};});return{id:id,indice:Math.round(soma/D.length/3*1000)/10,dimensoes:dims};}

function gravarAnalise_(r){const s=getSheet_(ARILUB.SHEETS.ANALISE),m=headerMap_(s);removerLinhasCandidato_(ARILUB.SHEETS.ANALISE,r.id);r.dimensoes.forEach(d=>{const x=new Array(s.getLastColumn()).fill('');x[m.ID_CANDIDATO-1]=r.id;x[m.DIMENSAO-1]=d.dimensao;x[m.NIVEL-1]=d.nivel;x[m.EVIDENCIAS-1]=d.evid;x[m.QUESTOES-1]=d.questoes;x[m.VALIDAR-1]=d.validar;if(m.INDICE_DIMENSAO)x[m.INDICE_DIMENSAO-1]=Math.round(d.indice*100)/100;if(m.EV_FLAG)x[m.EV_FLAG-1]=d.ev?'SIM':'NÃO';s.appendRow(x);});}

function perguntaCP_(d){const m={'Método':'Mostre seu checklist e como evitaria repetir o mesmo erro.','CRM':'Mostre o que consultaria no CRM e registre um próximo contato com data, hora, contexto e ação.','Qualidade de registro':'Escreva ao vivo uma nota de CRM que permita continuidade por outro colega.','Aprendizagem':'Como aprenderia uma ferramenta nova para operar sozinho em cinco dias?','Pesquisa':'Duas fontes divergem sobre uma empresa. Como decide o que usar?','Comunicação':'Sem resposta do setor interno, o que diria ao cliente e quando retornaria?','Interpretação':'Antes de agir em situação pouco clara, o que confirma e com quem?','Priorização':'Ordene retorno atrasado, proposta vencendo hoje e pesquisa sem prazo e justifique.','Organização':'Como controlaria cinco retornos em datas diferentes?'};return m[d]||('Dê um exemplo prático de como atua em '+d+'.');}

function gerarContraprovas_(r){const s=getSheet_(ARILUB.SHEETS.CONTRAPROVAS),m=headerMap_(s),ord={E0:0,E1:1,E2:2,E3:3};removerLinhasCandidato_(ARILUB.SHEETS.CONTRAPROVAS,r.id);const c=r.dimensoes.slice().sort((a,b)=>((b.ev?10:0)+3-ord[b.nivel])-((a.ev?10:0)+3-ord[a.nivel])),sel=[],seen={};c.filter(d=>d.ev||ord[d.nivel]<=1).concat(c.filter(d=>d.nivel==='E2')).forEach(d=>{if(!seen[d.dimensao]&&sel.length<7){seen[d.dimensao]=1;sel.push(d);}});for(let i=0;sel.length<5&&i<c.length;i++)if(!seen[c[i].dimensao]){seen[c[i].dimensao]=1;sel.push(c[i]);}sel.forEach(d=>{const x=new Array(s.getLastColumn()).fill('');x[m.ID_CANDIDATO-1]=r.id;x[m.DIMENSAO-1]=d.dimensao;if(m.ORIGEM)x[m.ORIGEM-1]=d.questoes;if(m.TIPO)x[m.TIPO-1]=d.ev?'VALIDAÇÃO':'APROFUNDAMENTO';if(m.EVIDENCIA)x[m.EVIDENCIA-1]=d.evid.substring(0,500);if(m.RESPOSTA_ORIGINAL_REFERENCIA)x[m.RESPOSTA_ORIGINAL_REFERENCIA-1]='Questões '+d.questoes;if(m.CONTRAPROVA)x[m.CONTRAPROVA-1]=perguntaCP_(d.dimensao);if(m.PRIORIDADE)x[m.PRIORIDADE-1]=(d.ev||ord[d.nivel]<=1)?'ALTA':'MÉDIA';s.appendRow(x);});return sel.length;}

function parecerPrevio_(r){const e3=r.dimensoes.filter(d=>d.nivel==='E3').map(d=>d.dimensao),fr=r.dimensoes.filter(d=>d.nivel==='E0'||d.nivel==='E1').map(d=>d.dimensao),ev=r.dimensoes.filter(d=>d.ev).map(d=>d.dimensao);return'Índice de Evidência '+r.indice+'/100. '+(e3.length?'Evidências fortes em '+e3.slice(0,4).join(', ')+'. ':'')+(fr.length?'Evidências mais frágeis em '+fr.slice(0,4).join(', ')+'. ':'')+(ev.length?'Validar em entrevista: '+ev.slice(0,5).join(', ')+'. ':'')+'Parecer prévio automático; decisão permanece humana.';}

function atualizarPainel_(r,p,n){const s=getSheet_('PAINEL'),last=s.getLastRow();if(last<8)return;const ids=s.getRange(8,1,last-7,1).getValues();let row=0;ids.forEach((x,i)=>{if(String(x[0]).trim()===String(r.id))row=i+8;});if(!row)return;const c={E0:0,E1:0,E2:0,E3:0};let ev=0;r.dimensoes.forEach(d=>{c[d.nivel]++;if(d.ev)ev++;});s.getRange(row,5).setValue('E3: '+c.E3+' | E2: '+c.E2+' | E1: '+c.E1+' | E0: '+c.E0+' | EV: '+ev);s.getRange(row,6).setValue(r.indice);s.getRange(row,7).setValue(ev);s.getRange(row,8).setValue('ANÁLISE PRONTA');s.getRange(row,11).setValue(p);if(!String(s.getRange(row,12).getValue()||'').trim())s.getRange(row,12).setValue('PENDENTE — HUMANA');}

function prepararFichaEntrevista_(id){const s=getSheet_(ARILUB.SHEETS.ENTREVISTAS),m=headerMap_(s);if(s.getLastRow()>=2 && s.getRange(2,m.ID_CANDIDATO,s.getLastRow()-1,1).getValues().some(r=>String(r[0]).trim()===String(id)))return;const x=new Array(s.getLastColumn()).fill('');x[m.ID_CANDIDATO-1]=id;if(m.MICROCASO)x[m.MICROCASO-1]='Cliente A aguarda retorno desde ontem; B precisa de proposta hoje; C pergunta produto desconhecido; D pediu contato quinta. Solicitar ordem, ação, justificativa e registro CRM.';if(m.OBSERVACOES)x[m.OBSERVACOES-1]='Ficha gerada automaticamente; usar contraprovas e julgamento humano.';if(m.STATUS_HUMANO)x[m.STATUS_HUMANO-1]='PENDENTE';s.appendRow(x);}

function prepararPosAssessment_(id){try{const nVal=contarRespostas_(id),tVal=totalOficialV22_();if(nVal!==tVal){return{ok:false,codigo:'ASSESSMENT_INCOMPLETO',respondidas:nVal,total:tVal,erro:'Avaliação incompleta; análise oficial bloqueada.'};}const r=analisarCandidato_(id);gravarAnalise_(r);const n=gerarContraprovas_(r);prepararFichaEntrevista_(id);const p=parecerPrevio_(r);atualizarPainel_(r,p,n);log_(id,'MOTOR_ANALISE_CONCLUIDO','Índice '+r.indice+'; contraprovas '+n+'.','','');return{ok:true,indice:r.indice,contraprovas:n,parecer:p,dimensoes:r.dimensoes};}catch(e){log_(id,'ERRO_POS_ASSESSMENT','Falha no motor.',String(e&&e.message?e.message:e),'');return{ok:false,erro:String(e)};}}

function reprocessarCandidato(id) {

  const candidatoId = String(id || '').trim();

  if (!candidatoId) {

    throw new Error('ID_CANDIDATO não informado.');

  }

  const resultado = prepararPosAssessment_(candidatoId);

  if (!resultado || resultado.ok !== true) {

    throw new Error(

      'Falha ao reprocessar ' + candidatoId + ': ' +

      (resultado && resultado.erro ? resultado.erro : 'erro não identificado')

    );

  }

  if (!resultado.dimensoes || resultado.dimensoes.length !== 15) {

    throw new Error(

      'Homologação bloqueada: esperadas 15 dimensões, recebidas ' +

      (resultado.dimensoes ? resultado.dimensoes.length : 0) + '.'

    );

  }

  return resultado;

}

function reprocessarTeste0004() {

  return reprocessarCandidato('TESTE-0004');

}

function testeMotor0003(){return prepararPosAssessment_('TESTE-0003');}

/* ============================================================

   13. LOG

   ============================================================ */

function log_(

  idCandidato,

  acao,

  detalhe,

  erro,

  token

) {

  try {

    const sheet =

      getSheet_(ARILUB.SHEETS.LOG);

    const config = getConfig_();

    sheet.appendRow([

      now_(),

      idCandidato || '',

      acao || '',

      detalhe || '',

      erro || '',

      token || '',

      config.VERSAO_ASSESSMENT ||

        ARILUB.VERSION

    ]);

  } catch (e) {

    console.error(

      'Falha ao registrar LOG:',

      e

    );

  }

}

/* ============================================================

   14. API — GET

   ============================================================ */

/* ===== PAINEL WEB ADMINISTRATIVO ===== */
function configurarChavePainel() {
  return configurarChavePainel_();
}

function configurarChavePainel_() {
  PropertiesService.getScriptProperties().setProperty('ARILUB_PAINEL_KEY', 'Arilub@123');
  Logger.log('Chave do painel configurada.');
}

function painelApi_(chave) {
  const esperada = String(PropertiesService.getScriptProperties().getProperty('ARILUB_PAINEL_KEY') || 'Arilub@123').trim();
  if (!esperada || String(chave || '').trim() !== esperada) {
    return {ok:false,codigo:'ACESSO_NEGADO',mensagem:'Chave de acesso inválida.'};
  }

  // REGRA v2.3: a aba PAINEL continua sendo a fonte principal.
  // Assim preservamos exatamente os campos que já estavam funcionando.
  // CANDIDATOS é usado apenas para completar IDs que ainda não possuem linha no PAINEL.
  const s = getSheet_(ARILUB.SHEETS.PAINEL || 'PAINEL');
  const lastRow = s.getLastRow();
  const lastCol = Math.max(12, s.getLastColumn());

  let headers = [];
  let candidatos = [];
  if (lastRow >= 8) {
    headers = s.getRange(8,1,1,lastCol).getDisplayValues()[0].map(v => String(v || '').trim());
  }
  const fb = ['ID','CANDIDATO','ORIGEM','STATUS PROCESSO','EVIDÊNCIAS','ÍNDICE','EV','STATUS ASSESSMENT','CONTRAPROVAS','ENTREVISTA','PARECER PRÉVIO','DECISÃO'];
  headers = Array.from({length:lastCol}, (_,i) => headers[i] || fb[i] || ('CAMPO '+(i+1)));

  if (lastRow >= 9) {
    const values = s.getRange(9,1,lastRow-8,lastCol).getDisplayValues();
    candidatos = values
      .filter(r => {
        const id = String(r[0] || '').trim();
        return /^ARI-\d+$/i.test(id);
      })
      .map(r => {
        const o={}; headers.forEach((h,i)=>o[h]=r[i]||''); return o;
      });
  }

  const idsPainel = {};
  candidatos.forEach(o => { const id=String(o[headers[0]]||'').trim(); if(id) idsPainel[id]=true; });

  // Índice da ANALISE, usado SOMENTE para candidatos ausentes da aba PAINEL.
  const analisePorId = {};
  try {
    const a = getSheet_(ARILUB.SHEETS.ANALISE);
    const am = headerMap_(a);
    if (a.getLastRow() >= 2 && am.ID_CANDIDATO) {
      a.getRange(2,1,a.getLastRow()-1,a.getLastColumn()).getDisplayValues().forEach(r => {
        const id=String(r[am.ID_CANDIDATO-1]||'').trim();
        if(id) (analisePorId[id]||(analisePorId[id]=[])).push(r);
      });
    }
    analisePorId.__map = am;
  } catch(err) {
    analisePorId.__map = {};
  }

  // Completa a visão com todos os candidatos reais sem substituir os 21 registros já consolidados.
  const c = getSheet_(ARILUB.SHEETS.CANDIDATOS);
  const cm = headerMap_(c);
  if (c.getLastRow() >= 2 && cm.ID_CANDIDATO) {
    const base = c.getRange(2,1,c.getLastRow()-1,c.getLastColumn()).getDisplayValues();
    base.forEach(r => {
      const id=String(r[cm.ID_CANDIDATO-1]||'').trim();
      if(!/^ARI-\d+$/i.test(id) || idsPainel[id]) return;

      const nome = cm.NOME ? String(r[cm.NOME-1]||'') : '';
      const grupo = cm.GRUPO_SHORTLIST ? String(r[cm.GRUPO_SHORTLIST-1]||'') : (cm.GRUPO ? String(r[cm.GRUPO-1]||'') : (cm.ORIGEM ? String(r[cm.ORIGEM-1]||'') : ''));
      const status = cm.STATUS ? String(r[cm.STATUS-1]||'') : '';
      const ars = analisePorId[id] || [];
      const am = analisePorId.__map || {};
      const cont={E0:0,E1:0,E2:0,E3:0}; let ev=0, soma=0, nidx=0;
      const fortes=[], frageis=[], validar=[];

      ars.forEach(x => {
        const nv=am.NIVEL ? String(x[am.NIVEL-1]||'').trim() : '';
        const dim=am.DIMENSAO ? String(x[am.DIMENSAO-1]||'').trim() : '';
        if(Object.prototype.hasOwnProperty.call(cont,nv)) cont[nv]++;
        if(am.EV_FLAG && normalize_(x[am.EV_FLAG-1])==='SIM'){ ev++; if(dim) validar.push(dim); }
        if(nv==='E3' && dim) fortes.push(dim);
        if((nv==='E0'||nv==='E1') && dim) frageis.push(dim);
        if(am.INDICE_DIMENSAO){
          const z=parseFloat(String(x[am.INDICE_DIMENSAO-1]||'').replace(',','.'));
          if(!isNaN(z)){soma+=z;nidx++;}
        }
      });

      const indice = nidx ? Math.round((soma/nidx)/3*1000)/10 : '';
      const resultado = ars.length ? ('E3: '+cont.E3+' | E2: '+cont.E2+' | E1: '+cont.E1+' | E0: '+cont.E0+' | EV: '+ev) : 'SEM RESULTADO';
      let parecer='';
      if(ars.length){
        parecer='Índice de Evidência '+indice+'/100. '
          +(fortes.length?'Evidências fortes em '+fortes.slice(0,4).join(', ')+'. ':'')
          +(frageis.length?'Evidências mais frágeis em '+frageis.slice(0,4).join(', ')+'. ':'')
          +(validar.length?'Validar em entrevista: '+validar.slice(0,5).join(', ')+'. ':'')
          +'Parecer prévio automático; decisão permanece humana.';
      }

      const o={}; headers.forEach(h=>o[h]='');
      const setAliases=(aliases,val)=>{
        const normal=v=>normalize_(v).normalize("NFD").replace(/[\u0300-\u036f]/g,"");
        const hs=headers.find(h=>aliases.map(normal).includes(normal(h)));
        if(hs) o[hs]=val;
      };
      setAliases(['ID'],id);
      setAliases(['CANDIDATO','NOME'],nome);
      setAliases(['GRUPO','ORIGEM'],grupo);
      setAliases(['STATUS DO FLUXO','STATUS PROCESSO','STATUS'],status);
      setAliases(['RESULTADO ASSESSMENT','EVIDENCIAS'],resultado);
      setAliases(['INDICE EVIDENCIA','INDICE EVIDENCIA*','INDICE'],indice);
      setAliases(['EV','PONTOS A VALIDAR'],ev || '');
      setAliases(['FICHA','STATUS ASSESSMENT'],ars.length?'ANÁLISE PRONTA':'PENDENTE');
      setAliases(['ENTREVISTA'],'NÃO AGENDADA');
      setAliases(['PARECER PREVIO'],parecer);
      setAliases(['DECISAO HUMANA','DECISAO'],ars.length?'PENDENTE — HUMANA':'');
      candidatos.push(o);
      idsPainel[id]=true;
    });
  }

  // V2.2: a completude é derivada das respostas, nunca da existência de uma análise.
  const contagensV22=contagensOficiaisV22_();
  const totalV22=totalOficialV22_();
  const baseV22=c.getDataRange().getValues();
  const statusV22={};
  baseV22.slice(1).forEach(r=>{const id=String(r[cm.ID_CANDIDATO-1]||'').trim();if(id)statusV22[id]={status:String(r[cm.STATUS-1]||''),fim:cm.DATA_FIM?r[cm.DATA_FIM-1]:''};});
  candidatos.forEach(o=>{
    const id=String(o[headers[0]]||'').trim(), n=contagensV22[id]||0, b=statusV22[id];
    if(n===totalV22) return;
    const encerrado=Boolean(b&&(b.fim||normalize_(b.status)===normalize_(ARILUB.STATUS.CONCLUIDO)||normalize_(b.status)===normalize_(ARILUB.STATUS.EXPIRADO)));
    const set=(i,val)=>{if(headers[i])o[headers[i]]=val;};
    if(encerrado)set(3,ARILUB.STATUS.EXPIRADO);
    set(4,n+'/'+totalV22+' respostas válidas');set(5,'');set(6,'');
    set(7,encerrado?'INCOMPLETO — NÃO CLASSIFICAR':'PENDENTE');
    set(8,'');set(10,encerrado?'Avaliação incompleta; resultado histórico não comparável.':'');
    // Decisão humana (coluna 12) nunca é alterada no armazenamento.
  });

  // Ordenação estável por ID para ARI-0001 ... ARI-0026.
  candidatos.sort((a,b)=>String(a[headers[0]]||'').localeCompare(String(b[headers[0]]||''),'pt-BR',{numeric:true}));

  return {ok:true,atualizadoEm:new Date().toISOString(),headers:headers,candidatos:candidatos};
}

function doGet(e) {

  try {

    const action =

      String(

        e.parameter.action || 'validate'

      ).trim();

    if (action === 'painel') {
      return json_(painelApi_(e.parameter.k || e.parameter.key || ''));
    }

    const token =

      String(

        e.parameter.t ||

        e.parameter.token ||

        ''

      ).trim();

    if (!token) {

      return json_({

        ok: false,

        codigo: 'TOKEN_AUSENTE',

        mensagem:

          'Token não informado.'

      });

    }

    if (action === 'validate') {

      return json_(

        validarToken(token)

      );

    }

    if (action === 'start') {

      return json_(

        iniciarAssessment_(token)

      );

    }

    return json_({

      ok: false,

      codigo: 'ACAO_INVALIDA'

    });

  } catch (e) {

    return json_({

      ok: false,

      codigo: 'ERRO_INTERNO',

      mensagem:

        'Não foi possível processar a solicitação.'

    });

  }

}

/* ============================================================

   15. API — POST

   ============================================================ */

function doPost(e) {

  let payload = {};

  try {

    payload =

      JSON.parse(

        e.postData.contents || '{}'

      );

    const action =

      String(

        payload.action || ''

      ).trim();

    const token =

      String(

        payload.token || ''

      ).trim();

    if (!token) {

      return json_({

        ok: false,

        codigo: 'TOKEN_AUSENTE'

      });

    }

    if (action === 'saveProgress') {
      return json_(salvarProgressoV22_(token,payload.bloco,payload.respostas || [],false));
    }

    if (action === 'saveBlock') {

      return json_(

        salvarBloco_(

          token,

          payload.bloco,

          payload.respostas || []

        )

      );

    }

    if (action === 'finish') {

      return json_(

        concluirAssessment_(token)

      );

    }

    if (action === 'timeout') {

      return json_(

        encerrarPorTempo_(token)

      );

    }

    return json_({

      ok: false,

      codigo: 'ACAO_INVALIDA'

    });

  } catch (e) {

    try {

      log_(

        '',

        'ERRO_API',

        payload.action || '',

        e.message || String(e),

        payload.token || ''

      );

    } catch (_) {}

    return json_({

      ok: false,

      codigo: 'ERRO_INTERNO',

      mensagem:

        'Não foi possível processar a solicitação.'

    });

  }

}

/* ============================================================

   16. PREPARAÇÃO DO SISTEMA

   ============================================================ */

function prepararSistema() {

  validarConfiguracao();

  const resultadoTokens =

    gerarTokens();

  let resultadoLinks =

    'Links ainda não gerados.';

  const config = getConfig_();

  if (

    String(

      config.GITHUB_PAGES_URL || ''

    ).trim()

  ) {

    resultadoLinks =

      prepararLinks();

  }

  return {

    ok: true,

    tokens: resultadoTokens,

    links: resultadoLinks

  };

}

/* ============================================================

   17. TESTE INTERNO

   ============================================================ */

function testeSistema() {

  const resultado =

    validarConfiguracao();

  const questoes =

    carregarQuestoes_();

  const sheet =

    getSheet_(ARILUB.SHEETS.CANDIDATOS);

  const map =

    headerMap_(sheet);

  return {

    configuracao: resultado,

    totalQuestoesCarregadas:

      questoes.length,

    possuiToken:

      Boolean(map.TOKEN),

    possuiLink:

      Boolean(map.LINK_AVALIACAO),

    possuiStatus:

      Boolean(map.STATUS),

    versao:

      ARILUB.VERSION

  };

}

/**

 * ============================================================

 * ARILUB — GERAR TOKEN EXCLUSIVAMENTE PARA CANDIDATO DE TESTE

 * ============================================================

 *

 * Atua somente sobre:

 * ID_CANDIDATO = TESTE-0001

 *

 * Não altera os candidatos reais.

 * Se TESTE-0001 já possuir token, mantém o token existente.

 * ============================================================

 */

function gerarTokenTeste() {

  const ID_TESTE = 'TESTE-0001';

  const sheet =

    getSheet_(ARILUB.SHEETS.CANDIDATOS);

  const map =

    headerMap_(sheet);

  // Validação das colunas necessárias

  if (!map.ID_CANDIDATO) {

    throw new Error(

      'Coluna ID_CANDIDATO não encontrada.'

    );

  }

  if (!map.TOKEN) {

    throw new Error(

      'Coluna TOKEN não encontrada.'

    );

  }

  const lastRow =

    sheet.getLastRow();

  if (lastRow < 2) {

    throw new Error(

      'Nenhum candidato encontrado.'

    );

  }

  // Procura SOMENTE o candidato TESTE-0001

  const ids =

    sheet

      .getRange(

        2,

        map.ID_CANDIDATO,

        lastRow - 1,

        1

      )

      .getValues();

  let linhaTeste = null;

  for (let i = 0; i < ids.length; i++) {

    const id =

      String(ids[i][0] || '').trim();

    if (id === ID_TESTE) {

      linhaTeste = i + 2;

      break;

    }

  }

  if (!linhaTeste) {

    throw new Error(

      'Candidato técnico TESTE-0001 não encontrado.'

    );

  }

  // Verifica se já existe token

  const tokenAtual =

    String(

      sheet

        .getRange(

          linhaTeste,

          map.TOKEN

        )

        .getValue() || ''

    ).trim();

  if (tokenAtual) {

    return {

      ok: true,

      id: ID_TESTE,

      token: tokenAtual,

      novoToken: false,

      mensagem:

        'TESTE-0001 já possuía token. Nenhuma alteração foi realizada.'

    };

  }

  // Gera token

  const novoToken =

    gerarToken_();

  sheet

    .getRange(

      linhaTeste,

      map.TOKEN

    )

    .setValue(novoToken);

  // Garante a versão do assessment, caso a coluna exista

  if (map.VERSAO_ASSESSMENT) {

    sheet

      .getRange(

        linhaTeste,

        map.VERSAO_ASSESSMENT

      )

      .setValue(ARILUB.VERSION);

  }

  // Registra no LOG

  log_(

    ID_TESTE,

    'TOKEN_TESTE_GERADO',

    'Token criado exclusivamente para o candidato técnico TESTE-0001.',

    '',

    novoToken

  );

  return {

    ok: true,

    id: ID_TESTE,

    token: novoToken,

    novoToken: true,

    mensagem:

      'Token técnico gerado com sucesso.'

  };

}

function testeSalvarBloco1() {

  const token = '69FE84AE345548BE';

  const respostas = [

    {

      idQuestao: 1,

      tipo: 'multipla',

      resposta: 'B',

      alternativa: 'B'

    },

    {

      idQuestao: 2,

      tipo: 'multipla',

      resposta: 'C',

      alternativa: 'C'

    },

    {

      idQuestao: 3,

      tipo: 'aberta',

      resposta: 'Organizaria os retornos no CRM por data e prioridade, deixando programada a próxima ação.'

    },

    {

      idQuestao: 4,

      tipo: 'multipla',

      resposta: 'B',

      alternativa: 'B'

    },

    {

      idQuestao: 5,

      tipo: 'multipla',

      resposta: 'C',

      alternativa: 'C'

    },

    {

      idQuestao: 6,

      tipo: 'aberta',

      resposta: 'Reviso a atividade, verifico pendências e confirmo se os registros e próximos passos foram realizados.'

    },

    {

      idQuestao: 7,

      tipo: 'multipla',

      resposta: 'C',

      alternativa: 'C'

    },

    {

      idQuestao: 8,

      tipo: 'aberta',

      resposta: 'Primeiro trataria o retorno prometido para ontem, depois a proposta que vence hoje e por último a pesquisa sem prazo, registrando os próximos passos.'

    },

    {

      idQuestao: 9,

      tipo: 'multipla',

      resposta: 'B',

      alternativa: 'B'

    },

    {

      idQuestao: 10,

      tipo: 'aberta',

      resposta: 'Organizo as atividades por prazo e prioridade e acompanho durante o dia o que foi concluído e o que continua pendente.'

    }

  ];

  const resultado = salvarBloco_(

    token,

    'BLOCO 1',

    respostas

  );

  Logger.log(

    JSON.stringify(resultado, null, 2)

  );

  return resultado;

}

function testeFecharAssessment() {

  const token = '69FE84AE345548BE';

  // =========================

  // BLOCO 2 — Questões 11–20

  // =========================

  const bloco2 = [

    { idQuestao: 11, tipo: 'multipla', resposta: 'B', alternativa: 'B' },

    {

      idQuestao: 12,

      tipo: 'aberta',

      resposta: 'Informaria ao cliente que estou aguardando uma informação interna e combinaria um prazo objetivo para retornar.'

    },

    { idQuestao: 13, tipo: 'multipla', resposta: 'C', alternativa: 'C' },

    {

      idQuestao: 14,

      tipo: 'aberta',

      resposta: 'Definiria critérios de potencial, pesquisaria as empresas em fontes confiáveis e organizaria as informações para priorizar os contatos.'

    },

    { idQuestao: 15, tipo: 'multipla', resposta: 'B', alternativa: 'B' },

    {

      idQuestao: 16,

      tipo: 'aberta',

      resposta: 'Registraria contexto, necessidade do cliente, informações relevantes, compromissos assumidos e o próximo passo.'

    },

    {

      idQuestao: 17,

      tipo: 'aberta',

      resposta: 'Consultaria primeiro os materiais disponíveis e fontes confiáveis. Se necessário, confirmaria a informação com alguém da equipe antes de responder.'

    },

    { idQuestao: 18, tipo: 'multipla', resposta: 'C', alternativa: 'C' },

    {

      idQuestao: 19,

      tipo: 'aberta',

      resposta: 'Identificaria a situação mais crítica, daria retorno inicial aos dois clientes e priorizaria o problema que pode comprometer a negociação.'

    },

    {

      idQuestao: 20,

      tipo: 'aberta',

      resposta: 'Um bom atendimento entende a necessidade, comunica com clareza, cumpre os combinados e acompanha o cliente até o próximo passo.'

    }

  ];

  // ========================

  // BLOCO 3 — Questões 21–30

  // =========================

  const bloco3 = [

    { idQuestao: 21, tipo: 'multipla', resposta: 'C', alternativa: 'C' },

    {

      idQuestao: 22,

      tipo: 'aberta',

      resposta: 'Verificaria o histórico, último contato, estágio da oportunidade, compromissos existentes e a próxima ação prevista.'

    },

    { idQuestao: 23, tipo: 'multipla', resposta: 'B', alternativa: 'B' },

    {

      idQuestao: 24,

      tipo: 'aberta',

      resposta: 'Buscaria entender a orientação, consultaria materiais disponíveis, praticaria na ferramenta e tiraria dúvidas específicas.'

    },

    {

      idQuestao: 25,

      tipo: 'aberta',

      resposta: 'Revisaria a causa do erro, confirmaria o procedimento correto e criaria uma forma de conferência para evitar a repetição.'

    },

    {

      idQuestao: 26,

      tipo: 'aberta',

      resposta: 'Utilizaria site da empresa, Google, redes e fontes institucionais ou comerciais confiáveis, organizando as informações encontradas.'

    },

    { idQuestao: 27, tipo: 'multipla', resposta: 'C', alternativa: 'C' },

    { idQuestao: 28, tipo: 'multipla', resposta: 'B', alternativa: 'B' },

    {

      idQuestao: 29,

      tipo: 'aberta',

      resposta: 'Cliente demonstrou interesse. Aguarda informação adicional antes da decisão. Retorno combinado amanhã às 10h. Criar tarefa de retorno para 10h.'

    },

    {

      idQuestao: 30,

      tipo: 'aberta',

      resposta: 'Nas primeiras semanas organizaria meu aprendizado por processos, ferramentas e produtos, praticaria as atividades, registraria dúvidas e buscaria feedback até conseguir executar com autonomia.'

    }

  ];

  // =========================

  // SALVAMENTO

  // =========================

  const resultadoBloco2 =

    salvarBloco_(

      token,

      'BLOCO 2',

      bloco2

    );

  const resultadoBloco3 =

    salvarBloco_(

      token,

      'BLOCO 3',

      bloco3

    );

  // =========================

  // CONFERÊNCIA

  // =========================

  const candidato =

    findCandidateByToken_(token);

  if (!candidato) {

    throw new Error(

      'TESTE-0001 não localizado.'

    );

  }

  const total =

    contarRespostas_(

      candidato.ID_CANDIDATO

    );

  if (total !== 30) {

    throw new Error(

      'Esperadas 30 respostas únicas, mas foram encontradas ' +

      total +

      '. Assessment NÃO foi concluído.'

    );

  }

  // =========================

  // CONCLUSÃO

  // =========================

  const conclusao =

    concluirAssessment_(token);

  // =========================

  // RESULTADO

  // =========================

  const resultado = {

    ok: conclusao.ok === true,

    bloco2: resultadoBloco2,

    bloco3: resultadoBloco3,

    respostasUnicas: total,

    conclusao: conclusao

  };

  Logger.log(

    JSON.stringify(

      resultado,

      null,

      2

    )

  );

  return resultado;

}

function resetarCandidatoTeste() {

  const ID_TESTE = 'TESTE-0001';

  const ss = getSS_();

  const shCand = getSheet_(ARILUB.SHEETS.CANDIDATOS);

  const shResp = getSheet_(ARILUB.SHEETS.RESPOSTAS);

  // =========================

  // 1. LOCALIZA TESTE-0001

  // =========================

  const dados = shCand.getDataRange().getValues();

  const headers = dados[0];

  const map = {};

  headers.forEach((h, i) => {

    map[String(h).trim()] = i;

  });

  let linha = -1;

  for (let i = 1; i < dados.length; i++) {

    if (String(dados[i][map.ID_CANDIDATO]).trim() === ID_TESTE) {

      linha = i + 1;

      break;

    }

  }

  if (linha === -1) {

    throw new Error('TESTE-0001 não encontrado.');

  }

  // =========================

  // 2. APAGA SOMENTE RESPOSTAS

  //    DO TESTE-0001

  // =========================

  const respostas = shResp.getDataRange().getValues();

  if (respostas.length > 1) {

    const hResp = respostas[0];

    const idxID = hResp.indexOf('ID_CANDIDATO');

    for (let i = respostas.length - 1; i >= 1; i--) {

      if (

        String(respostas[i][idxID]).trim() === ID_TESTE

      ) {

        shResp.deleteRow(i + 1);

      }

    }

  }

  // =========================

  // 3. RESETA DADOS OPERACIONAIS

  // =========================

  const limpar = [

    'LINK_AVALIACAO',

    'DATA_ENVIO',

    'DATA_INICIO',

    'DATA_FIM',

    'TEMPO_TOTAL_MIN',

    'TOKEN'

  ];

  limpar.forEach(campo => {

    if (map[campo] !== undefined) {

      shCand

        .getRange(linha, map[campo] + 1)

        .clearContent();

    }

  });

  // =========================

  // 4. VOLTA STATUS

  // =========================

  shCand

    .getRange(linha, map.STATUS + 1)

    .setValue('CONVIDAR');

  // =========================

  // 5. GARANTE VERSÃO

  // =========================

  if (map.VERSAO_ASSESSMENT !== undefined) {

    shCand

      .getRange(

        linha,

        map.VERSAO_ASSESSMENT + 1

      )

      .setValue('v2.0');

  }

  // =========================

  // 6. GERA NOVO TOKEN

  // =========================

  const novoToken = gerarToken_();

  shCand

    .getRange(linha, map.TOKEN + 1)

    .setValue(novoToken);

  // =========================

  // 7. LOG

  // =========================

  log_(

    ID_TESTE,

    'RESET_TESTE_INTERFACE',

    'Candidato técnico resetado para teste completo via GitHub Pages.',

    '',

    novoToken

  );

  // =========================

  // RESULTADO

  // =========================

  const resultado = {

    ok: true,

    candidato: ID_TESTE,

    status: 'CONVIDAR',

    token: novoToken,

    mensagem:

      'TESTE-0001 resetado. Utilize o novo token no GitHub Pages.'

  };

  Logger.log(

    JSON.stringify(resultado, null, 2)

  );

  return resultado;

}

/* ============================================================
   18. CONVITES POR E-MAIL — LOTE DINÂMICO
   ============================================================ */

const ARILUB_CONVITES = {
  // ATUALIZAR A CADA RODADA ANTES DO DISPARO.
  PRAZO_TEXTO: '13/10/2026 às 08h00',
  DELAY_MIN_MS: 12000,
  DELAY_MAX_MS: 25000,
  TEMPO_MAX_EXECUCAO_MS: 300000,
  ASSUNTO: 'AriLub | Convite para próxima etapa do processo seletivo'
};

function emailValido_(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || '').trim());
}

function primeiroNome_(nome) {
  const n = String(nome || '').trim();
  return n ? n.split(/\s+/)[0] : '';
}

function montarCorpoConvite_(nome, link) {
  const primeiroNome = primeiroNome_(nome);
  return [
    'Olá, ' + primeiroNome + '.',
    '',
    'Agradecemos sua participação no processo seletivo da AriLub Distribuidora, para a oportunidade de Assistente de Atendimento Comercial | WhatsApp + CRM.',
    '',
    'Após a análise do seu perfil profissional, você foi selecionado(a) para avançar para a próxima etapa do processo.',
    '',
    'AVALIAÇÃO DE PERFIL PROFISSIONAL E COMPORTAMENTAL',
    '',
    'A avaliação é realizada on-line e individualmente e contém 30 questões, com cronômetro de 25 minutos.',
    '',
    'Prazo para conclusão: ' + ARILUB_CONVITES.PRAZO_TEXTO,
    '',
    'Seu link individual:',
    link,
    '',
    'Reserve um momento em que possa responder com atenção, realize a avaliação individualmente e utilize somente o seu link. Após concluir e enviar, sua participação será registrada automaticamente.',
    '',
    'Não buscamos respostas “perfeitas”. Algumas questões apresentam situações práticas e diferentes formas de atuação. Responda de acordo com a maneira como você realmente agiria.',
    '',
    'A conclusão da avaliação não representa aprovação automática. Os resultados serão analisados em conjunto com as demais informações do processo seletivo. Os candidatos selecionados serão contatados diretamente pela AriLub para a próxima fase.',
    '',
    'Atenciosamente,',
    'Equipe AriLub Distribuidora'
  ].join('\n');
}

function validarEstruturaConvites_() {
  const sheet = getSheet_(ARILUB.SHEETS.CANDIDATOS);
  const map = headerMap_(sheet);
  const obrigatorias = [
    'ID_CANDIDATO', 'NOME', 'EMAIL', 'TOKEN',
    'LINK_AVALIACAO', 'STATUS', 'DATA_ENVIO'
  ];
  const faltando = obrigatorias.filter(h => !map[h]);
  if (faltando.length) {
    throw new Error('Colunas obrigatórias ausentes em CANDIDATOS: ' + faltando.join(', '));
  }
  return { sheet: sheet, map: map };
}

/**
 * Lê dinamicamente toda a aba CANDIDATOS.
 * Não existe mais whitelist fixa de e-mails.
 *
 * Inclui:
 * - candidatos com STATUS = CONVIDAR; e
 * - candidatos já enviados, apenas para auditoria/duplicidade.
 *
 * Exclui TESTE-*.
 */
function listarConvitesPendentes() {
  const estrutura = validarEstruturaConvites_();
  const sheet = estrutura.sheet;
  const map = estrutura.map;
  const lastRow = sheet.getLastRow();
  const saida = [];
  if (lastRow < 2) return saida;

  const values = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).getValues();

  values.forEach((r, i) => {
    const id = String(r[map.ID_CANDIDATO - 1] || '').trim();
    const status = String(r[map.STATUS - 1] || '').trim();
    const dataEnvio = r[map.DATA_ENVIO - 1] || '';

    if (!id || /^TESTE-/i.test(id)) return;

    // Só entram na auditoria candidatos desta rotina:
    // pendentes para convite ou já enviados anteriormente.
    if (normalize_(status) !== normalize_(ARILUB.STATUS.CONVIDAR) && !dataEnvio) return;

    saida.push({
      linha: i + 2,
      id: id,
      nome: String(r[map.NOME - 1] || '').trim(),
      email: String(r[map.EMAIL - 1] || '').trim(),
      status: status,
      token: String(r[map.TOKEN - 1] || '').trim(),
      link: String(r[map.LINK_AVALIACAO - 1] || '').trim(),
      dataEnvio: dataEnvio
    });
  });

  return saida;
}

/**
 * Validação dinâmica.
 * Dados inválidos de um candidato não bloqueiam todo o lote.
 * A função informa APTOS, IGNORADOS e ERROS.
 */
function validarLoteConvites() {
  const candidatos = listarConvitesPendentes();
  const aptos = [];
  const ignorados = [];
  const erros = [];

  const emailsPendentes = new Set();
  const tokensPendentes = new Set();
  const linksPendentes = new Set();

  candidatos.forEach(c => {
    if (c.dataEnvio) {
      ignorados.push({ id: c.id, nome: c.nome, motivo: 'JÁ ENVIADO' });
      return;
    }

    if (normalize_(c.status) !== normalize_(ARILUB.STATUS.CONVIDAR)) {
      ignorados.push({ id: c.id, nome: c.nome, motivo: 'STATUS ' + c.status });
      return;
    }

    const problemas = [];
    if (!c.id) problemas.push('ID_CANDIDATO ausente');
    if (!c.nome) problemas.push('NOME ausente');
    if (!emailValido_(c.email)) problemas.push('e-mail ausente ou inválido');
    if (!c.token) problemas.push('TOKEN ausente');
    if (!c.link) problemas.push('LINK_AVALIACAO ausente');

    if (c.link && c.token && c.link.indexOf(encodeURIComponent(c.token)) === -1) {
      problemas.push('link não corresponde ao token');
    }

    const e = c.email.toLowerCase();
    if (e && emailsPendentes.has(e)) problemas.push('e-mail duplicado entre pendentes');
    if (c.token && tokensPendentes.has(c.token)) problemas.push('token duplicado entre pendentes');
    if (c.link && linksPendentes.has(c.link)) problemas.push('link duplicado entre pendentes');

    if (problemas.length) {
      erros.push({
        id: c.id,
        nome: c.nome,
        email: c.email,
        erro: problemas.join('; ')
      });
      return;
    }

    emailsPendentes.add(e);
    tokensPendentes.add(c.token);
    linksPendentes.add(c.link);
    aptos.push(c);
  });

  const resultado = {
    ok: erros.length === 0,
    encontradosNaRotina: candidatos.length,
    aptosParaEnvio: aptos.length,
    jaEnviados: ignorados.length,
    erros: erros.length,
    detalhe: {
      aptos: aptos.map(c => ({id:c.id,nome:c.nome,email:c.email,status:c.status})),
      ignorados: ignorados,
      erros: erros
    }
  };

  Logger.log(JSON.stringify(resultado, null, 2));
  return resultado;
}

/**
 * Validação resumida para homologação antes do disparo.
 * Não envia e-mails e não altera a planilha.
 */
function validarLoteConvitesResumo() {
  const r = validarLoteConvites();
  const resumo = {
    ok: r.ok,
    encontradosNaRotina: r.encontradosNaRotina,
    aptosParaEnvio: r.aptosParaEnvio,
    jaEnviados: r.jaEnviados,
    erros: r.erros,
    detalheErros: (r.detalhe && r.detalhe.erros) ? r.detalhe.erros : []
  };
  Logger.log(JSON.stringify(resumo, null, 2));
  return resumo;
}

function enviarConvitesPendentes() {
  const inicioExecucao = Date.now();
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);

  try {
    const estrutura = validarEstruturaConvites_();
    const sheet = estrutura.sheet;
    const map = estrutura.map;
    const candidatos = listarConvitesPendentes();

    const resumo = {
      enviados: [],
      ignorados: [],
      erros: [],
      interrompidoPorTempo: false
    };

    for (let i = 0; i < candidatos.length; i++) {
      const c = candidatos[i];
      const status = normalize_(c.status);

      // DATA_ENVIO continua sendo a trava principal de duplicidade.
      if (c.dataEnvio) {
        resumo.ignorados.push({ id: c.id, nome: c.nome, motivo: 'JÁ ENVIADO' });
        continue;
      }

      if (status !== normalize_(ARILUB.STATUS.CONVIDAR)) {
        resumo.ignorados.push({ id: c.id, nome: c.nome, motivo: 'STATUS ' + c.status });
        continue;
      }

      const problemas = [];
      if (!emailValido_(c.email)) problemas.push('e-mail ausente ou inválido');
      if (!c.token) problemas.push('TOKEN ausente');
      if (!c.link) problemas.push('LINK_AVALIACAO ausente');
      if (c.link && c.token && c.link.indexOf(encodeURIComponent(c.token)) === -1) {
        problemas.push('link não corresponde ao token');
      }

      if (problemas.length) {
        const motivoDados = problemas.join('; ');

        // Ausência/invalidade de e-mail é pendência cadastral, não falha operacional.
        if (!emailValido_(c.email)) {
          resumo.ignorados.push({
            id: c.id,
            nome: c.nome,
            motivo: 'E-MAIL AUSENTE OU INVÁLIDO'
          });
          log_(c.id, 'CONVITE_IGNORADO', 'Convite não enviado.', motivoDados, c.token);
          continue;
        }

        // Token/link inconsistentes continuam sendo erro operacional.
        resumo.erros.push({
          id: c.id,
          nome: c.nome,
          email: c.email,
          erro: motivoDados
        });
        log_(c.id, 'CONVITE_ERRO', 'Convite não enviado.', motivoDados, c.token);
        continue;
      }

      if (Date.now() - inicioExecucao > ARILUB_CONVITES.TEMPO_MAX_EXECUCAO_MS) {
        resumo.interrompidoPorTempo = true;
        break;
      }

      try {
        GmailApp.sendEmail(
          c.email,
          ARILUB_CONVITES.ASSUNTO,
          montarCorpoConvite_(c.nome, c.link),
          { name: 'AriLub Distribuidora' }
        );

        const enviadoEm = now_();
        sheet.getRange(c.linha, map.DATA_ENVIO).setValue(enviadoEm);
        sheet.getRange(c.linha, map.STATUS).setValue(ARILUB.STATUS.CONVITE_ENVIADO);
        SpreadsheetApp.flush();

        log_(
          c.id,
          'CONVITE_ENVIADO',
          'Convite individual enviado para ' + c.email + '. Prazo: ' + ARILUB_CONVITES.PRAZO_TEXTO + '.',
          '',
          c.token
        );

        resumo.enviados.push({
          id: c.id,
          nome: c.nome,
          email: c.email,
          dataEnvio: enviadoEm
        });

      } catch (e) {
        const erro = String(e && e.message ? e.message : e);
        resumo.erros.push({ id: c.id, nome: c.nome, email: c.email, erro: erro });
        log_(c.id, 'CONVITE_ERRO', 'Falha no envio do convite para ' + c.email + '.', erro, c.token);
      }

      // Retardo apenas se ainda houver tempo operacional.
      if (i < candidatos.length - 1) {
        const atraso = Math.floor(
          Math.random() * (ARILUB_CONVITES.DELAY_MAX_MS - ARILUB_CONVITES.DELAY_MIN_MS + 1)
        ) + ARILUB_CONVITES.DELAY_MIN_MS;
        Utilities.sleep(atraso);
      }
    }

    const resultado = {
      ok: resumo.erros.length === 0,
      enviados: resumo.enviados.length,
      ignorados: resumo.ignorados.length,
      erros: resumo.erros.length,
      interrompidoPorTempo: resumo.interrompidoPorTempo,
      detalhe: resumo
    };

    Logger.log(JSON.stringify(resultado, null, 2));
    return resultado;

  } finally {
    lock.releaseLock();
  }
}

/**
 * AUDITORIA PÓS-DISPARO
 * Somente leitura: não envia e-mails e não altera a planilha.
 * Reconstrói o resultado atual da rodada a partir de CANDIDATOS.
 */
function auditarResultadoDisparos() {
  const sh = getSheet_('CANDIDATOS');
  const dados = sh.getDataRange().getValues();
  if (dados.length < 2) {
    const vazio = { ok: true, total: 0, enviados: 0, pendentes: 0, semEmail: 0, detalhePendentes: [] };
    Logger.log(JSON.stringify(vazio, null, 2));
    return vazio;
  }

  const h = dados[0].map(String);
  const idx = {};
  h.forEach((x, i) => idx[x] = i);

  const campo = nome => idx[nome];
  const enviados = [];
  const pendentes = [];
  const semEmail = [];

  for (let i = 1; i < dados.length; i++) {
    const r = dados[i];
    const id = String(r[campo('ID_CANDIDATO')] || '').trim();
    if (!id || id === 'TESTE') continue;

    const nome = String(r[campo('NOME')] || '').trim();
    const email = String(r[campo('EMAIL')] || '').trim();
    const status = String(r[campo('STATUS')] || '').trim();
    const dataEnvio = r[campo('DATA_ENVIO')];

    // Rodada operacional atual: ARI-0027 em diante.
    const m = id.match(/^ARI-(\d+)$/);
    if (!m || Number(m[1]) < 27) continue;

    if (dataEnvio) {
      enviados.push({ id, nome, email, status, dataEnvio });
    } else if (!emailValido_(email)) {
      semEmail.push({ id, nome, email, status });
    } else if (status === 'CONVIDAR') {
      pendentes.push({ id, nome, email, status });
    }
  }

  const resultado = {
    ok: pendentes.length === 0,
    totalRodadaMapeado: enviados.length + pendentes.length + semEmail.length,
    enviados: enviados.length,
    pendentesDeEnvio: pendentes.length,
    semEmail: semEmail.length,
    detalhePendentes: pendentes,
    detalheSemEmail: semEmail
  };

  Logger.log(JSON.stringify(resultado, null, 2));
  return resultado;
}

/* ============================================================
   19. ÚLTIMA CHAMADA — RECUPERAÇÃO CONTROLADA V4
   ============================================================
   V4 — RETOMADA APÓS REJEIÇÕES ASSÍNCRONAS E LIMITE DO GMAIL

   PRINCÍPIOS:
   - coorte fechada: somente os 40 candidatos com falha confirmada;
   - trava absoluta dos 21 candidatos sem falha confirmada;
   - corrige duplicidade ARI-0040 existente na lista V3;
   - NÃO considera o LOG V3 "ENVIADA" como prova de entrega;
   - primeiro passo é UM ÚNICO teste manual (ARI-0054);
   - o teste NÃO agenda gatilho e NÃO inicia lote;
   - qualquer lote posterior exige execução manual explícita;
   - lote V4 = no máximo 4 mensagens individuais;
   - não altera DATA_ENVIO nem STATUS;
   - não envia para quem já iniciou/concluiu;
   - LOG diferencia TENTATIVA de CONFIRMAÇÃO OPERACIONAL.
*/

const ARILUB_ULTIMA_CHAMADA = {
  ASSUNTO: 'AriLub | Última oportunidade — Processo Seletivo Assistente Comercial',
  PRAZO_TEXTO: '30/10/2026 às 21h30 (horário de Fortaleza)',
  TAMANHO_LOTE: 4,
  ID_TESTE: 'ARI-0054',
  PROP_TESTE_FEITO: 'ARILUB_UC_V4_TESTE_FEITO',
  PROP_TESTE_CONFIRMADO: 'ARILUB_UC_V4_TESTE_CONFIRMADO',
  PROP_FILA: 'ARILUB_UC_V4_FILA',

  IDS_RECUPERACAO: [
    'ARI-0050','ARI-0052','ARI-0054','ARI-0057','ARI-0058','ARI-0061','ARI-0062','ARI-0063',
    'ARI-0064','ARI-0066','ARI-0068','ARI-0069','ARI-0071','ARI-0072','ARI-0073','ARI-0075',
    'ARI-0076','ARI-0077','ARI-0078','ARI-0079','ARI-0080','ARI-0081','ARI-0084','ARI-0085',
    'ARI-0086','ARI-0087','ARI-0088','ARI-0089','ARI-0090','ARI-0091','ARI-0092','ARI-0093',
    'ARI-0094','ARI-0095','ARI-0096','ARI-0098','ARI-0099','ARI-0100','ARI-0101','ARI-0102'
  ],

  IDS_NAO_REENVIAR: [
    'ARI-0020','ARI-0022','ARI-0023','ARI-0025','ARI-0026','ARI-0028','ARI-0029',
    'ARI-0031','ARI-0032','ARI-0033','ARI-0034','ARI-0036','ARI-0037','ARI-0038',
    'ARI-0040','ARI-0041','ARI-0043','ARI-0047','ARI-0048','ARI-0049','ARI-0082'
  ]
};

function montarCorpoUltimaChamada_(nome, link) {
  return [
    'Olá!', '',
    'Estamos concluindo o processo seletivo para Assistente Comercial — Fortaleza/CE e reabrimos, excepcionalmente, a etapa de avaliação.', '',
    'Se você ainda deseja participar, utilize seu link individual da avaliação:',
    link, '',
    'O acesso desta última chamada ficará disponível até ' + ARILUB_ULTIMA_CHAMADA.PRAZO_TEXTO + '.', '',
    'A avaliação possui 30 questões, divididas em 3 blocos, com tempo total de 25 minutos após o início. Recomendamos realizá-la em um momento em que possa concluir a etapa sem interrupções.', '',
    'Após esse prazo, encerraremos esta fase do processo e seguiremos com os candidatos que tiverem participado.', '',
    'Atenciosamente,',
    'AriLub | Seleção'
  ].join('\n');
}

function candidatoUcV4PorId_(idProcurado) {
  const sh = getSheet_(ARILUB.SHEETS.CANDIDATOS);
  const map = headerMap_(sh);
  const obrig = ['ID_CANDIDATO','NOME','EMAIL','TOKEN','LINK_AVALIACAO','STATUS','DATA_INICIO','DATA_FIM'];
  const falt = obrig.filter(h => !map[h]);
  if (falt.length) throw new Error('Colunas ausentes em CANDIDATOS: ' + falt.join(', '));

  const dados = sh.getRange(2,1,Math.max(sh.getLastRow()-1,1),sh.getLastColumn()).getValues();
  for (let i=0; i<dados.length; i++) {
    const r = dados[i];
    const id = String(r[map.ID_CANDIDATO-1] || '').trim();
    if (id !== idProcurado) continue;
    return {
      linha:i+2, id:id,
      nome:String(r[map.NOME-1] || '').trim(),
      email:String(r[map.EMAIL-1] || '').trim(),
      token:String(r[map.TOKEN-1] || '').trim(),
      link:String(r[map.LINK_AVALIACAO-1] || '').trim(),
      status:String(r[map.STATUS-1] || '').trim(),
      dataInicio:r[map.DATA_INICIO-1],
      dataFim:r[map.DATA_FIM-1]
    };
  }
  return null;
}

function validarCandidatoUcV4_(c) {
  if (!c) return 'CANDIDATO NÃO LOCALIZADO';
  if (ARILUB_ULTIMA_CHAMADA.IDS_NAO_REENVIAR.indexOf(c.id) >= 0) return 'TRAVA ABSOLUTA — NÃO REENVIAR';
  if (ARILUB_ULTIMA_CHAMADA.IDS_RECUPERACAO.indexOf(c.id) < 0) return 'FORA DA COORTE DE RECUPERAÇÃO';
  if (c.dataInicio || c.dataFim) return 'JÁ INICIOU/CONCLUIU';
  if (!emailValido_(c.email)) return 'E-MAIL AUSENTE/INVÁLIDO';
  if (!c.token || !c.link || c.link.indexOf(encodeURIComponent(c.token)) === -1) return 'TOKEN/LINK INVÁLIDO';
  return '';
}

function idsConfirmadosV4NoLog_() {
  const ids = new Set();
  const sh = getSheet_(ARILUB.SHEETS.LOG);
  const map = headerMap_(sh);
  if (sh.getLastRow() < 2 || !map.ID_CANDIDATO || !map.ACAO) return ids;
  const dados = sh.getRange(2,1,sh.getLastRow()-1,sh.getLastColumn()).getValues();
  dados.forEach(r => {
    const acao = String(r[map.ACAO-1] || '').trim();
    if (acao === 'ULTIMA_CHAMADA_RECUPERACAO_V4_CONFIRMADA') {
      const id = String(r[map.ID_CANDIDATO-1] || '').trim();
      if (id) ids.add(id);
    }
  });
  return ids;
}

function prepararUltimaChamadaV4() {
  const props = PropertiesService.getScriptProperties();
  props.deleteProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_FEITO);
  props.deleteProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_CONFIRMADO);
  props.deleteProperty(ARILUB_ULTIMA_CHAMADA.PROP_FILA);

  // Segurança: remove gatilhos residuais da V3.
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'processarLoteUltimaChamada') ScriptApp.deleteTrigger(t);
  });

  const teste = candidatoUcV4PorId_(ARILUB_ULTIMA_CHAMADA.ID_TESTE);
  const impedimento = validarCandidatoUcV4_(teste);
  const resultado = {
    ok: !impedimento,
    versao: 'V4',
    coorteRecuperacao: ARILUB_ULTIMA_CHAMADA.IDS_RECUPERACAO.length,
    travaNaoReenviar: ARILUB_ULTIMA_CHAMADA.IDS_NAO_REENVIAR.length,
    testeSelecionado: teste ? {id:teste.id,nome:teste.nome,email:teste.email} : null,
    impedimentoTeste: impedimento || '',
    acaoSeguinte: impedimento ? 'CORRIGIR ANTES DE ENVIAR' : 'EXECUTAR testarUmEnvioUltimaChamadaV4() — APENAS 1 EMAIL'
  };
  Logger.log(JSON.stringify(resultado,null,2));
  return resultado;
}

function testarUmEnvioUltimaChamadaV4() {
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_FEITO) === 'SIM') {
    throw new Error('Teste V4 já executado. Não repetir. Audite o Gmail antes de qualquer nova ação.');
  }

  const c = candidatoUcV4PorId_(ARILUB_ULTIMA_CHAMADA.ID_TESTE);
  const impedimento = validarCandidatoUcV4_(c);
  if (impedimento) throw new Error('Teste bloqueado: ' + impedimento);

  // Marca antes da chamada para impedir duplo clique/reexecução acidental.
  props.setProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_FEITO,'SIM');
  props.setProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_CONFIRMADO,'NAO');

  try {
    GmailApp.sendEmail(c.email, ARILUB_ULTIMA_CHAMADA.ASSUNTO, montarCorpoUltimaChamada_(c.nome,c.link), {
      name:'AriLub Distribuidora'
    });
    log_(c.id,'ULTIMA_CHAMADA_RECUPERACAO_V4_TENTATIVA_TESTE',
      '1 envio de teste submetido ao Gmail. NÃO significa entrega confirmada.',c.email,'');
    const resultado = {
      ok:true,
      submetidoAoGmail:true,
      entregaConfirmada:false,
      candidato:{id:c.id,nome:c.nome,email:c.email},
      proximoPasso:'AGUARDAR E AUDITAR O GMAIL. NÃO EXECUTAR LOTE.'
    };
    Logger.log(JSON.stringify(resultado,null,2));
    return resultado;
  } catch(e) {
    log_(c.id,'ULTIMA_CHAMADA_RECUPERACAO_V4_ERRO_TESTE','Falha síncrona no teste V4.',c.email,String(e));
    const resultado = {ok:false,submetidoAoGmail:false,entregaConfirmada:false,candidato:{id:c.id,nome:c.nome,email:c.email},erro:String(e)};
    Logger.log(JSON.stringify(resultado,null,2));
    return resultado;
  }
}

function confirmarTesteUltimaChamadaV4() {
  // EXECUTAR SOMENTE após auditoria humana do Gmail sem bounce/rejeição do teste.
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_FEITO) !== 'SIM') throw new Error('Nenhum teste V4 foi executado.');
  if (props.getProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_CONFIRMADO) === 'SIM') return {ok:true,mensagem:'Teste já confirmado anteriormente.'};

  const c = candidatoUcV4PorId_(ARILUB_ULTIMA_CHAMADA.ID_TESTE);
  const impedimento = validarCandidatoUcV4_(c);
  if (impedimento && impedimento !== 'JÁ INICIOU/CONCLUIU') throw new Error('Não foi possível confirmar: ' + impedimento);

  props.setProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_CONFIRMADO,'SIM');
  log_(c.id,'ULTIMA_CHAMADA_RECUPERACAO_V4_CONFIRMADA','Teste confirmado após auditoria externa do Gmail.',c.email,'');
  return {ok:true,id:c.id,email:c.email,mensagem:'Teste V4 confirmado. Lotes permanecem manuais.'};
}

function montarFilaUltimaChamadaV4_() {
  const confirmados = idsConfirmadosV4NoLog_();
  const fila = [];
  const excluidos = [];
  ARILUB_ULTIMA_CHAMADA.IDS_RECUPERACAO.forEach(id => {
    const c = candidatoUcV4PorId_(id);
    const impedimento = validarCandidatoUcV4_(c);
    if (impedimento) { excluidos.push({id:id,motivo:impedimento}); return; }
    if (confirmados.has(id)) { excluidos.push({id:id,motivo:'CONFIRMADO V4 — NÃO REENVIAR'}); return; }
    fila.push({id:c.id,nome:c.nome,email:c.email,link:c.link});
  });
  return {fila:fila,excluidos:excluidos};
}

function prepararFilaUltimaChamadaV4() {
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_CONFIRMADO) !== 'SIM') {
    throw new Error('Teste V4 ainda não confirmado. Não é permitido preparar lote.');
  }
  const r = montarFilaUltimaChamadaV4_();
  props.setProperty(ARILUB_ULTIMA_CHAMADA.PROP_FILA,JSON.stringify(r.fila));
  const resultado = {ok:true,pendentes:r.fila.length,excluidos:r.excluidos,proximoLoteMaximo:Math.min(ARILUB_ULTIMA_CHAMADA.TAMANHO_LOTE,r.fila.length),automatico:false};
  Logger.log(JSON.stringify(resultado,null,2));
  return resultado;
}

function processarUmLoteUltimaChamadaV4() {
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_CONFIRMADO) !== 'SIM') throw new Error('Teste V4 não confirmado. Lote bloqueado.');

  let fila = [];
  try { fila = JSON.parse(props.getProperty(ARILUB_ULTIMA_CHAMADA.PROP_FILA) || '[]'); } catch(e) { fila=[]; }
  if (!fila.length) return {ok:true,enviadosNesteLote:0,restantes:0,mensagem:'Fila vazia. Execute prepararFilaUltimaChamadaV4() se necessário.'};

  const lote = fila.slice(0,ARILUB_ULTIMA_CHAMADA.TAMANHO_LOTE);
  const restantes = fila.slice(ARILUB_ULTIMA_CHAMADA.TAMANHO_LOTE);
  const tentativas=[];
  const erros=[];

  lote.forEach(item => {
    const c = candidatoUcV4PorId_(item.id);
    const impedimento = validarCandidatoUcV4_(c);
    if (impedimento) {
      erros.push({id:item.id,email:item.email,motivo:impedimento});
      log_(item.id,'ULTIMA_CHAMADA_RECUPERACAO_V4_IGNORADA','Não enviado no lote V4.',item.email,impedimento);
      return;
    }
    try {
      GmailApp.sendEmail(c.email,ARILUB_ULTIMA_CHAMADA.ASSUNTO,montarCorpoUltimaChamada_(c.nome,c.link),{name:'AriLub Distribuidora'});
      tentativas.push({id:c.id,nome:c.nome,email:c.email});
      log_(c.id,'ULTIMA_CHAMADA_RECUPERACAO_V4_TENTATIVA_LOTE','Submetido ao Gmail; entrega ainda não confirmada.',c.email,'');
    } catch(e) {
      erros.push({id:c.id,email:c.email,motivo:String(e)});
      log_(c.id,'ULTIMA_CHAMADA_RECUPERACAO_V4_ERRO_LOTE','Falha síncrona no envio V4.',c.email,String(e));
      // Falha síncrona volta para o início da fila.
      restantes.unshift(item);
    }
  });

  props.setProperty(ARILUB_ULTIMA_CHAMADA.PROP_FILA,JSON.stringify(restantes));
  const resultado={ok:true,tentativasNesteLote:tentativas.length,errosNesteLote:erros.length,restantes:restantes.length,automatico:false,tentativas:tentativas,erros:erros,proximoPasso:'AUDITAR GMAIL ANTES DE QUALQUER NOVO LOTE'};
  Logger.log(JSON.stringify(resultado,null,2));
  return resultado;
}

function auditarUltimaChamadaV4() {
  const props=PropertiesService.getScriptProperties();
  let fila=[];
  try { fila=JSON.parse(props.getProperty(ARILUB_ULTIMA_CHAMADA.PROP_FILA)||'[]'); } catch(e) { fila=[]; }
  const confirmados=Array.from(idsConfirmadosV4NoLog_());
  const gatilhos=ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction()==='processarLoteUltimaChamada').length;
  const resultado={
    ok:true,versao:'V4',coorteRecuperacao:40,travaNaoReenviar:21,
    testeFeito:props.getProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_FEITO)||'NAO',
    testeConfirmado:props.getProperty(ARILUB_ULTIMA_CHAMADA.PROP_TESTE_CONFIRMADO)||'NAO',
    confirmadosV4:confirmados,
    filaPersistida:fila.length,
    gatilhosV3Residuias:gatilhos,
    automatico:false
  };
  Logger.log(JSON.stringify(resultado,null,2));
  return resultado;
}

function cancelarUltimaChamada8x3() {
  // Compatibilidade: mantém a função antiga como trava de emergência.
  const props=PropertiesService.getScriptProperties();
  props.deleteProperty(ARILUB_ULTIMA_CHAMADA.PROP_FILA);
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction()==='processarLoteUltimaChamada') ScriptApp.deleteTrigger(t);
  });
  log_('','ULTIMA_CHAMADA_RECUPERACAO_V4_CANCELADA','Fila V4 limpa e gatilhos V3 removidos.','','');
  return {ok:true,mensagem:'Fila V4 limpa. Nenhum gatilho automático de recuperação permanece.'};
}


/* ============================================================
 * PATCH OPERACIONAL V2.2 — 12/11/2026
 * A versão da matriz de questões continua em CONFIG. Não alterar tokens.
 * ============================================================ */
function totalOficialV22_(){
  const q=carregarQuestoes_(), total=Number(getConfig_().TOTAL_QUESTOES||30);
  if(q.length!==total || new Set(q.map(x=>String(x.id))).size!==total)throw new Error('CONFIG_QUESTOES_INCONSISTENTE');
  return total;
}
function terminalV22_(c){
  return Boolean(c.DATA_FIM)||[ARILUB.STATUS.CONCLUIDO,ARILUB.STATUS.EXPIRADO,ARILUB.STATUS.ANALISE,ARILUB.STATUS.ENTREVISTA,ARILUB.STATUS.FINALISTA,ARILUB.STATUS.RESERVA,ARILUB.STATUS.ENCERRADO].map(normalize_).includes(normalize_(c.STATUS));
}
function reciboTerminalV22_(c,n,total){
  return {ok:true,jaEncerrado:true,expirado:n!==total,completo:n===total,respondidas:n,total:total,status:c.STATUS,mensagem:n===total?'Avaliação completa registrada.':'Avaliação encerrada com respostas parciais.'};
}
function finalizarV22_(c,n,total,expirado){
  const completo=n===total;
  if(!completo&&!expirado)throw new Error('INCOMPLETO');
  const sh=getSheet_(ARILUB.SHEETS.CANDIDATOS),m=headerMap_(sh),tempo=tempoAssessment_(c);
  const status=completo?ARILUB.STATUS.CONCLUIDO:ARILUB.STATUS.EXPIRADO;
  // Registro de fim efetivo limitado ao prazo contratual, não ao horário tardio da chamada.
  const fim=expirado?new Date(new Date(c.DATA_INICIO).getTime()+tempo.limiteMin*60000):now_();
  if(m.DATA_FIM)sh.getRange(c.row,m.DATA_FIM).setValue(fim);
  if(m.TEMPO_TOTAL_MIN)sh.getRange(c.row,m.TEMPO_TOTAL_MIN).setValue(Math.min(tempo.limiteMin,Math.max(0,Math.round((fim.getTime()-new Date(c.DATA_INICIO).getTime())/60000))));
  sh.getRange(c.row,m.STATUS).setValue(status);
  SpreadsheetApp.flush();
  log_(c.ID_CANDIDATO,completo?'ASSESSMENT_CONCLUIDO':'ASSESSMENT_TEMPO_ESGOTADO','Respostas válidas: '+n+'/'+total+'.','',''+c.TOKEN);
  // Não gerar notas nem fichas automáticas para avaliação parcial.
  const motor=completo?prepararPosAssessment_(c.ID_CANDIDATO):null;
  if(!completo){try{marcarPainelIncompletoV22_(c.ID_CANDIDATO,n,total);}catch(e){log_(c.ID_CANDIDATO,'ERRO_PAINEL_INCOMPLETO','Status registrado; painel necessita sincronização.',String(e),'');}}
  return {ok:true,expirado:!completo,completo:completo,respondidas:n,total:total,status:status,analise:motor,mensagem:completo?'Avaliação completa registrada.':'Tempo encerrado. Respostas salvas: '+n+'/'+total+'.'};
}
function salvarProgressoV22_(token,bloco,respostas,estrito){
  const lock=LockService.getScriptLock();lock.waitLock(15000);
  try{
    const c=findCandidateByToken_(token);if(!c)throw new Error('TOKEN_INVALIDO');
    if(terminalV22_(c))return {ok:false,codigo:'JA_CONCLUIDO'};
    if(!c.DATA_INICIO||normalize_(c.STATUS)!==normalize_(ARILUB.STATUS.INICIADO))return {ok:false,codigo:'NAO_INICIADO'};
    const tempo=tempoAssessment_(c);
    if(tempo.expirado)return {ok:false,codigo:'TEMPO_ESGOTADO'};
    if(!Array.isArray(respostas)||respostas.length<1||respostas.length>30)throw new Error('RESPOSTAS_INVALIDAS');
    const qs=carregarQuestoes_().filter(q=>normalize_(q.bloco)===normalize_(bloco));
    if(!qs.length)throw new Error('BLOCO_INVALIDO');
    if(estrito)validarRespostasBloco_(bloco,respostas);
    const qmap={};qs.forEach(q=>qmap[String(q.id)]=q);const vistos=new Set();
    // Valida o lote inteiro antes de gravar qualquer item.
    const normalizadas=respostas.map(r=>{
      const id=String(r.idQuestao||'').trim(),q=qmap[id];
      if(!q||vistos.has(id))throw new Error('QUESTAO_INVALIDA_OU_DUPLICADA');vistos.add(id);
      const multipla=normalize_(q.tipo).includes('MULTIPLA');
      if(r.clear===true&&!estrito&&!multipla)return {id:id,tipo:'aberta',texto:'',alt:''};
      const alt=multipla?normalize_(r.alternativa):'';
      const texto=multipla?String((q.alternativas||{})[alt]||'').trim():String(r.resposta==null?'':r.resposta).trim();
      if(!texto||texto.length>20000)throw new Error('RESPOSTA_INVALIDA_'+id);
      return {id:id,tipo:multipla?'multipla':'aberta',texto:texto,alt:alt};
    });
    const sh=getSheet_(ARILUB.SHEETS.RESPOSTAS),m=headerMap_(sh),exist=getExistingResponses_(c.ID_CANDIDATO),cfg=getConfig_(),novas=[];
    const campos=['ID_CANDIDATO','NOME','ID_QUESTAO','BLOCO','TIPO','RESPOSTA_BRUTA','VALOR_ALTERNATIVA','TIMESTAMP','VERSAO_ASSESSMENT','TOKEN'];
    campos.forEach(k=>{if(!m[k])throw new Error('COLUNA_AUSENTE_'+k);});
    normalizadas.forEach(r=>{
      const anterior=exist[r.id];
      if(anterior&&String(anterior.resposta||'')===r.texto&&String(anterior.alternativa||'')===r.alt)return;
      if(!anterior&&!r.texto)return;
      const linha=new Array(sh.getLastColumn()).fill('');
      const txt=/^[=+@-]/.test(r.texto)?"'"+r.texto:r.texto;
      const vals={ID_CANDIDATO:c.ID_CANDIDATO,NOME:c.NOME,ID_QUESTAO:Number(r.id),BLOCO:bloco,TIPO:r.tipo,RESPOSTA_BRUTA:txt,VALOR_ALTERNATIVA:r.alt,TIMESTAMP:now_(),VERSAO_ASSESSMENT:cfg.VERSAO_ASSESSMENT||ARILUB.VERSION,TOKEN:token,ETAPA_SALVAMENTO:bloco};
      Object.keys(vals).forEach(k=>{if(m[k])linha[m[k]-1]=vals[k];});
      if(anterior)sh.getRange(anterior.row,1,1,linha.length).setValues([linha]);else novas.push(linha);
    });
    if(novas.length){const inicio=sh.getLastRow()+1;const fim=inicio+novas.length-1;if(fim>sh.getMaxRows())sh.insertRowsAfter(sh.getMaxRows(),fim-sh.getMaxRows());sh.getRange(inicio,1,novas.length,sh.getLastColumn()).setValues(novas);}
    SpreadsheetApp.flush();
    const n=contarRespostas_(c.ID_CANDIDATO);
    // LOG por bloco, sem inflar histórico por cada edição de resposta.
    if(estrito)log_(c.ID_CANDIDATO,'BLOCO_SALVO','Bloco salvo: '+bloco,'',token);
    return {ok:true,bloco:bloco,respondidas:n,total:totalOficialV22_(),restanteSeg:tempoAssessment_(c).restanteSeg,mensagem:'Respostas registradas.'};
  }finally{lock.releaseLock();}
}
function contagensOficiaisV22_(){
  const sh=getSheet_(ARILUB.SHEETS.RESPOSTAS),m=headerMap_(sh),qmap={},sets={};
  carregarQuestoes_().forEach(q=>qmap[String(q.id)]=q);
  if(sh.getLastRow()<2)return {};
  sh.getRange(2,1,sh.getLastRow()-1,sh.getLastColumn()).getValues().forEach(r=>{
    const id=String(r[m.ID_CANDIDATO-1]||'').trim(),qid=String(r[m.ID_QUESTAO-1]||'').trim(),q=qmap[qid];
    if(!id||!q)return;
    if(!sets[id])sets[id]=new Set();
    const valida=String(r[m.RESPOSTA_BRUTA-1]||'').trim()&&(!normalize_(q.tipo).includes('MULTIPLA')||String((q.alternativas||{})[normalize_(r[m.VALOR_ALTERNATIVA-1])]||'').trim());
    if(valida)sets[id].add(qid);else sets[id].delete(qid);
  });
  const out={};Object.keys(sets).forEach(id=>out[id]=sets[id].size);return out;
}
// Somente leitura. Revisar o resultado antes de qualquer migração de status.
function auditarIntegridadeV22(){
  const sh=getSheet_(ARILUB.SHEETS.CANDIDATOS),m=headerMap_(sh),total=totalOficialV22_(),ns=contagensOficiaisV22_(),res=[];
  sh.getDataRange().getValues().slice(1).forEach(r=>{
    const id=String(r[m.ID_CANDIDATO-1]||'').trim();if(!/^ARI-/.test(id))return;
    const status=String(r[m.STATUS-1]||''),n=ns[id]||0;
    if(normalize_(status)===normalize_(ARILUB.STATUS.CONCLUIDO)&&n!==total)res.push({id:id,respondidas:n,total:total,status:status});
  });
  const resultado={ok:true,versaoPatch:'2.2',incompletos:res.length,detalhes:res};Logger.log(JSON.stringify(resultado));return resultado;
}
// Migração explícita: altera SOMENTE status dos encerrados incompletos. Preserva notas históricas, respostas e decisões.
function migrarEncerradosIncompletosV22(){
  const lock=LockService.getScriptLock();lock.waitLock(15000);
  try{
    const sh=getSheet_(ARILUB.SHEETS.CANDIDATOS),m=headerMap_(sh),total=totalOficialV22_(),ns=contagensOficiaisV22_(),alterados=[];
    sh.getDataRange().getValues().slice(1).forEach((r,i)=>{
      const id=String(r[m.ID_CANDIDATO-1]||'').trim(),n=ns[id]||0;
      if(!/^ARI-/.test(id)||n===total)return;
      const status=normalize_(r[m.STATUS-1]);
      if(status===normalize_(ARILUB.STATUS.EXPIRADO)){marcarPainelIncompletoV22_(id,n,total);return;}
      if(status!==normalize_(ARILUB.STATUS.CONCLUIDO))return;
      marcarPainelIncompletoV22_(id,n,total);
      sh.getRange(i+2,m.STATUS).setValue(ARILUB.STATUS.EXPIRADO);
      log_(id,'MIGRACAO_V22_INCOMPLETO','Status ajustado; '+n+'/'+total+' respostas válidas. Histórico preservado.','','');alterados.push(id);
    });
    const r={ok:true,alterados:alterados};Logger.log(JSON.stringify(r));return r;
  }finally{lock.releaseLock();}
}

function marcarPainelIncompletoV22_(id,n,total){
  const sh=getSheet_(ARILUB.SHEETS.PAINEL);if(sh.getLastRow()<9)return;
  const ids=sh.getRange(9,1,sh.getLastRow()-8,1).getValues();
  ids.forEach((r,i)=>{if(String(r[0]||'').trim()!==String(id))return;const row=i+9;
    sh.getRange(row,5,1,4).setValues([[n+'/'+total+' respostas válidas','','','INCOMPLETO — NÃO CLASSIFICAR']]);
    sh.getRange(row,11).setValue('Avaliação incompleta. Resultado histórico preservado em ANALISE; não comparar com testes completos.');
  });
}
// Operação manual de reconciliação; não instala gatilhos nem envia convites.
function reconciliarExpiradosV22(){
  const sh=getSheet_(ARILUB.SHEETS.CANDIDATOS),m=headerMap_(sh),resultados=[];
  sh.getDataRange().getValues().slice(1).forEach(r=>{
    const id=String(r[m.ID_CANDIDATO-1]||'').trim();
    if(!/^ARI-\d+$/.test(id)||normalize_(r[m.STATUS-1])!==normalize_(ARILUB.STATUS.INICIADO)||!r[m.DATA_INICIO-1]||!r[m.TOKEN-1])return;
    const c={DATA_INICIO:r[m.DATA_INICIO-1]};if(!tempoAssessment_(c).expirado)return;
    try{const res=encerrarPorTempo_(String(r[m.TOKEN-1]));resultados.push({id:id,ok:res.ok,status:res.status,respondidas:res.respondidas});}catch(e){resultados.push({id:id,ok:false,erro:String(e)});}
  });
  const resultado={ok:resultados.every(r=>r.ok),resultados:resultados};Logger.log(JSON.stringify(resultado));return resultado;
}

// Instalar manualmente SOMENTE após homologação e migração. Não cria gatilhos de e-mail.
function instalarReconciliacaoV22(){
  const ss=SpreadsheetApp.getActiveSpreadsheet();if(!ss)throw new Error('ABRA_A_PLANILHA_VINCULADA');
  PropertiesService.getScriptProperties().setProperty('ARILUB_PLANILHA_V22',ss.getId());
  const nome='reconciliarExpiradosV22';
  const existentes=ScriptApp.getProjectTriggers().filter(t=>t.getHandlerFunction()===nome);
  if(!existentes.length)ScriptApp.newTrigger(nome).timeBased().everyMinutes(5).create();
  // Remover duplicidade do mesmo reconciliador, sem tocar em outros gatilhos.
  existentes.slice(1).forEach(t=>ScriptApp.deleteTrigger(t));
  return {ok:true,intervaloMin:5,funcao:nome};
}
function removerReconciliacaoV22(){
  const nome='reconciliarExpiradosV22';let n=0;
  ScriptApp.getProjectTriggers().filter(t=>t.getHandlerFunction()===nome).forEach(t=>{ScriptApp.deleteTrigger(t);n++;});
  return {ok:true,removidos:n};
}

// Executar em cópia e conferir J5 antes de usar na planilha oficial.
function corrigirIndicadorFichaProntaV22(){
  const sh=getSheet_(ARILUB.SHEETS.PAINEL);
  if(normalize_(sh.getRange('I5').getDisplayValue())!=='FICHA PRONTA')throw new Error('LAYOUT_PAINEL_DIVERGENTE');
  sh.getRange('J5').setFormula('=SUM(ARRAYFORMULA(IF((CANDIDATOS!A2:A996<>"")*(CANDIDATOS!I2:I996="ASSESSMENT CONCLUÍDO")*(COUNTIF(ANALISE!A2:A;CANDIDATOS!A2:A996)=15);1;0)))');
  SpreadsheetApp.flush();return {ok:true,valor:sh.getRange('J5').getDisplayValue()};
}
