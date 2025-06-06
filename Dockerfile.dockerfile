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

# Instala Pandoc e um ambiente LaTeX mais específico para garantir 'xelatex'.
# Estes pacotes são comumente necessários para o Pandoc usar xelatex.
# 'texlive-xetex': O motor XeLaTeX em si.
# 'texlive-latex-base': Pacotes LaTeX fundamentais.
# 'texlive-latex-extra': Muitos pacotes LaTeX adicionais (comum para documentos complexos).
# 'texlive-fonts-recommended': Fontes comuns.
# 'texlive-binaries': Pode ser necessário para garantir que os executáveis estejam no PATH.
# 'fontconfig': Para o sistema de fontes.
# 'libxtst6', 'libxrender1': Dependências X para ambientes headless.
# 'locales': Para evitar erros de ambiente/encoding.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        pandoc \
        texlive-xetex \
        texlive-latex-base \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-binaries \
        fontconfig \
        libxtst6 \
        libxrender1 \
        unzip \
        locales \
    && rm -rf /var/lib/apt/lists/*

# Configura o locale para evitar warnings e erros
RUN locale-gen en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8

# PASSO DE DIAGNÓSTICO: Tenta encontrar o executável 'pandoc' e 'xelatex'
RUN which pandoc || echo "pandoc not found in path"
RUN which xelatex || echo "xelatex not found in path"

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
