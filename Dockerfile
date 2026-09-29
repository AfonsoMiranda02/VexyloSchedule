# Base image estável e otimizada (slim)
FROM python:3.11-slim

# Evita ficheiros .pyc e ativa unbuffered stdout/stderr para streaming correto de logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependências essenciais de compilação e limpar cache apt
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python com cache isolada
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Criar utilizador não-root para execução segura do processo
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copiar código da aplicação
COPY . /app/

# Garantir permissões de execução e posse do diretório
RUN chmod +x /app/entrypoint.sh \
    && chown -R appuser:appuser /app

# Executar como utilizador não privilegiado
USER appuser

EXPOSE 8000

# Verificação de saúde da aplicação
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/').read()" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
