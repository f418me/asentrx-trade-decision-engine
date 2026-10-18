

> **Note:** This service is a component of the [aSentrX Project](https://github.com/f418me/aSentrX). Please see the main repository for a complete architectural overview.

# aSentrX Trade Decision Engine

The aSentrX Trade Decision Engine receives monitor notifications, asks Jev typed questions in one API request, and applies local Python policies before the existing Bitfinex trade gates. All schemas, policies and tests live in this repository. There is no LLM fallback or dependency on an evaluation repository.

## Jev Configuration and Policy

Set `TYPESAFE_API_KEY`, `JEV_MODEL=typesafe:jev-1.13.0`, `JEV_CONFIDENCE_THRESHOLD=0.85` and `JEV_TIMEOUT_SECONDS=10` in `.env` or Fly secrets. The model is pinned to the version used in the live FOMC tests; evaluate future versions before changing it. The old `MODEL` and other model-provider keys are no longer used. Keep `PROD_EXECUTION=False` for initial evaluation.

Each analysis has one output schema and no tools or fallback. All questions are sent together. An overall timeout and zero agent retries bound waiting; timeout or provider failure produces `success_analysis_failed` without a trade. Unknown answers or missing, invalid or low confidence produce `success_no_action` without invoking the trader.

- **FOMC:** An explicit fresh rate decision is required. Signed rate surprise versus the baseline takes precedence over guidance. When rates match, more dovish guidance is positive, more hawkish guidance negative, and in-line/mixed guidance neutral. Missing guidance prevents a decision only when rates match.
- **CPI:** Jev compares headline/core monthly and annual readings to the baseline. A difference of at least 0.1 percentage point counts as a surprise. A core surprise is required for direction; conflicting readings are neutral. Missing readings abstain.
- **NFP:** Payroll surprises require at least 30k difference; unemployment and monthly wages require 0.1 percentage point. Soft payrolls and wages with unemployment at/above baseline are positive; the reverse is negative. Conflicts or a growth scare are neutral; unknown inputs abstain.
- **Truth Social:** Jev classifies the catalyst, concrete new action, transmission and timing. Python maps risk-on/off to up/down, vetoes contradictions, and retains the existing timing and sizing gates. `novelty_score` is now binary (1 for supported new action, otherwise 0). This is a text judgment, not verification against market history or prior posts.

`confidence` is the minimum provider confidence of the fields needed by the policy, including release relevance. It is **not** an estimated probability of a profitable trade and is not calibrated to the former LLM confidence. Existing trade thresholds, amounts and leverage remain configured separately; re-evaluate them on held-out releases before live use. CPI/NFP numeric `actual_*` fields remain null because these schemas classify comparisons rather than extract arbitrary numbers.

Console logs and Logfire's `jev_analysis_completed` include content ID/hash, exact baseline, model, policy version, judgments, provider confidence, decision and elapsed milliseconds. `jev_analysis_failed` records failures and elapsed time. No extra model call generates explanations. Actual end-to-end latency still includes the monitor, network and exchange; measure it in dry runs.

## Core Features

-   **Modular FastAPI Service:** Built with a clean separation of concerns, making it easy to extend and maintain.
-   **Jev Analysis and Python Policies:**
    -   **FED Decision Agent:** Jev identifies the announced rate change and guidance; Python compares them against the baseline to determine the Bitcoin signal.
    -   **NFP Decision Agent:** Analyzes official BLS Employment Situation releases against the current labor-market baseline.
    -   **CPI Decision Agent:** Analyzes official BLS Consumer Price Index releases against the current inflation baseline, with core CPI weighted most heavily.
    -   **Social Media Agent:** Jev classifies the event, concrete new action, transmission and timing; local policy determines whether it is tradeable and its Bitcoin direction.
-   **Source-Based Routing:** Incoming notifications are routed to the correct Jev analyzer based on their `type` (`web-monitor` or `truthsocial`) and macro source (`fed`, `nfp`, or `cpi`).
-   **Authenticated Notifications:** Monitor clients must send `Authorization: Bearer <NOTIFY_AUTH_TOKEN>` before any analysis or trade logic runs.
-   **Configurable Trading Logic:** Centralized and distinct management of trade parameters (amounts, leverage, confidence thresholds) for both FED and Social Media events via environment variables.
-   **Automated Trading:** Integrates with the Bitfinex API to execute `LIMIT` orders. Features a `PROD_EXECUTION` flag for safe "dry runs".
-   **Containerized & Reproducible:** Uses **uv** for dependency management and **Docker/Docker Compose** for easy, consistent deployment.
-   **Robust Testing Suite:** Includes a comprehensive set of unit and end-to-end tests using `pytest` to ensure reliability.

## Project Structure

```
asentrx-trade-decision-engine/
├── app/
│   ├── main.py             # FastAPI entry point & routing logic
│   ├── config.py           # Centralized configuration from .env
│   ├── models.py           # Pydantic models for API payloads & AI outputs
│   ├── expectations.json       # Configurable file for FED expectations
│   ├── nfp_expectations.json   # Configurable file for NFP expectations
│   ├── cpi_expectations.json   # Configurable file for CPI expectations
│   ├── ai/
│   │   ├── jev_analyzer.py    # Single request, timeout and audit logging
│   │   ├── jev_schemas.py     # Typed questions for each source
│   │   ├── jev_policy.py      # Local decisions and abstention
│   │   └── agents/            # Source-specific entry points
│   ├── trading/
│   │   └── trade_decision_manager.py
...
```

---

## Getting Started

### Prerequisites

-   Python 3.12+
-   [uv](https://docs.astral.sh/uv/getting-started/installation/)
-   [Docker](https://www.docker.com/products/docker-desktop/)

### Setup and Run Locally (with uv)

Python 3.12 is selected by `.python-version`. `uv.lock` is committed; use `uv sync --locked` for reproducible installs. The application is not installed as a Python package. Production images install only runtime dependencies with `uv sync --locked --no-dev`.

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
    Install the locked dependencies (including the development group):
    ```bash
    uv sync --locked
    ```

4.  **Run the application:**
    The application will be served by Uvicorn and accessible at `http://localhost:8000`.
    ```bash
    uv run --locked uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
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
-   **`live_jev`**: Live Jev API tests; no trader is constructed. These also carry the deprecated `live_llm` alias so existing `-m "not live_llm"` commands remain offline.

You can run tests as follows:

**1. Run all tests (including the live Jev tests):**
```bash
uv run --locked pytest
```

**2. Run only the fast unit and mocked E2E tests:**
This is the recommended command for CI/CD and most local testing.
```bash
uv run --locked pytest -m "not live_jev"
```

**3. Run only the live Jev integration tests:**
The expected-hike case checks Jev's classification separately and accepts either a neutral decision or an abstention caused by valid confidence below the configured threshold. Incorrect classification, missing confidence and provider failures still fail the test. Directional cases still require the expected direction.

Requires `TYPESAFE_API_KEY` and `PROD_EXECUTION=False` in the environment or `.env`. Tests make paid API calls. `.env.test` can supply the provider key; application settings are loaded at import time.
```bash
uv run --locked pytest -m live_jev
```

---

## API Usage Examples (cURL)

You can test the source-specific notification endpoints using `curl`.

### Example 1: Simulating a "Dovish" FED Announcement (`web-monitor`)

This payload contains text that should be interpreted by the **FED Decision Agent**.

```bash
curl -X 'POST' \
  'http://localhost:8000/notify/web-monitor' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <NOTIFY_AUTH_TOKEN>' \
  -d '{
  "uuid": "curl-test-dovish-001",
  "type": "web-monitor",
  "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240131a.htm",
  "content-id": "monetary20240131a",
  "content": "In a surprising move, the Federal Open Market Committee (FOMC) announced today they will not only hold interest rates steady but also signaled a potential rate cut sooner than anticipated. Chairman Powell mentioned concerns about slowing economic growth, suggesting a more accommodative monetary policy is necessary.",
  "ip": "127.0.0.1"
}'
```

### Example 2: Simulating a "Hawkish" Social Media Post (`truthsocial`)

This payload contains text that should be interpreted by the **Social Media Agent**.

```bash
curl -X 'POST' \
  'http://localhost:8000/notify/truth-social' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <NOTIFY_AUTH_TOKEN>' \
  -d '{
  "uuid": "curl-test-tariffs-001",
  "type": "truthsocial",
  "url": "https://truthsocial.com/@user/123",
  "username": "realDonaldTrump",
  "content-id": "123",
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
Check `jev_analysis_completed` in the logs for the Jev answers and local policy decision, followed by the resulting (simulated or real) trade action.
