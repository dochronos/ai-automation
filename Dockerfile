# -----------------------------
# Stage 1: Build & deps
# -----------------------------
FROM python:3.11-slim AS builder
WORKDIR /app

# System deps mínimos
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------
# Stage 2: Runtime
# -----------------------------
FROM python:3.11-slim
WORKDIR /app

# Copiamos runtime de Python y el proyecto
COPY --from=builder /usr/local /usr/local
COPY . .

# Variables útiles (puedes sobreescribir con -e)
ENV API_URL=http://localhost:8001 \
    DISABLE_AI_SUMMARY=true \
    PYTHONUNBUFFERED=1

# Expose puertos API y UI
EXPOSE 8001 8501

# Comando: lanza FastAPI y Streamlit
# (Nota: DISABLE_AI_SUMMARY=true acelera la UI dentro del contenedor)
CMD ["bash","-lc","uvicorn src.main:app --host 0.0.0.0 --port 8001 & streamlit run dashboard/streamlit_app.py --server.port=8501 --server.address=0.0.0.0"]
