# syntax=docker/dockerfile:1
FROM python:3.14-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080

COPY fit_analysis_orchestrator/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8080
CMD ["sh", "-c", "uvicorn fit_analysis_orchestrator.api:app --host 0.0.0.0 --port ${PORT}"]
