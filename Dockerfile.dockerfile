# Dockerfile
# Use uma imagem base Python oficial
FROM python:3.9-slim-buster

# Variáveis de ambiente (mantidas, podem ser úteis para outros aspectos)
ENV HOME=/tmp \
    XDG_CONFIG_HOME=/tmp/.config \
    XDG_DATA_HOME=/tmp/.local/share \
    TEMP=/tmp \
    TMPDIR=/tmp \
    SAL_USE_VCLPLUGIN=gen \
    NO_LOG_REDIRECT=1

# Instala Pandoc e um ambiente LaTeX minimalista (xelatex) para conversão de DOCX para PDF.
# 'texlive-xetex' fornece o motor xelatex, que Pandoc usa para gerar PDFs de alta qualidade.
# 'texlive-fonts-recommended' para fontes básicas.
# 'libxtst6', 'libxrender1': dependências comuns para ambientes headless que podem precisar de X (mesmo que virtual).
# 'locales': para evitar erros de locale.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        pandoc \
        texlive-xetex \
        texlive-fonts-recommended \
        libxtst6 \
        libxrender1 \
        unzip \
        fontconfig \
        locales \
    && rm -rf /var/lib/apt/lists/*

# Configura o locale para evitar warnings e erros
RUN locale-gen en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8

# PASSO DE DIAGNÓSTICO: Tenta encontrar o executável 'pandoc' e 'xelatex'
RUN which pandoc || echo "pandoc not found in path"
RUN which xelatex || echo "xelatex not found in path"
# RUN find /usr -name "pandoc" || echo "pandoc not found in /usr" # Opcional, para depuração mais profunda

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
