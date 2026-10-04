# September 16, 2026 FOMC Test Payloads

These synthetic payloads use a frozen September 2026 test baseline. They are not current market expectations or evidence of actual market outcomes:

- Expected decision: `+25bp`
- Expected target range after decision: `3.75%-4.00%`
- Expected narrative: `hawkish`

A hawkish `+25bp` hike with guidance matching this baseline is classified as in line. The policy returns neutral when required field confidence is sufficient, or abstains when it is below the configured threshold. Both mean no trade.

## Payloads

- `fomc-2026-09-16-expected-25bp-hawkish-neutral.json`
  Expected classification: fresh release, +25bp, hawkish, guidance in line. Acceptable policy result: neutral or abstention caused by valid confidence below threshold; no trade.

- `fomc-2026-09-16-surprise-hold-dovish-positive.json`
  Expected interpretation: materially less hawkish than a strongly priced baseline, likely BTC-positive.

- `fomc-2026-09-16-hawkish-50bp-negative.json`
  Expected interpretation: materially more hawkish than baseline, likely BTC-negative.

- `fomc-2026-09-16-dovish-hike-positive.json`
  Expected interpretation: rate hike matches baseline but statement is meaningfully dovish/one-and-done, likely BTC-positive or at least less bearish because forward guidance is less hawkish than expected.

- `fomc-2026-09-16-preview-irrelevant.json`
  Expected interpretation: preview only, no official decision, abstention/no trade.

## Live Jev Regression Tests

From the engine directory, with `TYPESAFE_API_KEY` configured:

```bash
uv run --locked pytest tests/integration/test_jev_live.py -m live_jev -v
```

These tests use the configured model (default `typesafe:jev-1.13.0`) and construct no trader. The baseline is frozen inside the test, independently of production baseline updates. The expected-hike test checks Jev's classification separately; wrong classifications, missing confidence and provider errors still fail. Directional cases must produce their expected direction.

## Local Usage

For manual payload tests, start the engine with `PROD_EXECUTION=False`, then run:

```bash
NOTIFY_AUTH_TOKEN=<same token as engine NOTIFY_AUTH_TOKEN> \
  scripts/post_web_monitor_payload.sh \
  tests/testdata/fomc-sept-2026/fomc-2026-09-16-surprise-hold-dovish-positive.json \
  http://localhost:8000
```




For Fly:

```bash
NOTIFY_AUTH_TOKEN=<same token as Fly engine NOTIFY_AUTH_TOKEN> \
  scripts/post_web_monitor_payload.sh \
  tests/testdata/fomc-sept-2026/fomc-2026-09-16-surprise-hold-dovish-positive.json \
  https://asentrx-trade-decision-engine.fly.dev
```
