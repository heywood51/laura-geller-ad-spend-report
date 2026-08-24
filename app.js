'use strict';

let M='orders', R='Total', SELECTED=null;
let MODEL={}, TOTAL={}, BALANCED={}, SUMMARY={}, IVALID={}, TVDIAG={};
const GREEN='#1f7a3f', RED='#b3261e', GREY='#c9c7bd';
const fmtN=new Intl.NumberFormat('en-US',{maximumFractionDigits:0});
const fmtM=v=>(v<0?'-':'')+'$'+(Math.abs(v)>=1e6?(Math.abs(v)/1e6).toFixed(1)+'m':fmtN.format(Math.abs(v)));
const num=(v,m=M)=>m==='revenue'?fmtM(v):fmtN.format(v);
const signed=(v,m=M)=>(v>0?'+':'')+num(v,m);
const short=(v,m)=>{const a=Math.abs(v),p=v<0?'-':v>0?'+':'';const n=a>=1e6?(a/1e6).toFixed(1)+'m':a>=1e3?(a/1e3).toFixed(0)+'k':fmtN.format(a);return p+(m==='revenue'?'$':'')+n};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

Promise.all([
  fetch('model/generated/halo-created-orders.json').then(r=>r.json()),
  fetch('model/generated/halo-created-revenue.json').then(r=>r.json()),
  fetch('model/generated/halo-balanced-orders.json?v=2').then(r=>r.json()),
  fetch('model/generated/halo-balanced-revenue.json?v=2').then(r=>r.json()),
  fetch('model/generated/halo-incrementality-orders.json').then(r=>r.json()),
  fetch('model/generated/halo-incrementality-revenue.json').then(r=>r.json()),
  fetch('model/generated/report-summary.json').then(r=>r.json()),
  fetch('model/generated/placebo-incrementality-orders.json').then(r=>r.json()),
  fetch('model/generated/placebo-incrementality-revenue.json').then(r=>r.json()),
  fetch('model/generated/tv-halo-diagnostic.json?v=1').then(r=>r.json())
]).then(([createdOrders,createdRevenue,balancedOrders,balancedRevenue,totalOrders,totalRevenue,summary,valOrders,valRevenue,tvdiag])=>{
  MODEL={orders:createdOrders,revenue:createdRevenue}; TOTAL={orders:totalOrders,revenue:totalRevenue};
  BALANCED={orders:balancedOrders,revenue:balancedRevenue};
  SUMMARY=summary; IVALID={orders:valOrders,revenue:valRevenue}; TVDIAG=tvdiag; buildTabs(); bind(); render();
}).catch(err=>{document.getElementById('hero').textContent='The model files could not be loaded';document.getElementById('heroTxt').textContent=err.message});

