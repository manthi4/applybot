"""Midnight blue-black theme with red accents for the ApplyBot dashboard."""

from __future__ import annotations

from fasthtml.common import Style

THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Design token layer (single source of truth) ───────────────── */
:root {
    --bg:         #050d16;
    --bg-raised:  #081422;
    --bg-card:    #0a1826;
    --bg-elev:    #0d1f30;
    --border:     #142030;
    --border-hi:  #1a304d;
    --border-lit: #224068;
    --text:       #c4ddf0;
    --text-2:     #5f88a8;
    --text-3:     #2e4a60;
    --red:        #8c1c1c;
    --red-lit:    #a62424;
    --red-hi:     #c43838;
    --red-glow:   rgba(140, 28, 28, 0.20);
    --red-dim:    rgba(140, 28, 28, 0.09);
    --link:       #4da4e8;
    --link-hi:    #80c0f5;
    --r:          0.625rem;
    --r-sm:       0.375rem;
    --inner-hi:   inset 0 1px 0 rgba(255, 255, 255, 0.055);
    --sh-sm:      0 1px 4px  rgba(0,0,0,0.55);
    --sh-md:      0 4px 16px rgba(0,0,0,0.65), 0 1px 4px rgba(0,0,0,0.5);
    --sh-lg:      0 14px 36px rgba(0,0,0,0.75), 0 4px 12px rgba(0,0,0,0.55);
    --sh-xl:      0 24px 60px rgba(0,0,0,0.8),  0 8px 20px rgba(0,0,0,0.6);
    --ease:       cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Pico token overrides ───────────────────────────────────────── */
:root[data-theme="dark"] {
    --pico-background-color:                    var(--bg);
    --pico-card-background-color:               var(--bg-card);
    --pico-card-sectioning-background-color:    var(--bg-raised);
    --pico-color:                               var(--text);
    --pico-muted-color:                         var(--text-2);
    --pico-muted-border-color:                  var(--border);
    --pico-primary:                             var(--red);
    --pico-primary-hover:                       #7a1616;
    --pico-primary-focus:                       var(--red-glow);
    --pico-primary-inverse:                     #ffffff;
    --pico-secondary:                           var(--bg-elev);
    --pico-secondary-hover:                     var(--border-hi);
    --pico-secondary-focus:                     rgba(26, 48, 77, 0.35);
    --pico-secondary-inverse:                   var(--text);
    --pico-contrast:                            var(--text);
    --pico-contrast-hover:                      #e8f4ff;
    --pico-contrast-focus:                      rgba(196, 221, 240, 0.2);
    --pico-contrast-inverse:                    var(--bg);
    --pico-border-radius:                       var(--r);
    --pico-form-element-background-color:       var(--bg-raised);
    --pico-form-element-border-color:           var(--border);
    --pico-form-element-color:                  var(--text);
    --pico-form-element-focus-color:            var(--red);
    --pico-switch-color:                        var(--border);
    --pico-switch-checked-background-color:     var(--red);
    --pico-table-border-color:                  var(--border);
    --pico-table-row-stripped-background-color: #071220;
    --pico-code-background-color:               #030810;
    --pico-code-color:                          var(--text);
    --pico-blockquote-border-left-color:        var(--red);
    --pico-hr-border-color:                     var(--border);
    --pico-mark-background-color:               rgba(140, 28, 28, 0.14);
    --pico-mark-color:                          var(--text);
    --pico-del-color:                           var(--text-2);
    --pico-ins-color:                           var(--red);
}

/* ── Base / reset ──────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background-color: var(--bg);
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    color: var(--text);
}

/* ── Typography ────────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
    letter-spacing: -0.025em;
    font-weight: 700;
    line-height: 1.22;
    color: var(--text);
}

h1 {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 1.5rem;
    letter-spacing: -0.03em;
}
h3 { font-size: 1.05rem; font-weight: 600; }
h4 { font-size: 0.95rem; font-weight: 600; color: var(--text-2); }

a {
    color: var(--link);
    text-decoration: none;
    transition: color 0.15s var(--ease);
}
a:hover { color: var(--link-hi); }

small { font-size: 0.8em; color: var(--text-2); }

hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, var(--border-hi) 30%, var(--border-hi) 70%, transparent 100%);
    margin: 1rem 0;
}

/* ── Scrollbar ─────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-lit); }

/* ── Navigation ────────────────────────────────────────────────── */
nav {
    background: rgba(4, 10, 19, 0.9);
    backdrop-filter: blur(20px) saturate(160%);
    -webkit-backdrop-filter: blur(20px) saturate(160%);
    border-bottom: 1px solid rgba(20, 32, 48, 0.95);
    padding: 0 1.5rem;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow:
        0 1px 0 rgba(20, 32, 48, 0.6),
        0 4px 28px rgba(0, 0, 0, 0.65);
}

/* Brand */
nav ul li strong a {
    color: var(--red-hi) !important;
    font-size: 1.05em;
    font-weight: 700;
    letter-spacing: -0.02em;
}

nav a {
    color: var(--text-2) !important;
    text-decoration: none;
    font-weight: 500;
    font-size: 0.9rem;
    letter-spacing: 0.01em;
    transition: color 0.15s var(--ease);
}
nav a:hover { color: var(--text) !important; }

/* ── Cards / articles ──────────────────────────────────────────── */
article {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    box-shadow: var(--sh-sm);
    transition: border-color 0.18s var(--ease), box-shadow 0.2s var(--ease);
}
article:hover {
    border-color: var(--border-hi);
    box-shadow: var(--sh-md);
}
article header, article footer {
    background: var(--bg-raised);
    border-color: var(--border);
}

/* detail-card: expandable summary header */
article > details > summary {
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text);
    cursor: pointer;
    padding: 0.9rem 1.1rem;
    margin: -1.25rem -1.25rem 0.75rem;
    background: rgba(255,255,255,0.018);
    border-bottom: 1px solid var(--border);
    border-radius: var(--r) var(--r) 0 0;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    transition: color 0.15s var(--ease), background 0.15s var(--ease);
}
article > details > summary::before {
    content: '›';
    display: inline-block;
    font-size: 1.1em;
    color: var(--text-2);
    transition: transform 0.2s var(--ease), color 0.15s;
    line-height: 1;
    flex-shrink: 0;
}
article > details[open] > summary::before {
    transform: rotate(90deg);
    color: var(--text-2);
}
article > details > summary::-webkit-details-marker { display: none; }
article > details > summary::marker { display: none; }
article > details[open] > summary { color: var(--text); }

