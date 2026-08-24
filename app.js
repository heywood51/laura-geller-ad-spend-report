'use strict';

let M='orders', R='Total', SELECTED=null;
let MODEL={}, SUMMARY={}, VALID={};
const GREEN='#1f7a3f', RED='#b3261e', GREY='#c9c7bd', GREYS='#8a877e';
const fmtN=new Intl.NumberFormat('en-US',{maximumFractionDigits:0});
const fmtM=v=>(v<0?'-':'')+'$'+(Math.abs(v)>=1e6?(Math.abs(v)/1e6).toFixed(1)+'m':fmtN.format(Math.abs(v)));
const num=(v,m=M)=>m==='revenue'?fmtM(v):fmtN.format(v);
const signed=(v,m=M)=>(v>0?'+':'')+num(v,m);
const short=(v,m)=>{const a=Math.abs(v),p=v<0?'-':v>0?'+':'';const n=a>=1e6?(a/1e6).toFixed(1)+'m':a>=1e3?(a/1e3).toFixed(0)+'k':fmtN.format(a);return p+(m==='revenue'?'$':'')+n};
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
function cellFor(m,g,s,d){return MODEL[m].views[g].cells[s+'|'+d]}
function rowTotalFor(m,g,s){return MODEL[m].destinations.reduce((a,d)=>a+(cellFor(m,g,s,d)?.effect||0),0)}
function rowIntervalFor(m,g,s){
  const total=rowTotalFor(m,g,s),cells=MODEL[m].destinations.map(d=>cellFor(m,g,s,d)).filter(c=>c?.passes_placebo);
  const conservativeSE=cells.reduce((a,c)=>a+(c.standard_error||0),0),margin=1.2815515655*conservativeSE;
  return {total,low:total-margin,high:total+margin,conservativeSE};
}
function sourceStatus(s,g=R){
  const o=rowIntervalFor('orders',g,s),r=rowIntervalFor('revenue',g,s),active=Math.abs(o.total)>0||Math.abs(r.total)>0;
  if(o.total<0||r.total<0)return {key:'test',label:'TEST counterintuitive',action:'Do not cut; investigate in a holdout'};
  if(!active)return {key:'none',label:'No surviving evidence',action:'No budget claim; improve variation'};
  if(o.total>0&&r.total>0&&o.low>0&&r.low>0)return {key:'protect',label:'Protect / test',action:'Protect while running a holdout'};
  return {key:'unresolved',label:'Unresolved',action:'Hold steady; test before moving spend'};
}

function render(){renderHero();renderMatrix();renderPanel();renderSpill();renderShift();renderText()}
function renderHero(){
  const survive=MODEL[M].channels.reduce((a,s)=>a+passed(s),0);
  const all=MODEL[M].channels.length*MODEL[M].destinations.length;
  const positive=MODEL[M].channels.filter(s=>rowTotal(s)>0).length,negative=MODEL[M].channels.filter(s=>rowTotal(s)<0).length;
  document.getElementById('hero').innerHTML=`${survive} / ${all} <em>attribution paths survive correction</em>`;
  document.getElementById('heroTxt').innerHTML=`In <strong>${esc(R)}</strong>, ${positive} source rows show a positive total-business result at risk and ${negative} show a counterintuitive negative association marked TEST. Separate source scenarios are not added into one budget claim, and negative rows are not treated as orders created or as permission to cut spend.`;
  document.getElementById('warn').innerHTML=`<strong>Conservative by design.</strong> The raw model is not displayed as the answer. For every pair, the calculator first removes the median fake-history effect and a 95% false-signal allowance. In validation, fake histories retained about <strong>74%</strong> of the observed headline signal before this correction—the issue previously described as 78%.`;
}

