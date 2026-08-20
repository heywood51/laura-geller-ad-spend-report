'use strict';

let M='orders', R='Total', SELECTED=null;
let MODEL={}, SUMMARY={}, VALID={};
const GREEN='#1f7a3f', RED='#b3261e', GREY='#c9c7bd', GREYS='#8a877e';
const fmtN=new Intl.NumberFormat('en-US',{maximumFractionDigits:0});
const fmtM=v=>(v<0?'-':'')+'$'+(Math.abs(v)>=1e6?(Math.abs(v)/1e6).toFixed(1)+'m':fmtN.format(Math.abs(v)));
const num=(v,m=M)=>m==='revenue'?fmtM(v):fmtN.format(v);
const signed=(v,m=M)=>(v>0?'+':'')+num(v,m);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

Promise.all([
  fetch('model/generated/halo-daily-orders.json').then(r=>r.json()),
  fetch('model/generated/halo-daily-revenue.json').then(r=>r.json()),
  fetch('model/generated/report-summary.json').then(r=>r.json()),
  fetch('model/generated/placebo-validation.json').then(r=>r.json())
]).then(([orders,revenue,summary,valid])=>{
  MODEL={orders,revenue}; SUMMARY=summary; VALID=valid;
  buildTabs(); bind(); render();
}).catch(err=>{
  document.getElementById('hero').textContent='The model files could not be loaded';
  document.getElementById('heroTxt').textContent=err.message;
});

function data(){return MODEL[M].views[R]||MODEL[M].views.Total}
function cell(s,d){return data().cells[s+'|'+d]||null}
function buildTabs(){
  const geos=['Total',...MODEL.orders.metadata.geographies];
  document.getElementById('rTabs').innerHTML=geos.map(g=>`<button data-r="${esc(g)}" class="${g==='Total'?'on':''}">${g==='United Kingdom'?'UK':g==='United States'?'US':esc(g)}</button>`).join('');
}
function bind(){
  document.getElementById('mTabs').onclick=e=>{if(!e.target.dataset.m)return;M=e.target.dataset.m;SELECTED=null;setOn('mTabs','m',M);render()};
  document.getElementById('rTabs').onclick=e=>{if(!e.target.dataset.r)return;R=e.target.dataset.r;SELECTED=null;setOn('rTabs','r',R);render()};
}
function setOn(id,k,v){document.querySelectorAll('#'+id+' button').forEach(b=>b.classList.toggle('on',b.dataset[k]===v))}
function rowTotal(s){return MODEL[M].destinations.reduce((a,d)=>a+(cell(s,d)?.effect||0),0)}
function direct(s){return cell(s,s)?.effect||0}
function rawTotal(s){return MODEL[M].destinations.reduce((a,d)=>a+(cell(s,d)?.raw_effect||0),0)}
function passed(s){return MODEL[M].destinations.filter(d=>cell(s,d)?.passes_placebo).length}

function render(){renderHero();renderMatrix();renderPanel();renderSpill();renderShift();renderText()}
function renderHero(){
  const total=MODEL[M].channels.reduce((a,s)=>a+rowTotal(s),0);
  const survive=MODEL[M].channels.reduce((a,s)=>a+passed(s),0);
  const all=MODEL[M].channels.length*MODEL[M].destinations.length;
  document.getElementById('hero').innerHTML=`${signed(total)} <em>annual ${M} across all source rows</em>`;
  document.getElementById('heroTxt').innerHTML=`This is the net of the ${survive} of ${all} source-to-destination cells that survive pair-specific placebo correction and false-discovery control in <strong>${esc(R)}</strong>. It is an adjusted observational scenario estimate, not a claim that every unit is incremental.`;
  document.getElementById('warn').innerHTML=`<strong>Conservative by design.</strong> The raw model is not displayed as the answer. For every pair, the calculator first removes the median fake-history effect and a 95% false-signal allowance. In validation, fake histories retained about <strong>74%</strong> of the observed headline signal before this correction—the issue previously described as 78%.`;
}

