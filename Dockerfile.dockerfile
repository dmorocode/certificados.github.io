# Dockerfile
# Use uma imagem base Python oficial
FROM python:3.9-slim-buster

# Variáveis de ambiente
ENV HOME=/tmp \
    XDG_CONFIG_HOME=/tmp/.config \
    XDG_DATA_HOME=/tmp/.local/share \
    TEMP=/tmp \
    TMPDIR=/tmp \
    SAL_USE_VCLPLUGIN=gen \
    NO_LOG_REDIRECT=1

# Instala Pandoc e um ambiente LaTeX mais completo para garantir 'xelatex'.
# Vamos tentar 'texlive-full' primeiro para garantir todas as dependências, mas esteja ciente que é GRANDE.
# Se 'texlive-full' resultar em uma imagem muito grande ou tempo de build excessivo,
# a alternativa seria: texlive-latex-extra texlive-fonts-extra texlive-pictures
# e verificar dependências como imagemagick, ghostscript, poppler-utils
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        pandoc \
        # Opção 1: Texlive-full (Garanti o xelatex, mas é muito grande)
        texlive-full \
        # --- OU ---
        # Opção 2: Pacotes mais específicos (se texlive-full for um problema)
        # texlive-xetex \
        # texlive-fonts-recommended \
        # texlive-latex-extra \
        # texlive-fonts-extra \
        # gsfonts \ # Common PostScript fonts
        # fontconfig \ # Já tinha, mas é importante
        # libxtst6 \
        # libxrender1 \
        unzip \
        # fontconfig \ # Já incluído em outras instalações
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
