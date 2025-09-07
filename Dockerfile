# Dockerfile (v1.4 - Versão Final)
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema se necessário
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requirements primeiro (para cache do Docker)
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instala os navegadores do Playwright
RUN playwright install chromium

# Copia todo o código da aplicação
COPY . .

# Cria diretórios necessários
RUN mkdir -p logs && chmod 755 logs

# Expõe a porta da aplicação
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Comando de inicialização
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5001", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "main_app:app"]