function renderMatrix(){
  const src=MODEL[M].channels,dst=MODEL[M].destinations;
  const max=Math.max(...src.flatMap(s=>dst.map(d=>Math.abs(cell(s,d)?.effect||0))),1);
  let h='<table class="m"><thead><tr><th></th>'+dst.map(d=>`<th class="col">${esc(d)}</th>`).join('')+'<th class="col" style="font-weight:800;color:#1a1a1a">Total business</th></tr></thead><tbody>';
  for(const s of src){h+=`<tr><th>${esc(s)}</th>`;for(const d of dst){const c=cell(s,d);const v=c?.effect||0;const ok=!!c?.passes_placebo;const a=ok?.15+.75*Math.sqrt(Math.abs(v)/max):0;const bg=!ok?'#e8e6df':v>=0?`rgba(31,122,63,${a})`:`rgba(179,38,30,${a})`;const fg=ok&&a>.52?'#fff':'#333';const sel=SELECTED&&SELECTED[0]===s&&SELECTED[1]===d?' sel':'';h+=`<td><div class="cell${sel}" data-s="${esc(s)}" data-d="${esc(d)}" style="background:${bg};color:${fg}" title="Attribution path ${esc(s)} to ${esc(d)}: ${signed(v)} protected by current spend">${ok&&Math.abs(v)>=1?signed(v):'—'}</div></td>`}const total=rowTotal(s),ta=.18+.72*Math.sqrt(Math.abs(total)/Math.max(...src.map(rowTotal).map(Math.abs),1)),tbg=total>0?`rgba(31,122,63,${ta})`:total<0?'#f1d9d6':'#e8e6df',tfg=total>0&&ta>.52?'#fff':'#222',label=total<0?'TEST':total>0?signed(total):'—';h+=`<td style="border-left:3px solid #1a1a1a"><div class="cell" style="background:${tbg};color:${tfg};font-weight:800;cursor:default" title="${total<0?`Unresolved negative association ${signed(total)}; do not treat as orders created without a holdout`:`Total company result protected by current ${esc(s)} level: ${signed(total)}`}">${label}</div></td></tr>`}h+='</tbody></table>';
  const el=document.getElementById('matrix');el.innerHTML=h;el.querySelectorAll('.cell[data-d]').forEach(x=>x.onclick=()=>{SELECTED=[x.dataset.s,x.dataset.d];renderMatrix();renderPanel()});
  document.getElementById('matcap').textContent=`${M==='revenue'?'Revenue':'New-order'} effect over 365 days in ${R}, shown as current result minus the result after a 20% cut. Positive is at risk after the cut. A negative destination cell can be credit routing; use Total business for the company-wide result.`;
}

function renderPanel(){
  if(!SELECTED){document.getElementById('panel').innerHTML='<h3 style="color:#888;font-weight:500">Select a cell</h3><p style="color:#888">Pick a source and destination pair to see its raw estimate, empirical correction, interval, row-total context and placebo diagnostics.</p>';return;}
  const [s,d]=SELECTED,c=cell(s,d);if(!c)return;
  const verdict=c.passes_placebo?(c.effect>=0?'Result protected by current spend':'Destination credit may rise after a cut'):'Does not survive correction';
  const cls=c.passes_placebo?(c.effect>=0?'v-hold':'v-neg'):'v-no';
  const total=rowTotal(s), cutChange=-c.effect, totalCutChange=-total;
  const meaning=d===s?'This is the source channel\'s own credited destination.':`This is an attribution-path cell, not the total company result. ${c.effect<0?'The model says some credit may move here after the cut; that is not evidence that the cut creates total orders.':''}`;
  const totalMeaning=total>0?`Across every destination, the model predicts the cut would reduce company ${M} by ${num(total)}.`:total<0?`Across every destination, the model has a ${num(-total)} counterintuitive gain association. The calculator classifies this as TEST / unresolved, not as orders created and not as a recommendation to cut spend.`:`Across every destination, no company-wide effect survives correction.`;
  document.getElementById('panel').innerHTML=`<h3>${esc(s)} &rarr; ${esc(d)}</h3><span class="verdict ${cls}">${verdict}</span><p class="why">${meaning} ${totalMeaning}</p><div class="stats">
    <div class="stat"><div class="k">Current minus reduced</div><div class="v">${signed(c.effect)}</div><div class="ex">this credited destination</div></div>
    <div class="stat"><div class="k">Predicted change after cut</div><div class="v">${signed(cutChange)}</div><div class="ex">this credited destination</div></div>
    <div class="stat"><div class="k">Total business decision</div><div class="v">${total<0?'TEST':total>0?signed(total):'—'}</div><div class="ex">${total<0?`unresolved model association ${signed(total)}`:`cut changes total by ${signed(totalCutChange)}`}</div></div>
    <div class="stat"><div class="k">Raw model</div><div class="v">${signed(c.raw_effect)}</div><div class="ex">before empirical-null correction</div></div>
    <div class="stat"><div class="k">80% interval</div><div class="v">${signed(c.lower80)} to ${signed(c.upper80)}</div></div>
    <div class="stat"><div class="k">Placebo bias</div><div class="v">${signed(c.placebo_bias)}</div><div class="ex">median of ${c.placebo_runs} shifts</div></div>
    <div class="stat"><div class="k">False-signal bar</div><div class="v">${num(c.placebo_threshold)}</div><div class="ex">95th percentile</div></div>
    <div class="stat"><div class="k">FDR q-value</div><div class="v">${(100*c.placebo_q_value).toFixed(1)}%</div><div class="ex">empirical p ${(100*c.placebo_empirical_p_value).toFixed(1)}%</div></div></div>`;
}