function renderMatrix(){
  const src=MODEL[M].channels,dst=MODEL[M].destinations;
  const max=Math.max(...src.flatMap(s=>dst.map(d=>Math.abs(cell(s,d)?.effect||0))),1);
  let h='<table class="m"><thead><tr><th></th>'+dst.map(d=>`<th class="col">${esc(d)}</th>`).join('')+'</tr></thead><tbody>';
  for(const s of src){h+=`<tr><th>${esc(s)}</th>`;for(const d of dst){const c=cell(s,d);const v=c?.effect||0;const ok=!!c?.passes_placebo;const a=ok?.15+.75*Math.sqrt(Math.abs(v)/max):0;const bg=!ok?'#e8e6df':v>=0?`rgba(31,122,63,${a})`:`rgba(179,38,30,${a})`;const fg=ok&&a>.52?'#fff':'#333';const sel=SELECTED&&SELECTED[0]===s&&SELECTED[1]===d?' sel':'';h+=`<td><div class="cell${sel}" data-s="${esc(s)}" data-d="${esc(d)}" style="background:${bg};color:${fg}" title="${esc(s)} → ${esc(d)}: ${signed(v)}">${ok&&Math.abs(v)>=1?signed(v):'—'}</div></td>`}h+='</tr>'}h+='</tbody></table>';
  const el=document.getElementById('matrix');el.innerHTML=h;el.querySelectorAll('.cell').forEach(x=>x.onclick=()=>{SELECTED=[x.dataset.s,x.dataset.d];renderMatrix();renderPanel()});
  document.getElementById('matcap').textContent=`${M==='revenue'?'Revenue':'New-order'} effect of a 20% reduction in the row channel over 365 days · ${R}. Positive means the reduction is associated with more of the column result; negative means less.`;
}

function renderPanel(){
  if(!SELECTED)return;
  const [s,d]=SELECTED,c=cell(s,d);if(!c)return;
  const verdict=c.passes_placebo?(c.effect>=0?'Survives correction · positive':'Survives correction · negative'):'Does not survive correction';
  const cls=c.passes_placebo?(c.effect>=0?'v-hold':'v-neg'):'v-no';
  document.getElementById('panel').innerHTML=`<h3>${esc(s)} &rarr; ${esc(d)}</h3><span class="verdict ${cls}">${verdict}</span><p class="why">The displayed estimate is the raw model effect after subtracting the pair&rsquo;s median shifted-history bias and its 95% false-signal threshold. Unpublished cells are kept at zero in totals.</p><div class="stats">
    <div class="stat"><div class="k">Adjusted effect</div><div class="v">${signed(c.effect)}</div><div class="ex">annual 20% scenario</div></div>
    <div class="stat"><div class="k">Raw model</div><div class="v">${signed(c.raw_effect)}</div><div class="ex">before empirical-null correction</div></div>
    <div class="stat"><div class="k">80% interval</div><div class="v">${signed(c.lower80)} to ${signed(c.upper80)}</div></div>
    <div class="stat"><div class="k">Placebo bias</div><div class="v">${signed(c.placebo_bias)}</div><div class="ex">median of ${c.placebo_runs} shifts</div></div>
    <div class="stat"><div class="k">False-signal bar</div><div class="v">${num(c.placebo_threshold)}</div><div class="ex">95th percentile</div></div>
    <div class="stat"><div class="k">FDR q-value</div><div class="v">${(100*c.placebo_q_value).toFixed(1)}%</div><div class="ex">empirical p ${(100*c.placebo_empirical_p_value).toFixed(1)}%</div></div></div>`;
}

