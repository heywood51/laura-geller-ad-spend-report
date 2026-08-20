# Halo model

This directory replaces the original pairwise regression/credibility arithmetic with a
counterfactual halo matrix. A cell answers one declared question:

> How many orders credited to destination `j` are at risk when source channel `i` is
> reduced by the configured percentage?

The engine uses channel-specific geometric carryover, Hill saturation, geography-level
partial pooling, annual seasonality, business controls, and Gaussian Bayesian shrinkage.
Randomized experiment results enter the posterior as noisy observations of the same
counterfactual used by the website.

## Current-data limitation

`index.html` contains 106 weekly observations for the US and UK and spend for ten paid
channels. It does not contain DMA/daily rows, randomized assignments, delivered email,
or delivered SMS. A model built from that payload is therefore emitted with status
`observational_candidate`, two missing levers, and an explicit non-causal warning. It
must not replace the production headline until experiment or suitable geo variation is
provided.

## Run the embedded-data preview

```powershell
node model/extract_embedded_panel.mjs index.html model/generated/weekly_panel.csv
python model/halo_model.py `
  --input model/generated/weekly_panel.csv `
  --config model/config.weekly.json `
  --output model/generated/halo-preview.json
```

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
