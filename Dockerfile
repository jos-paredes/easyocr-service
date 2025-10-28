# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Dependencias del sistema necesarias para PIL / easyocr
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código
COPY . .

# Exponer puerto (Render lo mapeará)
EXPOSE 8000

# Comando por defecto para ejecutar uvicorn
CMD ["uvicorn", "ocr_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
