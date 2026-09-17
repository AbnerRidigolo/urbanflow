# Dicionário e contratos

**Bronze**: arquivo Parquet original no modo public_full; SHA256 dos bytes, URL, ETag, tamanho, data de obtenção, mês e classificação. public_sample é um row group reserializado, explicitamente parcial; synthetic é fixture, nunca um dado observado de NYC.

**Silver / fct_trips** — grão: uma linha aceita da origem, sem chave natural única. `pickup_at`/`dropoff_at`: timestamp local sem timezone (America/New_York). `pickup_zone_id`/`dropoff_zone_id`: chaves da tabela TLC, 1–265. `distance_miles`: milhas; `total_usd`: total registrado em USD, admite ajustes negativos; `passengers`: campo informado, pode ser nulo; `payment_type`: código TLC; `duration_minutes`: diferença temporal em minutos; `source_month`: partição da origem. Nenhuma informação identifica motorista/passageiro.

**dim_zone** — zone_id único, borough, zone_name e service_zone. IDs 264/265 representam localização não atribuível; preservar contagens, excluir geometria. **dim_hour** — todas as horas de cada mês carregado, com indicador complete do arquivo. Não confundir arquivo completo com garantia de cobertura de todas as viagens na cidade.

**fct_hourly** — chave composta zone_id/hour_at, `trips` = contagem de linhas aceitas, `total_usd` e `duration_minutes` = somas aditivas. Mês completo permite zero em uma célula sem registros aceitos. Mês parcial mantém trips nulo quando não observado; ML bloqueado. `agg_zone` e `agg_hour` são agregações derivadas, não somar ambas em uma mesma medida.

**Previsões** — grão zone_id/hour_at/model_version: trips real, prediction não negativa, baseline=lag_168, cutoff=início da hora alvo (exclusivo para eventos), train_end_exclusive, absolute_error, model_version=SHA256 do artefato. Um modelo de regressão de contagens não precisa produzir inteiro; arredondamento só na apresentação.

**Qualidade** — rejeitar timestamps ausentes, pickup fora do mês, duração <=0 ou >1440min, zonas ausentes/fora de 1–265, distância ausente/não finita/<0/>500mi, total ausente/não finito/fora de [-1000,10000]USD. Regras são escolhas do projeto, não regras oficiais TLC. Fonte original preservada permite revisar o contrato. Campos adicionais futuros são mantidos em Bronze; ausência de campo crítico impede promoção. Passageiros e pagamentos desconhecidos não removem automaticamente uma viagem.

**Tempo/ML** — timestamps sem offset não permitem recuperar qual ocorrência corresponde à hora ambígua do DST. Horas ambíguas/inexistentes viram desconhecidas nas features. Reindexação mantém lacunas; médias exigem janela completa. Fato financeiro conserva registros; dashboard usa horas locais. Nunca inferir zero para mês ausente.

**Métricas** — MAE = média de |real-previsto| por par zona/hora; WAPE = soma |real-previsto| / soma |real|; se denominador zero, WAPE indefinido (null), nunca zero artificial. Médias regionais calculadas dos pares, sem média não ponderada dos MAEs de zonas. Relatórios incluem número de pares e soma real.
