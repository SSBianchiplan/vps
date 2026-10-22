.PHONY: backend frontend test build install-edge

backend:        ## Sobe o backend (FastAPI/uvicorn)
	bash scripts/run-backend.sh

frontend:       ## Sobe o frontend (Vite)
	bash scripts/run-frontend.sh

test:           ## Roda os testes do backend
	cd backend && . .venv/bin/activate && pip install -q -r requirements-dev.txt && pytest -q

build:          ## Build de produção do frontend
	cd frontend && npm run build

install-edge:   ## Instala o caminho edge opcional (YOLO/OCR) — use Python 3.12
	cd backend && . .venv/bin/activate && pip install -r requirements-edge.txt
