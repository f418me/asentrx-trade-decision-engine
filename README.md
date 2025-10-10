

> **Note:** This service is a component of the [aSentrX Project](https://github.com/f418me/aSentrX). Please see the main repository for a complete architectural overview.

# aSentrX Trade Decision Engine

The aSentrX Trade Decision Engine is a FastAPI-based service designed to receive notifications from external monitoring clients. It analyzes the incoming content using specialized AI agents and triggers automated trading actions on the Bitfinex exchange based on the analysis.

## Core Features

-   **Modular FastAPI Service:** Built with a clean separation of concerns, making it easy to extend and maintain.
-   **Dual AI-Powered Analysis Pipelines:**
    -   **FED Decision Agent:** A specialized agent to analyze Federal Reserve announcements, compare them against predefined expectations, and predict the market impact on Bitcoin.
    -   **Social Media Agent:** A second agent pipeline to analyze social media posts, classify them by topic (market, bitcoin, tariffs), and predict the price direction.
-   **Source-Based Routing:** Incoming notifications are routed to the correct AI agent based on their `type` (`web-monitor` or `truthsocial`).
-   **Configurable Trading Logic:** Centralized and distinct management of trade parameters (amounts, leverage, confidence thresholds) for both FED and Social Media events via environment variables.
-   **Automated Trading:** Integrates with the Bitfinex API to execute `LIMIT` orders. Features a `PROD_EXECUTION` flag for safe "dry runs".
-   **Containerized & Reproducible:** Uses **Poetry** for dependency management and **Docker/Docker Compose** for easy, consistent deployment.
-   **Robust Testing Suite:** Includes a comprehensive set of unit and end-to-end tests using `pytest` to ensure reliability.

## Project Structure

```
asentrx-trade-decision-engine/
├── app/
│   ├── main.py             # FastAPI entry point & routing logic
│   ├── config.py           # Centralized configuration from .env
│   ├── models.py           # Pydantic models for API payloads & AI outputs
│   ├── expectations.json   # Configurable file for FED expectations
│   ├── ai/
│   │   ├── fed_decision_agent.py
│   │   └── social_media_agent.py # <-- New Agent
│   ├── trading/
│   │   └── trade_decision_manager.py # Handles logic for both event types
...
```

---

## Getting Started

### Prerequisites

-   Python 3.12+
-   [Poetry](https://python-poetry.org/docs/#installation)
-   [Docker](https://www.docker.com/products/docker-desktop/)

### Setup and Run Locally (with Poetry)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/f418me/asentrx-trade-decision-engine.git
    cd asentrx-trade-decision-engine
    ```

2.  **Set up environment variables:**
    Copy the example `.env-example` file to `.env` and fill in the required values (e.g., API keys, notification settings).
    ```bash
    cp .env-example .env
    ```

3.  **Install dependencies:**
    Make sure you have Poetry installed, then run:
    ```bash
    poetry install
    ```

4.  **Run the application:**
    The application will be served by Uvicorn and accessible at `http://localhost:8000`.
    ```bash
    poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```

### Setup and Run (with Docker)

1.  **Clone the repository and set up the environment:**
    Follow steps 1 and 2 from the local setup guide above.

2.  **Build and run the Docker container:**
    This will start the service in a detached container.
    ```bash
    docker-compose up --build -d
    ```

3.  **Check the logs:**
    ```bash
    docker-compose logs -f
    ```

### Running Tests

The test suite is divided into several categories using pytest markers.

-   **`unit`**: Fast tests for individual components.
-   **`e2e`**: End-to-end tests that mock external services.
-   **`live_llm`**: A special E2E test that makes a real call to the configured LLM.

You can run tests as follows:

**1. Run all tests (including the live LLM test):**
```bash
poetry run pytest
```

**2. Run only the fast unit and mocked E2E tests:**
This is the recommended command for CI/CD and most local testing.
```bash
poetry run pytest -m "not live_llm"
```

**3. Run only the live LLM integration test:**
Requires a valid LLM API key in `.env.test`.
```bash
poetry run pytest -m live_llm
```

---

## API Usage Examples (cURL)

You can test the primary `/notify` endpoint using `curl`.

### Example 1: Simulating a "Dovish" FED Announcement (`web-monitor`)

This payload contains text that should be interpreted by the **FED Decision Agent**.

```bash
curl -X 'POST' \
  'http://localhost:8000/notify' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "uuid": "curl-test-dovish-001",
  "type": "web-monitor",
  "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240131a.htm",
  "content_id": "monetary20240131a",
  "content": "In a surprising move, the Federal Open Market Committee (FOMC) announced today they will not only hold interest rates steady but also signaled a potential rate cut sooner than anticipated. Chairman Powell mentioned concerns about slowing economic growth, suggesting a more accommodative monetary policy is necessary.",
  "ip": "127.0.0.1"
}'
```

### Example 2: Simulating a "Hawkish" Social Media Post (`truthsocial`)

This payload contains text that should be interpreted by the **Social Media Agent**.

```bash
curl -X 'POST' \
  'http://localhost:8000/notify' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "uuid": "curl-test-tariffs-001",
  "type": "truthsocial",
  "url": "https://truthsocial.com/@user/123",
  "content_id": "123",
  "content": "The massive tariffs on China are working. Billions are pouring into our treasury. We will be forced to increase them even further if they don't start playing fair. AMERICA FIRST!",
  "ip": "127.0.0.1"
}'
```

**Expected Response (for both):**

If the analysis results in an actionable trade:
```json
{
  "status": "success",
  "message": "Notification processed and trade logic triggered."
}
```
Check the application logs to see which AI agent was used and the resulting (simulated or real) trade action.
