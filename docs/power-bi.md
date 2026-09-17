# Power BI — modelo pronto para montar, sem PBIX fabricado

Não foi criado nem validado um PBIX. O painel HTML local é uma alternativa funcional gratuita, não Power BI. Power BI Desktop pode importar os CSVs em `artifacts/public_full/` ou conectar ao PostgreSQL local `127.0.0.1:55432`, banco urbanflow, usuário urbanflow, senha de desenvolvimento urbanflow_local_only. Não publicar no Service.

1. Importe dim_zone, dim_hour, fct_hourly e ml/predictions.csv. Configure tipos: IDs inteiros, datas timestamp, valores decimais, complete booleano. Renomeie predictions.csv para predictions.
2. Relacione dim_zone[zone_id] 1:* com fct_hourly[zone_id] e predictions[zone_id]. Relacione dim_hour[hour_at] 1:* com fct_hourly[hour_at] e predictions[hour_at]. Direção única da dimensão ao fato. Não ligar as duas fatos diretamente. Não relacione agg_zone/agg_hour simultaneamente para totalizar viagens.
3. Crie medidas de `measures.dax` individualmente. Filtros de região/hora operam nas dimensões compartilhadas. WAPE deve usar os pares com previsão, não todos os embarques do mês.
4. **Executivo**: cartões Viagens, Valor USD, Duração média; linha temporal, ranking de zonas. **Mobilidade**: matriz dia/hora e ranking por região; mapa com shape TLC convertido para TopoJSON e chave LocationID (Shape Map) ou visual equivalente verificado. Não geocodificar nomes de zonas como endereços.
5. **Previsões**: real/modelo/baseline na mesma escala; cartões MAE/WAPE, tabela por borough; informar teste histórico e cutoff. **Saúde**: importar quality.json via Power Query, expandir entrada/aceitos/rejeitados por mês, taxa de rejeição, SHA e status dbt.
6. Use fundo #F2F5F9, texto #182B40, destaque #139F89 e baseline #DB9140. Páginas 16:9, títulos 20–24pt e eixos legíveis. Valide totais contra dashboard/data.json antes de qualquer captura de portfólio.

Dashboard alternativo: `python -m urbanflow.cli serve` e abrir http://127.0.0.1:8080. Exportações contêm dados públicos; o modelo ML local em joblib deve ser carregado somente se confiável.
