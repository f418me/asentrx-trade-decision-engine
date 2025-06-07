# Stage 1: Builder - Installiert Abhängigkeiten
FROM python:3.12-slim AS builder

# Setze Umgebungsvariablen für Poetry
ENV POETRY_VERSION=1.8.2 # Eine neuere, stabile Version von Poetry
ENV POETRY_HOME="/opt/poetry"
ENV POETRY_CACHE_DIR="/tmp/poetry_cache"
# Wir erstellen ein virtuelles Environment im Projektverzeichnis, um es einfach kopieren zu können
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

# Installiere Systemabhängigkeiten (curl zum Herunterladen von Poetry)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Installiere Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION}
ENV PATH="${POETRY_HOME}/bin:${PATH}"

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere die Abhängigkeitsdateien, um den Docker-Cache zu nutzen
COPY poetry.lock pyproject.toml ./

# Installiere die Projekt-Abhängigkeiten
# --no-interaction: Keine interaktiven Fragen
# --no-ansi: Deaktiviert ANSI-Output
# --no-dev: Installiert keine Entwicklungs-Abhängigkeiten
RUN poetry install --no-interaction --no-ansi --no-dev

# Stage 2: Final - Erstellt das schlanke Produktionsimage
FROM python:3.12-slim AS final

# Setze Umgebungsvariablen für die Produktion
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:${PATH}" # Füge das venv zum PATH hinzu

WORKDIR /app

# Erstelle einen nicht-privilegierten Benutzer für die Anwendung
RUN useradd --create-home --shell /bin/bash appuser

# Kopiere das virtuelle Environment mit den installierten Paketen vom Builder-Stage
COPY --from=builder /app/.venv ./.venv

# Kopiere den gesamten Anwendungscode
# Da der Code in einem 'app'-Verzeichnis liegt, kopieren wir dieses Verzeichnis
COPY ./app ./app

# Kopiere andere wichtige Dateien
COPY ./expectations.json ./app/expectations.json # Stelle sicher, dass die Erwartungsdatei am richtigen Ort ist

# Gib dem neuen Benutzer die Eigentümerschaft über das App-Verzeichnis
RUN chown -R appuser:appuser /app

# Wechsle zum nicht-privilegierten Benutzer
USER appuser

# Exponiere den Port, auf dem die FastAPI-Anwendung läuft
EXPOSE 8000

# Kommando zum Starten der Anwendung mit Uvicorn
# Wir geben --host 0.0.0.0 an, damit die App von ausserhalb des Containers erreichbar ist
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]