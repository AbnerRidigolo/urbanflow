"""Cloud migration guard: never imply local postgres/dbt is an Athena deployment."""
raise SystemExit("Cloud disabled: configure/test S3 ingestion, Athena adapter, task inputs and model storage before deploying. Local mode is fully independent of AWS.")
