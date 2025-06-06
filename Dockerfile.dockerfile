# Dockerfile
# Use uma imagem base Python oficial (escolha uma versão de Python que você está usando localmente)
# Ex: python:3.9-slim-buster ou python:3.10-slim-buster
FROM python:3.9-slim-buster

# Instala o LibreOffice e dependências necessárias para a conversão de DOCX para PDF.
# Estas são as dependências do Ubuntu que o docx2pdf precisa.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
        # Dependências adicionais que podem ser úteis para docx2pdf ou Flask
        unzip \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho dentro do contêiner Docker
WORKDIR /app

# Copia o arquivo requirements.txt e instala as dependências Python
# Isso aproveita o cache do Docker se as dependências não mudarem
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do seu código (incluindo app.py, wsgi.py, templates/, etc.) para o contêiner
COPY . .

# Define a porta que o aplicativo vai escutar no contêiner.
# O Render injetará a porta real via variável de ambiente $PORT.
ENV PORT 8000
EXPOSE $PORT

# Comando para iniciar a aplicação usando Gunicorn.
# O Render pode sobrescrever isso com o "Start Command" na UI ou render.yaml
CMD ["gunicorn", "wsgi:application", "--bind", "0.0.0.0:$PORT"]