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
        <nav class="nav-links" aria-label="Workbench sections" data-i18n-aria-label="nav.aria" aria-describedby="navScrollHint">
          <a href="/" data-route="/" aria-current="page" data-i18n="nav.overview">Overview</a>
          <a href="/generate" data-route="/generate" data-i18n="nav.generate">Prepare</a>
          <a href="/review" data-route="/review" data-i18n="nav.review">Review</a>
          <a href="/sessions" data-route="/sessions" data-i18n="nav.sessions">Sessions</a>
          <a href="/settings" data-route="/settings" data-i18n="nav.settings">Settings</a>
        </nav>
      </div>
      <div class="header-tools">
        <span class="health-dot" id="healthDot" aria-hidden="true"></span>
        <span class="health-label" id="healthLabel" data-i18n="health.checking">Checking local service</span>
      </div>
    </div>
    <div class="context-strip">
      <div class="context-inner">
        <div class="context-copy"><strong id="contextProject" data-i18n="context.noProject">No project selected</strong><span class="context-meta" id="contextRun" data-i18n="context.noRun">No run selected</span></div>
        <button class="context-action" id="contextProjectAction" type="button" onclick="navigate('/generate')" data-i18n="context.openProject">Open project</button>
      </div>
    </div>
  </header>

  <main id="main-content" tabindex="-1">
    <div id="successStatus" class="status-notice" role="status" aria-live="polite"></div>
    <div id="errorStatus" class="error-notice" role="alert"><span id="errorMessage"></span><button type="button" onclick="clearError()" data-i18n="common.dismiss">Dismiss</button></div>

    <section class="page" data-page="/">
      <div class="home-dashboard">
        <div class="card hero">
          <p class="eyebrow" data-i18n="overview.kicker">Local, review-first workflow</p>
          <h1 id="pageTitle" data-i18n="overview.title">Prepare localization work with evidence</h1>
          <p class="lead" data-i18n="overview.lead">Inspect a project, prepare a provider-free handoff, review exact run evidence, and keep Apply behind separate authorization.</p>
          <div class="hero-actions">
            <button class="primary" type="button" onclick="runSafeDemo()" data-i18n="overview.safeDemo">Run safe demo</button>
            <button type="button" onclick="navigate('/generate')" data-i18n="overview.openProject">Open local project</button>
          </div>
          <div class="boundary">
            <div class="boundary-item"><strong data-i18n="overview.boundaryProviderTitle">No provider or model call from the safe demo</strong><span data-i18n="overview.boundaryProviderCopy">Uses a copied public fixture and synthetic output.</span></div>
            <div class="boundary-item"><strong data-i18n="overview.boundarySourceTitle">Source files stay unchanged</strong><span data-i18n="overview.boundarySourceCopy">Prepared artifacts are written outside the source project.</span></div>
            <div class="boundary-item"><strong data-i18n="overview.boundaryApplyTitle">Applying output requires separate authorization</strong><span data-i18n="overview.boundaryApplyCopy">The Workbench previews the Apply plan but does not execute it.</span></div>
          </div>
        </div>
        <div class="project-dashboard" id="overviewProject">
          <div class="grid two">
            <div class="card"><div class="card-header"><div><h2 data-i18n="overview.currentProjectTitle">Current project</h2><p class="card-copy" data-i18n="overview.currentProjectCopy">Local project context and latest run.</p></div></div><div class="card-body" id="overviewProjectBody"><div class="empty" data-i18n="overview.chooseProject">Choose a project to begin.</div></div></div>
            <div class="card"><div class="card-header"><div><h2 data-i18n="overview.nextActionTitle">Next useful action</h2><p class="card-copy" data-i18n="overview.nextActionCopy">One task at a time, based on available evidence.</p></div></div><div class="card-body" id="nextAction"><button class="primary" type="button" onclick="navigate('/generate')" data-i18n="overview.selectProject">Select project</button></div></div>
          </div>
          <div class="card"><div class="card-header"><div><h2 data-i18n="overview.recentSessionsTitle">Recent sessions</h2><p class="card-copy" data-i18n="overview.recentSessionsCopy">Open an exact run without falling back to latest.</p></div></div><div class="card-body" id="overviewSessions"><div class="empty" data-i18n="sessions.noneRecorded">No recorded sessions.</div></div></div>
        </div>
      </div>
    </section>

    <section class="page" data-page="/generate" hidden>
      <div class="workflow-shell">
        <div class="page-heading"><div><p class="eyebrow" data-i18n="prepare.kicker">Prepare</p><h1 data-i18n="prepare.title">Set up localization in order</h1><p class="lead" data-i18n="prepare.lead">Choose a project, confirm what was recognized, then set the language direction before preparing any handoff.</p></div></div>
        <div class="card workflow-card">
          <section class="workflow-section" aria-labelledby="projectStepTitle">
            <div class="step-index" aria-hidden="true">1</div>
            <div class="stage-content">
              <div class="step-heading"><h2 id="projectStepTitle" data-i18n="prepare.projectTitle">Choose the project</h2><p data-i18n="prepare.projectCopy">Open a local folder, or paste its path and recognize it manually.</p></div>
              <div class="project-path-row">
                <div><label for="project" data-i18n="prepare.projectPath">Project path *</label><input id="project" aria-describedby="projectError" placeholder="C:\path\to\project" data-i18n-placeholder="prepare.projectPlaceholder"><div class="field-error" id="projectError"></div></div>
                <button id="recognizeProjectButton" type="button" onclick="inspectProject()" data-i18n="prepare.recognizeProject">Recognize project</button>
              </div>
              <div class="choice-row">
                <button class="primary" id="chooseProjectButton" type="button" onclick="pickProjectDirectory()" data-i18n="prepare.chooseFolder">Choose local folder</button>
                <button id="importFilesButton" type="button" onclick="$('filePicker').click()" data-i18n="prepare.importFiles">Import files instead</button><input id="filePicker" type="file" multiple aria-label="Import files" data-i18n-aria-label="prepare.importFilesAria" hidden>
                <p class="choice-note" data-i18n="prepare.projectPrivacy">Local folders stay on this computer. Imported files are copied to a temporary project.</p>
              </div>
            </div>
          </section>

          <section class="workflow-section" id="recognitionSection" aria-labelledby="recognitionStepTitle">
            <div class="step-index" aria-hidden="true">2</div>
            <div class="stage-content">
              <div class="step-heading"><h2 id="recognitionStepTitle" data-i18n="prepare.recognitionTitle">Confirm the recognized project</h2><p data-i18n="prepare.recognitionCopy">Project type and resource routing come directly from the local inspection result.</p></div>
              <div id="routing" aria-live="polite"><div class="recognition-placeholder"><strong data-i18n="prepare.waitingProject">Waiting for a project</strong><p data-i18n="prepare.waitingProjectCopy">Recognition starts automatically after a folder is chosen.</p></div></div>
            </div>
          </section>

          <section class="workflow-section is-locked" id="languageSection" aria-labelledby="languageStepTitle" aria-disabled="true">
            <div class="step-index" aria-hidden="true">3</div>
            <div class="stage-content">
              <div class="step-heading"><h2 id="languageStepTitle" data-i18n="prepare.languageTitle">Set the language direction</h2><p data-i18n="prepare.languageCopy">The source is suggested from recognized metadata or writing system. You can correct it before continuing.</p></div>
              <div class="locale-flow">
                <div class="locale-card source">
                  <div class="locale-role"><span data-i18n="prepare.sourceRole">Source</span><span class="auto-badge" id="sourceLocaleBadge" data-i18n="prepare.waitingRecognition">Waiting for recognition</span></div>
                  <label for="sourceLocale" data-i18n="prepare.sourceLanguage">Source language</label>
                  <input id="sourceLocale" value="en-US" list="localeOptions" autocomplete="off" disabled>
                  <p class="locale-hint" id="sourceLocaleHint" data-i18n="prepare.sourceHintInitial">Choose a project to get a source-language suggestion.</p>
                </div>
                <div class="locale-arrow" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M5 12h14M14 7l5 5-5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
                <div class="locale-card">
                  <div class="locale-role"><span data-i18n="prepare.targetRole">Target</span><span data-i18n="common.required">Required</span></div>
                  <label for="targetLocale" data-i18n="prepare.targetLanguage">Target language</label>
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
              <div class="step-heading"><h2 id="prepareStepTitle" data-i18n="prepare.handoffTitle">Prepare the handoff</h2><p data-i18n="prepare.handoffCopy">Review the recognized project and language direction, then choose the smallest useful next action.</p></div>
              <div class="workflow-options">
                <div><label for="operatingMode" data-i18n="prepare.workflowMode">Workflow mode</label><select id="operatingMode" disabled><option value="greenfield_localization" data-i18n="prepare.modeNew">New localization</option><option value="existing_locale_maintenance" data-i18n="prepare.modeMaintain">Maintain an existing locale</option><option value="blind_benchmark" data-i18n="prepare.modeBenchmark">Blind benchmark</option></select></div>
                <span class="status-chip" data-i18n="prepare.providerFree">Provider-free preparation</span>
              </div>
              <details>
                <summary data-i18n="prepare.advancedOptions">Advanced run options</summary>
                <div class="details-body form-grid">
                  <div class="wide"><label for="sourceFiles" data-i18n="prepare.sourceFiles">Recognized source files, one relative path per line</label><textarea id="sourceFiles" disabled></textarea></div>
                  <div><label for="outputRoot" data-i18n="prepare.outputRoot">Output root</label><input id="outputRoot" disabled></div>
                  <div><label for="runId" data-i18n="prepare.runId">Run ID</label><input id="runId" disabled></div>
                  <div><label for="maxSegments" data-i18n="prepare.segmentLimit">Segment limit</label><input id="maxSegments" type="number" min="1" value="80" disabled></div>
                  <div><label for="responsesDir" data-i18n="prepare.responsesDir">Generated responses directory</label><input id="responsesDir" disabled></div>
                </div>
              </details>
              <div class="workflow-actions">
                <button class="primary" id="prepareHandoffButton" type="button" onclick="runAgent('handoff')" disabled data-i18n="prepare.prepareHandoff">Prepare generation handoff</button>
                <button id="syntheticDraftButton" type="button" onclick="runAgent('synthetic')" disabled data-i18n="prepare.syntheticDraft">Stage synthetic draft (demo)</button>
                <button id="importResponsesButton" type="button" onclick="runAgent('responses')" disabled data-i18n="prepare.importResponses">Import generated responses</button>
              </div>
              <p class="safety-note" data-i18n="prepare.safety">Preparation creates evidence and staged artifacts. It does not call a provider, change source files, authorize delivery, or execute Apply.</p>
            </div>
          </section>
        </div>
      </div>
    </section>

    <section class="page" data-page="/review" hidden>
      <div class="review-run-header"><div><p class="eyebrow" data-i18n="review.kicker">Review</p><h1 data-i18n="review.title">Exact run evidence</h1><p class="lead" data-i18n="review.lead">Readiness, delivery, claims, actions, and artifacts stay scoped to the selected run.</p></div><div><div class="review-run-id" id="reviewRunId" data-i18n="context.noRun">No run selected</div><span class="status-chip" id="reviewRunFreshness" data-i18n="review.notSelected">not selected</span></div></div>
      <div class="review-dashboard">
        <div id="reviewEmpty" class="card"><div class="card-body empty"><h2 id="reviewEmptyTitle" data-i18n="review.emptyTitle">Select a run</h2><p id="reviewEmptyMessage" data-i18n="review.emptyMessage">Select a session or run the safe demo to open Review.</p><div class="inline-actions"><button id="reviewRetry" type="button" onclick="retryReviewLoad()" hidden data-i18n="common.retry">Retry</button><button type="button" onclick="navigate('/sessions')" data-i18n="review.openSessions">Open sessions</button></div></div></div>
        <div id="reviewContent" class="stack" hidden>
          <div class="metric-grid">
            <div class="metric"><span data-i18n="review.runStatus">Run status</span><strong id="runStatus" data-i18n="common.unavailable">Unavailable</strong></div>
            <div class="metric"><span data-i18n="review.extractionCoverage">Extraction coverage</span><strong id="extractionCoverage" data-i18n="common.unavailable">Unavailable</strong></div>
            <div class="metric"><span data-i18n="review.qa">QA</span><strong id="qaStatus" data-i18n="status.not_checked">Not checked</strong></div>
            <div class="metric"><span data-i18n="review.artifactState">Artifact state</span><strong id="artifactStateStatus" data-i18n="common.unavailable">Unavailable</strong><span id="artifactStateCounts" data-i18n="review.noArtifactEvidence">No artifact evidence loaded</span></div>
          </div>
          <div class="grid three">
            <div class="card"><div class="card-header"><h2 data-i18n="review.readinessTitle">Review readiness</h2></div><div class="card-body" id="reviewReadiness"></div></div>
            <div class="card"><div class="card-header"><h2 data-i18n="review.deliveryTitle">Delivery</h2></div><div class="card-body" id="deliveryReadiness"></div></div>
            <div class="card"><div class="card-header"><h2 data-i18n="review.applyTitle">Apply plan</h2></div><div class="card-body" id="applyDetails"></div></div>
          </div>
          <div class="grid two">
          <div class="card"><div class="card-header"><div><h2 data-i18n="review.risksTitle">Risks and limitations</h2><p class="card-copy" data-i18n="review.risksCopy">Runtime evidence only. Scope and missing evidence stay explicit.</p></div></div><div class="card-body"><ul class="list" id="riskList"></ul></div></div>
            <div class="card"><div class="card-header"><div><h2 data-i18n="review.providerSmokeTitle">Provider smoke</h2><p class="card-copy" data-i18n="review.providerSmokeCopy">Two-segment path evidence is not a quality claim.</p></div></div><div class="card-body" id="providerSmoke" data-i18n="review.providerSmokeMissing">No provider smoke evidence found. The field provider_or_model_called_by_runtime is unavailable.</div></div>
          </div>
          <div class="grid two">
            <div class="card"><div class="card-header"><div><h2 data-i18n="review.queueTitle">Action queue</h2><p class="card-copy" id="queueScope" data-i18n="review.queueScopeSelected">Selected run evidence</p></div></div><div class="card-body"><div id="actionQueue" class="stack"></div><form id="actionComposer" class="stack" onsubmit="submitReviewAction(event)"><div><label for="actionItemId" data-i18n="review.queueItemId">Queue item ID</label><input id="actionItemId" name="target_queue_item_id"></div><div><label for="actionType" data-i18n="review.action">Action</label><select id="actionType"><option value="request_follow_up" data-i18n="review.requestFollowUp">Request follow-up</option><option value="acknowledge_limitation" data-i18n="review.acknowledgeLimitation">Acknowledge limitation</option></select></div><div><label for="actionReason" data-i18n="review.reason">Reason</label><textarea id="actionReason"></textarea></div><button type="submit" data-i18n="review.recordAction">Record action</button></form><div id="actionResult" role="status" aria-live="polite"></div></div></div>
            <div class="card"><div class="card-header"><div><h2 data-i18n="review.recentArtifactsTitle">Recent artifacts</h2><p class="card-copy" data-i18n="review.recentArtifactsCopy">Open readable files in the inspector.</p></div></div><div class="card-body" id="recentArtifacts"></div></div>
          </div>
          <div class="card"><div class="card-header"><div><h2 data-i18n="review.allArtifactsTitle">All runtime artifacts</h2><p class="card-copy" data-i18n="review.allArtifactsCopy">Directories remain path-only.</p></div></div><div class="card-body" id="allArtifacts"></div></div>
        </div>
      </div>
    </section>

    <section class="page" data-page="/sessions" hidden>
      <div class="page-heading"><div><p class="eyebrow" data-i18n="sessions.kicker">Sessions</p><h1 data-i18n="sessions.title">Recorded runs</h1><p class="lead" data-i18n="sessions.lead">Choose a run by identity. Historical evidence is never silently upgraded to current project state.</p></div></div>
      <div class="card"><div class="card-header"><div><h2 data-i18n="sessions.projectTitle">Project sessions</h2><p class="card-copy" data-i18n="sessions.newestFirst">Newest runs appear first.</p></div></div><div class="card-body" id="sessions"><div class="empty"><h3 data-i18n="sessions.emptyTitle">No sessions yet</h3><p data-i18n="sessions.emptyCopy">Select a project first or prepare a run.</p></div></div></div>
    </section>

    <section class="page" data-page="/settings" hidden>
      <div class="page-heading"><div><p class="eyebrow" data-i18n="settings.kicker">Settings</p><h1 data-i18n="settings.title">Workbench preferences</h1><p class="lead" data-i18n="settings.lead">Interface settings do not change runtime policy or provider authorization.</p></div></div>
      <div class="grid two">
        <div class="card"><div class="card-header"><h2 data-i18n="settings.languageTitle">Interface language</h2></div><div class="card-body"><p data-i18n="settings.languageCopy">Changes the complete Workbench interface, including forms, loading states, validation, and dynamic actions. Runtime evidence stays in its source language.</p><div class="language-switch" role="group" aria-label="Interface language" data-i18n-aria-label="settings.languageTitle"><button type="button" data-language="en" onclick="setLanguage('en')">English</button><button type="button" data-language="zh-CN" onclick="setLanguage('zh-CN')">中文</button></div></div></div>
        <div class="card"><div class="card-header"><h2 data-i18n="settings.serviceTitle">Local service</h2></div><div class="card-body"><p id="settingsHealth" data-i18n="settings.checking">Checking</p><p data-i18n="settings.serviceCopy">Health confirms only that this local Workbench service is reachable.</p></div></div></div>
      </div>
    </section>
  </main>

  <div class="operation-overlay" id="projectTransition" role="status" aria-live="polite" aria-atomic="true" tabindex="-1" hidden>
    <div class="operation-card">
      <div class="scan-indicator" aria-hidden="true"><span class="scan-ring"></span><span class="scan-core">LA</span></div>
      <p class="operation-kicker" data-i18n="operation.kicker">Project intake</p>
      <h2 id="projectTransitionTitle" data-i18n="operation.openingTitle">Opening project</h2>
      <p id="projectTransitionDetail" data-i18n="operation.openingDetail">Waiting for the local folder selection.</p>
      <div class="operation-track" aria-hidden="true"><span></span></div>
      <div class="operation-steps" aria-hidden="true">
        <span class="operation-step" data-operation-step="choose" data-i18n="operation.choose">Choose</span>
        <span class="operation-step" data-operation-step="inspect" data-i18n="operation.recognize">Recognize</span>
        <span class="operation-step" data-operation-step="ready" data-i18n="operation.ready">Ready</span>
      </div>
    </div>
  </div>

  <aside class="inspector" id="reviewInspector" role="dialog" aria-modal="true" aria-hidden="true" aria-labelledby="inspectorTitle">
    <div class="inspector-panel"><div class="inspector-header"><div><h2 id="inspectorTitle" data-i18n="inspector.title">Artifact</h2><div class="path" id="inspectorPath"></div></div><button id="inspectorClose" type="button" onclick="closeInspector()" data-i18n="common.close">Close</button></div><pre class="inspector-content" id="inspectorContent" dir="auto"></pre></div>
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
      en: {
        "app.title":"Localize Anything Workbench",
        "nav.aria":"Workbench sections","nav.overview":"Overview","nav.generate":"Prepare","nav.review":"Review","nav.sessions":"Sessions","nav.settings":"Settings",
        "a11y.skip":"Skip to main content","a11y.navScroll":"Navigation can scroll horizontally on small screens.",
        "health.checking":"Checking local service","health.ready":"Local service ready","health.readyVersion":"Local service ready, version {version}","health.offline":"Local service offline",
        "context.noProject":"No project selected","context.noRun":"No run selected","context.run":"Run {runId}","context.openProject":"Open project","context.changeProject":"Change project",
        "common.dismiss":"Dismiss","common.retry":"Retry","common.required":"Required","common.unavailable":"Unavailable","common.close":"Close","common.open":"Open","common.act":"Act","common.pathOnly":"path only",
        "overview.kicker":"Local, review-first workflow","overview.title":"Prepare localization work with evidence","overview.lead":"Inspect a project, prepare a provider-free handoff, review exact run evidence, and keep Apply behind separate authorization.",
        "overview.safeDemo":"Run safe demo","overview.openProject":"Open local project","overview.boundaryProviderTitle":"No provider or model call from the safe demo","overview.boundaryProviderCopy":"Uses a copied public fixture and synthetic output.","overview.boundarySourceTitle":"Source files stay unchanged","overview.boundarySourceCopy":"Prepared artifacts are written outside the source project.","overview.boundaryApplyTitle":"Applying output requires separate authorization","overview.boundaryApplyCopy":"The Workbench previews the Apply plan but does not execute it.",
        "overview.currentProjectTitle":"Current project","overview.currentProjectCopy":"Local project context and latest run.","overview.chooseProject":"Choose a project to begin.","overview.nextActionTitle":"Next useful action","overview.nextActionCopy":"One task at a time, based on available evidence.","overview.selectProject":"Select project","overview.recentSessionsTitle":"Recent sessions","overview.recentSessionsCopy":"Open an exact run without falling back to latest.","overview.latestRun":"Latest run: {runId}","overview.noRuns":"No runs recorded.","overview.artifactState":"Artifact state: {status}","overview.reviewLatest":"Review latest run","overview.prepareFirst":"Prepare first run",
        "prepare.kicker":"Prepare","prepare.title":"Set up localization in order","prepare.lead":"Choose a project, confirm what was recognized, then set the language direction before preparing any handoff.",
        "prepare.projectTitle":"Choose the project","prepare.projectCopy":"Open a local folder, or paste its path and recognize it manually.","prepare.projectPath":"Project path *","prepare.projectPlaceholder":"C:\\path\\to\\project","prepare.recognizeProject":"Recognize project","prepare.chooseFolder":"Choose local folder","prepare.importFiles":"Import files instead","prepare.importFilesAria":"Import files","prepare.projectPrivacy":"Local folders stay on this computer. Imported files are copied to a temporary project.",
        "prepare.recognitionTitle":"Confirm the recognized project","prepare.recognitionCopy":"Project type and resource routing come directly from the local inspection result.","prepare.waitingProject":"Waiting for a project","prepare.waitingProjectCopy":"Recognition starts automatically after a folder is chosen.","prepare.recognitionPending":"Recognition pending","prepare.recognitionPendingCopy":"Supported resources and project type will appear here.","prepare.noResources":"No supported localization resources found","prepare.noResourcesCopy":"Choose a different folder or import supported resource files.",
        "prepare.languageTitle":"Set the language direction","prepare.languageCopy":"The source is suggested from recognized metadata or writing system. You can correct it before continuing.","prepare.sourceRole":"Source","prepare.waitingRecognition":"Waiting for recognition","prepare.sourceLanguage":"Source language","prepare.sourceHintInitial":"Choose a project to get a source-language suggestion.","prepare.targetRole":"Target","prepare.targetLanguage":"Target language","prepare.noSuggestion":"No suggestion","prepare.noSuggestionCopy":"No source language can be suggested without supported resources.","prepare.autoSuggestion":"Auto · {confidence}","prepare.suggested":"suggested","prepare.suggestionFallback":"Suggested from project recognition.","prepare.manual":"Manual","prepare.manualSourceHint":"Source language adjusted manually after recognition.","prepare.recognitionRequiredHint":"Recognition must finish before the language direction is available.",
        "confidence.high":"high confidence","confidence.medium":"medium confidence","confidence.low":"low confidence","confidence.suggested":"suggested","suggestion.stringCatalog":"Read from the String Catalog source-language field.","suggestion.resourcePath":"Inferred from the locale identifier in the recognized resource path.","suggestion.writingSystem":"Inferred from the dominant writing system in recognized text resources.","suggestion.englishDefault":"No explicit source-language metadata was found; verify the English default.",
        "prepare.handoffTitle":"Prepare the handoff","prepare.handoffCopy":"Review the recognized project and language direction, then choose the smallest useful next action.","prepare.workflowMode":"Workflow mode","prepare.modeNew":"New localization","prepare.modeMaintain":"Maintain an existing locale","prepare.modeBenchmark":"Blind benchmark","prepare.providerFree":"Provider-free preparation","prepare.advancedOptions":"Advanced run options","prepare.sourceFiles":"Recognized source files, one relative path per line","prepare.outputRoot":"Output root","prepare.runId":"Run ID","prepare.segmentLimit":"Segment limit","prepare.responsesDir":"Generated responses directory","prepare.prepareHandoff":"Prepare generation handoff","prepare.syntheticDraft":"Stage synthetic draft (demo)","prepare.importResponses":"Import generated responses","prepare.safety":"Preparation creates evidence and staged artifacts. It does not call a provider, change source files, authorize delivery, or execute Apply.",
        "routing.detectedNature":"Detected project nature","routing.resources":"Resources","routing.adapters":"Adapters","routing.primaryRoute":"Primary route","routing.viewFiles":"View recognized files ({count})","routing.path":"Path","routing.adapter":"Adapter","routing.moreFiles":"{count} more recognized files are available in the inspection result.","routing.preflight":"Recommended preflight: {mode}",
        "projectType.android":"Android application resources","projectType.ios":"iOS string resources","projectType.xcstrings":"Apple String Catalog","projectType.document":"OpenXML document project","projectType.mixed":"Mixed localization project","projectType.generic":"General localization resources","projectType.unknown":"Unrecognized project",
        "adapter.android":"Android strings","adapter.ios":"iOS strings","adapter.xcstrings":"String Catalog","adapter.word":"Word documents","adapter.json":"JSON locale files","adapter.gettext":"Gettext catalogs","adapter.xliff":"XLIFF files","adapter.markup":"Markup content","adapter.subtitles":"Subtitles","adapter.tabular":"Tabular content","adapter.yaml":"YAML or TOML","adapter.unavailable":"Unavailable",
        "review.kicker":"Review","review.title":"Exact run evidence","review.lead":"Readiness, delivery, claims, actions, and artifacts stay scoped to the selected run.","review.notSelected":"not selected","review.emptyTitle":"Select a run","review.emptyMessage":"Select a session or run the safe demo to open Review.","review.openSessions":"Open sessions","review.loadErrorTitle":"Unable to load this run","review.loadErrorMessage":"The selected run could not be loaded.",
        "review.runStatus":"Run status","review.extractionCoverage":"Extraction coverage","review.qa":"QA","review.artifactState":"Artifact state","review.noArtifactEvidence":"No artifact evidence loaded","review.segments":"{count} segments","review.readinessTitle":"Review readiness","review.deliveryTitle":"Delivery","review.applyTitle":"Apply plan","review.risksTitle":"Risks and limitations","review.risksCopy":"Runtime evidence only. Scope and missing evidence stay explicit.","review.providerSmokeTitle":"Provider smoke","review.providerSmokeCopy":"Two-segment path evidence is not a quality claim.","review.providerSmokeMissing":"No provider smoke evidence found. The field provider_or_model_called_by_runtime is unavailable.",
        "review.queueTitle":"Action queue","review.queueScopeSelected":"Selected run evidence","review.queueScopeSelectedFull":"Selected run queue snapshot","review.queueScopeCurrent":"Current project queue for this exact run","review.queueItemId":"Queue item ID","review.action":"Action","review.requestFollowUp":"Request follow-up","review.acknowledgeLimitation":"Acknowledge limitation","review.reason":"Reason","review.recordAction":"Record action","review.queueItem":"Queue item","review.noQueueItems":"No actionable queue items for this scope.",
        "review.recentArtifactsTitle":"Recent artifacts","review.recentArtifactsCopy":"Open readable files in the inspector.","review.allArtifactsTitle":"All runtime artifacts","review.allArtifactsCopy":"Directories remain path-only.","review.noReadableArtifacts":"No readable artifacts.","review.noArtifacts":"No artifacts indexed.","review.openEvidenceManifest":"Open evidence manifest","review.providerEvidenceIndexed":"Provider path evidence is indexed for this run.","review.openRawArtifact":"Open raw artifact",
        "review.scopeCurrent":"Current project evidence for the same run (snapshot missing)","review.scopeSelected":"Selected run snapshot","review.runtimeEvidenceAvailable":"Runtime evidence is available.","review.evidenceUnavailable":"Evidence unavailable","review.artifactEvidenceUnavailable":"Artifact state evidence is unavailable","review.artifactCounts":"{indexed} indexed · {stale} stale · {missing} required missing · {review} need review","review.operations":"{count} planned operations","review.applyAvailable":"Apply plan available","review.applyAuthorization":"Applying output requires separate authorization.","review.applyNotExposed":"Apply execution is not exposed in this Workbench.","review.newerStateRisk":"Newer project state exists. This page remains scoped to the selected historical run.","review.noLimitations":"No recorded limitation artifact was found. This is not proof that the run is risk-free.","review.moreRisks":"{count} more recorded items are available in the raw artifacts.","review.recorded":"recorded",
        "sessions.kicker":"Sessions","sessions.title":"Recorded runs","sessions.lead":"Choose a run by identity. Historical evidence is never silently upgraded to current project state.","sessions.projectTitle":"Project sessions","sessions.newestFirst":"Newest runs appear first.","sessions.emptyTitle":"No sessions yet","sessions.emptyCopy":"Select a project first or prepare a run.","sessions.noneRecorded":"No recorded sessions.","sessions.openReview":"Open review",
        "settings.kicker":"Settings","settings.title":"Workbench preferences","settings.lead":"Interface settings do not change runtime policy or provider authorization.","settings.languageTitle":"Interface language","settings.languageCopy":"Changes the complete Workbench interface, including forms, loading states, validation, and dynamic actions. Runtime evidence stays in its source language.","settings.serviceTitle":"Local service","settings.checking":"Checking","settings.serviceCopy":"Health confirms only that this local Workbench service is reachable.",
        "operation.kicker":"Project intake","operation.openingTitle":"Opening project","operation.openingDetail":"Waiting for the local folder selection.","operation.choose":"Choose","operation.recognize":"Recognize","operation.ready":"Ready","operation.chooseTitle":"Choose a local project","operation.chooseDetail":"Use the system folder window to select the project you want to recognize.","operation.recognizingTitle":"Recognizing the project","operation.recognizingDetail":"Reading supported resources and adapter evidence. Large projects can take a little longer.","operation.recognizedTitle":"Project recognized","operation.recognizedDetail":"{count} supported resource files are ready to configure.","operation.readingFilesTitle":"Reading selected files","operation.readingFilesDetail":"Preparing {current} of {total} files for a temporary project.","operation.importingTitle":"Importing and recognizing","operation.importingDetail":"Creating the temporary project and reading supported resources.","operation.importedTitle":"Project imported",
        "inspector.title":"Artifact","inspector.truncated":"truncated",
        "validation.projectRequired":"Project path is required.","validation.chooseProject":"Choose or enter a project path.","validation.targetRequired":"Target language is required.","validation.targetDifferent":"Target language must differ from the source.","validation.recognizeFirst":"Recognize the project before preparing a handoff.","validation.responsesRequired":"Generated responses directory is required.","review.actionRunMismatch":"The selected run changed. Reload it before recording an action.",
        "success.projectLocal":"Local project recognized. Directory content stayed on this computer.","success.projectRecognized":"Project recognition complete.","success.filesImported":"Imported and recognized {count} files in a temporary project.","success.runPrepared":"Run artifacts prepared for review.","success.safeDemo":"Safe demo complete. Review package ready with warnings.",
        "error.invalidResponse":"The local service returned invalid JSON.","error.invalidArtifactJson":"The artifact is not valid JSON.","error.requestFailed":"Request failed",
        "status.unknown":"Unknown status","status.pass":"Pass","status.accepted":"Accepted","status.ready":"Ready","status.available":"Available","status.draft_package_created":"Draft package created","status.pending":"Pending","status.running":"Running","status.processing":"Processing","status.warning":"Warning","status.ready_with_warnings":"Ready with warnings","status.requires_human_review":"Requires human review","status.review_required":"Review required","status.stale":"Stale","status.historical":"Historical","status.blocked":"Blocked","status.blocking":"Blocking","status.authorization_required":"Authorization required","status.fail":"Fail","status.failed":"Failed","status.error":"Error","status.missing":"Missing","status.rejected":"Rejected","status.not_checked":"Not checked","status.unavailable":"Unavailable","status.current":"Current","status.directory":"Directory"
      },
      "zh-CN": {
        "app.title":"Localize Anything 工作台",
        "nav.aria":"工作台栏目","nav.overview":"概览","nav.generate":"准备","nav.review":"复核","nav.sessions":"运行记录","nav.settings":"设置",
        "a11y.skip":"跳到主要内容","a11y.navScroll":"小屏幕上导航可横向滚动。",
        "health.checking":"正在检查本地服务","health.ready":"本地服务已就绪","health.readyVersion":"本地服务已就绪，版本 {version}","health.offline":"本地服务离线",
        "context.noProject":"尚未选择项目","context.noRun":"尚未选择运行记录","context.run":"运行 {runId}","context.openProject":"打开项目","context.changeProject":"更换项目",
        "common.dismiss":"关闭提示","common.retry":"重试","common.required":"必填","common.unavailable":"不可用","common.close":"关闭","common.open":"打开","common.act":"处理","common.pathOnly":"仅路径",
        "overview.kicker":"本地优先、先复核后交付","overview.title":"用可核验的证据准备本地化工作","overview.lead":"识别项目，准备不调用服务商的交接包，复核本次运行的准确证据，并让应用操作始终受单独授权保护。",
        "overview.safeDemo":"运行安全演示","overview.openProject":"打开本地项目","overview.boundaryProviderTitle":"安全演示不会调用服务商或模型","overview.boundaryProviderCopy":"使用公开样例的副本和合成输出。","overview.boundarySourceTitle":"源文件保持不变","overview.boundarySourceCopy":"准备好的产物会写入源项目以外的位置。","overview.boundaryApplyTitle":"应用输出需要单独授权","overview.boundaryApplyCopy":"工作台只预览应用计划，不会执行应用操作。",
        "overview.currentProjectTitle":"当前项目","overview.currentProjectCopy":"本地项目上下文和最近一次运行。","overview.chooseProject":"请选择一个项目开始。","overview.nextActionTitle":"下一步建议","overview.nextActionCopy":"根据现有证据，一次只处理一项任务。","overview.selectProject":"选择项目","overview.recentSessionsTitle":"最近运行","overview.recentSessionsCopy":"按准确的运行标识打开，不会自动回退到最近一次。","overview.latestRun":"最近运行：{runId}","overview.noRuns":"暂无运行记录。","overview.artifactState":"产物状态：{status}","overview.reviewLatest":"复核最近运行","overview.prepareFirst":"准备第一次运行",
        "prepare.kicker":"准备","prepare.title":"按顺序设置本地化任务","prepare.lead":"先选择项目并确认识别结果，再设置源语言和目标语言，最后准备交接包。",
        "prepare.projectTitle":"选择项目","prepare.projectCopy":"打开本地文件夹，或粘贴路径后手动识别。","prepare.projectPath":"项目路径 *","prepare.projectPlaceholder":"C:\\项目路径\\project","prepare.recognizeProject":"识别项目","prepare.chooseFolder":"选择本地文件夹","prepare.importFiles":"改为导入文件","prepare.importFilesAria":"导入文件","prepare.projectPrivacy":"本地文件夹不会离开此电脑；导入的文件会复制到临时项目。",
        "prepare.recognitionTitle":"确认项目识别结果","prepare.recognitionCopy":"项目性质和资源路由直接来自本地检查结果。","prepare.waitingProject":"等待选择项目","prepare.waitingProjectCopy":"选择文件夹后会自动开始识别。","prepare.recognitionPending":"等待识别","prepare.recognitionPendingCopy":"支持的资源和项目性质会显示在这里。","prepare.noResources":"未找到支持的本地化资源","prepare.noResourcesCopy":"请选择其他文件夹，或导入受支持的资源文件。",
        "prepare.languageTitle":"设置语言方向","prepare.languageCopy":"系统会根据识别到的元数据或文字体系建议源语言，继续前可以手动修正。","prepare.sourceRole":"源语言","prepare.waitingRecognition":"等待识别","prepare.sourceLanguage":"源语言","prepare.sourceHintInitial":"选择项目后会显示源语言建议。","prepare.targetRole":"目标语言","prepare.targetLanguage":"目标语言","prepare.noSuggestion":"无建议","prepare.noSuggestionCopy":"没有受支持的资源，无法建议源语言。","prepare.autoSuggestion":"自动 · {confidence}","prepare.suggested":"建议值","prepare.suggestionFallback":"根据项目识别结果建议。","prepare.manual":"手动","prepare.manualSourceHint":"已在识别后手动调整源语言。","prepare.recognitionRequiredHint":"项目识别完成后才能设置语言方向。",
        "confidence.high":"高置信度","confidence.medium":"中等置信度","confidence.low":"低置信度","confidence.suggested":"建议值","suggestion.stringCatalog":"读取自字符串目录中的源语言字段。","suggestion.resourcePath":"根据已识别资源路径中的语言标识推断。","suggestion.writingSystem":"根据已识别文本资源中的主要文字体系推断。","suggestion.englishDefault":"未找到明确的源语言元数据，请核对默认的英语设置。",
        "prepare.handoffTitle":"准备交接包","prepare.handoffCopy":"核对识别到的项目和语言方向，然后选择当前最有用的下一步。","prepare.workflowMode":"工作流模式","prepare.modeNew":"新增本地化","prepare.modeMaintain":"维护现有语言版本","prepare.modeBenchmark":"盲测基准","prepare.providerFree":"不调用服务商","prepare.advancedOptions":"高级运行选项","prepare.sourceFiles":"识别到的源文件，每行一个相对路径","prepare.outputRoot":"输出根目录","prepare.runId":"运行 ID","prepare.segmentLimit":"片段上限","prepare.responsesDir":"生成结果目录","prepare.prepareHandoff":"准备生成交接包","prepare.syntheticDraft":"生成合成草稿（演示）","prepare.importResponses":"导入生成结果","prepare.safety":"准备过程只会创建证据和暂存产物，不会调用服务商、修改源文件、授权交付或执行应用操作。",
        "routing.detectedNature":"识别到的项目性质","routing.resources":"资源文件","routing.adapters":"适配器","routing.primaryRoute":"主要路由","routing.viewFiles":"查看识别到的文件（{count}）","routing.path":"路径","routing.adapter":"适配器","routing.moreFiles":"检查结果中还有 {count} 个已识别文件。","routing.preflight":"建议的预检模式：{mode}",
        "projectType.android":"Android 应用资源","projectType.ios":"iOS 字符串资源","projectType.xcstrings":"Apple 字符串目录","projectType.document":"OpenXML 文档项目","projectType.mixed":"混合本地化项目","projectType.generic":"通用本地化资源","projectType.unknown":"未识别的项目",
        "adapter.android":"Android 字符串","adapter.ios":"iOS 字符串","adapter.xcstrings":"字符串目录","adapter.word":"Word 文档","adapter.json":"JSON 语言文件","adapter.gettext":"Gettext 目录","adapter.xliff":"XLIFF 文件","adapter.markup":"标记文本","adapter.subtitles":"字幕","adapter.tabular":"表格内容","adapter.yaml":"YAML 或 TOML","adapter.unavailable":"不可用",
        "review.kicker":"复核","review.title":"本次运行的准确证据","review.lead":"就绪状态、交付、声明、操作和产物都严格限定在当前选择的运行记录。","review.notSelected":"未选择","review.emptyTitle":"选择一条运行记录","review.emptyMessage":"请选择一条运行记录，或运行安全演示后进入复核。","review.openSessions":"打开运行记录","review.loadErrorTitle":"无法载入这次运行","review.loadErrorMessage":"无法载入所选运行记录。",
        "review.runStatus":"运行状态","review.extractionCoverage":"提取覆盖","review.qa":"质量检查","review.artifactState":"产物状态","review.noArtifactEvidence":"尚未载入产物证据","review.segments":"{count} 个片段","review.readinessTitle":"复核就绪状态","review.deliveryTitle":"交付","review.applyTitle":"应用计划","review.risksTitle":"风险与限制","review.risksCopy":"只展示运行时证据，并明确标注范围和缺失证据。","review.providerSmokeTitle":"服务商冒烟检查","review.providerSmokeCopy":"两个片段的路径证据不代表质量结论。","review.providerSmokeMissing":"未找到服务商冒烟证据；字段 provider_or_model_called_by_runtime 不可用。",
        "review.queueTitle":"操作队列","review.queueScopeSelected":"所选运行的证据","review.queueScopeSelectedFull":"所选运行的队列快照","review.queueScopeCurrent":"此准确运行对应的当前项目队列","review.queueItemId":"队列项目 ID","review.action":"操作","review.requestFollowUp":"请求跟进","review.acknowledgeLimitation":"确认已知限制","review.reason":"原因","review.recordAction":"记录操作","review.queueItem":"队列项目","review.noQueueItems":"此范围内没有可处理的队列项目。",
        "review.recentArtifactsTitle":"最近产物","review.recentArtifactsCopy":"在检查器中打开可读取的文件。","review.allArtifactsTitle":"全部运行产物","review.allArtifactsCopy":"目录只显示路径。","review.noReadableArtifacts":"没有可读取的产物。","review.noArtifacts":"没有已索引的产物。","review.openEvidenceManifest":"打开证据清单","review.providerEvidenceIndexed":"本次运行已索引服务商路径证据。","review.openRawArtifact":"打开原始产物",
        "review.scopeCurrent":"同一次运行的当前项目证据（缺少快照）","review.scopeSelected":"所选运行的快照","review.runtimeEvidenceAvailable":"运行时证据可用。","review.evidenceUnavailable":"证据不可用","review.artifactEvidenceUnavailable":"产物状态证据不可用","review.artifactCounts":"已索引 {indexed} · 过期 {stale} · 缺少必需项 {missing} · 需复核 {review}","review.operations":"计划执行 {count} 项操作","review.applyAvailable":"应用计划可用","review.applyAuthorization":"应用输出需要单独授权。","review.applyNotExposed":"此工作台不提供应用执行入口。","review.newerStateRisk":"项目已有更新状态；此页面仍严格限定在所选历史运行。","review.noLimitations":"未找到已记录的限制产物，但这不能证明本次运行没有风险。","review.moreRisks":"原始产物中还有 {count} 条已记录内容。","review.recorded":"已记录",
        "sessions.kicker":"运行记录","sessions.title":"已记录的运行","sessions.lead":"按标识选择运行记录；历史证据绝不会被静默替换为当前项目状态。","sessions.projectTitle":"项目运行记录","sessions.newestFirst":"最近的运行排在最前。","sessions.emptyTitle":"暂无运行记录","sessions.emptyCopy":"请先选择项目或准备一次运行。","sessions.noneRecorded":"暂无已记录的运行。","sessions.openReview":"打开复核",
        "settings.kicker":"设置","settings.title":"工作台偏好设置","settings.lead":"界面设置不会更改运行时策略或服务商授权。","settings.languageTitle":"界面语言","settings.languageCopy":"切换整个工作台界面，包括表单、加载状态、校验提示和动态操作；运行时证据保持其原始语言。","settings.serviceTitle":"本地服务","settings.checking":"正在检查","settings.serviceCopy":"健康状态只表示本地工作台服务是否可访问。",
        "operation.kicker":"项目导入","operation.openingTitle":"正在打开项目","operation.openingDetail":"等待选择本地文件夹。","operation.choose":"选择","operation.recognize":"识别","operation.ready":"就绪","operation.chooseTitle":"选择本地项目","operation.chooseDetail":"请在系统文件夹窗口中选择要识别的项目。","operation.recognizingTitle":"正在识别项目","operation.recognizingDetail":"正在读取支持的资源和适配器证据；大型项目可能需要更长时间。","operation.recognizedTitle":"项目识别完成","operation.recognizedDetail":"已有 {count} 个受支持的资源文件可供配置。","operation.readingFilesTitle":"正在读取所选文件","operation.readingFilesDetail":"正在为临时项目准备第 {current}/{total} 个文件。","operation.importingTitle":"正在导入并识别","operation.importingDetail":"正在创建临时项目并读取受支持的资源。","operation.importedTitle":"项目导入完成",
        "inspector.title":"产物","inspector.truncated":"内容已截断",
        "validation.projectRequired":"项目路径为必填项。","validation.chooseProject":"请选择或输入项目路径。","validation.targetRequired":"目标语言为必填项。","validation.targetDifferent":"目标语言不能与源语言相同。","validation.recognizeFirst":"请先识别项目，再准备交接包。","validation.responsesRequired":"生成结果目录为必填项。","review.actionRunMismatch":"所选运行记录已变化，请重新载入后再记录操作。",
        "success.projectLocal":"本地项目识别完成；目录内容始终留在此电脑上。","success.projectRecognized":"项目识别完成。","success.filesImported":"已在临时项目中导入并识别 {count} 个文件。","success.runPrepared":"运行产物已准备好，可进入复核。","success.safeDemo":"安全演示完成；复核包已就绪，并带有警告。",
        "error.invalidResponse":"本地服务返回了无效的 JSON。","error.invalidArtifactJson":"产物不是有效的 JSON。","error.requestFailed":"请求失败",
        "status.unknown":"未知状态","status.pass":"通过","status.accepted":"已接受","status.ready":"就绪","status.available":"可用","status.draft_package_created":"草稿包已创建","status.pending":"等待中","status.running":"运行中","status.processing":"处理中","status.warning":"警告","status.ready_with_warnings":"就绪，但有警告","status.requires_human_review":"需要人工复核","status.review_required":"需要复核","status.stale":"已过期","status.historical":"历史状态","status.blocked":"已阻止","status.blocking":"阻止中","status.authorization_required":"需要授权","status.fail":"失败","status.failed":"失败","status.error":"错误","status.missing":"缺失","status.rejected":"已拒绝","status.not_checked":"未检查","status.unavailable":"不可用","status.current":"当前","status.directory":"目录"
      }
    };
    const STATUS_REGISTRY = {
      pass:{family:"success"}, accepted:{family:"success"}, ready:{family:"success"}, available:{family:"success"}, draft_package_created:{family:"success"},
      pending:{family:"progress"}, running:{family:"progress"}, processing:{family:"progress"},
      warning:{family:"warning"}, ready_with_warnings:{family:"warning"}, requires_human_review:{family:"warning"}, review_required:{family:"warning"}, stale:{family:"warning"}, historical:{family:"warning"},
      blocked:{family:"blocked"}, blocking:{family:"blocked"}, authorization_required:{family:"blocked"},
      fail:{family:"error"}, failed:{family:"error"}, error:{family:"error"}, missing:{family:"error"}, rejected:{family:"error"},
      not_checked:{family:"neutral"}, unavailable:{family:"neutral"}, current:{family:"neutral"}, directory:{family:"neutral"}
    };
    const savedLanguage = localStorage.getItem(LANGUAGE_KEY);
    let language = TRANSLATIONS[savedLanguage] ? savedLanguage : (navigator.language.toLowerCase().startsWith("zh") ? "zh-CN" : "en");
    let busy = false;
    let busyReturnFocus = null;
    let routingReady = false;
    let currentProject = "";
    let currentIndex = null;
    let currentArtifactState = null;
    let currentSession = null;
    let currentRunView = null;
    let currentRouting = null;
    let sourceLocaleManual = false;
    let healthState = {kind:"checking", version:""};
    let reviewEmptyState = {titleKey:"review.emptyTitle", messageKey:"review.emptyMessage", messageOverride:"", retryable:false};
    let inspectorReturnFocus = null;
    let operationReturnFocus = null;
    const rawArtifactPreviews = {};

    class WorkbenchRequestError extends Error {
      constructor(code, message, status, recoverable, actions) { super(message); this.code=code; this.status=status; this.recoverable=recoverable; this.actions=actions || []; }
    }
    function t(key, params={}) {
      const template=(TRANSLATIONS[language] || TRANSLATIONS.en)[key] || TRANSLATIONS.en[key] || key;
      return Object.entries(params).reduce((text,[name,value])=>text.replaceAll(`{${name}}`,String(value)),template);
    }
    function setLanguage(next) { if(!TRANSLATIONS[next]) return; language=next; localStorage.setItem(LANGUAGE_KEY,next); setStatus(""); clearError(); applyLanguage(); renderLocalizedState(); }
    function applyLanguage() {
      document.documentElement.lang=language;
      document.title=t("app.title");
      document.querySelectorAll("[data-i18n]").forEach((node)=>node.textContent=t(node.dataset.i18n));
      document.querySelectorAll("[data-i18n-placeholder]").forEach((node)=>node.setAttribute("placeholder",t(node.dataset.i18nPlaceholder)));
      document.querySelectorAll("[data-i18n-aria-label]").forEach((node)=>node.setAttribute("aria-label",t(node.dataset.i18nAriaLabel)));
      document.querySelectorAll("[data-language]").forEach((node)=>node.setAttribute("aria-pressed",String(node.dataset.language === language)));
    }
    function renderLocalizedState() {
      updateContext();
      renderRouting(currentRouting,true);
      renderSessions(currentIndex);
      renderOverview();
      renderHealth();
      if(currentRunView) void renderRunView(currentRunView); else renderReviewEmptyState();
    }
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
    function statusText(value) { return t(`status.${statusContract(value).status_code}`); }
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
      try { data = await response.json(); } catch (_) { throw new WorkbenchRequestError("INVALID_RESPONSE", t("error.invalidResponse"), response.status, true, ["RETRY"]); }
      if (!response.ok || data.status === "fail") {
        const details = data.error && typeof data.error === "object" ? data.error : {};
        throw new WorkbenchRequestError(details.code || data.message_code || "REQUEST_FAILED", details.message || data.error || t("error.requestFailed"), response.status, details.recoverable !== false, details.actions || []);
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
      $("contextProject").textContent=normalized ? normalized.split("/").pop() : t("context.noProject");
      $("contextRun").textContent=currentSession ? t("context.run",{runId:currentSession.run_id || currentSession.session_id}) : t("context.noRun");
      $("contextProjectAction").textContent=t(currentProject ? "context.changeProject" : "context.openProject");
    }
    function payloadBase() {
      const modeKey=$("operatingMode").value || "greenfield_localization";
      const mode=MODE_CONFIG[modeKey];
      return {project:$("project").value.trim(), source_locale:$("sourceLocale").value.trim() || "en-US", target_locale:$("targetLocale").value.trim(), source_files:$("sourceFiles").value, output_root:$("outputRoot").value.trim(), run_id:$("runId").value.trim(), max_segments:Number($("maxSegments").value || 80), operating_mode:modeKey, reference_policy:mode.reference_policy, workflow_depth:mode.workflow_depth, preflight_mode:mode.preflight_mode, privacy_mode:"standard", data_classification:"internal", status:"draft_package"};
    }
    function validateProjectInput() { const project=$("project").value.trim(); setFieldError("project",project ? "" : t("validation.projectRequired")); if(!project) throw new WorkbenchRequestError("VALIDATION_ERROR",t("validation.chooseProject"),400,true,[]); return project; }
    function validateRunInputs() { const project=validateProjectInput(); const source=$("sourceLocale").value.trim(); const target=$("targetLocale").value.trim(); const targetError=!target ? t("validation.targetRequired") : source === target ? t("validation.targetDifferent") : ""; setFieldError("targetLocale",targetError); if(!routingReady || targetError) throw new WorkbenchRequestError("VALIDATION_ERROR",!routingReady ? t("validation.recognizeFirst") : targetError,400,true,[]); return project; }

    async function pickProjectDirectory() { await runBusy(async()=>{ setProjectTransition("choose",t("operation.chooseTitle"),t("operation.chooseDetail")); try { const selection=await postJson("/api/pick-directory", {}); if(selection.status==="cancelled") return; currentSession=null; currentRunView=null; $("project").value=selection.project; currentProject=selection.project; resetProjectWorkflow(); updateContext(); setProjectTransition("inspect",t("operation.recognizingTitle"),t("operation.recognizingDetail")); const data=await postJson("/api/inspect",{project:selection.project}); useInspection(data); await loadProjectState(); navigate("/generate"); setProjectTransition("ready",t("operation.recognizedTitle"),t("operation.recognizedDetail",{count:data.routing.supported_file_count || 0})); await transitionPause(); setStatus(t("success.projectLocal")); } finally { hideProjectTransition(); } }); }
    function fileToBase64(file) { return new Promise((resolve,reject)=>{ const reader=new FileReader(); reader.onload=()=>resolve(String(reader.result || "").split(",",2)[1] || ""); reader.onerror=()=>reject(reader.error); reader.readAsDataURL(file); }); }
    async function importSelectedFiles(files) { const items=Array.from(files || []); if(!items.length) return; await runBusy(async()=>{ setProjectTransition("choose",t("operation.readingFilesTitle"),t("operation.readingFilesDetail",{current:0,total:items.length})); try { const payload=[]; for(let index=0;index<items.length;index++){const file=items[index];payload.push({relative_path:file.webkitRelativePath || file.name,content_base64:await fileToBase64(file)});$("projectTransitionDetail").textContent=t("operation.readingFilesDetail",{current:index+1,total:items.length});} setProjectTransition("inspect",t("operation.importingTitle"),t("operation.importingDetail")); const data=await postJson("/api/import-files",{files:payload}); currentSession=null; currentRunView=null; $("project").value=data.project; currentProject=data.project; useInspection(data); await loadProjectState(); navigate("/generate"); setProjectTransition("ready",t("operation.importedTitle"),t("operation.recognizedDetail",{count:data.routing.supported_file_count || 0})); await transitionPause(); setStatus(t("success.filesImported",{count:items.length})); } finally { hideProjectTransition(); $("filePicker").value=""; } }); }
    async function inspectProject() { await runBusy(async()=>{ const project=validateProjectInput(); resetProjectWorkflow(); setProjectTransition("inspect",t("operation.recognizingTitle"),t("operation.recognizingDetail")); try { const data=await postJson("/api/inspect",{project}); currentSession=null; currentRunView=null; currentProject=project; useInspection(data); await loadProjectState(); setProjectTransition("ready",t("operation.recognizedTitle"),t("operation.recognizedDetail",{count:data.routing.supported_file_count || 0})); await transitionPause(); setStatus(t("success.projectRecognized")); } finally { hideProjectTransition(); } }); }
    function resetProjectWorkflow() { routingReady=false; currentRouting=null; sourceLocaleManual=false; $("routing").innerHTML=`<div class="recognition-placeholder"><strong>${escapeHtml(t("prepare.recognitionPending"))}</strong><p>${escapeHtml(t("prepare.recognitionPendingCopy"))}</p></div>`; $("sourceLocaleBadge").textContent=t("prepare.waitingRecognition"); $("sourceLocaleHint").textContent=t("prepare.recognitionRequiredHint"); syncWorkflowControls(); }
    function useInspection(data) { const routing=data.routing || {}; sourceLocaleManual=false; $("sourceFiles").value=(data.source_files || (routing.supported_files || []).map(item=>item.path || item)).join("\n"); renderRouting(routing); }
    function projectTypeLabel(value) { const key=({android:"projectType.android",ios:"projectType.ios",xcstrings:"projectType.xcstrings",document:"projectType.document",mixed:"projectType.mixed",generic:"projectType.generic",unknown:"projectType.unknown"})[value]; return key ? t(key) : String(value || t("projectType.unknown")).replaceAll("_"," "); }
    function adapterLabel(value) { const key=({"core.android-strings":"adapter.android","core.ios-strings":"adapter.ios","core.xcstrings":"adapter.xcstrings","core.word-document":"adapter.word","core.json-locale":"adapter.json","core.gettext-po":"adapter.gettext","core.xliff":"adapter.xliff","core.markup":"adapter.markup","core.subtitles":"adapter.subtitles","core.tabular":"adapter.tabular","core.yaml-toml":"adapter.yaml"})[value]; return key ? t(key) : String(value || t("adapter.unavailable")); }
    function suggestionReason(value) { const key=({"Read from the String Catalog sourceLanguage field.":"suggestion.stringCatalog","Inferred from the locale identifier in the recognized resource path.":"suggestion.resourcePath","Inferred from the dominant writing system in recognized text resources.":"suggestion.writingSystem","No explicit source-language metadata was found; verify the English default.":"suggestion.englishDefault"})[value]; return key ? t(key) : value || t("prepare.suggestionFallback"); }
    function renderRouting(routing, preserveInputs=false) {
      currentRouting=routing || null;
      if(!routing){resetProjectWorkflow();return;}
      const files=routing.supported_files || []; const count=Number(routing.supported_file_count || 0); const adapters=routing.adapters || Object.entries(routing.adapter_counts || {}).map(([adapter,file_count])=>({adapter,file_count})); const suggestion=routing.source_locale_suggestion || {};
      routingReady=count > 0;
      if(!routingReady){$("routing").innerHTML=`<div class="recognition-placeholder"><strong>${escapeHtml(t("prepare.noResources"))}</strong><p>${escapeHtml(routing.reason || t("prepare.noResourcesCopy"))}</p></div>`;$("sourceLocaleBadge").textContent=t("prepare.noSuggestion");$("sourceLocaleHint").textContent=t("prepare.noSuggestionCopy");syncWorkflowControls();return;}
      if(suggestion.locale){const confidenceKey=`confidence.${suggestion.confidence || "suggested"}`;const confidence=t(confidenceKey) === confidenceKey ? suggestion.confidence || t("prepare.suggested") : t(confidenceKey);if(!preserveInputs && !sourceLocaleManual) $("sourceLocale").value=suggestion.locale;$("sourceLocaleBadge").textContent=sourceLocaleManual ? t("prepare.manual") : t("prepare.autoSuggestion",{confidence});$("sourceLocaleHint").textContent=sourceLocaleManual ? t("prepare.manualSourceHint") : suggestionReason(suggestion.reason);}
      if(!preserveInputs && (!$("targetLocale").value.trim() || $("targetLocale").value.trim() === $("sourceLocale").value.trim())) $("targetLocale").value=$("sourceLocale").value.trim() === "zh-CN" ? "en-US" : "zh-CN";
      const primary=routing.primary_adapter || (adapters[0] && adapters[0].adapter) || ""; const preflight=routing.recommended_preflight_mode || "auto"; const reason=routing.reason ? `<p>${escapeHtml(routing.reason)}</p>` : ""; const warning=(routing.warnings || [])[0];
      $("routing").innerHTML=`<div class="project-summary"><div class="project-signature"><span>${escapeHtml(t("routing.detectedNature"))}</span><strong>${escapeHtml(projectTypeLabel(routing.detected_project_type))}</strong>${reason}</div><div class="summary-stat"><span>${escapeHtml(t("routing.resources"))}</span><strong>${count}</strong></div><div class="summary-stat"><span>${escapeHtml(t("routing.adapters"))}</span><strong>${adapters.length}</strong></div><div class="summary-stat"><span>${escapeHtml(t("routing.primaryRoute"))}</span><strong>${escapeHtml(adapterLabel(primary))}</strong></div></div>${warning ? `<p class="safety-note">${escapeHtml(warning)}</p>` : ""}<details class="recognized-files"><summary>${escapeHtml(t("routing.viewFiles",{count}))}</summary><div class="table-wrap"><table><thead><tr><th>${escapeHtml(t("routing.path"))}</th><th>${escapeHtml(t("routing.adapter"))}</th></tr></thead><tbody>${files.slice(0,40).map(item=>`<tr><td>${escapeHtml(item.path || item)}</td><td>${escapeHtml(adapterLabel(item.adapter || ""))}</td></tr>`).join("")}</tbody></table>${files.length>40 ? `<p>${escapeHtml(t("routing.moreFiles",{count:files.length-40}))}</p>` : ""}<p>${escapeHtml(t("routing.preflight",{mode:preflight}))}</p></div></details>`;
      syncWorkflowControls();
    }
    async function runAgent(mode) { await runBusy(async()=>{ validateRunInputs(); const payload=payloadBase(); if(mode==="synthetic") payload.synthetic_draft=true; if(mode==="responses"){payload.responses_dir=$("responsesDir").value.trim(); if(!payload.responses_dir) throw new WorkbenchRequestError("RESPONSES_REQUIRED",t("validation.responsesRequired"),400,true,[]);} const data=await postJson("/api/agent-run",payload); currentProject=payload.project; currentSession={...data.agent_result, run_id:data.agent_result.run_id}; await loadProjectState(currentSession.run_id); navigate("/review",currentSession.run_id); setStatus(t("success.runPrepared")); }); }
    async function runSafeDemo() { await runBusy(async()=>{ const data=await postJson("/api/quickstart-demo",{}); const summary=data.demo_summary; $("project").value=summary.copied_project; currentProject=summary.copied_project; await loadProjectState(summary.run_id); navigate("/review",summary.run_id); setStatus(t("success.safeDemo")); }); }

    async function loadSessions() { const project=$("project").value.trim() || currentProject; currentArtifactState=null; if(!project){ renderSessions(null); return; } const data=await postJson("/api/sessions",{project}); currentProject=project; currentIndex=data.session_index; try { const artifactData=await getJson(`/api/artifact-state?project=${encodeURIComponent(project)}`); currentArtifactState=available(artifactData.artifact_state); } catch(requestError) { currentArtifactState=requestError.code === "ARTIFACT_MISSING" ? missing(requestError.code) : error(requestError.code,requestError.message); } renderSessions(currentIndex); renderOverview(); updateContext(); }
    async function loadProjectState(runId) { await loadSessions(); currentSession=runId ? (currentIndex.sessions || []).find(item=>(item.run_id || item.session_id)===runId) || {run_id:runId} : null; updateContext(); }
    function renderSessions(index) { const sessions=index && Array.isArray(index.sessions) ? index.sessions.slice().reverse() : []; if(!sessions.length){$("sessions").innerHTML=`<div class="empty"><h3>${escapeHtml(t("sessions.emptyTitle"))}</h3><p>${escapeHtml(t("sessions.emptyCopy"))}</p></div>`;$("overviewSessions").innerHTML=`<div class="empty">${escapeHtml(t("sessions.noneRecorded"))}</div>`;return;} const rows=sessions.map(item=>`<div class="session-row"><div><strong class="review-run-id">${escapeHtml(item.run_id || item.session_id)}</strong><div>${statusChip(item.status)} <span class="context-meta">${escapeHtml(item.target_locale || "")}</span></div></div><button type="button" onclick="selectSession('${escapeJs(item.run_id || item.session_id)}')">${escapeHtml(t("sessions.openReview"))}</button></div>`).join(""); $("sessions").innerHTML=rows; $("overviewSessions").innerHTML=rows; }
    function selectSession(runId) { const sessions=currentIndex && Array.isArray(currentIndex.sessions) ? currentIndex.sessions : []; currentSession=sessions.find(item=>(item.run_id || item.session_id)===runId) || {run_id:runId}; currentRunView=null; updateContext(); navigate("/review",runId); }
    function renderOverview() { const projectBody=$("overviewProjectBody"); if(!currentProject){projectBody.innerHTML=`<div class="empty">${escapeHtml(t("overview.chooseProject"))}</div>`;$("nextAction").innerHTML=`<button class="primary" type="button" onclick="navigate('/generate')">${escapeHtml(t("overview.selectProject"))}</button>`;return;} const artifactResult=currentArtifactState || missing("NOT_LOADED"); const artifactStatus=artifactResult.kind === "available" ? statusText(artifactResult.data.status || "unknown") : statusText(artifactResult.kind); projectBody.innerHTML=`<strong class="path">${escapeHtml(currentProject)}</strong><p>${currentIndex && currentIndex.latest_session_id ? escapeHtml(t("overview.latestRun",{runId:currentIndex.latest_session_id})) : escapeHtml(t("overview.noRuns"))}</p><p>${escapeHtml(t("overview.artifactState",{status:artifactStatus}))}</p>`; $("nextAction").innerHTML=currentIndex && currentIndex.latest_session_id ? `<button class="primary" type="button" onclick="navigate('/review', currentIndex.latest_session_id)">${escapeHtml(t("overview.reviewLatest"))}</button>` : `<button class="primary" type="button" onclick="navigate('/generate')">${escapeHtml(t("overview.prepareFirst"))}</button>`; }

    async function renderSessionReview(session) {
      const project=$("project").value.trim() || currentProject; const runId=session && (session.run_id || session.session_id);
      if(!project || !runId){showReviewEmpty("review.emptyTitle","review.emptyMessage",false);return;}
      try {
        const view=await getJson(`/api/workbench-run?project=${encodeURIComponent(project)}&run_id=${encodeURIComponent(runId)}`);
        await renderRunView(view);
      } catch(requestError) { currentRunView=null; currentSession=session; showReviewEmpty("review.loadErrorTitle","review.loadErrorMessage",requestError.recoverable !== false,requestError.message); showError(requestError); }
    }
    async function renderRunView(view) {
      currentRunView=view; currentSession=view.session; $("reviewEmpty").hidden=true; $("reviewContent").hidden=false;
      $("reviewRunId").textContent=view.run_id; $("reviewRunFreshness").textContent=statusText(view.freshness); $("reviewRunFreshness").className=`status-chip ${view.freshness === "current" ? "success" : "warning"}`;
      const summaryArtifact=resultFromProjection(view.summary_artifact); const summary=summaryArtifact.kind === "available" ? summaryArtifact.data : (view.summary || {}); $("runStatus").textContent=statusText(summary.status || view.session.status); $("extractionCoverage").textContent=summary.segment_count != null ? t("review.segments",{count:summary.segment_count}) : t("common.unavailable"); $("qaStatus").textContent=statusText(summary.qa_status || "not_checked");
      const readinessEvidence=reviewEvidence(view,"review_readiness"); const deliveryEvidence=reviewEvidence(view,"delivery_readiness"); const applyEvidence=reviewEvidence(view,"apply_readiness"); const artifactEvidence=reviewEvidence(view,"artifact_state");
      renderArtifactState(artifactEvidence,view.artifacts || []); renderProjection("reviewReadiness",readinessEvidence); renderProjection("deliveryReadiness",deliveryEvidence); await renderApply(view,applyEvidence); renderRisks(view,[readinessEvidence,deliveryEvidence,applyEvidence]); renderQueue(view); renderArtifacts(view.artifacts || []); renderProviderSmoke(view);
      updateContext();
    }
    function showReviewEmpty(titleKey, messageKey, retryable, messageOverride="") { reviewEmptyState={titleKey,messageKey,messageOverride,retryable}; renderReviewEmptyState(); }
    function renderReviewEmptyState() { $("reviewEmpty").hidden=false; $("reviewContent").hidden=true; $("reviewEmptyTitle").textContent=t(reviewEmptyState.titleKey); $("reviewEmptyMessage").textContent=reviewEmptyState.messageOverride || t(reviewEmptyState.messageKey); $("reviewRetry").hidden=!reviewEmptyState.retryable; $("reviewRunId").textContent=t("context.noRun"); $("reviewRunFreshness").textContent=t("review.notSelected"); }
    function retryReviewLoad() { if(currentSession) runBusy(()=>renderSessionReview(currentSession)); }
    function reviewEvidence(view, key) { const selected=view[key] || {state:"missing",reason:"ARTIFACT_MISSING"}; const current=view.current_project_projection; const sameRunCurrent=view.freshness === "current" && current && current.run_id === view.run_id; const candidate=sameRunCurrent && current[key]; if(selected.state === "missing" && candidate && candidate.state !== "missing") return {projection:candidate,scope:t("review.scopeCurrent")}; return {projection:selected,scope:t("review.scopeSelected")}; }
    function evidenceStatus(data) { return data.status || data.review_readiness_status || data.delivery_status || data.delivery_readiness_status || data.apply_status || data.apply_readiness_status || "available"; }
    function evidenceSummary(data) { const value=data.reason || data.recommended_next_action || (Array.isArray(data.recommended_next_actions) ? data.recommended_next_actions[0] : ""); return typeof value === "string" && value ? value : t("review.runtimeEvidenceAvailable"); }
    function renderArtifactState(evidence, artifacts) { const result=resultFromProjection(evidence.projection); if(result.kind !== "available"){ $("artifactStateStatus").textContent=statusText(result.kind); $("artifactStateCounts").textContent=t("review.artifactEvidenceUnavailable"); return; } const data=result.data || {}; const summary=data.summary || {}; const unavailable=t("common.unavailable"); $("artifactStateStatus").textContent=statusText(data.status || "unknown"); $("artifactStateCounts").textContent=t("review.artifactCounts",{indexed:Array.isArray(artifacts) ? artifacts.length : unavailable,stale:summary.stale_count ?? unavailable,missing:summary.missing_required_count ?? unavailable,review:summary.requires_human_review_count ?? unavailable}); }
    function renderProjection(id, evidence) { const projection=evidence.projection; const result=resultFromProjection(projection); const node=$(id); const scope=`<div class="evidence-scope">${escapeHtml(evidence.scope)}</div>`; if(result.kind==="available"){ const data=result.data || {}; node.innerHTML=`${statusChip(evidenceStatus(data))}${scope}<p>${escapeHtml(evidenceSummary(data))}</p>${rawPreviewAction(result,projection.path)}`; } else node.innerHTML=`${statusChip(result.kind)}${scope}<p>${escapeHtml(result.message || result.reason || t("review.evidenceUnavailable"))}</p>${rawPreviewAction(result,projection && projection.path)}`; }
    async function readJsonArtifact(path) { if(!path) return missing("ARTIFACT_MISSING"); try { const data=await postJson("/api/read-artifact",{path}); rawArtifactPreviews[path]={raw:data.content,truncated:data.truncated}; try{return available(JSON.parse(data.content));}catch(_){return error("INVALID_ARTIFACT_JSON",t("error.invalidArtifactJson"),path);} } catch(requestError){return error(requestError.code,requestError.message,path);} }
    async function renderApply(view, evidence) { const artifacts=Object.fromEntries((view.artifacts || []).map(item=>[item.artifact_id,item.path])); const plan=await readJsonArtifact(artifacts.apply_plan); const projection=resultFromProjection(evidence.projection); const scope=`<div class="evidence-scope">${escapeHtml(evidence.scope)}</div>`; if(plan.kind==="available"){const data=plan.data || {}; $("applyDetails").innerHTML=`${statusChip(projection.kind === "available" ? evidenceStatus(projection.data || {}) : projection.kind)}${scope}<p>${escapeHtml(data.operation_count != null ? t("review.operations",{count:data.operation_count}) : t("review.applyAvailable"))}</p><p>${escapeHtml(t("review.applyAuthorization"))}</p>${rawPreviewAction(plan,artifacts.apply_plan)}`;}else{$("applyDetails").innerHTML=`${statusChip(projection.kind)}${scope}<p>${escapeHtml(t("review.applyNotExposed"))}</p>${rawPreviewAction(plan,artifacts.apply_plan)}`;} }
    function riskText(item) { if(typeof item === "string") return item; if(!item || typeof item !== "object") return ""; return item.summary || item.recommended_action || item.reason || item.required_decision || ""; }
    function renderRisks(view, evidences) { const risks=[...(view.limitations || [])]; for(const evidence of evidences){const result=resultFromProjection(evidence.projection);if(result.kind !== "available") continue;const data=result.data || {};for(const group of [data.blockers,data.warnings,data.limitations]) for(const item of (Array.isArray(group) ? group : [])){const text=riskText(item);if(text) risks.push(text);}} if(view.newer_project_state_available) risks.unshift(t("review.newerStateRisk")); const unique=[...new Set(risks)]; if(!unique.length) unique.push(t("review.noLimitations")); const visible=unique.slice(0,8); if(unique.length>visible.length) visible.push(t("review.moreRisks",{count:unique.length-visible.length})); $("riskList").innerHTML=visible.map(item=>`<li class="list-item">${escapeHtml(item)}</li>`).join(""); }
    function renderQueue(view) { const current=view.current_project_projection; const useCurrent=view.freshness === "current" && current && current.run_id === view.run_id; const queueProjection=useCurrent ? current.queues.review : view.queues.review; $("queueScope").textContent=t(useCurrent ? "review.queueScopeCurrent" : "review.queueScopeSelectedFull"); const result=resultFromProjection(queueProjection); const items=result.kind==="available" && Array.isArray(result.data.items) ? result.data.items : []; $("actionQueue").innerHTML=items.length ? items.map(item=>`<div class="action-row"><div><strong>${escapeHtml(item.title || item.item_id || t("review.queueItem"))}</strong><p>${escapeHtml(item.reason || item.status || "")}</p></div><button type="button" onclick="prefillAction('${escapeJs(item.item_id || "")}')">${escapeHtml(t("common.act"))}</button></div>`).join("") : `<div class="empty">${escapeHtml(t("review.noQueueItems"))}${rawPreviewAction(result,queueProjection && queueProjection.path)}</div>`; }
    function prefillAction(itemId) { $("actionItemId").value=itemId; $("actionReason").focus(); }
    async function submitReviewAction(event) { event.preventDefault(); if(!currentRunView) return; await runBusy(async()=>{ const target_queue_item_id=$("actionItemId").value.trim(); const action={run_id:currentRunView.run_id, action_type:$("actionType").value, actor_role:"project_owner", target_queue_item_id, payload:{reason:$("actionReason").value.trim(), target_queue_item_id}}; if(action.run_id !== currentRunView.run_id) throw new WorkbenchRequestError("RUN_STATE_MISMATCH",t("review.actionRunMismatch"),409,true,["RELOAD_RUN"]); const endpoint=action.action_type === "request_follow_up" ? "/api/workbench-readiness-action" : "/api/workbench-action"; const result=await postJson(endpoint,{project:currentProject,run_id:currentRunView.run_id,action}); const output=result.workbench_action_result || result.workbench_readiness_action_result || result; $("actionResult").textContent=result.outcome || result.status || output.outcome || output.status || t("review.recorded"); await renderSessionReview(currentSession); }); }
    function renderArtifacts(artifacts) { const readable=artifacts.filter(item=>item.state !== "directory"); const recent=readable.slice(0,4).map(item=>`<div class="artifact-row"><div><strong>${escapeHtml(item.artifact_id)}</strong><div class="path">${escapeHtml(item.path)}</div></div><button type="button" onclick="previewArtifact('${escapeJs(item.path)}')">${escapeHtml(t("common.open"))}</button></div>`).join(""); $("recentArtifacts").innerHTML=recent || `<div class="empty">${escapeHtml(t("review.noReadableArtifacts"))}</div>`; $("allArtifacts").innerHTML=artifacts.length ? artifacts.map(item=>`<div class="artifact-row"><div><strong>${escapeHtml(item.artifact_id)}</strong><div class="path">${escapeHtml(item.path)}</div></div>${item.state === "directory" ? `<span class="status-chip">${escapeHtml(t("common.pathOnly"))}</span>` : `<button type="button" onclick="previewArtifact('${escapeJs(item.path)}')">${escapeHtml(t("common.open"))}</button>`}</div>`).join("") : `<div class="empty">${escapeHtml(t("review.noArtifacts"))}</div>`; }
    function renderProviderSmoke(view) { const artifacts=Object.fromEntries((view.artifacts || []).map(item=>[item.artifact_id,item.path])); const closure=artifacts.provider_smoke_closure_report; const manifest=artifacts.provider_smoke_evidence_manifest; $("providerSmoke").innerHTML=closure && manifest ? `<p>${escapeHtml(t("review.providerEvidenceIndexed"))}</p><button type="button" onclick="previewArtifact('${escapeJs(manifest)}')">${escapeHtml(t("review.openEvidenceManifest"))}</button>` : escapeHtml(t("review.providerSmokeMissing")); }
    function rawPreviewAction(result, path) { if(!path || !result || result.kind === "missing") return ""; if(result.data) rawArtifactPreviews[path]={raw:JSON.stringify(result.data,null,2),truncated:false}; return `<button type="button" onclick="openRawArtifactPreview('${escapeJs(path)}')">${escapeHtml(t("review.openRawArtifact"))}</button>`; }
    async function previewArtifact(path) { await runBusy(async()=>{ const data=await postJson("/api/read-artifact",{path}); rawArtifactPreviews[path]={raw:data.content,truncated:data.truncated}; openRawArtifactPreview(path); }); }
    function openRawArtifactPreview(path) { const cached=rawArtifactPreviews[path]; if(!cached){previewArtifact(path);return;} inspectorReturnFocus=document.activeElement; $("inspectorPath").textContent=path; $("inspectorContent").textContent=cached.raw+(cached.truncated ? `\n\n[${t("inspector.truncated")}]` : ""); $("reviewInspector").classList.add("open"); $("reviewInspector").setAttribute("aria-hidden","false"); $("inspectorClose").focus(); }
    function closeInspector() { $("reviewInspector").classList.remove("open"); $("reviewInspector").setAttribute("aria-hidden","true"); if(inspectorReturnFocus && typeof inspectorReturnFocus.focus === "function") inspectorReturnFocus.focus(); inspectorReturnFocus=null; }
    function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]); }
    function escapeJs(value) { return String(value ?? "").replace(/\\/g,"\\\\").replace(/'/g,"\\'"); }

    async function restoreFromUrl() { const url=new URL(location.href); const project=url.searchParams.get("project") || ""; const runId=url.searchParams.get("run"); if($("project").value.trim() !== project){$("project").value=project;currentProject=project;currentIndex=null;currentSession=null;currentRunView=null;resetProjectWorkflow();} renderRoute(); if(project){await runBusy(async()=>{await loadProjectState(runId);if(location.pathname==="/review" && currentSession) await renderSessionReview(currentSession);});}else{renderOverview();updateContext();} }
    function renderHealth() { if(healthState.kind==="ready"){$("healthLabel").textContent=t("health.ready");$("settingsHealth").textContent=t("health.readyVersion",{version:healthState.version});}else if(healthState.kind==="offline"){$("healthLabel").textContent=t("health.offline");$("settingsHealth").textContent=healthState.message || t("health.offline");}else{$("healthLabel").textContent=t("health.checking");$("settingsHealth").textContent=t("settings.checking");} }
    async function initializeWorkbench() { applyLanguage(); syncWorkflowControls(); renderHealth(); try { const health=await getJson("/api/health"); healthState={kind:"ready",version:health.version}; $("healthDot").classList.add("pass"); } catch(healthError) { healthState={kind:"offline",version:"",message:healthError.message}; } renderHealth(); await restoreFromUrl(); }
    document.querySelectorAll("[data-route]").forEach(link=>link.addEventListener("click",event=>{event.preventDefault();navigate(link.dataset.route);}));
    $("project").addEventListener("input",()=>{currentSession=null;currentRunView=null;currentIndex=null;currentArtifactState=null;setFieldError("project","");resetProjectWorkflow();updateContext();});
    $("sourceLocale").addEventListener("input",()=>{sourceLocaleManual=true;if(routingReady){$("sourceLocaleBadge").textContent=t("prepare.manual");$("sourceLocaleHint").textContent=t("prepare.manualSourceHint");}setFieldError("targetLocale","");syncWorkflowControls();});
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
