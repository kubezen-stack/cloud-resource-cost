# Experiment: cost anomaly detection

**Question.** Does the production detector (rolling-median baseline, Isolation Forest ranking and
guardrails) find cost spikes better than simpler methods, and at what price in missed spikes?

Reproduce: `python -m app.jobs.anomaly_benchmark --series 20` (about 3 minutes, no database, network or API key).
Code: `app/services/anomaly_benchmark.py`, tests in `tests/unit/test_anomaly_benchmark.py`.

## Method

Real billing data has no labels, so the benchmark generates 90-day daily cost series with a fixed seed,
injects spikes at random days and scores every detector on the days it flags. Only cost increases are
detected, as in production.

**Series (what "normal" looks like).**

| Name | Shape |
|---|---|
| flat | 50 with 4% noise |
| noisy | 200 with 20% noise |
| weekly | 60 on weekdays, 30 on weekends, small noise |
| growth | 20 growing 1% per day, small noise |
| tiny | about $0.05 a day (false-alarm test only) |

**Injected anomalies.** A single-day spike of x1.6, x2 or x3, and a 4-day plateau of x3, placed at a random
day after the first 21. For every series and injection there are 20 generated series (a clean one per
series type as well), 420 series in total.

**Detectors.** All use only the preceding days, except the forest.

| Detector | Rule |
|---|---|
| z-score | Previous 14 days: flag above 3 standard deviations from their mean |
| median + MAD | Previous 14 days: flag above 4 robust deviations from their median |
| Isolation Forest | 200 trees on the raw daily costs, 5% contamination, only days above the median |
| production (hybrid) | Rolling-median baseline, Isolation Forest on the deviations, then guardrails: at least +50%, at least $1 and at least 4 robust deviations above the baseline |

**Metrics.** Counted per day. A flagged injected day is a true positive, a flagged other day is a false
positive, an injected day not flagged is a miss. False alarms per series count every flagged day that was
not injected.

## Results

| Detector | Precision | Recall | F1 |
|---|---|---|---|
| z-score | 0.49 | 0.67 | 0.57 |
| median + MAD | 0.67 | 0.94 | 0.78 |
| Isolation Forest | 0.43 | 0.95 | 0.59 |
| **production (hybrid)** | **1.00** | 0.92 | **0.96** |

Recall by injected anomaly:

| Detector | spike x1.6 | spike x2 | spike x3 | 4-day plateau x3 |
|---|---|---|---|---|
| z-score | 0.74 | 0.94 | 0.97 | 0.51 |
| median + MAD | 0.75 | 0.90 | 1.00 | 0.97 |
| Isolation Forest | 0.74 | 0.96 | 1.00 | 0.99 |
| production (hybrid) | 0.70 | 0.90 | 0.96 | 0.97 |

False alarms per series:

| Detector | flat | noisy | weekly | growth | tiny |
|---|---|---|---|---|---|
| z-score | 0.56 | 0.66 | 0.00 | 2.48 | 1.10 |
| median + MAD | 0.46 | 0.52 | 0.05 | 1.38 | 0.85 |
| Isolation Forest | 1.73 | 1.65 | 0.73 | 2.30 | 3.40 |
| production (hybrid) | 0.00 | 0.02 | 0.00 | 0.00 | 0.00 |

## Reading the results

- **Precision is where the hybrid wins.** It raises almost no false alarms (0.02 per series at most),
  while the simpler methods raise one for every one to two series. For a tool that sends alerts, a false
  alarm costs trust; this is why the guardrails exist.
- **Recall is the same as the baselines, within noise.** The hybrid finds 92% of injected days against
  94-95% for median + MAD and the forest. The differences on single-day spikes (0.70-0.75) are inside what
  20 series per cell can resolve, so no method is better than another there.
- **The cost of the guardrails is small spikes.** A x1.6 spike on a noisy bill is not reported (+60% but
  under four robust deviations). That is the intended trade: very small deviations are not worth an alert.
- **The z-score fails on plateaus** (recall 0.51): after a day or two of high cost the window's own mean
  and spread rise, so the next days look normal. The median is not moved by a few high days.
- **Growth breaks the simple baselines** (1.4-2.5 false alarms per series): a rising bill is always above
  the average of the previous days. The forest alone flags a fixed share of days whether or not anything
  happened (hence 1.7 false alarms on flat series).

## Limits of this experiment

- **The guardrail thresholds were tuned on the same families of synthetic series**, so the hybrid's
  precision is optimistic. The comparison shows the design is sound, not that real bills behave this way.
  It must be repeated on real billing history from a connected account.
- Series are 90 days, one anomaly each, with Gaussian noise. Real bills have steps (a new service),
  month-end effects and heavier tails; none of those are generated.
- Only increases are scored. A drop in cost (a stopped service) is out of scope.
- Day-level scoring counts a 4-day plateau as four events, which gives long anomalies more weight.

## Next

Run the same benchmark on a real account's Cost Explorer export, and add a level-shift scenario (a
permanent step) to decide whether the detector should report it once or stay silent.
