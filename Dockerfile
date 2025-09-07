# Dockerfile (v1.3 - Abordagem Simplificada e Robusta)

# ==============================================================================
# Estágio 1: Build - Instalação de dependências
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy AS build

# Cria um ambiente virtual para instalar as dependências
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
# Instala as dependências DENTRO do ambiente virtual
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Estágio 2: Final - A imagem de produção
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Define o mesmo ambiente virtual
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copia o ambiente virtual inteiro com as dependências já instaladas
COPY --from=build $VIRTUAL_ENV $VIRTUAL_ENV

WORKDIR /app
# Copia o código da aplicação
COPY . .

# Expõe a porta
EXPOSE 5001

# Comando de início (agora usa o gunicorn de dentro do venv)
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5001", "--threads", "4", "--timeout", "120", "main_app:app"]
