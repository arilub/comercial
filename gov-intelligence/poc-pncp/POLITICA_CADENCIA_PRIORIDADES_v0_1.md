# GOV Intelligence — Política de cadência e prioridades (proposta v0.1)
Data: 2026-11-19
Status: PROPOSTA / NÃO ATIVADA. Requer homologação operacional da ARILUB.

## Prioridades rígidas
P0 Radar atual: atualização de oportunidades, prazos e eventos. Nunca aguardar tarefas históricas.
P1 Histórico consultável: construir/reaproveitar acervo local de 36 meses, com itens, resultados, vencedores, preços e cobertura explicitada.
P2 Reconciliação: revisitar arquivo histórico consolidado e corrigir versões quando fontes oficiais indicarem mudança.
P3 Pesquisa assistida/IA: pesquisa de marcas, equivalência técnica e fornecedores, acionada sob demanda e com fonte, data e confiança.

## Janela operacional sugerida
- Pregões novos / atualizados: observação de mudança incremental, ciclo alvo 30 min como ponto de partida; testar 15 min somente após medição e política HTTP 429.
- Registros com até 60 dias desde a publicação: atualização incremental prioritária.
- Registros mais antigos mas ainda com prazos/eventos/pendências: seguir monitorando independentemente da idade.
- Histórico mais antigo estabilizado: leitura local no painel, sem consultar API por filtro/clique.
- Reconciliação leve mensal: primeiro domingo do mês, 03:30 America/Fortaleza (a validar com janelas do servidor), apenas itens arquivados, em lotes com teto de requisições.
- Importante: cronograma e periodicidade acima NÃO estão instalados no Windows Task Scheduler.

## Controle de carga e concorrência
- Somente um coletor PNCP em rede por vez; prioridade P0 interrompe/adia P1/P2/P3.
- HTTP 429: observar Retry-After quando disponível, checkpoint, pausa progressiva, limite de tentativas, sem loop agressivo.
- Backfill histórico: executar somente em janelas ociosas, lotes retomáveis, sem consumir banda da operação Comercial V3/PIF.
- Em produção: impor tempos máximos, concorrência, orçamento de requisições e limite diário adaptativo após testes.
- Ler checkpoint antes de coletar; gravar dados de forma atômica e idempotente.
- A data de atualização não substitui histórico de eventos: preservar versões e origem de cada registro.

## Modelo mínimo de persistência
- Contratacao: numeroControlePNCP, orgao, unidade, municipio IBGE, UF, datas, situacao, ultima consulta, dataAtualizacaoGlobal, fonte.
- Item: (numeroControlePNCP, numeroItem), descricao integral, catalogo, unidade, quantidade, valor estimado, situacao, temResultado, aderencia=NEUTRO.
- Resultado: (numeroControlePNCP, numeroItem, sequencialResultado), fornecedor/CNPJ, valor e quantidade homologados, ordem SRP, dataResultado, cancelamento, fonte e snapshot.
- Eventos: chave estável, tipo, data oficial, data de detecção, diff, fonte; histórico imutável de snapshots.
- Checkpoints: janela, UF, codigoMunicipioIbge opcional, pagina, ultimo sucesso, erro, proxima execução.
- Cobertura: por contratação/itens/resultados, estados NAO_CONSULTADO, PARCIAL, COMPLETO, FALHA e DADO_NAO_DISPONIVEL.

## Integridade e fronteiras
- Informações de compras, fornecedores e valores: fontes governamentais exclusivamente.
- Histórico ARILUB: somente referência opcional para calibração futura, nunca fonte dos fatos oficiais do dashboard.
- Nenhum item é aderente automaticamente: default NEUTRO até regra homologada.
- Municipio do comprador != local de entrega; preservar ambos quando identificados.
- Acesso local protegido: não publicar datasets nominais no GitHub público.
- Não tocar em Shop9, PIF, Comercial ou HTML V0.7 nesta fase.

## Critérios para ativação futura
1. Homologar coleta incremental por data de atualização, deduplicação e detecção de eventos.
2. Homologar checkpoint e recuperação após HTTP 429; provar 2–3 ciclos manuais sequenciais.
3. Medir interferência e duração em paralelo com rotinas do servidor.
4. Homologar reconciliação de um pequeno lote arquivado e preservação das versões.
5. Obter autorização explícita para agendar tarefas; validar o primeiro ciclo não assistido.
