# #8 — Imagem do backend VisionDesk (core; edge/torch opcional via requirements-edge).
FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Edge (YOLO/torch) opcional — descomente p/ inferência local na imagem:
# COPY requirements-edge.txt . && pip install --no-cache-dir -r requirements-edge.txt

COPY app ./app

EXPOSE 8000
ENV VISIONDESK_HOST=0.0.0.0 VISIONDESK_PORT=8000
# Produção: múltiplos workers atrás de um proxy; GPU/edge accelerator quando disponível.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
