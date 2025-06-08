# aSentrX Trade Decision Engine

The aSentrX Trade Decision Engine is a FastAPI-based service designed to receive notifications from external monitoring clients (e.g., web scrapers, social media monitors). It analyzes the incoming content using AI agents and triggers automated trading actions on the Bitfinex exchange based on the analysis.

## Core Features

-   **Modular FastAPI Service:** Built with a clean separation of concerns, making it easy to extend and maintain.
-   **AI-Powered Analysis:**
    -   **FED Decision Agent:** A specialized AI agent to analyze Federal Reserve announcements, compare them against predefined expectations, and predict the market impact on Bitcoin.
    -   **Extensible Design:** Ready to incorporate other AI agents for different data sources (e.g., social media).
-   **Configurable Trading Logic:** Centralized management of trade parameters (amounts, leverage, confidence thresholds) via environment variables, allowing for fine-tuned trading strategies.
-   **Automated Trading:** Integrates with the Bitfinex API to execute `LIMIT` orders. Features a `PROD_EXECUTION` flag for safe "dry runs".
-   **Containerized & Reproducible:** Uses **Poetry** for dependency management and **Docker/Docker Compose** for easy, consistent deployment.
-   **Robust Testing Suite:** Includes a comprehensive set of unit and end-to-end tests using `pytest` to ensure reliability.

## Project Structure

```
asentrx-trade-decision-engine/
├── app/
│   ├── main.py             # FastAPI application entry point & endpoints
│   ├── config.py           # Centralized configuration from environment variables
│   ├── models.py           # Pydantic models for API payloads and AI outputs
│   ├── expectations.json   # Configurable file for FED interest rate expectations
│   ├── ai/                 # AI-related modules
│   │   └── fed_decision_agent.py
│   ├── trading/            # Trading logic and Bitfinex integration
│   │   ├── bitfinex_trader.py
│   │   ├── trade_decision_manager.py
│   │   └── trader.py
│   └── utils/              # Shared utilities (logging, etc.)
├── tests/
│   ├── unit/               # Unit tests (fast, mocked dependencies)
│   └── e2e/                # End-to-end tests (slower, real external calls)
├── .env.example            # Example environment variables
├── .env.test               # Environment variables for the test suite
├── docker-compose.yml      # Docker Compose configuration
├── Dockerfile              # Dockerfile for building the production image
├── pyproject.toml          # Poetry dependency and project configuration
└── README.md
```

---

## Getting Started

### Prerequisites

-   Python 3.12+
-   [Poetry](https://python-poetry.org/docs/#installation)
-   [Docker](https://www.docker.com/products/docker-desktop/) and Docker Compose

### 1. Local Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/asentrx-trade-decision-engine.git
    cd asentrx-trade-decision-engine
    ```

2.  **Install dependencies using Poetry:**
    This command creates a virtual environment and installs all packages listed in `pyproject.toml`.
    ```bash
    poetry install
    ```

3.  **Configure Environment Variables:**
    Copy the example environment file and fill in your actual credentials.
    ```bash
    cp .env.example .env
    ```
    **Crucial variables to set in `.env`:**
    -   `MODEL`: The language model to use (e.g., `groq:llama-3.3-70b-versatile` or `openai:gpt-4-turbo`).
    -   `GROQ_API_KEY` or `OPENAI_API_KEY`: The API key for your chosen LLM provider.
    -   `PROD_EXECUTION`: Set to `True` to enable actual trades on Bitfinex, `False` for dry runs (logs simulation messages instead).
    -   `BFX_API_KEY`, `BFX_API_SECRET`: Your Bitfinex API credentials.
    -   `TWILIO_*` variables: Required if you enable SMS notifications.

4.  **Review FED Expectations:**
    Before running, you can adjust your market expectations in `app/expectations.json`.

5.  **Run the Application Locally:**
    You can run the FastAPI server directly from the main script, which uses `uvicorn` with auto-reloading for development.
    ```bash
    poetry run python -m app.main.py
    ```
    The API will be available at `http://localhost:8000` and the interactive documentation at `http://localhost:8000/docs`.

---

## Docker Deployment

Using Docker is the recommended way to run the application in a stable environment.

1.  **Ensure your `.env` file is configured.** The `docker-compose.yml` file is set up to read it.

2.  **Build and run the container using Docker Compose:**
    ```bash
    docker-compose up --build
    ```
    To run in the background (detached mode):
    ```bash
    docker-compose up --build -d
    ```

3.  **Stopping the container:**
    ```bash
    docker-compose down
    ```

---

## Testing the Application

The project includes a robust test suite.

### 1. Configure Test Environment

Copy `.env.example` to `.env.test` and fill it with credentials for your **test/demo accounts**. Never use production keys for testing.

```bash
cp .env.example .env.test
```

### 2. Running Tests

-   **Run all unit tests (fast):**
    These tests are quick and mock all external network calls.
    ```bash
    poetry run pytest tests/unit/
    ```

-   **Run all end-to-end tests (slow):**
    These tests make real API calls to your configured LLM provider and require a valid `.env.test` file.
    ```bash
    poetry run pytest tests/e2e/
    ```

-   **Run all tests:**
    ```bash
    poetry run pytest
    ```

---

## API Usage Examples (cURL)

You can test the primary endpoint using `curl` from your terminal.

### Example 1: Simulating a "Dovish" FED Announcement

This payload contains text that should be interpreted by the AI as positive for the market.

```bash
curl -X 'POST' \
  'http://localhost:8000/notify/web-monitor' \
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

**Expected Response:**

```json
{
  "status": "success",
  "message": "Notification processed and trade logic triggered."
}
```
Check the application logs to see the AI's analysis and the resulting (simulated or real) trade action.

### Example 2: Simulating a "Hawkish" FED Announcement

This payload contains text that should be interpreted as negative, potentially triggering a "short" trade.

```bash
curl -X 'POST' \
  'http://localhost:8000/notify/web-monitor' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "uuid": "curl-test-hawkish-002",
  "type": "web-monitor",
  "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240320a.htm",
  "content_id": "monetary20240320a",
  "content": "The Federal Reserve today announced a surprise 0.25% interest rate hike, citing persistent inflationary pressures. Chairman Powell'\''s remarks were decidedly hawkish, emphasizing the committee'\''s resolve to bring inflation back to the 2% target, even at the risk of a short-term economic slowdown.",
  "ip": "127.0.0.1"
}'
```
**Note:** The single quotes within the JSON content are escaped with `'\''` for shell compatibility.