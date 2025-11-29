# Fast, clean, Streamlit-friendly base
FROM python:3.11-slim

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# -----------------------------
# 1. Install system dependencies
# -----------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg build-essential libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# 2. Work directory
# -----------------------------
WORKDIR /app

# -----------------------------
# 3. Copy requirement file first (cache optimization)
# -----------------------------
COPY requirements.local.txt /app/requirements.local.txt

# -----------------------------
# 4. Install Python dependencies
# -----------------------------
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install CPU torch
RUN pip install --no-cache-dir \
    torch==2.1.2+cpu \
    -f https://download.pytorch.org/whl/cpu/torch_stable.html

# Install all requirements
RUN pip install --no-cache-dir -r requirements.local.txt

# -----------------------------
# 5. Install spaCy English model (robust)
# Try known model wheel versions until one succeeds.
# -----------------------------
RUN set -e; \
    for ver in 3.7.0 3.6.0 3.5.0 3.4.0; do \
        url="https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-${ver}/en_core_web_sm-${ver}-py3-none-any.whl"; \
        echo \"Attempting to install spaCy model wheel: ${url}\"; \
        pip install --no-cache-dir "${url}" && break || echo \"Failed to install ${url}\"; \
    done


# -----------------------------
# 6. Copy all project files
# -----------------------------
COPY . /app

# -----------------------------
# 7. Streamlit config
# -----------------------------
ENV PORT=8501
EXPOSE 8501

# -----------------------------
# 8. Entrypoint
# -----------------------------
CMD ["streamlit", "run", "app_deploy.py", "--server.port=8501", "--server.address=0.0.0.0"]
