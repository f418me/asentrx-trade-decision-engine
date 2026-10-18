# FOMC October 28, 2026

Research snapshot: October 18, 2026. Refresh before deploying for the meeting.
All payloads here are synthetic scenarios, not published Fed statements.
Their statement URL is an anticipated fixture URL, not a verified live release.

## Timing and expectations

The [official October calendar](https://www.federalreserve.gov/newsevents/2026-october.htm)
lists the October 27-28 meeting, decision at 14:00 US Eastern and press conference
at 14:30. On October 28 this is **19:00 and 19:30 Europe/Zurich**: Europe has
already ended daylight saving time, the US has not. A three-minute lead means
18:57 Swiss time. This change does not configure or deploy the monitor/scheduler.

The [September statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm)
raised the target range to 3.75%-4.00%.
The [September minutes](https://www.federalreserve.gov/monetarypolicy/fomcminutes20260916.htm)
retain a tightening bias with timing dependent on the data.
The [meeting calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
does not mark October as an economic-projections meeting: no scheduled SEP/dot plot.

The [Reuters brokerage survey, October 15 (AOL republication)](https://www.aol.com/articles/factbox-major-brokerages-expect-next-114611000.html)
reports these forecasts for the remaining meetings:

| Analysts | October | December | Year-end target range |
| --- | --- | --- | --- |
| Goldman Sachs, J.P. Morgan, Morgan Stanley, Citi | Hold | +25bp | 4.00%-4.25% |
| Barclays, Deutsche Bank, HSBC, Nomura, UBS | Hold | +25bp | 4.00%-4.25% |
| BofA Global Research | +25bp | +25bp | 4.25%-4.50% |

These are dated forecasts, not unanimous expectations or guaranteed outcomes.
The working engine baseline is **hold / 0bp / hawkish**. The narrative label is
our interpretation: a pause while leaving further tightening open, not a dovish
pivot. No market-implied probability is encoded as Jev confidence.

## Scenario matrix

| Payload | Policy result at sufficient confidence |
| --- | --- |
| expected-hold.json | Neutral |
| dovish-hold.json | Positive |
| hawkish-hold.json | Negative |
| surprise-25bp-hike.json | Negative |
| surprise-50bp-hike.json | Negative |
| surprise-cut.json | Positive |
| mixed-hold.json | Neutral |
| missing-rate.json | Abstention |
| missing-guidance.json | Abstention |
| preview.json | Abstention |
| minutes.json | Abstention |

These are policy expectations, not predictions of realized Bitcoin returns.
Rate surprise takes precedence over guidance. Neutral is a valid completed
analysis without a directional signal; abstention means there is insufficient
reliable evidence to decide. Neither should create a trade.

## Run safely

From the engine repository:

```bash
uv run --locked pytest tests/unit/ai/test_fomc_october.py -q
uv run --locked pytest -m "not live_jev"
uv run --locked pytest tests/integration/test_jev_october_live.py -m live_jev -v --junitxml=/tmp/fomc-october.xml
```

Offline tests validate payload contracts, policy, confidence gates and rate
priority using explicit judgments. They do not test semantic extraction.
Live tests make 11 paid Jev requests using TYPESAFE_API_KEY, with no trader
constructed. They check decision-relevant judgments separately from the actual
confidence-gated result and record outcome/provider confidence in JUnit output.
A correctly classified directional case may still abstain on low confidence;
a green semantic suite therefore does not guarantee trade readiness.
Provider errors and wrong judgments fail. Keep Jev pinned to 1.13.0.

For manual API testing, use the individual payload files with
`scripts/post_web_monitor_payload.sh` against a **local dry-run engine** with
`PROD_EXECUTION=False` and its matching `NOTIFY_AUTH_TOKEN`. Never send these
synthetic cases to a real-trading deployment. Repeated content IDs are deduplicated.

The frozen baseline.json is independent of app/expectations.json so these
regressions remain valid after future meetings. cases.json holds synthetic
judgments and expected policy outputs, not observed Jev responses.

## Current limitations

The analyzer sends the structured baseline but excludes notes. Jev sees
hold/0bp/hawkish, not the bank forecasts, target range or detailed December path.
Fine distinctions within a hawkish tone therefore need live verification.
Freshness classification is not an event-date authentication mechanism.
Confidence measures answer certainty, not probability of a profitable trade.
Risk settings, trading policy, monitor schedule and deployment are unchanged.
