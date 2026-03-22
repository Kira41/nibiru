from __future__ import annotations

from flask import Flask, render_template_string

app = Flask(__name__)

EMAIL_DOMAIN_EXTRACTOR_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Email Domain Extractor</title>
  <style>
    :root {
      --bg-1: #0f172a;
      --bg-2: #111827;
      --panel: rgba(255, 255, 255, 0.08);
      --panel-border: rgba(255, 255, 255, 0.12);
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --accent-2: #22c55e;
      --accent-3: #a78bfa;
      --warning: #f59e0b;
      --danger: #f87171;
      --shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
      --radius: 20px;
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, Arial, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 30%),
        radial-gradient(circle at top right, rgba(34, 197, 94, 0.14), transparent 25%),
        linear-gradient(135deg, var(--bg-1), var(--bg-2));
      color: var(--text);
      padding: 28px;
    }

    .container { max-width: 1360px; margin: 0 auto; }

    .hero, .panel, .sticky-bar {
      background: var(--panel);
      border: 1px solid var(--panel-border);
      backdrop-filter: blur(14px);
      box-shadow: var(--shadow);
    }

    .hero {
      border-radius: 28px;
      padding: 28px;
      margin-bottom: 18px;
    }

    .hero h1 {
      margin: 0 0 8px;
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1.1;
    }

    .hero p {
      margin: 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.7;
      max-width: 980px;
    }

    .sticky-bar {
      position: sticky;
      top: 12px;
      z-index: 20;
      border-radius: 18px;
      padding: 12px;
      margin-bottom: 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
    }

    .sticky-left, .sticky-right {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    .pill {
      border-radius: 999px;
      padding: 8px 12px;
      background: rgba(255,255,255,0.07);
      border: 1px solid rgba(255,255,255,0.08);
      font-size: 12px;
      color: var(--muted);
    }

    .panel {
      border-radius: var(--radius);
      padding: 22px;
      margin-bottom: 20px;
    }

    .layout {
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr);
      gap: 20px;
      align-items: start;
    }

    .sidebar {
      position: sticky;
      top: 94px;
      display: grid;
      gap: 16px;
    }

    .input-area { display: grid; gap: 16px; }

    label {
      font-size: 14px;
      font-weight: 600;
      color: #f8fafc;
      display: inline-block;
      margin-bottom: 8px;
    }

    textarea, select, input[type="number"], input[type="text"] {
      width: 100%;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(15, 23, 42, 0.75);
      color: var(--text);
      padding: 14px 16px;
      font-size: 14px;
      line-height: 1.6;
      outline: none;
      transition: 0.2s ease;
    }

    textarea { min-height: 220px; resize: vertical; }

    textarea:focus, select:focus, input[type="number"]:focus, input[type="text"]:focus {
      border-color: rgba(56, 189, 248, 0.65);
      box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.15);
    }

    .actions, .toolbar, .selection-actions, .result-top-actions, .domain-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    button {
      border: none;
      border-radius: 14px;
      padding: 11px 16px;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.15s ease, opacity 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
    }

    button:hover { transform: translateY(-1px); }
    button:active { transform: translateY(0); }
    button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

    .btn-primary {
      background: linear-gradient(135deg, var(--accent), #0ea5e9);
      color: #00111a;
      box-shadow: 0 10px 25px rgba(14, 165, 233, 0.28);
    }

    .btn-secondary {
      background: rgba(255, 255, 255, 0.08);
      color: var(--text);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .btn-warning {
      background: linear-gradient(135deg, var(--warning), #fbbf24);
      color: #221100;
    }

    .btn-accent {
      background: linear-gradient(135deg, var(--accent-3), #8b5cf6);
      color: white;
    }

    .controls-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-top: 4px;
    }

    .checkbox-card {
      display: flex;
      align-items: center;
      gap: 12px;
      min-height: 56px;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(15, 23, 42, 0.75);
      padding: 12px 14px;
    }

    .checkbox-card input[type="checkbox"] {
      width: 18px;
      height: 18px;
      accent-color: #38bdf8;
      margin: 0;
      flex: 0 0 auto;
    }

    .checkbox-content { display: flex; flex-direction: column; gap: 2px; }
    .checkbox-content strong { font-size: 14px; font-weight: 700; }
    .checkbox-content span { color: var(--muted); font-size: 12px; line-height: 1.4; }

    .summary {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 8px;
    }

    .stat {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 14px;
      padding: 12px 14px;
      min-width: 148px;
    }

    .stat small { display: block; color: var(--muted); margin-bottom: 4px; font-size: 12px; }
    .stat strong { font-size: 18px; }

    .sidebar-card {
      border-radius: 18px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.08);
      padding: 16px;
    }

    .sidebar-card h3 { margin: 0 0 12px; font-size: 15px; }
    .sidebar-list { display: grid; gap: 10px; color: var(--muted); font-size: 13px; }
    .sidebar-item { display: flex; justify-content: space-between; gap: 12px; }
    .muted { color: var(--muted); }

    .results-header {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .results-header h2, .preview-header h2, .report-header h2 {
      margin: 0;
      font-size: 22px;
    }

    .results-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px;
    }

    .compact-view .domain-card textarea { display: none; }

    .domain-card {
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 18px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .combined-card {
      border-color: rgba(167, 139, 250, 0.28);
      background: linear-gradient(180deg, rgba(76, 29, 149, 0.16), rgba(15, 23, 42, 0.72));
    }

    .pinned-card {
      outline: 1px solid rgba(251, 191, 36, 0.4);
      box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.08);
    }

    .domain-head {
      padding: 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .domain-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .domain-left {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }

    .domain-title {
      font-size: 17px;
      font-weight: 800;
      word-break: break-word;
    }

    .provider-tag {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 11px;
      font-weight: 700;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.06);
      color: #dbeafe;
    }

    .badge {
      background: rgba(34, 197, 94, 0.14);
      color: #86efac;
      border: 1px solid rgba(34, 197, 94, 0.18);
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }

    .badge-alt {
      background: rgba(167, 139, 250, 0.16);
      color: #ddd6fe;
      border-color: rgba(167, 139, 250, 0.26);
    }

    .domain-variants, .domain-meta {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
      word-break: break-word;
    }

    .copy-btn {
      background: linear-gradient(135deg, var(--accent-2), #16a34a);
      color: white;
    }

    .mini-btn {
      background: rgba(255, 255, 255, 0.08);
      color: var(--text);
    }

    .pin-btn.active {
      background: linear-gradient(135deg, #f59e0b, #fbbf24);
      color: #221100;
    }

    .domain-card textarea, .selection-preview textarea, .report-box textarea {
      margin: 16px;
      margin-top: 0;
      min-height: 220px;
    }

    .selection-preview textarea, .report-box textarea {
      margin: 0;
      margin-top: 12px;
      min-height: 180px;
    }

    .selection-preview, .report-box { display: grid; gap: 12px; }
    .selection-chip-list { display: flex; flex-wrap: wrap; gap: 8px; }

    .selection-chip {
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(56,189,248,0.12);
      border: 1px solid rgba(56,189,248,0.18);
      font-size: 12px;
      color: #bae6fd;
    }

    .empty {
      text-align: center;
      padding: 36px 18px;
      color: var(--muted);
      border: 1px dashed rgba(255, 255, 255, 0.14);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.03);
    }

    .hint, .small-text {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }

    .success { color: #86efac; font-weight: 700; }
    .warning-text { color: #fcd34d; }
    .danger-text { color: #fca5a5; }
    .hidden { display: none !important; }

    @media (max-width: 1100px) {
      .layout { grid-template-columns: 1fr; }
      .sidebar { position: static; }
    }

    @media (max-width: 680px) {
      body { padding: 16px; }
      .hero, .panel, .sticky-bar { padding: 16px; }
      .domain-title-row { flex-direction: column; align-items: flex-start; }
      .sticky-bar { top: 8px; }
    }
  </style>
</head>
<body>
  <div class="container">
    <section class="hero">
      <h1>Email Domain Extractor</h1>
      <p>
        Paste your email list below, then click <strong>Extract</strong> to automatically group emails by domain.
        The biggest groups appear first by default. You can search, filter, pin, select groups, and preview selected emails in one large textarea for easy copy and paste.
      </p>
    </section>

    <section class="sticky-bar">
      <div class="sticky-left">
        <span class="pill" id="stickySelected">Selected: 0</span>
        <span class="pill" id="stickyVisible">Visible groups: 0</span>
        <span class="pill" id="stickyDuplicates">Duplicates removed: 0</span>
      </div>
      <div class="sticky-right">
        <button class="btn-secondary" id="scrollToPreviewBtn" type="button">Go to Selected Preview</button>
        <button class="btn-secondary" id="copySelectedBtnTop" type="button">Copy Selected</button>
      </div>
    </section>

    <div class="layout">
      <aside class="sidebar">
        <section class="sidebar-card">
          <h3>Quick Summary</h3>
          <div class="sidebar-list">
            <div class="sidebar-item"><span>Total extracted</span><strong id="sideTotalEmails">0</strong></div>
            <div class="sidebar-item"><span>Visible groups</span><strong id="sideVisibleGroups">0</strong></div>
            <div class="sidebar-item"><span>Selected groups</span><strong id="sideSelectedGroups">0</strong></div>
            <div class="sidebar-item"><span>Largest group</span><strong id="sideLargestGroup">-</strong></div>
            <div class="sidebar-item"><span>Smallest group</span><strong id="sideSmallestGroup">-</strong></div>
            <div class="sidebar-item"><span>Pinned groups</span><strong id="sidePinnedGroups">0</strong></div>
          </div>
        </section>

        <section class="sidebar-card">
          <h3>Quality Report</h3>
          <div class="sidebar-list">
            <div class="sidebar-item"><span>Unique emails</span><strong id="sideUniqueEmails">0</strong></div>
            <div class="sidebar-item"><span>Duplicates removed</span><strong id="sideDuplicatesRemoved">0</strong></div>
            <div class="sidebar-item"><span>Invalid entries</span><strong id="sideInvalidEntries">0</strong></div>
            <div class="sidebar-item"><span>Merged domains</span><strong id="sideMergedDomains">0</strong></div>
            <div class="sidebar-item"><span>Collected cards</span><strong id="sideCollectedCards">0</strong></div>
          </div>
        </section>

        <section class="sidebar-card">
          <h3>Top Groups</h3>
          <div class="sidebar-list" id="topGroupsList">
            <div class="muted">No results yet.</div>
          </div>
        </section>
      </aside>

      <main>
        <section class="panel input-area">
          <div>
            <label for="emailInput">Paste Emails Here</label>
            <textarea id="emailInput" placeholder="example@gmail.com&#10;john@yahoo.com&#10;alice@outlook.com&#10;mark@gmail.com&#10;random text here"></textarea>
          </div>

          <div class="actions">
            <button class="btn-primary" id="extractBtn" type="button">Extract Domains</button>
            <button class="btn-secondary" id="clearBtn" type="button">Clear All</button>
            <button class="btn-warning" id="pasteSampleBtn" type="button">Paste Demo Sample</button>
          </div>

          <div class="controls-grid">
            <div>
              <label for="groupCategory">Grouping Category</label>
              <select id="groupCategory">
                <option value="basic" selected>Basic</option>
                <option value="alias">Alias Based</option>
                <option value="structural">Structural</option>
                <option value="manual">Manual</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>

            <div>
              <label for="groupMethod">Grouping Method</label>
              <select id="groupMethod">
                <option value="exact" data-category="basic">Exact Domain</option>
                <option value="smart" data-category="basic" selected>Smart Similar Grouping</option>
                <option value="provider-alias" data-category="alias">Provider Alias Grouping</option>
                <option value="strict-alias" data-category="alias">Strict Alias Group</option>
                <option value="root-provider" data-category="structural">Root Provider Groups</option>
                <option value="subdomain-merge" data-category="structural">Subdomains Merge</option>
                <option value="normalize-domain" data-category="structural">Normalize Domain Characters</option>
                <option value="manual-rules" data-category="manual">Manual Rules Grouping</option>
                <option value="company-family" data-category="manual">Company Organization Family Group</option>
                <option value="hybrid" data-category="advanced">Hybrid Group</option>
              </select>
            </div>

            <div>
              <label for="similarityThreshold">Similarity Threshold</label>
              <select id="similarityThreshold">
                <option value="0.55">Loose</option>
                <option value="0.7" selected>Balanced</option>
                <option value="0.82">Strict</option>
              </select>
            </div>

            <div>
              <label for="collectLimit">Collect small groups up to</label>
              <input id="collectLimit" type="number" min="1" max="1000" step="1" value="100" />
            </div>
          </div>

          <div id="manualRulesContainer" class="hidden">
            <label for="manualRulesInput">Manual Rules Grouping Rules</label>
            <textarea id="manualRulesInput" style="min-height: 140px;" placeholder="hotmail, outlook, live, msn => microsoft&#10;&#10;gmail, googlemail => gmail">hotmail, outlook, live, msn =&gt; microsoft

gmail, googlemail =&gt; gmail</textarea>
            <div class="small-text">Write one rule per line. On the left put comma-separated domain families, then use =&gt; and write the final grouped name.</div>
          </div>

          <div class="controls-grid">
            <div>
              <label for="searchInput">Search groups</label>
              <input id="searchInput" type="text" placeholder="Search by group or domain..." />
            </div>
            <div>
              <label for="minEmailsFilter">Min emails per group</label>
              <input id="minEmailsFilter" type="number" min="0" step="1" value="0" />
            </div>
            <div>
              <label for="maxEmailsFilter">Max emails per group</label>
              <input id="maxEmailsFilter" type="number" min="0" step="1" value="0" placeholder="0 = no limit" />
            </div>
            <div>
              <label for="providerFilter">Provider filter</label>
              <select id="providerFilter">
                <option value="all">All Providers</option>
              </select>
            </div>
          </div>

          <div class="controls-grid">
            <label class="checkbox-card" for="collectSmallMode">
              <input id="collectSmallMode" type="checkbox" />
              <div class="checkbox-content">
                <strong>Collect small groups in shared cards</strong>
                <span>When enabled, domains with 1 to the chosen limit will be merged into combined cards.</span>
              </div>
            </label>
            <label class="checkbox-card" for="showOnlySelectedMode">
              <input id="showOnlySelectedMode" type="checkbox" />
              <div class="checkbox-content">
                <strong>Show only selected groups</strong>
                <span>Focus the result area on selected groups only.</span>
              </div>
            </label>
            <label class="checkbox-card" for="showOnlyPinnedMode">
              <input id="showOnlyPinnedMode" type="checkbox" />
              <div class="checkbox-content">
                <strong>Show only pinned groups</strong>
                <span>Display just your pinned important groups.</span>
              </div>
            </label>
            <label class="checkbox-card" for="compactViewMode">
              <input id="compactViewMode" type="checkbox" />
              <div class="checkbox-content">
                <strong>Compact view</strong>
                <span>Hide individual textareas for faster scanning.</span>
              </div>
            </label>
            <label class="checkbox-card" for="rememberSettingsMode">
              <input id="rememberSettingsMode" type="checkbox" checked />
              <div class="checkbox-content">
                <strong>Remember settings</strong>
                <span>Save filters and view preferences locally in your browser.</span>
              </div>
            </label>
          </div>

          <div class="summary" id="summary">
            <div class="stat"><small>Total Emails</small><strong id="totalEmails">0</strong></div>
            <div class="stat"><small>Visible Groups</small><strong id="totalDomains">0</strong></div>
            <div class="stat"><small>Status</small><strong id="statusText">Waiting</strong></div>
            <div class="stat"><small>Merged Domains</small><strong id="mergedDomains">0</strong></div>
            <div class="stat"><small>Collected Cards</small><strong id="collectedCards">0</strong></div>
            <div class="stat"><small>Selected</small><strong id="selectedCount">0</strong></div>
            <div class="stat"><small>Pinned</small><strong id="pinnedCount">0</strong></div>
            <div class="stat"><small>Invalid Entries</small><strong id="invalidCount">0</strong></div>
            <div class="stat"><small>Duplicates Removed</small><strong id="duplicateCount">0</strong></div>
          </div>
        </section>

        <section class="panel">
          <div class="preview-header results-header">
            <h2>Selected Groups Preview</h2>
            <div class="selection-actions">
              <button class="btn-secondary" id="selectAllBtn" type="button">Select All Visible</button>
              <button class="btn-secondary" id="unselectAllBtn" type="button">Unselect All</button>
              <button class="btn-secondary" id="selectTop3Btn" type="button">Select Top 3</button>
              <button class="btn-secondary" id="selectPinnedBtn" type="button">Select Pinned</button>
              <button class="btn-accent" id="copySelectedBtn" type="button">Copy Selected Text</button>
            </div>
          </div>
          <div class="selection-preview">
            <div class="small-text">Choose any groups below, then all selected emails will appear here in one large textarea for copy and paste.</div>
            <div class="selection-chip-list" id="selectedChipList"></div>
            <textarea id="selectedPreviewArea" readonly placeholder="Selected group emails will appear here..."></textarea>
          </div>
        </section>

        <section class="panel">
          <div class="report-header results-header">
            <h2>Duplicates & Invalid Entries</h2>
            <div class="result-top-actions">
              <button class="btn-secondary" id="copyDuplicatesBtn" type="button">Copy Duplicates</button>
              <button class="btn-secondary" id="copyInvalidBtn" type="button">Copy Invalid</button>
            </div>
          </div>
          <div class="controls-grid">
            <div class="report-box">
              <div class="small-text warning-text">Duplicate emails removed during extraction.</div>
              <textarea id="duplicatesArea" readonly placeholder="Duplicate emails will appear here..."></textarea>
            </div>
            <div class="report-box">
              <div class="small-text danger-text">Lines or tokens that did not match a valid email format.</div>
              <textarea id="invalidArea" readonly placeholder="Invalid entries will appear here..."></textarea>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="results-header">
            <h2>Grouped Results</h2>
            <div class="toolbar">
              <button class="btn-secondary" id="biggestFirstBtn" type="button">Biggest First</button>
              <button class="btn-secondary" id="smallestFirstBtn" type="button">Smallest First</button>
              <button class="btn-secondary" id="azBtn" type="button">A-Z</button>
              <button class="btn-secondary" id="zaBtn" type="button">Z-A</button>
            </div>
          </div>
          <div id="results"></div>
        </section>
      </main>
    </div>
  </div>

  <script>
    const STORAGE_KEY = 'email-domain-extractor-settings-v3';
    const EMAIL_REGEX_GLOBAL = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
    const EMAIL_REGEX_SINGLE = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    const MULTI_PART_TLDS = new Set(['co.uk', 'org.uk', 'gov.uk', 'ac.uk', 'com.au', 'net.au', 'org.au', 'co.nz', 'com.br', 'com.mx']);

    const emailInput = document.getElementById('emailInput');
    const extractBtn = document.getElementById('extractBtn');
    const clearBtn = document.getElementById('clearBtn');
    const pasteSampleBtn = document.getElementById('pasteSampleBtn');
    const results = document.getElementById('results');
    const totalEmails = document.getElementById('totalEmails');
    const totalDomains = document.getElementById('totalDomains');
    const statusText = document.getElementById('statusText');
    const mergedDomains = document.getElementById('mergedDomains');
    const collectedCards = document.getElementById('collectedCards');
    const selectedCount = document.getElementById('selectedCount');
    const pinnedCount = document.getElementById('pinnedCount');
    const invalidCount = document.getElementById('invalidCount');
    const duplicateCount = document.getElementById('duplicateCount');
    const groupCategory = document.getElementById('groupCategory');
    const groupMethod = document.getElementById('groupMethod');
    const similarityThreshold = document.getElementById('similarityThreshold');
    const manualRulesContainer = document.getElementById('manualRulesContainer');
    const manualRulesInput = document.getElementById('manualRulesInput');
    const collectSmallMode = document.getElementById('collectSmallMode');
    const collectLimit = document.getElementById('collectLimit');
    const searchInput = document.getElementById('searchInput');
    const minEmailsFilter = document.getElementById('minEmailsFilter');
    const maxEmailsFilter = document.getElementById('maxEmailsFilter');
    const providerFilter = document.getElementById('providerFilter');
    const showOnlySelectedMode = document.getElementById('showOnlySelectedMode');
    const showOnlyPinnedMode = document.getElementById('showOnlyPinnedMode');
    const compactViewMode = document.getElementById('compactViewMode');
    const rememberSettingsMode = document.getElementById('rememberSettingsMode');
    const selectAllBtn = document.getElementById('selectAllBtn');
    const unselectAllBtn = document.getElementById('unselectAllBtn');
    const selectTop3Btn = document.getElementById('selectTop3Btn');
    const selectPinnedBtn = document.getElementById('selectPinnedBtn');
    const copySelectedBtn = document.getElementById('copySelectedBtn');
    const copySelectedBtnTop = document.getElementById('copySelectedBtnTop');
    const scrollToPreviewBtn = document.getElementById('scrollToPreviewBtn');
    const selectedPreviewArea = document.getElementById('selectedPreviewArea');
    const selectedChipList = document.getElementById('selectedChipList');
    const duplicatesArea = document.getElementById('duplicatesArea');
    const invalidArea = document.getElementById('invalidArea');
    const copyDuplicatesBtn = document.getElementById('copyDuplicatesBtn');
    const copyInvalidBtn = document.getElementById('copyInvalidBtn');
    const biggestFirstBtn = document.getElementById('biggestFirstBtn');
    const smallestFirstBtn = document.getElementById('smallestFirstBtn');
    const azBtn = document.getElementById('azBtn');
    const zaBtn = document.getElementById('zaBtn');
    const stickySelected = document.getElementById('stickySelected');
    const stickyVisible = document.getElementById('stickyVisible');
    const stickyDuplicates = document.getElementById('stickyDuplicates');
    const sideTotalEmails = document.getElementById('sideTotalEmails');
    const sideVisibleGroups = document.getElementById('sideVisibleGroups');
    const sideSelectedGroups = document.getElementById('sideSelectedGroups');
    const sideLargestGroup = document.getElementById('sideLargestGroup');
    const sideSmallestGroup = document.getElementById('sideSmallestGroup');
    const sidePinnedGroups = document.getElementById('sidePinnedGroups');
    const sideUniqueEmails = document.getElementById('sideUniqueEmails');
    const sideDuplicatesRemoved = document.getElementById('sideDuplicatesRemoved');
    const sideInvalidEntries = document.getElementById('sideInvalidEntries');
    const sideMergedDomains = document.getElementById('sideMergedDomains');
    const sideCollectedCards = document.getElementById('sideCollectedCards');
    const topGroupsList = document.getElementById('topGroupsList');

    const state = {
      rawEmails: [],
      uniqueEmails: [],
      duplicates: [],
      invalidEntries: [],
      grouped: {},
      visibleEntries: [],
      selected: new Set(),
      pinned: new Set(),
      combinedCardCount: 0,
      exactDomainCount: 0,
      sortMode: 'count-desc'
    };

    const providerAliases = {
      gmail: 'Google',
      googlemail: 'Google',
      yahoo: 'Yahoo',
      ymail: 'Yahoo',
      rocketmail: 'Yahoo',
      hotmail: 'Microsoft',
      outlook: 'Microsoft',
      live: 'Microsoft',
      msn: 'Microsoft',
      gmx: 'GMX',
      proton: 'Proton',
      protonmail: 'Proton',
      icloud: 'Apple',
      me: 'Apple',
      mac: 'Apple',
      aol: 'AOL',
      mail: 'Mail',
      yandex: 'Yandex',
      zoho: 'Zoho'
    };

    const groupAliasDefaults = {
      microsoft: ['hotmail', 'outlook', 'live', 'msn'],
      gmail: ['gmail', 'googlemail'],
      yahoo: ['yahoo', 'ymail', 'rocketmail'],
      gmx: ['gmx']
    };

    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function saveSettings() {
      if (!rememberSettingsMode.checked) return;
      const payload = {
        groupCategory: groupCategory.value,
        groupMethod: groupMethod.value,
        similarityThreshold: similarityThreshold.value,
        manualRulesInput: manualRulesInput.value,
        collectSmallMode: collectSmallMode.checked,
        collectLimit: collectLimit.value,
        searchInput: searchInput.value,
        minEmailsFilter: minEmailsFilter.value,
        maxEmailsFilter: maxEmailsFilter.value,
        providerFilter: providerFilter.value,
        showOnlySelectedMode: showOnlySelectedMode.checked,
        showOnlyPinnedMode: showOnlyPinnedMode.checked,
        compactViewMode: compactViewMode.checked,
        rememberSettingsMode: rememberSettingsMode.checked,
        sortMode: state.sortMode
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    }

    function loadSettings() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw);
        if (saved.groupCategory) groupCategory.value = saved.groupCategory;
        if (saved.groupMethod) groupMethod.value = saved.groupMethod;
        if (saved.similarityThreshold) similarityThreshold.value = saved.similarityThreshold;
        if (typeof saved.manualRulesInput === 'string') manualRulesInput.value = saved.manualRulesInput;
        collectSmallMode.checked = Boolean(saved.collectSmallMode);
        if (saved.collectLimit) collectLimit.value = saved.collectLimit;
        if (saved.searchInput) searchInput.value = saved.searchInput;
        if (saved.minEmailsFilter) minEmailsFilter.value = saved.minEmailsFilter;
        if (saved.maxEmailsFilter) maxEmailsFilter.value = saved.maxEmailsFilter;
        showOnlySelectedMode.checked = Boolean(saved.showOnlySelectedMode);
        showOnlyPinnedMode.checked = Boolean(saved.showOnlyPinnedMode);
        compactViewMode.checked = Boolean(saved.compactViewMode);
        rememberSettingsMode.checked = saved.rememberSettingsMode !== false;
        if (saved.sortMode) state.sortMode = saved.sortMode;
      } catch (error) {
        console.warn('Could not load settings', error);
      }
    }

    function extractEmailsAndMeta(text) {
      const matches = String(text || '').match(EMAIL_REGEX_GLOBAL) || [];
      const lowered = matches.map(email => email.toLowerCase());
      const seen = new Set();
      const uniqueEmails = [];
      const duplicates = [];

      lowered.forEach(email => {
        if (seen.has(email)) duplicates.push(email);
        else {
          seen.add(email);
          uniqueEmails.push(email);
        }
      });

      const invalidEntries = String(text || '')
        .split(/[\n,;\t ]+/)
        .map(token => token.trim())
        .filter(Boolean)
        .filter(token => !EMAIL_REGEX_SINGLE.test(token));

      return {
        rawEmails: lowered,
        uniqueEmails,
        duplicates,
        invalidEntries: [...new Set(invalidEntries)]
      };
    }

    function normalizeDomain(domain) {
      return String(domain || '')
        .toLowerCase()
        .trim()
        .replace(/^www\./, '')
        .replace(/^mail\./, '')
        .replace(/^email\./, '')
        .replace(/[^a-z0-9.-]/g, '')
        .replace(/\.{2,}/g, '.')
        .replace(/^-+|-+$/g, '');
    }

    function getDomainCore(domain) {
      const clean = normalizeDomain(domain);
      const labels = clean.split('.').filter(Boolean);
      if (!labels.length) return clean;
      const lastTwo = labels.slice(-2).join('.');
      if (labels.length >= 3 && MULTI_PART_TLDS.has(lastTwo)) {
        return labels[labels.length - 3];
      }
      if (labels.length >= 2) return labels[labels.length - 2];
      return labels[0];
    }

    function getRootProviderDomain(domain) {
      const clean = normalizeDomain(domain);
      const labels = clean.split('.').filter(Boolean);
      if (!labels.length) return clean;
      const lastTwo = labels.slice(-2).join('.');
      if (labels.length >= 3 && MULTI_PART_TLDS.has(lastTwo)) {
        return labels.slice(-3).join('.');
      }
      return labels.slice(-2).join('.');
    }

    function getCompanyFamilyKey(domain) {
      return getDomainCore(domain).replace(/[-_.]/g, '');
    }

    function getProviderLabel(groupName, domains = []) {
      const candidates = [groupName, ...domains].map(getDomainCore);
      for (const candidate of candidates) {
        if (providerAliases[candidate]) return providerAliases[candidate];
      }
      return 'Other';
    }

    function groupByDomain(emails) {
      const groups = {};
      emails.forEach(email => {
        const parts = email.split('@');
        if (parts.length !== 2) return;
        const domain = normalizeDomain(parts[1]);
        if (!groups[domain]) groups[domain] = [];
        groups[domain].push(email.toLowerCase());
      });
      return groups;
    }

    function parseManualRules(text) {
      const rules = [];
      String(text || '')
        .split(/\n+/)
        .map(line => line.trim())
        .filter(Boolean)
        .forEach(line => {
          const normalizedLine = line.replace(/&gt;/g, '>');
          const parts = normalizedLine.split('=>');
          if (parts.length !== 2) return;
          const aliases = parts[0].split(',').map(item => item.trim().toLowerCase()).filter(Boolean);
          const target = parts[1].trim().toLowerCase();
          if (aliases.length && target) rules.push({ aliases, target });
        });
      return rules;
    }

    function applyGroupingByKey(exactGroups, keyBuilder) {
      const buckets = {};
      Object.entries(exactGroups).forEach(([domain, emails]) => {
        const key = String(keyBuilder(domain, emails) || domain).trim().toLowerCase();
        if (!buckets[key]) {
          buckets[key] = { emails: [], domains: [], isCombined: false, sourceCount: 0 };
        }
        buckets[key].emails.push(...emails);
        buckets[key].domains.push(domain);
      });

      const result = {};
      Object.entries(buckets).forEach(([key, value]) => {
        const uniqueDomains = [...new Set(value.domains)].sort((a, b) => a.localeCompare(b));
        result[key] = {
          emails: [...new Set(value.emails)],
          domains: uniqueDomains,
          isCombined: false,
          sourceCount: uniqueDomains.length,
          provider: getProviderLabel(key, uniqueDomains)
        };
      });
      return result;
    }

    function buildProviderAliasGroups(exactGroups) {
      return applyGroupingByKey(exactGroups, domain => {
        const core = getDomainCore(domain);
        const match = Object.entries(groupAliasDefaults).find(([, aliases]) => aliases.includes(core));
        return match ? match[0] : core;
      });
    }

    function buildRootProviderGroups(exactGroups) {
      return applyGroupingByKey(exactGroups, domain => getDomainCore(getRootProviderDomain(domain)));
    }

    function buildSubdomainMergeGroups(exactGroups) {
      return applyGroupingByKey(exactGroups, domain => getRootProviderDomain(domain));
    }

    function buildNormalizeDomainGroups(exactGroups) {
      return applyGroupingByKey(exactGroups, domain => normalizeDomain(domain));
    }

    function buildManualRuleGroups(exactGroups, rulesText) {
      const rules = parseManualRules(rulesText);
      return applyGroupingByKey(exactGroups, domain => {
        const normalizedDomain = normalizeDomain(domain);
        const core = getDomainCore(normalizedDomain);
        const root = getRootProviderDomain(normalizedDomain);
        const matchedRule = rules.find(rule => rule.aliases.some(alias => core === alias || root.includes(alias) || normalizedDomain.includes(alias)));
        return matchedRule ? matchedRule.target : core;
      });
    }

    function buildCompanyFamilyGroups(exactGroups) {
      return applyGroupingByKey(exactGroups, domain => getCompanyFamilyKey(domain));
    }

    function buildStrictAliasGroups(exactGroups) {
      return applyGroupingByKey(exactGroups, domain => {
        const core = getDomainCore(domain);
        const match = Object.entries(groupAliasDefaults).find(([, aliases]) => aliases.includes(core));
        return match ? match[0] : domain;
      });
    }

    function levenshteinDistance(a, b) {
      const m = a.length;
      const n = b.length;
      const dp = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
      for (let i = 0; i <= m; i++) dp[i][0] = i;
      for (let j = 0; j <= n; j++) dp[0][j] = j;
      for (let i = 1; i <= m; i++) {
        for (let j = 1; j <= n; j++) {
          const cost = a[i - 1] === b[j - 1] ? 0 : 1;
          dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
        }
      }
      return dp[m][n];
    }

    function similarityScore(a, b) {
      if (!a || !b) return 0;
      if (a === b) return 1;
      if (a.includes(b) || b.includes(a)) {
        return Math.max(Math.min(Math.min(a.length, b.length) / Math.max(a.length, b.length) + 0.15, 1), 0);
      }
      const distance = levenshteinDistance(a, b);
      return 1 - distance / Math.max(a.length, b.length);
    }

    function chooseBestFamilyKey(cores) {
      const counts = {};
      cores.forEach(core => { counts[core] = (counts[core] || 0) + 1; });
      return Object.keys(counts).sort((a, b) => {
        if (counts[b] !== counts[a]) return counts[b] - counts[a];
        if (a.length !== b.length) return a.length - b.length;
        return a.localeCompare(b);
      })[0];
    }

    function buildSmartGroups(exactGroups, threshold) {
      const domainEntries = Object.entries(exactGroups).map(([domain, emails]) => ({ domain, emails, core: getDomainCore(domain) }));
      const families = [];

      domainEntries.forEach(entry => {
        let bestIndex = -1;
        let bestScore = 0;
        families.forEach((family, index) => {
          const score = similarityScore(entry.core, family.key);
          if (score > bestScore) {
            bestScore = score;
            bestIndex = index;
          }
        });

        if (bestIndex !== -1 && bestScore >= threshold) {
          families[bestIndex].domains.push(entry.domain);
          families[bestIndex].emails.push(...entry.emails);
          families[bestIndex].cores.push(entry.core);
          families[bestIndex].key = chooseBestFamilyKey(families[bestIndex].cores);
        } else {
          families.push({ key: entry.core, cores: [entry.core], domains: [entry.domain], emails: [...entry.emails] });
        }
      });

      const result = {};
      families.forEach(family => {
        const uniqueDomains = [...new Set(family.domains)].sort((a, b) => a.localeCompare(b));
        result[family.key] = {
          emails: [...new Set(family.emails)],
          domains: uniqueDomains,
          isCombined: false,
          sourceCount: uniqueDomains.length,
          provider: getProviderLabel(family.key, uniqueDomains)
        };
      });
      return result;
    }

    function buildHybridGroups(exactGroups, threshold, rulesText) {
      const manualFirst = buildManualRuleGroups(exactGroups, rulesText);
      const aliasInput = Object.fromEntries(
        Object.entries(manualFirst).map(([key, data]) => [key, data.emails || []])
      );
      const aliasStage = buildProviderAliasGroups(aliasInput);
      const smartInput = Object.fromEntries(
        Object.entries(aliasStage).map(([key, data]) => [key, data.emails || []])
      );
      return buildSmartGroups(smartInput, threshold);
    }

    function collectSmallGroups(grouped, limit) {
      const safeLimit = Math.max(1, Number(limit) || 100);
      const entries = Object.entries(grouped);
      const bigEntries = [];
      const smallEntries = [];

      entries.forEach(([name, data]) => {
        const emailCount = Array.isArray(data.emails) ? data.emails.length : 0;
        if (emailCount >= 1 && emailCount <= safeLimit) smallEntries.push([name, data]);
        else bigEntries.push([name, data]);
      });

      const combinedEntries = [];
      for (let i = 0; i < smallEntries.length; i += safeLimit) {
        const slice = smallEntries.slice(i, i + safeLimit);
        const allEmails = [];
        const allDomains = [];
        const labels = [];
        const providerBucket = new Set();

        slice.forEach(([name, data]) => {
          allEmails.push(...(data.emails || []));
          allDomains.push(...(data.domains || [name]));
          labels.push(`${name} (${(data.emails || []).length})`);
          providerBucket.add(data.provider || 'Other');
        });

        const cardName = `Collected Small Groups ${combinedEntries.length + 1}`;
        combinedEntries.push([cardName, {
          emails: allEmails,
          domains: allDomains,
          isCombined: true,
          labels,
          sourceCount: slice.length,
          provider: providerBucket.size === 1 ? [...providerBucket][0] : 'Mixed'
        }]);
      }

      return {
        grouped: Object.fromEntries([...bigEntries, ...combinedEntries]),
        combinedCardCount: combinedEntries.length
      };
    }

    function sortGroupedEntries(entries, mode) {
      return entries.sort((a, b) => {
        const aLen = (a[1].emails || []).length;
        const bLen = (b[1].emails || []).length;
        const aPinned = state.pinned.has(a[0]) ? 1 : 0;
        const bPinned = state.pinned.has(b[0]) ? 1 : 0;
        if (aPinned !== bPinned) return bPinned - aPinned;
        if (mode === 'count-asc') return aLen - bLen || a[0].localeCompare(b[0]);
        if (mode === 'name-asc') return a[0].localeCompare(b[0]);
        if (mode === 'name-desc') return b[0].localeCompare(a[0]);
        return bLen - aLen || a[0].localeCompare(b[0]);
      });
    }

    function rebuildProviderFilter(grouped) {
      const current = providerFilter.value;
      const providers = [...new Set(Object.values(grouped).map(item => item.provider || 'Other'))].sort((a, b) => a.localeCompare(b));
      providerFilter.innerHTML = '<option value="all">All Providers</option>';
      providers.forEach(provider => {
        const option = document.createElement('option');
        option.value = provider;
        option.textContent = provider;
        providerFilter.appendChild(option);
      });
      if ([...providerFilter.options].some(option => option.value === current)) {
        providerFilter.value = current;
      }
    }

    function applyFilters(grouped) {
      const query = searchInput.value.trim().toLowerCase();
      const minValue = Math.max(0, Number(minEmailsFilter.value) || 0);
      const maxValue = Math.max(0, Number(maxEmailsFilter.value) || 0);
      const providerValue = providerFilter.value;
      const entries = sortGroupedEntries(Object.entries(grouped), state.sortMode || 'count-desc');

      return entries.filter(([name, data]) => {
        const emailsLen = (data.emails || []).length;
        const haystack = `${name} ${(data.domains || []).join(' ')} ${(data.labels || []).join(' ')}`.toLowerCase();
        const matchesQuery = !query || haystack.includes(query);
        const matchesMin = emailsLen >= minValue;
        const matchesMax = maxValue === 0 || emailsLen <= maxValue;
        const matchesProvider = providerValue === 'all' || (data.provider || 'Other') === providerValue;
        const matchesSelected = !showOnlySelectedMode.checked || state.selected.has(name);
        const matchesPinned = !showOnlyPinnedMode.checked || state.pinned.has(name);
        return matchesQuery && matchesMin && matchesMax && matchesProvider && matchesSelected && matchesPinned;
      });
    }

    async function copyText(text, button) {
      try {
        await navigator.clipboard.writeText(String(text || ''));
        const original = button.textContent;
        button.textContent = 'Copied';
        button.disabled = true;
        setTimeout(() => {
          button.textContent = original;
          button.disabled = false;
        }, 1200);
      } catch (error) {
        alert('Copy failed. Please copy manually.');
      }
    }

    function updateSelectionPreview() {
      const selectedEntries = Object.entries(state.grouped).filter(([name]) => state.selected.has(name));
      const chips = [];
      const textParts = [];

      selectedEntries.forEach(([name, data]) => {
        chips.push(`<span class="selection-chip">${escapeHtml(name)} (${(data.emails || []).length})</span>`);
        textParts.push(`### ${name}\n${(data.emails || []).join('\n')}`);
      });

      selectedChipList.innerHTML = chips.join('');
      selectedPreviewArea.value = textParts.join('\n\n');
      const selectedSize = selectedEntries.length;
      selectedCount.textContent = String(selectedSize);
      sideSelectedGroups.textContent = String(selectedSize);
      stickySelected.textContent = `Selected: ${selectedSize}`;
    }

    function renderTopGroups(entries) {
      if (!entries.length) {
        topGroupsList.innerHTML = '<div class="muted">No results yet.</div>';
        return;
      }
      topGroupsList.innerHTML = entries.slice(0, 5).map(([name, data]) => (
        `<div class="sidebar-item"><span>${escapeHtml(name)}</span><strong>${(data.emails || []).length}</strong></div>`
      )).join('');
    }

    function updateSummary(entries) {
      const largest = entries[0];
      const smallest = entries[entries.length - 1];
      totalDomains.textContent = String(entries.length);
      stickyVisible.textContent = `Visible groups: ${entries.length}`;
      sideVisibleGroups.textContent = String(entries.length);
      sideLargestGroup.textContent = largest ? `${largest[0]} (${(largest[1].emails || []).length})` : '-';
      sideSmallestGroup.textContent = smallest ? `${smallest[0]} (${(smallest[1].emails || []).length})` : '-';
      pinnedCount.textContent = String(state.pinned.size);
      sidePinnedGroups.textContent = String(state.pinned.size);
      renderTopGroups(entries);
      updateSelectionPreview();
    }

    function renderResults(entries) {
      if (!entries.length) {
        results.innerHTML = '<div class="empty">No groups match the current filters.</div>';
        updateSummary([]);
        return;
      }

      const grid = document.createElement('div');
      grid.className = compactViewMode.checked ? 'results-grid compact-view' : 'results-grid';

      entries.forEach(([groupName, data], index) => {
        const emails = Array.isArray(data.emails) ? data.emails : [];
        const joined = emails.join('\n');
        const domainList = Array.isArray(data.domains) ? data.domains.join(', ') : groupName;
        const labels = Array.isArray(data.labels) ? data.labels.join(', ') : domainList;
        const areaId = `domain-area-${index}`;
        const isCombined = Boolean(data.isCombined);
        const isSelected = state.selected.has(groupName);
        const isPinned = state.pinned.has(groupName);

        const card = document.createElement('div');
        card.className = `${isCombined ? 'domain-card combined-card' : 'domain-card'}${isPinned ? ' pinned-card' : ''}`;

        const head = document.createElement('div');
        head.className = 'domain-head';

        const titleRow = document.createElement('div');
        titleRow.className = 'domain-title-row';

        const left = document.createElement('div');
        left.className = 'domain-left';

        const selectBox = document.createElement('input');
        selectBox.type = 'checkbox';
        selectBox.checked = isSelected;
        selectBox.addEventListener('change', () => {
          if (selectBox.checked) state.selected.add(groupName);
          else state.selected.delete(groupName);
          updateSelectionPreview();
          saveSettings();
        });

        const title = document.createElement('div');
        title.className = 'domain-title';
        title.textContent = groupName;

        const provider = document.createElement('span');
        provider.className = 'provider-tag';
        provider.textContent = data.provider || 'Other';

        left.appendChild(selectBox);
        left.appendChild(title);
        left.appendChild(provider);

        const badge = document.createElement('div');
        badge.className = isCombined ? 'badge badge-alt' : 'badge';
        badge.textContent = isCombined ? `${data.sourceCount || 0} groups · ${emails.length} emails` : `${emails.length} emails`;

        titleRow.appendChild(left);
        titleRow.appendChild(badge);

        const variants = document.createElement('div');
        variants.className = 'domain-variants';
        variants.textContent = isCombined ? `Included Groups: ${labels}` : `Variants: ${domainList || groupName}`;

        const meta = document.createElement('div');
        meta.className = 'domain-meta';
        meta.textContent = `Unique domains: ${(data.domains || []).length} · Provider: ${data.provider || 'Other'}`;

        const actions = document.createElement('div');
        actions.className = 'domain-actions';

        const copyButton = document.createElement('button');
        copyButton.className = 'copy-btn';
        copyButton.type = 'button';
        copyButton.textContent = 'Copy Emails';
        copyButton.addEventListener('click', () => copyText(joined, copyButton));

        const copyGroupButton = document.createElement('button');
        copyGroupButton.className = 'mini-btn';
        copyGroupButton.type = 'button';
        copyGroupButton.textContent = isCombined ? 'Copy Included Groups' : 'Copy Group Name';
        copyGroupButton.addEventListener('click', () => copyText(isCombined ? labels : groupName, copyGroupButton));

        const pinButton = document.createElement('button');
        pinButton.className = `mini-btn pin-btn${isPinned ? ' active' : ''}`;
        pinButton.type = 'button';
        pinButton.textContent = isPinned ? 'Pinned' : 'Pin';
        pinButton.addEventListener('click', () => {
          if (state.pinned.has(groupName)) state.pinned.delete(groupName);
          else state.pinned.add(groupName);
          renderCurrentView();
          saveSettings();
        });

        const previewOnlyButton = document.createElement('button');
        previewOnlyButton.className = 'mini-btn';
        previewOnlyButton.type = 'button';
        previewOnlyButton.textContent = 'Preview Only';
        previewOnlyButton.addEventListener('click', () => {
          state.selected.clear();
          state.selected.add(groupName);
          updateSelectionPreview();
          selectedPreviewArea.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });

        actions.appendChild(copyButton);
        actions.appendChild(copyGroupButton);
        actions.appendChild(pinButton);
        actions.appendChild(previewOnlyButton);

        const textarea = document.createElement('textarea');
        textarea.id = areaId;
        textarea.readOnly = true;
        textarea.value = joined;

        head.appendChild(titleRow);
        head.appendChild(variants);
        head.appendChild(meta);
        head.appendChild(actions);
        card.appendChild(head);
        card.appendChild(textarea);
        grid.appendChild(card);
      });

      results.innerHTML = '';
      results.appendChild(grid);
      updateSummary(entries);
    }

    function renderCurrentView() {
      state.visibleEntries = applyFilters(state.grouped);
      renderResults(state.visibleEntries);
      saveSettings();
    }

    function syncGroupingControls() {
      const selectedCategory = groupCategory.value;
      const methodOptions = Array.from(groupMethod.options);

      methodOptions.forEach(option => {
        const allowed = option.dataset.category === selectedCategory;
        option.disabled = !allowed;
        option.hidden = !allowed;
      });

      const currentOption = groupMethod.options[groupMethod.selectedIndex];
      if (!currentOption || currentOption.disabled) {
        const firstAllowed = methodOptions.find(option => !option.disabled);
        if (firstAllowed) {
          groupMethod.value = firstAllowed.value;
        }
      }

      manualRulesContainer.classList.toggle('hidden', !['manual-rules', 'hybrid'].includes(groupMethod.value));
      similarityThreshold.disabled = !['smart', 'hybrid'].includes(groupMethod.value);
      similarityThreshold.parentElement.style.opacity = similarityThreshold.disabled ? '0.55' : '1';
    }

    function handleExtract() {
      const rawText = emailInput.value.trim();
      const extracted = extractEmailsAndMeta(rawText);
      state.rawEmails = extracted.rawEmails;
      state.uniqueEmails = extracted.uniqueEmails;
      state.duplicates = extracted.duplicates;
      state.invalidEntries = extracted.invalidEntries;

      const exactGroups = groupByDomain(state.uniqueEmails);
      state.exactDomainCount = Object.keys(exactGroups).length;
      const threshold = Number(similarityThreshold.value);
      const mode = groupMethod.value;
      const shouldCollectSmall = collectSmallMode.checked;
      const limit = Math.max(1, Number(collectLimit.value) || 100);

      let grouped;
      if (mode === 'smart') grouped = buildSmartGroups(exactGroups, threshold);
      else if (mode === 'provider-alias') grouped = buildProviderAliasGroups(exactGroups);
      else if (mode === 'root-provider') grouped = buildRootProviderGroups(exactGroups);
      else if (mode === 'subdomain-merge') grouped = buildSubdomainMergeGroups(exactGroups);
      else if (mode === 'normalize-domain') grouped = buildNormalizeDomainGroups(exactGroups);
      else if (mode === 'manual-rules') grouped = buildManualRuleGroups(exactGroups, manualRulesInput.value);
      else if (mode === 'company-family') grouped = buildCompanyFamilyGroups(exactGroups);
      else if (mode === 'strict-alias') grouped = buildStrictAliasGroups(exactGroups);
      else if (mode === 'hybrid') grouped = buildHybridGroups(exactGroups, threshold, manualRulesInput.value);
      else {
        grouped = Object.fromEntries(
          Object.entries(exactGroups).map(([domain, list]) => [domain, {
            emails: list,
            domains: [domain],
            isCombined: false,
            sourceCount: 1,
            provider: getProviderLabel(domain, [domain])
          }])
        );
      }

      let combinedCardCount = 0;
      if (shouldCollectSmall) {
        const collected = collectSmallGroups(grouped, limit);
        grouped = collected.grouped;
        combinedCardCount = collected.combinedCardCount;
      }

      state.grouped = grouped;
      state.combinedCardCount = combinedCardCount;
      rebuildProviderFilter(grouped);

      totalEmails.textContent = String(state.uniqueEmails.length);
      sideTotalEmails.textContent = String(state.uniqueEmails.length);
      sideUniqueEmails.textContent = String(state.uniqueEmails.length);
      mergedDomains.textContent = String(Math.max(state.exactDomainCount - Object.keys(grouped).length + combinedCardCount, 0));
      collectedCards.textContent = String(combinedCardCount);
      duplicateCount.textContent = String(state.duplicates.length);
      invalidCount.textContent = String(state.invalidEntries.length);
      sideDuplicatesRemoved.textContent = String(state.duplicates.length);
      sideInvalidEntries.textContent = String(state.invalidEntries.length);
      sideMergedDomains.textContent = mergedDomains.textContent;
      sideCollectedCards.textContent = String(combinedCardCount);
      stickyDuplicates.textContent = `Duplicates removed: ${state.duplicates.length}`;
      duplicatesArea.value = [...new Set(state.duplicates)].join('\n');
      invalidArea.value = state.invalidEntries.join('\n');
      statusText.innerHTML = state.uniqueEmails.length ? '<span class="success">Done</span>' : 'No emails found';

      renderCurrentView();
    }

    function clearFilters() {
      searchInput.value = '';
      minEmailsFilter.value = '0';
      maxEmailsFilter.value = '0';
      providerFilter.value = 'all';
      showOnlySelectedMode.checked = false;
      showOnlyPinnedMode.checked = false;
    }

    function resetAll() {
      emailInput.value = '';
      clearFilters();
      totalEmails.textContent = '0';
      totalDomains.textContent = '0';
      mergedDomains.textContent = '0';
      collectedCards.textContent = '0';
      selectedCount.textContent = '0';
      pinnedCount.textContent = '0';
      invalidCount.textContent = '0';
      duplicateCount.textContent = '0';
      statusText.textContent = 'Waiting';
      state.sortMode = 'count-desc';
      selectedPreviewArea.value = '';
      duplicatesArea.value = '';
      invalidArea.value = '';
      selectedChipList.innerHTML = '';
      providerFilter.innerHTML = '<option value="all">All Providers</option>';
      stickySelected.textContent = 'Selected: 0';
      stickyVisible.textContent = 'Visible groups: 0';
      stickyDuplicates.textContent = 'Duplicates removed: 0';
      sideTotalEmails.textContent = '0';
      sideVisibleGroups.textContent = '0';
      sideSelectedGroups.textContent = '0';
      sideLargestGroup.textContent = '-';
      sideSmallestGroup.textContent = '-';
      sidePinnedGroups.textContent = '0';
      sideUniqueEmails.textContent = '0';
      sideDuplicatesRemoved.textContent = '0';
      sideInvalidEntries.textContent = '0';
      sideMergedDomains.textContent = '0';
      sideCollectedCards.textContent = '0';
      topGroupsList.innerHTML = '<div class="muted">No results yet.</div>';
      state.rawEmails = [];
      state.uniqueEmails = [];
      state.duplicates = [];
      state.invalidEntries = [];
      state.grouped = {};
      state.visibleEntries = [];
      state.selected.clear();
      state.pinned.clear();
      state.combinedCardCount = 0;
      state.exactDomainCount = 0;
      results.innerHTML = '<div class="empty">No results yet. Paste your email list above and click Extract Domains.</div>';
      syncGroupingControls();
      saveSettings();
    }

    function pasteDemoSample() {
      emailInput.value = [
        'a@gmail.com',
        'b@gmail.com',
        'c@gmail.com',
        'd@yahoo.com',
        'e@yahoo.fr',
        'f@hotmail.com',
        'g@hotmail.fr',
        'h@outlook.com',
        'i@gmx.de',
        'j@gmx.net',
        'duplicate@gmail.com',
        'duplicate@gmail.com',
        'bad-entry',
        'not-an-email',
        'user@mail.googlemail.com'
      ].join('\n');
    }

    function selectVisible() {
      state.visibleEntries.forEach(([name]) => state.selected.add(name));
      updateSelectionPreview();
      renderCurrentView();
    }

    function unselectAll() {
      state.selected.clear();
      updateSelectionPreview();
      renderCurrentView();
    }

    function selectTop(count) {
      state.selected.clear();
      state.visibleEntries.slice(0, count).forEach(([name]) => state.selected.add(name));
      updateSelectionPreview();
      renderCurrentView();
    }

    function selectPinned() {
      state.selected.clear();
      state.visibleEntries.forEach(([name]) => {
        if (state.pinned.has(name)) state.selected.add(name);
      });
      updateSelectionPreview();
      renderCurrentView();
    }

    function runSelfTests() {
      const basic = extractEmailsAndMeta('a@gmail.com a@gmail.com bad');
      console.assert(basic.uniqueEmails.length === 1, 'Unique email test failed');
      console.assert(basic.duplicates.length === 1, 'Duplicate detection failed');
      console.assert(basic.invalidEntries.includes('bad'), 'Invalid detection failed');
      console.assert(getDomainCore('hotmail.co.uk') === 'hotmail', 'Domain core failed');
      console.assert(getProviderLabel('hotmail', ['hotmail.fr']) === 'Microsoft', 'Provider detection failed');

      const smart = buildSmartGroups({ 'hotmail.com': ['a@hotmail.com'], 'hotmail.fr': ['b@hotmail.fr'], 'gmx.de': ['c@gmx.de'] }, 0.7);
      console.assert(Boolean(smart.hotmail), 'Smart group hotmail missing');
      console.assert(smart.hotmail.emails.length === 2, 'Hotmail merge count failed');

      const aliasGroups = buildProviderAliasGroups({ 'outlook.com': ['a@outlook.com'], 'live.com': ['b@live.com'] });
      console.assert(Boolean(aliasGroups.microsoft), 'Provider alias grouping failed');

      const manualRulesText = 'hotmail, outlook, live, msn => microsoft\ngmail, googlemail => gmail';
      const manualGroups = buildManualRuleGroups({
        'hotmail.com': ['a@hotmail.com'],
        'googlemail.com': ['b@googlemail.com']
      }, manualRulesText);
      console.assert(Boolean(manualGroups.microsoft), 'Manual rule grouping failed');
      console.assert(Boolean(manualGroups.gmail), 'Manual gmail rule failed');

      const hybridGroups = buildHybridGroups({
        'hotmail.com': ['a@hotmail.com'],
        'live.com': ['b@live.com'],
        'hotmail.fr': ['c@hotmail.fr']
      }, 0.7, manualRulesText);
      console.assert(Boolean(hybridGroups.microsoft || hybridGroups.hotmail), 'Hybrid grouping failed');

      const sorted = sortGroupedEntries([
        ['small', { emails: ['a'] }],
        ['big', { emails: ['a', 'b'] }]
      ], 'count-desc');
      console.assert(sorted[0][0] === 'big', 'Sort biggest first failed');

      const collected = collectSmallGroups({
        a: { emails: ['1@a.com'], domains: ['a.com'], provider: 'Other' },
        b: { emails: ['1@b.com'], domains: ['b.com'], provider: 'Other' },
        large: { emails: Array.from({ length: 150 }, (_, i) => `${i}@large.com`), domains: ['large.com'], provider: 'Other' }
      }, 100);
      console.assert(collected.combinedCardCount === 1, 'Collect small groups failed');

      const parsedRules = parseManualRules(manualRulesText);
      console.assert(parsedRules.length === 2, 'Manual rules parsing failed');
      console.assert(parsedRules[0].target === 'microsoft', 'Manual target parse failed');

      groupCategory.value = 'alias';
      syncGroupingControls();
      console.assert(groupMethod.value === 'provider-alias' || groupMethod.value === 'strict-alias', 'Grouping validation failed to select allowed alias option');
      console.assert(Array.from(groupMethod.options).filter(option => !option.disabled).every(option => option.dataset.category === 'alias'), 'Grouping validation failed to disable conflicting methods');

      const sampleRuleTextareaValue = manualRulesInput.value;
      console.assert(sampleRuleTextareaValue.includes('hotmail') && sampleRuleTextareaValue.includes('gmail'), 'Manual rules sample should remain visible in textarea');
    }

    extractBtn.addEventListener('click', handleExtract);
    clearBtn.addEventListener('click', resetAll);
    pasteSampleBtn.addEventListener('click', pasteDemoSample);
    selectAllBtn.addEventListener('click', selectVisible);
    unselectAllBtn.addEventListener('click', unselectAll);
    selectTop3Btn.addEventListener('click', () => selectTop(3));
    selectPinnedBtn.addEventListener('click', selectPinned);
    copySelectedBtn.addEventListener('click', () => copyText(selectedPreviewArea.value, copySelectedBtn));
    copySelectedBtnTop.addEventListener('click', () => copyText(selectedPreviewArea.value, copySelectedBtnTop));
    copyDuplicatesBtn.addEventListener('click', () => copyText(duplicatesArea.value, copyDuplicatesBtn));
    copyInvalidBtn.addEventListener('click', () => copyText(invalidArea.value, copyInvalidBtn));
    scrollToPreviewBtn.addEventListener('click', () => selectedPreviewArea.scrollIntoView({ behavior: 'smooth', block: 'center' }));
    biggestFirstBtn.addEventListener('click', () => { state.sortMode = 'count-desc'; renderCurrentView(); });
    smallestFirstBtn.addEventListener('click', () => { state.sortMode = 'count-asc'; renderCurrentView(); });
    azBtn.addEventListener('click', () => { state.sortMode = 'name-asc'; renderCurrentView(); });
    zaBtn.addEventListener('click', () => { state.sortMode = 'name-desc'; renderCurrentView(); });

    [groupCategory, groupMethod, similarityThreshold, manualRulesInput, collectSmallMode, collectLimit, searchInput, minEmailsFilter, maxEmailsFilter, providerFilter, showOnlySelectedMode, showOnlyPinnedMode, compactViewMode, rememberSettingsMode].forEach(control => {
      const eventName = control.tagName === 'TEXTAREA' || (control.tagName === 'INPUT' && control.type === 'text') ? 'input' : 'change';
      control.addEventListener(eventName, () => {
        if (control === rememberSettingsMode && !rememberSettingsMode.checked) {
          localStorage.removeItem(STORAGE_KEY);
        }
        if (control === groupCategory || control === groupMethod) syncGroupingControls();
        if (Object.keys(state.grouped).length) {
          if ([groupCategory, groupMethod, similarityThreshold, manualRulesInput, collectSmallMode].includes(control)) handleExtract();
          else renderCurrentView();
        }
        saveSettings();
      });
    });

    collectLimit.addEventListener('input', () => Object.keys(state.grouped).length && handleExtract());
    loadSettings();
    syncGroupingControls();
    runSelfTests();
    resetAll();
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(EMAIL_DOMAIN_EXTRACTOR_HTML)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