/* confirmed-card style (post-action) */
article:not(:has(details)) {
    padding: 0.9rem 1.1rem;
}

/* ── Alert roles ────────────────────────────────────────────────── */
article[role="note"]   { border-left: 3px solid #3b82f6; }
article[role="status"] { border-left: 3px solid #22c55e; }
article[role="alert"]  { border-left: 3px solid var(--red); }

/* ── Buttons ───────────────────────────────────────────────────── */
[role="button"], button, input[type="submit"], input[type="button"] {
    font-family: inherit;
    font-weight: 600;
    font-size: 0.85rem;
    letter-spacing: 0.015em;
    border-radius: var(--r-sm);
    transition: transform 0.14s var(--ease), box-shadow 0.18s var(--ease),
                background-color 0.15s, border-color 0.15s;
    will-change: transform;
}
/* Primary button */
button:not([class*="secondary"]):not([class*="outline"]):not([class*="contrast"]) {
    background: var(--red) !important;
    border-color: transparent !important;
}
button:not([class*="secondary"]):not([class*="outline"]):not([class*="contrast"]):hover:not(:disabled) {
    background: var(--red-lit) !important;
    transform: translateY(-1px);
    box-shadow: var(--sh-sm) !important;
}
/* Secondary button */
button[class*="secondary"]:hover:not(:disabled) {
    border-color: var(--border-hi) !important;
    transform: translateY(-1px);
}
button:active, [role="button"]:active { transform: translateY(0) !important; }

/* ── Progress bars ─────────────────────────────────────────────── */
progress {
    border-radius: 999px;
    overflow: hidden;
    height: 0.375rem;
    background: var(--border);
}
progress::-webkit-progress-bar {
    background: var(--border);
    border-radius: 999px;
}
progress::-webkit-progress-value {
    background: var(--red-hi);
    border-radius: 999px;
}
progress::-moz-progress-bar {
    background: var(--red-hi);
    border-radius: 999px;
}

/* ── Tables ─────────────────────────────────────────────────────── */
table {
    border-radius: var(--r);
    border-collapse: separate;
    border-spacing: 0;
    overflow: hidden;
    font-size: 0.9rem;
}
thead th {
    background: var(--bg-raised);
    color: var(--text-2);
    font-size: 0.67rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    padding: 0.6rem 0.75rem;
    border-bottom: 1px solid var(--border-hi);
}
thead th:first-child { border-radius: var(--r-sm) 0 0 0; }
thead th:last-child  { border-radius: 0 var(--r-sm) 0 0; }
tbody td { padding: 0.55rem 0.75rem; vertical-align: middle; }
tbody td:nth-child(2) { font-variant-numeric: tabular-nums; color: var(--text-2); font-size: 0.88rem; }
tbody tr { transition: background-color 0.1s; }
tbody tr:hover td { background: rgba(26, 48, 77, 0.35); }

/* ── Code & pre ────────────────────────────────────────────────── */
pre, code {
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}
pre {
    background: #030810;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 1rem 1.1rem;
    font-size: 0.82rem;
    line-height: 1.7;
    overflow-x: auto;
    box-shadow: var(--sh-sm), var(--inner-hi);
}
code { color: #82bfe8; font-size: 0.88em; }
pre code { color: var(--text); font-size: inherit; }

/* ── Form elements ─────────────────────────────────────────────── */
input:not([type="checkbox"]):not([type="radio"]):not([type="range"]),
select, textarea {
    font-family: inherit;
    background: var(--bg-raised) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: var(--r-sm) !important;
    font-size: 0.9rem;
    transition: border-color 0.15s var(--ease), box-shadow 0.15s var(--ease);
}
input:focus, select:focus, textarea:focus {
    border-color: var(--red-hi) !important;
    box-shadow: 0 0 0 3px rgba(140, 28, 28, 0.2) !important;
    outline: none;
}
label {
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-2);
    margin-bottom: 0.4rem;
}

/* ── Summary / details (standalone, not in article) ────────────── */
details:not(article > details) summary {
    color: var(--text);
    cursor: pointer;
    font-weight: 500;
    transition: color 0.15s;
    list-style: none;
}
details:not(article > details) summary:hover { color: var(--text); }
details:not(article > details)[open] > summary { color: var(--text); }
details:not(article > details) summary::-webkit-details-marker { display: none; }
details:not(article > details) summary::marker { display: none; }

/* ── Layout spacing ────────────────────────────────────────────── */
.container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1100px;
}
.grid { gap: 1rem; }

/* ── Stat cards ────────────────────────────────────────────────── */
.stat-card {
    text-align: center;
    padding: 1.75rem 1.25rem;
}
.stat-card h3 {
    color: var(--red-hi);
    font-size: 2.75rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
    line-height: 1;
    letter-spacing: -0.04em;
}
.stat-card p {
    color: var(--text-2);
    margin: 0;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
}

/* ── Status badges ─────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 0.2em 0.65em;
    border-radius: 999px;
    font-size: 0.67em;
    font-weight: 700;
    letter-spacing: 0.065em;
    text-transform: uppercase;
    border: 1px solid transparent;
    vertical-align: middle;
    white-space: nowrap;
}
.badge-approved  { background: rgba(34,197,94,0.09);   color: #4ade80; border-color: rgba(34,197,94,0.28); }
.badge-new       { background: rgba(59,130,246,0.09);  color: #60a5fa; border-color: rgba(59,130,246,0.28); }
.badge-skipped   { background: rgba(95,136,168,0.09);  color: #6b94b5; border-color: rgba(95,136,168,0.22); }
.badge-applied   { background: rgba(140,28,28,0.10);   color: #c43838; border-color: rgba(140,28,28,0.28); }
.badge-interview { background: rgba(168,85,247,0.09);  color: #c084fc; border-color: rgba(168,85,247,0.28); }
.badge-rejected  { background: rgba(120,20,20,0.10);   color: #b03030; border-color: rgba(120,20,20,0.25); }
.badge-default   { background: rgba(95,136,168,0.08);  color: #6b94b5; border-color: rgba(95,136,168,0.2); }

/* ── Alert roles ────────────────────────────────────────────────── */
article[role="note"]   { border-left: 3px solid #3b82f6; }
article[role="status"] { border-left: 3px solid #22c55e; }
article[role="alert"]  { border-left: 3px solid var(--red); }

/* ── Profile page ──────────────────────────────────────────────── */
.profile-section {
    margin-bottom: 2rem;
    padding: 1.5rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
}
.profile-section h3 {
    margin-top: 0;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
}
.profile-field {
    margin-bottom: 0.6rem;
    display: flex;
    gap: 0.5rem;
}
.profile-field-label {
    font-weight: 600;
    color: var(--text-2);
    min-width: 120px;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.profile-field-value {
    color: var(--text);
    font-size: 0.9rem;
}
.profile-empty {
    color: var(--text-3);
    font-style: italic;
    font-size: 0.85rem;
}
.profile-tag {
    display: inline-block;
    padding: 0.15em 0.55em;
    margin: 0.15em;
    background: rgba(140, 28, 28, 0.08);
    border: 1px solid rgba(140, 28, 28, 0.2);
    border-radius: 999px;
    font-size: 0.8rem;
    color: var(--text);
}
.resume-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem;
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    margin-bottom: 1rem;
    font-size: 0.9rem;
}
.profile-completeness {
    margin-bottom: 1.5rem;
    padding: 1rem 1.5rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
}
.completeness-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}
.completeness-pct {
    font-weight: 700;
    font-size: 0.9rem;
    color: var(--red-hi);
}
.completeness-bar {
    height: 6px;
    background: var(--border);
    border-radius: 999px;
    overflow: hidden;
}
.completeness-fill {
    height: 100%;
    background: var(--red-hi);
    border-radius: 999px;
    transition: width 0.3s var(--ease);
}
.resume-download {
    margin-left: auto;
    font-size: 0.85rem;
    font-weight: 600;
}

/* ── Nav badge ─────────────────────────────────────────────────── */
nav a { position: relative; }
.nav-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.1em;
    padding: 0 0.3em;
    height: 1.1em;
    border-radius: 999px;
    font-size: 0.62rem;
    font-weight: 800;
    line-height: 1;
    background: var(--red-hi);
    color: #fff;
    margin-left: 0.3em;
    vertical-align: middle;
    letter-spacing: 0;
    box-shadow: 0 0 6px rgba(196,56,56,0.45);
}

/* ── Section eyebrow label ─────────────────────────────────────── */
.section-eyebrow {
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-2);
}