function renderSpill(){
  const cut=Math.abs(SUMMARY.scenario_relative_change),rows=MODEL.orders.channels.map(s=>{
    const spend=SUMMARY.views[R]?.sources?.[s]?.spend,saved=spend==null?null:spend*cut,o=rowIntervalFor('orders',R,s),r=rowIntervalFor('revenue',R,s),status=sourceStatus(s);
    return {s,spend,saved,o,r,status,oc:MODEL.orders.destinations.filter(d=>cellFor('orders',R,s,d)?.passes_placebo).length,rc:MODEL.revenue.destinations.filter(d=>cellFor('revenue',R,s,d)?.passes_placebo).length};
  }).sort((a,b)=>Math.abs(b.r.total)-Math.abs(a.r.total));
  let h='<div class="hscroll"><table class="s tight"><tr><th class="stick">Channel</th><th>20% spend<br>saved</th><th>Orders protected<br><span class="asof">diagnostic 80%</span></th><th>Revenue protected<br><span class="asof">diagnostic 80%</span></th><th>Revenue at risk<br>/ $ saved</th><th>Saved spend<br>/ order at risk</th><th>Evidence</th><th>Status</th><th>Action</th></tr>';
  for(const x of rows){const neg=x.o.total<0||x.r.total<0,ofmt=x.o.total<0?'TEST':x.o.total>0?`${short(x.o.total,'orders')}<div class="asof">${short(x.o.low,'orders')} to ${short(x.o.high,'orders')}</div>`:'—',rfmt=x.r.total<0?'TEST':x.r.total>0?`${short(x.r.total,'revenue')}<div class="asof">${short(x.r.low,'revenue')} to ${short(x.r.high,'revenue')}</div>`:'—',ratio=x.saved&&x.r.total>0?x.r.total/x.saved:null,cpo=x.saved&&x.o.total>0?x.saved/x.o.total:null;h+=`<tr><td class="l stick">${esc(x.s)}</td><td>${x.saved==null?'—':fmtM(x.saved)}</td><td class="${x.o.total<0?'val-bad':''}">${ofmt}</td><td class="${x.r.total<0?'val-bad':''}">${rfmt}</td><td>${ratio==null?'—':ratio.toFixed(2)+'×'}</td><td>${cpo==null?'—':'$'+fmtN.format(cpo)}</td><td>O ${x.oc}/14 · R ${x.rc}/14</td><td><strong class="${x.status.key==='test'?'val-bad':''}">${x.status.label}</strong></td><td class="wrap">${x.status.action}</td></tr>`}h+='</table></div><p class="cap">Row intervals conservatively add passing-cell standard errors before applying the 80% multiplier; they are diagnostics, not experimental confidence intervals.</p>';document.getElementById('spill').innerHTML=h;
}

// Original report SVG bar renderer, retaining its dimensions, axis, spacing and two-bar treatment.
function renderShift(){
  const el=document.getElementById('shift'); if(!el) return;
  const cap=document.getElementById('shiftcap');
  if(cap) cap.innerHTML=(M==='revenue'?'Revenue':'New-order')+' protected by current spend for <strong>'+esc(R)+'</strong>. Gray is the source\'s own credited path; colored is the company-wide total across all destinations.';
  const rows=MODEL[M].channels.map(k=>({k,a:direct(k),b:rowTotal(k)})).filter(x=>Number.isFinite(x.a)&&Number.isFinite(x.b)).sort((x,y)=>Math.abs(y.b)-Math.abs(x.b));
  const W=880,L=118,RPAD=88,rowH=30,top=6,HH=top+rows.length*rowH+24;
  const lo=Math.min(0,...rows.flatMap(x=>[x.a,x.b])),hi=Math.max(0,...rows.flatMap(x=>[x.a,x.b]));
  const range=Math.max(hi-lo,1), plotW=W-L-RPAD, x=v=>L+(v-lo)/range*plotW, zero=x(0);
  let svg=`<div class="key"><span><i style="background:${GREY}"></i>Own credited path</span><span><i style="background:${GREEN}"></i>Total business result</span></div><svg viewBox="0 0 ${W} ${HH}" role="img" aria-label="Own credited effect compared with total business effect by channel"><line class="axis" x1="${zero}" x2="${zero}" y1="0" y2="${HH-19}"/>`;
  rows.forEach((r,i)=>{const y=top+i*rowH;const bar=(v,yy,color)=>{const xx=x(v),left=Math.min(zero,xx),w=Math.max(1,Math.abs(xx-zero));return `<rect x="${left}" y="${yy}" width="${w}" height="8" rx="1" fill="${color}"/>`};const color=r.b<0?RED:GREEN,label=r.b<0?`TEST ${signed(r.b)}`:signed(r.b);svg+=`<text class="lab" x="${L-7}" y="${y+14}" text-anchor="end">${esc(r.k)}</text>${bar(r.a,y+3,GREY)}${bar(r.b,y+13,color)}<text class="val" x="${r.b>=0?x(r.b)+5:x(r.b)-5}" y="${y+21}" text-anchor="${r.b>=0?'start':'end'}" fill="${color}">${label}</text>`});
  svg+='</svg>';el.innerHTML=svg;
}

