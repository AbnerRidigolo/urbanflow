FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PYTHONPATH=/app/src SPARK_LOCAL_IP=127.0.0.1 PYTHONUNBUFFERED=1
COPY config.json ./
COPY dbt ./dbt
COPY dashboard ./dashboard
CMD ["python", "-m", "urbanflow.cli", "run"]
