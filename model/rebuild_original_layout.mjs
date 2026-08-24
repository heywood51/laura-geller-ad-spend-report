import fs from 'node:fs';

const current = fs.readFileSync('index.html', 'utf8');
const style = current.match(/<style>[\s\S]*?<\/style>/)?.[0];
if (!style) throw new Error('Could not recover the original report stylesheet.');

const body = `
<div class="wrap">
<h1>Is spend here affecting results there?</h1>
<p class="sub">Laura Geller &middot; daily, Jan 2025 &ndash; Jul 2026 &middot; every channel estimated at once, with empirical placebo correction<br><span class="asof">Annual impact view uses the 365 days through 2026-07-27</span></p>

<div class="answer"><div class="big" id="hero">Loading&hellip;</div><p id="heroTxt"></p></div>

<div class="controls">
  <span class="lbl">Result</span>
  <div class="grp" id="mTabs"><button data-m="orders" class="on">New orders</button><button data-m="revenue">Revenue</button></div>
  <span class="lbl">Region</span>
  <div class="grp" id="rTabs"></div>
  <span class="asof" style="flex-basis:100%;margin-top:2px">The default is a 20% channel reduction over 365 days. Each geography is fitted separately; Total is the sum of the six geography models.</span>
</div>

<div style="overflow-x:auto"><div id="matrix"></div></div>
<div class="cap" id="matcap" style="margin-top:6px"></div>
<div class="legend">
  <span><i class="sw" style="background:#1f7a3f"></i>Result protected by current spend</span>
  <span><i class="sw" style="background:#f1d9d6"></i>Destination credit may rise after a cut</span>
  <span><i class="sw" style="background:#e8e6df"></i>Did not survive the placebo gate</span>
  <span style="color:#999">Click any cell</span>
</div>
<p class="note" style="margin:10px 0 0"><strong>Destination cells describe attribution paths; the final Total business cell describes the company-wide result.</strong> Values are current results minus the modelled result after a 20% cut. Positive means the current spend protects that result. A negative destination can be credit moving to another path. A negative Total business association is shown as <strong>TEST</strong>, never as orders created or a cut recommendation.</p>
<div class="warn" id="warn"></div>
<div class="panel" id="panel"><h3 style="color:#888;font-weight:500">Select a cell</h3><p style="color:#888">Pick a source and destination pair to see its raw estimate, empirical correction, interval and placebo diagnostics.</p></div>

<h2>Budget decision guide</h2>
<p class="note"><strong>Orders, revenue and spend are joined at the source-row level.</strong> The economic comparison uses the spend saved by the modelled 20% reduction—not full annual spend. Intervals are diagnostic 80% row intervals; decisions remain observational until a holdout confirms them.</p>
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
  <h3>Downloads</h3><p><a class="dl" href="model/generated/halo-daily-orders.json" download>Corrected orders JSON</a><a class="dl" href="model/generated/halo-daily-revenue.json" download>Corrected revenue JSON</a><a class="dl" href="model/generated/placebo-validation.json" download>Orders placebo audit</a><a class="dl" href="model/generated/report-summary.json" download>Annual source summary</a></p>
</div></details>

<details class="sec"><summary><h2>How this was worked out</h2><span class="tease">Daily distributed lags, hierarchical pooling, placebo debiasing and what the method cannot prove</span></summary>
<div class="method">
  <p><strong>The model.</strong> The calculator uses daily data from 2025-01-01 through 2026-07-27. All twelve paid and CRM levers are estimated together against every attributed destination, using a hierarchical Bayesian distributed-lag model. Geography-specific estimates borrow strength without pretending spend in one market caused orders in another.</p>
  <p><strong>The scenario and sign.</strong> Every displayed value is the modelled current result minus the result after a 20% channel reduction held for 365 days. Positive is therefore the amount at risk after the cut. Destination-level negatives can be attribution routing. A negative cross-destination row sum is an observational cannibalization candidate, but the calculator classifies it as TEST / unresolved until a randomized holdout confirms it.</p>
  <p><strong>The 78% problem.</strong> The earlier model&rsquo;s apparent signal was mostly reproducible in fake histories. This version circularly shifts each source in time, refits the model 50 times per measure, subtracts the pair-specific median placebo bias and then subtracts the 95th-percentile false-signal threshold. Only cells that also survive matrix-wide false-discovery control are published.</p>
  <p><strong>Interpretation.</strong> A source-to-destination cell can reflect incremental demand, attribution displacement, or both. The method controls observed co-movement and tests temporal placebos, but it remains observational. A randomized geo or audience holdout is still required to establish causality.</p>
</div></details>

<details class="apx"><summary><h2>Appendix &mdash; build status</h2></summary><div class="method" id="appendix"></div></details>
<div class="foot">Daily hierarchical distributed-lag model. Cell-specific time-shift placebo debiasing, 95% empirical false-signal threshold, and false-discovery control. Scenario period: 365 days through 27 July 2026.</div>
</div>
<script src="app.js"></script>`;

const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Is spend here affecting results there?</title>
${style}</head><body>${body}</body></html>\n`;

fs.writeFileSync('index.html', html);
console.log('Rebuilt index.html with the original report stylesheet and corrected model shell.');
