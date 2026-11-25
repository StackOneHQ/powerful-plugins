'use strict';
const query=s=>document.querySelector(s);
let imageData='',original='',overlay='',result=null,bundle=null,imported=null;
let showingOverlay=false,benchmarks=null,revision=0,drawRevision=0;
const names={bars:'Bar labels',calendar:'Calendar and curve',ticks:'Visible Y ticks',first_customer:'First-customer caption',comparison_totals:'Comparison-period totals',external_daily_revenue:'Public daily revenue'};
const fmt=v=>v==null?'Unresolved':Number(v).toLocaleString(undefined,{maximumFractionDigits:2});
function readingMode(){return query('#agent').checked?'agent':query('#calendar').checked?'calendar':query('#automatic').checked?'bars':'manual';}
function sourceLink(source){
  const link=document.getElementById('sourceLink');link.hidden=true;link.removeAttribute('href');
  if(typeof source!=='string')return;
  try{const url=new URL(source);if(url.protocol!=='http:'&&url.protocol!=='https:')return;link.href=url.href;link.hidden=false;}
  catch{/* An invalid source remains plain evidence text. */}
}
function paragraph(text,container=query('#evidenceDecisions')){const p=document.createElement('p');p.textContent=text;container.append(p);return p;}
function benchmarkView(){
  const selected=bundle?.agent_views?.find(v=>v.id===result?.selected_view);
  let key=readingMode()==='agent'?null:readingMode()==='bars'?'automatic':readingMode()==='calendar'?'calendar':'geometry';
  if(selected)key=selected.reader==='first_customer'?'caption':selected.reader==='external_daily_revenue'?'external':selected.reader==='calendar'&&selected.scope==='inferred_correspondence'?'hypotheses':selected.reader==='bars'?'automatic':selected.reader;
  const labels={geometry:'GEOMETRY BENCHMARK',automatic:'BAR LABEL TEST',calendar:'CALENDAR IMAGE TEST',hypotheses:'CALENDAR INFERENCE TEST',caption:'FIRST-CUSTOMER TEST',ticks:'VISIBLE TICK TEST',external:'EXTERNAL EVIDENCE TESTS'};
  const b=key==='geometry'?benchmarks:benchmarks?.[key];
  query('#bench').textContent=b?.charts?b.passed+' / '+b.charts:key==='external'?(benchmarks?.external_studies?.length||0)+' studies':'—';
  query('#benchLabel').textContent=labels[key]||'SELECT A READER TO SEE ITS TEST';
  if(key==='comparison_totals')query('#benchLabel').textContent='TWO-TOTAL LINEAR HYPOTHESIS TEST';
  let note='Controlled benchmarks do not establish accuracy on public posts.';
  if(key==='caption')note=b?`${b.passed} of ${b.charts} flat-then-rising synthetic charts passed; ${b.abstentions} abstained. Caption truth was supplied by construction. No independent public accuracy measured.`:'No first-customer benchmark is available.';
  if(key==='comparison_totals')note=b?`${b.passed}/${b.charts} controlled linear charts passed; ${b.abstained} abstained; ${b.returned_failures} returned failures. Separately, ${b.assumption_stress_failures??0}/${b.assumption_stress_cases??0} scale/axis stress cases returned incorrect estimates. Shared linear scale and equal daily counts are assumptions; public values remain unchecked.`:'Two totals fit a shared linear axis. No independent public daily-value accuracy measured.';
  if(key==='external')note=(benchmarks?.external_studies||[]).map(s=>`${s.label}: ${s.passed}/${s.charts} pass, ${s.abstentions} abstain, ${s.returned_failures} returned failures.`).join(' ')+' These are separate controlled studies, not public accuracy.';
  query('#benchNote').textContent=note;
}
function draw(src){
  const token=++drawRevision,im=new Image();
  im.onload=()=>{if(token!==drawRevision)return;const c=query('#canvas');c.width=im.width;c.height=im.height;c.getContext('2d').drawImage(im,0,0);c.hidden=false;query('#empty').hidden=true;};
  im.src=src;
}
function invalidate(message='Settings changed. Run recovery to update the results.'){
  revision++;result=null;bundle=null;overlay='';showingOverlay=false;
  query('#rows').replaceChildren();query('#resultControls').hidden=true;query('#resultChoice').replaceChildren();
  query('#seriesCount').textContent='—';query('#pointCount').textContent='—';query('#trace').textContent='No current analysis.';query('#evidenceDecisions').textContent='No current evidence decisions.';
  for(const id of ['csv','json','toggle'])query('#'+id).disabled=true;
  query('#dailyCsv').hidden=true;query('#dailyCsv').disabled=true;
  if(original)draw(original);query('#stage').textContent=imageData?'Ready to inspect':'Awaiting chart';query('#status').textContent=message;benchmarkView();
}
function readerView(){
  const mode=readingMode(),strict=query('#strictOnly').checked;
  query('#kind').disabled=mode!=='manual';query('#calendarControls').hidden=mode!=='calendar';query('#agentControls').hidden=mode!=='agent';query('#scale').disabled=mode==='agent';
  query('#evidenceMode').disabled=strict;query('#profileUrl').disabled=strict;query('#profileText').disabled=strict;
  query('#profileControls').hidden=strict||query('#evidenceMode').value!=='profile';query('#discoveryNote').hidden=strict||query('#evidenceMode').value!=='discover';benchmarkView();
}
for(const id of ['calendar','agent','automatic'])query('#'+id).onchange=()=>{
  if(query('#'+id).checked)for(const other of ['calendar','agent','automatic'])if(other!==id)query('#'+other).checked=false;
  readerView();invalidate();
};
for(const id of ['sameMetric','fullMonth','kind','scale','strictOnly','evidenceMode'])query('#'+id).onchange=()=>{readerView();invalidate();};
for(const id of ['config','sourceUrl','postCaption','profileUrl','profileText'])query('#'+id).oninput=()=>{sourceLink(query('#sourceUrl').value);invalidate();};
query('#importUrl').oninput=()=>{
  if(imported){imageData='';original='';imported=null;drawRevision++;query('#canvas').hidden=true;query('#empty').hidden=false;query('#importImages').hidden=true;query('#importImage').replaceChildren();query('#sourceUrl').value='';query('#postCaption').value='';query('#config').value='{}';sourceLink('');}
  invalidate('Post URL changed. Import the post to load its image and caption.');
};
function load(b64,config={},keepImport=false,mime='image/png'){
  if(!/^image\/(png|jpeg|gif|webp|bmp|avif)$/.test(mime))throw Error('Unsupported browser image type.');
  imageData=b64;original='data:'+mime+';base64,'+b64;
  if(!keepImport){imported=null;query('#importImages').hidden=true;query('#importImage').replaceChildren();}
  query('#agent').checked=config.reader==='agent';query('#strictOnly').checked=Boolean(config.strict_only);query('#calendar').checked=config.reader==='calendar';query('#automatic').checked=Boolean(config.auto_layout||config.reader==='bars');
  query('#sameMetric').checked=Boolean(config.assume_shared_daily_revenue);query('#fullMonth').checked=Boolean(config.assume_full_month);
  query('#sourceUrl').value=config.source||config.post_url||'';query('#postCaption').value=config.post_text||'';
  query('#evidenceMode').value=config.evidence_profile_url?'profile':config.discover_evidence?'discover':'none';query('#profileUrl').value=config.evidence_profile_url||'';query('#profileText').value=config.evidence_profile_text||'';
  query('#kind').value=config.kind||'auto';query('#scale').value=config.scale||'unknown';query('#config').value=JSON.stringify(config,null,2);query('#coords').textContent='No point selected';
  sourceLink(query('#sourceUrl').value);readerView();invalidate('Chart loaded. Check the evidence before running.');
}
query('#upload').onchange=async e=>{
  const f=e.target.files[0];if(!f)return;invalidate('Loading image…');const token=revision,r=new FileReader();
  r.onload=()=>{if(token!==revision)return;try{load(String(r.result).split(',')[1],{reader:'agent'},false,String(r.result).slice(5).split(';')[0]);}catch(e){query('#status').textContent=e.message;}};r.onerror=()=>{if(token===revision)query('#status').textContent='Could not read this image.';};r.readAsDataURL(f);
};
const examples={
  comparison:{url:'/api/comparison-example',description:'Synthetic revenue curves with two disclosed totals. A shared linear axis and daily positions are hypotheses, not independently verified facts.'},
  automatic:{url:'/api/automatic-example',description:'Synthetic bar card: locate the two printed labels and recover missing amounts under a supplied linear-scale assumption.'},
  example:{url:'/api/example',description:'Synthetic line with two supplied endpoint anchors and a linear-scale assumption. Interior values are not supplied.'}
};
query('#exampleChoice').onchange=()=>{query('#exampleDescription').textContent=examples[query('#exampleChoice').value].description;invalidate('Load the selected experiment to inspect it.');};
query('#loadExample').onclick=async()=>{
  invalidate('Loading synthetic example…');const token=revision;
  try{const r=await fetch(examples[query('#exampleChoice').value].url),d=await r.json();if(token!==revision)return;if(!r.ok)throw Error(d.error||'Example unavailable');load(d.image,d.config);}
  catch(e){if(token===revision)query('#status').textContent=e.message;}
};
function selectImported(){
  const item=imported.images[Number(query('#importImage').value)],p=imported.post;
  load(item.image,{reader:'agent',source:p.url,post_text:p.text||'',post_date:p.created_at},true,item.mime_type||'image/png');
  query('#status').textContent=`Imported public post with ${imported.images.length} image(s). Review its caption and source before recovery.`+(imported.errors?.length?' Some media could not be collected.':'');
}
query('#importImage').onchange=selectImported;
query('#importPost').onclick=async()=>{
  const url=query('#importUrl').value.trim();if(!url){query('#status').textContent='Enter an original public X post URL.';return;}
  invalidate('Fetching the public post and its images…');const token=revision;query('#importPost').disabled=true;
  try{
    const r=await fetch('/api/import-post',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})}),d=await r.json();
    if(token!==revision)return;if(!r.ok)throw Error(d.error||'Public post unavailable');
    imported=d;query('#importImage').replaceChildren(...d.images.map((_,i)=>new Option('Image '+(i+1),String(i))));query('#importImages').hidden=d.images.length<2;selectImported();
  }catch(e){if(token===revision)query('#status').textContent=e.message;}
  finally{query('#importPost').disabled=false;}
};
function pointLabel(r,s,i){
  const assignment=r.date_assignment||r.correspondence?.date_assignment,p=s.points[i];
  if(assignment==='month_day_proposed_year_unknown')return s.id+' / display x '+p.month_day+' (proposed)';
  if(assignment==='unassigned'||assignment==='proposed_unverified')return 'Position '+(100*(p.x_fraction??i/Math.max(1,s.points.length-1))).toFixed(1)+'%';
  if(p.date)return p.date;
  if(p.x_fraction!=null)return 'Position '+(100*p.x_fraction).toFixed(1)+'%';
  const l=r.calendar?.layout;
  if(l)return `${l.year}-${String(l.month).padStart(2,'0')}-${String(i+1).padStart(2,'0')}${r.correspondence?.status==='matched'?'':' (proposed)'}`;
  return r.visual_evidence?.binding?.labels?.[i]||s.id+' / '+i;
}
function evidenceView(r){
  const el=query('#evidenceDecisions');el.replaceChildren();
  if(r.agent)paragraph(`Automatic investigation: ${r.agent.strict_candidates} strict candidate(s), ${r.agent.conditional_candidates} conditional candidate(s). All reader attempts are retained in the evidence JSON.`);
  for(const reason of r.reasons||[])paragraph(reason);
  for(const assumption of r.assumptions||[])paragraph('Assumption: '+assumption);
  if(r.evidence_strength==='two_totals_unchecked')paragraph('Two period totals fit one shared linear axis. Scale, aggregation, daily counts and curve identities remain hypotheses. Independent numerical checking values: 0. Month/day labels describe displayed x positions; actual dates for the previous period and the year remain unassigned.');
  if(r.evidence_strength==='caption_and_headline_unchecked'){
    paragraph(`Caption claim: “${r.caption_claim?.quote||''}”`);
    if(r.status==='conditional_calibration')paragraph(`Read headline: ${r.headline?.text||'unresolved'}. The zero baseline is inferred from the caption. Independent checking values: ${r.independent_checking_values??0}.`);
    else paragraph('The caption hypothesis was withheld. No monetary estimates were returned by this attempt.');
  }
  if(r.checking)paragraph(`${r.checking.count} unused checking dates: ${(r.checking.nmae*100).toFixed(2)}% error relative to the observed range; ${(r.checking.interval_coverage*100).toFixed(0)}% interval coverage. These values test the proposed match; they do not independently establish the source’s truth.`);
  if(r.profile_source)paragraph('Public profile: '+r.profile_source);
  if(r.daily_recovery?.length)paragraph(`${r.daily_recovery.length} daily plateau estimates are available in the daily CSV. Dates are proposed under the recorded step convention; the raw trace CSV retains every measured curve column.`);
  if(r.calendar){
    paragraph(`${r.calendar.observations.length} monetary calendar cells read consistently. ${r.correspondence?.status==='matched'?'Correspondence accepted under the recorded assumptions.':'The calendar-to-curve correspondence needs review.'}`);
    for(const reason of r.correspondence?.reasons||[])paragraph(reason);
    for(const assumption of r.correspondence?.assumptions||[])paragraph((r.status==='conditional_calibration'?'Inferred':'Supplied')+' assumption: '+assumption);
    if(r.calendar.observations.length){const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Inspect the read calendar amounts';details.append(summary);paragraph(r.calendar.observations.map(o=>`${o.date}: ${o.text||o.value}`).join(' · '),details);el.append(details);}
  }
  for(const h of r.hypothesis_evaluation?.hypotheses||[])paragraph(h.id.replaceAll('_',' ')+': '+h.status.replaceAll('_',' ')+(h.check?` · ${h.fit_observations} fitting cells, ${h.check_observations} unused checking cells · ${(h.check.nmae*100).toFixed(2)}% checking error. Checking cells are from the same image.`:' · '+(h.reasons||[]).join(' ')));
  if(r.correspondence?.date_label_audit?.status==='label_centers_disagree')paragraph('Date-label positions disagree with the proposed full-month spacing. Plot dates remain unassigned.');
  const binding=r.evidence_binding;
  for(const d of binding?.decisions||[]){
    const claim=binding.claims?.find(c=>c.id===d.claim_id);
    const p=paragraph((d.status==='accepted'?'Used':'Not used')+' · '+(d.period||'Period unknown')+' · '+(claim?.quote||'')+' · '+(d.status==='accepted'?'Identity, metric, currency and date matched.':(d.reasons||[]).map(x=>x.replaceAll('_',' ')).join('; ')));
    if(/^https?:\/\//i.test(d.source||'')){const a=document.createElement('a');a.href=d.source;a.textContent='Source';a.target='_blank';a.rel='noreferrer';p.append(document.createTextNode(' '),a);}
  }
  const visual=r.visual_evidence?.binding;
  for(const d of visual?.decisions||[]){const used=d.status==='accepted'&&visual.anchors?.some(a=>a.point_index===d.point_index);paragraph((used?'Read as calibration evidence':'Not used')+' · '+(d.period_label||'Bar layout')+' · '+(d.text||d.reason||'Review required'));}
  if(!el.children.length)paragraph('No automatic evidence matches. Inspect the trace and supplied anchors.');
}
function renderResult(r){
  result=r;evidenceView(r);benchmarkView();overlay='data:image/png;base64,'+r.overlay;showingOverlay=true;draw(overlay);query('#toggle').textContent='Show original';
  const recoveries=r.recovery||[],series=r.geometry?.series||[],unchecked=r.status==='conditional_calibration'&&r.evidence_strength==='caption_and_headline_unchecked';
  const uncheckedTotals=r.status==='conditional_calibration'&&r.evidence_strength==='two_totals_unchecked';
  query('#stage').textContent=unchecked?'Unchecked caption hypothesis':uncheckedTotals?'Unchecked totals hypothesis':r.status==='conditional_calibration'?'Conditional hypothesis':r.status==='calibrated'?'Conditionally calibrated':recoveries.some(x=>x.status==='bounded_only')?'Ranges only':'Evidence needed';
  query('#seriesCount').textContent=series.length;query('#pointCount').textContent=series.reduce((n,s)=>n+s.points.length,0);
  let message=(r.reasons||[]).concat(recoveries.map(x=>(x.series||'Series')+': '+(x.reason||'Values calibrated under the recorded evidence and assumptions.'))).join('\n')||'No supported calibration. Inspect the reader evidence and extracted geometry.';
  if(unchecked)message='Unchecked caption hypothesis: zero history is inferred from the first-customer claim and the MRR headline is assumed to be the endpoint. No independent numerical checks; dates remain unassigned.';
  else if(uncheckedTotals)message='Unchecked shared-axis hypothesis: two period sums determine a linear scale under the recorded assumptions. No independent numerical checks. Month/day positions are proposed; the year is unknown.';
  else if(r.status==='conditional_calibration')message='Conditional reconstruction from an inferred evidence match. Review the correspondence assumptions and checking values before using this estimate.';
  query('#status').textContent=message;
  query('#trace').textContent=JSON.stringify({trace:r.trace,reasons:r.reasons,warnings:r.geometry?.warnings,assumptions:r.assumptions||recoveries.map(x=>x.assumptions),date_assignment:r.date_assignment||r.correspondence?.date_assignment},null,2);
  const body=query('#rows');body.replaceChildren();
  series.forEach((s,j)=>{
    const cal=recoveries.find(c=>c.series===s.id)||recoveries[j]||{};
    s.points.forEach((p,i)=>{const tr=document.createElement('tr');[pointLabel(r,s,i),Number(p.y).toFixed(1),fmt(cal.values?.[i]),cal.lower?`${fmt(cal.lower[i])} – ${fmt(cal.upper?.[i])}`:'—'].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td);});body.append(tr);});
  });
  if(!series.length){const row=body.insertRow();const cell=row.insertCell();cell.colSpan=4;cell.textContent='No supported geometry from this reader.';}
  for(const id of ['csv','json','toggle'])query('#'+id).disabled=false;
  query('#dailyCsv').hidden=!r.daily_csv;query('#dailyCsv').disabled=!r.daily_csv;
}
function selectResult(id){
  const v=bundle.agent_views.find(v=>v.id===id);if(!v)return;
  renderResult({...v.result,overlay:v.overlay,csv:v.csv,daily_csv:v.daily_csv,selected_view:v.id,agent:bundle.agent,agent_evidence:bundle.agent_evidence,agent_views:bundle.agent_views,trace:[...(v.result.trace||[]),...(bundle.agent?.steps||[])]});
}
query('#resultChoice').onchange=()=>selectResult(query('#resultChoice').value);
function receiveResult(r){
  bundle=r;const views=r.agent_views||[];query('#resultControls').hidden=!views.length;
  query('#resultChoice').replaceChildren(...views.map(v=>new Option(`${names[v.reader]||v.reader} · ${v.status==='conditional_calibration'&&v.result.evidence_strength==='caption_and_headline_unchecked'?'unchecked caption hypothesis':v.status.replaceAll('_',' ')}`,v.id)));
  if(views.length){query('#resultChoice').value=r.selected_view;selectResult(r.selected_view);}else renderResult(r);
}
query('#canvas').onclick=e=>{const c=e.target,b=c.getBoundingClientRect(),x=(e.clientX-b.left)*c.width/b.width,y=(e.clientY-b.top)*c.height/b.height;query('#coords').textContent=`x ${x.toFixed(1)} · y ${y.toFixed(1)} · horizontal coordinate ${(-x).toFixed(1)}`;};
query('#analyze').onclick=async()=>{
  if(!imageData){query('#status').textContent='Load a chart first.';return;}
  const btn=query('#analyze');let token=revision;
  try{
    const config=JSON.parse(query('#config').value);if(!config||Array.isArray(config)||typeof config!=='object')throw Error('Configuration must be a JSON object.');
    config.reader=readingMode();config.strict_only=query('#strictOnly').checked;config.auto_layout=config.reader==='bars';config.assume_shared_daily_revenue=query('#sameMetric').checked;config.assume_full_month=query('#fullMonth').checked;config.kind=query('#kind').value;config.scale=config.reader==='agent'?'unknown':query('#scale').value;
    config.source=query('#sourceUrl').value.trim();config.post_url=config.source;
    if(config.reader==='agent'){
      config.post_text=query('#postCaption').value;config.discover_evidence=!config.strict_only&&query('#evidenceMode').value==='discover';
      delete config.evidence_profile_url;delete config.evidence_profile_text;
      if(!config.strict_only&&query('#evidenceMode').value==='profile'){
        if(!query('#profileUrl').value.trim())throw Error('Enter the public profile URL.');
        config.evidence_profile_url=query('#profileUrl').value.trim();config.evidence_profile_text=query('#profileText').value;
      }
    }
    invalidate('Reading the image and checking its evidence…');token=revision;btn.disabled=true;query('#stage').textContent='Investigating';
    const response=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:imageData,config})}),r=await response.json();
    if(token!==revision)return;if(!response.ok)throw Error(r.error||'Recovery failed.');receiveResult(r);
  }catch(e){if(token===revision){query('#status').textContent=e.message;query('#stage').textContent='Review needed';}}
  finally{btn.disabled=false;}
};
query('#toggle').onclick=()=>{showingOverlay=!showingOverlay;draw(showingOverlay?overlay:original);query('#toggle').textContent=showingOverlay?'Show original':'Show detected marks';};
function download(content,name,type){const u=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),500);}
query('#csv').onclick=()=>{if(result)download(result.csv,'recovered-chart.csv','text/csv');};
query('#dailyCsv').onclick=()=>{if(result?.daily_csv)download(result.daily_csv,'recovered-daily-estimates.csv','text/csv');};
query('#json').onclick=()=>{
  if(!result)return;
  const r={...result};delete r.overlay;delete r.csv;delete r.daily_csv;
  if(r.agent_views)r.agent_views=r.agent_views.map(({overlay,csv,daily_csv,...view})=>view);
  download(JSON.stringify(r,null,2),'chart-evidence.json','application/json');
};
fetch('/api/benchmark').then(r=>r.json()).then(r=>{benchmarks=r;benchmarkView();}).catch(()=>{});
readerView();