function renderSpill(){
  const rows=MODEL[M].channels.map(s=>({s,sp:SUMMARY.views[R]?.sources?.[s]?.spend,di:direct(s),cr:rowTotal(s)-direct(s),to:rowTotal(s),ra:rawTotal(s),pa:passed(s)})).sort((a,b)=>Math.abs(b.to)-Math.abs(a.to));
  let h='<div class="hscroll"><table class="s"><tr><th class="stick">Channel changed</th><th>Annual spend</th><th>Direct</th><th>Cross-channel</th><th>Total effect</th><th>Raw model</th><th>Cells kept</th><th>Spend / |effect|</th></tr>';
  for(const x of rows){const eff=x.sp!=null&&Math.abs(x.to)>0?x.sp/Math.abs(x.to):null;h+=`<tr><td class="l stick">${esc(x.s)}</td><td>${x.sp==null?'—':fmtM(x.sp)}</td><td>${signed(x.di)}</td><td>${signed(x.cr)}</td><td><strong>${signed(x.to)}</strong></td><td>${signed(x.ra)}</td><td>${x.pa} / ${MODEL[M].destinations.length}</td><td>${eff==null?'—':M==='orders'?'$'+fmtN.format(eff):eff.toFixed(2)+'×'}</td></tr>`}h+='</table></div>';document.getElementById('spill').innerHTML=h;
}

// Original report SVG bar renderer, retaining its dimensions, axis, spacing and two-bar treatment.
function renderShift(){
  const el=document.getElementById('shift'); if(!el) return;
  const cap=document.getElementById('shiftcap');
  if(cap) cap.innerHTML=(M==='revenue'?'Revenue':'New-order')+' effect for <strong>'+esc(R)+'</strong>. Follows both buttons above.';
  const rows=MODEL[M].channels.map(k=>({k,a:direct(k),b:rowTotal(k)})).filter(x=>Number.isFinite(x.a)&&Number.isFinite(x.b)).sort((x,y)=>Math.abs(y.b)-Math.abs(x.b));
  const W=880,L=118,RPAD=88,rowH=30,top=6,HH=top+rows.length*rowH+24;
  const lo=Math.min(0,...rows.flatMap(x=>[x.a,x.b])),hi=Math.max(0,...rows.flatMap(x=>[x.a,x.b]));
  const range=Math.max(hi-lo,1), plotW=W-L-RPAD, x=v=>L+(v-lo)/range*plotW, zero=x(0);
  let svg=`<div class="key"><span><i style="background:${GREY}"></i>Direct destination only</span><span><i style="background:${GREEN}"></i>Total after cross-channel effects</span></div><svg viewBox="0 0 ${W} ${HH}" role="img" aria-label="Direct effect compared with total effect by channel"><line class="axis" x1="${zero}" x2="${zero}" y1="0" y2="${HH-19}"/>`;
  rows.forEach((r,i)=>{const y=top+i*rowH;const bar=(v,yy,color)=>{const xx=x(v),left=Math.min(zero,xx),w=Math.max(1,Math.abs(xx-zero));return `<rect x="${left}" y="${yy}" width="${w}" height="8" rx="1" fill="${color}"/>`};const color=r.b<0?RED:GREEN;svg+=`<text class="lab" x="${L-7}" y="${y+14}" text-anchor="end">${esc(r.k)}</text>${bar(r.a,y+3,GREY)}${bar(r.b,y+13,color)}<text class="val" x="${r.b>=0?x(r.b)+5:x(r.b)-5}" y="${y+21}" text-anchor="${r.b>=0?'start':'end'}" fill="${color}">${signed(r.b)}</text>`});
  svg+='</svg>';el.innerHTML=svg;
}

