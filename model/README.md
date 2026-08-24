# Halo model

This directory replaces the original pairwise regression/credibility arithmetic with a
counterfactual halo matrix. A cell answers one declared question:

> How many orders credited to destination `j` are at risk when source channel `i` is
> reduced by the configured percentage?

The engine uses channel-specific geometric carryover, Hill saturation, geography-level
partial pooling, annual seasonality, business controls, and Gaussian Bayesian shrinkage.
Randomized experiment results enter the posterior as noisy observations of the same
counterfactual used by the website.

## Current evidence status

The warehouse build produces 573 daily observations for six countries, 12 source
channels (including delivered email and SMS), and 14 credited destinations for both
orders and revenue. This is a materially better modeling panel, but it is not randomized.

The required circular-shift placebo test failed: impossible, time-shifted media histories
produced a median 74% as much absolute cell-level halo as the observed histories over 50
independent runs. The warehouse-wide table search also found no lift, holdout, geo-test,
or incrementality results. The best-available calculator therefore uses a cell-specific
empirical-null correction rather than treating predictive fit as causality.

For every cell, the production pass subtracts the median placebo bias, requires the
debiased signal to exceed that cell's 95th-percentile false-signal threshold, and applies
Benjamini-Hochberg false-discovery control across all 168 comparisons. It then refits
each source using exposure from 1, 2, 3, 7, and 14 days in the future on an identical
trimmed sample. A result is rejected when any future-exposure effect is at least as
strong as the correctly timed effect, because that pattern is compatible with platform
pacing or demand causing spend. Cells that fail either gate become zero. Passing values are labeled `placebo_adjusted_observational`, never
experiment-calibrated.

The balanced attribution artifact is intentionally a sensitivity scenario rather
than a causal output. Its point halo multiplies interval reliability by timing
separation (`1 - max future/correct effect ratio`) for both the source total and
destination routing. It also publishes a non-negative plausible range for every
cell. Diagonals remain accounting residuals, and the point allocation plus the
explicit non-addressable remainder reconciles exactly to original attribution.
The site exposes three zero-sum evidence standards. Validated conservative
requires every hard gate and applies interval and timing discounts. Best
observational recovers empirical-null-adjusted signals before the hard lead gate
and applies interval precision plus a soft `1 / (1 + lead ratio)` timing penalty.
Raw association stress uses positive uncorrected source and routing associations,
capped by each destination's attribution benchmark. The raw view is a confounding
stress test, not an estimate; none of the three is a causal result.

## Run the embedded-data preview

```powershell
node model/extract_embedded_panel.mjs index.html model/generated/weekly_panel.csv
python model/halo_model.py `
  --input model/generated/weekly_panel.csv `
  --config model/config.weekly.json `
  --output model/generated/halo-preview.json
```

## Build the private daily panel

The query in `build_daily_panel.sql` targets the `asbeauty-bi-dev` warehouse. Keep its
CSV and fitted JSON outputs local because this repository is public.

```powershell
Get-Content -Raw model/build_daily_panel.sql |
  bq query --use_legacy_sql=false --format=csv --max_rows=100000 --quiet |
  Set-Content model/generated/daily_panel.csv

python model/halo_model.py --input model/generated/daily_panel.csv `
  --config model/config.daily.orders.json `
  --output model/generated/halo-daily-orders.json

python model/halo_model.py --input model/generated/daily_panel.csv `
  --config model/config.daily.revenue.json `
  --output model/generated/halo-daily-revenue.json

python model/validate_placebos.py --input model/generated/daily_panel.csv `
  --config model/config.daily.orders.json `
  --output model/generated/placebo-validation.json `
  --adjusted-output model/generated/halo-daily-orders.json `
  --runs 50 --alpha 0.05

python model/validate_placebos.py --input model/generated/daily_panel.csv `
  --config model/config.daily.revenue.json `
  --output model/generated/placebo-validation-revenue.json `
  --adjusted-output model/generated/halo-daily-revenue.json `
  --runs 50 --alpha 0.05 --seed 20260821

# To add the lead gate to an already empirical-null-adjusted artifact without
# repeating the time-shift placebo fits:
python model/apply_lead_falsification.py --input model/generated/daily_panel.csv `
  --config model/config.daily.orders.json `
  --adjusted-input model/generated/halo-daily-orders.json `
  --output model/generated/halo-daily-orders.json

python model/build_report_summary.py `
  --input model/generated/daily_panel.csv `
  --orders-config model/config.daily.orders.json `
  --revenue-config model/config.daily.revenue.json `
  --output model/generated/report-summary.json
```

`index.html` consumes only these corrected outputs. Its matrix, source and destination
tables, budget guide, experiment priorities, reliability summary, and narrative callouts
are calculated from the same JSON at page load; no legacy regression payload remains.

## Production input

Use one row per geography and day. Required fields are configured rather than hardcoded:

- date and geography;
- exposure for every source channel (GRPs, impressions, clicks, or delivered messages);
- spend separately when the exposure metric is not spend;
- new-customer orders and revenue for every credited destination;
- pre-treatment confounders such as promotion depth, inventory, price, and organic query
  volume.

Do not add clicks, sessions, or other post-exposure mediators as controls.

## Experiment calibration

Append observations to `experiments` in the configuration:

```json
{
  "channel": "Television",
  "destination": "CRM Email",
  "geo": "DMA group A",
  "start": "2026-09-01",
  "end": "2026-10-31",
  "relative_change": -0.40,
  "effect": -4200,
  "standard_error": 900
}
```

`effect` is treatment minus the unchanged counterfactual. A reduction that lowers orders
therefore has a negative effect. The reported matrix reverses the sign for reduction
scenarios and presents the result as orders at risk.

Each source-channel experiment can provide all destination outcomes, so one experiment
calibrates an entire row rather than one cell.

The website's publication rule is deliberate: each cell stays masked until randomized
evidence for that source/destination pair is supplied. A source experiment should record
all destination outcomes, which unlocks its row. Once every pair is constrained, the
output status becomes `experiment_calibrated`.
