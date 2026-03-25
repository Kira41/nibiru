import csv
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import math
import shlex
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path
from tkinter import Tk, filedialog

from nibiru import database_path
from flask import Flask, jsonify, redirect, render_template_string, request, send_file, session, url_for

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
CACHE_DB = database_path("campaign_monitor_cache.db", "campaign_monitor_cache.db")
MAX_WORKERS = max(4, (os.cpu_count() or 4))
PMTA_ACCOUNTING_FILE = Path("/var/log/pmta/acct.csv")
PMTA_COMMANDS_REFERENCE = Path(__file__).with_name("pmta_cli_commands_reference.txt")
DEFAULT_SOURCE_MODE = "local"


def get_pmta_runtime_info():
    host = os.getenv("PMTA_SSH_HOST", "ops.demo.internal")
    user = os.getenv("PMTA_SSH_USER", "pmtaops")
    command = ["ssh", f"{user}@{host}", "pmta show status"]
    runtime = {
        "platform": sys.platform,
        "accounting_file": str(PMTA_ACCOUNTING_FILE),
        "accounting_exists": PMTA_ACCOUNTING_FILE.exists(),
        "commands_reference": PMTA_COMMANDS_REFERENCE.name,
        "ssh_command": " ".join(command),
        "ssh_status": "not-configured",
        "ssh_output": "Set PMTA_SSH_HOST and PMTA_SSH_USER to enable a live SSH probe.",
    }
    if not os.getenv("PMTA_SSH_HOST"):
        return runtime
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
        runtime["ssh_status"] = "ok" if result.returncode == 0 else f"exit-{result.returncode}"
        runtime["ssh_output"] = (result.stdout or result.stderr or "No SSH output returned.").strip()[:240]
    except Exception as exc:
        runtime["ssh_status"] = "error"
        runtime["ssh_output"] = str(exc)
    return runtime


