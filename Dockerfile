# Base image simples e otimizada (slim)
FROM python:3.11-slim

# Evita que o Python escreva ficheiros .pyc no disco
ENV PYTHONDONTWRITEBYTECODE 1
# Garante que a saída do Python não fica em buffer (melhor para logs do Docker)
ENV PYTHONUNBUFFERED 1

# Define o diretório de trabalho principal
WORKDIR /app

# Instala as dependências de sistema essenciais (se necessário para algum pacote)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala o requirements.txt (para usar cache no Docker e acelerar builds)
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia o resto do código da aplicação
COPY . /app/

# Expõe a porta interna onde o Django vai correr
EXPOSE 8000

# Dá permissões de execução ao entrypoint.sh e define como arranque
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
