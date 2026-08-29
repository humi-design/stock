/* Humisense 3-minute guided demo orchestration.

The presenter can drive the full journey with a single click per stage:
reconciliation → exceptions → hero case → investigation → evidence →
recommendation → approval → resolution → ROI.

Attach the guided-demo section by including the "wizard" template block on
the dashboard page.
*/
(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  async function postJSON(url, body) {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    return res.json();
  }

  // Guided demo stage deck
  const STAGES = [
    { id: 'load',     title: '1 · Load synthetic data',     icon: 'database' },
    { id: 'recon',    title: '2 · Run reconciliation',      icon: 'git-compare' },
    { id: 'exceptions', title: '3 · Open exception queue', icon: 'list-checks' },
    { id: 'case',     title: '4 · Open hero case #82931',   icon: 'folder-open' },
    { id: 'invest',   title: '5 · Humisense investigation', icon: 'bot' },
    { id: 'evidence', title: '6 · Show evidence',           icon: 'file-search' },
    { id: 'recommend',title: '7 · Show recommendation',     icon: 'sparkles' },
    { id: 'approve',  title: '8 · Human approval',          icon: 'shield-check' },
    { id: 'resolve',  title: '9 · Resolve case',            icon: 'badge-check' },
    { id: 'roi',      title: '10 · Show ROI',               icon: 'trending-up' },
  ];

  const PLAYBACK = {
    load: async () => { await postJSON('/start-demo', {}); },
    recon: async () => { window.location.href = '/dashboard'; },
    exceptions: async () => { window.location.href = '/exceptions'; },
    case: async () => { window.location.href = '/cases/CASE%20%2382931'; },
    invest: async () => {
      const ref = 'CASE #82931';
      await postJSON(`/cases/${encodeURIComponent(ref)}/investigate`, {});
      window.location.href = '/cases/' + encodeURIComponent(ref) + '#investigation';
    },
    evidence: async () => { window.location.href = '/cases/CASE%20%2382931#evidence'; },
    recommend: async () => { window.location.href = '/cases/CASE%20%2382931#resolution'; },
    approve: async () => { window.location.href = '/cases/CASE%20%2382931#resolution'; },
    resolve: async () => { window.location.href = '/cases/CASE%20%2382931#resolution'; },
    roi: async () => { window.location.href = '/roi'; },
  };

  function buildWizard() {
    const host = $('#demo-wizard-host');
    if (!host) return;
    host.innerHTML = `
      <section class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm p-6 mb-8">
        <div class="flex items-center justify-between flex-wrap gap-3 mb-4">
          <div>
            <h2 class="font-extrabold text-lg flex items-center gap-2"><i data-lucide="play-circle" class="lucide w-5 h-5 text-indigo-500"></i> Start 3-Minute Demo</h2>
            <p class="text-sm text-slate-500">The presenter drives each stage — pause anywhere.</p>
          </div>
          <button id="wizard-step" class="btn-primary"><i data-lucide="arrow-right-circle" class="lucide w-4 h-4"></i> Start</button>
        </div>
        <div id="wizard-stages" class="grid sm:grid-cols-2 lg:grid-cols-5 gap-2">
          ${STAGES.map((s, i) => `
            <div class="rounded-lg border ${i === 0 ? 'border-indigo-300 dark:border-indigo-500/40 bg-indigo-50/60 dark:bg-indigo-500/10' : 'border-slate-200 dark:border-slate-800'} px-3 py-2 text-[11px] font-semibold text-slate-600 dark:text-slate-300 flex items-center gap-2" data-stage="${s.id}">
              <i data-lucide="${s.icon}" class="lucide w-3.5 h-3.5 ${i === 0 ? 'text-indigo-500' : 'text-slate-400'}"></i>${s.title}
            </div>`).join('')}
        </div>
        <p class="text-[11px] text-slate-400 mt-3 font-medium">Demo is fully offline — no external AI calls.</p>
      </section>`;
    if (window.lucide) lucide.createIcons();

    let idx = 0;
    const btn = $('#wizard-step');
    const highlight = () => {
      $$('#wizard-stages [data-stage]').forEach((el, i) => {
        el.className = 'rounded-lg border px-3 py-2 text-[11px] font-semibold flex items-center gap-2 ' +
          (i === idx
            ? 'border-indigo-300 dark:border-indigo-500/40 bg-indigo-50/60 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300'
            : i < idx
              ? 'border-emerald-200 dark:border-emerald-500/30 bg-emerald-50/50 dark:bg-emerald-500/5 text-emerald-700 dark:text-emerald-300'
              : 'border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300');
      });
    };
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      const stage = STAGES[idx];
      btn.innerHTML = `<i data-lucide="loader" class="lucide w-4 h-4 animate-spin"></i> ${stage.title}`;
      if (window.lucide) lucide.createIcons();
      try { await PLAYBACK[stage.id](); } catch (e) { console.error(e); }
      idx = (idx + 1) % STAGES.length;
      const next = STAGES[idx];
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="arrow-right-circle" class="lucide w-4 h-4"></i> ${idx === 0 ? 'Restart' : next.title}`;
      highlight();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildWizard);
  } else {
    buildWizard();
  }
})();