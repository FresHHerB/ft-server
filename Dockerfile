# Dockerfile (v1.1 - Versão do Python Corrigida)

# ==============================================================================
# Estágio 1: Build - Instalação de dependências
# ==============================================================================
# Usamos a imagem oficial do Playwright que já vem com os navegadores e dependências do sistema.
# Esta imagem usa Python 3.12.
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy AS build

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo de dependências primeiro para aproveitar o cache do Docker.
COPY requirements.txt .

# Instala as dependências Python usando pip
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Estágio 2: Final - A imagem de produção
# ==============================================================================
# Começamos novamente da imagem base para manter a imagem final limpa
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# CORREÇÃO: Ajustado para a versão Python 3.12, que é a usada na imagem base
# Copia as dependências já instaladas do estágio de build
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# Copia todo o código da aplicação para o diretório de trabalho
COPY . .

# Expõe a porta que o Flask/SocketIO irá usar
EXPOSE 5001

# Define o comando que será executado quando o contêiner iniciar.
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5001", "--threads", "4", "--timeout", "120", "main_app:app"]
