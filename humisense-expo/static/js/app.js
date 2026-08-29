/* Humisense demo application logic */
(function () {
  'use strict';

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ---------------------------------------------------------------- //
  // Theme toggle
  // ---------------------------------------------------------------- //
  function applyTheme(theme) {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    $$('#theme-toggle .lucide').forEach(icon => icon.setAttribute('data-lucide', theme === 'dark' ? 'sun' : 'moon'));
    if (window.lucide) lucide.createIcons();
  }
  const savedTheme = localStorage.getItem('theme') || document.cookie.match(/theme=(\w+)/)?.[1] || 'light';
  applyTheme(savedTheme);
  $('#theme-toggle').addEventListener('click', () => {
    const next = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
    document.cookie = `theme=${next}; path=/; max-age=31536000`;
    localStorage.setItem('theme', next);
    applyTheme(next);
  });

  // ---------------------------------------------------------------- //
  // Utility
  // ---------------------------------------------------------------- //
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    return res.json();
  }

  // ---------------------------------------------------------------- //
  // Reconciliation runner (dashboard)
  // ---------------------------------------------------------------- //
  const RUNNER_STEPS = [
    ['Reading Bank Transactions...', 'bank'],
    ['Reading Broker Ledger...', 'broker'],
    ['Reading Settlement...', 'settlement'],
    ['Normalizing Records...', 'normalize'],
    ['Matching Records...', 'match'],
    ['Detecting Exceptions...', 'detect'],
  ];

  async function runReconciliation(files) {
    const runner = $('#recon-runner');
    if (!runner) return null;
    runner.classList.remove('hidden');
    const stepsEl = $('#recon-steps');
    stepsEl.innerHTML = '';
    for (const [label] of RUNNER_STEPS) {
      stepsEl.insertAdjacentHTML('beforeend', `<div class="step-item" data-step><i data-lucide="loader" class="lucide w-4 h-4 animate-spin"></i><span>${label}</span></div>`);
    }
    if (window.lucide) lucide.createIcons();
    const stepEls = $$('[data-step]', stepsEl);

    for (let i = 0; i < RUNNER_STEPS.length; i++) {
      await sleep(240);
      const el = stepEls[i];
      el.classList.add('active');
      el.innerHTML = `<i data-lucide="loader" class="lucide w-4 h-4 animate-spin"></i><span>${RUNNER_STEPS[i][0]}</span>`;
      if (window.lucide) lucide.createIcons();
      await sleep(420);
      el.classList.remove('active');
      el.classList.add('done');
      el.innerHTML = `<i data-lucide="circle-check" class="lucide w-4 h-4"></i><span>${RUNNER_STEPS[i][0]} ✓</span>`;
      if (window.lucide) lucide.createIcons();
    }

    let data;
    if (files) {
      const fd = new FormData();
      fd.append('bank', files.bank);
      fd.append('broker', files.broker);
      fd.append('settlement', files.settlement);
      const res = await fetch('/reconcile', { method: 'POST', body: fd });
      data = await res.json();
    } else {
      data = await postJSON('/reconcile', {});
    }

    if (!data.ok) {
      stepsEl.insertAdjacentHTML('beforeend', `<div class="step-item text-rose-600"><i data-lucide="circle-x" class="lucide w-4 h-4"></i><span>${data.error || 'Reconciliation failed'}</span></div>`);
      if (window.lucide) lucide.createIcons();
      return null;
    }

    const s = data.summary;
    stepsEl.insertAdjacentHTML('beforeend', `
      <div class="mt-3 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 px-4 py-3 font-bold text-emerald-700 dark:text-emerald-300 fade-in-up">
        <i data-lucide="badge-check" class="lucide w-5 h-5 inline"></i> RECONCILIATION COMPLETE
        <div class="text-xs font-medium mt-1 text-emerald-600 dark:text-emerald-300">
          ${s.processed.toLocaleString()} records · ${s.matched.toLocaleString()} matched · ${s.exceptions.toLocaleString()} exceptions
        </div>
      </div>`);
    if (window.lucide) lucide.createIcons();

    // Update stats
    const setV = (id, val) => { const el = $(id); if (el) el.textContent = val; };
    setV('#st-processed', s.processed.toLocaleString());
    setV('#st-matched', s.matched.toLocaleString());
    setV('#st-exceptions', s.exceptions.toLocaleString());

    stepsEl.insertAdjacentHTML('beforeend', `
      <div class="mt-4"><a href="/exceptions" class="btn-primary"><i data-lucide="list-checks" class="lucide w-4 h-4"></i> View Exceptions</a>
      <button class="btn-ghost ml-2" id="btn-open-hero"><i data-lucide="star" class="lucide w-4 h-4"></i> Open Hero Case #82931</button></div>`);
    if (window.lucide) lucide.createIcons();
    const heroBtn = $('#btn-open-hero');
    if (heroBtn) heroBtn.addEventListener('click', () => {
      window.location.href = '/cases/' + encodeURIComponent('CASE #82931');
    });

    await sleep(600);
    runner.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return data;
  }

  const btnRun = $('#btn-run-recon');
  if (btnRun) btnRun.addEventListener('click', () => runReconciliation(null));

  const btnDemoData = $('#btn-use-demo');
  if (btnDemoData) btnDemoData.addEventListener('click', () => runReconciliation(null));

  // File uploads
  const PENDING_FILES = {};
  $$('[data-upload]').forEach(input => {
    input.addEventListener('change', () => {
      const key = input.dataset.upload;
      const label = $(`label[data-label="${key}"]`) || input.closest('label');
      if (input.files.length) {
        PENDING_FILES[key] = input.files[0];
        input.closest('label').classList.add('has-file');
        input.closest('label').innerHTML = `<i data-lucide="check" class="lucide w-4 h-4"></i> ${input.files[0].name}`;
      } else {
        delete PENDING_FILES[key];
      }
      if (window.lucide) lucide.createIcons();
      const names = Object.keys(PENDING_FILES);
      if (names.length === 3) {
        if (btnRun) btnRun.innerHTML = `<i data-lucide="play" class="lucide w-4 h-4"></i> Run on Uploaded Data`;
        if (btnRun) btnRun.classList.add('btn-primary');
        btnRun.onclick = () => runReconciliation(PENDING_FILES);
      } else if (names.length > 0 && names.length < 3) {
        if (btnRun) btnRun.innerHTML = `<i data-lucide="files" class="lucide w-4 h-4"></i> Upload All 3 Files (${names.length}/3)`;
        if (btnRun) btnRun.disabled = true;
      } else {
        if (btnRun) { btnRun.innerHTML = `<i data-lucide="play" class="lucide w-4 h-4"></i> Run Reconciliation`; btnRun.disabled = false; btnRun.onclick = () => runReconciliation(null); }
      }
    });
  });

  // ---------------------------------------------------------------- //
  // One-click demo + reset
  // ---------------------------------------------------------------- //
  const btnReset = $('#btn-reset');
  if (btnReset) btnReset.addEventListener('click', async () => {
    btnReset.disabled = true;
    await postJSON('/reset', {});
    window.location.href = '/';
  });

  // ---------------------------------------------------------------- //
  // Severity filters (exceptions page)
  // ---------------------------------------------------------------- //
  $$('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      window.location.href = '/exceptions?severity=' + pill.dataset.filter;
    });
  });

  // Clickable case rows
  $$('.case-row').forEach(row => {
    row.addEventListener('click', () => { window.location.href = row.dataset.href; });
  });

  // ---------------------------------------------------------------- //
  // Case detail: tabs
  // ---------------------------------------------------------------- //
  const tabs = $$('.case-tab');
  if (tabs.length) {
    tabs.forEach(tab => tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      $$('.tab-panel').forEach(p => {
        p.classList.toggle('hidden', p.dataset.panel !== tab.dataset.tab);
        if (!p.classList.contains('hidden')) p.classList.add('fade-in-up');
      });
      if (window.lucide) lucide.createIcons();
    }));
  }

  // ---------------------------------------------------------------- //
  // Investigation
  // ---------------------------------------------------------------- //
  const btnInvestigate = $('#btn-investigate');
  if (btnInvestigate) {
    const INVEST_STEPS = [
      ['Understanding exception', 'search'],
      ['Retrieving related records', 'database'],
      ['Comparing financial records', 'git-compare'],
      ['Searching evidence', 'file-search'],
      ['Determining probable root cause', 'brain'],
      ['Generating recommendation', 'sparkles'],
    ];
    btnInvestigate.addEventListener('click', async () => {
      $('#investigate-empty').classList.add('hidden');
      const running = $('#investigate-running');
      running.classList.remove('hidden');
      const stepsEl = $('#investigate-steps');
      stepsEl.innerHTML = '';
      INVEST_STEPS.forEach(([label]) => {
        stepsEl.insertAdjacentHTML('beforeend', `<div class="step-item" data-istep><i data-lucide="loader" class="lucide w-4 h-4 animate-spin"></i><span>${label}</span></div>`);
      });
      if (window.lucide) lucide.createIcons();
      const stepEls = $$('[data-istep]', stepsEl);
      for (let i = 0; i < INVEST_STEPS.length; i++) {
        await sleep(280);
        stepEls[i].classList.add('active');
        await sleep(360);
        stepEls[i].classList.remove('active');
        stepEls[i].classList.add('done');
        stepEls[i].innerHTML = `<i data-lucide="circle-check" class="lucide w-4 h-4"></i><span>${INVEST_STEPS[i][0]} ✓</span>`;
        if (window.lucide) lucide.createIcons();
      }
      const data = await postJSON(`/cases/${encodeURIComponent(window.CASE_REF)}/investigate`, {});
      running.classList.add('hidden');
      const resultEl = $('#investigate-result');
      resultEl.classList.remove('hidden');
      $('#invest-what').textContent = data.what_happened;
      $('#invest-cause').textContent = data.root_cause;
      $('#invest-rationale').innerHTML = (data.rationale || '').replace(/·/g, '<span class="px-1.5 text-slate-300 dark:text-slate-600">·</span>');
      $('#conf-bar').style.width = data.confidence + '%';
      $('#conf-value').textContent = data.confidence + '%';
      $('#rec-text').textContent = data.recommendation;
      $('#provider-tag').textContent = (data.provider === 'live') ? 'LIVE AI' : 'DEMO AI';
      if (data.fallback) {
        document.querySelectorAll('#investigate-result .badge-warn').forEach(el => el.classList.remove('hidden'));
      }
      // Enable resolution actions
      ['#btn-approve', '#btn-reject', '#btn-escalate'].forEach(s => { const el = $(s); if (el) el.disabled = false; });
      // Update statuses
      const badge = $('#case-status-badge');
      if (badge) { badge.textContent = 'Investigated'; badge.className = 'badge ' + (window.status_cls ? window.status_cls('Investigated') : 'badge-info'); }
      const line = $('#case-status-line');
      if (line) line.innerHTML = '<span class="inline-flex items-center gap-1.5 text-amber-600 dark:text-amber-400"><i data-lucide="clock" class="lucide w-4 h-4"></i> INVESTIGATION COMPLETE — AWAITING HUMAN DECISION</span>';
      if (window.lucide) lucide.createIcons();
      resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // ---------------------------------------------------------------- //
  // Approval modal + resolution
  // ---------------------------------------------------------------- //
  function openModal(caseRef, amount, recommendation) {
    $('#modal-root').innerHTML = `
      <div class="modal-overlay">
        <div class="modal-card fade-in-up">
          <div class="flex items-start justify-between mb-1">
            <h3 class="text-lg font-extrabold">Approve Action?</h3>
            <button class="btn-ghost p-1" id="modal-close"><i data-lucide="x" class="lucide w-4 h-4"></i></button>
          </div>
          <p class="text-sm text-slate-500 mb-4">Humisense recommends:</p>
          <div class="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3 text-sm font-semibold mb-3">${recommendation}</div>
          <div class="grid grid-cols-3 gap-2 text-sm mb-5">
            <div><div class="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Amount</div><div class="font-extrabold">${amount}</div></div>
            <div><div class="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Risk</div><div class="font-bold"><span class="badge badge-high">HIGH</span></div></div>
            <div><div class="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Approval</div><div class="font-bold"><span class="badge badge-warn">REQUIRED</span></div></div>
          </div>
          <p class="text-xs text-slate-500 mb-5 flex items-center gap-1.5"><i data-lucide="shield" class="lucide w-4 h-4 text-indigo-500"></i>This action requires human approval. Humisense will not execute it automatically.</p>
          <div class="flex gap-2">
            <button id="modal-confirm" class="btn-primary flex-1 justify-center"><i data-lucide="shield-check" class="lucide w-4 h-4"></i> Confirm Approval</button>
            <button id="modal-cancel" class="btn-secondary">Cancel</button>
          </div>
        </div>
      </div>`;
    if (window.lucide) lucide.createIcons();
    $('#modal-close').addEventListener('click', closeModal);
    $('#modal-cancel').addEventListener('click', closeModal);
    $('#modal-confirm').addEventListener('click', async () => {
      closeModal();
      await executeResolution(caseRef, recommendation);
    });
    document.querySelector('.modal-overlay').addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-overlay')) closeModal();
    });
  }
  function closeModal() { $('#modal-root').innerHTML = ''; }

  async function executeResolution(caseRef, recommendation) {
    $('#resolution-empty').classList.add('hidden');
    const running = $('#resolution-running');
    running.classList.remove('hidden');
    const stepsEl = $('#resolution-steps');
    const RES_STEPS = [
      ['Validate settlement...', 'check'],
      ['Prepare ledger resolution...', 'file-edit'],
      ['Execute simulated action...', 'play'],
      ['Verify result...', 'badge-check'],
    ];
    stepsEl.innerHTML = '';
    RES_STEPS.forEach(([label]) => stepsEl.insertAdjacentHTML('beforeend', `<div class="step-item" data-rstep><i data-lucide="loader" class="lucide w-4 h-4 animate-spin"></i><span>${label}</span></div>`));
    if (window.lucide) lucide.createIcons();
    const stepEls = $$('[data-rstep]', stepsEl);
    for (let i = 0; i < RES_STEPS.length; i++) {
      await sleep(300);
      stepEls[i].classList.add('active');
      await sleep(380);
      stepEls[i].classList.remove('active');
      stepEls[i].classList.add('done');
      stepEls[i].innerHTML = `<i data-lucide="circle-check" class="lucide w-4 h-4"></i><span>${RES_STEPS[i][0]} ✓</span>`;
      if (window.lucide) lucide.createIcons();
    }
    // Record human approval + resolve on the server
    await postJSON(`/cases/${encodeURIComponent(caseRef)}/approved`, {});
    await sleep(200);
    const data = await postJSON(`/cases/${encodeURIComponent(caseRef)}/action`, { action: 'approve' });
    running.classList.add('hidden');
    $('#resolution-done').classList.remove('hidden');
    $('#res-text').textContent = recommendation || 'Settlement ledger updated.';
    // Audit trail refresh
    await refreshAudit();
    // Update status
    const badge = $('#case-status-badge');
    if (badge) { badge.textContent = 'Resolved'; badge.className = 'badge badge-success'; }
    const line = $('#case-status-line');
    if (line) line.innerHTML = '<span class="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400"><i data-lucide="circle-check" class="lucide w-4 h-4"></i> CASE RESOLVED — FULLY AUDITED</span>';
    // Hide action buttons
    const actions = $('#resolution-actions');
    if (actions) actions.innerHTML = '<span class="badge badge-success text-sm"><i data-lucide="circle-check" class="lucide w-4 h-4"></i> Resolution executed · Simulated</span>';
    if (window.lucide) lucide.createIcons();
    $('#resolution-done').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  const btnApprove = $('#btn-approve');
  if (btnApprove) btnApprove.addEventListener('click', () => {
    // Amount shown in the case header (e.g. ₹184,500)
    const amountText = ($('#resolution-empty .font-bold') || {}).textContent
      ? $('#resolution-empty .font-bold').textContent.trim()
      : '';
    openModal(window.CASE_REF, amountText, $('#rec-text').textContent.trim());
  });

  const btnReject = $('#btn-reject');
  if (btnReject) btnReject.addEventListener('click', async () => {
    await postJSON(`/cases/${encodeURIComponent(window.CASE_REF)}/action`, { action: 'reject' });
    window.location.reload();
  });
  const btnEscalate = $('#btn-escalate');
  if (btnEscalate) btnEscalate.addEventListener('click', async () => {
    await postJSON(`/cases/${encodeURIComponent(window.CASE_REF)}/action`, { action: 'escalate' });
    window.location.reload();
  });

  async function refreshAudit() {
    const url = '/cases/' + encodeURIComponent(window.CASE_REF);
    const res = await fetch(url);
    const html = await res.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const newList = doc.querySelector('#audit-list');
    if (newList) $('#audit-list').innerHTML = newList.innerHTML;
  }

  // ---------------------------------------------------------------- //
  // ROI calculator
  // ---------------------------------------------------------------- //
  const btnCalc = $('#btn-calc');
  if (btnCalc) {
    const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 1 });
    btnCalc.addEventListener('click', async () => {
      const payload = {
        monthly_exceptions: $('#in-monthly').value,
        handling_minutes: $('#in-handling').value,
        hourly_cost: $('#in-hourly').value,
        ai_rate: $('#in-rate').value,
        review_minutes: $('#in-review').value,
      };
      const data = await postJSON('/roi/calculate', payload);
      if (!data.ok) return;
      const e = data.estimate;
      $('#r-hours').textContent = fmt(e.current_manual_hours) + ' hrs';
      $('#r-released').textContent = fmt(e.potential_hours_released) + ' hrs';
      $('#r-cost').textContent = '₹' + fmt(e.monthly_operational_cost);
      $('#r-capacity').textContent = fmt(e.capacity_released) + ' hrs';
      $('#r-annual').textContent = fmt(e.annual_capacity) + ' hrs';
    });
  }

  // ---------------------------------------------------------------- //
  // Settings: test connection
  // ---------------------------------------------------------------- //
  const btnTest = $('#btn-test-conn');
  if (btnTest) btnTest.addEventListener('click', async () => {
    const resEl = $('#conn-result');
    resEl.classList.remove('hidden');
    resEl.textContent = 'Testing connection…';
    resEl.className = 'text-sm font-semibold mt-3 text-slate-500';
    const fd = new FormData();
    fd.append('ai_provider', $('#ai-provider').value);
    fd.append('ai_base_url', document.querySelector('[name="ai_base_url"]').value);
    fd.append('ai_model', document.querySelector('[name="ai_model"]').value);
    fd.append('ai_api_key', document.querySelector('[name="ai_api_key"]').value);
    const res = await fetch('/settings/test', { method: 'POST', body: fd });
    const data = await res.json();
    resEl.textContent = (data.ok ? '✓ ' : '✗ ') + data.message;
    resEl.className = 'text-sm font-semibold mt-3 ' + (data.ok ? 'text-emerald-600' : 'text-rose-600');
  });

  // ---------------------------------------------------------------- //
  // Landing scroll cue (optional)
  // ---------------------------------------------------------------- //
})();