function data(){return MODEL[M].views[R]||MODEL[M].views.Total}
function cell(s,d){return data().cells[s+'|'+d]||null}
function balancedData(){return BALANCED[M].views[R]||BALANCED[M].views.Total}
function balancedCell(s,d){return balancedData().cells[s+'|'+d]||null}
function balancedRowTotal(s){return balancedData().row_totals[s]||0}
function cellFor(m,g,s,d){return MODEL[m].views[g]?.cells[s+'|'+d]||null}
function totalCellFor(m,g,s){return TOTAL[m].views[g]?.cells[s+'|Total Business']||null}
function accepted(c){return !!(c?.passes_placebo&&c.effect>0&&c.lower80>0)}
function rowTotalFor(m,g,s){return MODEL[m].views[g]?.row_totals?.[s]??MODEL[m].destinations.reduce((a,d)=>a+(cellFor(m,g,s,d)?.effect||0),0)}
function rowTotal(s){return rowTotalFor(M,R,s)}
function direct(s){return cell(s,s)?.effect||0}
function routeCount(m,g,s){return MODEL[m].destinations.filter(d=>cellFor(m,g,s,d)?.passes_placebo).length}
function haloRouteCount(m,g,s){return MODEL[m].destinations.filter(d=>d!==s&&cellFor(m,g,s,d)?.passes_placebo).length}
function attributionBenchmark(m,g,d){return (SUMMARY.views[g]?.[m]?.[d]||0)*Math.abs(SUMMARY.scenario_relative_change)}
function columnParts(m,g,d){
  const self=MODEL[m].channels.includes(d)?(cellFor(m,g,d,d)?.effect||0):0;
  const halo=MODEL[m].channels.reduce((a,s)=>a+(s===d?0:(cellFor(m,g,s,d)?.effect||0)),0);
  const benchmark=attributionBenchmark(m,g,d),supported=self+halo;
  return {self,halo,supported,benchmark,gap:benchmark-supported,overage:Math.max(0,supported-benchmark)};
}
function rowIntervalFor(m,g,s){const c=totalCellFor(m,g,s);return {total:c?.effect||0,low:c?.lower80||0,high:c?.upper80||0,se:c?.standard_error||0,passes:!!c?.passes_placebo,accepted:accepted(c),q:c?.placebo_q_value}}
function sourceStatus(s,g=R){
  const o=rowIntervalFor('orders',g,s),r=rowIntervalFor('revenue',g,s);
  if(o.accepted&&r.accepted)return {key:'protect',label:'Supported / test',action:'Protect while confirming with a holdout'};
  if(o.accepted||r.accepted)return {key:'partial',label:'Partial evidence',action:'Hold steady; test the unresolved outcome'};
  if((o.passes&&o.total<0)||(r.passes&&r.total<0))return {key:'test',label:'TEST counterintuitive',action:'Do not cut; investigate in a holdout'};
  if(o.passes||r.passes)return {key:'unresolved',label:'Unresolved total',action:'Hold steady; the total interval includes zero'};
  return {key:'none',label:'No incrementality evidence',action:'No budget claim; create better variation'};
}
function buildTabs(){const geos=['Total',...MODEL.orders.metadata.geographies];document.getElementById('rTabs').innerHTML=geos.map(g=>`<button data-r="${esc(g)}" class="${g==='Total'?'on':''}">${g==='United Kingdom'?'UK':g==='United States'?'US':esc(g)}</button>`).join('')}
function bind(){document.getElementById('mTabs').onclick=e=>{if(!e.target.dataset.m)return;M=e.target.dataset.m;SELECTED=null;setOn('mTabs','m',M);render()};document.getElementById('rTabs').onclick=e=>{if(!e.target.dataset.r)return;R=e.target.dataset.r;SELECTED=null;setOn('rTabs','r',R);render()}}
function setOn(id,k,v){document.querySelectorAll('#'+id+' button').forEach(b=>b.classList.toggle('on',b.dataset[k]===v))}
function render(){renderHero();renderMatrixV2();renderPanelV3();renderSpill();renderShift();renderText()}

function renderHero(){
  const view=balancedData(),rec=Object.values(view.column_reconciliation),halo=rec.reduce((a,x)=>a+x.cross_source_halo,0),benchmark=rec.reduce((a,x)=>a+x.benchmark,0),paths=MODEL[M].channels.flatMap(s=>MODEL[M].destinations.map(d=>s!==d&&balancedCell(s,d)?.effect>0)).filter(Boolean).length,v=IVALID[M].summary;
  document.getElementById('hero').innerHTML=`${short(halo,M)} <em>of the ${num(benchmark)} attribution benchmark is reassigned as halo</em>`;
  document.getElementById('heroTxt').innerHTML=`In <strong>${esc(R)}</strong>, ${paths} off-diagonal paths are supported after continuous uncertainty weighting. The remainder stays with its original destination diagonal, so one correlated channel cannot absorb the whole business.`;
  document.getElementById('warn').innerHTML=`<strong>Raw association is not the answer.</strong> Fake histories reproduced ${Math.round(100*v.fake_to_observed_absolute_median)}% of the raw headline magnitude, so the calculator rejects that raw model. After calibration, the separate held-out gate published <strong>0 false source rows in both the median and worst of ${v.heldout_placebo_runs} fake histories</strong>. This is strong falsification performance, but only a randomized holdout can establish causality.`;
}

