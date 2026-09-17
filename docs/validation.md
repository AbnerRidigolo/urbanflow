# Validação local — 16/09/2026

## Execução real medida

Fonte: NYC TLC Yellow Taxi, janeiro/2024. Download completo de **49.961.641 bytes**. SHA256 `c4d59da7bbc8abaeeeb1727947ee93d9891a71acb42854bd80db1571b2030510`. Manifesto em `data/bronze/public_full/2024-01/current.json`.

Entrada **2.964.624**; aceitos **2.963.695**; quarentena **929**. Motivos: 886 duration_invalid, 25 distance_invalid, 18 outside_partition. A soma reconcilia. Original preservado e Silver promovida após verificação. Valor total registrado aceito: **US$ 79.410.362,63**; não representa lucro.

PostgreSQL 16 portátil, loopback 127.0.0.1:55432. COPY real de 2.963.695 linhas. dbt Core 1.12.4 + dbt-postgres 1.9.0: **6 modelos e 10 testes passaram**. Views analytics apontam para schema validado; logs e run_results.json em `artifacts/dbt/uf_gold_ca0e4f8751/`.

## ML real, preliminar

Warmup: 168h. Validação começa 22/01 às 09h; teste começa 27/01 às 04h e termina 31/01 às 23h. Treino final: 121.900 pares. Teste: **30.740 pares zona/hora**, com 476.259 embarques reais aceitos. Modelo HistGradientBoosting, 15 folhas, 80 iterações.

- MAE modelo: **2,879730**; baseline semanal: **2,935459**.
- WAPE modelo: **18,5871%**; baseline: **18,9468%**.
- Modelo melhora ligeiramente o agregado, mas perde para baseline em várias regiões esparsas, inclusive Bronx, Brooklyn, Queens e Staten Island. WAPE em Staten Island é muito alto por baixo denominador e excesso de previsão. Não afirmar superioridade uniforme.
- Um único mês e menos de uma semana de teste não sustentam generalização anual. Sem dados em tempo real, sem intervalos calibrados, sem avaliação de impacto operacional.

MLflow SQLite foi inicializado e registrou parâmetros, MAE, modelo, métricas e CSV. `analytics.predictions` contém 30.740 previsões com cutoff, train_end_exclusive e model_version; verificação SQL confirmou treino anterior ou igual ao início de cada hora alvo. Arquivos em `artifacts/public_full/ml/`.

## Verificações executadas

- Testes de features: mutação de dados futuros não altera features anteriores; lag por hora de calendário; ausência não vira zero; DST inválido excluído; WAPE zero-denominador indefinido; orçamento de linhas; ML bloqueado para amostra parcial; lock/JSON atômico.
- Suíte principal: **9 testes passaram em 87,04 segundos**, incluindo Spark, substituição da partição após correção de origem, rebuild PostgreSQL/dbt sem duplicação e dbt reprovado preservando as views Gold anteriores. Banco de teste separado `urbanflow_test`; dados reais não foram sobrescritos. XML em `artifacts/pytest-results.xml`.
- Ingestão: **3 testes adicionais passaram em 0,22s** — orçamento impede requisição excessiva, resposta integral inesperada a Range é recusada e ETag estável com checksum válido reutiliza o arquivo. XML em `artifacts/pytest-ingest.xml`. Total: **12 testes executados e aprovados**.
- `scripts/validate_static.py`: parse AST Python, HCL, YAML, JSON e presença dos assets passou.
- `node --check dashboard/app.js`: passou.
- `docker compose config --quiet`: passou; **containers não foram iniciados/testados**, pois Docker Desktop não disponibilizou daemon neste host.
- Terraform 1.9.8 + AWS provider 5.100.0: `fmt -check` e `validate` passaram após `init -backend=false`. **Nenhum plan/apply, credencial AWS, resource query, deploy ou custo cloud.** Terraform é referência, runner cloud bloqueado e adaptadores ainda pendentes conforme infra/README.md.
- Navegador local: páginas executivo/mobilidade/previsões/saúde renderizadas, mapa real de 263 zonas, filtro Queens e reset para todas, seleção JFK e reset da série de previsão; console sem erros. Viewport desktop verificado; mobile não foi inspecionado visualmente.

## Limites honestos da entrega

Não há PBIX verificado nem publicação Power BI. Exportações, DAX e instruções concretas foram entregues; painel HTML é a alternativa local. AWS é arquitetura alvo e código estático de referência, não uma migração operacional concluída. CI manual foi escrito, mas não executado no GitHub. Defaults têm três meses configuráveis; somente janeiro/2024 foi processado com dados reais nesta validação.

O ambiente inicial aproveitou dependências Python previamente instaladas via venv com system-site-packages. requirements.txt fixa as dependências diretas relevantes; uma instalação limpa/Compose ainda deve ser validada para atestar reprodução fora deste host. Aviso Windows sobre winutils não impediu Spark; saída usa streaming Arrow em partições pequenas. Java/Python podem imprimir aviso de permissão ao encerrar o gateway, embora os testes/artefatos tenham passado.
