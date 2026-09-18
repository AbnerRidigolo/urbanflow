# Demo em 5 minutos

1. Abra o painel executivo e diga fonte, mês e definição de viagens aceitas. Mostre os valores efetivamente calculados, sem extrapolar o mês para o ano.
2. Abra saúde, reconcilie entrada/aceitos/quarentena e explique um motivo. Abra manifesto Bronze e SHA. Diga por que não deduplicar por campos.
3. Mostre etl.py (ETL PySpark), warehouse.py (COPY isolado) e lineage de refs dbt (ELT SQL). Rode teste de reexecução/failed promotion, sem baixar novamente.
4. Previsões: compare MAE e WAPE reais do modelo e baseline. Explique shift, cutoff, split temporal, ausência vs zero e simulação histórica mensal. Se baseline ganhar, explique o resultado honestamente.
5. Mostre architecture.mmd e a área AWS alvo. Distinga claramente código local validado de Terraform de referência não implantado. Termine com próximos passos: mais meses, testes cloud autorizados e avaliação da proposta Databricks.

# Texto para LinkedIn

A versão atual, com métricas medidas e arquitetura Databricks explicitamente identificada como proposta, está em [linkedin.md](linkedin.md).
