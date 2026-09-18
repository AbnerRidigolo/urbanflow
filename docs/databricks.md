# Databricks — proposta de evolução, sem execução cloud

UrbanFlow executou PySpark, Parquet, PostgreSQL, dbt Core e MLflow localmente. **Não executou Databricks, Delta Lake nem Unity Catalog**. A arquitetura abaixo é um plano técnico para uma futura migração autorizada, sem contratação ou uso de créditos nesta entrega.

## Mapeamento da arquitetura

- Bronze: preservar o Parquet original em armazenamento de objetos; registrar manifesto e checksum. Uma tabela Delta de ingestão pode acrescentar proveniência sem substituir o arquivo original como evidência.
- Silver: portar as regras PySpark para runtime compatível. Persistir aceitos e quarentena em Delta. Substituir a partição do mês corrigido com predicado validado e transação; nunca fazer MERGE por hash de campos como se ele fosse ID de viagem.
- Gold: migrar o SQL PostgreSQL para Spark SQL/dbt-databricks. `generate_series`, casts e funções de datas exigem portabilidade e testes; trocar apenas o profile não resolve. Manter a grade hora/zona e o contrato ausência versus zero.
- Unity Catalog: organizar schemas Bronze/Silver/Gold, ownership, permissões por função e linhagem. O catálogo local atual não oferece essas capacidades de governança centralizada.
- Jobs: orquestrar ingestão, qualidade, ELT, ML e publicação do snapshot. Um gate falho deve impedir tarefas dependentes; lock local precisa ser substituído por coordenação adequada a múltiplos escritores.
- MLflow: migrar experimentos e artefatos mantendo cutoff, split temporal e comparação com baseline. Dataset e versão do modelo devem permanecer vinculados.
- BI local: consumir exportação agregada validada e versionada. Não expor tokens ou conexão de SQL Warehouse no navegador.

## Critérios antes da migração

Validar as regras em runtime real, conferir custos de compute/armazenamento, testar correções de origem, permissões, concorrência e rollback. Reconciliar exatamente as contagens locais antes de trocar a fonte do BI. Cloud continua fora da execução autorizada de custo zero.

Databricks é uma **alternativa de evolução** à referência AWS Glue/Athena existente, não um componente já operando junto dela. Não foram criados arquivos de deployment que aparentem uma migração concluída.

Referências: [Medallion no Databricks](https://docs.databricks.com/aws/pt/lakehouse/medallion), [desenho Delta Lake](https://docs.databricks.com/aws/en/lakehouse-architecture/deployment-guide/delta-lake). O padrão Medallion organiza responsabilidades; não é uma comprovação de uso da plataforma.