DASHBOARD_HTML = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Campaign Monitoring Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg: #081120;
            --bg2: #0b1730;
            --panel: #0b1a2f;
            --panel2: #0e2240;
            --line: rgba(79, 124, 189, 0.28);
            --line-strong: rgba(120, 170, 255, 0.35);
            --text: #e6edf7;
            --muted: #9ca9c4;
            --chip: #122847;
            --green: #2bdc8d;
            --red: #ff5b7e;
            --yellow: #ffcb52;
            --blue: #6ba7ff;
            --cyan: #43d3ff;
            --orange: #ff9a57;
            --shadow: 0 12px 30px rgba(0, 0, 0, 0.28);
        }

        * { box-sizing: border-box; }
        html, body { margin: 0; padding: 0; }
        body {
            font-family: Inter, Segoe UI, Arial, sans-serif;
            color: var(--text);
            background:
                radial-gradient(circle at top left, rgba(115,148,230,0.14), transparent 34%),
                linear-gradient(180deg, #081120 0%, #0b1730 100%);
            min-height: 100vh;
        }

        .shell {
            display: grid;
            grid-template-columns: 280px 1fr;
            min-height: 100vh;
        }

        .nibiru-sidebar {
            padding: 20px 18px 24px;
            border-right: 1px solid rgba(255,255,255,.06);
            background: linear-gradient(180deg, rgba(7,13,26,.98), rgba(8,17,32,.94));
            position: sticky;
            top: 0;
            height: 100vh;
        }

        .sidebarHeader {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brandLogo {
            width: 44px;
            height: 44px;
            border-radius: 12px;
            object-fit: cover;
            box-shadow: 0 10px 24px rgba(0,0,0,.28);
            border: 1px solid rgba(255,255,255,.12);
        }

        .brand {
            font-weight: 900;
            font-size: 22px;
            letter-spacing: -.03em;
            color: #f2f6ff;
        }

        .brandSub {
            margin-top: 10px;
            color: var(--muted);
            font-size: 13px;
            line-height: 1.6;
            max-width: 230px;
        }

        .menu {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 22px;
        }

        .menu a {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 13px 16px;
            min-height: 46px;
            border-radius: 16px;
            border: 1px solid rgba(158,177,214,.16);
            background: rgba(21,32,51,.72);
            color: var(--text);
            text-decoration: none;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.03);
        }

        .menu a.active {
            background: linear-gradient(180deg, rgba(74,97,156,.5), rgba(87,112,178,.42));
            border-color: rgba(141,165,241,.65);
            font-weight: 800;
            color: #f6f8ff;
            box-shadow: 0 0 0 1px rgba(111,138,217,.18) inset;
        }

        .sidebarCard {
            margin-top: 20px;
            padding: 16px 14px;
            border-radius: 18px;
            border: 1px solid rgba(158,177,214,.2);
            background: linear-gradient(180deg, rgba(36,46,64,.82), rgba(29,38,55,.9));
            box-shadow: var(--shadow);
        }

        .content {
            padding: 28px 18px 28px 24px;
        }

        .container {
            max-width: 1660px;
            margin: 0 auto;
            padding: 18px;
        }

        .card {
            background: linear-gradient(180deg, rgba(11, 26, 47, 0.98), rgba(7, 20, 38, 0.98));
            border: 1px solid var(--line);
            border-radius: 18px;
            box-shadow: var(--shadow);
        }

        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }

        .title h1 {
            margin: 0;
            font-size: 30px;
            letter-spacing: 0.2px;
        }

        .title p {
            margin: 6px 0 0;
            color: var(--muted);
            font-size: 14px;
        }

        .actions {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 11px 16px;
            border-radius: 13px;
            border: 1px solid var(--line);
            background: linear-gradient(180deg, #0d2546, #0a1d37);
            color: var(--text);
            text-decoration: none;
            cursor: pointer;
            font-weight: 700;
            transition: 0.18s ease;
        }

        .btn:hover { transform: translateY(-1px); border-color: var(--line-strong); }
        .btn.success { border-color: rgba(43,220,141,0.35); }
        .btn.danger { border-color: rgba(255,91,126,0.35); }
        .btn.info { border-color: rgba(67,211,255,0.35); }

        .notice {
            padding: 14px 16px;
            border-radius: 14px;
            margin-bottom: 16px;
            color: #c9e5ff;
            border: 1px solid rgba(67, 211, 255, 0.22);
            background: rgba(67, 211, 255, 0.06);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 16px;
        }

        .stat-card {
            padding: 16px;
            min-height: 104px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 8px;
        }

        .stat-title {
            color: var(--muted);
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.9px;
        }

        .stat-value {
            font-size: 34px;
            font-weight: 800;
            line-height: 1;
        }

        .stat-sub {
            color: var(--muted);
            font-size: 12px;
        }

        .green { color: var(--green); }
        .red { color: var(--red); }
        .yellow { color: var(--yellow); }
        .blue { color: var(--blue); }
        .cyan { color: var(--cyan); }
        .orange { color: var(--orange); }

        .section { margin-bottom: 16px; }
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
            padding: 18px 18px 0;
            flex-wrap: wrap;
        }

        .section-header h3 {
            margin: 0;
            font-size: 24px;
            letter-spacing: 0.2px;
        }

        .section-header p {
            margin: 6px 0 0;
            color: var(--muted);
            font-size: 13px;
        }

        .section-body { padding: 16px 18px 18px; }

        .toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }

        .filter-group {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }

        .filter-label {
            color: var(--muted);
            font-size: 13px;
            margin-right: 4px;
        }

        #serverPerPage {
            min-width: 96px;
            height: 42px;
            padding: 9px 38px 9px 14px;
            border-radius: 12px;
            border: 1px solid rgba(67, 211, 255, 0.28);
            background:
                linear-gradient(180deg, rgba(16, 36, 63, 0.98), rgba(10, 26, 46, 0.98));
            color: var(--text);
            font-weight: 800;
            font-size: 14px;
            line-height: 1;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(0,0,0,0.08);
            cursor: pointer;
            appearance: none;
            -webkit-appearance: none;
            -moz-appearance: none;
            background-image:
                linear-gradient(45deg, transparent 50%, #cfe3ff 50%),
                linear-gradient(135deg, #cfe3ff 50%, transparent 50%),
                linear-gradient(180deg, rgba(16, 36, 63, 0.98), rgba(10, 26, 46, 0.98));
            background-position:
                calc(100% - 18px) calc(50% - 3px),
                calc(100% - 12px) calc(50% - 3px),
                0 0;
            background-size: 6px 6px, 6px 6px, 100% 100%;
            background-repeat: no-repeat;
            transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
        }

        #serverPerPage:hover {
            border-color: rgba(67, 211, 255, 0.48);
            transform: translateY(-1px);
        }

        #serverPerPage:focus {
            border-color: rgba(67, 211, 255, 0.62);
            box-shadow: 0 0 0 3px rgba(67, 211, 255, 0.16);
        }

        .chip {
            border: 1px solid var(--line);
            background: var(--chip);
            color: #dce8ff;
            padding: 8px 12px;
            border-radius: 999px;
            font-weight: 700;
            cursor: pointer;
            user-select: none;
            font-size: 13px;
        }

        .chip.active {
            border-color: var(--line-strong);
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04);
            background: linear-gradient(180deg, #17365f, #112848);
        }

        .controls {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 14px;
        }

        .control {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .control label {
            color: var(--muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }

        .control input, .control select {
            width: 100%;
            border: 1px solid var(--line);
            outline: none;
            color: var(--text);
            background: #08182d;
            padding: 11px 12px;
            border-radius: 12px;
        }

        .layout-2 {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
            margin-bottom: 16px;
            align-items: stretch;
        }

        .layout-3 {
            display: grid;
            grid-template-columns: 1fr;
            gap: 14px;
            margin-bottom: 16px;
        }

        .table-wrap {
            overflow-x: hidden;
            overflow-y: auto;
            border-radius: 14px;
            border: 1px solid var(--line);
            background: rgba(0,0,0,0.08);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 0;
            table-layout: fixed;
        }

        th, td {
            padding: 10px 10px;
            border-bottom: 1px solid rgba(79,124,189,0.16);
            text-align: left;
            font-size: 12px;
            vertical-align: top;
            white-space: normal;
            word-break: break-word;
            overflow-wrap: anywhere;
            line-height: 1.35;
        }

        thead th {
            position: sticky;
            top: 0;
            z-index: 1;
            background: linear-gradient(180deg, #365176, #2d4668);
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.7px;
            color: #f5f9ff;
            cursor: pointer;
        }

        tbody tr:hover {
            background: rgba(255,255,255,0.025);
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
            border: 1px solid transparent;
        }

        .badge.green {
            color: #bbffd9;
            background: rgba(43,220,141,0.12);
            border-color: rgba(43,220,141,0.22);
        }
        .badge.red {
            color: #ffd0d8;
            background: rgba(255,91,126,0.12);
            border-color: rgba(255,91,126,0.22);
        }
        .badge.yellow {
            color: #ffe8ad;
            background: rgba(255,203,82,0.12);
            border-color: rgba(255,203,82,0.22);
        }
        .badge.blue {
            color: #d8e7ff;
            background: rgba(107,167,255,0.12);
            border-color: rgba(107,167,255,0.22);
        }

        .status-ok { color: var(--green); font-weight: 800; }
        .status-bounced { color: var(--red); font-weight: 800; }
        .status-unknown { color: var(--yellow); font-weight: 800; }
        .muted { color: var(--muted); }
        .mono {
            font-family: Consolas, Monaco, monospace;
            font-size: 11px;
            line-height: 1.35;
            word-break: break-all;
            overflow-wrap: anywhere;
        }
        .w-full { width: 100%; }
        .insight-list {
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
        }
        .insight-item {
            padding: 12px 14px;
            border-radius: 12px;
            border: 1px solid var(--line);
            background: rgba(255,255,255,0.02);
            font-size: 14px;
            line-height: 1.5;
        }

        .downloads {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
        }

        .download-card {
            padding: 14px;
            border-radius: 14px;
            border: 1px solid var(--line);
            background: rgba(255,255,255,0.02);
        }

        .download-card h4 { margin: 0 0 8px; font-size: 15px; }
        .download-card p { margin: 0 0 12px; color: var(--muted); font-size: 13px; }

        .hidden-row { display: none; }
        .sort-indicator { opacity: 0.75; margin-left: 6px; font-size: 11px; }

        @media (max-width: 1300px) {
            .stats-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
            .controls { grid-template-columns: repeat(3, minmax(0, 1fr)); }
            .layout-2, .layout-3 { grid-template-columns: 1fr; }
            .downloads { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            th, td { font-size: 11px; padding: 9px 8px; }
        }

        @media (max-width: 760px) {
            .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .controls { grid-template-columns: 1fr; }
            .downloads { grid-template-columns: 1fr; }
            .layout-2 { grid-template-columns: 1fr; }
        }

        @media (max-width: 920px) {
            .shell { grid-template-columns: 1fr; }
            .nibiru-sidebar {
                position: relative;
                height: auto;
                border-right: 0;
                border-bottom: 1px solid rgba(255,255,255,.08);
            }
            .content { padding: 18px 14px 24px; }
        }
    </style>
</head>
<body>
{% if show_nibiru_nav %}
<div class="shell">
    <aside class="nibiru-sidebar">
        <div class="sidebarHeader">
            <img class="brandLogo" src="{{ nav_urls.shiva_logo }}" alt="Shiva logo">
            <div class="brand">Shiva</div>
        </div>
        <div class="brandSub">Unified single-file Flask frontend sandbox with the Shiva Mini Sand styling applied across dashboard, jobs, job details, config, domains, send, and accounting surfaces.</div>
        <nav class="menu" aria-label="Shiva navigation">
            <a href="{{ nav_urls.dashboard }}">📊 Dashboard</a>
            <a href="{{ nav_urls.campaigns }}">📌 Campaigns</a>
            <a href="{{ nav_urls.send }}">✉️ Send mailer</a>
            <a href="{{ nav_urls.jobs }}">📄 Jobs</a>
            <a href="{{ nav_urls.job }}">🧩 Job Detail</a>
            <a href="{{ nav_urls.config }}">⚙️ Config</a>
            <a href="{{ nav_urls.domains }}">🌐 Domains</a>
            <a href="{{ nav_urls.accounting }}" class="active">🧾 Accounting Summary</a>
            <a href="{{ nav_urls.spamhaus }}">🛡️ Spamhaus Tool</a>
            <a href="{{ nav_urls.extractor }}">📬 Domain Extractor</a>
            <a href="{{ nav_urls.infra }}">🏗️ Infra Workspace</a>
            <a href="{{ nav_urls.tracker }}">🧭 Tracker Workbench</a>
        </nav>
        <div class="sidebarCard">
            <div style="font-weight:800; font-size:14px">Demo status</div>
            <div class="muted" style="margin-top:8px; line-height:1.6">Campaign: <code>{{ nav_status.name }}</code><br>Status: <b>{{ nav_status.status }}</b><br>Updated: {{ nav_status.updated_at }}</div>
        </div>
    </aside>
    <main class="content">
{% endif %}
<div class="container">
    <div class="topbar">
        <div class="title">
            <h1>Results</h1>
            <p>Dense one-page campaign monitoring layout with local DB cache support, sortable tables, domain diagnostics, and quick action exports.</p>
        </div>
        <div class="actions">
            {% if enable_ssh_mode %}
            <a class="btn {{ 'info' if source_mode == 'ssh' else '' }}" href="{{ action_use_ssh }}">Use SSH Source</a>
            {% endif %}
            <a class="btn {{ 'info' if source_mode == 'local' else '' }}" href="{{ action_use_local }}">Use Local Folder</a>
            <a class="btn" href="{{ action_select_folder }}">Select Folder</a>
            <a class="btn" href="{{ action_refresh }}">Refresh</a>
        </div>
    </div>

    <div class="notice">
        <div><strong>Mode:</strong> {{ source_mode_label }}</div>
        <div class="muted" style="margin-top:6px;">{{ source_mode_hint }}</div>
    </div>

    {% if not has_data %}
        <div class="notice">{{ empty_state_message }}</div>
    {% else %}
        <div class="notice">
            <div><strong>Folder:</strong> <span class="mono">{{ summary.folder }}</span></div>
            <div class="muted" style="margin-top:6px;">Files: {{ summary.files_count }} | Cached rows: {{ summary.cached_rows }} | Recipient domain cache: {{ summary.recipient_domain_total_rows or 0 }} | Total rows: {{ summary.total_rows }} | Thread workers: {{ summary.thread_workers }} | Last analysis: {{ summary.generated_at }}</div>
            <div class="muted" style="margin-top:6px;">PMTA file: {{ summary.pmta_runtime.accounting_file }} | Exists: {{ "yes" if summary.pmta_runtime.accounting_exists else "no" }} | SSH: {{ summary.pmta_runtime.ssh_status }} | Platform: {{ summary.pmta_runtime.platform }}</div>
        </div>

        <div class="stats-grid">
            <div class="card stat-card"><div class="stat-title">OK</div><div class="stat-value green">{{ summary.delivered }}</div><div class="stat-sub">{{ summary.delivery_rate }}% delivery rate</div></div>
            <div class="card stat-card"><div class="stat-title">Bounced</div><div class="stat-value red">{{ summary.bounced }}</div><div class="stat-sub">{{ summary.bounce_rate }}% bounce rate</div></div>
            <div class="card stat-card"><div class="stat-title">Refered</div><div class="stat-value yellow">{{ summary.unknown }}</div><div class="stat-sub">Rows that need review</div></div>
            <div class="card stat-card"><div class="stat-title">Sender Domains</div><div class="stat-value blue">{{ summary.unique_sender_domains }}</div><div class="stat-sub">Distinct sending domains</div></div>
            <div class="card stat-card"><div class="stat-title">Recipient Domains</div><div class="stat-value cyan">{{ summary.unique_recipient_domains }}</div><div class="stat-sub">Distinct destination domains</div></div>
            <div class="card stat-card"><div class="stat-title">DB File</div><div class="stat-value" style="font-size: 15px; line-height: 1.4;">{{ summary.db_file }}</div><div class="stat-sub">Local cache metadata</div></div>
        </div>

        <div class="layout-2">
            <div class="card section">
                <div class="section-header">
                    <div>
                        <h3>Executive Insights</h3>
                        <p>Automatic findings, actions, and campaign diagnosis generated from the logs.</p>
                    </div>
                </div>
                <div class="section-body">
                    <div class="insight-list">
                        {% for item in insights %}
                            <div class="insight-item">{{ item }}</div>
                        {% endfor %}
                    </div>
                </div>
            </div>
            <div class="card section">
                <div class="section-header">
                    <div>
                        <h3>Quick Charts</h3>
                        <p>Delivery mix and main bounce categories.</p>
                    </div>
                </div>
                <div class="section-body">
                    <canvas id="resultChart" height="120"></canvas>
                    <div style="height:16px"></div>
                    <canvas id="bounceChart" height="130"></canvas>
                </div>
            </div>
        </div>

        <div class="card section w-full" id="recipient-domain-section">
            <div class="section-header">
                <div>
                    <h3>Top Recipient Domains</h3>
                    <p>This section occupies the full width on purpose so long diagnostics remain visible. Click any header to sort ascending or descending, and use the chips to filter the table instantly.</p>
                </div>
            </div>
            <div class="section-body">
                <div class="toolbar">
                    <div class="filter-group">
                        <span class="filter-label">Show Filter</span>
                        <button class="chip active status-chip" data-status="all">All</button>
                        <button class="chip status-chip" data-status="delivered">OK</button>
                        <button class="chip status-chip" data-status="bounced">Bounced</button>
                        <button class="chip status-chip" data-status="mixed">Mixed</button>
                        <button class="chip status-chip" data-status="highrisk">High Risk</button>
                    </div>
                    <div class="filter-group">
                        <label class="filter-label" for="serverPerPage">Rows</label>
                        <select id="serverPerPage" onchange="changeRecipientPageSize()">
                            {% for size in page_size_options %}
                                <option value="{{ size }}" {% if size == selected_per_page %}selected{% endif %}>{{ size }}</option>
                            {% endfor %}
                        </select>
                        <a class="btn success" href="{{ download_base }}/recipient_domain_summary">Download Domain Summary</a>
                    </div>
                </div>

                <div class="controls">
                    <div class="control"><label>Search</label><input id="recipientSearch" placeholder="recipient domain, bounce reason, mx host..." oninput="applyRecipientFilters()"></div>
                    <div class="control"><label>Min Delivery %</label><input id="minDelivery" type="number" min="0" max="100" value="0" oninput="applyRecipientFilters()"></div>
                    <div class="control"><label>Max Delivery %</label><input id="maxDelivery" type="number" min="0" max="100" value="100" oninput="applyRecipientFilters()"></div>
                    <div class="control"><label>Rank Range</label><input id="rankMax" type="number" min="1" placeholder="Show top N rows" oninput="applyRecipientFilters()"></div>
                    <div class="control"><label>Sort Status</label><select id="statusRule" onchange="applyRecipientFilters()"><option value="all">All</option><option value="delivered">Only 100% OK</option><option value="bounced">Only 0% delivery</option><option value="mixed">Mixed</option><option value="risk">High Risk Only</option></select></div>
                </div>

                <div class="table-wrap">
                    <table id="recipientDomainTable" class="compact-table">
                        <thead>
                            <tr>
                                <th data-type="number" style="width:5%;">Rank</th>
                                <th data-type="text" style="width:13%;">Recipient Domain</th>
                                <th data-type="number" style="width:7%;">Total</th>
                                <th data-type="number" style="width:7%;">Delivered</th>
                                <th data-type="number" style="width:7%;">Bounced</th>
                                <th data-type="number" style="width:7%;">Refered</th>
                                <th data-type="number" style="width:7%;">Delivery %</th>
                                <th data-type="number" style="width:7%;">Bounce %</th>
                                <th data-type="text" style="width:16%;">Top Bounce Reason</th>
                                <th data-type="text" style="width:10%;">Top Category</th>
                                <th data-type="text" style="width:10%;">Top MX Host</th>
                                <th data-type="text" style="width:14%;">Recommendation</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in recipient_domain_rows %}
                            <tr data-delivery="{{ row.delivery_rate }}" data-bounce="{{ row.bounce_rate }}" data-rank="{{ row.row_rank or (recipient_page.offset + loop.index) }}" data-mode="{{ row.mode }}" data-risk="{{ row.risk_level }}">
                                <td>{{ row.row_rank or (recipient_page.offset + loop.index) }}</td>
                                <td class="mono">{{ row.domain }}</td>
                                <td>{{ row.total }}</td>
                                <td><span class="badge green">{{ row.delivered }}</span></td>
                                <td><span class="badge red">{{ row.bounced }}</span></td>
                                <td><span class="badge yellow">{{ row.unknown }}</span></td>
                                <td class="status-ok">{{ row.delivery_rate }}%</td>
                                <td class="status-bounced">{{ row.bounce_rate }}%</td>
                                <td>{{ row.top_bounce_reason }}</td>
                                <td>{{ row.top_bounce_category }}</td>
                                <td class="mono">{{ row.top_mx_host }}</td>
                                <td>{{ row.recommendation }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:12px;flex-wrap:wrap;">
                    <div class="muted">Showing {{ recipient_page.rows|length }} rows from {{ recipient_page.total_rows }} total recipient domains. Page {{ recipient_page.page }} of {{ recipient_page.total_pages }}.</div>
                    <div class="filter-group">
                        {% if recipient_page.page > 1 %}
                            <a class="btn" href="{{ index_base }}?page=1&per_page={{ selected_per_page }}">First</a>
                            <a class="btn" href="{{ index_base }}?page={{ recipient_page.page - 1 }}&per_page={{ selected_per_page }}">Previous</a>
                        {% endif %}
                        {% if recipient_page.page < recipient_page.total_pages %}
                            <a class="btn" href="{{ index_base }}?page={{ recipient_page.page + 1 }}&per_page={{ selected_per_page }}">Next</a>
                            <a class="btn" href="{{ index_base }}?page={{ recipient_page.total_pages }}&per_page={{ selected_per_page }}">Last</a>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <div class="layout-3">
            <div class="card section">
                <div class="section-header"><div><h3>Sender Domain Performance</h3><p>Moved here as requested, next to other infrastructure diagnostics.</p></div></div>
                <div class="section-body">
                    <div class="table-wrap">
                        <table class="sortable-table compact-table">
                            <thead>
                                <tr>
                                    <th data-type="number" style="width:6%;">Rank</th>
                                    <th data-type="text" style="width:24%;">Sender Domain</th>
                                    <th data-type="number" style="width:12%;">Total</th>
                                    <th data-type="number" style="width:12%;">Delivered</th>
                                    <th data-type="number" style="width:12%;">Bounced</th>
                                    <th data-type="number" style="width:12%;">Delivery %</th>
                                    <th data-type="text" style="width:22%;">Top Category</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for row in sender_domain_rows[:25] %}
                                <tr>
                                    <td>{{ loop.index }}</td><td class="mono">{{ row.domain }}</td><td>{{ row.total }}</td><td>{{ row.delivered }}</td><td>{{ row.bounced }}</td><td>{{ row.delivery_rate }}%</td><td>{{ row.top_bounce_category }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="card section">
                <div class="section-header"><div><h3>Infrastructure Diagnostics</h3><p>Pool, source IP, and source host insights.</p></div></div>
                <div class="section-body">
                    <div class="table-wrap">
                        <table class="sortable-table compact-table">
                            <thead>
                                <tr>
                                    <th data-type="text" style="width:16%;">Entity</th>
                                    <th data-type="text" style="width:32%;">Value</th>
                                    <th data-type="number" style="width:12%;">Total</th>
                                    <th data-type="number" style="width:12%;">Delivered</th>
                                    <th data-type="number" style="width:12%;">Bounced</th>
                                    <th data-type="number" style="width:16%;">Delivery %</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for row in infra_rows %}
                                <tr>
                                    <td>{{ row.kind }}</td><td class="mono">{{ row.value }}</td><td>{{ row.total }}</td><td>{{ row.delivered }}</td><td>{{ row.bounced }}</td><td>{{ row.delivery_rate }}%</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="card section">
                <div class="section-header"><div><h3>Bounce Categories</h3><p>Grouped root causes for faster decision making.</p></div></div>
                <div class="section-body">
                    <div class="table-wrap">
                        <table class="sortable-table compact-table">
                            <thead>
                                <tr>
                                    <th data-type="number" style="width:8%;">Rank</th>
                                    <th data-type="text" style="width:26%;">Category</th>
                                    <th data-type="number" style="width:14%;">Count</th>
                                    <th data-type="number" style="width:14%;">Share %</th>
                                    <th data-type="text" style="width:38%;">Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for row in bounce_category_rows %}
                                <tr>
                                    <td>{{ loop.index }}</td><td>{{ row.category }}</td><td>{{ row.count }}</td><td>{{ row.rate }}%</td><td>{{ row.action }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div class="layout-2">
            <div class="card section">
                <div class="section-header"><div><h3>Time Analysis</h3><p>Messages over time to expose spikes, throttling, or sudden blocks.</p></div></div>
                <div class="section-body"><canvas id="timelineChart" height="150"></canvas></div>
            </div>
            <div class="card section">
                <div class="section-header"><div><h3>Action Center</h3><p>Extract ready-made lists for retry, referred review, or deeper investigation.</p></div></div>
                <div class="section-body">
                    <div class="downloads">
                        <div class="download-card"><h4>Delivered Recipients</h4><p>All successful addresses.</p><a class="btn success" href="{{ download_base }}/delivered_recipients">Download</a></div>
                        <div class="download-card"><h4>Bounced Recipients</h4><p>All failed addresses.</p><a class="btn danger" href="{{ download_base }}/bounced_recipients">Download</a></div>
                        <div class="download-card"><h4>Referred Emails TXT</h4><p>All referred recipients gathered into one TXT download.</p><a class="btn danger" href="{{ download_base }}/referred_emails">Download Referred</a></div>
                        <div class="download-card"><h4>Retry Later List</h4><p>Temporary and remotely rejected domains.</p><a class="btn info" href="{{ download_base }}/retry_later_list">Download</a></div>
                        <div class="download-card"><h4>Bounced Rows CSV</h4><p>Full bounced rows with categories.</p><a class="btn danger" href="{{ download_base }}/bounced_rows">Download</a></div>
                        <div class="download-card"><h4>Sender Summary CSV</h4><p>Sender domain level intelligence.</p><a class="btn info" href="{{ download_base }}/sender_domain_summary">Download</a></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="card section">
            <div class="section-header"><div><h3>Recent Bounce Events</h3><p>Latest failures with recipient, destination, status, pool, and SMTP response.</p></div></div>
            <div class="section-body">
                <div class="table-wrap">
                    <table class="sortable-table compact-table">
                        <thead>
                            <tr>
                                <th data-type="text">Time</th>
                                <th data-type="text">Sender</th>
                                <th data-type="text">Recipient</th>
                                <th data-type="text">Recipient Domain</th>
                                <th data-type="text">Pool</th>
                                <th data-type="text">MX Host</th>
                                <th data-type="text">Category</th>
                                <th data-type="text">Response</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in recent_bounces %}
                            <tr>
                                <td>{{ row.arrival_time }}</td>
                                <td class="mono">{{ row.sender }}</td>
                                <td class="mono">{{ row.recipient }}</td>
                                <td>{{ row.recipient_domain }}</td>
                                <td>{{ row.pool }}</td>
                                <td class="mono">{{ row.mx_host }}</td>
                                <td>{{ row.bounce_category }}</td>
                                <td>{{ row.response_text }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    {% endif %}
</div>

{% if has_data %}
<script>
const chartSummary = {{ chart_summary | safe }};
const bounceSummary = {{ bounce_chart | safe }};
const timelineSummary = {{ timeline_chart | safe }};

new Chart(document.getElementById('resultChart'), {
    type: 'bar',
    data: {
        labels: chartSummary.labels,
        datasets: [{ label: 'Rows', data: chartSummary.values, backgroundColor: ['rgba(43,220,141,0.7)','rgba(255,91,126,0.7)','rgba(255,203,82,0.7)'], borderWidth: 1 }]
    },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#dce8ff' }, grid: { color: 'rgba(255,255,255,0.05)' } }, y: { ticks: { color: '#dce8ff' }, grid: { color: 'rgba(255,255,255,0.05)' } } } }
});

new Chart(document.getElementById('bounceChart'), {
    type: 'bar',
    data: {
        labels: bounceSummary.labels,
        datasets: [{ label: 'Bounces', data: bounceSummary.values, backgroundColor: 'rgba(107,167,255,0.72)', borderWidth: 1 }]
    },
    options: { responsive: true, plugins: { legend: { labels: { color: '#dce8ff' } } }, scales: { x: { ticks: { color: '#dce8ff' }, grid: { color: 'rgba(255,255,255,0.05)' } }, y: { ticks: { color: '#dce8ff' }, grid: { color: 'rgba(255,255,255,0.05)' } } } }
});

new Chart(document.getElementById('timelineChart'), {
    type: 'line',
    data: {
        labels: timelineSummary.labels,
        datasets: [
            { label: 'Delivered', data: timelineSummary.delivered, borderColor: 'rgba(43,220,141,1)', backgroundColor: 'rgba(43,220,141,0.15)', tension: 0.25, fill: true },
            { label: 'Bounced', data: timelineSummary.bounced, borderColor: 'rgba(255,91,126,1)', backgroundColor: 'rgba(255,91,126,0.10)', tension: 0.25, fill: true }
        ]
    },
    options: { responsive: true, plugins: { legend: { labels: { color: '#dce8ff' } } }, scales: { x: { ticks: { color: '#dce8ff' }, grid: { color: 'rgba(255,255,255,0.05)' } }, y: { ticks: { color: '#dce8ff' }, grid: { color: 'rgba(255,255,255,0.05)' } } } }
});

function makeSortable(table) {
    const headers = table.querySelectorAll('thead th');
    headers.forEach((header, idx) => {
        let direction = 1;
        header.addEventListener('click', () => {
            const type = header.dataset.type || 'text';
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            headers.forEach(h => {
                const s = h.querySelector('.sort-indicator');
                if (s) s.remove();
            });
            rows.sort((a, b) => {
                let av = a.children[idx].innerText.trim();
                let bv = b.children[idx].innerText.trim();
                if (type === 'number') {
                    av = parseFloat(av.replace(/[^0-9.-]/g, '')) || 0;
                    bv = parseFloat(bv.replace(/[^0-9.-]/g, '')) || 0;
                    return (av - bv) * direction;
                }
                return av.localeCompare(bv) * direction;
            });
            rows.forEach(r => tbody.appendChild(r));
            const indicator = document.createElement('span');
            indicator.className = 'sort-indicator';
            indicator.textContent = direction === 1 ? '▲' : '▼';
            header.appendChild(indicator);
            direction *= -1;
        });
    });
}

document.querySelectorAll('.sortable-table, #recipientDomainTable').forEach(makeSortable);

const statusChips = document.querySelectorAll('.status-chip');
let currentChip = 'all';
statusChips.forEach(chip => {
    chip.addEventListener('click', () => {
        statusChips.forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        currentChip = chip.dataset.status;
        applyRecipientFilters();
    });
});

function applyRecipientFilters() {
    const q = document.getElementById('recipientSearch').value.toLowerCase().trim();
    const minDelivery = parseFloat(document.getElementById('minDelivery').value || '0');
    const maxDelivery = parseFloat(document.getElementById('maxDelivery').value || '100');
    const rankMax = parseInt(document.getElementById('rankMax').value || '0', 10);
    const statusRule = document.getElementById('statusRule').value;
    const rows = document.querySelectorAll('#recipientDomainTable tbody tr');

    rows.forEach((row) => {
        const txt = row.innerText.toLowerCase();
        const delivery = parseFloat(row.dataset.delivery || '0');
        const rank = parseInt(row.dataset.rank || '0', 10);
        const mode = row.dataset.mode || '';
        const risk = row.dataset.risk || '';

        let ok = true;
        if (q && !txt.includes(q)) ok = false;
        if (delivery < minDelivery || delivery > maxDelivery) ok = false;
        if (rankMax && rank > rankMax) ok = false;

        const effective = statusRule === 'all' ? currentChip : statusRule;
        if (effective === 'delivered' && mode !== 'delivered') ok = false;
        if (effective === 'bounced' && mode !== 'bounced') ok = false;
        if (effective === 'mixed' && mode !== 'mixed') ok = false;
        if (effective === 'risk' && risk !== 'high') ok = false;
        if (effective === 'highrisk' && risk !== 'high') ok = false;

        row.style.display = ok ? '' : 'none';
    });
}

function changeRecipientPageSize() {
    const perPage = document.getElementById('serverPerPage').value;
    const url = new URL(window.location.href);
    url.searchParams.set('per_page', perPage);
    url.searchParams.set('page', '1');
    window.location.href = url.toString();
}
</script>
{% if show_nibiru_nav %}
    </main>
</div>
{% endif %}
{% endif %}
</body>
</html>
'''


def init_db():
    conn = sqlite3.connect(str(CACHE_DB))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS folder_cache (
            folder_path TEXT PRIMARY KEY,
            signature TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS recipient_domain_cache (
            folder_path TEXT NOT NULL,
            signature TEXT NOT NULL,
            row_rank INTEGER NOT NULL,
            domain TEXT,
            total INTEGER,
            delivered INTEGER,
            bounced INTEGER,
            unknown INTEGER,
            delivery_rate REAL,
            bounce_rate REAL,
            top_bounce_reason TEXT,
            top_bounce_category TEXT,
            top_mx_host TEXT,
            recommendation TEXT,
            mode TEXT,
            risk_level TEXT,
            PRIMARY KEY(folder_path, signature, row_rank)
        )
        """
    )
    conn.commit()
    conn.close()


def get_folder_signature(folder_path):
    parts = []
    for p in sorted(Path(folder_path).glob("*.csv")):
        try:
            stat = p.stat()
            parts.append(f"{p.name}:{stat.st_size}:{int(stat.st_mtime)}")
        except Exception:
            continue
    return "|".join(parts)


def load_cache(folder_path, signature):
    conn = sqlite3.connect(str(CACHE_DB))
    cur = conn.cursor()
    cur.execute("SELECT payload FROM folder_cache WHERE folder_path=? AND signature=?", (folder_path, signature))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row[0])


def get_recipient_domain_page(folder_path, signature, page=1, per_page=25):
    page = max(1, int(page or 1))
    per_page = max(1, min(1000, int(per_page or 25)))
    offset = (page - 1) * per_page

    conn = sqlite3.connect(str(CACHE_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM recipient_domain_cache WHERE folder_path=? AND signature=?", (folder_path, signature))
    total_rows = cur.fetchone()[0]

    if total_rows == 0:
        conn.close()
        return {
            "rows": [],
            "total_rows": 0,
            "page": 1,
            "per_page": per_page,
            "total_pages": 1,
            "offset": 0,
        }

    total_pages = max(1, math.ceil(total_rows / per_page))
    if page > total_pages:
        page = total_pages
        offset = (page - 1) * per_page

    cur.execute(
        """
        SELECT row_rank, domain, total, delivered, bounced, unknown, delivery_rate, bounce_rate,
               top_bounce_reason, top_bounce_category, top_mx_host, recommendation, mode, risk_level
        FROM recipient_domain_cache
        WHERE folder_path=? AND signature=?
        ORDER BY row_rank ASC
        LIMIT ? OFFSET ?
        """,
        (folder_path, signature, per_page, offset)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    return {
        "rows": rows,
        "total_rows": total_rows,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "offset": offset,
    }


def replace_recipient_domain_cache(folder_path, signature, rows):
    conn = sqlite3.connect(str(CACHE_DB))
    cur = conn.cursor()
    cur.execute("DELETE FROM recipient_domain_cache WHERE folder_path=?", (folder_path,))

    payload = []
    for idx, row in enumerate(rows, start=1):
        payload.append((
            folder_path,
            signature,
            idx,
            row.get("domain", ""),
            row.get("total", 0),
            row.get("delivered", 0),
            row.get("bounced", 0),
            row.get("unknown", 0),
            row.get("delivery_rate", 0.0),
            row.get("bounce_rate", 0.0),
            row.get("top_bounce_reason", "-"),
            row.get("top_bounce_category", "-"),
            row.get("top_mx_host", "-"),
            row.get("recommendation", ""),
            row.get("mode", "mixed"),
            row.get("risk_level", "normal"),
        ))

    if payload:
        cur.executemany(
            """
            INSERT INTO recipient_domain_cache(
                folder_path, signature, row_rank, domain, total, delivered,
                bounced, unknown, delivery_rate, bounce_rate,
                top_bounce_reason, top_bounce_category, top_mx_host,
                recommendation, mode, risk_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload
        )
    conn.commit()
    conn.close()


def ensure_recipient_domain_cache(folder_path, signature, analysis):
    conn = sqlite3.connect(str(CACHE_DB))
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM recipient_domain_cache WHERE folder_path=? AND signature=?",
        (folder_path, signature)
    )
    count = cur.fetchone()[0]
    conn.close()

    if count == 0:
        rows = (analysis or {}).get("recipient_domain_rows") or []
        if rows:
            replace_recipient_domain_cache(folder_path, signature, rows)
        return len(rows)
    return count


def save_cache(folder_path, signature, payload):
    conn = sqlite3.connect(str(CACHE_DB))
    cur = conn.cursor()
    cur.execute(
        "REPLACE INTO folder_cache(folder_path, signature, payload, updated_at) VALUES (?, ?, ?, ?)",
        (folder_path, signature, json.dumps(payload), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def percent(part, total):
    if not total:
        return 0.0
    return round((part / total) * 100, 2)


def normalize_email(value):
    if not value:
        return ""
    _, addr = parseaddr(str(value).strip())
    return addr.lower().strip()


def extract_domain(email_value):
    email_value = normalize_email(email_value)
    if "@" not in email_value:
        return ""
    return email_value.split("@", 1)[1].lower().strip()


def parse_dt(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            pass
    return None


def clean_text(value):
    return re.sub(r"\s+", " ", (value or "").strip())


def bounce_category(reason, status_text=""):
    hay = f"{reason} {status_text}".lower()
    if not hay.strip():
        return "unknown"
    if "cloudmark" in hay or "listed on" in hay or "blacklist" in hay or "blocklist" in hay:
        return "blocklist"
    if "spam" in hay:
        return "spam-related"
    if "user unknown" in hay or "does not exist" in hay or "bad destination mailbox address" in hay or "recipient address rejected" in hay:
        return "bad-mailbox"
    if "not authorized" in hay or "policy" in hay:
        return "policy-rejection"
    if "system not accepting network messages" in hay or "try again later" in hay or "temporar" in hay:
        return "temporary-or-remote-rejection"
    if "mailbox full" in hay or "quota" in hay:
        return "mailbox-full"
    if "timeout" in hay:
        return "timeout"
    return "other"


def bounce_action(category):
    return {
        "bad-mailbox": "Suppress permanently",
        "spam-related": "Review content and reputation",
        "blocklist": "Fix IP/domain reputation before retry",
        "policy-rejection": "Inspect policy, SPF, DKIM, DMARC",
        "temporary-or-remote-rejection": "Retry later",
        "mailbox-full": "Retry later",
        "timeout": "Retry later",
        "other": "Manual review",
        "unknown": "Manual review",
    }.get(category, "Manual review")


def classify_record(row):
    code = (row[0] if len(row) > 0 else "").strip().lower()
    status_word = (row[6] if len(row) > 6 else "").strip().lower()
    smtp_status = (row[7] if len(row) > 7 else "").strip().lower()
    if code == "d" or "success" in status_word or "relayed" in status_word or "2.0.0" in smtp_status:
        return "delivered"
    if code == "b" or "fail" in status_word or smtp_status.startswith("5"):
        return "bounced"
    return "unknown"


def row_to_record(row, source_file):
    row = list(row)
    while len(row) < 21:
        row.append("")
    sender = normalize_email(row[3])
    recipient = normalize_email(row[4])
    result = classify_record(row)
    response_text = clean_text(row[8])
    category = bounce_category(response_text, row[7])
    dt = parse_dt(row[2]) or parse_dt(row[1])
    bucket = dt.strftime("%Y-%m-%d %H:00") if dt else "Refered"
    return {
        "type_code": clean_text(row[0]),
        "log_time": clean_text(row[1]),
        "arrival_time": clean_text(row[2]),
        "sender": sender,
        "recipient": recipient,
        "result_word": clean_text(row[6]),
        "smtp_status": clean_text(row[7]),
        "response_text": response_text,
        "mx_host": clean_text(row[9]),
        "dsn_group": clean_text(row[10]),
        "protocol": clean_text(row[11]),
        "source_host": clean_text(row[12]),
        "source_protocol": clean_text(row[13]),
        "source_ip": clean_text(row[14]),
        "target_ip": clean_text(row[15]),
        "smtp_features": clean_text(row[16]),
        "size": clean_text(row[17]),
        "pool": clean_text(row[18]),
        "category_path": clean_text(row[20]),
        "sender_domain": extract_domain(sender),
        "recipient_domain": extract_domain(recipient),
        "result": result,
        "bounce_category": category,
        "recommended_action": bounce_action(category),
        "source_file": source_file,
        "time_bucket": bucket,
    }


def parse_csv_file(file_path):
    records = []
    with open(file_path, "r", encoding="utf-8", newline="", errors="replace") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        for row in reader:
            if not row:
                continue
            records.append(row_to_record(row, file_path.name))
    return records


def parse_csv_text(csv_text, source_name):
    records = []
    handle = io.StringIO(csv_text)
    sample = handle.read(4096)
    handle.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample)
    except Exception:
        dialect = csv.excel
    reader = csv.reader(handle, dialect)
    for row in reader:
        if not row:
            continue
        records.append(row_to_record(row, source_name))
    return records


def summarize_entity(records, key_name, top_n=20, include_category=False):
    stats = defaultdict(lambda: {"delivered": 0, "bounced": 0, "unknown": 0, "total": 0, "cats": Counter()})
    for r in records:
        value = r.get(key_name) or "unknown"
        stats[value][r["result"]] += 1
        stats[value]["total"] += 1
        if r["result"] == "bounced":
            stats[value]["cats"][r["bounce_category"]] += 1
    rows = []
    for value, s in stats.items():
        row = {
            "value": value,
            "total": s["total"],
            "delivered": s["delivered"],
            "bounced": s["bounced"],
            "unknown": s["unknown"],
            "delivery_rate": percent(s["delivered"], s["total"]),
        }
        if include_category:
            row["top_bounce_category"] = s["cats"].most_common(1)[0][0] if s["cats"] else "-"
        rows.append(row)
    rows.sort(key=lambda x: (-x["total"], x["value"]))
    return rows[:top_n]


def build_runtime_config(external_config=None):
    external_config = external_config or {}
    host = (external_config.get("ssh_host") or os.getenv("PMTA_SSH_HOST") or "").strip()
    user = (external_config.get("ssh_user") or os.getenv("PMTA_SSH_USER") or "").strip()
    port = str(external_config.get("ssh_port") or os.getenv("PMTA_SSH_PORT") or "22").strip() or "22"
    key_path = (external_config.get("ssh_key_path") or os.getenv("PMTA_SSH_KEY_PATH") or "").strip()
    remote_file = (external_config.get("pmta_accounting_file") or os.getenv("PMTA_ACCOUNTING_FILE") or str(PMTA_ACCOUNTING_FILE)).strip()
    timeout_raw = external_config.get("ssh_timeout") or os.getenv("PMTA_SSH_TIMEOUT") or "8"
    try:
        timeout = max(3, int(float(timeout_raw)))
    except Exception:
        timeout = 8
    return {
        "ssh_host": host,
        "ssh_user": user,
        "ssh_port": port,
        "ssh_key_path": key_path,
        "ssh_pass": (external_config.get("ssh_pass") or "").strip(),
        "ssh_timeout": timeout,
        "pmta_accounting_file": remote_file,
        "ssh_enabled": bool(host and user),
    }


def build_ssh_command(runtime_config, remote_command):
    target = f"{runtime_config['ssh_user']}@{runtime_config['ssh_host']}"
    command = [
        "ssh",
        "-p",
        str(runtime_config["ssh_port"]),
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={runtime_config['ssh_timeout']}",
    ]
    if runtime_config.get("ssh_key_path"):
        command.extend(["-i", runtime_config["ssh_key_path"]])
    command.extend([target, remote_command])
    return command


def run_ssh_command(runtime_config, remote_command):
    if not runtime_config.get("ssh_enabled"):
        raise RuntimeError("SSH host/user are not configured yet.")
    if runtime_config.get("ssh_pass"):
        raise RuntimeError("Password-based SSH is not supported by script6.py in this environment; use an SSH key or agent.")
    command = build_ssh_command(runtime_config, remote_command)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=max(5, runtime_config["ssh_timeout"] + 2),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"SSH exited with code {result.returncode}").strip())
    return {
        "command": " ".join(shlex.quote(part) for part in command),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def build_analysis(records, *, source_label, files_count, signature, bad_files=None, cacheable=False):
    init_db()
    bad_files = bad_files or []
    delivered = [r for r in records if r["result"] == "delivered"]
    bounced = [r for r in records if r["result"] == "bounced"]
    unknown = [r for r in records if r["result"] == "unknown"]

    sender_domain_stats = defaultdict(lambda: {"delivered": 0, "bounced": 0, "unknown": 0, "total": 0, "cats": Counter()})
    recipient_domain_stats = defaultdict(lambda: {"delivered": 0, "bounced": 0, "unknown": 0, "total": 0, "reasons": Counter(), "cats": Counter(), "mx": Counter()})
    bounce_category_counter = Counter()
    bounce_reason_counter = Counter()
    time_buckets = defaultdict(lambda: {"delivered": 0, "bounced": 0})

    for r in records:
        sdom = r["sender_domain"] or "unknown"
        rdom = r["recipient_domain"] or "unknown"
        sender_domain_stats[sdom][r["result"]] += 1
        sender_domain_stats[sdom]["total"] += 1
        recipient_domain_stats[rdom][r["result"]] += 1
        recipient_domain_stats[rdom]["total"] += 1
        if r["result"] == "bounced":
            sender_domain_stats[sdom]["cats"][r["bounce_category"]] += 1
            recipient_domain_stats[rdom]["reasons"][r["response_text"] or "-"] += 1
            recipient_domain_stats[rdom]["cats"][r["bounce_category"]] += 1
            recipient_domain_stats[rdom]["mx"][r["mx_host"] or "-"] += 1
            bounce_category_counter[r["bounce_category"]] += 1
            if r["response_text"]:
                bounce_reason_counter[r["response_text"]] += 1
        if r["time_bucket"] != "Refered":
            if r["result"] == "delivered":
                time_buckets[r["time_bucket"]]["delivered"] += 1
            elif r["result"] == "bounced":
                time_buckets[r["time_bucket"]]["bounced"] += 1

    recipient_domain_rows = []
    for domain, s in recipient_domain_stats.items():
        delivery_rate = percent(s["delivered"], s["total"])
        bounce_rate = percent(s["bounced"], s["total"])
        mode = "mixed"
        if s["delivered"] == s["total"]:
            mode = "delivered"
        elif s["bounced"] == s["total"]:
            mode = "bounced"
        risk_level = "high" if bounce_rate >= 70 or s["cats"].get("blocklist", 0) or s["cats"].get("spam-related", 0) else "normal"
        top_category = s["cats"].most_common(1)[0][0] if s["cats"] else "-"
        recommendation = bounce_action(top_category) if top_category != "-" else "Keep sending"
        recipient_domain_rows.append({
            "domain": domain,
            "total": s["total"],
            "delivered": s["delivered"],
            "bounced": s["bounced"],
            "unknown": s["unknown"],
            "delivery_rate": delivery_rate,
            "bounce_rate": bounce_rate,
            "top_bounce_reason": s["reasons"].most_common(1)[0][0] if s["reasons"] else "-",
            "top_bounce_category": top_category,
            "top_mx_host": s["mx"].most_common(1)[0][0] if s["mx"] else "-",
            "recommendation": recommendation,
            "mode": mode,
            "risk_level": risk_level,
        })
    recipient_domain_rows.sort(key=lambda x: (-x["total"], x["domain"]))
    replace_recipient_domain_cache(source_label, signature, recipient_domain_rows)

    sender_domain_rows = []
    for domain, s in sender_domain_stats.items():
        sender_domain_rows.append({
            "domain": domain,
            "total": s["total"],
            "delivered": s["delivered"],
            "bounced": s["bounced"],
            "unknown": s["unknown"],
            "delivery_rate": percent(s["delivered"], s["total"]),
            "top_bounce_category": s["cats"].most_common(1)[0][0] if s["cats"] else "-",
        })
    sender_domain_rows.sort(key=lambda x: (-x["total"], x["domain"]))

    infra_rows = []
    for kind, key in [("Pool", "pool"), ("Source IP", "source_ip"), ("Source Host", "source_host"), ("MX Host", "mx_host")]:
        for row in summarize_entity(records, key, top_n=6):
            infra_rows.append({"kind": kind, "value": row["value"], "total": row["total"], "delivered": row["delivered"], "bounced": row["bounced"], "delivery_rate": row["delivery_rate"]})
    infra_rows.sort(key=lambda x: (-x["total"], x["kind"], x["value"]))

    bounce_category_rows = []
    for category, count in bounce_category_counter.most_common():
        bounce_category_rows.append({
            "category": category,
            "count": count,
            "rate": percent(count, len(bounced)),
            "action": bounce_action(category),
        })

    top_sender = sender_domain_rows[0]["domain"] if sender_domain_rows else "N/A"
    worst_sender = min(sender_domain_rows, key=lambda x: x["delivery_rate"])["domain"] if sender_domain_rows else "N/A"
    top_recipient = recipient_domain_rows[0]["domain"] if recipient_domain_rows else "N/A"
    worst_recipient = max(recipient_domain_rows, key=lambda x: x["bounce_rate"])["domain"] if recipient_domain_rows else "N/A"
    top_reason = bounce_reason_counter.most_common(1)[0][0] if bounce_reason_counter else "N/A"

    insights = [
        f"Threaded parsing is enabled with {MAX_WORKERS} workers, so multiple CSV files are processed in parallel for faster loading.",
        f"Best sender domain by volume is {top_sender}, while the weakest sender by delivery rate is {worst_sender}.",
        f"Top recipient domain by volume is {top_recipient}; highest-risk recipient domain is {worst_recipient} based on bounce behavior.",
        f"Most repeated bounce reason is: {top_reason}",
        f"Recipient-domain rows are now paged from SQLite instead of rendering the full dataset in memory on the browser.",
        f"The page size selector supports 25, 50, 100, 500, and 1000 rows per page so the browser stays stable with huge datasets.",
        f"Suppression and retry lists are generated automatically from bounce categories, which turns raw logs into usable action lists.",
        f"Infrastructure diagnostics compare pools, source IPs, source hosts, and MX hosts so you can see whether the issue comes from content, identity, or transport path.",
        f"Timeline analysis can expose burst failures, throttling windows, or sudden reputation drops during a campaign run.",
        f"Cached results are stored in the local SQLite DB file {CACHE_DB} and reused when the folder signature has not changed.",
    ]

    sorted_buckets = sorted(time_buckets.items())
    timeline_chart = {
        "labels": [k for k, _ in sorted_buckets][:36],
        "delivered": [v["delivered"] for _, v in sorted_buckets][:36],
        "bounced": [v["bounced"] for _, v in sorted_buckets][:36],
    }

    pmta_runtime = get_pmta_runtime_info()

    analysis = {
        "summary": {
            "folder": source_label,
            "files_count": files_count,
            "bad_files_count": len(bad_files),
            "total_rows": len(records),
            "cached_rows": len(records),
            "delivered": len(delivered),
            "bounced": len(bounced),
            "unknown": len(unknown),
            "delivery_rate": percent(len(delivered), len(records)),
            "bounce_rate": percent(len(bounced), len(records)),
            "unique_sender_domains": len(sender_domain_stats),
            "unique_recipient_domains": len(recipient_domain_stats),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "thread_workers": MAX_WORKERS,
            "db_file": CACHE_DB,
            "signature": signature,
            "recipient_domain_total_rows": len(recipient_domain_rows),
            "pmta_runtime": pmta_runtime,
        },
        "records": records,
        "delivered": delivered,
        "bounced": bounced,
        "unknown": unknown,
        "recipient_domain_rows": recipient_domain_rows,
        "sender_domain_rows": sender_domain_rows,
        "infra_rows": infra_rows,
        "bounce_category_rows": bounce_category_rows,
        "recent_bounces": sorted(bounced, key=lambda r: parse_dt(r["arrival_time"]) or datetime.min, reverse=True)[:80],
        "insights": insights,
        "chart_summary": {"labels": ["OK", "Bounced", "Refered"], "values": [len(delivered), len(bounced), len(unknown)]},
        "bounce_chart": {"labels": [x["category"] for x in bounce_category_rows[:8]], "values": [x["count"] for x in bounce_category_rows[:8]]},
        "timeline_chart": timeline_chart,
        "bad_files": bad_files,
        "retry_later": [r for r in bounced if r["bounce_category"] in {"temporary-or-remote-rejection", "mailbox-full", "timeout"}],
        "suppression_list": [r for r in bounced if r["bounce_category"] in {"bad-mailbox"}],
    }
    if cacheable:
        save_cache(source_label, signature, analysis)
    return analysis


def analyze_folder(folder_path):
    init_db()
    signature = get_folder_signature(folder_path)
    cached = load_cache(folder_path, signature)
    if cached:
        cached.setdefault("summary", {})["db_file"] = CACHE_DB
        cached["summary"]["cached_rows"] = cached["summary"].get("total_rows", 0)
        cached["summary"]["thread_workers"] = MAX_WORKERS
        cached["summary"]["signature"] = signature
        cached["summary"].setdefault("pmta_runtime", get_pmta_runtime_info())
        if "recipient_domain_total_rows" not in cached["summary"]:
            cached["summary"]["recipient_domain_total_rows"] = len(cached.get("recipient_domain_rows") or [])
        cache_count = ensure_recipient_domain_cache(folder_path, signature, cached)
        cached["summary"]["recipient_domain_cached_count"] = cache_count
        cached["summary"]["source_mode"] = "local"
        return cached

    files = sorted(Path(folder_path).glob("*.csv"))
    records = []
    bad_files = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(parse_csv_file, fp): fp for fp in files}
        for future in as_completed(futures):
            fp = futures[future]
            try:
                records.extend(future.result())
            except Exception as exc:
                bad_files.append({"file": fp.name, "error": str(exc)})

    analysis = build_analysis(
        records,
        source_label=folder_path,
        files_count=len(files),
        signature=signature,
        bad_files=bad_files,
        cacheable=True,
    )
    analysis["summary"]["source_mode"] = "local"
    return analysis


def analyze_ssh_source(external_config=None):
    runtime_config = build_runtime_config(external_config)
    remote_file = runtime_config["pmta_accounting_file"]
    remote_command = f"test -f {shlex.quote(remote_file)} && cat {shlex.quote(remote_file)}"
    result = run_ssh_command(runtime_config, remote_command)
    records = parse_csv_text(result["stdout"], f"ssh:{runtime_config['ssh_host']}:{Path(remote_file).name}")
    analysis = build_analysis(
        records,
        source_label=f"ssh://{runtime_config['ssh_user']}@{runtime_config['ssh_host']}:{runtime_config['ssh_port']}{remote_file}",
        files_count=1,
        signature=f"ssh::{runtime_config['ssh_host']}::{remote_file}",
        bad_files=[],
        cacheable=False,
    )
    analysis["summary"]["source_mode"] = "ssh"
    analysis["summary"]["pmta_runtime"] = {
        **analysis["summary"].get("pmta_runtime", {}),
        "ssh_status": "ok",
        "ssh_command": result["command"],
        "accounting_file": remote_file,
        "accounting_exists": True,
        "ssh_output": (result["stdout"] or result["stderr"] or "Remote accounting file loaded successfully.").strip()[:240],
    }
    return analysis


def get_analysis(namespace="script6"):
    return app.config.get(f"ANALYSIS_{namespace}")


def set_analysis(data, namespace="script6"):
    app.config[f"ANALYSIS_{namespace}"] = data


def state_key(namespace, name):
    return f"{namespace}_{name}"


def get_source_mode(namespace="script6"):
    return session.get(state_key(namespace, "source_mode"), DEFAULT_SOURCE_MODE)


def set_source_mode(mode, namespace="script6"):
    session[state_key(namespace, "source_mode")] = "ssh" if mode == "ssh" else "local"


def get_last_folder(namespace="script6"):
    return session.get(state_key(namespace, "last_folder"))


def set_last_folder(folder_path, namespace="script6"):
    session[state_key(namespace, "last_folder")] = folder_path


def build_mode_metadata(source_mode, runtime_config, has_data):
    if source_mode == "ssh":
        target = runtime_config.get("ssh_host") or "not-configured"
        remote_file = runtime_config.get("pmta_accounting_file") or str(PMTA_ACCOUNTING_FILE)
        label = "SSH / Nibiru configuration"
        hint = f"Reads the remote accounting CSV over SSH from {target}:{remote_file} using the SSH settings saved in Nibiru."
        empty = "No SSH data loaded yet. Make sure Nibiru SSH host/user are configured, then click Refresh."
    else:
        label = "Local folder / Select Folder"
        hint = "Uses the original Script 6 folder-based workflow with Select Folder and local CSV parsing."
        empty = "No data loaded yet. Click Select Folder and choose a folder that contains CSV files."
    if has_data:
        empty = ""
    return label, hint, empty


def load_analysis_for_mode(namespace="script6", external_config=None):
    source_mode = get_source_mode(namespace)
    if source_mode == "ssh":
        return analyze_ssh_source(external_config)
    folder_path = get_last_folder(namespace)
    if folder_path and os.path.isdir(folder_path):
        return analyze_folder(folder_path)
    return None


def render_dashboard_page(
    *,
    namespace="script6",
    external_config=None,
    route_urls=None,
):
    analysis = get_analysis(namespace)
    has_data = analysis is not None
    runtime_config = build_runtime_config(external_config)
    source_mode = get_source_mode(namespace)
    recipient_page = {"rows": [], "page": 1, "per_page": 25, "total_pages": 1, "total_rows": 0, "offset": 0}
    page_size_options = [25, 50, 100, 500, 1000]
    selected_per_page = 25

    if has_data:
        selected_page = max(1, int(request.args.get("page", 1) or 1))
        selected_per_page = int(request.args.get("per_page", 25) or 25)
        if selected_per_page not in page_size_options:
            selected_per_page = 25
        summary = analysis.get("summary", {})
        summary_folder = summary.get("folder") or summary.get("signature") or source_mode
        summary_signature = summary.get("signature") or summary_folder
        recipient_page = get_recipient_domain_page(
            summary_folder,
            summary_signature,
            selected_page,
            selected_per_page,
        )
        if recipient_page["total_rows"] == 0 and analysis.get("recipient_domain_rows"):
            replace_recipient_domain_cache(
                summary_folder,
                summary_signature,
                analysis.get("recipient_domain_rows") or [],
            )
            recipient_page = get_recipient_domain_page(
                summary_folder,
                summary_signature,
                selected_page,
                selected_per_page,
            )

    route_urls = route_urls or {}
    show_nibiru_nav = bool(route_urls.get("show_nibiru_nav"))
    nav_urls = {
        "dashboard": route_urls.get("dashboard", "/"),
        "campaigns": route_urls.get("campaigns", "/campaigns"),
        "send": route_urls.get("send", "/send"),
        "jobs": route_urls.get("jobs", "/jobs"),
        "job": route_urls.get("job", "/job/job-240301-a"),
        "config": route_urls.get("config", "/config"),
        "domains": route_urls.get("domains", "/domains"),
        "accounting": route_urls.get("accounting", route_urls.get("index", "/")),
        "spamhaus": route_urls.get("spamhaus", "/spamhaus"),
        "extractor": route_urls.get("extractor", "/extractor"),
        "infra": route_urls.get("infra", "/infra"),
        "tracker": route_urls.get("tracker", "/tracker"),
        "shiva_logo": route_urls.get("shiva_logo", "/img/shiva.png"),
    }
    nav_status = {
        "name": route_urls.get("sidebar_campaign_name", "Demo launch"),
        "status": route_urls.get("sidebar_campaign_status", "running"),
        "updated_at": route_urls.get("sidebar_updated_at", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")),
    }
    source_mode_label, source_mode_hint, empty_state_message = build_mode_metadata(source_mode, runtime_config, has_data)

    return render_template_string(
        DASHBOARD_HTML,
        has_data=has_data,
        summary=(analysis or {}).get("summary", {}),
        recipient_domain_rows=recipient_page.get("rows", []),
        recipient_page=recipient_page,
        page_size_options=page_size_options,
        selected_per_page=selected_per_page,
        sender_domain_rows=(analysis or {}).get("sender_domain_rows", []),
        infra_rows=(analysis or {}).get("infra_rows", []),
        bounce_category_rows=(analysis or {}).get("bounce_category_rows", []),
        recent_bounces=(analysis or {}).get("recent_bounces", []),
        insights=(analysis or {}).get("insights", []),
        chart_summary=json.dumps((analysis or {}).get("chart_summary", {})),
        bounce_chart=json.dumps((analysis or {}).get("bounce_chart", {})),
        timeline_chart=json.dumps((analysis or {}).get("timeline_chart", {})),
        source_mode=source_mode,
        source_mode_label=source_mode_label,
        source_mode_hint=source_mode_hint,
        empty_state_message=empty_state_message,
        enable_ssh_mode=True,
        action_select_folder=route_urls.get("select_folder", "/select-folder"),
        action_refresh=route_urls.get("refresh", "/refresh"),
        action_use_ssh=route_urls.get("use_ssh", "/use-ssh"),
        action_use_local=route_urls.get("use_local", "/use-local"),
        index_base=route_urls.get("index", "/"),
        download_base=route_urls.get("download_base", "/download"),
        show_nibiru_nav=show_nibiru_nav,
        nav_urls=nav_urls,
        nav_status=nav_status,
    )


def select_folder_action(namespace="script6"):
    folder_path = choose_folder_dialog()
    if not folder_path:
        return False
    set_source_mode("local", namespace)
    set_last_folder(folder_path, namespace)
    set_analysis(analyze_folder(folder_path), namespace)
    return True


def refresh_action(namespace="script6", external_config=None):
    analysis = load_analysis_for_mode(namespace, external_config)
    if analysis is not None:
        set_analysis(analysis, namespace)
    return analysis


def download_action(kind, namespace="script6"):
    analysis = get_analysis(namespace)
    if not analysis:
        return None
    if kind == "delivered_recipients":
        return make_text_download("delivered_recipients.txt", sorted({r["recipient"] for r in analysis["delivered"] if r["recipient"]}))
    if kind == "bounced_recipients":
        return make_text_download("bounced_recipients.txt", sorted({r["recipient"] for r in analysis["bounced"] if r["recipient"]}))
    if kind == "referred_emails":
        return make_text_download("referred_emails.txt", sorted({r["recipient"] for r in analysis["unknown"] if r["recipient"]}))
    if kind == "retry_later_list":
        return make_text_download("retry_later_list.txt", sorted({r["recipient"] for r in analysis["retry_later"] if r["recipient"]}))
    if kind == "bounced_rows":
        headers = ["arrival_time", "sender", "sender_domain", "recipient", "recipient_domain", "result", "smtp_status", "response_text", "bounce_category", "recommended_action", "mx_host", "pool", "source_ip", "target_ip", "source_file"]
        return make_csv_download("bounced_rows.csv", analysis["bounced"], headers)
    if kind == "recipient_domain_summary":
        headers = ["domain", "total", "delivered", "bounced", "unknown", "delivery_rate", "bounce_rate", "top_bounce_reason", "top_bounce_category", "top_mx_host", "recommendation", "mode", "risk_level"]
        rows = analysis.get("recipient_domain_rows") or []
        return make_csv_download("recipient_domain_summary.csv", rows, headers)
    if kind == "sender_domain_summary":
        headers = ["domain", "total", "delivered", "bounced", "unknown", "delivery_rate", "top_bounce_category"]
        return make_csv_download("sender_domain_summary.csv", analysis["sender_domain_rows"], headers)
    return False


def choose_folder_dialog():
    selected = {"path": None}
    def open_dialog():
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected["path"] = filedialog.askdirectory(title="Select Folder That Contains CSV Files")
        root.destroy()
    thread = threading.Thread(target=open_dialog)
    thread.start()
    thread.join()
    return selected["path"]


def make_text_download(filename, lines):
    output = io.BytesIO("\n".join(lines).encode("utf-8"))
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=filename, mimetype="text/plain")


def make_csv_download(filename, rows, headers):
    sio = io.StringIO()
    writer = csv.DictWriter(sio, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in headers})
    bio = io.BytesIO(sio.getvalue().encode("utf-8"))
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=filename, mimetype="text/csv")


@app.route("/")
def index():
    return render_dashboard_page(
        namespace="script6",
        route_urls={
            "index": url_for("index"),
            "select_folder": url_for("select_folder"),
            "refresh": url_for("refresh"),
            "use_ssh": url_for("use_ssh"),
            "use_local": url_for("use_local"),
            "download_base": "/download",
        },
    )


@app.route("/select-folder")
def select_folder():
    if not select_folder_action("script6"):
        return redirect(url_for("index"))
    return redirect(url_for("index"))


@app.route("/refresh")
def refresh():
    refresh_action("script6")
    return redirect(url_for("index"))


@app.route("/use-ssh")
def use_ssh():
    set_source_mode("ssh", "script6")
    try:
        refresh_action("script6")
    except Exception:
        set_analysis(None, "script6")
    return redirect(url_for("index"))


@app.route("/use-local")
def use_local():
    set_source_mode("local", "script6")
    refresh_action("script6")
    return redirect(url_for("index"))


@app.route("/api/stats")
def api_stats():
    analysis = get_analysis("script6")
    if not analysis:
        return jsonify({"error": "No analysis loaded"}), 404
    return jsonify(analysis["summary"])


@app.route("/download/<kind>")
def download(kind):
    response = download_action(kind, "script6")
    if response is None:
        return redirect(url_for("index"))
    if response is False:
        return redirect(url_for("index"))
    return response


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
