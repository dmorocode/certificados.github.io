# Dockerfile
# Use uma imagem base Python oficial (escolha uma versão de Python que você está usando localmente)
FROM python:3.9-slim-buster

# Variáveis de ambiente para ajudar o LibreOffice a funcionar em modo headless
ENV HOME=/tmp \
    XDG_CONFIG_HOME=/tmp/.config \
    XDG_DATA_HOME=/tmp/.local/share \
    TEMP=/tmp \
    TMPDIR=/tmp \
    # Desativa algumas features que podem dar problema em ambientes headless
    SAL_USE_VCLPLUGIN=gen \
    NO_LOG_REDIRECT=1

# Instala o LibreOffice, unoconv e outras dependências necessárias para a conversão de DOCX para PDF.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
        unzip \
        fontconfig \
        unoconv \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho padrão dentro do contêiner Docker
WORKDIR /app

# Copia o arquivo requirements.txt e instala as dependências Python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o restante do seu código (incluindo app_backend.py, templates/, etc.) para o contêiner.
COPY . .

# PASSO DE DIAGNÓSTICO: Lista o conteúdo do diretório de trabalho após a cópia
# Mantenha isso temporariamente para depuração se houver problemas de arquivo
RUN ls -l /app

# Define a variável de ambiente PORT. O Render injetará a porta real em tempo de execução.
ENV PORT 8000
EXPOSE $PORT

# Comando padrão para iniciar a aplicação usando Gunicorn.
CMD ["gunicorn", "app_backend:app", "--bind", "0.0.0.0:$PORT"]
