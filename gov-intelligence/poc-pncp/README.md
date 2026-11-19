# POC-01 — Integração PNCP / Compras.gov.br
**Produto:** GOV Intelligence — Presença Pro  
**Ambiente inicial de requisitos:** operação real de uma distribuidora fornecedora do setor público; dados internos permanecem privados.  
**Status:** código inicial de consulta desenvolvido; **requisição ao vivo e homologação pendentes**.  
**Escopo:** somente leitura pública, sem cadastro, envio de lances ou uso de credenciais.

## Achados documentais — 19/11/2026

1. O PNCP disponibiliza API pública de consultas por data de publicação: [Swagger](https://pncp.gov.br/api/consulta/swagger-ui/index.html), `GET /v1/contratacoes/publicacao`. Endpoint detalhado: `https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao`.
2. O Compras.gov.br mantém sua própria [API de dados abertos](https://www.gov.br/compras/pt-br/cidadao/portal-de-dados-abertos/documentacao-interativa-da-api-de-dados-abertos), com dados de contratações, itens e resultados. **Não presumir que o conjunto seja idêntico ao PNCP ou que todo PNCP corresponda a pregão do Compras.gov.br.**
3. O comunicado oficial **40/26, publicado em 24/09/2026**, confirma alertas no aplicativo Compras.gov.br conforme linhas de fornecimento. A desativação geral de avisos por e-mail em agosto de 2026 **não foi comprovada**; conservar os detalhes e capturas da mensagem que a operação visualizou.

## POC-01 entregue neste diretório

`pncp_radar.py` é uma consulta Python com biblioteca padrão:
- filtra publicações de modalidade 6 (pregão) por datas, UF e palavras-chave;
- pagina de forma limitada, com retentativas para erros transitórios;
- normaliza informações principais, deduplica, gera JSON e CSV;
- inclui URL e horário da consulta em cada registro;
- falha explicitamente quando a API retorna erro ou formato inesperado;
- não inventa resultados e não promete lista exaustiva.

### Execução local

```bash
python poc-pncp/pncp_radar.py --inicio 2026-11-18 --fim 2026-11-19 --uf CE --palavras "lubrificante,óleo,fluido" --paginas 2 --saida saida/pregoes_ce.json
python -m unittest discover -s poc-pncp -p "test_*.py" -v
```

Executar a partir de `gov-intelligence/`. Instalação: Python 3.10+; sem dependências adicionais. Os arquivos `saida/` não devem conter dados privados. As consultas ao vivo podem falhar por instabilidade/rate limiting.

**Importante:** filtro por `objetoCompra` é triagem por palavras, **não matching de itens**, e não substitui leitura do edital. O endpoint por publicação também não garante que as propostas ainda estejam abertas.

## Fases e critérios de aceite

| Gate | Critério objetivo | Estado |
|---|---|---|
| 0 — Fontes | Endpoints e documentação identificados | Concluído documentalmente |
| 1 — PNCP | 3 consultas reais bem-sucedidas em dias distintos, status HTTP e contagens registrados | Pendente |
| 2 — Qualidade | Amostra de 50 pregões verificada manualmente; URL, objeto, órgão, UF e prazo | Pendente |
| 3 — Compras.gov | Consultar itens e resultados reais, validar chaves de cruzamento com PNCP em 20 processos | Pendente |
| 4 — Alertas | Deduplicação entre coletas e entrega controlada de 10 alertas de teste | Pendente |
| 5 — Painel | Conectar dados homologados à V0.7 sem alterar suas métricas demonstrativas até a virada | Pendente |

## Delimitação e segurança

- Dados de clientes (cadastros, e-mails, catálogo, CNPJ, preços e fornecedores) não entram neste repositório público.
- Credenciais, se necessárias para integrações privadas posteriores, são armazenadas somente no backend privado.
- Não publicar resultados do laboratório com identificação da empresa sem autorização.
- Preservar a V0.7 como baseline demonstrativa; desenvolver ingestão em diretório isolado.
- Não realizar lances, inscrição ou qualquer modificação no Compras.gov.br.

### Próxima etapa: amostra da operação

Registrar de forma privada quais linhas de fornecimento eram cadastradas para avisos por e-mail, localização, faixa de valor, modalidades, periodicidade e exemplo da mensagem informando mudança para API. Isso permite confrontar o novo radar com o comportamento anterior sem assumir que a mensagem refletia descontinuação geral.

### Diagnóstico complementar — Compras.gov.br

`compras_dados_abertos.py` consulta inicialmente uma página de cada fonte oficial de **contratações, itens ou resultados** e armazena a resposta bruta para auditoria de schema. É exploratório; ainda não demonstra junção confiável PNCP ↔ Compras.gov.br.

```bash
python poc-pncp/compras_dados_abertos.py --tipo contratacoes --saida saida/compras_contratacoes.json
python poc-pncp/compras_dados_abertos.py --tipo itens --saida saida/compras_itens.json
python poc-pncp/compras_dados_abertos.py --tipo resultados --saida saida/compras_resultados.json
```

Fonte: [Manual da API de Dados Abertos, versão 2.0 (02/2026)](https://www.gov.br/compras/pt-br/acesso-a-informacao/manuais/manual-dados-abertos/manual-api-compras.pdf).
