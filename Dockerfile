# Dockerfile (v1.2 - Descoberta Dinâmica de Caminho)

# ==============================================================================
# Estágio 1: Build - Instalação e descoberta de dependências
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy AS build

WORKDIR /app

COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# NOVO: Descobre dinamicamente o caminho do site-packages e o salva em um arquivo.
# Usamos 'flask' como exemplo, pois é uma dependência garantida.
# O comando extrai a linha "Location:" e remove o prefixo "Location: ".
RUN pip show flask | grep Location | awk '{print $2}' > /app/site-packages-path.txt

# ==============================================================================
# Estágio 2: Final - A imagem de produção
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Copia o arquivo com o caminho do site-packages do estágio de build
COPY --from=build /app/site-packages-path.txt /app/site-packages-path.txt

# Copia os binários (como o gunicorn)
COPY --from=build /usr/local/bin /usr/local/bin

# Lê o caminho do arquivo e o usa em um comando `COPY` com `ARG`.
# Isso garante que o caminho correto seja usado para copiar as bibliotecas.
RUN SITE_PACKAGES_PATH=$(cat /app/site-packages-path.txt) && \
    cp -r --parents $(find $SITE_PACKAGES_PATH -mindepth 1 -maxdepth 1) /usr/local/lib/$(basename $(dirname $SITE_PACKAGES_PATH))/site-packages/

# Copia o restante do código da aplicação
COPY . .

# Expõe a porta
EXPOSE 5001

# Comando de início (sem alterações)
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5001", "--threads", "4", "--timeout", "120", "main_app:app"]
