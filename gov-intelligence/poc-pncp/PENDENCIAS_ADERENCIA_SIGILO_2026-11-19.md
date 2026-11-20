# GOV Intelligence — Pendências de aderência e orçamento sigiloso
**Registro:** 19/11/2026  
**Estado:** PENDENTE DE VALIDAÇÃO GERENCIAL — não é política aprovada.  
**Escopo:** radar PNCP Ceará; não alterar Comercial, PIF ou Shop9.

## Evidências homologadas
- SQLite POC: 540 contratações, 540 versões, integridade `ok`.
- Os 540 snapshots resumidos analisados não contêm `orcamentoSigilosoCodigo`: `None` significa **NÃO CONSULTADO**, nunca confirmação de orçamento aberto.
- Valores no resumo: 482 com estimativa positiva; 58 ausente ou zero; 193 com homologação positiva; 347 ausente ou zero.
- Consulta detalhada da contratação: `/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}`.
  - 2024/24102: código `2`, parcialmente sigiloso; estimado R$ 1.582.207,10; homologado R$ 1.272.562,70.
  - 2026/25554: código `3`, totalmente sigiloso; estimado `0`, homologado ausente.
- No pregão 2026/25554, 66 itens materiais sinalizam `orcamentoSigiloso=True`, valores estimados `0` e `temResultado=False`. Zero não é preço comprovadamente gratuito.
- `temResultado=True`: consultar resultados oficiais por item para vencedor e preços homologados; não misturar com preço estimado.
- Classificação oficial por item `materialOuServico`: `M` material, `S` serviço. Testados 189 materiais e 1 serviço em 3 checkpoints.

## Pendências a decidir com a gestão
1. **Aderência por produto**: famílias, marcas, especificações equivalentes, catálogo, linhas representadas e distribuidores habilitados.
2. **Sigilo total**: em quais condições disputar sem orçamento estimado público? Avaliar possibilidade de formar preço independente, margem mínima, frete, tributos, prazo, capital de giro e risco.
3. **Sigilo parcial**: diferentes preços e resultados por item; quando aprofundar a consulta?
4. **Preço e rentabilidade**: margem mínima, custos e comparação contextual com homologações anteriores (sem presumir preço atual).
5. **Capacidade e habilitação**: fornecedor, estoque, logística, assistência, documentos e exigências técnicas.
6. **Lotes e proposta**: regras de julgamento, participação por item versus grupo/lote, garantias, prazos, retificações e status.
7. **Bens imóveis**: excluir da seleção de produtos somente quando a natureza imóvel estiver comprovada; ausência de campo não implica bem móvel.

## Regras provisórias (não homologadas comercialmente)
- **Aderência comercial** = `NEUTRO`; produto material não implica fornecibilidade.
- **Sigilo total** = `SIGILO_TOTAL — AVALIACAO_COMERCIAL_NECESSARIA`; não excluir nem aprovar automaticamente.
- **Sigilo parcial** = preservar o que for publicado; manter condição por item.
- **Sigilo ausente no resumo** = `SIGILO_NAO_CONSULTADO`, não `NAO_SIGILOSO`.
- **Material** = elegível para triagem; **Serviço** = fora da seleção comercial de produtos. Em processo misto, analisar item a item.
- **Bem imóvel comprovado** = fora da seleção comercial; manter histórico.
- **Preço estimado zerado com sigilo** = mostrar `ORCAMENTO_SIGILOSO`; não usar zero como preço.
- **Resultado homologado** é outra dimensão; não confundir com estimativa.
- Status `Divulgada no PNCP` e prazo futuro não confirmam disponibilidade operacional sem rever eventuais retificações.

## Próxima fase técnica
1. Implementar diagnóstico de enriquecimento da classificação de sigilo **offline**, usando consulta detalhada somente em amostra controlada, sem alterar SQLite.
2. Medir presença e consistência das chaves, incluindo resultados dos itens.
3. Projetar armazenamento enriquecido separado (source/timestamp/hash), sem destruir snapshots anteriores.
4. Validar critérios gerenciais de aderência e decisão de participar com sigilo total antes de classificar oportunidades.