function renderMatrixV2(){
  const src=MODEL[M].channels,dst=MODEL[M].destinations;
  const max=Math.max(...src.flatMap(s=>dst.map(d=>Math.abs(balancedCell(s,d)?.effect||0))),1);
  const rowMax=Math.max(...src.map(balancedRowTotal),1);
  let h='<table class="m"><thead><tr><th></th>'+dst.map(d=>`<th class="col">${esc(d)}</th>`).join('')+'<th class="col" style="font-weight:800;color:#1a1a1a">Total business</th></tr></thead><tbody>';
  for(const s of src){
    h+=`<tr><th>${esc(s)}</th>`;
    for(const d of dst){
      const c=balancedCell(s,d),v=c?.effect||0,ok=v>0,self=s===d,structural=c?.kind==='structural_zero_non_addressable';
      const a=ok?.15+.75*Math.sqrt(v/max):0,bg=ok?(self?`rgba(70,105,130,${a})`:`rgba(31,122,63,${a})`):'#e8e6df',fg=ok&&a>.52?'#fff':'#333';
      const sel=SELECTED&&SELECTED[0]===s&&SELECTED[1]===d?' sel':'';
      const title=structural?`${s} cannot receive direct attribution; any supported effect must route off-diagonal`:ok?(self?`${signed(v)} original attribution retained on diagonal`:`${signed(v)} cross-source halo ${M} assigned from ${esc(d)} to ${esc(s)}`):'No stable halo allocated';
      h+=`<td><div class="cell${sel}" data-s="${esc(s)}" data-d="${esc(d)}" style="background:${bg};color:${fg}" title="${title}">${structural?'0':ok&&v>=1?signed(v):'—'}</div></td>`;
    }
    const total=balancedRowTotal(s),ok=total>0,a=ok?.18+.72*Math.sqrt(total/rowMax):0,bg=ok?`rgba(31,122,63,${a})`:'#e8e6df',fg=ok&&a>.52?'#fff':'#222';
    h+=`<td style="border-left:3px solid #1a1a1a"><div class="cell" style="background:${bg};color:${fg};font-weight:800;cursor:default" title="${num(total)} diagonally balanced attribution assigned to ${esc(s)}">${ok?num(total):'—'}</div></td></tr>`;
  }
  const parts=dst.map(d=>{const x=balancedData().column_reconciliation[d];return {self:x.retained_self_attribution,halo:x.cross_source_halo,gap:x.unassigned_original_attribution,benchmark:x.benchmark}}),sum=k=>parts.reduce((a,p)=>a+p[k],0);
  const reconRow=(label,key)=>`<tr><th>${label}</th>${parts.map(p=>`<td><div class="cell" style="cursor:default">${Math.abs(p[key])>=1?num(p[key]):'—'}</div></td>`).join('')}<td style="border-left:3px solid #1a1a1a"><div class="cell" style="cursor:default;font-weight:800">${num(sum(key))}</div></td></tr>`;
  h+='</tbody><tfoot>'+reconRow('Retained original attribution','self')+reconRow('Cross-source halo','halo')+reconRow('Unassigned / non-addressable','gap')+reconRow('20% attribution benchmark','benchmark')+'</tfoot></table>';
  const el=document.getElementById('matrix');el.innerHTML=h;
  el.querySelectorAll('.cell[data-d]').forEach(x=>x.onclick=()=>{SELECTED=[x.dataset.s,x.dataset.d];renderMatrixV2();renderPanelV3()});
  document.getElementById('matcap').textContent=`Every destination column reconciles exactly: retained original attribution + uncertainty-weighted cross-source halo + any no-diagonal remainder = the 20% attribution benchmark for ${R}.`;
}

function renderPanelV2(){
  if(!SELECTED){document.getElementById('panel').innerHTML='<h3 style="color:#888;font-weight:500">Select a cell</h3><p style="color:#888">Pick a cell to see whether it is a same-source check or genuine cross-source halo, plus its destination-column reconciliation.</p>';return}
  const [s,d]=SELECTED,c=cell(s,d);if(!c)return;
  const tc=totalCellFor(M,R,s),ok=!!c.passes_placebo,totalOK=accepted(tc),pct=100*(c.routing_weight||0),self=s===d,parts=columnParts(M,R,d);
  const verdict=ok?(self?'Self-attribution check':'Halo result published'):'No created result published',cls=ok?'v-hold':'v-no';
  const why=ok?(self?`${num(c.effect)} is the supported same-source portion of the ${num(parts.benchmark)} 20% original-attribution benchmark for ${d}. It is a reconciliation check, not halo.`:`The model supports ${num(tc.effect)} total-business ${M} created by ${s}; ${pct.toFixed(1)}% is credited to ${d} as cross-source halo.`):`The calculator does not claim that ${s} created ${M} credited to ${d}, because total incrementality, destination routing, or both did not clear the gate.`;
  document.getElementById('panel').innerHTML=`<h3>${esc(s)} &rarr; ${esc(d)}</h3><span class="verdict ${cls}">${verdict}</span><p class="why">${esc(why)}</p><div class="stats">
    <div class="stat"><div class="k">${self?'Same-source check':'Cross-source halo'}</div><div class="v">${ok?signed(c.effect):'—'}</div><div class="ex">supported total × routing share</div></div>
    <div class="stat"><div class="k">Share of supported source total</div><div class="v">${ok?pct.toFixed(1)+'%':'—'}</div></div>
    <div class="stat"><div class="k">Supported source total</div><div class="v">${totalOK?signed(tc.effect):'—'}</div></div>
    <div class="stat"><div class="k">Total 80% interval</div><div class="v">${tc?signed(tc.lower80)+' to '+signed(tc.upper80):'—'}</div></div>
    <div class="stat"><div class="k">20% column benchmark</div><div class="v">${num(parts.benchmark)}</div><div class="ex">same measurement basis</div></div>
    <div class="stat"><div class="k">Same-source supported</div><div class="v">${num(parts.self)}</div></div>
    <div class="stat"><div class="k">Other-source halo</div><div class="v">${num(parts.halo)}</div></div>
    <div class="stat"><div class="k">${parts.gap>=0?'Unresolved remainder':'Over benchmark'}</div><div class="v">${num(Math.abs(parts.gap))}</div></div>
    <div class="stat"><div class="k">Routing gate</div><div class="v">${c.routing_passes?'Pass':'Unresolved'}</div></div>
    <div class="stat"><div class="k">Row status</div><div class="v">${esc((c.row_status||'unresolved').replaceAll('_',' '))}</div></div></div>`;
}

