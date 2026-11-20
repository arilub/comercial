# GOV Intelligence — Auditoria estática inicial de candidatos externos
Data: 2026-11-19
Status: PARCIAL / NENHUM CANDIDATO APROVADO. Proibido executar, instalar ou importar códigos externos no servidor ARILUB sem novo gate.

## Procedimento e limite
Leitura direta via conector GitHub de arquivos selecionados nos repositórios, com hashes Git blob SHA abaixo. Isto NÃO constitui varredura exaustiva, não verifica binários de publicação, cadeia de dependências transitivas, CVEs, releases ou totalidade do código. Sem execução, instalação, acesso ao servidor ou tráfego PNCP neste ciclo.

## 1. AnxietyLab/pncp-cli
- README.md blob 3aff373c44f2f539211fc777657b7da9744f19aa
- pyproject.toml blob 9919dc67fa1b59a99c89018ab9b246066a2f217d
- src/pncp_cli/client.py blob 1ec47bb89d0deebdb7233b2a5286427ce2c99fcf
- src/pncp_cli/commands/skill.py blob 95be8c14312b83252ea38476c08f2935ed857234
- src/pncp_cli/skill/SKILL.md blob dbb38acce03d51d8e13634802b0c01e83645d2b0
- Manifesto: Python >=3.10, build setuptools>=68, declara MIT; pacote principal sem dependências de execução declaradas.
- Cliente HTTP: urllib, retry 429/5xx, Retry-After limitado, backoff; default pausa=0, logo configuração padrão NÃO é adequada ao PNCP sob carga.
- Superfície relevante: baixar(url,destino) aceita URL arbitrária e grava destino; deve haver allowlist de hosts, diretório sandbox e limites antes de reaproveitar conceito. Não foi constatada exfiltração maliciosa nos arquivos inspecionados.
- Comando skill.py cria ~/.claude/skills/pncp/SKILL.md (ou CLAUDE_CONFIG_DIR), copiando instruções de agente; risco de prompt injection/autoridade delegada; NÃO usar/installar.
- Recomendo: extrair APENAS ideias de janela temporal, checkpoint e respeito a Retry-After; NÃO copiar skill, cliente ou scripts de download sem auditoria completa.

## 2. gabrielgz0/pypncp
- README.md blob d0c7baefac261bad5e470c01f44d4ad9436f813b
- pyproject.toml blob 72591e4d2ea7a24bcc7ff9c68ce7cbad00a55260
- src/pypncp/client.py blob 68067474f4726350a3716e6f1bd7f56ed0bc66ee
- src/pypncp/_internal/http.py blob 1e251603ba55bdfaa2ba5a05f512bcaf6b5d7240
- .github/workflows/ci.yml blob bf9c5447d617fff5ec20fa60f7f1aad240376f77
- Python >=3.12, 3 dependências diretas httpx>=0.28.1 pydantic>=2.13.4 tenacity>=9.0.0; ranges abertos, validar lock/SBOM.
- PNCPClient default max_concurrent=3 e max_retries=3; transport usa semáforo para requisições concorrentes mas não impõe pacing global entre chamadas, então não serve como controle de taxa suficiente.
- Transporte aceita base_url configurável e HTTP verbs POST/PUT/DELETE; na camada GOV PNCP deve ser somente GET e host oficial.
- CI tem teste/ruff/mypy e publicação PyPI via workflow; passos executam terceiros em runners, não autoriza instalar no servidor.
- Recomendo: estudo da tipagem e tratamento de erros, sem instalar a dependência.

## 3. bussola-dot/radar-pncp
- README.md blob 6a21631e06385fcd9010bd9f832652565a3f90c8
- requirements.txt blob 0e833851900ffb2cb4fca7a64bcebb47362c6858
- .github/workflows/coleta.yml blob 1beb92a64079e6e41ea6c398b40bce856cbe4d8b
- README descreve SQLite upsert, radar, API web, scripts Windows, separação de histórico.
- requirements: requests>=2.31, fastapi>=0.110, uvicorn>=0.27, openpyxl>=3.1, psycopg[binary]>=3.2; sem lock detalhado nesta seleção; uso com scripts pip no CI é supply-chain surface.
- CI agenda diária 09:00 UTC, concurrency group evita processos simultâneos, env secrets DATABASE_URL e senha de e-mail; etapa coleta usa continue-on-error=true e passos posteriores if always(), risco operacional de relatório derivar de coleta parcial se não sinalizar cobertura.
- CI usa actions/checkout@v4 e setup-python@v5 por tag major mutável, em vez de commit pinado.
- Recomendação: adotar conceitualmente SQLite com upsert transacional, prioridade do radar, single-worker e relatório de cobertura, não importar workflow nem dependências.

## Decisões técnicas para ARILUB
- NÃO instalar pip/uv/pipx, npx, MCP, skills ou workflows externos.
- NÃO clonar para servidor operacional; artefatos externos somente em quarentena de análise.
- Preferir implementar internamente padrões comprováveis, com código pequeno, tests, timeout, limites de resposta, endpoints PNCP em allowlist.
- P0 prioridade radar, P1 histórico, P2 revisão mensal, P3 pesquisa de mercado/IA.
- Antes de qualquer aquisição externa posterior: inventário de todos os arquivos, scanner estático, secrets scan, SBOM e vulnerabilidades transitivas, revisão de permissões/rede, teste em ambiente isolado, aprovação formal.
- Dado PNCP/documento PDF/HTML/metadata MCP deve ser tratado como dados não confiáveis; nunca permitir que texto de edital acione comandos, alterações de arquivos ou exfiltração.

## Próximo objetivo
Implementar coletor incremental próprio e auditoria offline de progresso, reaproveitando a arquitetura POC já validada; manter apenas referências e resultados da auditoria dos projetos terceiros.
