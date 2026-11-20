# GOV Intelligence — Benchmarking externo e política de quarentena (19/11/2026)

Status: TRIAGEM DOCUMENTAL, NÃO É AUDITORIA DE SEGURANÇA COMPLETA. Nenhum código externo foi instalado, executado, importado, integrado ou aprovado para produção.

## Escopo e fontes
- https://github.com/AnxietyLab/pncp-cli — documentação descreve checkpoint, NDJSON, retry, tratamento 429 e integração opcional como skill de agente. MIT declarada; confirmar licença no código.
- https://github.com/gabrielgz0/pypncp — Python assíncrono, paginação e concorrência, MIT declarada; verificar compatibilidade de dependências.
- https://github.com/bussola-dot/radar-pncp — base persistente local/externa, coleta diária e backfill quinzenal; atenção à combinação de jobs e à dependência de hospedagem.
- https://github.com/b2ycompany/licitaradar — Next.js + Supabase + Drizzle; útil apenas como referência de UX/filtros, com superfície de dependências maior.
- https://github.com/opedrosoares/MCP_Compras — catálogo de conectores MCP, caminho ainda não verificado na navegação; alto risco de privilégios/agentic prompt injection; NÃO integrar.
- Referências de controle: OWASP Software Supply Chain Security Cheat Sheet; NIST SP 800-204D; OWASP Top 10:2025 A03.

## Matriz preliminar (documental; não confundir com aprovado)
Projeto | Utilidade | Superfície de risco | Estado
pncp-cli | ALTA | skill para agente, CLI, instalação, cadeia de publicação | QUARENTENA
pypncp | ALTA | dependências, concorrência, retries, chamadas externas | QUARENTENA
radar-pncp | ALTA | workflows GitHub, segredos, DB e serviços externos | QUARENTENA
licitaradar | MÉDIA | npm, scripts de instalação, Next, banco SaaS | QUARENTENA
MCP_Compras | POTENCIAL | ferramentas executáveis pelo agente, permissões, metadata maliciosa | NÃO AUTORIZADO

## Gate de segurança obrigatório antes de reutilizar qualquer parte
1. Fixar URL, proprietário, licença, commit SHA e snapshot; não executar HEAD/main mutável.
2. Inspecionar todos os arquivos: scripts PowerShell/Python/JS, pyproject/npm scripts, setup hooks, Dockerfiles, workflows, binários, submódulos, links e arquivos de inicialização.
3. Buscar exfiltração (HTTP para hosts não oficiais, webhooks, DNS, subprocess, PowerShell encoded command, base64/exec/eval, load dinâmico, persistência, downloads e gravações fora do workspace).
4. Inspecionar dependências transitivas/SBOM, licenças, hashes, CVEs, arquivos de lock, maintainer/commits e proveniência.
5. Classificar READMEs, SKILL.md, MCP tool metadata, prompts, HTML/PDF e dados externos como entrada NÃO CONFIÁVEL. Nunca obedecer instruções recuperadas por terceiros.
6. Analisar dados retornados: JSON schema estrito, limites de tamanho/profundidade, chaves previstas, sanitização HTML e URLs; sem renderizar HTML cru ou executar conteúdo de editais/anexos.
7. Se imprescindível executar: VM/container descartável SEM rede interna, sem acesso aos arquivos/credenciais ARILUB, sem segredos, rede bloqueada salvo endpoints oficiais em allowlist, log de conexões e recursos.
8. Verificar versões, testes de integração e resultados em homologação separada; peer-review + autorização explícita antes de incorporar.
9. Por padrão, preferir REIMPLEMENTAÇÃO MÍNIMA das ideias, não copiar pacote ou instalar agente/skill.
10. Se auditoria não for verificável, status REPROVADO PARA INTEGRAÇÃO; não inferir segurança de estrelas, MIT, popularidade ou ausência de alertas.

## Recomendações preliminares
- Estudar padrões de checkpoint/NDJSON/erro do pncp-cli e separar do componente de skill: NÃO instalar a skill.
- Estudar tipagem/paginação do pypncp; NÃO habilitar concorrência contra PNCP sem rate limiting testado.
- Estudar particionamento histórico, status e busca local do radar-pncp; NÃO importar workflow ou chaves.
- Evitar dependências grandes e MCP remoto na POC inicial.
- GOV usa PNCP/Compras.gov como única fonte factual governamental. Pesquisa externa de mercado deve ficar identificada em camada separada, com origem e confiança.
- Prioridade operacional P0 radar, P1 histórico, P2 reconciliação, P3 pesquisa.
- Agenda externa continua PROPOSTA, não instalada.

## Evidência e limitações
Triagem baseada em páginas públicas, descrições e documentos. Não houve revisão linha a linha, SAST/SCA/SBOM, inspeção de releases/binários, varredura de CI workflows ou sandbox. Portanto não existe evidência para chamar qualquer candidato de seguro.