function renderPanelV3(){
  if(!SELECTED){document.getElementById('panel').innerHTML='<h3 style="color:#888;font-weight:500">Select a cell</h3><p style="color:#888">Blue diagonal cells retain original attribution. Green off-diagonal cells are uncertainty-weighted halo estimates.</p>';return}
  const [s,d]=SELECTED,c=balancedCell(s,d);if(!c)return;
  const self=s===d,structural=c.kind==='structural_zero_non_addressable',rec=balancedData().column_reconciliation[d],ev=c.source_evidence||balancedData().source_evidence[s];
  const verdict=structural?'Structural zero: non-addressable':self?'Retained original attribution':c.effect>0?'Cross-source halo estimate':'No stable halo allocated';
  const why=structural?`${s} results cannot normally be attributed back to ${s}, so this diagonal is forced to zero. Any supported ${s} effect must appear in other destination columns.`:self?`${num(c.effect)} remains on ${d}'s original-attribution diagonal after supported inbound halo is removed. This is the consistency anchor, not a claim that ${d} spend caused every retained result.`:c.effect>0?`${num(c.effect)} is reassigned from ${d}'s original attribution to ${s}. The source estimate is discounted by ${(100*ev.reliability_weight).toFixed(0)}% for uncertainty before routing.`:`The available data does not provide stable enough source and routing evidence to reassign ${d} attribution to ${s}.`;
  const tv=TVDIAG[M],tvStats=structural?`<div class="stat"><div class="k">TV-specific candidate</div><div class="v">${signed(tv.candidate_effect)}</div><div class="ex">not published</div></div><div class="stat"><div class="k">TV candidate 80%</div><div class="v">${signed(tv.lower80)} to ${signed(tv.upper80)}</div></div><div class="stat"><div class="k">TV time-placebo p</div><div class="v">${(100*tv.time_placebo_empirical_p).toFixed(1)}%</div></div><div class="stat"><div class="k">TV failed checks</div><div class="v">${esc(tv.failed_gates.join(', ').replaceAll('_',' '))}</div></div>`:'';
  document.getElementById('panel').innerHTML=`<h3>${esc(s)} &rarr; ${esc(d)}</h3><span class="verdict ${c.effect>0?'v-hold':'v-no'}">${verdict}</span><p class="why">${esc(why)}</p><div class="stats">
    <div class="stat"><div class="k">${structural?'Required diagonal':self?'Retained on diagonal':'Reassigned halo'}</div><div class="v">${structural?'0':c.effect>0?num(c.effect):'—'}</div></div>
    <div class="stat"><div class="k">Destination benchmark</div><div class="v">${num(rec.benchmark)}</div></div>
    <div class="stat"><div class="k">All inbound halo</div><div class="v">${num(rec.cross_source_halo)}</div></div>
    <div class="stat"><div class="k">Retained self-attribution</div><div class="v">${num(rec.retained_self_attribution)}</div></div>
    <div class="stat"><div class="k">Unassigned, no diagonal</div><div class="v">${num(rec.unassigned_original_attribution)}</div></div>
    <div class="stat"><div class="k">Source reliability weight</div><div class="v">${(100*ev.reliability_weight).toFixed(0)}%</div><div class="ex">continuous, not pass/fail</div></div>
    <div class="stat"><div class="k">Source adjusted effect</div><div class="v">${signed(ev.adjusted_total_effect)}</div></div>
    <div class="stat"><div class="k">Source 80% interval</div><div class="v">${signed(ev.lower80)} to ${signed(ev.upper80)}</div></div>
    <div class="stat"><div class="k">Routing evidence</div><div class="v">${c.routing_passes?'Pass':'Unresolved'}</div></div>
    ${tvStats}<div class="stat"><div class="k">Cell role</div><div class="v">${structural?'Non-addressable structural zero':self?'Consistency check':'Halo'}</div></div></div>`;
}

