# September 16, 2026 FOMC Manual Test Payloads

These payloads are designed for the current September 2026 FOMC baseline:

- Expected decision: `+25bp`
- Expected target range after decision: `3.75%-4.00%`
- Expected narrative: `hawkish`
- Market-implied confidence: high, roughly mid-80s to mid-90s percent probability for `+25bp`

Because a normal hawkish `+25bp` hike is now a high-confidence baseline, it should usually be neutral unless the statement is more hawkish than expected.

## Payloads

- `fomc-2026-09-16-expected-25bp-hawkish-neutral.json`
  Expected interpretation: broadly in line with baseline, likely neutral/no trade.

- `fomc-2026-09-16-surprise-hold-dovish-positive.json`
  Expected interpretation: materially less hawkish than a strongly priced baseline, likely BTC-positive.

- `fomc-2026-09-16-hawkish-50bp-negative.json`
  Expected interpretation: materially more hawkish than baseline, likely BTC-negative.

- `fomc-2026-09-16-dovish-hike-positive.json`
  Expected interpretation: rate hike matches baseline but statement is meaningfully dovish/one-and-done, likely BTC-positive or at least less bearish because forward guidance is less hawkish than expected.

- `fomc-2026-09-16-preview-irrelevant.json`
  Expected interpretation: preview only, no official decision, irrelevant/no trade.

## Local Usage

Start the engine locally, then run:

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
