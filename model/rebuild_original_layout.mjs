import fs from 'node:fs';

const current = fs.readFileSync('index.html', 'utf8');
const style = current.match(/<style>[\s\S]*?<\/style>/)?.[0];
if (!style) throw new Error('Could not recover the original report stylesheet.');

const body = `
<div class="wrap">
<h1>Is spend here affecting results there?</h1>
<p class="sub">Laura Geller &middot; daily, Jan 2025 &ndash; Jul 2026 &middot; total-business incrementality first, attribution routing second<br><span class="asof">Annual impact view uses the 365 days through 2026-07-27</span></p>

<div class="answer"><div class="big" id="hero">Loading&hellip;</div><p id="heroTxt"></p></div>

<div class="controls">
  <span class="lbl">Result</span>
  <div class="grp" id="mTabs"><button data-m="orders" class="on">New orders</button><button data-m="revenue">Revenue</button></div>
  <span class="lbl">Region</span>
  <div class="grp" id="rTabs"></div>
  <span class="asof" style="flex-basis:100%;margin-top:2px">The default is a 20% channel reduction over 365 days. Each geography and the pooled Total view are fitted separately.</span>
</div>

<div style="overflow-x:auto"><div id="matrix"></div></div>
<div class="cap" id="matcap" style="margin-top:6px"></div>
<div class="legend">
  <span><i class="sw" style="background:#1f7a3f"></i>Incremental result created and routed here</span>
  <span><i class="sw" style="background:#e8e6df"></i>Total incrementality or routing unresolved</span>
  <span style="color:#999">Click any cell</span>
</div>
<p class="note" style="margin:10px 0 0"><strong>A destination cell prints only after two independent questions clear their gates.</strong> First, the row source must show positive total-business incrementality under a 99% placebo/FDR rule and a positive conservative interval. Second, the destination must show positive corrected routing evidence. Printed cells divide the supported source total across those destinations and therefore add exactly to Total business.</p>
<div class="warn" id="warn"></div>
<div class="panel" id="panel"><h3 style="color:#888;font-weight:500">Select a cell</h3><p style="color:#888">Pick a source and destination pair to see its raw estimate, empirical correction, interval and placebo diagnostics.</p></div>

<h2>Budget decision guide</h2>
<p class="note"><strong>Orders, revenue and spend are joined at the source-row level.</strong> Only total-business rows passing the strict final gate enter economics. The comparison uses the spend saved by the modelled 20% reduction—not full annual spend. Destination routing never creates extra volume.</p>
<div id="spill"></div>

<h3 class="shifth">Direct credited effect versus total business effect</h3>
<p class="cap" id="shiftcap"></p>
<div id="shift"></div>

<h2>Experiment priorities</h2><p class="note">Specific planning targets for the strongest actionable rows. Expected effects are scaled to the proposed eight-week test; final power must be checked against experiment-specific daily variance before launch.</p><div id="hold"></div>
<h2>Decision rules</h2><p class="note">These rules keep observational evidence separate from budget authority.</p><div id="suggest"></div>

<details class="apx"><summary><h2>Diagnostics &mdash; falsification, uncertainty and market consistency</h2></summary><div class="method">
  <h3>How much survives falsification?</h3><div id="rely"></div>
  <h3>What did the false-history tests find?</h3><div id="sens"></div>
  <h3>Does the pattern repeat across markets?</h3><div id="stab"></div>
  <h3>Does the report reconcile?</h3><div id="cons"></div>
  <h3>Downloads</h3><p><a class="dl" href="model/generated/halo-created-orders.json" download>Created orders matrix</a><a class="dl" href="model/generated/halo-created-revenue.json" download>Created revenue matrix</a><a class="dl" href="model/generated/halo-incrementality-orders.json" download>Total orders model</a><a class="dl" href="model/generated/halo-incrementality-revenue.json" download>Total revenue model</a><a class="dl" href="model/generated/placebo-incrementality-orders.json" download>Orders held-out audit</a><a class="dl" href="model/generated/placebo-incrementality-revenue.json" download>Revenue held-out audit</a></p>
</div></details>

<details class="sec"><summary><h2>How this was worked out</h2><span class="tease">Daily distributed lags, hierarchical pooling, placebo debiasing and what the method cannot prove</span></summary>
<div class="method">
  <p><strong>Layer one: total-business incrementality.</strong> The calculator uses daily data from 2025-01-01 through 2026-07-27. All twelve paid and CRM levers are estimated together against total new-customer orders or total new-customer revenue. A row is accepted only if it survives a 99% time-shift placebo threshold, false-discovery control, and a positive conservative interval.</p>
  <p><strong>Layer two: attribution routing.</strong> The accepted source total is allocated only across destinations with positive corrected routing evidence. Routing weights sum to one, so destination cells cannot manufacture more orders or revenue than the source-level total.</p>
  <p><strong>The raw-confounding problem.</strong> Fake histories still reproduce much of the uncorrected association. That is why the raw model is never the answer. In held-out validation, the complete final gate—not merely the regression—must publish no fake rows before the model is released.</p>
  <p><strong>Interpretation.</strong> The page now answers: “Does this source have supported total-business incrementality, and where does corrected attribution evidence place it?” It remains observational until a randomized geo or audience holdout calibrates the source row.</p>
</div></details>

<details class="apx"><summary><h2>Appendix &mdash; build status</h2></summary><div class="method" id="appendix"></div></details>
<div class="foot">Daily hierarchical distributed-lag model. Source-to-total-business empirical-null correction, 99% source gate, positive 80% interval, and conditional destination routing. Scenario period: 365 days through 27 July 2026.</div>
</div>
<script src="app.js"></script>`;

const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Is spend here affecting results there?</title>
${style}</head><body>${body}</body></html>\n`;

fs.writeFileSync('index.html', html);
console.log('Rebuilt index.html with the original report stylesheet and corrected model shell.');
