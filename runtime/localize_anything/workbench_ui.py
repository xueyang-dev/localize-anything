from __future__ import annotations


WORKBENCH_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Localize Anything Workbench</title>
  <link rel="icon" href="data:,">
  <style>
    :root {
      color-scheme: light;
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-subtle: #f1f5f9;
      --text: #0f172a;
      --muted: #475569;
      --line: #dbe3ec;
      --line-strong: #b7c3d0;
      --accent: #2563eb;
      --accent-hover: #1d4ed8;
      --accent-soft: #eff6ff;
      --success: #047857;
      --success-soft: #ecfdf5;
      --warning: #a16207;
      --warning-soft: #fffbeb;
      --danger: #b91c1c;
      --danger-soft: #fef2f2;
      --radius: 10px;
      --shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }
    * { box-sizing: border-box; }
    html { background: var(--bg); }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    button, input, select, textarea { font: inherit; }
    button, a, summary { cursor: pointer; }
    button {
      min-height: 44px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background: var(--surface);
      color: var(--text);
      padding: 0 14px;
      font-weight: 700;
      transition: background 160ms ease, border-color 160ms ease, color 160ms ease, box-shadow 160ms ease;
    }
    button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
    button.primary { border-color: var(--accent); background: var(--accent); color: #fff; }
    button.primary:hover:not(:disabled) { border-color: var(--accent-hover); background: var(--accent-hover); color: #fff; }
    button.danger { border-color: #fecaca; color: var(--danger); }
    button:disabled { cursor: not-allowed; opacity: .55; }
    :focus-visible { outline: 3px solid #93c5fd; outline-offset: 2px; }
    input, select, textarea {
      width: 100%;
      min-height: 44px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background: #fff;
      color: var(--text);
      padding: 10px 12px;
    }
    textarea { min-height: 92px; resize: vertical; }
    label { display: block; margin: 0 0 6px; font-size: 13px; font-weight: 750; }
    .field-error { min-height: 18px; margin: 4px 0 0; color: var(--danger); font-size: 12px; }
    .skip-link {
      position: fixed;
      top: 8px;
      left: 8px;
      z-index: 100;
      transform: translateY(-160%);
      border-radius: 8px;
      background: var(--text);
      color: #fff;
      padding: 10px 14px;
      font-weight: 750;
    }
    .skip-link:focus { transform: translateY(0); }
    .app-header { position: sticky; top: 0; z-index: 20; border-bottom: 1px solid var(--line); background: rgba(255,255,255,.96); }
    .header-row { max-width: 1240px; margin: 0 auto; min-height: 64px; padding: 0 22px; display: flex; align-items: center; gap: 24px; }
    .brand { display: flex; align-items: center; gap: 10px; min-width: 215px; font-weight: 820; }
    .brand-mark { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 8px; background: var(--accent); color: #fff; font-size: 12px; }
    .nav-wrap { min-width: 0; flex: 1; }
    .nav-links { display: flex; gap: 4px; overflow-x: auto; scrollbar-width: thin; }
    .nav-links a { min-height: 44px; display: inline-flex; align-items: center; padding: 0 12px; border-radius: 8px; color: var(--muted); text-decoration: none; font-weight: 700; white-space: nowrap; }
    .nav-links a:hover, .nav-links a[aria-current="page"] { background: var(--accent-soft); color: var(--accent); }
    .header-tools { display: flex; align-items: center; gap: 8px; }
    .health-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--warning); }
    .health-dot.pass { background: var(--success); }
    .context-strip { border-top: 1px solid var(--line); background: var(--surface-subtle); }
    .context-inner { max-width: 1240px; margin: 0 auto; min-height: 48px; padding: 6px 22px; display: flex; align-items: center; gap: 14px; overflow-x: auto; }
    .context-copy { min-width: 0; flex: 1; display: flex; align-items: baseline; gap: 10px; white-space: nowrap; }
    .context-copy strong { overflow: hidden; text-overflow: ellipsis; }
    .context-meta { color: var(--muted); font-size: 13px; white-space: nowrap; }
    .evidence-scope { margin-top: 6px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    .context-action { min-height: 36px; padding: 0 11px; }
    main { max-width: 1240px; margin: 0 auto; padding: 34px 22px 56px; }
    .page[hidden] { display: none; }
    .page-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; margin-bottom: 22px; }
    h1 { margin: 0; font-size: clamp(26px, 4vw, 38px); line-height: 1.15; letter-spacing: -.03em; }
    h2 { margin: 0; font-size: 18px; }
    h3 { margin: 0; font-size: 15px; }
    p { color: var(--muted); }
    .eyebrow { margin: 0 0 7px; color: var(--accent); font-size: 12px; font-weight: 820; letter-spacing: .08em; text-transform: uppercase; }
    .lead { max-width: 720px; margin: 9px 0 0; font-size: 16px; }
    .stack { display: grid; gap: 16px; }
    .grid { display: grid; gap: 16px; }
    .grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .card { min-width: 0; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); }
    .card-header { padding: 17px 18px 13px; display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; border-bottom: 1px solid var(--line); }
    .card-body { padding: 18px; }
    .card-copy { margin: 5px 0 0; font-size: 13px; }
    .hero { padding: clamp(26px, 5vw, 54px); background: linear-gradient(135deg, #fff 20%, #eff6ff); }
    .hero-actions, .inline-actions { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 18px; }
    .boundary { margin-top: 20px; display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 12px; }
    .boundary-item { border: 1px solid #bfdbfe; border-radius: 8px; background: rgba(255,255,255,.8); padding: 13px; }
    .boundary-item strong { display: block; margin-bottom: 3px; font-size: 13px; }
    .boundary-item span { color: var(--muted); font-size: 12px; }
    .project-dashboard, .home-dashboard, .review-dashboard { display: grid; gap: 16px; }
    .metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; }
    .metric { border: 1px solid var(--line); border-radius: 9px; background: var(--surface); padding: 15px; }
    .metric span { display: block; color: var(--muted); font-size: 12px; }
    .metric strong { display: block; margin-top: 5px; font-size: 19px; overflow-wrap: anywhere; }
    .form-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; }
    .form-grid .wide { grid-column: 1 / -1; }
    .workflow-shell { max-width: 940px; margin: 0 auto; }
    .workflow-card { overflow: hidden; }
    .workflow-section { display: grid; grid-template-columns: 42px minmax(0,1fr); gap: 16px; padding: 24px; }
    .workflow-section + .workflow-section { border-top: 1px solid var(--line); }
    .workflow-section.is-locked .step-index { border-color: var(--line); background: var(--surface-subtle); color: var(--muted); }
    .workflow-section.is-locked .stage-content { opacity: .58; }
    .step-index { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid #bfdbfe; border-radius: 50%; background: var(--accent-soft); color: var(--accent); font-size: 13px; font-weight: 820; }
    .step-heading { margin-bottom: 16px; }
    .step-heading h2 { font-size: 17px; }
    .step-heading p { margin: 5px 0 0; font-size: 13px; }
    .project-path-row { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 10px; align-items: start; }
    .project-path-row button { margin-top: 25px; }
    .choice-row { display: flex; flex-wrap: wrap; align-items: center; gap: 9px; margin-top: 10px; }
    .choice-note { margin: 0; color: var(--muted); font-size: 12px; }
    .recognition-placeholder { border: 1px dashed var(--line-strong); border-radius: 9px; padding: 22px; background: var(--surface-subtle); text-align: center; }
    .recognition-placeholder p { margin: 5px 0 0; font-size: 13px; }
    .project-summary { display: grid; grid-template-columns: minmax(220px,1.5fr) repeat(3,minmax(110px,.55fr)); gap: 10px; }
    .project-signature, .summary-stat { min-width: 0; border: 1px solid var(--line); border-radius: 9px; padding: 14px; background: var(--surface-subtle); }
    .project-signature { border-color: #bfdbfe; background: var(--accent-soft); }
    .project-signature span, .summary-stat span { display: block; color: var(--muted); font-size: 11px; font-weight: 760; letter-spacing: .04em; text-transform: uppercase; }
    .project-signature strong, .summary-stat strong { display: block; margin-top: 6px; overflow-wrap: anywhere; }
    .project-signature p { margin: 5px 0 0; font-size: 12px; }
    .recognized-files { margin-top: 12px; border: 1px solid var(--line); border-radius: 9px; }
    .recognized-files summary { padding: 11px 13px; }
    .recognized-files .table-wrap { padding: 0 13px 13px; }
    .locale-flow { display: grid; grid-template-columns: minmax(0,1fr) 52px minmax(0,1fr); gap: 12px; align-items: stretch; }
    .locale-card { border: 1px solid var(--line); border-radius: 10px; padding: 15px; background: var(--surface-subtle); }
    .locale-card.source { border-color: #bfdbfe; background: var(--accent-soft); }
    .locale-role { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 9px; color: var(--muted); font-size: 12px; font-weight: 760; }
    .auto-badge { display: inline-flex; align-items: center; min-height: 22px; border: 1px solid #bfdbfe; border-radius: 999px; padding: 1px 8px; background: #fff; color: var(--accent); font-size: 11px; }
    .locale-card label { font-size: 12px; }
    .locale-hint { min-height: 36px; margin: 7px 0 0; font-size: 12px; }
    .locale-arrow { display: grid; place-items: center; color: var(--accent); }
    .locale-arrow svg { width: 28px; height: 28px; }
    .workflow-options { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 12px; align-items: end; }
    .workflow-actions { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 18px; }
    .safety-note { margin-top: 14px; border-left: 3px solid var(--line-strong); padding: 2px 0 2px 12px; color: var(--muted); font-size: 12px; }
    .operation-overlay { position: fixed; inset: 0; z-index: 80; display: grid; place-items: center; padding: 20px; background: rgba(15,23,42,.46); backdrop-filter: blur(4px); }
    .operation-overlay[hidden] { display: none; }
    .operation-card { width: min(520px,100%); border: 1px solid rgba(255,255,255,.7); border-radius: 14px; padding: 30px; background: var(--surface); box-shadow: 0 24px 70px rgba(15,23,42,.24); text-align: center; }
    .scan-indicator { position: relative; width: 66px; height: 66px; margin: 0 auto 18px; display: grid; place-items: center; }
    .scan-ring { position: absolute; inset: 0; border: 3px solid #dbeafe; border-top-color: var(--accent); border-radius: 50%; animation: scan-rotate 1s ease-in-out infinite; }
    .scan-core { width: 26px; height: 26px; display: grid; place-items: center; border-radius: 8px; background: var(--accent-soft); color: var(--accent); font-size: 10px; font-weight: 820; }
    .operation-overlay.complete .scan-ring { border-color: #a7f3d0; border-top-color: var(--success); animation: none; }
    .operation-overlay.complete .scan-core { background: var(--success-soft); color: var(--success); }
    .operation-kicker { margin: 0 0 6px; color: var(--accent); font-size: 11px; font-weight: 820; letter-spacing: .08em; text-transform: uppercase; }
    .operation-card h2 { font-size: 21px; }
    .operation-card > p:not(.operation-kicker) { margin: 8px auto 0; max-width: 390px; font-size: 13px; }
    .operation-track { height: 4px; margin: 22px 0 17px; overflow: hidden; border-radius: 999px; background: #e2e8f0; }
    .operation-track span { display: block; width: 38%; height: 100%; border-radius: inherit; background: var(--accent); animation: scan-track 1.35s ease-in-out infinite; }
    .operation-overlay.complete .operation-track span { width: 100%; background: var(--success); animation: none; }
    .operation-steps { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; color: var(--muted); font-size: 11px; }
    .operation-step { border-top: 2px solid var(--line); padding-top: 7px; }
    .operation-step.active { border-color: var(--accent); color: var(--accent); font-weight: 760; }
    .operation-step.complete { border-color: var(--success); color: var(--success); }
    @keyframes scan-rotate { to { transform: rotate(360deg); } }
    @keyframes scan-track { 0% { transform: translateX(-110%); } 50% { transform: translateX(85%); } 100% { transform: translateX(245%); } }
    details { border-top: 1px solid var(--line); }
    summary { padding: 14px 18px; color: var(--muted); font-weight: 750; }
    .details-body { padding: 0 18px 18px; }
    .status-notice, .error-notice { display: none; margin-bottom: 16px; border-radius: 8px; padding: 12px 14px; }
    .status-notice.visible { display: block; border: 1px solid #a7f3d0; background: var(--success-soft); color: #065f46; }
    .error-notice.visible { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; border: 1px solid #fecaca; background: var(--danger-soft); color: #991b1b; }
    .status-chip { display: inline-flex; align-items: center; min-height: 26px; border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; background: var(--surface-subtle); color: var(--muted); font-size: 12px; font-weight: 760; }
    .status-chip.success { border-color: #a7f3d0; background: var(--success-soft); color: var(--success); }
    .status-chip.warning, .status-chip.progress { border-color: #fde68a; background: var(--warning-soft); color: var(--warning); }
    .status-chip.blocked, .status-chip.error { border-color: #fecaca; background: var(--danger-soft); color: var(--danger); }
    .review-run-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 22px; }
    .review-run-id { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }
    .list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
    .list-item { border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
    .list-item p { margin: 4px 0 0; font-size: 13px; }
    .artifact-row, .session-row, .action-row { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 12px; align-items: center; border-bottom: 1px solid var(--line); padding: 12px 0; }
    .artifact-row:last-child, .session-row:last-child, .action-row:last-child { border-bottom: 0; }
    .path { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }
    .empty { border: 1px dashed var(--line-strong); border-radius: 8px; padding: 24px; text-align: center; color: var(--muted); }
    .table-wrap { max-width: 100%; overflow-x: auto; }
    table { width: 100%; min-width: 620px; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 11px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; }
    .inspector { position: fixed; inset: 0; z-index: 50; display: none; background: rgba(15,23,42,.42); }
    .inspector.open { display: grid; place-items: stretch end; }
    .inspector-panel { width: min(720px, 100vw); height: 100%; display: grid; grid-template-rows: auto 1fr; background: var(--surface); box-shadow: -12px 0 40px rgba(15,23,42,.2); }
    .inspector-header { padding: 16px; display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); }
    .inspector-content { margin: 0; padding: 18px; overflow: auto; color: #e2e8f0; background: #0f172a; font: 12px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
    .language-switch { display: inline-flex; gap: 4px; }
    .language-switch button { min-height: 44px; padding: 0 11px; }
    @media (max-width: 900px) {
      .header-row { flex-wrap: wrap; gap: 8px; padding-top: 10px; padding-bottom: 10px; }
      .brand { min-width: 0; }
      .nav-wrap { order: 3; flex-basis: 100%; }
      .grid.two, .grid.three, .metric-grid, .boundary { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .project-summary { grid-template-columns: repeat(2,minmax(0,1fr)); }
      .project-signature { grid-column: 1 / -1; }
    }
    @media (max-width: 640px) {
      main { padding: 24px 14px 44px; }
      .header-row, .context-inner { padding-left: 14px; padding-right: 14px; }
      .header-tools .health-label { display: none; }
      .page-heading, .review-run-header { display: grid; }
      .grid.two, .grid.three, .metric-grid, .boundary, .form-grid { grid-template-columns: 1fr; }
      .form-grid .wide { grid-column: auto; }
      .hero { padding: 24px 18px; }
      .artifact-row, .session-row, .action-row { grid-template-columns: 1fr; }
      .artifact-row button, .session-row button, .action-row button { width: 100%; }
      .workflow-section { grid-template-columns: 1fr; gap: 10px; padding: 20px 16px; }
      .project-path-row, .workflow-options, .project-summary, .locale-flow { grid-template-columns: 1fr; }
      .project-path-row button { width: 100%; margin-top: 0; }
      .project-signature { grid-column: auto; }
      .locale-arrow { min-height: 36px; transform: rotate(90deg); }
      .workflow-actions button, .choice-row button { width: 100%; justify-content: center; }
      .operation-card { padding: 25px 18px; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
      .scan-ring, .operation-track span { animation: none !important; }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#main-content" data-i18n="a11y.skip">Skip to main content</a>
  <header class="app-header">
    <div class="header-row">
      <div class="brand"><span class="brand-mark" aria-hidden="true">LA</span><span>Localize Anything</span></div>
      <div class="nav-wrap">
        <span id="navScrollHint" hidden data-i18n="a11y.navScroll">Navigation can scroll horizontally on small screens.</span>
        <nav class="nav-links" aria-label="Workbench sections" aria-describedby="navScrollHint">
          <a href="/" data-route="/" aria-current="page" data-i18n="nav.overview">Overview</a>
          <a href="/generate" data-route="/generate" data-i18n="nav.generate">Prepare</a>
          <a href="/review" data-route="/review" data-i18n="nav.review">Review</a>
          <a href="/sessions" data-route="/sessions" data-i18n="nav.sessions">Sessions</a>
          <a href="/settings" data-route="/settings" data-i18n="nav.settings">Settings</a>
        </nav>
      </div>
      <div class="header-tools">
        <span class="health-dot" id="healthDot" aria-hidden="true"></span>
        <span class="health-label" id="healthLabel">Checking local service</span>
      </div>
    </div>
    <div class="context-strip">
      <div class="context-inner">
        <div class="context-copy"><strong id="contextProject">No project selected</strong><span class="context-meta" id="contextRun">No run selected</span></div>
        <button class="context-action" id="contextProjectAction" type="button" onclick="navigate('/generate')">Open project</button>
      </div>
    </div>
  </header>

  <main id="main-content" tabindex="-1">
    <div id="successStatus" class="status-notice" role="status" aria-live="polite"></div>
    <div id="errorStatus" class="error-notice" role="alert"><span id="errorMessage"></span><button type="button" onclick="clearError()">Dismiss</button></div>

    <section class="page" data-page="/">
      <div class="home-dashboard">
        <div class="card hero">
          <p class="eyebrow">Local, review-first workflow</p>
          <h1 id="pageTitle">Prepare localization work with evidence</h1>
          <p class="lead">Inspect a project, prepare a provider-free handoff, review exact run evidence, and keep Apply behind separate authorization.</p>
          <div class="hero-actions">
            <button class="primary" type="button" onclick="runSafeDemo()">Run safe demo</button>
            <button type="button" onclick="navigate('/generate')">Open local project</button>
          </div>
          <div class="boundary">
            <div class="boundary-item"><strong>No provider or model call from the safe demo</strong><span>Uses a copied public fixture and synthetic output.</span></div>
            <div class="boundary-item"><strong>Source files stay unchanged</strong><span>Prepared artifacts are written outside the source project.</span></div>
            <div class="boundary-item"><strong>Applying output requires separate authorization</strong><span>The Workbench previews the Apply plan but does not execute it.</span></div>
          </div>
        </div>
        <div class="project-dashboard" id="overviewProject">
          <div class="grid two">
            <div class="card"><div class="card-header"><div><h2>Current project</h2><p class="card-copy">Local project context and latest run.</p></div></div><div class="card-body" id="overviewProjectBody"><div class="empty">Choose a project to begin.</div></div></div>
            <div class="card"><div class="card-header"><div><h2>Next useful action</h2><p class="card-copy">One task at a time, based on available evidence.</p></div></div><div class="card-body" id="nextAction"><button class="primary" type="button" onclick="navigate('/generate')">Select project</button></div></div>
          </div>
          <div class="card"><div class="card-header"><div><h2>Recent sessions</h2><p class="card-copy">Open an exact run without falling back to latest.</p></div></div><div class="card-body" id="overviewSessions"><div class="empty">No recorded sessions.</div></div></div>
        </div>
      </div>
    </section>

    <section class="page" data-page="/generate" hidden>
      <div class="workflow-shell">
        <div class="page-heading"><div><p class="eyebrow">Prepare</p><h1>Set up localization in order</h1><p class="lead">Choose a project, confirm what was recognized, then set the language direction before preparing any handoff.</p></div></div>
        <div class="card workflow-card">
          <section class="workflow-section" aria-labelledby="projectStepTitle">
            <div class="step-index" aria-hidden="true">1</div>
            <div class="stage-content">
              <div class="step-heading"><h2 id="projectStepTitle">Choose the project</h2><p>Open a local folder, or paste its path and recognize it manually.</p></div>
              <div class="project-path-row">
                <div><label for="project">Project path *</label><input id="project" aria-describedby="projectError" placeholder="C:\path\to\project"><div class="field-error" id="projectError"></div></div>
                <button id="recognizeProjectButton" type="button" onclick="inspectProject()">Recognize project</button>
              </div>
              <div class="choice-row">
                <button class="primary" id="chooseProjectButton" type="button" onclick="pickProjectDirectory()">Choose local folder</button>
                <button id="importFilesButton" type="button" onclick="$('filePicker').click()">Import files instead</button><input id="filePicker" type="file" multiple aria-label="Import files" hidden>
                <p class="choice-note">Local folders stay on this computer. Imported files are copied to a temporary project.</p>
              </div>
            </div>
          </section>

          <section class="workflow-section" id="recognitionSection" aria-labelledby="recognitionStepTitle">
            <div class="step-index" aria-hidden="true">2</div>
            <div class="stage-content">
              <div class="step-heading"><h2 id="recognitionStepTitle">Confirm the recognized project</h2><p>Project type and resource routing come directly from the local inspection result.</p></div>
              <div id="routing" aria-live="polite"><div class="recognition-placeholder"><strong>Waiting for a project</strong><p>Recognition starts automatically after a folder is chosen.</p></div></div>
            </div>
          </section>

          <section class="workflow-section is-locked" id="languageSection" aria-labelledby="languageStepTitle" aria-disabled="true">
            <div class="step-index" aria-hidden="true">3</div>
            <div class="stage-content">
              <div class="step-heading"><h2 id="languageStepTitle">Set the language direction</h2><p>The source is suggested from recognized metadata or writing system. You can correct it before continuing.</p></div>
              <div class="locale-flow">
                <div class="locale-card source">
                  <div class="locale-role"><span>Source</span><span class="auto-badge" id="sourceLocaleBadge">Waiting for recognition</span></div>
                  <label for="sourceLocale">Source language</label>
                  <input id="sourceLocale" value="en-US" list="localeOptions" autocomplete="off" disabled>
                  <p class="locale-hint" id="sourceLocaleHint">Choose a project to get a source-language suggestion.</p>
                </div>
                <div class="locale-arrow" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M5 12h14M14 7l5 5-5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
                <div class="locale-card">
                  <div class="locale-role"><span>Target</span><span>Required</span></div>
                  <label for="targetLocale">Target language</label>
                  <input id="targetLocale" value="zh-CN" list="localeOptions" aria-describedby="targetLocaleError" autocomplete="off" disabled>
                  <div class="field-error" id="targetLocaleError"></div>
                </div>
              </div>
              <datalist id="localeOptions">
                <option value="de-DE" label="Deutsch (Deutschland) · 德语（德国）"></option>
                <option value="en-US" label="English (United States) · 英语（美国）"></option>
                <option value="es-ES" label="Español (España) · 西班牙语（西班牙）"></option>
                <option value="fr-FR" label="Français (France) · 法语（法国）"></option>
                <option value="ja-JP" label="日本語 (日本) · 日语（日本）"></option>
                <option value="ko-KR" label="한국어 (대한민국) · 韩语（韩国）"></option>
                <option value="pt-BR" label="Português (Brasil) · 葡萄牙语（巴西）"></option>
                <option value="ru-RU" label="Русский (Россия) · 俄语（俄罗斯）"></option>
                <option value="th-TH" label="ไทย (ประเทศไทย) · 泰语（泰国）"></option>
                <option value="zh-CN" label="简体中文（中国大陆）"></option>
                <option value="zh-TW" label="繁體中文（台灣）"></option>
              </datalist>
            </div>
          </section>

          <section class="workflow-section is-locked" id="prepareSection" aria-labelledby="prepareStepTitle" aria-disabled="true">
            <div class="step-index" aria-hidden="true">4</div>
            <div class="stage-content">
              <div class="step-heading"><h2 id="prepareStepTitle">Prepare the handoff</h2><p>Review the recognized project and language direction, then choose the smallest useful next action.</p></div>
              <div class="workflow-options">
                <div><label for="operatingMode">Workflow mode</label><select id="operatingMode" disabled><option value="greenfield_localization">New localization</option><option value="existing_locale_maintenance">Maintain an existing locale</option><option value="blind_benchmark">Blind benchmark</option></select></div>
                <span class="status-chip">Provider-free preparation</span>
              </div>
              <details>
                <summary>Advanced run options</summary>
                <div class="details-body form-grid">
                  <div class="wide"><label for="sourceFiles">Recognized source files, one relative path per line</label><textarea id="sourceFiles" disabled></textarea></div>
                  <div><label for="outputRoot">Output root</label><input id="outputRoot" disabled></div>
                  <div><label for="runId">Run ID</label><input id="runId" disabled></div>
                  <div><label for="maxSegments">Segment limit</label><input id="maxSegments" type="number" min="1" value="80" disabled></div>
                  <div><label for="responsesDir">Generated responses directory</label><input id="responsesDir" disabled></div>
                </div>
              </details>
              <div class="workflow-actions">
                <button class="primary" id="prepareHandoffButton" type="button" onclick="runAgent('handoff')" disabled>Prepare generation handoff</button>
                <button id="syntheticDraftButton" type="button" onclick="runAgent('synthetic')" disabled>Stage synthetic draft (demo)</button>
                <button id="importResponsesButton" type="button" onclick="runAgent('responses')" disabled>Import generated responses</button>
              </div>
              <p class="safety-note">Preparation creates evidence and staged artifacts. It does not call a provider, change source files, authorize delivery, or execute Apply.</p>
            </div>
          </section>
        </div>
      </div>
    </section>

    <section class="page" data-page="/review" hidden>
      <div class="review-run-header"><div><p class="eyebrow">Review</p><h1>Exact run evidence</h1><p class="lead">Readiness, delivery, claims, actions, and artifacts stay scoped to the selected run.</p></div><div><div class="review-run-id" id="reviewRunId">No run selected</div><span class="status-chip" id="reviewRunFreshness">not selected</span></div></div>
      <div class="review-dashboard">
        <div id="reviewEmpty" class="card"><div class="card-body empty"><h2 id="reviewEmptyTitle">Select a run</h2><p id="reviewEmptyMessage">Select a session or run the safe demo to open Review.</p><div class="inline-actions"><button id="reviewRetry" type="button" onclick="retryReviewLoad()" hidden>Retry</button><button type="button" onclick="navigate('/sessions')">Open sessions</button></div></div></div>
        <div id="reviewContent" class="stack" hidden>
          <div class="metric-grid">
            <div class="metric"><span>Run status</span><strong id="runStatus">Unavailable</strong></div>
            <div class="metric"><span>Extraction coverage</span><strong id="extractionCoverage">Unavailable</strong></div>
            <div class="metric"><span>QA</span><strong id="qaStatus">Not checked</strong></div>
            <div class="metric"><span>Artifact state</span><strong id="artifactStateStatus">Unavailable</strong><span id="artifactStateCounts">No artifact evidence loaded</span></div>
          </div>
          <div class="grid three">
            <div class="card"><div class="card-header"><h2>Review readiness</h2></div><div class="card-body" id="reviewReadiness"></div></div>
            <div class="card"><div class="card-header"><h2>Delivery</h2></div><div class="card-body" id="deliveryReadiness"></div></div>
            <div class="card"><div class="card-header"><h2>Apply plan</h2></div><div class="card-body" id="applyDetails"></div></div>
          </div>
          <div class="grid two">
          <div class="card"><div class="card-header"><div><h2>Risks and limitations</h2><p class="card-copy">Runtime evidence only. Scope and missing evidence stay explicit.</p></div></div><div class="card-body"><ul class="list" id="riskList"></ul></div></div>
            <div class="card"><div class="card-header"><div><h2>Provider smoke</h2><p class="card-copy">Two-segment path evidence is not a quality claim.</p></div></div><div class="card-body" id="providerSmoke">No provider smoke evidence found. The field provider_or_model_called_by_runtime is unavailable.</div></div>
          </div>
          <div class="grid two">
            <div class="card"><div class="card-header"><div><h2>Action queue</h2><p class="card-copy" id="queueScope">Selected run evidence</p></div></div><div class="card-body"><div id="actionQueue" class="stack"></div><form id="actionComposer" class="stack" onsubmit="submitReviewAction(event)"><div><label for="actionItemId">Queue item ID</label><input id="actionItemId" name="target_queue_item_id"></div><div><label for="actionType">Action</label><select id="actionType"><option value="request_follow_up">Request follow-up</option><option value="acknowledge_limitation">Acknowledge limitation</option></select></div><div><label for="actionReason">Reason</label><textarea id="actionReason"></textarea></div><button type="submit">Record action</button></form><div id="actionResult" role="status" aria-live="polite"></div></div></div>
            <div class="card"><div class="card-header"><div><h2>Recent artifacts</h2><p class="card-copy">Open readable files in the inspector.</p></div></div><div class="card-body" id="recentArtifacts"></div></div>
          </div>
          <div class="card"><div class="card-header"><div><h2>All runtime artifacts</h2><p class="card-copy">Directories remain path-only.</p></div></div><div class="card-body" id="allArtifacts"></div></div>
        </div>
      </div>
    </section>

    <section class="page" data-page="/sessions" hidden>
      <div class="page-heading"><div><p class="eyebrow">Sessions</p><h1>Recorded runs</h1><p class="lead">Choose a run by identity. Historical evidence is never silently upgraded to current project state.</p></div></div>
      <div class="card"><div class="card-header"><div><h2>Project sessions</h2><p class="card-copy">Newest runs appear first.</p></div></div><div class="card-body" id="sessions"><div class="empty"><h3 data-i18n="sessions.emptyTitle">No sessions yet</h3><p>Select a project first or prepare a run.</p></div></div></div>
    </section>

    <section class="page" data-page="/settings" hidden>
      <div class="page-heading"><div><p class="eyebrow">Settings</p><h1>Workbench preferences</h1><p class="lead">Interface settings do not change runtime policy or provider authorization.</p></div></div>
      <div class="grid two">
        <div class="card"><div class="card-header"><h2>Navigation language</h2></div><div class="card-body"><p>Changes navigation labels and the session empty state. Runtime evidence stays in its source language.</p><div class="language-switch"><button type="button" data-language="en" onclick="setLanguage('en')">English</button><button type="button" data-language="zh-CN" onclick="setLanguage('zh-CN')">中文</button></div></div></div>
        <div class="card"><div class="card-header"><h2>Local service</h2></div><div class="card-body"><p id="settingsHealth">Checking</p><p>Health confirms only that this local Workbench service is reachable.</p></div></div>
      </div>
    </section>
  </main>

  <div class="operation-overlay" id="projectTransition" role="status" aria-live="polite" aria-atomic="true" tabindex="-1" hidden>
    <div class="operation-card">
      <div class="scan-indicator" aria-hidden="true"><span class="scan-ring"></span><span class="scan-core">LA</span></div>
      <p class="operation-kicker">Project intake</p>
      <h2 id="projectTransitionTitle">Opening project</h2>
      <p id="projectTransitionDetail">Waiting for the local folder selection.</p>
      <div class="operation-track" aria-hidden="true"><span></span></div>
      <div class="operation-steps" aria-hidden="true">
        <span class="operation-step" data-operation-step="choose">Choose</span>
        <span class="operation-step" data-operation-step="inspect">Recognize</span>
        <span class="operation-step" data-operation-step="ready">Ready</span>
      </div>
    </div>
  </div>

  <aside class="inspector" id="reviewInspector" role="dialog" aria-modal="true" aria-hidden="true" aria-labelledby="inspectorTitle">
    <div class="inspector-panel"><div class="inspector-header"><div><h2 id="inspectorTitle">Artifact</h2><div class="path" id="inspectorPath"></div></div><button id="inspectorClose" type="button" onclick="closeInspector()">Close</button></div><pre class="inspector-content" id="inspectorContent" dir="auto"></pre></div>
  </aside>

  <script>
    const $ = (id) => document.getElementById(id);
    const LANGUAGE_KEY = "localize-anything-language";
    const MODE_CONFIG = {
      greenfield_localization: {reference_policy: "style_only", workflow_depth: "ask", preflight_mode: "auto"},
      existing_locale_maintenance: {reference_policy: "preserve_existing", workflow_depth: "standard", preflight_mode: "auto"},
      blind_benchmark: {reference_policy: "blind", workflow_depth: "high_assurance", preflight_mode: "full"}
    };
    const TRANSLATIONS = {
      en: {"nav.overview":"Overview","nav.generate":"Prepare","nav.review":"Review","nav.sessions":"Sessions","nav.settings":"Settings","a11y.skip":"Skip to main content","a11y.navScroll":"Navigation can scroll horizontally on small screens.","sessions.emptyTitle":"No sessions yet","status.unknown":"Unknown status"},
      "zh-CN": {"nav.overview":"概览","nav.generate":"准备","nav.review":"审查","nav.sessions":"运行记录","nav.settings":"设置","a11y.skip":"跳到主要内容","a11y.navScroll":"小屏幕上导航可横向滚动。","sessions.emptyTitle":"暂无运行记录","status.unknown":"未知状态"}
    };
    const STATUS_REGISTRY = {
      pass:{family:"success"}, accepted:{family:"success"}, ready:{family:"success"}, available:{family:"success"}, draft_package_created:{family:"success"},
      pending:{family:"progress"}, running:{family:"progress"}, processing:{family:"progress"},
      warning:{family:"warning"}, ready_with_warnings:{family:"warning"}, requires_human_review:{family:"warning"}, review_required:{family:"warning"}, stale:{family:"warning"}, historical:{family:"warning"},
      blocked:{family:"blocked"}, blocking:{family:"blocked"}, authorization_required:{family:"blocked"},
      fail:{family:"error"}, failed:{family:"error"}, error:{family:"error"}, missing:{family:"error"}, rejected:{family:"error"},
      not_checked:{family:"neutral"}, unavailable:{family:"neutral"}, current:{family:"neutral"}, directory:{family:"neutral"}
    };
    let language = localStorage.getItem(LANGUAGE_KEY) || "en";
    let busy = false;
    let busyReturnFocus = null;
    let routingReady = false;
    let currentProject = "";
    let currentIndex = null;
    let currentArtifactState = null;
    let currentSession = null;
    let currentRunView = null;
    let inspectorReturnFocus = null;
    let operationReturnFocus = null;
    const rawArtifactPreviews = {};

    class WorkbenchRequestError extends Error {
      constructor(code, message, status, recoverable, actions) { super(message); this.code=code; this.status=status; this.recoverable=recoverable; this.actions=actions || []; }
    }
    function t(key) { return (TRANSLATIONS[language] || TRANSLATIONS.en)[key] || TRANSLATIONS.en[key] || key; }
    function setLanguage(next) { language = next; localStorage.setItem(LANGUAGE_KEY, next); applyLanguage(); }
    function applyLanguage() { document.documentElement.lang = language; document.querySelectorAll("[data-i18n]").forEach((node) => node.textContent = t(node.dataset.i18n)); document.querySelectorAll("[data-language]").forEach((node)=>node.setAttribute("aria-pressed",String(node.dataset.language === language))); }
    function available(data) { return {kind:"available", data}; }
    function missing(reason, path) { return {kind:"missing", reason:reason || "ARTIFACT_MISSING", path}; }
    function stale(data, reason) { return {kind:"stale", data, reason:reason || "RUN_STATE_MISMATCH"}; }
    function error(code, message, path) { return {kind:"error", code, message, path}; }
    function resultFromProjection(projection) {
      if (!projection) return missing("ARTIFACT_MISSING");
      if (projection.state === "available") return available(projection.data);
      if (projection.state === "stale") return stale(projection.data, projection.reason);
      if (projection.state === "error") return error(projection.reason || "INVALID_ARTIFACT_JSON", projection.message, projection.path);
      return missing(projection.reason, projection.path);
    }
    function statusContract(value) {
      const objectValue = value && typeof value === "object" ? value : {};
      const code = String(objectValue.status_code || objectValue.status || objectValue.outcome || value || "not_checked").trim().toLowerCase();
      const entry = STATUS_REGISTRY[code];
      if (!entry) return {status_code: "unknown", status_family: "neutral", message_code: "STATUS_UNKNOWN", message_params: {code}};
      return {status_code: code, status_family: objectValue.status_family || entry.family, message_code: objectValue.message_code || `STATUS_${code.toUpperCase()}`, message_params: objectValue.message_params || {}};
    }
    function statusFamily(value) { return statusContract(value).status_family; }
    function statusText(value) { const contract=statusContract(value); return contract.status_code === "unknown" ? t("status.unknown") : contract.status_code.replaceAll("_", " "); }
    function statusChip(value) { const c=statusContract(value); return `<span class="status-chip ${escapeHtml(statusFamily(c))}">${escapeHtml(statusText(c))}</span>`; }
    function setStatus(message) { $("successStatus").textContent=message; $("successStatus").classList.toggle("visible", Boolean(message)); }
    function showError(value) { $("errorMessage").textContent=value.message || String(value); $("errorStatus").classList.add("visible"); }
    function clearError() { $("errorStatus").classList.remove("visible"); }
    function setFieldError(id, message) { const field=$(id); const output=$(id+"Error"); if(output) output.textContent=message || ""; if(field) field.setAttribute("aria-invalid", String(Boolean(message))); }
    function setBusy(value) {
      busy=value;
      document.body.setAttribute("aria-busy", String(value));
      document.querySelectorAll("button,input,select,textarea").forEach((node) => {
        if(value){node.dataset.busyDisabled=String(node.disabled);node.disabled=true;}
        else if("busyDisabled" in node.dataset){node.disabled=node.dataset.busyDisabled === "true";delete node.dataset.busyDisabled;}
      });
      if(!value) syncWorkflowControls();
    }
    async function runBusy(task) { if(busy) return; busyReturnFocus=document.activeElement; clearError(); setStatus(""); setBusy(true); try { await task(); } catch(value) { showError(value); } finally { setBusy(false); if(operationReturnFocus && typeof operationReturnFocus.focus === "function") operationReturnFocus.focus(); operationReturnFocus=null; busyReturnFocus=null; } }
    function syncWorkflowControls() {
      const enabled=routingReady && !busy;
      for(const id of ["sourceLocale","targetLocale","operatingMode","sourceFiles","outputRoot","runId","maxSegments","responsesDir"]){$(id).disabled=!enabled;}
      const source=$("sourceLocale").value.trim(); const target=$("targetLocale").value.trim();
      const directionReady=enabled && Boolean(source) && Boolean(target) && source !== target;
      for(const id of ["prepareHandoffButton","syntheticDraftButton","importResponsesButton"]){$(id).disabled=!directionReady;}
      for(const id of ["languageSection","prepareSection"]){$(id).classList.toggle("is-locked",!routingReady);$(id).setAttribute("aria-disabled",String(!routingReady));}
    }
    function setProjectTransition(stage, title, detail) {
      const overlay=$("projectTransition");
      if(overlay.hidden){operationReturnFocus=busyReturnFocus || document.activeElement;overlay.hidden=false;overlay.focus();}
      overlay.classList.toggle("complete",stage === "ready");
      $("projectTransitionTitle").textContent=title;
      $("projectTransitionDetail").textContent=detail;
      const order=["choose","inspect","ready"]; const active=order.indexOf(stage);
      overlay.querySelectorAll("[data-operation-step]").forEach((node)=>{const index=order.indexOf(node.dataset.operationStep);node.classList.toggle("active",index === active);node.classList.toggle("complete",index < active || stage === "ready");});
    }
    function hideProjectTransition() { const overlay=$("projectTransition"); overlay.hidden=true; overlay.classList.remove("complete"); }
    function transitionPause() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? Promise.resolve() : new Promise((resolve)=>setTimeout(resolve,420)); }

    async function requestJson(path, options) {
      let response;
      try { response = await fetch(path, options); } catch (networkError) { throw new WorkbenchRequestError("NETWORK_ERROR", networkError.message, 0, true, ["RETRY"]); }
      let data;
      try { data = await response.json(); } catch (_) { throw new WorkbenchRequestError("INVALID_RESPONSE", "The local service returned invalid JSON.", response.status, true, ["RETRY"]); }
      if (!response.ok || data.status === "fail") {
        const details = data.error && typeof data.error === "object" ? data.error : {};
        throw new WorkbenchRequestError(details.code || data.message_code || "REQUEST_FAILED", details.message || data.error || "Request failed", response.status, details.recoverable !== false, details.actions || []);
      }
      return data;
    }
    const postJson = (path, payload) => requestJson(path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload || {})});
    const getJson = (path) => requestJson(path);

    function routeUrl(path, runId) { const url=new URL(path, location.origin); const project=$("project").value.trim() || currentProject; const selectedRun=runId || (currentSession && (currentSession.run_id || currentSession.session_id)); if(project) url.searchParams.set("project", project); if(selectedRun) url.searchParams.set("run", selectedRun); return url.pathname+url.search; }
    function navigate(path, runId) { history.pushState({}, "", routeUrl(path, runId)); restoreFromUrl(); }
    function renderRoute() {
      const route=["/","/generate","/review","/sessions","/settings"].includes(location.pathname) ? location.pathname : "/";
      document.querySelectorAll(".page").forEach((node) => node.hidden=node.dataset.page !== route);
      document.querySelectorAll("[data-route]").forEach((link) => { const active=link.dataset.route===route; if(active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current"); });
    }
    function updateContext() {
      currentProject=$("project").value.trim();
      const normalized=currentProject.replace(/\\/g,"/").replace(/\/$/,"");
      $("contextProject").textContent=normalized ? normalized.split("/").pop() : "No project selected";
      $("contextRun").textContent=currentSession ? `Run ${currentSession.run_id || currentSession.session_id}` : "No run selected";
      $("contextProjectAction").textContent=currentProject ? "Change project" : "Open project";
    }
    function payloadBase() {
      const modeKey=$("operatingMode").value || "greenfield_localization";
      const mode=MODE_CONFIG[modeKey];
      return {project:$("project").value.trim(), source_locale:$("sourceLocale").value.trim() || "en-US", target_locale:$("targetLocale").value.trim(), source_files:$("sourceFiles").value, output_root:$("outputRoot").value.trim(), run_id:$("runId").value.trim(), max_segments:Number($("maxSegments").value || 80), operating_mode:modeKey, reference_policy:mode.reference_policy, workflow_depth:mode.workflow_depth, preflight_mode:mode.preflight_mode, privacy_mode:"standard", data_classification:"internal", status:"draft_package"};
    }
    function validateProjectInput() { const project=$("project").value.trim(); setFieldError("project",project ? "" : "Project path is required."); if(!project) throw new WorkbenchRequestError("VALIDATION_ERROR","Choose or enter a project path.",400,true,[]); return project; }
    function validateRunInputs() { const project=validateProjectInput(); const source=$("sourceLocale").value.trim(); const target=$("targetLocale").value.trim(); const targetError=!target ? "Target language is required." : source === target ? "Target language must differ from the source." : ""; setFieldError("targetLocale",targetError); if(!routingReady || targetError) throw new WorkbenchRequestError("VALIDATION_ERROR",!routingReady ? "Recognize the project before preparing a handoff." : targetError,400,true,[]); return project; }

    async function pickProjectDirectory() { await runBusy(async()=>{ setProjectTransition("choose","Choose a local project","Use the system folder window to select the project you want to recognize."); try { const selection=await postJson("/api/pick-directory", {}); if(selection.status==="cancelled") return; currentSession=null; currentRunView=null; $("project").value=selection.project; currentProject=selection.project; resetProjectWorkflow(); updateContext(); setProjectTransition("inspect","Recognizing the project","Reading supported resources and adapter evidence. Large projects can take a little longer."); const data=await postJson("/api/inspect",{project:selection.project}); useInspection(data); await loadProjectState(); navigate("/generate"); setProjectTransition("ready","Project recognized",`${data.routing.supported_file_count || 0} supported resource files are ready to configure.`); await transitionPause(); setStatus("Local project recognized. Directory content stayed on this computer."); } finally { hideProjectTransition(); } }); }
    function fileToBase64(file) { return new Promise((resolve,reject)=>{ const reader=new FileReader(); reader.onload=()=>resolve(String(reader.result || "").split(",",2)[1] || ""); reader.onerror=()=>reject(reader.error); reader.readAsDataURL(file); }); }
    async function importSelectedFiles(files) { const items=Array.from(files || []); if(!items.length) return; await runBusy(async()=>{ setProjectTransition("choose","Reading selected files",`Preparing 0 of ${items.length} files for a temporary project.`); try { const payload=[]; for(let index=0;index<items.length;index++){const file=items[index];payload.push({relative_path:file.webkitRelativePath || file.name,content_base64:await fileToBase64(file)});$("projectTransitionDetail").textContent=`Preparing ${index+1} of ${items.length} files for a temporary project.`;} setProjectTransition("inspect","Importing and recognizing","Creating the temporary project and reading supported resources."); const data=await postJson("/api/import-files",{files:payload}); currentSession=null; currentRunView=null; $("project").value=data.project; currentProject=data.project; useInspection(data); await loadProjectState(); navigate("/generate"); setProjectTransition("ready","Project imported",`${data.routing.supported_file_count || 0} supported resource files are ready to configure.`); await transitionPause(); setStatus(`Imported and recognized ${items.length} files in a temporary project.`); } finally { hideProjectTransition(); $("filePicker").value=""; } }); }
    async function inspectProject() { await runBusy(async()=>{ const project=validateProjectInput(); resetProjectWorkflow(); setProjectTransition("inspect","Recognizing the project","Reading supported resources and adapter evidence. Large projects can take a little longer."); try { const data=await postJson("/api/inspect",{project}); currentSession=null; currentRunView=null; currentProject=project; useInspection(data); await loadProjectState(); setProjectTransition("ready","Project recognized",`${data.routing.supported_file_count || 0} supported resource files are ready to configure.`); await transitionPause(); setStatus("Project recognition complete."); } finally { hideProjectTransition(); } }); }
    function resetProjectWorkflow() { routingReady=false; $("routing").innerHTML='<div class="recognition-placeholder"><strong>Recognition pending</strong><p>Supported resources and project type will appear here.</p></div>'; $("sourceLocaleBadge").textContent="Waiting for recognition"; $("sourceLocaleHint").textContent="Recognition must finish before the language direction is available."; syncWorkflowControls(); }
    function useInspection(data) { const routing=data.routing || {}; $("sourceFiles").value=(data.source_files || (routing.supported_files || []).map(item=>item.path || item)).join("\n"); renderRouting(routing); }
    function projectTypeLabel(value) { return ({android:"Android application resources",ios:"iOS string resources",xcstrings:"Apple String Catalog",document:"OpenXML document project",mixed:"Mixed localization project",generic:"General localization resources",unknown:"Unrecognized project"})[value] || String(value || "Unrecognized project").replaceAll("_"," "); }
    function adapterLabel(value) { return ({"core.android-strings":"Android strings","core.ios-strings":"iOS strings","core.xcstrings":"String Catalog","core.word-document":"Word documents","core.json-locale":"JSON locale files","core.gettext-po":"Gettext catalogs","core.xliff":"XLIFF files","core.markup":"Markup content","core.subtitles":"Subtitles","core.tabular":"Tabular content","core.yaml-toml":"YAML or TOML"})[value] || String(value || "Unavailable"); }
    function renderRouting(routing) {
      if(!routing){resetProjectWorkflow();return;}
      const files=routing.supported_files || []; const count=Number(routing.supported_file_count || 0); const adapters=routing.adapters || Object.entries(routing.adapter_counts || {}).map(([adapter,file_count])=>({adapter,file_count})); const suggestion=routing.source_locale_suggestion || {};
      routingReady=count > 0;
      if(!routingReady){$("routing").innerHTML=`<div class="recognition-placeholder"><strong>No supported localization resources found</strong><p>${escapeHtml(routing.reason || "Choose a different folder or import supported resource files.")}</p></div>`;$("sourceLocaleBadge").textContent="No suggestion";$("sourceLocaleHint").textContent="No source language can be suggested without supported resources.";syncWorkflowControls();return;}
      if(suggestion.locale){$("sourceLocale").value=suggestion.locale;$("sourceLocaleBadge").textContent=`Auto · ${suggestion.confidence || "suggested"}`;$("sourceLocaleHint").textContent=suggestion.reason || "Suggested from project recognition.";}
      if(!$("targetLocale").value.trim() || $("targetLocale").value.trim() === $("sourceLocale").value.trim()) $("targetLocale").value=$("sourceLocale").value.trim() === "zh-CN" ? "en-US" : "zh-CN";
      const primary=routing.primary_adapter || (adapters[0] && adapters[0].adapter) || "Unavailable"; const preflight=routing.recommended_preflight_mode || "auto"; const reason=routing.reason ? `<p>${escapeHtml(routing.reason)}</p>` : ""; const warning=(routing.warnings || [])[0];
      $("routing").innerHTML=`<div class="project-summary"><div class="project-signature"><span>Detected project nature</span><strong>${escapeHtml(projectTypeLabel(routing.detected_project_type))}</strong>${reason}</div><div class="summary-stat"><span>Resources</span><strong>${count}</strong></div><div class="summary-stat"><span>Adapters</span><strong>${adapters.length}</strong></div><div class="summary-stat"><span>Primary route</span><strong>${escapeHtml(adapterLabel(primary))}</strong></div></div>${warning ? `<p class="safety-note">${escapeHtml(warning)}</p>` : ""}<details class="recognized-files"><summary>View recognized files (${count})</summary><div class="table-wrap"><table><thead><tr><th>Path</th><th>Adapter</th></tr></thead><tbody>${files.slice(0,40).map(item=>`<tr><td>${escapeHtml(item.path || item)}</td><td>${escapeHtml(item.adapter || "")}</td></tr>`).join("")}</tbody></table>${files.length>40 ? `<p>${files.length-40} more recognized files are available in the inspection result.</p>` : ""}<p>Recommended preflight: ${escapeHtml(preflight)}</p></div></details>`;
      syncWorkflowControls();
    }
    async function runAgent(mode) { await runBusy(async()=>{ validateRunInputs(); const payload=payloadBase(); if(mode==="synthetic") payload.synthetic_draft=true; if(mode==="responses"){payload.responses_dir=$("responsesDir").value.trim(); if(!payload.responses_dir) throw new WorkbenchRequestError("RESPONSES_REQUIRED","Generated responses directory is required.",400,true,[]);} const data=await postJson("/api/agent-run",payload); currentProject=payload.project; currentSession={...data.agent_result, run_id:data.agent_result.run_id}; await loadProjectState(currentSession.run_id); navigate("/review",currentSession.run_id); setStatus("Run artifacts prepared for review."); }); }
    async function runSafeDemo() { await runBusy(async()=>{ const data=await postJson("/api/quickstart-demo",{}); const summary=data.demo_summary; $("project").value=summary.copied_project; currentProject=summary.copied_project; await loadProjectState(summary.run_id); navigate("/review",summary.run_id); setStatus("Safe demo complete. Review package ready with warnings."); }); }

    async function loadSessions() { const project=$("project").value.trim() || currentProject; currentArtifactState=null; if(!project){ renderSessions(null); return; } const data=await postJson("/api/sessions",{project}); currentProject=project; currentIndex=data.session_index; try { const artifactData=await getJson(`/api/artifact-state?project=${encodeURIComponent(project)}`); currentArtifactState=available(artifactData.artifact_state); } catch(requestError) { currentArtifactState=requestError.code === "ARTIFACT_MISSING" ? missing(requestError.code) : error(requestError.code,requestError.message); } renderSessions(currentIndex); renderOverview(); updateContext(); }
    async function loadProjectState(runId) { await loadSessions(); currentSession=runId ? (currentIndex.sessions || []).find(item=>(item.run_id || item.session_id)===runId) || {run_id:runId} : null; updateContext(); }
    function renderSessions(index) { const sessions=index && Array.isArray(index.sessions) ? index.sessions.slice().reverse() : []; if(!sessions.length){$("sessions").innerHTML='<div class="empty"><h3 data-i18n="sessions.emptyTitle">No sessions yet</h3><p>Select a project first or prepare a run.</p></div>';$("overviewSessions").innerHTML='<div class="empty">No recorded sessions.</div>';return;} const rows=sessions.map(item=>`<div class="session-row"><div><strong class="review-run-id">${escapeHtml(item.run_id || item.session_id)}</strong><div>${statusChip(item.status)} <span class="context-meta">${escapeHtml(item.target_locale || "")}</span></div></div><button type="button" onclick="selectSession('${escapeJs(item.run_id || item.session_id)}')">Open review</button></div>`).join(""); $("sessions").innerHTML=rows; $("overviewSessions").innerHTML=rows; }
    function selectSession(runId) { const sessions=currentIndex && Array.isArray(currentIndex.sessions) ? currentIndex.sessions : []; currentSession=sessions.find(item=>(item.run_id || item.session_id)===runId) || {run_id:runId}; currentRunView=null; updateContext(); navigate("/review",runId); }
    function renderOverview() { const projectBody=$("overviewProjectBody"); if(!currentProject){projectBody.innerHTML='<div class="empty">Choose a project to begin.</div>';return;} const artifactResult=currentArtifactState || missing("NOT_LOADED"); const artifactCopy=artifactResult.kind === "available" ? `Artifact state: ${statusText(artifactResult.data.status || "unknown")}` : `Artifact state: ${artifactResult.kind}`; projectBody.innerHTML=`<strong class="path">${escapeHtml(currentProject)}</strong><p>${currentIndex && currentIndex.latest_session_id ? `Latest run: ${escapeHtml(currentIndex.latest_session_id)}` : "No runs recorded."}</p><p>${escapeHtml(artifactCopy)}</p>`; $("nextAction").innerHTML=currentIndex && currentIndex.latest_session_id ? '<button class="primary" type="button" onclick="navigate(\'/review\', currentIndex.latest_session_id)">Review latest run</button>' : '<button class="primary" type="button" onclick="navigate(\'/generate\')">Prepare first run</button>'; }

    async function renderSessionReview(session) {
      const project=$("project").value.trim() || currentProject; const runId=session && (session.run_id || session.session_id);
      if(!project || !runId){showReviewEmpty("Select a run","Select a session or run the safe demo to open Review.",false);return;}
      try {
        const view=await getJson(`/api/workbench-run?project=${encodeURIComponent(project)}&run_id=${encodeURIComponent(runId)}`);
        currentRunView=view; currentSession=view.session; $("reviewEmpty").hidden=true; $("reviewContent").hidden=false;
        $("reviewRunId").textContent=view.run_id; $("reviewRunFreshness").textContent=view.freshness; $("reviewRunFreshness").className=`status-chip ${view.freshness === "current" ? "success" : "warning"}`;
        const summaryArtifact=resultFromProjection(view.summary_artifact); const summary=summaryArtifact.kind === "available" ? summaryArtifact.data : (view.summary || {}); $("runStatus").textContent=statusText(summary.status || view.session.status); $("extractionCoverage").textContent=summary.segment_count != null ? `${summary.segment_count} segments` : "Unavailable"; $("qaStatus").textContent=statusText(summary.qa_status || "not_checked");
        const readinessEvidence=reviewEvidence(view,"review_readiness"); const deliveryEvidence=reviewEvidence(view,"delivery_readiness"); const applyEvidence=reviewEvidence(view,"apply_readiness"); const artifactEvidence=reviewEvidence(view,"artifact_state");
        renderArtifactState(artifactEvidence,view.artifacts || []); renderProjection("reviewReadiness",readinessEvidence); renderProjection("deliveryReadiness",deliveryEvidence); await renderApply(view,applyEvidence); renderRisks(view,[readinessEvidence,deliveryEvidence,applyEvidence]); renderQueue(view); renderArtifacts(view.artifacts || []); renderProviderSmoke(view);
        updateContext();
      } catch(requestError) { currentRunView=null; currentSession=session; showReviewEmpty("Unable to load this run",requestError.message || "The selected run could not be loaded.",requestError.recoverable !== false); showError(requestError); }
    }
    function showReviewEmpty(title, message, retryable) { $("reviewEmpty").hidden=false; $("reviewContent").hidden=true; $("reviewEmptyTitle").textContent=title; $("reviewEmptyMessage").textContent=message; $("reviewRetry").hidden=!retryable; }
    function retryReviewLoad() { if(currentSession) runBusy(()=>renderSessionReview(currentSession)); }
    function reviewEvidence(view, key) { const selected=view[key] || {state:"missing",reason:"ARTIFACT_MISSING"}; const current=view.current_project_projection; const sameRunCurrent=view.freshness === "current" && current && current.run_id === view.run_id; const candidate=sameRunCurrent && current[key]; if(selected.state === "missing" && candidate && candidate.state !== "missing") return {projection:candidate,scope:"Current project evidence for the same run (snapshot missing)"}; return {projection:selected,scope:"Selected run snapshot"}; }
    function evidenceStatus(data) { return data.status || data.review_readiness_status || data.delivery_status || data.delivery_readiness_status || data.apply_status || data.apply_readiness_status || "available"; }
    function evidenceSummary(data) { const value=data.reason || data.recommended_next_action || (Array.isArray(data.recommended_next_actions) ? data.recommended_next_actions[0] : ""); return typeof value === "string" && value ? value : "Runtime evidence is available."; }
    function renderArtifactState(evidence, artifacts) { const result=resultFromProjection(evidence.projection); if(result.kind !== "available"){ $("artifactStateStatus").textContent=statusText(result.kind); $("artifactStateCounts").textContent="Artifact state evidence is unavailable"; return; } const data=result.data || {}; const summary=data.summary || {}; $("artifactStateStatus").textContent=statusText(data.status || "unknown"); const counts=[`${Array.isArray(artifacts) ? artifacts.length : "Unavailable"} indexed`,`${summary.stale_count ?? "Unavailable"} stale`,`${summary.missing_required_count ?? "Unavailable"} required missing`,`${summary.requires_human_review_count ?? "Unavailable"} need review`]; $("artifactStateCounts").textContent=counts.join(" · "); }
    function renderProjection(id, evidence) { const projection=evidence.projection; const result=resultFromProjection(projection); const node=$(id); const scope=`<div class="evidence-scope">${escapeHtml(evidence.scope)}</div>`; if(result.kind==="available"){ const data=result.data || {}; node.innerHTML=`${statusChip(evidenceStatus(data))}${scope}<p>${escapeHtml(evidenceSummary(data))}</p>${rawPreviewAction(result,projection.path)}`; } else node.innerHTML=`${statusChip(result.kind)}${scope}<p>${escapeHtml(result.message || result.reason || "Evidence unavailable")}</p>${rawPreviewAction(result,projection && projection.path)}`; }
    async function readJsonArtifact(path) { if(!path) return missing("ARTIFACT_MISSING"); try { const data=await postJson("/api/read-artifact",{path}); rawArtifactPreviews[path]={raw:data.content,truncated:data.truncated}; try{return available(JSON.parse(data.content));}catch(_){return error("INVALID_ARTIFACT_JSON","Artifact is not valid JSON.",path);} } catch(requestError){return error(requestError.code,requestError.message,path);} }
    async function renderApply(view, evidence) { const artifacts=Object.fromEntries((view.artifacts || []).map(item=>[item.artifact_id,item.path])); const plan=await readJsonArtifact(artifacts.apply_plan); const projection=resultFromProjection(evidence.projection); const scope=`<div class="evidence-scope">${escapeHtml(evidence.scope)}</div>`; if(plan.kind==="available"){const data=plan.data || {}; $("applyDetails").innerHTML=`${statusChip(projection.kind === "available" ? evidenceStatus(projection.data || {}) : projection.kind)}${scope}<p>${escapeHtml(data.operation_count != null ? `${data.operation_count} planned operations` : "Apply plan available")}</p><p>Applying output requires separate authorization.</p>${rawPreviewAction(plan,artifacts.apply_plan)}`;}else{$("applyDetails").innerHTML=`${statusChip(projection.kind)}${scope}<p>Apply execution is not exposed in this Workbench.</p>${rawPreviewAction(plan,artifacts.apply_plan)}`;} }
    function riskText(item) { if(typeof item === "string") return item; if(!item || typeof item !== "object") return ""; return item.summary || item.recommended_action || item.reason || item.required_decision || ""; }
    function renderRisks(view, evidences) { const risks=[...(view.limitations || [])]; for(const evidence of evidences){const result=resultFromProjection(evidence.projection);if(result.kind !== "available") continue;const data=result.data || {};for(const group of [data.blockers,data.warnings,data.limitations]) for(const item of (Array.isArray(group) ? group : [])){const text=riskText(item);if(text) risks.push(text);}} if(view.newer_project_state_available) risks.unshift("Newer project state exists. This page remains scoped to the selected historical run."); const unique=[...new Set(risks)]; if(!unique.length) unique.push("No recorded limitation artifact was found. This is not proof that the run is risk-free."); const visible=unique.slice(0,8); if(unique.length>visible.length) visible.push(`${unique.length-visible.length} more recorded items are available in the raw artifacts.`); $("riskList").innerHTML=visible.map(item=>`<li class="list-item">${escapeHtml(item)}</li>`).join(""); }
    function renderQueue(view) { const current=view.current_project_projection; const useCurrent=view.freshness === "current" && current && current.run_id === view.run_id; const queueProjection=useCurrent ? current.queues.review : view.queues.review; $("queueScope").textContent=useCurrent ? "Current project queue for this exact run" : "Selected run queue snapshot"; $("queueScope").dataset.copy=useCurrent ? "review.queueScopeCurrent" : "review.queueScopeSelected"; const result=resultFromProjection(queueProjection); const items=result.kind==="available" && Array.isArray(result.data.items) ? result.data.items : []; $("actionQueue").innerHTML=items.length ? items.map(item=>`<div class="action-row"><div><strong>${escapeHtml(item.title || item.item_id || "Queue item")}</strong><p>${escapeHtml(item.reason || item.status || "")}</p></div><button type="button" onclick="prefillAction('${escapeJs(item.item_id || "")}')">Act</button></div>`).join("") : `<div class="empty">No actionable queue items for this scope.${rawPreviewAction(result,queueProjection && queueProjection.path)}</div>`; }
    function prefillAction(itemId) { $("actionItemId").value=itemId; $("actionReason").focus(); }
    async function submitReviewAction(event) { event.preventDefault(); if(!currentRunView) return; await runBusy(async()=>{ const target_queue_item_id=$("actionItemId").value.trim(); const action={run_id:currentRunView.run_id, action_type:$("actionType").value, actor_role:"project_owner", target_queue_item_id, payload:{reason:$("actionReason").value.trim(), target_queue_item_id}}; if(action.run_id !== currentRunView.run_id) throw new WorkbenchRequestError("RUN_STATE_MISMATCH","review.actionRunMismatch",409,true,["RELOAD_RUN"]); const endpoint=action.action_type === "request_follow_up" ? "/api/workbench-readiness-action" : "/api/workbench-action"; const result=await postJson(endpoint,{project:currentProject,run_id:currentRunView.run_id,action}); const output=result.workbench_action_result || result.workbench_readiness_action_result || result; $("actionResult").textContent=result.outcome || result.status || output.outcome || output.status || "recorded"; await renderSessionReview(currentSession); }); }
    function renderArtifacts(artifacts) { const readable=artifacts.filter(item=>item.state !== "directory"); const recent=readable.slice(0,4).map(item=>`<div class="artifact-row"><div><strong>${escapeHtml(item.artifact_id)}</strong><div class="path">${escapeHtml(item.path)}</div></div><button type="button" onclick="previewArtifact('${escapeJs(item.path)}')">Open</button></div>`).join(""); $("recentArtifacts").innerHTML=recent || '<div class="empty">No readable artifacts.</div>'; $("allArtifacts").innerHTML=artifacts.length ? artifacts.map(item=>`<div class="artifact-row"><div><strong>${escapeHtml(item.artifact_id)}</strong><div class="path">${escapeHtml(item.path)}</div></div>${item.state === "directory" ? '<span class="status-chip">path only</span>' : `<button type="button" onclick="previewArtifact('${escapeJs(item.path)}')">Open</button>`}</div>`).join("") : '<div class="empty">No artifacts indexed.</div>'; }
    function renderProviderSmoke(view) { const artifacts=Object.fromEntries((view.artifacts || []).map(item=>[item.artifact_id,item.path])); const closure=artifacts.provider_smoke_closure_report; const manifest=artifacts.provider_smoke_evidence_manifest; $("providerSmoke").innerHTML=closure && manifest ? `<p>Provider path evidence is indexed for this run.</p><button type="button" onclick="previewArtifact('${escapeJs(manifest)}')">Open evidence manifest</button>` : "No provider smoke evidence found. The field provider_or_model_called_by_runtime is unavailable."; }
    function rawPreviewAction(result, path) { if(!path || !result || result.kind === "missing") return ""; if(result.data) rawArtifactPreviews[path]={raw:JSON.stringify(result.data,null,2),truncated:false}; return `<button type="button" onclick="openRawArtifactPreview('${escapeJs(path)}')">Open raw artifact</button>`; }
    async function previewArtifact(path) { await runBusy(async()=>{ const data=await postJson("/api/read-artifact",{path}); rawArtifactPreviews[path]={raw:data.content,truncated:data.truncated}; openRawArtifactPreview(path); }); }
    function openRawArtifactPreview(path) { const cached=rawArtifactPreviews[path]; if(!cached){previewArtifact(path);return;} inspectorReturnFocus=document.activeElement; $("inspectorPath").textContent=path; $("inspectorContent").textContent=cached.raw+(cached.truncated ? "\n\n[truncated]" : ""); $("reviewInspector").classList.add("open"); $("reviewInspector").setAttribute("aria-hidden","false"); $("inspectorClose").focus(); }
    function closeInspector() { $("reviewInspector").classList.remove("open"); $("reviewInspector").setAttribute("aria-hidden","true"); if(inspectorReturnFocus && typeof inspectorReturnFocus.focus === "function") inspectorReturnFocus.focus(); inspectorReturnFocus=null; }
    function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]); }
    function escapeJs(value) { return String(value ?? "").replace(/\\/g,"\\\\").replace(/'/g,"\\'"); }

    async function restoreFromUrl() { const url=new URL(location.href); const project=url.searchParams.get("project") || ""; const runId=url.searchParams.get("run"); if($("project").value.trim() !== project){$("project").value=project;currentProject=project;currentIndex=null;currentSession=null;currentRunView=null;resetProjectWorkflow();} renderRoute(); if(project){await runBusy(async()=>{await loadProjectState(runId);if(location.pathname==="/review" && currentSession) await renderSessionReview(currentSession);});}else{renderOverview();updateContext();} }
    async function initializeWorkbench() { applyLanguage(); syncWorkflowControls(); try { const health=await getJson("/api/health"); $("healthDot").classList.add("pass"); $("healthLabel").textContent="Local service ready"; $("settingsHealth").textContent=`Local service ready, version ${health.version}`; } catch(healthError) { $("healthLabel").textContent="Local service offline"; $("settingsHealth").textContent=healthError.message; } await restoreFromUrl(); }
    document.querySelectorAll("[data-route]").forEach(link=>link.addEventListener("click",event=>{event.preventDefault();navigate(link.dataset.route);}));
    $("project").addEventListener("input",()=>{currentSession=null;currentRunView=null;currentIndex=null;currentArtifactState=null;setFieldError("project","");resetProjectWorkflow();updateContext();});
    $("sourceLocale").addEventListener("input",()=>{if(routingReady){$("sourceLocaleBadge").textContent="Manual";$("sourceLocaleHint").textContent="Source language adjusted manually after recognition.";}setFieldError("targetLocale","");syncWorkflowControls();});
    $("targetLocale").addEventListener("input",()=>{setFieldError("targetLocale","");syncWorkflowControls();});
    $("filePicker").addEventListener("change",event=>importSelectedFiles(event.target.files));
    $("reviewInspector").addEventListener("click",event=>{if(event.target === $("reviewInspector")) closeInspector();});
    document.addEventListener("keydown",event=>{if(event.key === "Escape" && $("reviewInspector").classList.contains("open")) closeInspector();});
    window.addEventListener("popstate",restoreFromUrl);
    initializeWorkbench();
  </script>
</body>
</html>
"""
