# PCE: November 25, 2026

Prepared November 24 for the October 2026 Personal Income and Outlays report.
Release: 08:30 New York = 13:30 UTC = 14:30 Europe/Zurich (CET).
The engine accepts PCE only from 13:30 inclusive to 13:35 exclusive UTC, including
a second time check after Jev responds. The deadline is carried into the trader:
PCE quote requests have connect/read timeouts and the deadline is checked again
before order submission. Already submitted limit orders are not automatically
cancelled at expiry and may fill later. The orchestrator starts the web monitor
at 13:27 UTC and stops it at 13:35 UTC. All timestamps are timezone-aware.

## Baseline and Sources

| Price index | Monthly | Annual |
| --- | --- | --- |
| Core PCE | 0.3% | 3.2% |
| Headline PCE | 0.3% | 3.8% |

- [BEA release schedule](https://www.bea.gov/news/schedule): PCE and Q3 GDP second estimate are simultaneous.
- [U.S. Bank November 20 calendar](https://www.usbank.com/content/dam/usbank/en/documents/pdfs/corporate-and-commercial-banking/econ-weekly-pdf-11-20-26.pdf): corroborates the core baseline.
- [Continuum Economics November 17 preview](https://continuumeconomics.com/a/7b31577f/preview-due-november-25-us-october-personal-income-and-spending-5-month-high-for-yryr-core-pce-prices): core and headline forecasts. Headline values here are a working analyst forecast, not an independently established consensus.

Production reads `app/pce_expectations.json`; `baseline.json` here is the frozen
test baseline. These numbers are expectations, not published actuals. Recheck
before deployment; do not reuse this baseline for another month's report.

## Policy and Exposure

One Jev call classifies the release and compares four inflation measures.
Local Python maps cooler monthly core to positive and hotter monthly core to
negative, provided no annual/core/headline comparison points the other way.
In-line monthly core is neutral even if annual inflation surprises. Conflicts,
missing values, wrong month and insufficient provider confidence abstain.

PCE-specific defaults (also explicit in `fly.toml`):

| Tier | Minimum confidence | Long / short amount | Leverage |
| --- | --- | --- | --- |
| High | 0.95 | +2.0 / -2.0 BTC | 50 |
| Medium | 0.90 | +1.0 / -1.0 BTC | 30 |

These are user-selected high-risk settings, not conservative defaults. At an
assumed BTC price of USD 60,000, initial margin is approximately USD 2,400 for
the high tier and USD 2,000 for the medium tier, excluding fees and reserves.
The tiers are alternatives, not two simultaneous orders. No free-collateral
check or automatic stop-loss is implemented; higher confidence does not make
this exposure safe.

The PCE limit offset is 0.002 (0.2% from the trader's quote), independent of FED
settings. It is not a stop-loss or a guarantee against losses. The configured
instrument remains `TRADE_SYMBOL`. Provider confidence is answer certainty,
not a probability of profit. Review amounts and leverage before live execution.

## Tests

Offline, no provider/exchange requests:

```bash
uv run --locked pytest -m "not live_jev" -q
uv run --locked pytest tests/unit/ai/test_pce.py tests/e2e/test_e2e_pce_decision_flow.py -q
```

Opt-in paid Jev semantic tests, no trader constructed:

```bash
PROD_EXECUTION=False uv run --locked pytest tests/integration/test_jev_pce_live.py -m live_jev -v
```

`cases.json` contains synthetic hot, cool, in-line, conflict, old-month and GDP
texts, not actual BEA releases. Live tests bypass only the clock gate and record
provider confidence. Correct classification with confidence below the Jev gate
is reported as abstention, not proof of live trade readiness. Transport failures,
missing confidence and incorrect judgments fail the tests.

## Deployment Checklist

1. Deploy the engine first, then the PCE web monitor, then the orchestrator.
2. Check effective Fly settings/secrets: secrets can override `fly.toml`. Keep
   `NOTIFY_AUTH_TOKEN` consistent; verify `TYPESAFE_API_KEY` and Slack settings.
3. Confirm the monitor targets PCE, October 2026 and November 25 at 13:30 UTC.
4. Keep one engine worker/machine and one monitor for this attempt. Deduplication
   is not shared across engine replicas or restarts. Do not replay synthetic
   test payloads against production.
5. Inspect `notification_received`, `jev_analysis_completed` and `trade_outcome`
   by content ID (`bea-pce-2026-10`). Slack follows order attempts and analyzer
   abstentions. Abstention alerts explicitly say `NO TRADE`, include the reason
   and field confidence, and do not submit orders. Neutral/gated signals and
   duplicate or pre-analysis URL/time rejections remain silent.

The existing Fly engine configuration enables real orders. The GDP release is
not jointly analyzed and may cause an opposing market reaction. No automatic
exit/stop-loss strategy is added here. Fast retrieval, successful fills and
profits are not guaranteed. An upstream failure or a late release can mean no
trade; fail-closed behavior is intentional. No deployment is performed by tests.
