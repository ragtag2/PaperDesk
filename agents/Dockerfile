FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install -r requirements.txt

RUN useradd --create-home --user-group --uid 10001 paperdesk

COPY --chown=paperdesk:paperdesk *.py ./agents/

RUN mkdir -p /app/agents/runs/analyses \
    && chown -R paperdesk:paperdesk /app/agents/runs

USER paperdesk

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "agents.main:app", "--host", "0.0.0.0", "--port", "8000"]