# ==============================================================================
# Estágio 1: Build - Instalação de dependências
# ==============================================================================
# Usamos a imagem oficial do Playwright que já vem com os navegadores e dependências do sistema.
# Isso economiza muito tempo e evita problemas de compatibilidade.
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy AS build

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo de dependências primeiro para aproveitar o cache do Docker.
# Se requirements.txt não mudar, esta camada não será reconstruída.
COPY requirements.txt .

# Instala as dependências Python usando pip
# --no-cache-dir economiza espaço na imagem final
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Estágio 2: Final - A imagem de produção
# ==============================================================================
# Começamos novamente da imagem base para manter a imagem final limpa
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Copia as dependências já instaladas do estágio de build
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# Copia todo o código da aplicação para o diretório de trabalho
COPY . .

# Expõe a porta que o Flask/SocketIO irá usar
EXPOSE 5001

# Define o comando que será executado quando o contêiner iniciar.
# Usamos 'gunicorn' para um servidor de produção mais robusto que o servidor de desenvolvimento do Flask.
# -w 1: Um único worker para evitar problemas de concorrência com o subprocesso do bot.
# -b 0.0.0.0:5001: Escuta em todas as interfaces de rede na porta 5001.
# --threads 4: Permite que o servidor lide com múltiplas conexões simultaneamente (importante para SocketIO).
# --timeout 120: Aumenta o timeout para requisições longas.
# main_app:app: Diz ao gunicorn para executar o objeto 'app' do arquivo 'main_app.py'.
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5001", "--threads", "4", "--timeout", "120", "main_app:app"]
