# AWS — arquitetura alvo, sem recursos em execução

Este Terraform é uma **base de infraestrutura para revisão**, não uma migração cloud concluída. Não foi feito apply, deploy, chamada a recursos AWS, uso de créditos ou consulta faturável. A agenda nasce DESABILITADA. O runner cloud falha deliberadamente até os adaptadores estarem prontos. Não use esta pasta para afirmar experiência operacional de produção.

S3 Bronze/Silver/Gold e artefatos: versionamento, bloqueio público, TLS e SSE-S3. Glue PySpark e Catalog. Athena com limite de 1 GiB por query e resultados criptografados. EventBridge → Step Functions → ECS/Glue/dbt/ML; falhas → SNS. Imagem ECR imutável, rede privada fornecida como variável. GitHub OIDC limitado a repositório e environment exatos, sem permissão de deploy anexada.

## Validação sem conta

`terraform fmt -check` e `terraform init -backend=false` seguido de `terraform validate`. O init baixa provider gratuito; não executar plan/apply. Também há `scripts/validate_static.py` para parse HCL e JSON sem Terraform.

## Antes de uma futura implantação autorizada

- Portar ingestão para S3 com manifestos condicionais e trava distribuída (o lock local não basta), registrar partições no Catalog apenas após gate.
- Implementar dbt-athena-core separadamente: SQL PostgreSQL com generate_series não é compatível automaticamente. Athena exige CTAS/Iceberg e estratégia de partições, catálogo e permissões de delete cuidadosamente limitadas.
- Empacotar a biblioteca UrbanFlow para Glue 5.0 (Spark 3.5.4 / Python 3.11) e testar schema/timezone. A validação local usa Spark 3.5.3; não presumir equivalência total. [Runtime oficial](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html).
- Substituir cloud.runner por adaptadores testados de ingestão, dbt e ML; receber mês/run_id por Overrides. A máquina de estados é uma referência de dependências.
- Separar IAM task por estágio; o role de referência tem acesso combinado às quatro camadas. Ajustar prefixos e conta exata nas permissões CloudWatch/Step Functions.
- Definir endpoints privados/NAT e custos, gravar temporários em volume gravável, adicionar alarmes CloudWatch e assinatura SNS confirmada.
- Criar orçamento/alertas **não garante custo zero**. Free Tier não foi usado. Não implantar sob a restrição atual.
