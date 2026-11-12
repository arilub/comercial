# ARILUB — Patch operacional do assessment V2.2

Data: 12/11/2026. Escopo: seleção Assistente Comercial (WhatsApp/CRM/ERP).

## Diagnóstico e escopo

- O backend enviado encerrava por tempo usando `ASSESSMENT CONCLUÍDO`, independentemente do número de respostas, e acionava o motor pós-assessment.
- O navegador gravava somente blocos completos. A expiração ignorava respostas ainda não enviadas e erros de comunicação.
- A rotina de reprocessamento podia remover a ficha de entrevista existente. O painel lia a linha 7 como cabeçalho, mas o cabeçalho efetivo está na linha 8.
- Na auditoria da base: 32 registros encerrados; 20 integrais (30/30), 5 com 20, 5 com 10 e 2 sem resposta. Os 12 parciais não devem entrar no ranking de avaliações integrais.

## Arquivos

- `Code.gs`: substituição completa do backend enviado pelo consultor, com patch. Mantém rotinas de convites, recuperação, tokens, matriz de pontuação, funções históricas e URL do assessment. A versão do banco de questões na CONFIG permanece v2.0; V2.2 identifica o patch operacional.
- `index.html`: substituição completa de `avaliacao/index.html` no GitHub. Base original conferida pelo hash Git `18a595222639c6b7fd052e83e8bcdf3d9ae566be`.
- `painel.html`: substituição completa de `avaliacao/painel.html` no GitHub. Base original conferida pelo hash Git `8fd34f200634e7867fcceffc9ac052c8ad64e451`.
- `testes_backend.cjs`, `testes_interface.py` e `RESULTADOS_TESTES.txt`: 18 cenários do backend em memória e 6 cenários em Chromium, com API simulada. Não são homologação do serviço Google publicado.

**Atenção:** `Code.gs` é código administrativo privado e contém configuração de autenticação já existente. Nunca o publique no repositório público. Somente os dois HTML vão para GitHub Pages. Preserve `logo-arilub.png` e os demais arquivos do repositório. O pacote não muda a senha do painel; a configuração legada possui uma chave fixa/fraca e fallback no código. Recomenda-se rotacioná-la e remover o fallback, em ação de segurança separada, sem expor a nova chave.

## 1. Homologação antes da publicação

1. Faça backup da planilha oficial e do projeto Apps Script atual (todos os arquivos e a versão publicada), além das versões atuais dos dois HTML. Confirme que o código enviado corresponde ao projeto em uso. Pause novos convites e combine uma janela sem avaliações ativas.
2. Use uma cópia isolada da planilha vinculada e do Apps Script. Confira se o script está vinculado à cópia (não à planilha oficial). Não execute rotinas de e-mail, preparação de lote ou reset de candidatos reais. Utilize somente candidatos técnicos fictícios.
3. Substitua o `Code.gs` da cópia e salve. Execute `testeSistema()`; deve retornar 30 questões. Execute `auditarIntegridadeV22()` (somente leitura). A auditoria da cópia deve refletir os registros existentes no momento do backup.
4. Publique uma implantação de teste vinculada à cópia e aponte APENAS cópias locais dos dois HTML para a URL de teste. Não use os links reais nesta homologação.
5. Valide: 30/30 gera análise e ficha; 10 ou 20 respostas no prazo gera estado parcial sem motor; expiração sem respostas; salvamento automático no meio de um bloco; retomada após recarregar; corte de prazo; falha e nova tentativa de conexão; painel separa completo/expirado; reprocessamento não apaga entrevista. Confira que o tempo segue 25 minutos.
6. Teste também `migrarEncerradosIncompletosV22()` na cópia: somente registros encerrados incompletos devem mudar o status. Verifique que respostas, ANALISE, CONTRAPROVAS, ENTREVISTAS, tokens e decisões permanecem intactos. A aba PAINEL tem os campos de evidência/índice/ficha/parecer corrigidos para os IDs parciais existentes; as notas históricas continuam em ANALISE. A execução repetida é segura.

## 2. Implantação na base oficial (somente após homologar)