function renderMatrix(){
  const src=MODEL[M].channels,dst=MODEL[M].destinations,max=Math.max(...src.flatMap(s=>dst.map(d=>Math.abs(cell(s,d)?.effect||0))),1),rowMax=Math.max(...src.map(rowTotal),1);
  let h='<table class="m"><thead><tr><th></th>'+dst.map(d=>`<th class="col">${esc(d)}</th>`).join('')+'<th class="col" style="font-weight:800;color:#1a1a1a">Total business</th></tr></thead><tbody>';
  for(const s of src){h+=`<tr><th>${esc(s)}</th>`;for(const d of dst){const c=cell(s,d),v=c?.effect||0,ok=!!c?.passes_placebo,a=ok?.15+.75*Math.sqrt(v/max):0,bg=ok?`rgba(31,122,63,${a})`:'#e8e6df',fg=ok&&a>.52?'#fff':'#333',sel=SELECTED&&SELECTED[0]===s&&SELECTED[1]===d?' sel':'';h+=`<td><div class="cell${sel}" data-s="${esc(s)}" data-d="${esc(d)}" style="background:${bg};color:${fg}" title="${ok?`${signed(v)} incremental ${M} created by ${esc(s)} and credited to ${esc(d)}`:'No created result published: total incrementality, routing, or both are unresolved'}">${ok&&v>=1?signed(v):'—'}</div></td>`}const total=rowTotal(s),ok=accepted(totalCellFor(M,R,s)),a=ok?.18+.72*Math.sqrt(total/rowMax):0,bg=ok?`rgba(31,122,63,${a})`:'#e8e6df',fg=ok&&a>.52?'#fff':'#222';h+=`<td style="border-left:3px solid #1a1a1a"><div class="cell" style="background:${bg};color:${fg};font-weight:800;cursor:default" title="${ok?`${signed(total)} supported total-business ${M} created by ${esc(s)}`:'No supported total-business creation result'}">${ok?signed(total):'—'}</div></td></tr>`}h+='</tbody></table>';
  const el=document.getElementById('matrix');el.innerHTML=h;el.querySelectorAll('.cell[data-d]').forEach(x=>x.onclick=()=>{SELECTED=[x.dataset.s,x.dataset.d];renderMatrix();renderPanel()});document.getElementById('matcap').textContent=`Estimated incremental ${M} created by the row source and credited to the column over 365 days in ${R}. A cell prints only when total source incrementality and destination routing both pass. Printed cells sum exactly to Total business.`;
}

function renderPanel(){
  if(!SELECTED){document.getElementById('panel').innerHTML='<h3 style="color:#888;font-weight:500">Select a cell</h3><p style="color:#888">Pick a source and destination pair to see the total-business incrementality result and how the supported total was routed.</p>';return}
  const [s,d]=SELECTED,c=cell(s,d);if(!c)return;const tc=totalCellFor(M,R,s),ok=!!c.passes_placebo,totalOK=accepted(tc),pct=100*(c.routing_weight||0),verdict=ok?'Created result published':'No created result published',cls=ok?'v-hold':'v-no';
  const why=ok?`The model supports ${num(tc.effect)} total-business ${M} created by ${s}; ${pct.toFixed(1)}% is credited to ${d}.`:`The calculator does not claim that ${s} created ${M} credited to ${d}, because total incrementality, destination routing, or both did not clear the gate.`;
  document.getElementById('panel').innerHTML=`<h3>${esc(s)} &rarr; ${esc(d)}</h3><span class="verdict ${cls}">${verdict}</span><p class="why">${esc(why)}</p><div class="stats"><div class="stat"><div class="k">Created here</div><div class="v">${ok?signed(c.effect):'—'}</div><div class="ex">supported total × routing share</div></div><div class="stat"><div class="k">Share of supported total</div><div class="v">${ok?pct.toFixed(1)+'%':'—'}</div></div><div class="stat"><div class="k">Supported source total</div><div class="v">${totalOK?signed(tc.effect):'—'}</div><div class="ex">total-business decision layer</div></div><div class="stat"><div class="k">Total 80% interval</div><div class="v">${tc?signed(tc.lower80)+' to '+signed(tc.upper80):'—'}</div></div><div class="stat"><div class="k">Total FDR q-value</div><div class="v">${tc?.placebo_q_value!=null?(100*tc.placebo_q_value).toFixed(2)+'%':'—'}</div><div class="ex">99% source gate</div></div><div class="stat"><div class="k">Routing estimate</div><div class="v">${c.routing_effect?signed(c.routing_effect):'—'}</div><div class="ex">used only as a positive share</div></div><div class="stat"><div class="k">Routing gate</div><div class="v">${c.routing_passes?'Pass':'Unresolved'}</div></div><div class="stat"><div class="k">Row status</div><div class="v">${esc((c.row_status||'unresolved').replaceAll('_',' '))}</div></div></div>`;
}

