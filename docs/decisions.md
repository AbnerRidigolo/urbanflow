# Decisões técnicas

1. **Spark obrigatório** no detalhe: engine distribuída demonstrável; pandas limitado aos agregados ML. PostgreSQL expõe a diferença entre ETL (antes da carga) e ELT (depois da carga, SQL/dbt).
2. **Versões imutáveis + ponteiro atômico**, sem overwrite destrutivo. SHA local confere integridade; ETag remoto é sinal de versão, não tratado como MD5 (multipart existe). Gate falho mantém a versão anterior; quarentena é evidência.
3. **Sem natural trip ID**: hash dos campos não torna uma linha única; viagens idênticas legítimas são preservadas. Reexecução usa substituição de partição/snapshot, não deduplicação cega.
4. **Zero versus ausência**: completo é estado do arquivo mensal, não promessa de captura universal. Apenas após arquivo completo e gate bem-sucedido preencher zero de contagens aceitas. Amostra, mês ausente e hora DST incerta não viram zero nas features.
5. **HistGradientBoosting** satisfaz a alternativa scikit-learn sem LightGBM extra. Validação temporal seleciona apenas 7/15 folhas; teste não seleciona vencedor. Erros por região/zone ajudam expor grandes volumes de zonas com zero.
6. **Snapshot SQL completo nesta versão**: simples, atômico e fácil de auditar. Bronze/Silver são incrementais por mês; dbt Gold é rebuild do conjunto selecionado. Otimização incremental Gold fica para a próxima versão.
7. **AWS sem deploy**: alvo S3/Glue/Catalog/Athena/ECS/Step Functions em Terraform. O fluxo de migração cloud não está pronto para produção; runner deliberadamente bloqueado. Não trocar runtime PostgreSQL por Athena apenas mudando profile.
8. **Limitações operacionais**: lock local não é distribuído; um crash pode deixar lock que exige conferir PID antes de removê-lo. Garbage collection de versões/schemas não é automática. Atomicidade é por camada, não transação global filesystem+PostgreSQL+MLflow. Falha de ML não revoga Gold já validada; dashboard só troca o JSON ao final.
