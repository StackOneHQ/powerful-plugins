(() => {
  'use strict';
  const photo = '__CONCERT_PHOTO__';
  const variants = ['The poster', 'The box office'];
  const rows = [
    {device: 'Mobile', visits: [2000, 8000], orders: [40, 240]},
    {device: 'Desktop', visits: [8000, 2000], orders: [480, 140]}
  ];
  const chapters = ['The blind pick', 'The sales report', 'The device split', 'The test plan'];
  const rate = (row, i) => 100 * row.orders[i] / row.visits[i];
  const total = (field, i) => rows.reduce((sum, row) => sum + row[field][i], 0);
  const fmt = n => n.toLocaleString('en-GB');
  let mobileMix = 50;

  function setup() {
    document.body.classList.add('after-hours');
    document.documentElement.style.setProperty('--concert-photo', 'url("' + photo + '")');
    document.querySelector('.brand').innerHTML = '<i aria-hidden="true">↗</i> Tinder Artifact <span class="product-divider">/</span> <span class="product-type">Design duel</span>';
    document.querySelector('.mast-tools').innerHTML = '<span class="sample-label"><i></i> Simulated experiment</span>';
    $('deck-label').textContent = 'After Hours · Ticketing';
    $('deck-title').textContent = 'The ticket test';
    $('own-task').textContent = 'My decks ↗';
    document.title = 'The ticket test · After Hours';
    document.addEventListener('input', e => {
      if (e.target.id === 'duel-mix') {
        mobileMix = Number(e.target.value);
        $('mix-mobile').textContent = mobileMix + '% mobile';
        $('mix-rates').textContent = mixReadout();
      }
    });
  }

  function designs(d, r) {
    const previews = [
      '<span class="poster-art"><span class="event-top">London &nbsp; / &nbsp; Club night</span><strong>AFTER<br>HOURS<span>.</span></strong><span class="event-foot"><span>24 OCT &nbsp;·&nbsp; THE ARCH</span><b>Get tickets · £35 ↗</b></span></span>',
      '<span class="box-art"><span class="box-photo"><small>THE ARCH PRESENTS</small></span><span class="box-copy"><strong>After Hours</strong><span>Sat 24 Oct · 22:00</span><span class="stub-price">Entry <b>£35</b></span><b class="box-cta">Buy a ticket ↗</b></span></span>'
    ];
    return '<fieldset class="mock-pair"><legend class="sr-only">Pick the page you think sells more tickets</legend>' + d.options.map((o, i) => {
      const chosen = r.selected.includes(o.id);
      return '<label class="mock ' + (chosen ? 'picked' : '') + '"><input class="mock-input" type="radio" name="choice" value="' + o.id + '" ' + (chosen ? 'checked' : '') + ' aria-label="' + esc(o.label) + '" aria-describedby="design-description-' + i + '"><span class="sr-only" id="design-description-' + i + '">' + esc(o.detail) + '</span><span class="mock-frame" aria-hidden="true">' + previews[i] + '</span><span class="mock-caption"><i>' + 'AB'[i] + '</i><b>' + variants[i] + '</b><span class="select-mark" aria-hidden="true">' + (chosen ? '✓' : '') + '</span></span><small class="mock-tag">' + (o.rec ? 'Suggested first pick' : 'Ticket details first') + '</small></label>';
    }).join('') + '</fieldset>';
  }

  function scoreboard() {
    return '<section class="exhibit score"><div class="exhibit-head"><span>Box-office report</span><span>7 days</span></div><h3>Paid ticket orders</h3>' + variants.map((v, i) => {
      const orders = total('orders', i), visits = total('visits', i);
      return '<div class="score-line"><div><b>' + 'AB'[i] + ' / ' + v + '</b><span>' + (orders * 100 / visits).toFixed(1) + '% of ' + fmt(visits) + ' visits</span></div><strong>' + orders + '</strong><div class="score-track"><i style="width:' + (orders / total('orders', 0) * 100) + '%"></i></div></div>';
    }).join('') + '<small>One paid order per converting visit.</small></section>';
  }

  function mixReadout() {
    return [0, 1].map(i => 'AB'[i] + ' ' + ((mobileMix * rate(rows[0], i) + (100 - mobileMix) * rate(rows[1], i)) / 100).toFixed(1) + '%').join('   /   ');
  }

  function deviceSplit() {
    return '<section class="exhibit split"><div class="exhibit-head"><span>Conversion by device</span><span>Orders / visits</span></div><table><thead><tr><th scope="col">Device</th><th scope="col">A · Poster</th><th scope="col">B · Box office</th></tr></thead><tbody>' + rows.map(row => '<tr><th scope="row">' + row.device + '</th>' + [0,1].map(i => '<td><strong>' + rate(row, i) + '%</strong><small>' + fmt(row.orders[i]) + ' / ' + fmt(row.visits[i]) + '</small></td>').join('') + '</tr>').join('') + '</tbody></table><div class="mix"><label for="duel-mix">Try a shared audience mix</label><div><output id="mix-mobile" for="duel-mix">' + mobileMix + '% mobile</output><b id="mix-rates">' + mixReadout() + '</b></div><input id="duel-mix" type="range" min="0" max="100" step="5" value="' + mobileMix + '" aria-label="Mobile share of both audiences"><small>Modeled orders per 100 visits at this mix.</small></div></section>';
  }

  function outcome(i) {
    const d = definitions[i], r = record(d.id);
    return {d, r, status: group(d,r), labels: (d.options || []).filter(o => r.selected.includes(o.id)).map(o => o.label)};
  }
  function planPreview() {
    const next = outcome(2), hold = next.status === 'Apply' && next.r.selected.includes('option-3');
    if (next.status !== 'Apply') return '<section class="exhibit plan"><div class="exhibit-head">Test plan</div><h3>Design choice open</h3><p>Choose a next step on the previous card before the AI can use these guardrails.</p></section>';
    return '<section class="exhibit plan"><div class="exhibit-head">Experiment brief</div><h3>' + (hold ? 'Audit first.' : 'Run it again.') + '</h3><dl><div><dt>Your call</dt><dd>' + esc(next.labels.join(', ')) + '</dd></div><div><dt>' + (hold ? 'Audit scope' : 'Assignment') + '</dt><dd>' + (hold ? 'Trace campaign and device routing' : '1:1 within mobile and desktop') + '</dd></div><div><dt>Primary metric</dt><dd>Paid orders per eligible visit</dd></div></dl><small>Draft for the promoter · fictional event</small></section>';
  }

  function card(d,r) {
    const i = definitions.indexOf(d);
    const exhibits = [() => designs(d,r), scoreboard, deviceSplit, planPreview];
    const intros = [d.description,'Two pages, 10,000 visits each. The promoter wants one line for the morning report.','Desktop visitors bought more often. Page A received most of them. Compare each device, then try giving both pages the same audience.','Choose the guardrails the promoter should put in the experiment brief.'];
    const copy = i === 1 ? '<div class="headline-edit"><div><small>First draft</small><p>' + esc(d.before) + '</p></div><div><small>Proposed revision</small><p>' + esc(r.proposal) + '</p></div></div>' : '';
    const choice = i > 0 && d.options ? optionsHtml(d,r) : '';
    const warning = r.stale ? 'A prerequisite changed. Review this decision again.' : blocked(d,r);
    const notes = (r.notes ? '<p class="notice"><b>Your note</b> ' + esc(r.notes) + '</p>' : '') + (unfinished(r) ? '<p class="notice">Finish your note in Add info before approval.</p>' : '') + (warning ? '<p class="notice">' + esc(warning) + '</p>' : '') + (r.previousRevision ? '<p class="prior-choice"><b>Previous revision request</b> ' + esc(r.previousRevision) + '</p>' : '');
    return '<article class="card duel-card" id="decision-card"><header class="duel-heading"><span class="chapter">' + chapters[i] + '</span><h2 id="card-heading" tabindex="-1">' + esc(d.title) + '</h2><p>' + esc(intros[i]) + '</p></header><div class="duel-grid"><div class="visual-evidence">' + exhibits[i]() + '</div><div class="decision-side">' + copy + choice + '<div class="editor-note"><span>AI pick</span><p><b>' + esc(d.recommendation) + '</b> ' + esc(d.reason) + '</p></div>' + notes + '<p class="duel-scope"><b>On approval</b> ' + esc(d.action) + '</p><button id="evidence-btn">Inspect the evidence ↗</button>' + (r.intent === 'revise' && d.after !== undefined ? '<button id="new-proposal-btn">Add revised headline</button>' : '') + '</div></div><div class="drag-zone" id="drag-zone" aria-label="Swipe right to approve, left to dismiss, or up to add information"><div class="drag-grip"></div><strong id="drag-label">← Dismiss &nbsp; · &nbsp; ↑ Add info &nbsp; · &nbsp; Approve →</strong></div></article>';
  }

  function approvedLabel(i, fallback) {
    const v = outcome(i);
    return v.status === 'Apply' ? v.labels.join(', ') : fallback;
  }
  function ready() {
    return outcome(2).status === 'Apply';
  }
  function brief() {
    const lines = ['# After Hours · Experiment brief', '', 'Fictional event · Simulated observations · Draft for review', ''];
    for (const [i, d] of definitions.entries()) {
      const v = outcome(i);
      lines.push('## ' + chapters[i], v.status + ' — ' + d.title);
      if (v.status === 'Apply') lines.push(v.labels.length ? v.labels.join('; ') : v.r.proposal);
      if (v.r.notes) lines.push((v.status === 'Revise' ? 'Revision request: ' : 'Reviewer note: ') + v.r.notes);
      if (v.status === 'Apply' && i === 3) for(const o of d.options.filter(o => v.r.selected.includes(o.id))) lines.push('- ' + o.detail);
      lines.push('');
    }
    if (ready()) {
      lines.push('## Evidence', 'A had 520 paid orders from 10,000 visits. B had 380 from 10,000. At an equal device mix, the modeled rates are A 4% and B 5%. The initial assignment was observational.', '');
      const hold = outcome(2).r.selected.includes('option-3');
      lines.push('## Next step', hold ? 'Reconcile campaign routing, unique eligible visits, paid orders and device classification before designing a test.' : 'Prepare a 1:1 randomized comparison within each device type. Use paid orders per eligible visit as the primary metric. Size the sample and duration with a baseline and a minimum effect before launch.');
    }
    return lines.join('\n');
  }
  function verdict() {
    if (!ready()) return '<section class="verdict"><small>After Hours / Launch brief</small><h3>Your verdict is open.</h3><p>Approve a next step on the device-split card to make your share card.</p></section>';
    return '<section class="verdict"><small>After Hours / Your verdict</small><h3>' + esc(approvedLabel(2,'')) + '</h3><p>First pick: <b>' + esc(approvedLabel(0,'No prediction recorded')) + '</b></p><p>At the same 50/50 audience mix, the modeled conversion rates are <b>A 4% · B 5%</b>. The next step is yours.</p><div class="export-tools"><button id="save-verdict" class="primary">Save share card ↓</button><button id="save-plan">Download launch brief ↓</button><a id="blank-challenge" download="the-ticket-test.html">Get the blank challenge ↓</a></div><span id="export-status" role="status"></span></section>';
  }
  function download(blob,name) {
    if (!blob) throw Error('Export unavailable');
    const url=URL.createObjectURL(blob), link=document.createElement('a');
    link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
  }
  async function shareCard() {
    const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1200;
    const ctx=canvas.getContext('2d');
    ctx.fillStyle='#161614';ctx.fillRect(0,0,1080,1200);
    const img=new Image();img.src=photo;await img.decode();
    const cropHeight = img.naturalWidth * 480 / 1080;
    ctx.drawImage(img,0,(img.naturalHeight-cropHeight)/2,img.naturalWidth,cropHeight,0,0,1080,480);
    ctx.fillStyle='rgba(18,10,7,.34)';ctx.fillRect(0,0,1080,480);
    function line(text,x,y,font,color) { ctx.font=font;ctx.fillStyle=color;ctx.fillText(text,x,y,960); }
    line('AFTER HOURS  /  THE TICKET TEST',64,81,'bold 31px sans-serif','#fff6e8');
    line('Which page sells',64,280,'bold 96px sans-serif','#fff6e8');
    line('more tickets?',64,390,'bold 96px sans-serif','#fff6e8');
    line('MY FIRST PICK',64,560,'bold 24px monospace','#e0bbac');
    line(approvedLabel(0,'No prediction recorded'),64,639,'bold 55px sans-serif','#fff6e8');
    line('MY CALL AFTER THE DATA',64,735,'bold 24px monospace','#e0bbac');
    line(approvedLabel(2,''),64,811,'bold 55px sans-serif','#ff845f');
    line('Raw paid orders       A 520    B 380',64,932,'32px monospace','#fff6e8');
    line('Equal device mix      A 4%     B 5%',64,995,'32px monospace','#fff6e8');
    ctx.fillStyle='#8f7267';ctx.fillRect(64,1055,952,2);
    line('20,000 simulated visits · Observational first run',64,1125,'28px sans-serif','#f4dace');
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
    download(blob,'after-hours-my-verdict.png');
  }
  function bindVerdict() {
    if (!$('save-verdict')) return;
    $('save-plan').onclick=()=>download(new Blob([brief()+'\n'],{type:'text/markdown;charset=utf-8'}),'after-hours-launch-brief.md');
    $('save-verdict').onclick=async()=>{try{await shareCard();$('export-status').textContent='Share card saved as a PNG.';}catch{$('export-status').textContent='The image export failed. You can still download the brief.';}};
    $('blank-challenge').href=location.href.split(/[?#]/)[0];
  }
  globalThis.tinderPresentation={setup,card,verdict,bindVerdict};
})();
