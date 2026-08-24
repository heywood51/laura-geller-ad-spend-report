# Laura Geller spend incrementality report

This report answers two different questions in sequence:

1. **Does spend in this source appear to create incremental total-business orders or revenue?** A daily distributed-lag model fits each source against the sum of all credited destinations. Time-shift fake histories estimate the empirical null. A result must pass the 99% source gate and have a positive 80% interval.
2. **Where are those supported orders or revenue credited?** Positive destination routes divide the accepted source total into shares. Routing never creates or changes the total.

The production gate is evaluated on 25 held-out fake histories that were not used to set it. In the current orders and revenue builds, the median and worst held-out history both publish zero false source rows. This is strong falsification performance, but the report remains observational until channel holdouts or geo experiments calibrate it.

## Rebuild

From `model/`, run the total-business models first, then the created matrices:

```text
python build_incrementality.py --measure orders --output generated/halo-incrementality-orders.json --validation-output generated/placebo-incrementality-orders.json
python build_incrementality.py --measure revenue --output generated/halo-incrementality-revenue.json --validation-output generated/placebo-incrementality-revenue.json
python build_created_matrix.py --incrementality generated/halo-incrementality-orders.json --routing generated/halo-daily-orders.json --output generated/halo-created-orders.json
python build_created_matrix.py --incrementality generated/halo-incrementality-revenue.json --routing generated/halo-daily-revenue.json --output generated/halo-created-revenue.json
```

The private daily panel is `model/generated/daily_panel.csv` and is intentionally ignored by Git.
