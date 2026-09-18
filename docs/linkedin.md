# Texto para LinkedIn

Como transformar quase 3 milhões de registros em informação confiável — e explicar cada etapa do caminho?

Esse foi o foco do UrbanFlow, meu projeto de portfólio em engenharia de dados com ciência de dados e BI local.

Estruturei uma arquitetura Bronze → Silver → Gold:
• Bronze: dados originais NYC TLC, manifestos e checksums para rastreabilidade.
• Silver: ETL em PySpark, validação, quarentena e reconciliação.
• Gold: carga no PostgreSQL e ELT com dbt Core, criando fatos, dimensões e agregações para análise.

No processamento de janeiro/2024, foram 2.964.624 registros de entrada, 2.963.695 aceitos e 929 em quarentena. Reexecução e correção de origem foram testadas sem duplicar viagens; uma falha de qualidade preserva a versão anterior.

O BI local permite explorar mobilidade, previsões, saúde dos dados e a própria arquitetura. Para prever embarques por zona/hora, comparei um modelo scikit-learn com um baseline semanal, usando split temporal e features sem dados futuros, com experimentos registrados no MLflow. No recorte de teste, o MAE foi 2,880 contra 2,935 do baseline — uma melhora pequena, que não ocorreu em todas as regiões.

Também documentei uma proposta de evolução para Databricks, com Delta Lake, Unity Catalog e orquestração de jobs. Essa parte é arquitetura alvo: a execução validada foi local, sem recursos cloud pagos. A fonte é mensal, então as previsões representam uma simulação histórica, não uma operação em tempo real.

Mais do que montar um dashboard, quis demonstrar como qualidade, rastreabilidade e decisões de arquitetura sustentam uma análise confiável.

Código e documentação: https://github.com/AbnerRidigolo/urbanflow

#EngenhariaDeDados #DataEngineering #PySpark #SQL #dbt #MachineLearning #Databricks #Portfolio
