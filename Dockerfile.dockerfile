# Dockerfile
# Use uma imagem base Python oficial (escolha uma versão de Python que você está usando localmente)
FROM python:3.9-slim-buster

# Variáveis de ambiente para ajudar o LibreOffice a funcionar em modo headless
ENV HOME=/tmp \
    XDG_CONFIG_HOME=/tmp/.config \
    XDG_DATA_HOME=/tmp/.local/share \
    TEMP=/tmp \
    TMPDIR=/tmp \
    SAL_USE_VCLPLUGIN=gen \
    NO_LOG_REDIRECT=1

# Instala o LibreOffice e outras dependências necessárias para a conversão de DOCX para PDF.
# Adicionadas default-jre (para Java, comum para LibreOffice) e locales (para evitar erros de locale).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
        unzip \
        fontconfig \
        default-jre \ # Adicionado: Java Runtime Environment
        locales \     # Adicionado: Para gerar locales e evitar erros de ambiente
    && rm -rf /var/lib/apt/lists/*

# Configura o locale para evitar warnings e erros
RUN locale-gen en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8

# PASSO DE DIAGNÓSTICO: Tenta encontrar o executável 'soffice'
# Isso vai imprimir o caminho nos logs de build do Render.
RUN which soffice || find /usr -name "soffice" || echo "soffice not found in common paths"

# Define o diretório de trabalho padrão dentro do contêiner Docker
WORKDIR /app

# Copia o arquivo requirements.txt e instala as dependências Python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o restante do seu código (incluindo app_backend.py, templates/, etc.) para o contêiner.
COPY . .

# PASSO DE DIAGNÓSTICO: Lista o conteúdo do diretório de trabalho após a cópia
RUN ls -l /app

# Define a variável de ambiente PORT. O Render injetará a porta real em tempo de execução.
ENV PORT 8000
EXPOSE $PORT

# Comando padrão para iniciar a aplicação usando Gunicorn.
CMD ["gunicorn", "app_backend:app", "--bind", "0.0.0.0:$PORT"]