function renderText(){
  const all=MODEL[M].channels.flatMap(s=>MODEL[M].destinations.map(d=>({s,d,c:cell(s,d)}))).filter(x=>x.c);
  const kept=all.filter(x=>x.c.passes_placebo), raw=all.reduce((a,x)=>a+Math.abs(x.c.raw_effect||0),0),adj=all.reduce((a,x)=>a+Math.abs(x.c.effect||0),0);
  const top=[...MODEL[M].channels].sort((a,b)=>Math.abs(rowTotal(b))-Math.abs(rowTotal(a))).slice(0,3);
  document.getElementById('soWhat').innerHTML=`<div class="callout"><h4>The display is familiar; the answer underneath it is different.</h4><p>The matrix, click-through detail, source table and paired horizontal bars are the original report components. Their inputs now come from daily geography models and cell-specific placebo correction. In ${esc(R)}, the largest adjusted source rows are ${top.map(s=>`<strong>${esc(s)}</strong> (${signed(rowTotal(s))})`).join(', ')}.</p></div>`;
  document.getElementById('rely').innerHTML=`<div class="hscroll"><table class="s"><tr><th>Diagnostic</th><th>${esc(R)}</th></tr><tr><td class="l">Cells tested</td><td>${all.length}</td></tr><tr><td class="l">Cells surviving all gates</td><td>${kept.length}</td></tr><tr><td class="l">Absolute raw signal</td><td>${num(raw)}</td></tr><tr><td class="l">Absolute adjusted signal</td><td>${num(adj)}</td></tr><tr><td class="l">Share removed by correction</td><td>${raw?((1-adj/raw)*100).toFixed(1):'0.0'}%</td></tr><tr><td class="l">Placebo refits per cell</td><td>${MODEL[M].metadata.placebo_runs}</td></tr></table></div>`;
  const val=VALID[M]||VALID.measures?.[M]||{};
  document.getElementById('sens').innerHTML=`<div class="method"><p><strong>The fake histories are part of the estimator, not a footnote.</strong> Each source series was shifted to dates where it cannot preserve the real source-to-result timing, then the complete model was rerun. The correction is cell-specific, so a noisy pair pays a larger penalty than a clean one. The published answer uses a fixed 95% empirical threshold and FDR q-values; there is no user-controlled slider that can loosen the evidence after seeing the result.</p><div class="eq">adjusted = sign(raw − placebo median) × max(|raw − placebo median| − placebo 95th percentile, 0)<br>publish only if the empirical false-discovery gate also passes</div></div>`;
  const geos=MODEL[M].metadata.geographies.map(g=>({g,n:Object.values(MODEL[M].views[g].cells).filter(c=>c.passes_placebo).length,t:MODEL[M].channels.reduce((a,s)=>a+MODEL[M].destinations.reduce((b,d)=>b+(MODEL[M].views[g].cells[s+'|'+d]?.effect||0),0),0)}));
  document.getElementById('stab').innerHTML='<div class="hscroll"><table class="s"><tr><th>Market fitted separately</th><th>Cells kept</th><th>Net annual effect</th></tr>'+geos.map(x=>`<tr><td class="l">${esc(x.g)}</td><td>${x.n}</td><td>${signed(x.t)}</td></tr>`).join('')+'</table></div>';
  document.getElementById('cons').innerHTML=`<div class="method"><p><strong>All views are generated from the same corrected cell matrix.</strong> The headline is the sum of row totals; each row total is the sum of the cells shown in that matrix; the source table and SVG bars use those identical row totals. Total is constructed from the separately fitted geography outputs, so changing region refreshes every section together.</p></div>`;
  document.getElementById('suggest').innerHTML=`<ol class="sug"><li>Use the largest surviving rows to choose holdout priorities, not as permission to move the full budget immediately.</li><li>For channels with a large raw estimate but little adjusted effect, improve variation or instrumentation before making a budget claim.</li><li>Read direct and cross-channel bars together: a strong cross-channel result is especially likely to contain attribution displacement.</li></ol>`;
  document.getElementById('hold').innerHTML=`<div class="callout"><h4>Validate the largest actionable row first</h4><p>For ${esc(R)} ${M}, that is <strong>${esc(top[0])}</strong> at ${signed(rowTotal(top[0]))} in the standardized annual scenario. Pre-register one primary total-business outcome, randomize by geography or audience where feasible, and size the test from daily residual variance before launch.</p></div>`;
  document.getElementById('appendix').innerHTML=`<p><strong>Status:</strong> ${esc(MODEL[M].status)}.</p><p><strong>Window:</strong> ${MODEL[M].metadata.date_min} through ${MODEL[M].metadata.date_max}; ${fmtN.format(MODEL[M].metadata.row_count)} geography-days.</p><p><strong>Measures:</strong> orders and net revenue are fitted separately with the same channels, destinations, scenario and placebo rules.</p><p><strong>Important limitation:</strong> no completed randomized experiments were available for calibration, so the calculator is deliberately labelled observational.</p>`;
}