function renderText(){
  const all=MODEL[M].channels.flatMap(s=>MODEL[M].destinations.map(d=>({s,d,c:cell(s,d)}))).filter(x=>x.c);
  const kept=all.filter(x=>x.c.passes_placebo), raw=all.reduce((a,x)=>a+Math.abs(x.c.raw_effect||0),0),adj=all.reduce((a,x)=>a+Math.abs(x.c.effect||0),0);
  document.getElementById('rely').innerHTML=`<div class="hscroll"><table class="s"><tr><th>Diagnostic</th><th>${esc(R)} ${M}</th></tr><tr><td class="l">Attribution paths tested</td><td>${all.length}</td></tr><tr><td class="l">Paths surviving all gates</td><td>${kept.length}</td></tr><tr><td class="l">Absolute raw association</td><td>${num(raw)}</td></tr><tr><td class="l">Absolute adjusted association</td><td>${num(adj)}</td></tr><tr><td class="l">Magnitude removed by the conservative correction</td><td>${raw?((1-adj/raw)*100).toFixed(1):'0.0'}%</td></tr><tr><td class="l">Placebo refits per path</td><td>${MODEL[M].metadata.placebo_runs}</td></tr></table></div><p class="cap">The removed share is shrinkage applied by the estimator; it is not an estimate of the percentage that was definitively false.</p>`;
  document.getElementById('sens').innerHTML=`<p><strong>The fake histories are part of the estimator, not a claim of causality.</strong> Each source series is shifted to dates where the real timing cannot survive and the complete model is rerun. The fixed rule removes the pair-specific median placebo bias, subtracts its 95th-percentile false-signal allowance, and applies matrix-wide false-discovery control.</p><div class="eq">adjusted = sign(raw − placebo median) × max(|raw − placebo median| − placebo 95th percentile, 0)<br>publish only if the empirical false-discovery gate also passes</div>`;
  const geos=MODEL[M].metadata.geographies,stability=MODEL[M].channels.map(s=>{const total=rowTotalFor(M,R,s),sign=Math.sign(total),vals=geos.map(g=>rowTotalFor(M,g,s)),pos=vals.filter(v=>v>0).length,neg=vals.filter(v=>v<0).length,none=vals.filter(v=>v===0).length,same=sign===0?0:vals.filter(v=>Math.sign(v)===sign).length,orO=rowTotalFor('orders',R,s),orR=rowTotalFor('revenue',R,s),agree=orO&&orR&&Math.sign(orO)===Math.sign(orR)?'Agree':orO||orR?'Mixed / one absent':'No signal';return{s,total,pos,neg,none,same,agree}}).sort((a,b)=>Math.abs(b.total)-Math.abs(a.total));
  document.getElementById('stab').innerHTML='<div class="hscroll"><table class="s"><tr><th class="stick">Source</th><th>Positive markets</th><th>Negative / TEST</th><th>No signal</th><th>Markets matching Total</th><th>Orders / revenue</th><th>Total-business effect</th></tr>'+stability.map(x=>`<tr><td class="l stick">${esc(x.s)}</td><td>${x.pos} / ${geos.length}</td><td>${x.neg} / ${geos.length}</td><td>${x.none} / ${geos.length}</td><td>${x.same} / ${geos.length}</td><td>${x.agree}</td><td>${x.total<0?'TEST '+signed(x.total):x.total?signed(x.total):'—'}</td></tr>`).join('')+'</table></div>';
  document.getElementById('cons').innerHTML=`<div class="method"><p><strong>All views are generated from the same corrected cell matrix.</strong> Each Total business cell is the sum of the fourteen attribution-path cells in its row; the source table and SVG bars use that identical total. A negative path can be offset by positive paths elsewhere, so it is never presented as a company-wide gain on its own. The region called Total is constructed from separately fitted geography outputs.</p></div>`;
  const groups={protect:[],unresolved:[],test:[],none:[]};MODEL.orders.channels.forEach(s=>groups[sourceStatus(s).key].push(s));
  document.getElementById('suggest').innerHTML=`<div class="callout"><h4>Protect while testing</h4><p>${groups.protect.length?groups.protect.map(esc).join(', '):'None in this view.'} These rows have positive orders and revenue with diagnostic row intervals above zero; that still does not authorize a permanent budget move.</p></div><div class="callout"><h4>Hold steady; unresolved</h4><p>${groups.unresolved.length?groups.unresolved.map(esc).join(', '):'None in this view.'} At least one outcome or row interval is not decisive.</p></div><div class="callout"><h4>Counterintuitive — do not cut from this model</h4><p>${groups.test.length?groups.test.map(esc).join(', '):'None in this view.'} Test for cannibalization or attribution routing before treating a negative association as savings.</p></div><div class="callout"><h4>No surviving evidence</h4><p>${groups.none.length?groups.none.map(esc).join(', '):'None in this view.'} This means no claim, not zero effectiveness.</p></div>`;
  const paid=MODEL.orders.channels.filter(s=>SUMMARY.views[R]?.sources?.[s]?.spend!=null),positive=paid.filter(s=>sourceStatus(s).key==='protect').sort((a,b)=>rowTotalFor('revenue',R,b)-rowTotalFor('revenue',R,a)).slice(0,3),counter=paid.filter(s=>sourceStatus(s).key==='test').slice(0,1),priorities=[...positive,...counter],days=56;
  let exp='<div class="hscroll"><table class="s tight"><tr><th class="stick">Priority</th><th>Test market</th><th>Holdout</th><th>Duration</th><th>Spend withheld</th><th>Primary KPI</th><th>Required MDE ceiling</th><th>Decision rule</th></tr>';
  for(const s of priorities){const test=sourceStatus(s).key==='test',matching=geos.filter(g=>test?rowTotalFor('revenue',g,s)<0:rowTotalFor('revenue',g,s)>0),pool=matching.length?matching:geos,geo=[...pool].sort((a,b)=>(SUMMARY.views[b]?.sources?.[s]?.spend||0)-(SUMMARY.views[a]?.sources?.[s]?.spend||0))[0],geoSpend=SUMMARY.views[geo]?.sources?.[s]?.spend||0,saved=geoSpend*Math.abs(SUMMARY.scenario_relative_change),rev=rowTotalFor('revenue',geo,s),orders=rowTotalFor('orders',geo,s),mde=Math.abs(rev)*days/365;exp+=`<tr><td class="l stick">${esc(s)}${test?' · cannibalization check':''}</td><td>${esc(geo)} audience / geo clusters</td><td>20%</td><td>8 weeks</td><td>${fmtM(saved*days/365)}</td><td>Total new-customer revenue<br><span class="asof">secondary: total orders + all destinations</span></td><td>${test?'Detect '+fmtM(mde)+' or smaller':short(mde,'revenue')+' revenue; '+short(Math.abs(orders)*days/365,'orders')+' orders'}</td><td class="wrap">${test?'Do not cut unless a randomized interval supports a genuine total-business gain.':'Protect if the randomized total-business interval excludes zero; otherwise classify unresolved.'}</td></tr>`}exp+='</table></div><p class="cap">Spend withheld and the MDE ceiling use the selected test market only. The MDE ceiling is the largest minimum detectable effect the design can tolerate if it is to test the model-sized eight-week effect. Recalculate actual power from pre-period experimental-unit variance before assignment.</p>';document.getElementById('hold').innerHTML=exp;
  document.getElementById('appendix').innerHTML=`<p><strong>Status:</strong> ${esc(MODEL[M].status)}.</p><p><strong>Window:</strong> ${MODEL[M].metadata.date_min} through ${MODEL[M].metadata.date_max}; ${fmtN.format(MODEL[M].metadata.row_count)} geography-days.</p><p><strong>Measures:</strong> orders and net revenue are fitted separately with the same channels, destinations, scenario and placebo rules.</p><p><strong>Row uncertainty:</strong> the displayed diagnostic interval sums the standard errors of passing destination cells before applying the 80% multiplier. This is deliberately conservative and avoids assuming destinations are independent, but it is not a randomized confidence interval.</p><p><strong>Important limitation:</strong> no completed randomized experiments were available for calibration, so the calculator remains observational.</p>`;
}
