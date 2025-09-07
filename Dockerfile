# Dockerfile (v1.3 - Correção de Build)

# ==============================================================================
# Estágio 1: Build - Instalação de dependências
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy AS build

WORKDIR /app

# Copia o requirements.txt
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Estágio 2: Final - Imagem de produção
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Instala apenas as dependências necessárias no estágio final
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código da aplicação
COPY . .

# Expõe a porta da aplicação
EXPOSE 5001

# Comando de inicialização
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5001", "--threads", "4", "--timeout", "120", "main_app:app"]
