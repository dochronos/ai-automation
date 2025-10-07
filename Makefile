run:
	uvicorn src.main:app --reload --port 8001 & streamlit run dashboard/streamlit_app.py

docker-build:
	docker build -t ai-automation:latest .

docker-run:
	docker run --rm -p 8001:8001 -p 8501:8501 \
		-e API_URL="http://localhost:8001" \
		-e DISABLE_AI_SUMMARY="true" \
		ai-automation:latest

# Dev con bind-mount (recarga rápida de código sin rebuild completo)
docker-dev:
	docker run --rm -p 8001:8001 -p 8501:8501 \
		-v $$(pwd):/app \
		-e API_URL="http://localhost:8001" \
		-e DISABLE_AI_SUMMARY="true" \
		ai-automation:latest