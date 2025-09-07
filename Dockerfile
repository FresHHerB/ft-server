# Dockerfile (v1.3 - Abordagem com Ambiente Virtual)

# ==============================================================================
# Estágio 1: Build - Instalação de dependências em um venv
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy AS build

# Cria um ambiente virtual para isolar as dependências
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Define o diretório de trabalho
WORKDIR /app

# Copia e instala as dependências DENTRO do ambiente virtual
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Estágio 2: Final - A imagem de produção
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Define o mesmo ambiente virtual para que os comandos o encontrem
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copia o ambiente virtual inteiro com as dependências já instaladas do estágio de build
COPY --from=build $VIRTUAL_ENV $VIRTUAL_ENV

WORKDIR /app
# Copia o código da aplicação
COPY . .

# Expõe a porta
EXPOSE 5001

# Comando de início (usa o gunicorn de dentro do venv)
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5001", "--threads", "4", "--timeout", "120", "main_app:app"]