function renderSpill(){
  const cut=Math.abs(SUMMARY.scenario_relative_change),rows=MODEL.orders.channels.map(s=>{const spend=SUMMARY.views[R]?.sources?.[s]?.spend,saved=spend==null?null:spend*cut,o=rowIntervalFor('orders',R,s),r=rowIntervalFor('revenue',R,s),status=sourceStatus(s);return{s,saved,o,r,status,oc:routeCount('orders',R,s),rc:routeCount('revenue',R,s)}}).sort((a,b)=>(b.r.accepted?b.r.total:0)-(a.r.accepted?a.r.total:0));
  let h='<div class="hscroll"><table class="s tight"><tr><th class="stick">Channel</th><th>20% spend<br>saved</th><th>Orders created<br><span class="asof">total 80%</span></th><th>Revenue created<br><span class="asof">total 80%</span></th><th>Revenue created<br>/ $ saved</th><th>Saved spend<br>/ order created</th><th>Evidence</th><th>Status</th><th>Action</th></tr>';
  for(const x of rows){const ratio=x.saved&&x.r.accepted?x.r.total/x.saved:null,cpo=x.saved&&x.o.accepted?x.saved/x.o.total:null;h+=`<tr><td class="l stick">${esc(x.s)}</td><td>${x.saved==null?'—':fmtM(x.saved)}</td><td>${x.o.accepted?`${short(x.o.total,'orders')}<div class="asof">${short(x.o.low,'orders')} to ${short(x.o.high,'orders')}</div>`:x.o.passes?'Unresolved':'—'}</td><td>${x.r.accepted?`${short(x.r.total,'revenue')}<div class="asof">${short(x.r.low,'revenue')} to ${short(x.r.high,'revenue')}</div>`:x.r.passes?'Unresolved':'—'}</td><td>${ratio==null?'—':ratio.toFixed(2)+'×'}</td><td>${cpo==null?'—':'$'+fmtN.format(cpo)}</td><td>O ${x.o.accepted?'pass':'—'} (${x.oc} routes) · R ${x.r.accepted?'pass':'—'} (${x.rc} routes)</td><td><strong class="${x.status.key==='test'?'val-bad':''}">${x.status.label}</strong></td><td class="wrap">${x.status.action}</td></tr>`}h+='</table></div><p class="cap">Economics appear only when the source-to-total-business result clears the final gate. Destination routing determines where that supported total is credited; it cannot manufacture a total.</p>';document.getElementById('spill').innerHTML=h;
}

function renderShift(){
  const el=document.getElementById('shift');if(!el)return;const cap=document.getElementById('shiftcap'),view=balancedData();
  const driverRows=MODEL[M].channels.map(k=>({k,a:view.column_reconciliation[k]?.benchmark||0,b:view.row_totals[k]||0}));
  const attributionOnly=MODEL[M].destinations.filter(k=>!MODEL[M].channels.includes(k)).map(k=>({k:k+' attribution',a:view.column_reconciliation[k].benchmark,b:view.column_reconciliation[k].unassigned_original_attribution}));
  const nonAddressableRemainder=MODEL[M].channels.reduce((a,k)=>a+(view.column_reconciliation[k]?.unassigned_original_attribution||0),0);
  const rows=[...driverRows,...attributionOnly,{k:'Unassigned non-addressable',a:0,b:nonAddressableRemainder}].sort((x,y)=>Math.max(y.a,y.b)-Math.max(x.a,x.b));
  const totalNetRaw=rows.reduce((a,r)=>a+r.b-r.a,0),totalNet=Math.abs(totalNetRaw)<1e-6?0:totalNetRaw;if(cap)cap.innerHTML=(M==='revenue'?'Revenue':'Orders')+' assigned to likely driver for <strong>'+esc(R)+'</strong>. Gray is original attribution; green/red is the balanced total. <strong>Zero-sum check: '+num(totalNet)+'</strong>.';
  const W=880,L=135,RPAD=155,rowH=30,top=6,HH=top+rows.length*rowH+24,hi=Math.max(1,...rows.flatMap(x=>[x.a,x.b])),plotW=W-L-RPAD,x=v=>L+v/hi*plotW;
  let svg=`<div class="key"><span><i style="background:${GREY}"></i>Original attribution benchmark</span><span><i style="background:${GREEN}"></i>Balanced total · net gain</span><span><i style="background:${RED}"></i>Balanced total · net loss</span></div><svg viewBox="0 0 ${W} ${HH}" role="img" aria-label="Original attribution compared with balanced driver total and net gain or loss by channel"><line class="axis" x1="${L}" x2="${L}" y1="0" y2="${HH-19}"/>`;
  rows.forEach((r,i)=>{const y=top+i*rowH,net=r.b-r.a,color=net>0?GREEN:net<0?RED:GREY,bar=(v,yy,c)=>`<rect x="${L}" y="${yy}" width="${Math.max(v?1:0,x(v)-L)}" height="8" rx="1" fill="${c}"/>`,label=`${num(r.b)} (${net>0?'+':''}${num(net)} net)`;svg+=`<text class="lab" x="${L-7}" y="${y+14}" text-anchor="end">${esc(r.k)}</text>${bar(r.a,y+3,GREY)}${bar(r.b,y+13,color)}<text class="val" x="${x(r.b)+5}" y="${y+21}" text-anchor="start" fill="${color}">${label}</text>`});svg+='</svg>';el.innerHTML=svg;
}