1. Abra a planilha oficial → Extensões → Apps Script. Substitua o conteúdo do arquivo `Code.gs` pela versão deste pacote, preservando outros arquivos do projeto se houver. Salve.
2. Em Implantar → Gerenciar implantações, edite a implantação Web App existente e selecione uma nova versão. Preserve a URL /exec e as permissões atuais para não quebrar links já enviados. Não crie outra URL para produção.
3. Execute `testeSistema()` e `auditarIntegridadeV22()`; compare resultados com a base. Não execute qualquer função de disparo de convites.
4. Faça commit dos dois HTML em `arilub/comercial`, caminhos `avaliacao/index.html` e `avaliacao/painel.html`. Não inclua Code.gs nem testes no repositório público. Aguarde a publicação do GitHub Pages e confira as páginas reais com um candidato técnico controlado, nunca com token de candidato real.
5. Execute `migrarEncerradosIncompletosV22()` (alteração controlada). Os 12 IDs do diagnóstico são uma fotografia de 12/11; a execução consulta os dados atuais e não usa lista fixa. Confira o número de alterações e o LOG. Esta etapa não apaga análise histórica nem ficha humana.
6. Execute `reconciliarExpiradosV22()` para fechar avaliações iniciadas cujo prazo já terminou. Confira o resultado e o LOG; não altera candidatos ainda dentro do prazo. Depois, execute `instalarReconciliacaoV22()` uma única vez para agendar o reconciliador interno a cada 5 minutos. A função não envia convites. `removerReconciliacaoV22()` remove apenas esse gatilho.
7. Atualize o painel web e confira a separação dos indicadores. A fórmula antiga de `Ficha pronta` da aba PAINEL (J5) contava apenas `ANÁLISE CONCLUÍDA`, embora o motor mantenha o status `ASSESSMENT CONCLUÍDO`. Há uma função isolada `corrigirIndicadorFichaProntaV22()` para teste em cópia; a fórmula nativa ainda precisa ser homologada no Sheets. Só a execute em produção após validar J5 na cópia. O painel web não depende dessa fórmula.

## 3. Regras após o patch

- `ASSESSMENT CONCLUÍDO`: total oficial de questões válidas e distintas, normalmente 30. Somente avaliações completas acionam o motor. O motor pode registrar falha operacional; nesse caso, o resultado da análise deve ser conferido antes de reprocessar.
- `ASSESSMENT EXPIRADO — INCOMPLETO`: prazo esgotado com menos de 30 respostas válidas. Não gera nova nota nem ficha automática; não entra no ranking integral.
- `saveProgress` salva respostas progressivamente em pequenos lotes de alterações, com confirmação de quantidade pelo servidor. `saveBlock` continua compatível com os clientes antigos. Não é possível assegurar recuperação de conteúdo que não chegou ao servidor (por exemplo, queda de internet no último segundo). O front-end não indica sucesso sem confirmação.
- Expiração com 30 respostas já gravadas dentro da janela: avaliação integral, ainda que a chamada final ocorra depois do prazo. Repetição de chamadas de encerramento não reprocessa o motor.
- Pontuação histórica de avaliações parciais continua na aba ANALISE para rastreabilidade; o painel web e a apresentação da aba PAINEL não devem compará-la à avaliação integral. A seleção e qualquer oferta de reavaliação permanecem decisões humanas.
- Não se altera o tempo de 25 minutos, o banco de questões, pesos da matriz, tokens, IDs, URLs, convites ou entrevistas registradas. As avaliações complementares de Ariane/Júlia continuam no histórico e seus registros integrais não são invalidados.

## 4. Regressão e reversão

Se ocorrer falha durante homologação/publicação, interrompa novos convites. Reimplante a versão anterior do Apps Script na implantação existente e reverta os dois commits HTML. Remova o gatilho V2.2 se instalado. A migração dos status não é automaticamente revertida pelo rollback de código; se necessário, restaure SOMENTE os campos alterados com base no backup e no LOG, sem sobrescrever respostas novas. Não restaure a planilha inteira por cima da produção sem conciliar alterações ocorridas após o backup.

## 5. Testes locais reproduzíveis

```sh
node testes_backend.cjs
python testes_interface.py
```

O segundo requer Python, Playwright e Chromium (`/usr/bin/chromium` no ambiente de teste; adapte o caminho no seu ambiente). Os testes interceptam a API em memória e usam somente dados fictícios. Nenhuma requisição de teste real foi feita à produção. O teste de trigger e a fórmula opcional J5 exigem homologação nativa.