/* ── Score chips ───────────────────────────────────────────────── */
.score-chip {
    display: inline-block;
    padding: 0.13em 0.5em;
    border-radius: 999px;
    font-size: 0.67rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
    background: rgba(95,136,168,0.08);
    color: var(--text-2);
    border: 1px solid rgba(95,136,168,0.16);
}
.score-chip.score-high { background: rgba(34,197,94,0.08);  color: #4ade80; border-color: rgba(34,197,94,0.22); }
.score-chip.score-mid  { background: rgba(234,179,8,0.07);  color: #facc15; border-color: rgba(234,179,8,0.2); }
.score-chip.score-low  { background: rgba(239,68,68,0.06);  color: #f87171; border-color: rgba(239,68,68,0.16); }

/* ── Staging Area ──────────────────────────────────────────────── */
.staging-area {
    background: linear-gradient(135deg, rgba(140,28,28,0.06) 0%, var(--bg-card) 60%);
    border: 1px solid rgba(140,28,28,0.2);
    border-radius: var(--r);
    padding: 1.25rem 1.5rem 1.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 0 0 1px rgba(140,28,28,0.06), var(--sh-sm);
}
.staging-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
    flex-wrap: wrap;
    gap: 0.75rem;
}
.staging-header-left { display: flex; align-items: center; gap: 0.6rem; }
.staging-header-right { display: flex; align-items: center; gap: 0.6rem; }
.staging-count {
    display: inline-flex;
    align-items: center;
    padding: 0.15em 0.6em;
    border-radius: 999px;
    font-size: 0.67rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    background: rgba(95,136,168,0.09);
    color: var(--text-2);
    border: 1px solid rgba(95,136,168,0.18);
}
.staging-count-active {
    background: rgba(140,28,28,0.12);
    color: var(--red-hi);
    border-color: rgba(140,28,28,0.28);
}
.staging-body { margin-top: 0.25rem; }
.staging-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 0.5rem;
}
.staging-card {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.65rem 0.9rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    transition: border-color 0.15s var(--ease);
    overflow: hidden;
}
.staging-card:hover { border-color: var(--border-hi); }
.staging-card-text {
    min-width: 0;
    overflow: hidden;
    flex: 1;
}
.staging-card-actions {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-shrink: 0;
}
.staging-card-title {
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.staging-card-company {
    font-size: 0.74rem;
    color: var(--text-2);
    margin-top: 0.1rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.staging-empty-msg {
    font-size: 0.85rem;
    color: var(--text-3);
    font-style: italic;
}
.staging-result { margin-top: 0.75rem; }

/* ── Build button ──────────────────────────────────────────────── */
.build-btn {
    font-size: 0.82rem !important;
    padding: 0.45rem 1.1rem !important;
    margin: 0 !important;
}
.build-btn:not([disabled]):hover {
    box-shadow: 0 4px 16px rgba(140,28,28,0.35) !important;
}
.build-btn[disabled] {
    opacity: 0.38 !important;
    cursor: not-allowed !important;
    transform: none !important;
}

/* ── Unstage-all button ────────────────────────────────────────── */
.unstage-all-btn {
    font-size: 0.78rem !important;
    padding: 0.4rem 0.9rem !important;
    margin: 0 !important;
    background: transparent !important;
    color: var(--text-2) !important;
    border: 1px solid var(--border-hi) !important;
}
.unstage-all-btn:not([disabled]):hover {
    color: var(--red-hi) !important;
    border-color: rgba(140,28,28,0.4) !important;
    background: rgba(140,28,28,0.08) !important;
}
.unstage-all-btn[disabled] {
    opacity: 0.38 !important;
    cursor: not-allowed !important;
    transform: none !important;
}

/* ── HTMX loading indicator ────────────────────────────────────── */
.htmx-indicator { opacity: 0; transition: opacity 0.2s var(--ease); pointer-events: none; }
.htmx-request .htmx-indicator,
.htmx-request.htmx-indicator { opacity: 1; }
.staging-spinner {
    display: inline-block;
    width: 15px;
    height: 15px;
    border: 2px solid rgba(196,56,56,0.22);
    border-top-color: var(--red-hi);
    border-radius: 50%;
    animation: spin 0.65s linear infinite;
    vertical-align: middle;
    flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Job card meta row ─────────────────────────────────────────── */
.job-meta-row {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    margin: 0.5rem 0 0;
}
.meta-label {
    font-size: 0.67rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-3);
    flex-shrink: 0;
}
.meta-value {
    font-size: 0.875rem;
    color: var(--text);
    line-height: 1.5;
}

/* ── Staging remove button ─────────────────────────────────────── */
.staging-remove-btn {
    all: unset;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.3rem;
    height: 1.3rem;
    border-radius: 50%;
    font-size: 0.65rem;
    color: var(--text-3);
    background: transparent;
    border: 1px solid transparent !important;
    transition: color 0.15s var(--ease), background 0.15s var(--ease);
    flex-shrink: 0;
    padding: 0 !important;
    margin: 0 !important;
    transform: none !important;
    box-shadow: none !important;
}
.staging-remove-btn:hover {
    color: var(--red-hi) !important;
    background: rgba(140,28,28,0.12) !important;
    border-color: rgba(140,28,28,0.2) !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── Profile gap section (on /apps cards) ──────────────────────── */
.gap-section {
    background: rgba(234,179,8,0.04);
    border: 1px solid rgba(234,179,8,0.18);
    border-radius: var(--r-sm);
    padding: 0.75rem 0.9rem;
    margin: 0.75rem 0 0.25rem;
}
.gap-header {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    margin-bottom: 0.6rem;
}
.gap-header-label {
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #fbbf24;
}
.gap-header-sub {
    font-size: 0.78rem;
    color: var(--text-2);
}
.gap-item {
    display: flex;
    align-items: flex-start;
    gap: 0.55rem;
    padding: 0.3rem 0;
    border-top: 1px solid rgba(234,179,8,0.1);
}
.gap-item:first-of-type { border-top: none; }
.gap-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.2rem;
    height: 1.2rem;
    border-radius: 50%;
    background: rgba(234,179,8,0.12);
    color: #fbbf24;
    font-size: 0.65rem;
    font-weight: 800;
    flex-shrink: 0;
    margin-top: 0.05rem;
}
.gap-question {
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--text);
    line-height: 1.4;
}
.gap-context {
    font-size: 0.78rem;
    color: var(--text-2);
    margin-top: 0.1rem;
    line-height: 1.4;
}

/* ── Browse section ────────────────────────────────────────────── */
.jobs-browse-section { margin-top: 0; }
.jobs-browse-section > .section-eyebrow {
    display: block;
    margin-bottom: 0.75rem;
}
"""

theme_headers = (Style(THEME_CSS),)
