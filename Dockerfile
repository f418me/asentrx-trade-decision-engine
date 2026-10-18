# Stage 1: Builder - Installiert Abhängigkeiten
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8.8 /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=never
ENV UV_LINK_MODE=copy

# Git is required for the pinned Bitfinex and Truthbrush dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere die Abhängigkeitsdateien, um den Docker-Cache zu nutzen
COPY uv.lock pyproject.toml .python-version ./

# Install only production dependencies from the committed lockfile.
RUN uv sync --locked --no-dev

# Stage 2: Final - Erstellt das schlanke Produktionsimage
FROM python:3.12-slim AS final

# Setze Umgebungsvariablen für die Produktion
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Erstelle einen nicht-privilegierten Benutzer für die Anwendung
RUN useradd --create-home --shell /bin/bash appuser

# Kopiere das virtuelle Environment mit den installierten Paketen vom Builder-Stage
COPY --from=builder /app/.venv ./.venv

# Kopiere den gesamten Anwendungscode
# Da der Code in einem 'app'-Verzeichnis liegt, kopieren wir dieses Verzeichnis
COPY ./app ./app

# Gib dem neuen Benutzer die Eigentümerschaft über das App-Verzeichnis
RUN chown -R appuser:appuser /app

# Wechsle zum nicht-privilegierten Benutzer
USER appuser

# Exponiere den Port, auf dem die FastAPI-Anwendung läuft
EXPOSE 8000

# Kommando zum Starten der Anwendung mit Uvicorn
# Wir geben --host 0.0.0.0 an, damit die App von ausserhalb des Containers erreichbar ist
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
