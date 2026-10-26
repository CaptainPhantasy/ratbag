'use strict';

/* Browser-native control surface. Server responses are the source of run state.
 * Inline line icons follow Lucide geometry; see assets/Lucide-LICENSE.txt.
 * Credentials are never written to browser storage or included in URLs. */
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const ICONS = {
    help: [['circle',{cx:12,cy:12,r:9}],['path',{d:'M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3m.1 4h.01'}]],
    menu: [['path',{d:'M4 6h16M4 12h16M4 18h16'}]],
    compass: [['circle',{cx:12,cy:12,r:9}],['path',{d:'m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z'}]],
    book: [['path',{d:'M4 3h12a3 3 0 0 1 3 3v15H6a3 3 0 0 1-3-3V4a1 1 0 0 1 1-1Zm-1 15a3 3 0 0 1 3-3h13M7 7h7M7 10h5'}]],
    sliders: [['path',{d:'M4 7h7m4 0h5M4 17h3m4 0h9'}],['circle',{cx:13,cy:7,r:2}],['circle',{cx:9,cy:17,r:2}]],
    'arrow-up-right': [['path',{d:'M7 17 17 7M7 7h10v10'}]],
    refresh: [['path',{d:'M3 10a9 9 0 0 1 15.4-6.4L21 6m0-4v4h-4M21 14a9 9 0 0 1-15.4 6.4L3 18m0 4v-4h4'}]],
    expand: [['path',{d:'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5'}]],
    plus: [['path', {d:'M12 5v14M5 12h14'}]],
    close: [['path', {d:'m6 6 12 12M6 18 18 6'}]],
    'arrow-right': [['path', {d:'M5 12h14m-6-6 6 6-6 6'}]],
    'chevron-right': [['path', {d:'m9 18 6-6-6-6'}]],
    'chevron-down': [['path', {d:'m6 9 6 6 6-6'}]],
    history: [['path', {d:'M3 12a9 9 0 1 0 2.7-6.4L3 8m0-5v5h5m4-1v5l3 2'}]],
    settings: [['path', {d:'M9.7 4.3a2.4 2.4 0 0 1 4.6 0l.3.8 1 .6.8-.1a2.4 2.4 0 0 1 2.3 4l-.5.7v1.2l.5.7a2.4 2.4 0 0 1-2.3 4l-.8-.1-1 .6-.3.8a2.4 2.4 0 0 1-4.6 0l-.3-.8-1-.6-.8.1a2.4 2.4 0 0 1-2.3-4l.5-.7v-1.2l-.5-.7a2.4 2.4 0 0 1 2.3-4l.8.1 1-.6z'}],['circle',{cx:12,cy:11,r:3}]],
    architecture: [['rect',{x:9,y:3,width:6,height:5,rx:1}],['rect',{x:2,y:16,width:6,height:5,rx:1}],['rect',{x:16,y:16,width:6,height:5,rx:1}],['path',{d:'M12 8v4M5 16v-4h14v4'}]],
    code: [['path',{d:'m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16'}]],
    route: [['circle',{cx:6,cy:18,r:3}],['circle',{cx:18,cy:6,r:3}],['path',{d:'M6 15V8a5 5 0 0 1 5-5h4M9 18h7a5 5 0 0 0 5-5v-1'}]],
    search: [['circle',{cx:10.5,cy:10.5,r:7.5}],['path',{d:'m16 16 5 5'}]],
    references: [['path',{d:'M10 13a5 5 0 0 0 7 .2l3-3a5 5 0 0 0-7-7l-1.7 1.7m2.7 6.1a5 5 0 0 0-7-.2l-3 3a5 5 0 0 0 7 7l1.7-1.7'}]],
    'check-file': [['path',{d:'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6m-12 7 3 3 5-6'}]],
    file: [['path',{d:'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h5'}]],
    download: [['path',{d:'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3'}]],
    shield: [['path',{d:'M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z'}]],
    circle: [['circle',{cx:12,cy:12,r:8}]],
    check: [['path',{d:'m5 12 4 4L19 6'}]],
    info: [['circle',{cx:12,cy:12,r:9}],['path',{d:'M12 11v6M12 7h.01'}]],
    activity: [['path',{d:'M22 12h-4l-3 9L9 3l-3 9H2'}]],
    pause: [['rect',{x:6,y:4,width:4,height:16,rx:1}],['rect',{x:14,y:4,width:4,height:16,rx:1}]],
    play: [['path',{d:'m6 3 15 9-15 9V3Z'}]],
    stop: [['rect',{x:5,y:5,width:14,height:14,rx:2}]],
    layers: [['path',{d:'m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5'}]],
    folder: [['path',{d:'M20 20H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2Z'}]],
    branch: [['circle',{cx:6,cy:3,r:2}],['circle',{cx:6,cy:21,r:2}],['circle',{cx:18,cy:6,r:2}],['path',{d:'M6 5v14M18 8a8 8 0 0 1-8 8H6'}]],
    clock: [['circle',{cx:12,cy:12,r:9}],['path',{d:'M12 7v5l3 2'}]],
    connection: [['path',{d:'M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0m-10 4a5 5 0 0 1 6 0M12 20h.01'}]],
    lock: [['rect',{x:4,y:10,width:16,height:12,rx:2}],['path',{d:'M8 10V6a4 4 0 0 1 8 0v4'}]]
  };
  const ROLE_INFO = {
    architect: {title:'Architect', icon:'architecture', description:'Plan and final review'},
    lead: {title:'Builder', icon:'code', description:'Plans and prepares code changes'},
    scout: {title:'Scout', icon:'search', description:'Finds files and references'},
    auditor: {title:'Auditor', icon:'check-file', description:'Reviews changes and check results'},
    router: {title:'Router fallback', icon:'route', description:'Optional help for ambiguous routing decisions'}
  };
  const ROLE_ORDER = ['architect','lead','scout','auditor','router'];
  const STAGES = {queued:'Queued',preparing:'Preparing the workspace',discovering:'Finding relevant files',planning:'Preparing the plan',plan_review:'Reviewing the plan',building:'Preparing code changes',checking:'Checking the changes',auditing:'Reviewing check results',final_review:'Final review',ready_for_review:'Ready for your review'};
  const STATUSES = {queued:'Queued',running:'Running',paused:'Paused',cancelled:'Stopped',interrupted:'Interrupted',failed:'Failed',needs_input:'Needs input',ready_for_review:'Ready for review'};
  const WORKER_STATES = {idle:'On call',working:'Working',done:'Finished',failed:'Failed'};
  const TERMINAL = new Set(['ready_for_review','failed','needs_input','cancelled','interrupted']);
  const PROFILES = [
    ['custom','Custom / local service',''],
    ['deepseek','DeepSeek','https://api.deepseek.com/v1'],
    ['minimax','MiniMax','https://api.minimax.io/v1'],
    ['openrouter','OpenRouter','https://openrouter.ai/api/v1'],
    ['zai-coding','Z.ai · USA coding endpoint','https://api.z.ai/api/coding/paas/v4']
  ];
  const APP_BASE = new URL('.', document.currentScript?.src || location.href);
  const S = {projects:[],projectRoots:[],project:null,projectId:'',projectRequest:0,catalog:[],setup:null,router:null,setupStep:0,setupOpened:false,sampleTask:null,settingsTab:'accounts',layout:'desktop',orientation:'portrait',phoneTab:'work',evidenceView:'overview',preferenceTheme:'system',preferenceLayout:'auto',checkingAccounts:false,token:'',health:null,providers:{},runs:[],run:null,selectedId:null,events:[],visibleEvents:50,polling:false,connected:false,selection:0,loading:false,toastTimer:null,evidence:null,artifactRequest:0,pollCount:0};

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('class','icon'); svg.setAttribute('aria-hidden','true');
    for (const [tag, attrs] of (ICONS[name] || ICONS.file)) {
      const part = document.createElementNS('http://www.w3.org/2000/svg',tag);
      for (const [key,value] of Object.entries(attrs)) part.setAttribute(key,String(value));
      svg.append(part);
    }
    return svg;
  }
  function fillIcons(root = document) {
    $$('[data-icon]',root).forEach(node => node.replaceChildren(icon(node.dataset.icon)));
  }
  function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
  function asText(value, fallback = '') { return typeof value === 'string' ? value : fallback; }
  function statusName(value) { return STATUSES[value] || asText(value,'Unknown'); }
  function timestamp(value) { const d = new Date(value); return Number.isNaN(d.valueOf()) ? null : d; }
  function formatTime(value) { const d = timestamp(value); return d ? new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(d) : '—'; }
  function formatDate(value) { const d = timestamp(value); return d ? new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(d) : 'Time unavailable'; }
  function formatDuration(ms) { if (!finite(ms) || ms < 0) return '—'; const sec = Math.floor(ms / 1000); if (sec < 60) return `${sec}s`; const min = Math.floor(sec/60); return min < 60 ? `${min}m ${sec%60}s` : `${Math.floor(min/60)}h ${min%60}m`; }
  function bytes(value) { if (!finite(value)) return ''; return value < 1024 ? `${value} bytes` : `${(value/1024).toFixed(1)} KB`; }
  function roleTitle(role) { return ({search:'Find files',grep:'Find references',audit:'Tests & review',router:'Routing',system:'System',runtime:'Runtime',engine:'Engine',router:'Routing'}[role]) || ROLE_INFO[role]?.title || role || 'System'; }
  function artifactName(item) { return typeof item === 'string' ? item : asText(item?.name); }
  function artifactList() { return Array.isArray(S.run?.artifacts) ? S.run.artifacts.filter(item => artifactName(item)) : []; }
  function isRunning(run = S.run) { return run && (run.status === 'running' || run.status === 'queued'); }
  function setText(selector, value) { const target = $(selector); if (target) target.textContent = value; }
  function announce(message) { $('#announcement').textContent = message; }
  function toast(message) { clearTimeout(S.toastTimer); $('#toast').textContent = message; $('#toast').hidden = false; S.toastTimer = setTimeout(() => { $('#toast').hidden = true; },5000); }
  function formError(target, message) { target.textContent = message || ''; target.hidden = !message; }
  function openDialog(id) { const dialog = document.getElementById(id); if (!dialog.open) dialog.showModal(); }
  function closeDialog(id) { document.getElementById(id).close(); }
  function setButtonLabel(button, label) { const span = $('span:not([data-icon])',button); if (span) span.textContent = label; else button.textContent = label; }

  async function api(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(),options.timeout || 20000);
    const headers = {Accept:options.plain ? 'text/plain' : 'application/json'};
    if (S.token) headers.Authorization = `Bearer ${S.token}`;
    const init = {method:options.method || 'GET',headers,signal:controller.signal,cache:'no-store',credentials:'same-origin'};
    if (options.body !== undefined) { headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(options.body); }
    try {
      const response = await fetch(new URL(`api${path}`,APP_BASE),init);
      if (!response.ok) {
        let message = response.status === 401 ? 'The server requires a valid access token.' : `The server could not complete this request (${response.status}).`;
        try { const payload = await response.json(); if (typeof payload.error === 'string') message = payload.error; } catch (_) { /* Never display an untrusted raw error body. */ }
        const error = new Error(message); error.status = response.status; throw error;
      }
      return options.plain ? await response.text() : await response.json();
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The request timed out. The run may still be active; reconnect to check its state.');
      if (error instanceof TypeError) throw new Error('Unable to reach the RATBAG server. Check that it is running, then reconnect.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  function connection(ok, message = '') {
    S.connected = ok;
    $('#footer-dot').dataset.connected = String(ok);
    $('#connection-banner').hidden = ok;
    setText('#connection-message',message);
    setText('#server-status',ok ? `Connected${S.health?.version ? ` · RATBAG ${S.health.version}` : ' to RATBAG'}` : 'Connection unavailable');
  }
  function handleConnectionError(error) {
    connection(false,error.message);
    if (error.status === 401 && !$('#access-dialog').open) openDialog('access-dialog');
  }
  function sortRuns(runs) { return (Array.isArray(runs) ? runs : []).filter(run => run && typeof run.id === 'string').sort((a,b) => (timestamp(b.created_at)?.valueOf() || 0) - (timestamp(a.created_at)?.valueOf() || 0)); }
  function upsertRun(run) { if (!run?.id) return; S.runs = sortRuns([run,...S.runs.filter(item => item.id !== run.id)]); }

  async function bootstrap() {
    try {
      S.health = await api('/health');
      const [providers,runs,setup,projects,catalog,router] = await Promise.all([api('/providers'),api('/runs'),api('/setup'),api('/projects'),api('/models/catalog'),api('/router')]);
      S.providers = providers.providers || {}; S.setup = setup; S.projects = projects.projects || []; S.projectRoots = projects.roots || []; S.catalog = catalog.models || []; S.router = router;
      S.runs = sortRuns(runs.runs);
      connection(true);
      renderProviders(); renderHistory(); renderProjectChoices(); renderProjectList(); renderSetup(); renderAccounts(); renderRouter();
      const hashSetup = location.hash === '#setup';
      const requested = new URLSearchParams(location.hash.slice(1)).get('run');
      const selected = S.selectedId || (requested && S.runs.some(run => run.id === requested) ? requested : null) || S.health.running_run_id || S.runs[0]?.id;
      if (selected) await selectRun(selected); else renderRun();
      if (!S.setupOpened && (hashSetup || (!S.setup.completed && !S.runs.length))) openSetup();
      return true;
    } catch (error) { handleConnectionError(error); if (!S.run) { setText('#run-status-label','Server not connected'); } return false; }
  }
  async function refreshRuns() {
    const [runs,health,setup] = await Promise.all([api('/runs'),api('/health'),api('/setup')]);
    S.runs = sortRuns(runs.runs); S.health = health; S.setup = setup; renderSetup();
    if ($('#history-dialog').open) renderHistory();
    connection(true);
  }
  async function selectRun(id) {
    const generation = ++S.selection;
    S.selectedId = id; S.loading = true; S.run = null; S.events = []; S.visibleEvents = 50; S.evidence = null; S.evidenceView = 'overview'; S.artifactRequest++;
    renderRun(); renderEvents();
    try {
      const [result,events] = await Promise.all([api(`/runs/${encodeURIComponent(id)}`),api(`/runs/${encodeURIComponent(id)}/events?after=0`)]);
      if (generation !== S.selection) return;
      S.run = result.run; S.events = Array.isArray(events.events) ? events.events : []; S.loading = false;
      upsertRun(S.run); history.replaceState(null,'',`#run=${encodeURIComponent(id)}`);
      renderRun(); renderEvents(); renderInspection(); connection(true);
    } catch (error) { if (generation === S.selection) { S.loading = false; renderRun(); handleConnectionError(error); } }
  }
  async function poll() {
    if (S.polling || $('#access-dialog').open) return;
    S.polling = true;
    try {
      if (!S.connected) { S.pollCount++; if (S.pollCount % 4 === 0) await bootstrap(); return; }
      if (S.selectedId && S.run && !S.loading && (isRunning() || S.run.status === 'paused')) {
        const id = S.selectedId; const generation = S.selection;
        const after = S.events.reduce((max,event) => Math.max(max,finite(event.id) ? event.id : 0),0);
        const [result,eventResult] = await Promise.all([api(`/runs/${encodeURIComponent(id)}`),api(`/runs/${encodeURIComponent(id)}/events?after=${after}`)]);
        if (generation === S.selection && id === S.selectedId) {
          const previous = `${S.run?.status}:${S.run?.stage}`;
          S.run = result.run; upsertRun(S.run);
          const known = new Set(S.events.map(event => event.id));
          const incoming = (Array.isArray(eventResult.events) ? eventResult.events : []).filter(event => !known.has(event.id));
          S.events.push(...incoming);
          renderRun(); if (incoming.length) renderEvents();
          if (previous !== `${S.run?.status}:${S.run?.stage}`) announce(`${statusName(S.run.status)}. ${STAGES[S.run.stage] || S.run.stage}.`);
        }
      }
      S.pollCount++;
      if (S.pollCount % 7 === 0) await refreshRuns();
    } catch (error) { handleConnectionError(error); }
    finally { S.polling = false; }
  }

  function configuredModel(role, worker) {
    if (typeof worker?.model === 'string' && worker.model) return worker.model;
    const cfg = S.providers[role];
    return cfg?.model_id ? `Configured: ${cfg.model_id}` : 'Configure a model';
  }
  function stateLabel(node, worker, empty = 'Not running') {
    const state = worker?.state;
    node.textContent = state === 'working' && S.run && !isRunning() ? statusName(S.run.status) : state ? (WORKER_STATES[state] || state) : (S.run ? 'Waiting' : empty);
    node.dataset.state = state || 'idle';
  }
  function metadata(iconName, value, title) {
    const item = el('span','metadata-item'); item.append(icon(iconName),el('span','',value));
    if (title) item.title = title;
    return item;
  }
  function renderCheckpoint(type, review) {
    const row = $(`#checkpoint-${type}`), button = $('button',row), result = $('.checkpoint-result',row);
    const pending = type === 'plan' ? 'Waiting for a plan' : 'Waiting for checked changes';
    const working = S.run?.stage === (type === 'plan' ? 'plan_review' : 'final_review') && isRunning();
    row.dataset.state = review ? (review.approved === true ? 'approved' : 'rejected') : working ? 'working' : 'pending';
    $('.checkpoint-mark',row).replaceChildren(icon(review ? (review.approved === true ? 'check' : 'close') : 'circle'));
    button.disabled = !review;
    result.textContent = review ? (review.approved === true ? 'Approved · open review' : 'Changes required · open review') : working ? 'Review in progress' : S.run ? pending : (type === 'plan' ? 'Waiting for a task' : 'Waiting for changes');
  }
  function renderRun() {
    const run = S.run, workers = run?.workers || {};
    if (!run) {
      setText('#run-status-label',S.loading ? 'Opening saved run' : S.connected ? 'Ready when you are' : 'Getting connected');
      $('#run-status-dot').dataset.state = ''; setText('#run-short-id','');
      setText('#task-title',S.loading ? 'Opening your work…' : 'Good work starts here.');
      setText('#task-description','Start a task to follow its plan, changes, checks, and review in one place.');
      $('#run-metadata').hidden = true; $('#task-controls').hidden = true; $('#next-action').hidden = true;
    } else {
      setText('#run-status-label',statusName(run.status)); $('#run-status-dot').dataset.state = run.status;
      setText('#run-short-id',run.id.slice(0,8)); setText('#task-title',run.task || 'Untitled task');
      setText('#task-description',run.repo_path || 'Repository path unavailable');
      const meta = $('#run-metadata'); meta.replaceChildren(); meta.hidden = false;
      if (run.base_commit) meta.append(metadata('branch',`Base ${String(run.base_commit).slice(0,8)}`,String(run.base_commit)));
      const start = timestamp(run.started_at || run.created_at);
      const end = TERMINAL.has(run.status) ? timestamp(run.finished_at || run.updated_at) : new Date();
      if (start && end) meta.append(metadata('clock',`${formatDuration(end-start)} elapsed`));
      if (finite(run.attempt) && run.attempt > 0) meta.append(metadata('layers',`Attempt ${run.attempt}${finite(run.max_attempts) ? ` of ${run.max_attempts}` : ''}`));
      if (finite(run.model_calls)) meta.append(metadata('activity',`${run.model_calls} model request${run.model_calls === 1 ? '' : 's'}`));
      const running = isRunning(run), resumable = run.status === 'paused' || run.status === 'interrupted';
      const revisable = ['needs_input','failed','interrupted'].includes(run.status);
      $('#task-controls').hidden = !(running || resumable || revisable);
      $('#revise-button').hidden = !revisable;
      $('#pause-button').hidden = !running;
      $('#pause-button').disabled = !!run.pause_requested || !!run.cancel_requested;
      setButtonLabel($('#pause-button'),run.pause_requested ? 'Pause requested' : 'Pause');
      $('#resume-button').hidden = !resumable; $('#resume-button').disabled = !!run.cancel_requested;
      $('#cancel-button').hidden = !(running || run.status === 'paused'); $('#cancel-button').disabled = !!run.cancel_requested;
      setButtonLabel($('#cancel-button'),run.cancel_requested ? 'Stopping…' : 'Stop');
      let next = asText(run.next_action);
      if (run.cancel_requested && running) next = 'Stop requested. Waiting for the current operation to end; saved evidence will remain available.';
      else if (run.pause_requested && running) next = 'Pause requested. The task will pause at the next safe stage boundary.';
      else if (run.status === 'interrupted' && !next) next = 'This run was interrupted. Resume it to continue from its preserved state.';
      $('#next-action').hidden = !next; $('#next-action p').textContent = next;
    }
    setText('#architect-model',configuredModel('architect',workers.architect));
    stateLabel($('#architect-state'),workers.architect);
    renderCheckpoint('plan',run?.reviews?.plan); renderCheckpoint('final',run?.reviews?.final);
    const recovery = recoveryReview();
    const recoveryState = recovery ? (recovery.detail?.approved === true ? 'approved' : 'rejected') : 'pending';
    $('#checkpoint-recovery').dataset.state = recoveryState;
    $('#checkpoint-recovery .checkpoint-mark').replaceChildren(icon(recovery ? (recoveryState === 'approved' ? 'check' : 'close') : 'circle'));
    $('#checkpoint-recovery .checkpoint-result').textContent = recovery ? (recoveryState === 'approved' ? 'Approved · open review' : 'Changes required · open review') : 'On call when needed';
    $('#recovery-review-button').disabled = !recovery;
    const review = run?.reviews?.final || run?.reviews?.plan;
    setText('#architect-message',asText(workers.architect?.message) || asText(review?.summary) || 'Review results will appear here with their supporting evidence.');
    setText('#lead-model',configuredModel('lead',workers.lead)); stateLabel($('#lead-state'),workers.lead);
    $('#lead-card').dataset.working = String(workers.lead?.state === 'working' && isRunning());
    setText('#lead-action',run ? (isRunning() ? (STAGES[run.stage] || statusName(run.status)) : statusName(run.status)) : 'Ready for your next task');
    setText('#lead-message',asText(workers.lead?.message) || (run ? 'The current stage and its results are recorded in Activity below.' : 'Describe the result you want. The team will find the relevant files, prepare a plan, and check its work.'));
    setText('#current-stage span:not([data-icon])',run ? (STAGES[run.stage] || statusName(run.status)) : 'Plan, build, check, review');
    $('#view-evidence-button').disabled = !run;
    const routing = run?.routing;
    $('#routing-button').disabled = !S.connected;
    setText('#routing-message',asText(routing?.reason) || 'Roles have clear jobs. Open the recommended team and the reason behind each choice.');
    setText('#routing-meta',routing ? `${routing.via === 'router' ? 'Model-assisted' : 'Rule'}${finite(routing.elapsed_ms) ? ` · ${routing.elapsed_ms.toFixed(1)} ms` : ''}` : '');
    for (const [name,role] of [['search','scout'],['grep','scout'],['audit','auditor']]) {
      const card = $(`#worker-${name}`), worker = workers[name];
      stateLabel($('.state-label',card),worker); card.dataset.state = worker?.state || 'idle';
      $('.model-name',card).textContent = configuredModel(role,worker);
      const defaults = {search:'Locate the files relevant to the task.',grep:'Trace matching code and where it is used.',audit:'Check the proposed changes in a separate workspace.'};
      $('.worker-message',card).textContent = asText(worker?.message) || defaults[name];
      $('.worker-details',card).disabled = !run || (!worker && !(name === 'audit' && run.checks?.length));
    }
    const patch = finalPatch();
    $('#outcome-card').dataset.ready = String(run?.status === 'ready_for_review');
    $('#download-patch-button').hidden = !patch;
    if (run?.status === 'ready_for_review') {
      setText('#outcome-title','Ready for your review');
      setText('#outcome-description',patch ? 'The checked and approved patch is preserved with its evidence.' : 'Open the saved evidence to inspect this result.');
    } else if (run && TERMINAL.has(run.status)) {
      setText('#outcome-title',`${statusName(run.status)} · evidence preserved`);
      setText('#outcome-description','Open the run evidence to inspect its attempts and recorded results.');
    } else {
      setText('#outcome-title','A result you can inspect');
      setText('#outcome-description',run ? 'The final patch appears here after the required checks and reviews pass.' : 'Changes and evidence stay available after the run.');
    }
    setText('#footer-detail',run?.patch_hash ? `Patch ${String(run.patch_hash).slice(0,12)}` : 'A task is complete only when its evidence is saved.');
    $('#phone-new-task').hidden = !$('#task-controls').hidden;
    renderInspection(); renderTaskReadiness();
  }
  function finalPatch() {
    if (S.run?.status !== 'ready_for_review') return null;
    const name = asText(S.run.patch_artifact,'final.patch');
    return artifactList().find(item => artifactName(item) === name) || null;
  }
  function recoveryReview() {
    return S.events.filter(event => event.actor === 'architect' && event.kind === 'review' && event.detail?.phase === 'repeated_failure').at(-1);
  }

  function renderEvents() {
    const list = $('#activity-list'), previousTop = list.scrollTop;
    const following = $('#follow-latest').checked;
    list.replaceChildren(); setText('#event-count',S.events.length ? String(S.events.length) : '');
    $('#earlier-events').hidden = S.events.length <= S.visibleEvents;
    if (!S.events.length) {
      const empty = el('div','activity-empty'); empty.append(icon('activity'),el('p','',S.loading ? 'Opening the saved activity…' : 'Each meaningful step will appear here.'),el('span','','Open any event to inspect its details.')); list.append(empty); return;
    }
    for (const event of S.events.slice(-S.visibleEvents)) {
      const row = el('button','event-row'); row.type = 'button'; row.dataset.kind = asText(event.kind);
      row.append(el('span','event-time',formatTime(event.timestamp)),el('span','event-actor',roleTitle(event.actor)),el('span','event-message',asText(event.message)),icon('chevron-right'));
      row.title = 'Open event details'; row.addEventListener('click',() => openEvent(event)); list.append(row);
    }
    if (following) list.scrollTop = list.scrollHeight; else list.scrollTop = previousTop;
  }
  function renderHistory() {
    const list = $('#history-list'); list.replaceChildren();
    if (!S.runs.length) {
      const empty = el('div','history-empty'); empty.append(el('p','','Your saved tasks will appear here.'));
      const button = el('button','button primary','Start your first task'); button.addEventListener('click',() => { closeDialog('history-dialog'); openTask(); }); empty.append(button); list.append(empty); return;
    }
    for (const run of S.runs) {
      const button = el('button','history-entry'); button.type = 'button'; button.setAttribute('aria-current',String(run.id === S.selectedId));
      const meta = el('span','history-entry-meta'); meta.append(el('span','',statusName(run.status)),el('span','',formatDate(run.created_at)),el('span','mono',run.id.slice(0,8)));
      button.append(el('strong','',run.task || 'Untitled task'),meta);
      button.addEventListener('click',() => { closeDialog('history-dialog'); selectRun(run.id); }); list.append(button);
    }
  }

  function field(label, name, options = {}) {
    const wrapper = el('label','field',label);
    let input;
    if (options.choices) {
      input = el('select'); for (const [value,text] of options.choices) { const option = el('option','',text); option.value = value; input.append(option); }
    } else { input = el('input'); input.type = options.type || 'text'; }
    input.name = name; input.value = options.value ?? ''; input.autocomplete = 'off'; input.spellcheck = false;
    if (options.required) input.required = true;
    if (options.readOnly) input.readOnly = true;
    if (options.disabled) input.disabled = true;
    if (options.min !== undefined) input.min = String(options.min);
    if (options.max !== undefined) input.max = String(options.max);
    if (options.placeholder) input.placeholder = options.placeholder;
    wrapper.append(input);
    if (options.help) wrapper.append(el('span','field-help',options.help));
    return wrapper;
  }
  function updateProviderSummary(entry, role, cfg) {
    $('.provider-model',entry).textContent = cfg.model_id || 'No model configured';
    const keyStatus = $('.provider-key-status',entry);
    keyStatus.textContent = role === 'router' && cfg.enabled === false ? 'Optional · off' : cfg.key_present ? 'Key available' : 'Key needed';
    keyStatus.dataset.present = String(!!cfg.key_present && !(role === 'router' && cfg.enabled === false));
  }
  function providerCheckTimeout(role) { return (Number(S.providers[role]?.timeout_seconds || 120) + 10) * 1000; }
  function effortChoices(values) { return (values || ['low','medium','high','xhigh','max']).map(value => [value,({low:'Low',medium:'Medium',high:'High',xhigh:'Extra high',max:'Maximum'})[value] || value]); }
  function renderProviders() {
    const list = $('#provider-list');
    if ($$('input[name=api_key]',list).some(input => input.value) && $('#settings-dialog').open) return;
    const expanded = $('details[open]',list)?.dataset.role;
    list.replaceChildren();
    for (const role of ROLE_ORDER) {
      const cfg = S.providers[role]; if (!cfg) continue;
      const info = ROLE_INFO[role], locked = !!cfg.endpoint_locked;
      const entry = el('details','provider-entry'); entry.dataset.role = role; entry.open = expanded === role;
      const summary = el('summary'); summary.append(icon(info.icon));
      const desc = el('span','provider-summary'); desc.append(el('strong','',info.title),el('span','provider-model','')); summary.append(desc,el('span','provider-key-status',''),icon('chevron-down')); entry.append(summary);
      const form = el('form','provider-form'); form.dataset.role = role; form.append(el('p','field-help',info.description));
      const candidates = S.catalog.filter(model => !Array.isArray(model.roles) || model.roles.includes(role));
      const current = candidates.find(model => model.model_id === cfg.model_id && model.base_url === cfg.base_url);
      form.append(field('Model','catalog_model',{choices:[...candidates.map(model => [model.id,model.label]),['custom','Custom model / connection']],value:current?.id || 'custom'}));
      const toggle = el('label','toggle-row'), enabled = el('input'); enabled.type = 'checkbox'; enabled.name = 'enabled'; enabled.checked = cfg.enabled !== false;
      toggle.append(enabled,el('span','',role === 'router' ? 'Enable this optional model for uncertain routing choices. Save and check its connection before use.' : 'Use this role for new tasks. Core roles must be enabled to start.')); form.append(toggle);
      const advanced = el('details','advanced-options provider-custom'); advanced.open = !current;
      advanced.append(el('summary','','Custom connection and limits')); const fields = el('div','form-stack');
      const profile = PROFILES.find(item => item[2] && item[2] === cfg.base_url)?.[0] || 'custom';
      fields.append(field('Provider profile','profile',{choices:PROFILES.map(item => [item[0],item[1]]),value:profile}));
      const pair = el('div','two-fields'); pair.append(field('Model ID','model_id',{value:cfg.model_id,required:true}),field('API format','protocol',{choices:[['openai','OpenAI compatible'],['anthropic','Anthropic compatible']],value:cfg.protocol,disabled:locked})); fields.append(pair);
      fields.append(field('Provider address','base_url',{type:'url',value:cfg.base_url,required:true,readOnly:locked,help:'Native GLM models use the requested Z.ai Coding address. Custom connections use their own provider address.'}));
      const tuning = el('div','two-fields'); tuning.append(field('Reasoning effort','effort',{choices:effortChoices(current?.efforts || (locked ? ['low','high','max'] : undefined)),value:cfg.effort || 'high'}),field('Maximum output tokens','max_tokens',{type:'number',value:cfg.max_tokens || 4096,min:64,max:131072,required:true})); fields.append(tuning);
      fields.append(field('Connection timeout, seconds','timeout_seconds',{type:'number',value:cfg.timeout_seconds || 120,min:1,max:600,required:true,help:'How long a model request may wait for its provider.'}));
      fields.append(field('Environment key name','api_key_env',{value:cfg.api_key_env || '',required:true,help:'The server can read its key from this environment variable. Enter the variable name here, not the key.'}));
      fields.append(field('Session API key','api_key',{type:'password',value:'',placeholder:cfg.key_present ? 'A key is available · enter only to replace it' : 'Enter the provider key',help:'For custom accounts. The Accounts tab shares a native GLM key across both reviewer roles. Keys stay in server memory.'}));
      advanced.append(fields); form.append(advanced);
      const feedback = el('p','provider-feedback'); feedback.setAttribute('role','status');
      if (cfg.last_check) feedback.textContent = `${cfg.last_check.ok ? 'Last connection check succeeded' : 'Last connection check failed'}${cfg.last_check.checked_at ? ` · ${formatDate(cfg.last_check.checked_at)}` : ''}${cfg.last_check.message ? `. ${cfg.last_check.message}` : ''}`;
      const actions = el('div','provider-actions'); actions.append(el('span','field-help','Check connection sends a model request and may use credits.'));
      const buttons = el('div','provider-buttons'), check = el('button','button secondary','Check connection'), save = el('button','button primary','Save role'); check.type = 'button'; save.type = 'submit'; buttons.append(check,save); actions.append(buttons); form.append(feedback,actions); entry.append(form); list.append(entry); updateProviderSummary(entry,role,cfg);
      const markDirty = () => { form.dataset.dirty = 'true'; check.disabled = true; check.title = 'Save this role before checking its new settings.'; };
      form.addEventListener('input',markDirty);
      form.addEventListener('change',event => {
        if (event.target.name === 'catalog_model') {
          const model = candidates.find(item => item.id === event.target.value);
          if (model) {
            for (const name of ['model_id','protocol','base_url','api_key_env','max_tokens','effort']) if (model[name] !== undefined) form.elements[name].value = String(model[name]);
            const effort = form.elements.effort; effort.replaceChildren(...effortChoices(model.efforts).map(([value,label]) => optionNode(value,label))); effort.value = model.effort || 'high';
            const native = /^glm-/i.test(model.model_id); form.elements.protocol.disabled = native; form.elements.base_url.readOnly = native;
            form.elements.profile.value = PROFILES.find(item => item[2] === model.base_url)?.[0] || 'custom';
          } else advanced.open = true;
        } else if (event.target.name === 'profile') {
          const selected = PROFILES.find(item => item[0] === event.target.value);
          if (selected?.[2] && !/^glm-/i.test(form.elements.model_id.value)) { form.elements.base_url.value = selected[2]; form.elements.protocol.value = 'openai'; }
          form.elements.catalog_model.value = 'custom';
        } else if (event.target.name === 'model_id') {
          form.elements.catalog_model.value = 'custom'; const native = /^glm-/i.test(form.elements.model_id.value.trim());
          form.elements.protocol.disabled = native; form.elements.base_url.readOnly = native;
          if (native) { form.elements.base_url.value = 'https://api.z.ai/api/coding/paas/v4'; form.elements.protocol.value = 'openai'; }
        }
        markDirty();
      });
      form.addEventListener('submit',event => { event.preventDefault(); saveProvider(role,form,entry,save,check,feedback); });
      check.addEventListener('click',async () => {
        S.checkingAccounts = true; applySettingsLocks(); feedback.dataset.error = 'false'; feedback.dataset.success = 'false'; feedback.textContent = 'Checking the saved connection…';
        try {
          const result = await api(`/providers/${role}/check`,{method:'POST',body:{},timeout:providerCheckTimeout(role)});
          feedback.dataset.success = String(result.ok === true); feedback.dataset.error = String(result.ok !== true);
          feedback.textContent = `${result.ok ? 'Connection succeeded' : 'Connection failed'}${result.model ? ` · ${result.model}` : ''}${result.message ? `. ${result.message}` : ''}`;
        } catch (error) { feedback.dataset.error = 'true'; feedback.textContent = error.message; }
        finally {
          S.checkingAccounts = false; await refreshSetupSafely(); applySettingsLocks();
        }
      });
    }
    applySettingsLocks();
  }
  async function saveProvider(role,form,entry,save,check,feedback) {
    if (!form.checkValidity()) { $('.provider-custom',form).open = true; form.reportValidity(); return; }
    save.disabled = true; check.disabled = true; feedback.dataset.error = 'false'; feedback.dataset.success = 'false'; feedback.textContent = 'Saving this role…';
    const values = {};
    for (const name of ['model_id','protocol','base_url','api_key_env','effort']) values[name] = form.elements[name].value.trim();
    values.max_tokens = Number(form.elements.max_tokens.value); values.timeout_seconds = Number(form.elements.timeout_seconds.value); values.enabled = form.elements.enabled.checked;
    if (form.elements.api_key.value) values.api_key = form.elements.api_key.value;
    try {
      const result = await api(`/providers/${role}`,{method:'PUT',body:values});
      delete values.api_key; S.providers[role] = result.provider; form.elements.api_key.value = ''; form.dataset.dirty = 'false'; updateProviderSummary(entry,role,result.provider); renderRun();
      feedback.dataset.success = 'true'; feedback.textContent = 'Role saved. No model request was sent.';
      if (role !== 'router') {
        try { const routing = await api('/router/apply',{method:'POST',body:{mode:'manual'}}); S.router = routing.router; S.setup = routing.setup; feedback.textContent = 'Role saved. Manual routing now keeps your chosen settings for new tasks. No model request was sent.'; }
        catch (error) { feedback.dataset.error = 'true'; feedback.dataset.success = 'false'; feedback.textContent = `The role was saved, but the routing preference could not be updated. Select Manual in your new task to keep this choice. ${error.message}`; }
      }
      await refreshSetupSafely(); announce(`${ROLE_INFO[role].title} settings saved.`);
    } catch (error) { feedback.dataset.error = 'true'; feedback.textContent = error.message; }
    finally { delete values.api_key; applySettingsLocks(); }
  }

  async function openTask(mode = 'new') {
    const revising = mode === 'revise' && S.run, form = $('#task-form');
    formError($('#task-form-error'),'');
    $('#task-revision-note').hidden = !revising;
    setText('#task-dialog-title',revising ? 'Revise this task' : 'What should we work on?');
    setButtonLabel($('button[type=submit]',form),revising ? 'Start new run' : 'Start task');
    if (revising) {
      for (const name of ['task','repo_path','test_command','symbol']) form.elements[name].value = asText(S.run[name]);
      for (const name of ['max_attempts','max_model_calls','test_timeout']) form.elements[name].value = finite(S.run[name]) ? String(S.run[name]) : form.elements[name].defaultValue;
      form.elements.routing_mode.value = S.run.routing_mode || S.setup?.routing_mode || 'manual';
      const project = S.projects.find(item => item.id === S.run.project_id || item.path === S.run.repo_path);
      form.elements.project_id.value = project?.id || 'custom';
      $('.advanced-options',form).open = true;
      setText('#task-revision-note',`This starts a new run with revised instructions. Run ${S.run.id.slice(0,8)} and its evidence stay in History.`);
      await updateTaskProject(project?.id || 'custom');
      if (S.run.test_command) { form.elements.test_choice.value = 'custom'; form.elements.test_command.value = S.run.test_command; updateTaskCheck(); }
    } else {
      form.elements.project_id.value = S.projectId || '';
      form.elements.routing_mode.value = S.setup?.routing_mode || 'smart';
      if (S.sampleTask && S.project?.kind === 'sample' && !form.elements.task.value.trim()) {
        form.elements.task.value = S.sampleTask.task; form.elements.symbol.value = S.sampleTask.symbol || '';
      }
      if (form.elements.project_id.value) await updateTaskProject(form.elements.project_id.value);
    }
    await previewTaskRouter(); renderTaskReadiness(); openDialog('task-dialog');
  }
  async function controlRun(action,button) {
    if (!S.run) return;
    const id = S.run.id, generation = S.selection;
    button.disabled = true;
    try {
      const result = await api(`/runs/${encodeURIComponent(id)}/${action}`,{method:'POST',body:{}});
      if (generation === S.selection) { S.run = result.run; upsertRun(S.run); renderRun(); }
      toast(action === 'pause' ? 'Pause requested. The task will pause at a safe boundary.' : action === 'cancel' ? 'Stop requested. Waiting for active work to end.' : 'Resume requested. Following the saved run.');
    } catch (error) { toast(error.message); if (error.status === 401) handleConnectionError(error); }
    finally { if (generation === S.selection) renderRun(); }
  }

  function evidenceOverview() {
    const run = S.run;
    if (!run) return '';
    const lines = [`TASK\n${run.task || ''}`,`STATE\n${statusName(run.status)} · ${STAGES[run.stage] || run.stage}`,`REPOSITORY\n${run.repo_path || ''}`];
    if (run.base_commit) lines.push(`STARTING COMMIT\n${run.base_commit}`);
    if (run.snapshot_commit) lines.push(`SOURCE SNAPSHOT\n${run.snapshot_commit}`);
    if (run.candidate_hash) lines.push(`CHECKED CANDIDATE\n${run.candidate_hash}`);
    if (run.patch_hash) lines.push(`PATCH SHA-256\n${run.patch_hash}`);
    if (run.next_action) lines.push(`NEXT ACTION\n${run.next_action}`);
    const checks = Array.isArray(run.checks) ? run.checks : [];
    if (checks.length) lines.push(`RECORDED CHECKS\n${checks.map(check => `${check.name || 'Check'}: ${check.status || (check.passed === true ? 'passed' : check.passed === false ? 'failed' : 'unknown')}\n${check.message || ''}${check.artifact ? `\nEvidence: ${check.artifact}` : ''}`).join('\n\n')}`);
    return lines.join('\n\n');
  }
  function renderEvidenceFiles(selected) {
    const list = $('#evidence-files'); list.replaceChildren(); list.append(el('h3','','Saved evidence'));
    const overview = el('button','artifact-button'); overview.append(icon('layers'),el('span','','Run overview')); overview.setAttribute('aria-current',String(!selected)); overview.addEventListener('click',() => showOverview()); list.append(overview);
    for (const artifact of artifactList()) {
      const name = artifactName(artifact), button = el('button','artifact-button'); button.append(icon('file'),el('span','',name)); button.setAttribute('aria-current',String(name === selected)); button.addEventListener('click',() => loadArtifact(name)); list.append(button);
    }
  }
  function showEvidence(title,text,description = '',selection = null) {
    S.artifactRequest++; S.evidence = null; S.evidenceView = selection ? 'file' : title === 'Run overview' ? 'overview' : 'record';
    setText('#evidence-title','Evidence'); setText('#evidence-name',title); setText('#evidence-description',description); setText('#evidence-text',text);
    $('#evidence-text').dataset.error = 'false'; $('#evidence-download').hidden = true;
    renderEvidenceFiles(selection);
    if (S.layout !== 'ultrawide' || !$('#inspection-dock')) openDialog('evidence-dialog');
    else $('#evidence-surface').scrollIntoView({block:'nearest',behavior:'auto'});
  }
  function showOverview() { showEvidence('Run overview',evidenceOverview(),'Recorded results and the identity of the preserved changes.'); }
  async function loadArtifact(name) {
    if (!S.run) return;
    const runId = S.run.id, selection = S.selection;
    showEvidence(name,'Opening saved evidence…','',name);
    const request = ++S.artifactRequest;
    try {
      const text = await api(`/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(name)}`,{plain:true});
      if (request !== S.artifactRequest || selection !== S.selection) return;
      const meta = artifactList().find(item => artifactName(item) === name);
      S.evidence = {name,text}; setText('#evidence-text',text || '(This saved file is empty.)');
      setText('#evidence-description',[bytes(meta?.size_bytes),meta?.sha256 ? `SHA-256 ${meta.sha256}` : ''].filter(Boolean).join(' · '));
      $('#evidence-download').hidden = false;
    } catch (error) { if (request === S.artifactRequest) { setText('#evidence-text',error.message); $('#evidence-text').dataset.error = 'true'; } }
  }
  function openEvent(event) {
    let detail = '';
    if (event.detail !== undefined && event.detail !== null) detail = typeof event.detail === 'string' ? event.detail : JSON.stringify(event.detail,null,2);
    showEvidence(`${roleTitle(event.actor)} · ${formatTime(event.timestamp)}`,[event.message,detail].filter(Boolean).join('\n\n'),`${formatDate(event.timestamp)} · ${event.kind || 'event'}`);
  }
  function openReview(type) {
    const review = S.run?.reviews?.[type]; if (!review) return;
    if (review.artifact) { loadArtifact(review.artifact); return; }
    showEvidence(type === 'plan' ? 'Plan review' : 'Final review',`${review.approved === true ? 'APPROVED' : 'CHANGES REQUIRED'}\n\n${review.summary || ''}\n\n${(review.issues || []).map(issue => `• ${issue}`).join('\n')}`,'Recorded architect decision.');
  }
  function openWorker(name) {
    if (!S.run) return;
    const worker = S.run.workers?.[name] || {};
    const matches = S.events.filter(event => event.actor === name || (name === 'audit' && ['auditor','checks','test','runtime'].includes(event.actor)));
    let text = `${roleTitle(name)}\n${worker.message || ''}`;
    if (name === 'audit') text += `\n\n${(S.run.checks || []).map(check => `${check.name || 'Check'} · ${check.status || 'unknown'}\n${check.message || ''}${check.artifact ? `\nEvidence file: ${check.artifact}` : ''}`).join('\n\n')}`;
    text += `\n\n${matches.map(event => `${formatTime(event.timestamp)} · ${event.message}`).join('\n\n')}`;
    showEvidence(roleTitle(name),text.trim(),'Open a saved file for the complete source or check output.');
  }
  function downloadText(name,text) {
    const blob = new Blob([text],{type:'text/plain;charset=utf-8'}), url = URL.createObjectURL(blob);
    const link = el('a'); link.href = url; link.download = name.split(/[\\/]/).at(-1) || 'evidence.txt'; link.hidden = true; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
  }
  async function downloadPatch() {
    const artifact = finalPatch(); if (!artifact || !S.run) return;
    const name = artifactName(artifact), id = S.run.id, button = $('#download-patch-button'); button.disabled = true;
    try { const text = await api(`/runs/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(name)}`,{plain:true}); downloadText(`swarm-${id.slice(0,8)}-${name}`,text); toast('Saved patch downloaded.'); }
    catch (error) { toast(error.message); }
    finally { button.disabled = false; }
  }


  // Harmless display preferences are the only values written to browser storage.
  function readPreference(key, allowed, fallback) { try { const value = localStorage.getItem(key); return allowed.includes(value) ? value : fallback; } catch (_) { return fallback; } }
  function savePreference(key, value) { try { localStorage.setItem(key,value); } catch (_) { toast('Your browser cannot save preferences. This choice still works for the open page.'); } }
  const THEME_NAMES = ['system','dark','light','contrast'];
  const LAYOUT_NAMES = {phone:'iPhone',tablet:'iPad',desktop:'Desktop',wide:'Widescreen',ultrawide:'Ultrawide'};
  const LAYOUT_DESCRIPTIONS = {
    phone:'RATBAG welcomes you to Work and your More menu. Work, Team, and Activity stay focused, with important controls within reach.',
    tablet:'RATBAG and your projects share a touch-friendly shelf above separate work and team panes.',
    desktop:'A dedicated RATBAG and project rail beside the complete Architect, Builder, workers, and Activity overview.',
    wide:'Project, work, and review lanes let you follow the task and its checks side by side.',
    ultrawide:'A permanent evidence desk beside the work. Open plans, checks, and patches without covering the Builder.'
  };
  let COMPONENTS = {};
  function autoLayout() {
    const width = window.innerWidth, height = window.innerHeight, shortSide = Math.min(width,height);
    const coarse = matchMedia('(pointer:coarse)').matches;
    if (width < 600 || ((coarse || /iPhone|iPod/i.test(navigator.userAgent)) && shortSide < 600)) return 'phone';
    if (width < 1200 || (coarse && shortSide <= 1100 && Math.max(width,height) < 1450)) return 'tablet';
    if (width >= 2600) return 'ultrawide';
    if (width >= 1800) return 'wide';
    return 'desktop';
  }
  function applyTheme() {
    const resolved = S.preferenceTheme === 'system' ? (matchMedia('(prefers-color-scheme:light)').matches ? 'light' : 'dark') : S.preferenceTheme;
    document.documentElement.dataset.theme = resolved; $('#theme-select').value = S.preferenceTheme;
    $('meta[name=theme-color]').content = resolved === 'light' ? '#f2f4f8' : resolved === 'contrast' ? '#000000' : '#101318';
  }
  function lane(className, label, children, showLabel = false) {
    const node = el('section',`lane ${className}`); node.setAttribute('aria-label',label);
    if (showLabel) node.append(el('h2','lane-title',label));
    children.filter(Boolean).forEach(child => node.append(child)); return node;
  }
  function composeLayout(force = false) {
    const profile = S.preferenceLayout === 'auto' ? autoLayout() : S.preferenceLayout;
    const orientation = innerWidth > innerHeight ? 'landscape' : 'portrait';
    if (!force && profile === S.layout && orientation === S.orientation) return;
    S.layout = profile; S.orientation = orientation;
    document.documentElement.dataset.layout = profile; document.documentElement.dataset.orientation = orientation;
    const host = $('#layout-host'), parking = $('#component-parking'), menu = $('#menu-dialog'), brandRail = $('#brand-rail'), C = COMPONENTS;
    if (!C.lead) return;
    if (menu?.open && profile === 'phone') { S.phoneTab = 'more'; menu.close(); }
    // Move the existing live controls; no duplicated IDs, models, or independent display state.
    Object.entries(C).forEach(([name,node]) => { if (!['evidence','controls'].includes(name)) parking.append(node); });
    if (!$('#evidence-dialog').open) $('#evidence-dialog').append(C.evidence);
    $('#desktop-controls').append(C.controls); host.replaceChildren(); brandRail.replaceChildren();
    if (profile === 'phone') {
      for (const [tab,label,children] of [
        ['work','Current work',[C.brand,C.lead,C.routing,C.outcome]],['team','Team and reviews',[C.architect,C.workers]],
        ['activity','Run activity',[C.activity]],['more','Workspace tools',[C.more,C.project,C.inspection]]
      ]) { const panel = lane(`phone-panel${tab === 'work' ? ' work-lane' : ''}`,label,children); panel.dataset.phonePanel = tab; host.append(panel); }
      $('#phone-actions').append(C.controls); $('#phone-dock').hidden = false; activatePhoneTab(S.phoneTab,false);
    } else if (profile === 'tablet') {
      host.append(lane('tablet-project','RATBAG and project shelf',[C.brand,C.project]),lane('work-lane','Work and activity',[C.lead,C.routing,C.outcome,C.activity]),lane('team-lane','Team and review',[C.architect,C.workers,C.inspection]));
    } else if (profile === 'desktop') {
      brandRail.append(...[C.brand,C.project].filter(Boolean));
      host.append(lane('left-lane','Architect',[C.architect]),lane('work-lane','Build and check',[C.lead,C.routing,C.workers,C.outcome]),lane('desktop-activity','Activity',[C.activity]));
    } else if (profile === 'wide') {
      host.append(lane('left-lane','RATBAG and projects',[C.brand,C.project]),lane('work-lane','Current work',[C.lead,C.routing,C.workers,C.outcome,C.activity]),lane('review-lane','Review',[C.architect,C.inspection],true));
    } else {
      const dock = el('section','inspection-dock'); dock.id = 'inspection-dock'; dock.setAttribute('aria-label','Permanent evidence desk');
      if (!$('#evidence-dialog').open) dock.append(C.evidence);
      host.append(lane('left-lane','RATBAG, projects, and saved checks',[C.brand,C.project,C.inspection]),lane('work-lane','Current work',[C.lead,C.routing,C.workers,C.outcome,C.activity]),lane('review-lane','Review and evidence',[C.architect,dock],true));
      if (S.evidenceView === 'overview') updateDockOverview();
    }
    if (menu?.open) menu.prepend(C.more);
    if (profile !== 'phone') $('#phone-dock').hidden = true;
    $('#layout-select').value = S.preferenceLayout;
    setText('#layout-caption',`${LAYOUT_NAMES[profile]} workspace`);
    setText('#layout-description',LAYOUT_DESCRIPTIONS[profile]);
    const preview = $('#layout-preview'); preview.dataset.profile = profile; preview.replaceChildren(...Array.from({length:profile === 'phone' || profile === 'tablet' ? 2 : 3},() => el('span')));
    setText('#inspection-title',profile === 'ultrawide' ? 'Saved checks' : 'Review desk');
  }
  function activatePhoneTab(tab, scroll = true) {
    S.phoneTab = ['work','team','activity','more'].includes(tab) ? tab : 'work';
    document.documentElement.dataset.phoneView = S.phoneTab;
    if (S.layout === 'phone' && COMPONENTS.brand) {
      const target = S.phoneTab === 'more' ? COMPONENTS.more : $('[data-phone-panel=work]');
      if (target) target.prepend(COMPONENTS.brand);
      COMPONENTS.brand.dataset.presentation = S.phoneTab === 'more' ? 'menu' : 'work';
    }
    $$('[data-phone-panel]').forEach(panel => { panel.hidden = panel.dataset.phonePanel !== S.phoneTab; });
    $$('[data-phone-tab]').forEach(button => { if (button.dataset.phoneTab === S.phoneTab) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current'); });
    if (scroll && S.layout === 'phone') window.scrollTo({top:0,behavior:'auto'});
  }
  function updateDockOverview() {
    if (S.evidenceView !== 'overview') return;
    setText('#evidence-name','Run overview'); setText('#evidence-text',S.run ? evidenceOverview() : 'Select a task from History or start a new one. Its saved plans, changes, and checks will appear here.');
    setText('#evidence-description',S.run ? 'Recorded results and the identity of the preserved changes.' : 'The evidence desk stays beside your work on ultrawide screens.');
    renderEvidenceFiles(null); $('#evidence-download').hidden = true;
  }
  function renderInspection() {
    const checks = Array.isArray(S.run?.checks) ? S.run.checks : [], list = $('#inspection-checks'), files = $('#inspection-files');
    if (!list) return;
    list.replaceChildren(); files.replaceChildren();
    setText('#inspection-summary',S.run ? `${checks.length} recorded check${checks.length === 1 ? '' : 's'} · ${artifactList().length} saved file${artifactList().length === 1 ? '' : 's'}` : 'The receipts stay with the work.');
    for (const check of checks.slice(-4)) {
      const state = check.status || (check.passed === true ? 'passed' : check.passed === false ? 'failed' : 'recorded');
      const row = el('div','inspection-check'); row.dataset.state = state;
      const label = el('span','',check.name || 'Check'); label.append(el('small','',state === 'passed' ? 'Passed' : state === 'failed' ? 'Failed' : state));
      row.append(icon(state === 'passed' ? 'check' : state === 'failed' ? 'close' : 'file'),label); list.append(row);
    }
    if (!checks.length) list.append(el('p','empty-copy',S.run ? 'Checks will appear as the run progresses.' : 'Start a task to collect real check results.'));
    for (const artifact of artifactList().slice(-4)) { const name = artifactName(artifact), button = el('button','artifact-button'); button.append(icon('file'),el('span','',name)); button.addEventListener('click',() => loadArtifact(name)); files.append(button); }
    $$('[data-action=evidence]').forEach(button => { button.disabled = !S.run; });
    if (S.layout === 'ultrawide') updateDockOverview();
  }
  function optionNode(value,label) { const node = el('option','',label); node.value = value; return node; }
  function renderProjectChoices() {
    for (const id of ['workspace-project','onboarding-project','task-project']) {
      const select = document.getElementById(id), previous = select.value || S.projectId;
      select.replaceChildren(optionNode('',S.projects.length ? 'Choose a project' : 'No projects listed yet'));
      for (const project of S.projects) select.append(optionNode(project.id,`${project.name}${project.kind === 'sample' ? ' · practice' : ''}`));
      if (id === 'task-project') select.append(optionNode('custom','Advanced — enter a server folder'));
      if ([...select.options].some(option => option.value === previous)) select.value = previous;
    }
    renderProjectShortcuts();
  }
  function renderProjectShortcuts() {
    const list = $('#project-short-list'); list.replaceChildren();
    if (!S.projects.length) list.append(el('p','empty-copy','No projects listed yet. Create a practice project or open Projects to use a server folder.'));
    for (const project of S.projects.slice(0,5)) {
      const button = el('button','project-shortcut'), text = el('span','',project.name); text.append(el('small','',project.kind === 'sample' ? 'Practice project' : project.path));
      button.setAttribute('aria-current',String(S.projectId === project.id)); button.append(icon('folder'),text);
      button.addEventListener('click',async () => { await chooseProject(project.id); toast(`${project.name} selected for your next task.`); }); list.append(button);
    }
  }
  function renderProjectList() {
    const list = $('#project-list'), query = $('#project-search').value.toLowerCase().trim(); list.replaceChildren();
    const projects = S.projects.filter(item => `${item.name} ${item.path}`.toLowerCase().includes(query));
    if (!projects.length) list.append(el('p','empty-copy',S.projects.length ? 'No matching projects. Try a shorter name or folder.' : 'No projects have been found in the configured folders yet. Create a practice project to get started.'));
    for (const project of projects) {
      const button = el('button','project-list-entry'), copy = el('span'); copy.append(el('strong','',project.name),el('small','',project.path));
      button.setAttribute('aria-current',String(S.projectId === project.id)); button.append(icon('folder'),copy,icon('chevron-right'));
      button.addEventListener('click',async () => { if (await chooseProject(project.id)) { closeDialog('projects-dialog'); openTask(); } }); list.append(button);
    }
    const roots = S.projectRoots.map(root => `${root.path}${root.available ? '' : ' (unavailable)'}`);
    setText('#project-roots-note',roots.length ? `Scanned folders: ${roots.join(', ')}. If your project is elsewhere, use its full server path.` : 'If your project is elsewhere, enter its full server folder path in a new task.');
  }
  async function refreshProjects() { const result = await api('/projects'); S.projects = result.projects || []; S.projectRoots = result.roots || []; renderProjectChoices(); renderProjectList(); }
  async function chooseProject(id) {
    const request = ++S.projectRequest;
    if (!id) { S.project = null; S.projectId = ''; renderProjectChoices(); return false; }
    try {
      const result = await api(`/projects/${encodeURIComponent(id)}`);
      if (request !== S.projectRequest) return false;
      S.project = result.project; S.projectId = id; renderProjectChoices(); renderProjectList();
      setText('#onboarding-project-note',[S.project.path,S.project.branch ? `Branch ${S.project.branch}` : '',...(S.project.notes || [])].filter(Boolean).join(' · '));
      return true;
    } catch (error) { toast(error.message); formError($('#projects-error'),error.message); return false; }
  }
  async function createSample() {
    if (S.creatingSample) return;
    S.creatingSample = true; $$('[data-action=sample]').forEach(button => { button.disabled = true; });
    try {
      const result = await api('/projects/sample',{method:'POST',body:{},timeout:30000});
      S.sampleTask = result.suggested_task; await refreshProjects(); await chooseProject(result.project.id);
      toast('Practice project created. Its first task is ready to review.');
      if ($('#onboarding-dialog').open) { if (S.setupStep < 1) setSetupStep(1); }
      else { if ($('#projects-dialog').open) closeDialog('projects-dialog'); closeMenu(); await openTask(); }
    } catch (error) { toast(error.message); formError($('#projects-error'),error.message); if ($('#onboarding-dialog').open) formError($('#onboarding-error'),error.message); }
    finally { S.creatingSample = false; $$('[data-action=sample]').forEach(button => { button.disabled = false; }); }
  }
  function fillTaskChecks(project) {
    S.taskProject = project; const select = $('#task-checks'); select.replaceChildren();
    const options = project?.test_options || [];
    for (const check of options) select.append(optionNode(check.id,`${check.label}${check.id === project.recommended_test_id ? ' · recommended' : ''}`));
    if (!options.length) select.append(optionNode('','Let RATBAG inspect the project'));
    select.append(optionNode('custom','Advanced — use my own check command'));
    select.value = project?.recommended_test_id || options[0]?.id || ''; updateTaskCheck();
  }
  async function updateTaskProject(id) {
    const request = (S.taskProjectRequest || 0) + 1; S.taskProjectRequest = request;
    const custom = id === 'custom'; $('#task-custom-path').hidden = !custom; $('#task-form').elements.repo_path.required = custom;
    if (custom || !id) { fillTaskChecks(null); return; }
    try {
      const result = S.project?.id === id ? {project:S.project} : await api(`/projects/${encodeURIComponent(id)}`);
      if (request !== S.taskProjectRequest) return;
      fillTaskChecks(result.project); setText('#task-project-help',result.project.path);
    } catch (error) { if (request === S.taskProjectRequest) { fillTaskChecks(null); formError($('#task-form-error'),error.message); } }
  }
  function updateTaskCheck() {
    const choice = $('#task-checks').value, custom = choice === 'custom'; $('#task-custom-check').hidden = !custom;
    $('#task-form').elements.test_command.required = custom;
    const check = S.taskProject?.test_options?.find(item => item.id === choice);
    setText('#task-check-help',custom ? 'Use a command already supported by this project.' : check ? [check.reason,check.command].filter(Boolean).join(' · ') : 'RATBAG will inspect the project settings. If it cannot choose safely, it will ask for a command.');
  }
  async function inspectCustomPath() {
    const path = $('#task-form').elements.repo_path.value.trim(); if (!path) { formError($('#task-form-error'),'Enter the project folder first.'); return; }
    const button = $('#inspect-project-button'); button.disabled = true; formError($('#task-form-error'),'');
    try { const result = await api('/projects/inspect',{method:'POST',body:{repo_path:path}}); fillTaskChecks(result.project); setText('#task-project-help',`Project found: ${result.project.name}`); }
    catch (error) { formError($('#task-form-error'),error.message); }
    finally { button.disabled = false; }
  }
  async function previewTaskRouter() {
    const mode = $('#task-routing').value, request = (S.taskRoutingRequest || 0) + 1; S.taskRoutingRequest = request; S.taskRoutingError = ''; S.taskRouter = null;
    renderTaskReadiness();
    try { const result = await api(`/router?mode=${encodeURIComponent(mode)}`); if (request === S.taskRoutingRequest) { S.taskRouter = result; renderTaskReadiness(); } }
    catch (error) { if (request === S.taskRoutingRequest) { S.taskRoutingError = error.message; renderTaskReadiness(); } }
  }
  function renderTaskReadiness() {
    const node = $('#task-readiness'); if (!node) return; node.replaceChildren();
    const mode = $('#task-routing').value, router = S.taskRouter?.mode === mode ? S.taskRouter : S.router?.mode === mode ? S.router : null;
    const ready = S.connected && !!router?.ready, checked = ready && !!router.assignments?.length && router.assignments.every(assignment => assignment.check?.ok === true);
    node.dataset.ready = String(ready); node.append(icon(ready ? 'check' : 'info'));
    let message;
    if (!S.connected) message = 'Connect to the server before starting.';
    else if (S.taskRoutingError) message = `The chosen team could not be checked: ${S.taskRoutingError}`;
    else if (S.health?.running_run_id) message = 'A task is active. Finish or stop it before starting a new one.';
    else if (!router) message = 'Reading the chosen team settings. This sends no model request.';
    else if (ready) message = checked ? 'The connections for this selected team have been checked.' : 'Keys for this selected team are available. You can check its connections in Models.';
    else if (router.failed_roles?.length) message = `A connection check failed for ${router.failed_roles.map(roleTitle).join(', ')}. Open Models to fix the account and check again.`;
    else message = `The selected team needs keys or enabled roles for ${(router.missing_roles || []).map(roleTitle).join(', ') || 'its models'}. Open Models to finish setup.`;
    node.append(el('span','',message));
    if (!ready) { const button = el('button','text-button','Open Models'); button.type = 'button'; button.addEventListener('click',() => { closeDialog('task-dialog'); openSettings('accounts'); }); node.append(button); }
  }
  function renderSetup() {
    if (!S.setup) return;
    $('#setup-card').hidden = S.setup.completed && S.setup.ready;
    setText('#setup-card-description',S.setup.ready ? (S.setup.verified ? 'Your core connections are checked. Pick a project and start a task.' : 'Your keys are available. Finish setup or check the connections in Models.') : 'Pick a project, connect your accounts, and choose your team.');
    setText('#routing-mode-label',S.setup.routing_mode === 'manual' ? 'Manual routing' : 'Smart routing');
    renderTaskReadiness(); applySettingsLocks();
  }
  function accountStatus(account) {
    if (account.checked && account.status === 'ready') return ['Connection checked','ready'];
    if (account.status === 'failed' || account.status === 'error' || account.failed || (account.key_present && /fail|expired|rejected/i.test(account.status || ''))) return ['Check failed','failed'];
    if (account.status === 'disabled') return ['Role disabled','missing'];
    return account.key_present ? ['Key saved · not checked','saved'] : ['Key needed','missing'];
  }
  function renderAccounts() {
    for (const id of ['account-fields','onboarding-account-fields']) {
      const container = document.getElementById(id);
      if ($$('input',container).some(input => input.value) || container.contains(document.activeElement)) continue;
      container.replaceChildren();
      for (const account of S.setup?.accounts || []) {
        if (account.id === 'router') continue;
        const entry = el('section','account-entry'); entry.dataset.account = account.id;
        const heading = el('div','account-heading'), state = accountStatus(account), label = el('span','',state[0]); label.dataset.state = state[1];
        heading.append(el('strong','',account.label),label); entry.append(heading);
        entry.append(field(`${account.label} API key`,account.id,{type:'password',value:'',placeholder:account.key_present ? 'Key available · leave blank to keep it' : 'Paste your provider key here'}));
        entry.append(el('p','field-help',(account.message || '').replaceAll('Check core models','Check connections') || (account.id === 'glm' ? 'One key for both Architect and Auditor. Uses the requested Z.ai Coding endpoint.' : `Used by ${account.id === 'deepseek' ? 'the Builder' : 'both Scouts'}.`)));
        container.append(entry);
      }
    }
    applySettingsLocks();
  }
  function applySettingsLocks() {
    const locked = S.checkingAccounts || S.advancingSetup || S.setup?.can_change_settings === false;
    for (const container of [$('#account-fields'),$('#onboarding-account-fields')]) $$('input',container).forEach(input => { input.disabled = locked; });
    for (const id of ['save-accounts-button','check-accounts-button','apply-routing-button','routing-select','onboarding-routing','onboarding-check-accounts']) $('#'+id).disabled = locked;
    $$('.provider-form').forEach(form => {
      $$('input,select,button',form).forEach(input => { input.disabled = locked || (input.name === 'protocol' && /^glm-/i.test(form.elements.model_id.value)); });
      const check = $$('button',form).find(button => button.type === 'button'); if (check && form.dataset.dirty === 'true') check.disabled = true;
    });
    $('#onboarding-next').disabled = S.checkingAccounts || S.advancingSetup; $('#onboarding-back').disabled = S.checkingAccounts || S.advancingSetup;
    setText('#model-settings-note',S.advancingSetup ? 'Finishing this setup step. Settings reopen when it finishes.' : locked ? 'Settings are locked while a task or connection check is active. They reopen when it finishes.' : 'Your run history and saved evidence stay available.');
  }
  async function refreshSetupSafely() {
    try { const [setup,providers,router] = await Promise.all([api('/setup'),api('/providers'),api('/router')]); S.setup = setup; S.providers = providers.providers || S.providers; S.router = router; renderSetup(); renderAccounts(); renderRouter(); }
    catch (error) { toast(error.message); }
  }
  async function saveAccounts(containerId = 'account-fields',feedbackId = 'account-feedback') {
    const container = document.getElementById(containerId), feedback = document.getElementById(feedbackId), values = {};
    $$('input[type=password]',container).forEach(input => { if (input.value.trim()) values[input.name] = input.value.trim(); });
    feedback.dataset.error = 'false'; feedback.dataset.success = 'false';
    try {
      if (Object.keys(values).length) {
        feedback.textContent = 'Saving accounts…'; const result = await api('/setup/accounts',{method:'PUT',body:values}); S.setup = result.setup;
        $$('input[type=password]',container).forEach(input => { input.value = ''; });
        feedback.textContent = 'Accounts saved. No model request was sent.'; feedback.dataset.success = 'true';
      } else { S.setup = await api('/setup'); feedback.textContent = 'Existing account keys kept. No model request was sent.'; }
      renderSetup(); renderAccounts(); await refreshSetupSafely(); return true;
    } catch (error) { feedback.dataset.error = 'true'; feedback.textContent = error.message; return false; }
    finally { for (const key of Object.keys(values)) delete values[key]; }
  }
  async function checkAccounts(onboarding = false) {
    if (S.checkingAccounts) return false;
    S.checkingAccounts = true; applySettingsLocks();
    const containerId = onboarding ? 'onboarding-account-fields' : 'account-fields', feedbackId = onboarding ? 'onboarding-account-feedback' : 'account-feedback';
    if (!await saveAccounts(containerId,feedbackId)) { S.checkingAccounts = false; applySettingsLocks(); return false; }
    const feedback = document.getElementById(feedbackId); S.checkingAccounts = true; applySettingsLocks();
    feedback.dataset.error = 'false'; feedback.dataset.success = 'false'; feedback.textContent = 'Checking Architect, Builder, Scout, and Auditor connections. Keep this page open; provider response times vary.';
    try {
      const result = await api('/providers/check-core',{method:'POST',body:{},timeout:620000}); S.setup = result.setup;
      feedback.dataset.success = String(result.ok === true); feedback.dataset.error = String(result.ok !== true);
      feedback.textContent = Object.entries(result.results || {}).map(([role,check]) => `${roleTitle(role)}: ${check.ok ? 'connected' : 'connection failed'}${check.message ? ` — ${check.message}` : ''}`).join('\n');
      await refreshSetupSafely(); return result.ok === true;
    } catch (error) { feedback.dataset.error = 'true'; feedback.textContent = error.message; return false; }
    finally { S.checkingAccounts = false; await refreshSetupSafely(); applySettingsLocks(); }
  }
  function assignmentNodes(router) {
    return (router?.assignments || []).map(assignment => {
      const role = ROLE_INFO[assignment.role] || {title:assignment.role,icon:'route'}, row = el('div','routing-assignment'), badge = el('span','role-icon'); badge.append(icon(role.icon));
      const title = el('div'); title.append(el('h3','',role.title),el('div','model-name',assignment.model_id));
      const reason = el('p','',assignment.reason || 'Uses your saved role settings.');
      if (assignment.enabled === false) reason.append(el('span','key-missing','Role disabled · enable it in Models, Advanced'));
      else if (!assignment.key_present) reason.append(el('span','key-missing','Account key needed'));
      else if (assignment.check?.ok === false) reason.append(el('span','key-missing','Connection check failed · review this account'));
      row.append(badge,title,reason); return row;
    });
  }
  function renderRouter(router = S.router, target = null) {
    for (const id of target ? [target] : ['routing-assignments','onboarding-assignments']) document.getElementById(id).replaceChildren(...assignmentNodes(router));
    if (!target && !$('#settings-dialog').open) $('#routing-select').value = S.setup?.routing_mode || 'smart';
  }
  async function previewRouter(mode,target) {
    const generation = (S.routerRequest || 0) + 1; S.routerRequest = generation;
    try { const result = await api(`/router?mode=${encodeURIComponent(mode)}`); if (generation === S.routerRequest) renderRouter(result,target); }
    catch (error) { toast(error.message); }
  }
  async function applyRouter(mode,feedbackId = 'routing-feedback') {
    const feedback = document.getElementById(feedbackId); if (feedback) { feedback.dataset.error = 'false'; feedback.textContent = 'Saving routing…'; }
    try {
      const result = await api('/router/apply',{method:'POST',body:{mode}}); S.router = result.router; S.setup = result.setup; S.providers = result.providers || S.providers;
      renderRouter(); renderSetup(); renderProviders(); renderRun();
      if (feedback) { feedback.dataset.success = 'true'; feedback.textContent = 'Routing saved. No model request was sent.'; } return true;
    } catch (error) { if (feedback) { feedback.dataset.error = 'true'; feedback.textContent = error.message; } return false; }
  }
  function setSettingsTab(tab) {
    S.settingsTab = ['accounts','routing','advanced'].includes(tab) ? tab : 'accounts';
    $$('[data-settings-panel]').forEach(panel => { panel.hidden = panel.dataset.settingsPanel !== S.settingsTab; });
    $$('[data-settings-tab]').forEach(button => { if (button.dataset.settingsTab === S.settingsTab) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current'); });
  }
  async function openSettings(tab = 'accounts') {
    closeMenu(); setSettingsTab(tab); openDialog('settings-dialog'); formError($('#settings-error'),'');
    try { const [providers,setup,router,catalog] = await Promise.all([api('/providers'),api('/setup'),api('/router'),api('/models/catalog')]); S.providers = providers.providers || {}; S.setup = setup; S.router = router; S.catalog = catalog.models || []; renderAccounts(); renderProviders(); renderSetup(); renderRouter(); $('#routing-select').value = S.setup.routing_mode || 'smart'; }
    catch (error) { formError($('#settings-error'),error.message); }
  }
  function setSetupStep(step) {
    S.setupStep = Math.max(0,Math.min(4,step)); formError($('#onboarding-error'),'');
    $$('[data-setup-step]').forEach(panel => { panel.hidden = Number(panel.dataset.setupStep) !== S.setupStep; });
    $$('[data-step-label]').forEach(label => { const index = Number(label.dataset.stepLabel); label.dataset.number = String(index + 1); label.dataset.completed = String(index < S.setupStep); if (index === S.setupStep) label.setAttribute('aria-current','step'); else label.removeAttribute('aria-current'); });
    $('#onboarding-back').hidden = S.setupStep === 0; setButtonLabel($('#onboarding-next'),S.setupStep === 4 ? 'Create first task' : S.setupStep === 0 ? 'Get started' : 'Continue');
    setText('#onboarding-eyebrow',S.setupStep === 0 ? 'WELCOME TO RATBAG' : `GUIDED SETUP · STEP ${S.setupStep + 1} OF 5`);
    $('#onboarding-dialog .dialog-body').scrollTop = 0;
    if (S.setupStep === 3) { $('#onboarding-routing').value = S.setup?.routing_mode || 'smart'; previewRouter($('#onboarding-routing').value,'onboarding-assignments'); }
    if (S.setupStep === 4) {
      const summary = $('#onboarding-summary'); summary.replaceChildren();
      const checks = S.project?.test_options?.find(check => check.id === S.project.recommended_test_id);
      for (const [label,value] of [['Project',S.project?.name || 'Choose a project'],['Accounts',S.setup?.verified ? 'All core connections checked' : 'Keys available · connections not yet checked'],['Routing',S.setup?.routing_mode === 'manual' ? 'Your saved role settings' : 'Recommended smart team'],['Checks',checks?.label || 'Inspect project settings']]) { const row = el('div'); row.append(el('dt','',label),el('dd','',value)); summary.append(row); }
    }
  }
  function openSetup() {
    closeMenu(); if ($('#help-dialog').open) closeDialog('help-dialog');
    S.setupOpened = true; setSetupStep(0); renderAccounts(); renderProjectChoices(); openDialog('onboarding-dialog');
  }
  function setupReadinessIssue() {
    const failed = S.setup?.failed_roles || [], missing = S.setup?.missing_roles || [];
    const disabled = missing.filter(role => S.providers[role]?.enabled === false), keys = missing.filter(role => !disabled.includes(role));
    const issues = [];
    if (keys.length) issues.push(`Add account keys for ${keys.map(roleTitle).join(', ')} here, then Continue.`);
    if (failed.length) issues.push(`A connection check failed for ${failed.map(roleTitle).join(', ')}. Update the account and choose Check connections again.`);
    if (disabled.length) issues.push(`Enable ${disabled.map(roleTitle).join(', ')} in Models, Advanced, or restore Smart routing in Models, Routing.`);
    return issues.join(' ') || 'The selected team is not ready yet. Open Models to review its settings.';
  }
  async function nextSetupStep() {
    if (S.advancingSetup || S.checkingAccounts) return;
    S.advancingSetup = true; applySettingsLocks(); formError($('#onboarding-error'),'');
    try {
      if (S.setupStep === 1) { if (!$('#onboarding-project').value || !await chooseProject($('#onboarding-project').value)) throw new Error('Choose a project, or press Create practice project for your first run.'); }
      if (S.setupStep === 2) {
        if (!await saveAccounts('onboarding-account-fields','onboarding-account-feedback')) return;
        if (!S.setup?.ready) throw new Error(setupReadinessIssue());
      }
      if (S.setupStep === 3) {
        if (!await applyRouter($('#onboarding-routing').value,'onboarding-account-feedback')) throw new Error('Routing could not be saved. Open Models to review the current settings, then try again.');
        if (!S.router?.ready || !S.setup?.ready) { setSetupStep(2); renderAccounts(); throw new Error(`Routing saved. ${setupReadinessIssue()}`); }
      }
      if (S.setupStep === 4) {
        const result = await api('/setup/complete',{method:'POST',body:{}}); S.setup = result.setup; renderSetup(); closeDialog('onboarding-dialog'); await openTask(); return;
      }
      setSetupStep(S.setupStep + 1);
    } catch (error) { formError($('#onboarding-error'),error.message); }
    finally { S.advancingSetup = false; applySettingsLocks(); }
  }
  function closeMenu() { const menu = $('#menu-dialog'); if (menu?.open) menu.close(); }
  function restoreMenuContent() {
    const menu = $('#menu-dialog');
    if (menu && !menu.open && COMPONENTS.more.parentNode === menu) $('#component-parking').append(COMPONENTS.more);
  }
  function openMenu() {
    if (S.layout === 'phone') { activatePhoneTab('more'); return; }
    let dialog = $('#menu-dialog');
    if (!dialog) {
      dialog = el('dialog','modal'); dialog.id = 'menu-dialog'; dialog.setAttribute('aria-label','App menu');
      const close = el('button','button quiet','Close menu'); close.addEventListener('click',() => dialog.close()); const footer = el('div','dialog-footer'); footer.append(close); dialog.append(footer); document.body.append(dialog);
      dialog.addEventListener('close',restoreMenuContent);
    }
    dialog.prepend(COMPONENTS.more); openDialog('menu-dialog');
  }
  async function action(name) {
    if (name !== 'menu') closeMenu();
    if (name === 'new') return openTask();
    if (name === 'projects') { renderProjectList(); openDialog('projects-dialog'); try { await refreshProjects(); } catch (error) { formError($('#projects-error'),error.message); } }
    if (name === 'history') { renderHistory(); openDialog('history-dialog'); try { await refreshRuns(); } catch (error) { toast(error.message); } }
    if (name === 'models' || name === 'routing') return openSettings(name === 'routing' ? 'routing' : 'accounts');
    if (name === 'appearance') openDialog('appearance-dialog');
    if (name === 'help') openDialog('help-dialog');
    if (name === 'setup') openSetup();
    if (name === 'sample') return createSample();
    if (name === 'evidence' && S.run) showOverview();
    if (name === 'menu') openMenu();
  }

  fillIcons();
  COMPONENTS = {brand:$('#ratbag-brand'),project:$('#project-card'),architect:$('#architect-card'),lead:$('#lead-card'),routing:$('#routing-group'),workers:$('#workers'),outcome:$('#outcome-card'),activity:$('#activity-card'),inspection:$('#inspection-card'),more:$('#more-card'),evidence:$('#evidence-surface'),controls:$('#task-controls')};
  S.preferenceTheme = readPreference('swarm.theme',THEME_NAMES,'system');
  S.preferenceLayout = readPreference('swarm.layout',['auto',...Object.keys(LAYOUT_NAMES)],'auto');
  applyTheme(); composeLayout(true);

  $$('[data-close]').forEach(button => button.addEventListener('click',() => closeDialog(button.dataset.close)));
  document.addEventListener('invalid',event => { const details = event.target.closest('details'); if (details) details.open = true; },true);
  document.addEventListener('click',event => { const button = event.target.closest('[data-action]'); if (button && !button.disabled) action(button.dataset.action).catch(error => toast(error.message)); });
  $('#new-task-button').addEventListener('click',() => openTask());
  $('#projects-button').addEventListener('click',() => action('projects'));
  $('#history-button').addEventListener('click',() => action('history'));
  $('#settings-button').addEventListener('click',() => openSettings());
  $('#help-button').addEventListener('click',() => action('help'));
  $('#appearance-button').addEventListener('click',() => action('appearance'));
  $$('[data-settings-tab]').forEach(button => button.addEventListener('click',() => setSettingsTab(button.dataset.settingsTab)));
  $$('[data-phone-tab]').forEach(button => button.addEventListener('click',() => activatePhoneTab(button.dataset.phoneTab)));
  $('#theme-select').addEventListener('change',event => { S.preferenceTheme = event.target.value; savePreference('swarm.theme',S.preferenceTheme); applyTheme(); });
  $('#layout-select').addEventListener('change',event => { S.preferenceLayout = event.target.value; savePreference('swarm.layout',S.preferenceLayout); composeLayout(true); announce(`${LAYOUT_NAMES[S.layout]} workspace selected.`); });
  matchMedia('(prefers-color-scheme:light)').addEventListener('change',() => { if (S.preferenceTheme === 'system') applyTheme(); });
  window.addEventListener('storage',event => { if (event.key === 'swarm.theme') { S.preferenceTheme = readPreference('swarm.theme',THEME_NAMES,'system'); applyTheme(); } else if (event.key === 'swarm.layout') { S.preferenceLayout = readPreference('swarm.layout',['auto',...Object.keys(LAYOUT_NAMES)],'auto'); composeLayout(true); } });
  let resizeTimer; window.addEventListener('resize',() => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => composeLayout(),100); });
  $('#workspace-project').addEventListener('change',event => chooseProject(event.target.value));
  $('#onboarding-project').addEventListener('change',event => chooseProject(event.target.value));
  $('#task-project').addEventListener('change',async event => { const value = event.target.value; await updateTaskProject(value); if (value && value !== 'custom') await chooseProject(value); });
  $('#task-checks').addEventListener('change',updateTaskCheck);
  $('#task-routing').addEventListener('change',previewTaskRouter);
  $('#project-search').addEventListener('input',renderProjectList);
  $('#refresh-projects-button').addEventListener('click',async () => { const button = $('#refresh-projects-button'); button.disabled = true; try { await refreshProjects(); formError($('#projects-error'),''); toast('Project list refreshed.'); } catch (error) { formError($('#projects-error'),error.message); } finally { button.disabled = false; } });
  $('#custom-project-button').addEventListener('click',async () => { closeDialog('projects-dialog'); await openTask(); $('#task-project').value = 'custom'; await updateTaskProject('custom'); $('#task-form').elements.repo_path.focus(); });
  const inspectButton = el('button','text-button','Inspect folder'); inspectButton.id = 'inspect-project-button'; inspectButton.type = 'button'; inspectButton.append(icon('arrow-right')); $('#task-custom-path').append(inspectButton); inspectButton.addEventListener('click',inspectCustomPath);
  const templates = {
    fix:'Fix the following problem: [describe what happens now].\n\nExpected result: [describe what should happen instead].\n\nAdd a focused check that proves the problem is fixed.',
    feature:'Add the following behavior: [describe the result].\n\nA good result should: [list the important details].\n\nKeep existing behavior working and add focused checks.',
    tests:'Improve checks for [name the feature].\n\nCover these cases: [describe the cases that matter].\n\nKeep the existing behavior unchanged.',
    clarity:'Make [name the feature or screen] easier to use.\n\nThe current problem is: [describe the friction].\n\nThe desired result is: [describe a clear, useful result].'
  };
  $('#task-template').addEventListener('change',event => {
    const template = templates[event.target.value], field = $('#task-form').elements.task;
    if (!template) return;
    if (!field.value.trim() || field.value === S.lastTemplate) { field.value = template; S.lastTemplate = template; field.focus(); const start = field.value.indexOf('['), end = field.value.indexOf(']'); if (start >= 0) field.setSelectionRange(start,end + 1); }
    else toast('Your existing draft is kept. Clear the Task field to insert a different starting point.');
  });
  $('#save-accounts-button').addEventListener('click',async () => { const button = $('#save-accounts-button'); button.disabled = true; try { await saveAccounts(); } finally { applySettingsLocks(); } });
  $('#check-accounts-button').addEventListener('click',() => checkAccounts());
  $('#onboarding-check-accounts').addEventListener('click',() => checkAccounts(true));
  $('#routing-select').addEventListener('change',event => previewRouter(event.target.value,'routing-assignments'));
  $('#onboarding-routing').addEventListener('change',event => previewRouter(event.target.value,'onboarding-assignments'));
  $('#apply-routing-button').addEventListener('click',async () => { const button = $('#apply-routing-button'); button.disabled = true; try { await applyRouter($('#routing-select').value); } finally { applySettingsLocks(); } });
  $('#onboarding-next').addEventListener('click',nextSetupStep);
  $('#onboarding-back').addEventListener('click',() => setSetupStep(S.setupStep - 1));
  $('#onboarding-skip').addEventListener('click',() => closeDialog('onboarding-dialog'));
  $('#settings-dialog').addEventListener('close',() => { $$('input[type=password]',$('#settings-dialog')).forEach(input => { input.value = ''; }); });
  $('#onboarding-dialog').addEventListener('close',() => { $$('input[type=password]',$('#onboarding-dialog')).forEach(input => { input.value = ''; }); });
  $('#access-dialog').addEventListener('close',() => { $('#access-form').elements.access_token.value = ''; });
  $('#evidence-dialog').addEventListener('close',() => { if (S.layout === 'ultrawide' && $('#inspection-dock')) $('#inspection-dock').append(COMPONENTS.evidence); else { S.artifactRequest++; S.evidence = null; } });
  $('#evidence-expand').addEventListener('click',() => { $('#evidence-dialog').append(COMPONENTS.evidence); openDialog('evidence-dialog'); });
  $('#connection-retry').addEventListener('click',async () => { $('#connection-retry').disabled = true; try { await bootstrap(); } finally { $('#connection-retry').disabled = false; } });
  $('#access-form').addEventListener('submit',async event => {
    event.preventDefault(); const form = event.currentTarget, button = $('button[type=submit]',form); button.disabled = true; formError($('#access-error'),'');
    S.token = form.elements.access_token.value.trim();
    try { S.health = await api('/health'); await api('/providers'); closeDialog('access-dialog'); await bootstrap(); }
    catch (error) { S.token = ''; formError($('#access-error'),error.message); }
    finally { button.disabled = false; }
  });
  $('#task-form').addEventListener('submit',async event => {
    event.preventDefault(); const form = event.currentTarget; if (!form.reportValidity()) return;
    const button = $('button[type=submit]',form); button.disabled = true; formError($('#task-form-error'),'');
    const values = {task:form.elements.task.value.trim(),symbol:form.elements.symbol.value.trim(),routing_mode:form.elements.routing_mode.value};
    if (Object.values(templates).includes(values.task) || /\[(?:describe|name|list) (?:the|a|what|this)/i.test(values.task)) { formError($('#task-form-error'),'Replace the bracketed prompts with your own instructions before starting.'); button.disabled = false; return; }
    if (form.elements.project_id.value === 'custom') values.repo_path = form.elements.repo_path.value.trim(); else values.project_id = form.elements.project_id.value;
    values.test_choice = form.elements.test_choice.value;
    if (values.test_choice === 'custom') values.test_command = form.elements.test_command.value.trim();
    for (const name of ['max_attempts','max_model_calls','test_timeout']) values[name] = Number(form.elements[name].value);
    try {
      const result = await api('/runs',{method:'POST',body:values,timeout:30000});
      closeDialog('task-dialog'); form.elements.task.value = ''; form.elements.task_template.value = 'custom'; S.lastTemplate = ''; upsertRun(result.run); await selectRun(result.run.id); activatePhoneTab('work'); await refreshRuns(); announce('Task started.');
    } catch (error) { formError($('#task-form-error'),error.message); if (error.status === 401) handleConnectionError(error); }
    finally { button.disabled = false; }
  });
  $('#pause-button').addEventListener('click',() => controlRun('pause',$('#pause-button')));
  $('#revise-button').addEventListener('click',() => openTask('revise'));
  $('#resume-button').addEventListener('click',() => controlRun('resume',$('#resume-button')));
  $('#cancel-button').addEventListener('click',() => controlRun('cancel',$('#cancel-button')));
  $('#view-evidence-button').addEventListener('click',showOverview);
  $('#routing-button').addEventListener('click',() => { if (S.run?.routing) showEvidence('Routing decision',JSON.stringify(S.run.routing,null,2),'The recorded rule or model-assisted choice. Duration is measured; confidence is not inferred.'); else openSettings('routing'); });
  $$('[data-review]').forEach(button => button.addEventListener('click',() => openReview(button.dataset.review)));
  $('#recovery-review-button').addEventListener('click',() => { const review = recoveryReview(); if (review) openEvent(review); });
  $$('[data-worker]').forEach(button => button.addEventListener('click',() => openWorker(button.dataset.worker)));
  $('#download-patch-button').addEventListener('click',downloadPatch);
  $('#evidence-download').addEventListener('click',() => { if (S.evidence) downloadText(S.evidence.name,S.evidence.text); });
  $('#earlier-events').addEventListener('click',() => { S.visibleEvents += 50; $('#follow-latest').checked = false; renderEvents(); $('#activity-list').scrollTop = 0; });
  $('#follow-latest').addEventListener('change',event => { if (event.target.checked) $('#activity-list').scrollTop = $('#activity-list').scrollHeight; });
  $('#activity-list').addEventListener('wheel',event => { if (event.deltaY < 0) $('#follow-latest').checked = false; },{passive:true});
  document.addEventListener('visibilitychange',() => { if (!document.hidden) poll(); });
  window.addEventListener('hashchange',() => { if (location.hash === '#setup') { openSetup(); return; } const id = new URLSearchParams(location.hash.slice(1)).get('run'); if (id && id !== S.selectedId) selectRun(id); });
  bootstrap();
  setInterval(poll,1500);
})();
