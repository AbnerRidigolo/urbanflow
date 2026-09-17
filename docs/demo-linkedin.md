# Demo em 5 minutos

1. Abra o painel executivo e diga fonte, mês e definição de viagens aceitas. Mostre os valores efetivamente calculados, sem extrapolar o mês para o ano.
2. Abra saúde, reconcilie entrada/aceitos/quarentena e explique um motivo. Abra manifesto Bronze e SHA. Diga por que não deduplicar por campos.
3. Mostre etl.py (ETL PySpark), warehouse.py (COPY isolado) e lineage de refs dbt (ELT SQL). Rode teste de reexecução/failed promotion, sem baixar novamente.
4. Previsões: compare MAE e WAPE reais do modelo e baseline. Explique shift, cutoff, split temporal, ausência vs zero e simulação histórica mensal. Se baseline ganhar, explique o resultado honestamente.
5. Mostre architecture.mmd e a área AWS alvo. Distinga claramente código local validado de Terraform de referência não implantado. Termine com próximos passos: mais meses, testes cloud autorizados e Power BI Desktop.

# Texto para LinkedIn — preencher só com evidência

Desenvolvi o UrbanFlow, um projeto de engenharia de dados com ciência de dados integrada usando os dados públicos NYC TLC.

Implementei ingestão versionada com checksums, ETL em PySpark, quarentena e reconciliação, carga PostgreSQL e ELT com dbt Core. No período [PERÍODO VALIDADO], o pipeline processou [ENTRADA MEDIDA] registros, aceitou [ACEITOS MEDIDOS] e segregou [REJEITADOS MEDIDOS].

Para embarques por zona/hora, comparei um baseline semanal com HistGradientBoosting em split temporal. MAE: [MODELO MEDIDO] versus [BASELINE MEDIDO]. A avaliação é uma simulação histórica; a fonte mensal não sustenta uma promessa de previsão ao vivo.

O projeto inclui um painel local de quatro páginas e preparação para Power BI. Documentei AWS como arquitetura alvo (S3, Glue, Athena, ECS e Step Functions), sem implantar recursos. Toda a validação foi local e sem serviços pagos.

https://github.com/AbnerRidigolo/urbanflow

Os campos entre colchetes são placeholders, não resultados. Copie valores de docs/validation.md ou artifacts/public_full/ml/metrics.json antes de postar. Não afirmar ter criado PBIX nem operado infraestrutura AWS.