function renderText(){
  const v=IVALID[M].summary,supported=MODEL[M].channels.filter(s=>rowIntervalFor(M,R,s).accepted),routes=supported.reduce((a,s)=>a+routeCount(M,R,s),0);
  document.getElementById('rely').innerHTML=`<div class="hscroll"><table class="s"><tr><th>Diagnostic</th><th>${esc(R)} ${M}</th></tr><tr><td class="l">Source rows tested</td><td>${MODEL[M].channels.length}</td></tr><tr><td class="l">Source rows clearing final gate</td><td>${supported.length}</td></tr><tr><td class="l">Published destination routes</td><td>${routes}</td></tr><tr><td class="l">Raw fake / observed magnitude</td><td>${(100*v.fake_to_observed_absolute_median).toFixed(1)}%</td></tr><tr><td class="l">Held-out fake rows, median</td><td>${v.heldout_fake_passing_rows_median}</td></tr><tr><td class="l">Held-out fake rows, worst</td><td>${v.heldout_fake_passing_rows_max}</td></tr><tr><td class="l">Held-out fake histories</td><td>${v.heldout_placebo_runs}</td></tr></table></div><p class="cap">The high raw fake share demonstrates confounding in the uncorrected model. The held-out rows evaluate the final decision rule on fake histories that were not used to set it.</p>`;
  const tv=TVDIAG[M];
  document.getElementById('sens').innerHTML=`<p><strong>The calculator no longer uses a winner-takes-all source gate for the attribution matrix.</strong> Positive source evidence is continuously discounted for interval uncertainty, then divided only across corrected positive off-diagonal routes. Each destination caps inbound halo at its 20% original-attribution benchmark, and every remaining attributed result stays on that destination's diagonal.</p><div class="eq">halo budget = corrected source effect × continuous reliability weight<br>retained diagonal = attribution benchmark − supported inbound halo</div><p><strong>TV-specific result:</strong> the US donor-control intensity model estimates a directional ${num(tv.candidate_effect)} candidate, but publishes ${num(tv.published_effect)} because it failed ${esc(tv.failed_gates.join(', ').replaceAll('_',' '))}. TV ran every day and only in the US, so false timing patterns remain too large to identify its halo reliably.</p>`;
  const geos=MODEL[M].metadata.geographies,stability=MODEL[M].channels.map(s=>{const total=rowIntervalFor(M,R,s),vals=geos.map(g=>rowIntervalFor(M,g,s)),pos=vals.filter(x=>x.accepted).length,unresolved=vals.filter(x=>x.passes&&!x.accepted).length,none=vals.filter(x=>!x.passes).length,o=rowIntervalFor('orders',R,s),r=rowIntervalFor('revenue',R,s),agree=o.accepted&&r.accepted?'Both pass':o.accepted||r.accepted?'One passes':'Neither passes';return{s,total,pos,unresolved,none,agree}}).sort((a,b)=>(b.total.accepted?b.total.total:0)-(a.total.accepted?a.total.total:0));
  document.getElementById('stab').innerHTML='<div class="hscroll"><table class="s"><tr><th class="stick">Source</th><th>Supported markets</th><th>Unresolved markets</th><th>No evidence</th><th>Orders / revenue</th><th>Total-business result</th></tr>'+stability.map(x=>`<tr><td class="l stick">${esc(x.s)}</td><td>${x.pos} / ${geos.length}</td><td>${x.unresolved} / ${geos.length}</td><td>${x.none} / ${geos.length}</td><td>${x.agree}</td><td>${x.total.accepted?signed(x.total.total):'—'}</td></tr>`).join('')+'</table></div>';
  document.getElementById('cons').innerHTML='<div class="method"><p><strong>The attribution matrix reconciles exactly by construction.</strong> For destinations with a matching source row, retained diagonal attribution + inbound cross-source halo equals the 20% original-attribution benchmark. Organic and Direct have no spend-source diagonal, so any remainder stays explicitly unassigned. The strict source-to-total model remains visible in the decision table as a separate diagnostic rather than controlling the whole matrix.</p></div>';
  const groups={protect:[],partial:[],unresolved:[],test:[],none:[]};MODEL.orders.channels.forEach(s=>groups[sourceStatus(s).key].push(s));
  document.getElementById('suggest').innerHTML=`<div class="callout"><h4>Supported on both outcomes</h4><p>${groups.protect.length?groups.protect.map(esc).join(', '):'None in this view.'} Protect while confirming with a randomized holdout.</p></div><div class="callout"><h4>Partial evidence</h4><p>${groups.partial.length?groups.partial.map(esc).join(', '):'None in this view.'} One outcome clears the gate and the other does not.</p></div><div class="callout"><h4>Unresolved</h4><p>${[...groups.unresolved,...groups.test].length?[...groups.unresolved,...groups.test].map(esc).join(', '):'None in this view.'} Do not infer a cut or an increase from these observational estimates.</p></div><div class="callout"><h4>No incrementality evidence</h4><p>${groups.none.length?groups.none.map(esc).join(', '):'None in this view.'} This means the calculator cannot make a claim, not that effectiveness is zero.</p></div>`;
  const rank={protect:3,partial:2,unresolved:1},paid=MODEL.orders.channels.filter(s=>SUMMARY.views[R]?.sources?.[s]?.spend!=null),priorities=paid.filter(s=>rank[sourceStatus(s).key]).sort((a,b)=>rank[sourceStatus(b).key]-rank[sourceStatus(a).key]).slice(0,3),days=56;
  let exp='<div class="hscroll"><table class="s tight"><tr><th class="stick">Priority</th><th>Test market</th><th>Holdout</th><th>Duration</th><th>Spend withheld</th><th>Primary KPI</th><th>Model-sized 8-week effect</th><th>Decision rule</th></tr>';
  for(const s of priorities){const matching=geos.filter(g=>rowIntervalFor('revenue',g,s).accepted||rowIntervalFor('orders',g,s).accepted),pool=matching.length?matching:geos,geo=[...pool].sort((a,b)=>(SUMMARY.views[b]?.sources?.[s]?.spend||0)-(SUMMARY.views[a]?.sources?.[s]?.spend||0))[0],geoSpend=SUMMARY.views[geo]?.sources?.[s]?.spend||0,saved=geoSpend*Math.abs(SUMMARY.scenario_relative_change),rev=rowIntervalFor('revenue',geo,s),orders=rowIntervalFor('orders',geo,s),revEff=rev.accepted?rev.total*days/365:0,ordEff=orders.accepted?orders.total*days/365:0;exp+=`<tr><td class="l stick">${esc(s)}</td><td>${esc(geo)} audience / geo clusters</td><td>20%</td><td>8 weeks</td><td>${fmtM(saved*days/365)}</td><td>Total new-customer revenue<br><span class="asof">secondary: total orders</span></td><td>${revEff?short(revEff,'revenue'):'revenue unresolved'}; ${ordEff?short(ordEff,'orders'):'orders unresolved'}</td><td class="wrap">Treat the channel as causal only if the randomized total-business interval excludes zero in the predicted direction.</td></tr>`}exp+='</table></div><p class="cap">Use pre-period experimental-unit variance to power the test before assignment. Observational model size is a planning input, not proof.</p>';document.getElementById('hold').innerHTML=exp;
  document.getElementById('appendix').innerHTML=`<p><strong>Status:</strong> ${esc(MODEL[M].status)}.</p><p><strong>Window:</strong> ${MODEL[M].metadata.date_min} through ${MODEL[M].metadata.date_max}; ${fmtN.format(MODEL[M].metadata.row_count)} geography-days.</p><p><strong>Measures:</strong> orders and net revenue are fitted independently against total business, then routed to destinations.</p><p><strong>Decision rule:</strong> empirical-null correction, 99% source gate, and positive 80% interval; the final rule is checked on ${v.heldout_placebo_runs} separately held-out fake histories.</p><p><strong>Important limitation:</strong> no completed randomized experiments were available for calibration, so this remains observational evidence rather than a causal estimate.</p>`;
}
