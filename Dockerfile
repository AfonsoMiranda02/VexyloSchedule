# Estágio 1: Compilação de Assets Frontend (Tailwind CSS)
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tailwind.config.js ./
COPY website/ ./website/
COPY static/ ./static/
RUN npm run build:css

# Estágio 2: Compilação das Dependências Python
FROM python:3.11-slim AS python-builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Estágio 3: Imagem Final de Execução (Runtime leve sem compilador gcc/headers)
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Apenas bibliotecas de runtime necessárias (sem gcc nem libpq-dev)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependências Python já instaladas do builder
COPY --from=python-builder /install /usr/local

# Criar utilizador não-root
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copiar código da aplicação
COPY . /app/
# Copiar CSS compilado de produção
COPY --from=frontend-builder /app/static/css/tailwind.css /app/static/css/tailwind.css

# Permissões do entrypoint e do diretório
RUN chmod +x /app/entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health/ || exit 1

ENTRYPOINT ["./entrypoint.sh"]
