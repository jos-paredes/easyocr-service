FROM python:3.10-slim

WORKDIR /app

# SOLO dependencias esenciales (elimina build-essential y git)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copiar requirements primero para mejor cache
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar solo archivos necesarios (no toda la carpeta)
COPY ocr_server.py .

EXPOSE 8000

# Solo 1 worker y optimizado para memoria
CMD ["uvicorn", "ocr_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "asyncio"]
