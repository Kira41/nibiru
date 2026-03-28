
from __future__ import annotations

import copy
import csv
import json
import os
import random
import re
import shutil
import subprocess
import sys
import uuid
import socket
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template_string, request, send_from_directory, url_for


REPO_ROOT = Path(__file__).resolve().parent
DATABASE_DIR = REPO_ROOT / "database"


def ensure_database_dir() -> Path:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    return DATABASE_DIR


def database_path(filename: str, *legacy_candidates: str | Path) -> Path:
    target_path = ensure_database_dir() / filename

    if target_path.exists():
        return target_path

    candidates = []
    for candidate in legacy_candidates:
        candidate_path = Path(candidate)
        if not candidate_path.is_absolute():
            candidate_path = REPO_ROOT / candidate_path
        candidates.append(candidate_path)

    for candidate_path in candidates:
        if candidate_path.exists() and candidate_path != target_path:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(candidate_path), str(target_path))
            break

    return target_path


import script1
import script2
import script3
import script4
import script5
import script6

app = Flask(__name__)
app.secret_key = os.getenv("NIBIRU_SECRET_KEY", "nibiru-dev-secret")

TOOL_NAV_CSS = r"""
<style>
  .nibiru-tool-body{padding-top:72px !important;}
  .nibiru-topnav{
    position:fixed;
    top:0;
    left:0;
    right:0;
    z-index:9999;
    display:flex;
    align-items:center;
    gap:12px;
    flex-wrap:wrap;
    padding:14px 18px;
    background:rgba(6,12,24,.94);
    backdrop-filter:blur(14px);
    border-bottom:1px solid rgba(145,164,201,.18);
    box-shadow:0 10px 30px rgba(0,0,0,.25);
  }
  .nibiru-topnav__brand{
    display:inline-flex;
    align-items:center;
    gap:10px;
    margin-right:8px;
    color:#f2f6ff;
    font-weight:900;
    text-decoration:none;
    letter-spacing:-.02em;
  }
  .nibiru-topnav__brand img{
    width:34px;
    height:34px;
    border-radius:10px;
    object-fit:cover;
    border:1px solid rgba(255,255,255,.12);
    box-shadow:0 8px 20px rgba(0,0,0,.28);
  }
  .nibiru-topnav__links{display:flex; gap:8px; flex-wrap:wrap; align-items:center;}
  .nibiru-topnav__links a{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    gap:8px;
    min-height:40px;
    padding:9px 12px;
    border-radius:999px;
    border:1px solid rgba(158,177,214,.16);
    background:rgba(21,32,51,.72);
    color:#e6edf7;
    text-decoration:none;
    font:600 13px/1.2 Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .nibiru-topnav__links a:hover{filter:brightness(1.06);}
  .nibiru-topnav__links a.active{
    background:linear-gradient(180deg, rgba(74,97,156,.5), rgba(87,112,178,.42));
    border-color:rgba(141,165,241,.65);
    color:#f6f8ff;
    font-weight:800;
  }
  @media (max-width: 820px){
    .nibiru-tool-body{padding-top:110px !important;}
    .nibiru-topnav{padding:12px 14px;}
    .nibiru-topnav__brand{width:100%;}
  }
</style>
"""


def inject_nibiru_navbar(html: str, active_page: str) -> str:
    if not html or "<body" not in html.lower():
        return html

    nav_links = [
        ("dashboard", "📊 Dashboard", url_for("dashboard")),
        ("jobs", "📄 Jobs", url_for("jobs_page")),
        ("spamhaus", "🛡️ Spamhaus", url_for("spamhaus_page")),
        ("infra", "🏗️ Infra", url_for("infra_page")),
        ("extractor", "📬 Extractor", url_for("extractor_page")),
        ("campaigns", "📌 Campaigns", url_for("campaigns_page")),
        ("send", "✉️ Send", url_for("send_page", new="1")),
        ("tracker", "🧭 Tracker", url_for("tracker_page")),
        ("accounting", "🧾 Accounting", url_for("accounting_page")),
    ]
    nav_markup = [
        '<nav class="nibiru-topnav" aria-label="Nibiru navigation">',
        f'<a class="nibiru-topnav__brand" href="{url_for("dashboard")}"><img src="{url_for("image_asset", filename="shiva.png")}" alt="Shiva logo"><span>Nibiru</span></a>',
        '<div class="nibiru-topnav__links">',
    ]
    for key, label, href in nav_links:
        active_class = " active" if key == active_page else ""
        nav_markup.append(f'<a class="{active_class.strip()}" href="{href}">{label}</a>' if active_class else f'<a href="{href}">{label}</a>')
    nav_markup.append('</div></nav>')
    nav_html = "".join(nav_markup)

    updated = re.sub(r"<body([^>]*)>", rf'<body\1 class="nibiru-tool-body">{nav_html}', html, count=1, flags=re.IGNORECASE)
    if updated == html:
        return html
    if "</head>" in updated.lower():
        updated = re.sub(r"</head>", TOOL_NAV_CSS + "</head>", updated, count=1, flags=re.IGNORECASE)
    else:
        updated = TOOL_NAV_CSS + updated
    return updated


def render_tool_page(html: str, active_page: str) -> Response:
    return Response(inject_nibiru_navbar(html, active_page), mimetype="text/html")


@app.route("/img/<path:filename>")
def image_asset(filename: str):
    return send_from_directory(Path(app.root_path) / "img", filename)

JOBS_PAGE_HTML = r"""<html lang="en"><head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Jobs</title>
  <style>
    :root{
      --bg:#081120;
      --bg2:#0b1730;
      --card: rgba(255,255,255,.08);
      --card2: rgba(255,255,255,.05);
      --border: rgba(145,164,201,.18);
      --text:#e6edf7;
      --muted:#9ca9c4;
      --accent:#7394e6;
      --accent-strong:#8ea9f4;
      --good:#35e49a;
      --bad:#ff5e73;
      --warn:#ffc14d;
      --shadow: 0 20px 55px rgba(0,0,0,.35);
      --radius: 20px;
    }
    *{box-sizing:border-box}
    body{
      font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
      margin:0;
      background:
        radial-gradient(circle at top left, rgba(115,148,230,.14), transparent 34%),
        linear-gradient(180deg, var(--bg) 0%, var(--bg2) 100%);
      color: var(--text);
      min-height:100vh;
    }
    a{color:var(--accent); text-decoration:none}

    .content{padding:28px 18px 28px}
    .wrap{max-width: 1200px; margin: 0 auto;}

    .top{display:flex; gap:12px; flex-wrap:wrap; align-items:flex-start; justify-content:space-between; margin-bottom:12px;}
    h2{margin:0; font-size: 20px;}
    .sub{margin-top:6px; color:var(--muted); font-size:12px; line-height:1.6; max-width: 760px;}

    .nav{display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:8px}
    .nav form{display:inline; margin:0;}

    .btn{
      border:1px solid rgba(255,255,255,.14);
      background: rgba(122,167,255,.14);
      color: rgba(255,255,255,.92);
      padding:10px 12px;
      border-radius: 14px;
      cursor:pointer;
      font: inherit;
      font-weight: 800;
      display:inline-flex;
      align-items:center;
      gap:8px;
      text-decoration:none;
    }
    .btn:hover{filter:brightness(1.06)}
    .btn.secondary{background: rgba(255,255,255,.06); font-weight:700;}
    .btn.danger{background: rgba(255,94,115,.14);}
    .btn:disabled{opacity:.55; cursor:not-allowed;}

    .job{
      background: linear-gradient(180deg, var(--card), var(--card2));
      border:1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 14px;
      margin-bottom: 12px;
      backdrop-filter: blur(10px);
    }

    .filterToggleBtn{
      position: fixed;
      top: 86px;
      right: 14px;
      z-index: 45;
      border-radius: 999px;
      padding: 11px 12px;
      box-shadow: var(--shadow);
      background: rgba(10,16,34,.95);
      border: 1px solid rgba(255,255,255,.24);
      transition: opacity .2s ease;
    }
    body.filterMenuOpen .filterToggleBtn{ opacity:.92; }

    .filterDrawerBackdrop{
      position: fixed;
      inset: 0;
      background: rgba(3,7,20,.58);
      backdrop-filter: blur(2px);
      z-index: 46;
      opacity: 0;
      pointer-events: none;
      transition: opacity .22s ease;
    }
    .filterDrawer{
      position: fixed;
      top: 0;
      right: 0;
      width: min(380px, 94vw);
      height: 100vh;
      overflow-y: auto;
      z-index: 47;
      transform: translateX(102%);
      transition: transform .24s ease;
      padding: 74px 14px 16px;
      background: linear-gradient(180deg, rgba(10,16,34,.96), rgba(8,13,28,.98));
      border-left: 1px solid var(--border);
      box-shadow: -14px 0 42px rgba(0,0,0,.36);
    }
    body.filterMenuOpen .filterDrawerBackdrop{opacity:1; pointer-events:auto;}
    body.filterMenuOpen .filterDrawer{transform: translateX(0);}

    .filterBar{
      background: linear-gradient(180deg, var(--card), var(--card2));
      border:1px solid var(--border);
      border-radius: 14px;
      padding: 10px 12px;
      margin-bottom: 6px;
      display:grid;
      grid-template-columns: 1fr;
      gap:8px;
      align-items:end;
    }
    .filterCell label{
      display:block;
      font-size:11px;
      color:var(--muted);
      margin-bottom:5px;
      font-weight:700;
      text-transform:uppercase;
      letter-spacing:.3px;
    }
    .filterCell select{
      width:100%;
      border:1px solid rgba(255,255,255,.16);
      background: rgba(255,255,255,.06);
      color: rgba(255,255,255,.9);
      border-radius:10px;
      font: inherit;
      font-size:13px;
      padding:8px 9px;
    }
    .filterCell option{ background:#0b1020; color:#fff; }
    .filterMeta{ grid-column:1 / -1; font-size:12px; color:var(--muted); margin-top:2px; }

    .jobTop{display:flex; gap:12px; flex-wrap:wrap; align-items:flex-start; justify-content:space-between;}
    .titleRow{display:flex; gap:10px; flex-wrap:wrap; align-items:center}
    .mini{color:var(--muted); font-size:12px; line-height:1.55}
    code{background:rgba(255,255,255,.08); padding:2px 6px; border-radius:8px;}

    .pill{padding:6px 10px; border-radius:999px; border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.06); font-size:12px;}
    .pill.good{border-color: rgba(53,228,154,.35); color: var(--good); font-weight:900}
    .pill.bad{border-color: rgba(255,94,115,.35); color: var(--bad); font-weight:900}
    .pill.warn{border-color: rgba(255,193,77,.35); color: var(--warn); font-weight:900}

    .triageRow{display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin-top:8px; max-width:100%;}
    .triageBadge{
      display:inline-flex;
      align-items:center;
      gap:6px;
      max-width:100%;
      border:1px solid rgba(255,255,255,.14);
      background:rgba(255,255,255,.06);
      border-radius:999px;
      padding:4px 9px;
      font-size:11px;
      font-weight:800;
      line-height:1.2;
      color:rgba(255,255,255,.88);
      white-space:nowrap;
      overflow:visible;
      min-width:0;
    }
    .triageBadge .badgeLabel{
      min-width:0;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }
    .triageBadge.good{border-color: rgba(53,228,154,.35); color: var(--good);}
    .triageBadge.warn{border-color: rgba(255,193,77,.35); color: var(--warn);}
    .triageBadge.bad{border-color: rgba(255,94,115,.35); color: var(--bad);}
    .bridgeConnBadge{gap:7px;}
    .statusDot{
      width:9px;
      height:9px;
      border-radius:50%;
      display:inline-block;
      box-shadow:0 0 0 2px rgba(255,255,255,.12);
      flex:0 0 auto;
    }
    .statusDot.good{background: var(--good);}
    .statusDot.bad{background: var(--bad);}

    .kpiWrap{margin-top:12px; border:1px solid rgba(255,255,255,.10); background: rgba(0,0,0,.10); border-radius: 14px; padding: 10px 12px;}
    .kpiRow{display:grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap:8px;}
    .kpiCell{border:1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.03); border-radius:10px; padding:7px 9px;}
    .kpiCell .k{font-size:11px; color: rgba(255,255,255,.62); text-transform:uppercase; letter-spacing:.3px;}
    .kpiCell .v{font-size:16px; font-weight:900; margin-top:2px; display:flex; align-items:center; gap:6px;}
    .kpiCell.kpi-del .k, .kpiCell.kpi-del .v{color:var(--good);}
    .kpiCell.kpi-bnc .k, .kpiCell.kpi-bnc .v{color:var(--bad);}
    .kpiCell.kpi-def .k, .kpiCell.kpi-def .v{color:var(--warn);}
    .kpiCell.kpi-cmp .k, .kpiCell.kpi-cmp .v{color:#ff8bd6;}
    .kpiCell.kpi-sent .k, .kpiCell.kpi-sent .v{color:#fff;}
    .kpiWarn{font-size:12px; color:var(--warn); cursor:help;}
    .ratesRow{display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:8px; margin-top:8px;}
    .rateCell{border:1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.02); border-radius:10px; padding:6px 9px;}
    .rateCell .k{font-size:11px; color: rgba(255,255,255,.62); text-transform:uppercase; letter-spacing:.3px;}
    .rateCell .v{font-size:13px; font-weight:800; margin-top:2px;}
    .qualityMini{margin-top:8px;}
    .qualityMini summary{cursor:pointer; color:rgba(255,255,255,.78); font-size:12px; user-select:none;}
    .qualityLine{margin-top:6px; font-size:12px; color:rgba(255,255,255,.72);}
    @media (max-width: 980px){ .kpiRow{grid-template-columns: repeat(3, minmax(0,1fr));} }
    @media (max-width: 620px){ .kpiRow{grid-template-columns: repeat(2, minmax(0,1fr));} .ratesRow{grid-template-columns: 1fr;} }

    .bars{display:grid; grid-template-columns: 1fr; gap:10px; margin-top: 12px;}
    .barWrap{display:flex; gap:10px; flex-wrap:wrap; align-items:center; justify-content:space-between;}
    .bar{height: 10px; background: rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.14); border-radius:999px; overflow:hidden; width:100%;}
    .bar > div{height:100%; width:0%; background: rgba(122,167,255,.65);} 

    .twoCol{display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-top:12px;}
    @media (max-width: 980px){ .twoCol{grid-template-columns: 1fr;} }
    .panel{border:1px solid rgba(255,255,255,.10); background: rgba(0,0,0,.10); border-radius: 14px; padding: 10px 12px;}
    .panel h4{margin:0 0 8px; font-size: 13px; color: rgba(255,255,255,.86)}

    .quickIssues{margin-top:10px; font-size:12px; color:var(--warn);}
    .quickIssues:empty{display:none;}
    .more{margin-top:10px;}
    .more > summary{cursor:pointer; user-select:none; font-weight:800; color:rgba(255,255,255,.88);}
    .moreBlock{margin-top:10px;}
    .errorFold{margin-top:12px; margin-left:10px;}
    .errorFold summary{cursor:pointer; color:rgba(255,255,255,.75); font-size:12px;}
    .errorSummaryBox{
      margin-top:8px;
      border:1px solid rgba(255,94,115,.45);
      background: rgba(90,18,32,.36);
      border-radius:10px;
      padding:9px 10px;
      color: rgba(255,206,214,.95);
    }
    .errorSummaryBox:empty{display:none;}
    .sopHeader{
      display:flex;
      align-items:center;
      gap:8px;
      margin:0 0 10px;
      color:rgba(255,255,255,.95);
      font-weight:900;
      letter-spacing:.2px;
      font-size:14px;
    }
    .sopBlock{margin-top:12px; padding:10px; border:1px solid rgba(255,255,255,.1); border-radius:10px; background:rgba(255,255,255,.02);}
    .sopBlock:first-of-type{margin-top:6px;}
    .sopLabel{font-size:12px; font-weight:900; margin-bottom:6px; letter-spacing:.2px;}
    .sopLabel.system{color:#9fd0ff;}
    .sopLabel.provider{color:#c8f5b1;}
    .sopLabel.integrity{color:#ffd9a8;}
    .sopLine{font-size:13px; line-height:1.5; color:rgba(255,255,255,.88);}
    .legacyDiagnosticsBox{
      margin-top:14px;
      padding:12px;
      border:1px solid rgba(255,255,255,.14);
      border-radius:12px;
      background:linear-gradient(180deg, rgba(122,167,255,.12), rgba(122,167,255,.03));
    }
    .legacyDiagnosticsTitle{
      margin:0;
      font-size:13px;
      font-weight:900;
      color:#d5e4ff;
      display:flex;
      align-items:center;
      gap:8px;
    }
    .legacySectionLabel{
      margin-top:10px;
      font-size:11px;
      text-transform:uppercase;
      letter-spacing:.3px;
      color:rgba(213,228,255,.84);
      font-weight:800;
    }
    .legacyDataLine{
      margin-top:6px;
      padding:8px 10px;
      border:1px solid rgba(255,255,255,.12);
      border-radius:10px;
      background:rgba(0,0,0,.16);
      color:rgba(255,255,255,.9);
      overflow-wrap:anywhere;
    }
    .bridgeSnapshotBox{
      margin-top:12px;
      padding:10px 12px;
      border:1px solid rgba(64,225,173,.35);
      border-radius:10px;
      background:rgba(13,67,51,.26);
      color:#c8ffed;
    }
    .debugTerminal{
      margin-top:10px;
      border:1px solid rgba(255,94,115,.62);
      border-radius:12px;
      background:linear-gradient(180deg, rgba(60,9,18,.94), rgba(30,5,10,.98));
      box-shadow: inset 0 0 0 1px rgba(255,138,156,.18), 0 14px 32px rgba(0,0,0,.42);
      overflow:hidden;
    }
    .debugTerminalHead{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      padding:8px 10px;
      border-bottom:1px solid rgba(255,122,143,.35);
      background:rgba(255,94,115,.14);
      color:#ffd8df;
      font-size:12px;
      font-weight:900;
      letter-spacing:.2px;
    }
    .debugTerminalHead .muted{color:rgba(255,220,228,.85);}
    .debugTerminalBody{
      max-height:220px;
      overflow:auto;
      padding:10px 11px;
      font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      color:#ffd8de;
      white-space:pre-wrap;
      word-break:break-word;
    }
    .debugTerminalBody .line{display:block; margin-top:2px;}
    .debugTerminalBody .line:first-child{margin-top:0;}

    /* PMTA Live Panel (Jobs) — clearer layout */
    .pmtaLive{ margin-top:10px; }
    .pmtaCompact{
      margin-top:10px;
      font-size:12px;
      color:rgba(255,255,255,.86);
      border:1px solid rgba(255,255,255,.14);
      background:rgba(0,0,0,.14);
      border-radius:10px;
      padding:8px 10px;
      font-weight:800;
      line-height:1.45;
      overflow-wrap:anywhere;
    }
    .pmtaToggle{ margin-top:8px; }
    .pmtaToggle > summary{ cursor:pointer; user-select:none; color:rgba(255,255,255,.88); font-weight:800; }
    .pmtaGrid{ display:grid; grid-template-columns: repeat(7, minmax(0,1fr)); gap:10px; }
    @media (max-width: 1150px){ .pmtaGrid{ grid-template-columns: repeat(4, minmax(0,1fr)); } }
    @media (max-width: 820px){ .pmtaGrid{ grid-template-columns: repeat(2, minmax(0,1fr)); } }

    .pmtaBox{
      border:1px solid rgba(255,255,255,.12);
      background: rgba(0,0,0,.14);
      border-radius: 14px;
      padding: 10px 12px;
      min-height: 74px;
    }
    .pmtaTitle{
      font-size: 11px;
      letter-spacing: .6px;
      text-transform: uppercase;
      color: rgba(255,255,255,.60);
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:10px;
      margin-bottom: 8px;
      user-select:none;
    }
    .pmtaTitle .tag{font-size:11px; padding:2px 8px; border-radius:999px; border:1px solid rgba(255,255,255,.14); background: rgba(255,255,255,.06);}
    .pmtaTitle .tag.good{ border-color: rgba(53,228,154,.35); color: var(--good); font-weight:900; }
    .pmtaTitle .tag.warn{ border-color: rgba(255,193,77,.35); color: var(--warn); font-weight:900; }
    .pmtaTitle .tag.bad{ border-color: rgba(255,94,115,.35); color: var(--bad); font-weight:900; }

    .pmtaRow{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin-top:6px; }
    .pmtaKey{ font-size: 11px; color: rgba(255,255,255,.60); letter-spacing:.4px; text-transform:uppercase; }
    .pmtaVal{
      font-size: 16px;
      font-weight: 950;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      color: rgba(255,255,255,.92);
    }
    .pmtaVal.good{ color: var(--good); }
    .pmtaVal.warn{ color: var(--warn); }
    .pmtaVal.bad{ color: var(--bad); }
    .pmtaBig{ font-size: 22px; font-weight: 1000; letter-spacing: .2px; }
    .pmtaSub{ margin-top:8px; font-size: 11px; color: rgba(255,255,255,.60); line-height: 1.35; word-break: break-word; overflow-wrap:anywhere; }
    .pmtaHint{ margin-top:6px; font-size: 11px; color: rgba(255,255,255,.52); line-height: 1.35; }

    .chunkMeta{
      display:flex;
      flex-wrap:wrap;
      gap:6px;
      margin-top:8px;
      padding:8px;
      border:1px solid rgba(122,167,255,.28);
      border-radius:11px;
      background:linear-gradient(135deg, rgba(122,167,255,.14), rgba(53,228,154,.08));
    }
    .chunkMetaPill{
      display:inline-flex;
      align-items:center;
      gap:6px;
      padding:4px 9px;
      border-radius:999px;
      border:1px solid rgba(255,255,255,.2);
      background:rgba(8,14,34,.48);
      font-size:11px;
      color:rgba(255,255,255,.92);
      font-weight:800;
      line-height:1.2;
    }
    .chunkList{display:grid; gap:7px; margin-top:10px;}
    .chunkItem{display:flex; align-items:flex-start; gap:8px; padding:7px 9px; border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.03); border-radius:10px;}
    .chunkIcon{font-size:13px; line-height:1.2; margin-top:1px;}
    .chunkLabel{font-size:11px; color:rgba(255,255,255,.62); text-transform:uppercase; letter-spacing:.35px;}
    .chunkValue{font-size:12px; color:rgba(255,255,255,.92); font-weight:800; line-height:1.35; overflow-wrap:anywhere;}
    .chunkValue.warn{color:var(--warn);}
    .chunkValue.bad{color:var(--bad);}
    .chunkValue.good{color:var(--good);}
    .chunkNote{margin-top:8px; padding:8px 10px; border-radius:10px; border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.03);}
    .chunkNoteAdaptive{border-color:rgba(53,228,154,.32); background:rgba(53,228,154,.08);}
    .chunkNoteDomains{margin-top:10px; border-color:rgba(255,152,65,.38); background:rgba(255,152,65,.09);}

    .pmtaBanner{
      border:1px solid rgba(255,255,255,.14);
      border-radius: 14px;
      padding: 10px 12px;
      background: rgba(0,0,0,.16);
      color: rgba(255,255,255,.90);
      font-weight: 800;
      line-height: 1.5;
    }
    .pmtaBanner.good{ border-color: rgba(53,228,154,.35); }
    .pmtaBanner.warn{ border-color: rgba(255,193,77,.35); }
    .pmtaBanner.bad{ border-color: rgba(255,94,115,.35); }

    details.more{margin-top:10px;}
    details.more summary{cursor:pointer; color: rgba(255,255,255,.86); font-weight:900;}

    .moreGrid{display:grid; grid-template-columns: 1.1fr .9fr; gap:10px; margin-top:10px;}
    @media (max-width: 980px){ .moreGrid{grid-template-columns: 1fr;} }

    .smallBar{height:8px; border-radius:999px; background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.12); overflow:hidden}
    .smallBar > div{height:100%; width:0%; background: rgba(53,228,154,.55);} 

    .outcomesWrap{
      margin-top:8px;
      padding:10px;
      border:1px solid rgba(255,255,255,.10);
      border-radius:12px;
      background: rgba(255,255,255,.03);
    }
    .outcomesGrid{
      display:grid;
      grid-template-columns: repeat(2, minmax(0,1fr));
      gap:8px;
    }
    .outChip{
      border:1px solid rgba(255,255,255,.10);
      border-radius:10px;
      padding:8px 10px;
      background: rgba(0,0,0,.16);
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:8px;
    }
    .outChip .k{font-size:11px; letter-spacing:.5px; text-transform:uppercase; color:rgba(255,255,255,.62);}
    .outChip .v{font-weight:900; font-size:15px;}
    .outChip.del .v{color: var(--good);}
    .outChip.bnc .v{color: var(--bad);}
    .outChip.def .v{color: var(--warn);}
    .outChip.cmp .v{color: #ff8bd6;}
    .outTrend{
      margin-top:10px;
      padding:10px;
      border:1px dashed rgba(255,255,255,.14);
      border-radius:10px;
      background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.01));
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size:12px;
      line-height:1.5;
      color: rgba(255,255,255,.84);
      overflow-wrap:anywhere;
      word-break:break-word;
    }
    .trendHead{ color: rgba(255,255,255,.66); margin-right:8px; font-weight:800; }
    .trendSeg{ display:inline-flex; align-items:center; gap:6px; margin:2px 8px 2px 0; }
    .trendSeg .lbl{ font-weight:900; letter-spacing:.5px; }
    .trendSeg .spark{ font-size:13px; }
    .trendSeg.del .lbl, .trendSeg.del .spark{ color: var(--good); }
    .trendSeg.bnc .lbl, .trendSeg.bnc .spark{ color: var(--bad); }
    .trendSeg.def .lbl, .trendSeg.def .spark{ color: var(--warn); }
    .trendSeg.cmp .lbl, .trendSeg.cmp .spark{ color: #ff8bd6; }
    .outMeta{ margin-top:8px; font-size:11px; color:rgba(255,255,255,.62); }
    @media (max-width: 560px){ .outcomesGrid{ grid-template-columns: 1fr; } }
    @media (max-width: 920px){ .content{padding:18px 14px 24px} }

    table{width:100%; border-collapse:collapse; font-size: 12px;}
    th,td{padding:8px; border-bottom:1px solid rgba(255,255,255,.10); text-align:left; vertical-align:top}

    .ok{color:var(--good); font-weight:900}
    .no{color:var(--bad); font-weight:900}

    /* Toast */
    .toast-wrap{ position: fixed; right: 16px; bottom: 16px; z-index: 9999; display:flex; flex-direction:column; gap:10px; }
    .toast{
      min-width: 280px;
      max-width: 460px;
      background: rgba(0,0,0,.55);
      border: 1px solid rgba(255,255,255,.18);
      box-shadow: 0 18px 55px rgba(0,0,0,.35);
      backdrop-filter: blur(10px);
      border-radius: 14px;
      padding: 12px 14px;
      color: rgba(255,255,255,.92);
      font-size: 13px;
      line-height: 1.5;
      animation: pop .18s ease-out;
    }
    @keyframes pop{ from{ transform: translateY(6px); opacity: .2; } to{ transform: translateY(0); opacity: 1; } }
    .toast .t{font-weight:900; margin-bottom:4px}
    .toast.good{ border-color: rgba(53,228,154,.35); }
    .toast.bad{ border-color: rgba(255,94,115,.35); }
    .toast.warn{ border-color: rgba(255,193,77,.35); }

    .labelTip{ display:inline-flex; align-items:center; gap:6px; }
    .tip{display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:999px;
      border:1px solid rgba(255,255,255,.18); background: rgba(0,0,0,.18); color: rgba(255,255,255,.86);
      font-size: 12px; cursor: help; position: relative; user-select:none}
    .triageBadge .tip{ width:14px; height:14px; font-size:10px; }
    .tip:hover::after{
      content: attr(data-tip);
      position: absolute;
      left: 0;
      top: 24px;
      min-width: 240px;
      max-width: 420px;
      background: rgba(0,0,0,.72);
      border: 1px solid rgba(255,255,255,.18);
      box-shadow: 0 18px 55px rgba(0,0,0,.35);
      backdrop-filter: blur(10px);
      color: rgba(255,255,255,.92);
      padding: 10px 12px;
      border-radius: 14px;
      z-index: 999;
      white-space: normal;
    }
  </style>
</head>
<body>
  <main class="content">
    <div class="wrap">

    <div class="top">
      <div>
        <h2>Jobs</h2>
        <div class="sub">
          Live monitoring: summary, current chunk, backoff, progress bars, top domains, counters, error histogram, and chunk preflight history. This page keeps the full `jobs.html` CSS/layout while now using the same shared top navigation layout as the other demo surfaces.
        </div>
      </div>
    </div>

    <div class="job" id="jobsDiagnostics">
      <div style="font-weight:800; margin-bottom:6px">Operational diagnostics</div>
      <div class="mini" id="jobsDiagnosticsSummary">Loading diagnostics…</div>
      <div class="mini" id="jobsDiagnosticsList" style="margin-top:6px"></div>
    </div>

    <button class="btn secondary filterToggleBtn" type="button" id="btnToggleFilters">🎛️</button>
    <div class="filterDrawerBackdrop" id="jobsFilterBackdrop"></div>
    <aside class="filterDrawer" id="jobsFilterDrawer" aria-hidden="true">
      <div class="filterBar" id="jobsFilterBar">
        <div class="filterCell">
          <label for="fltStatus" class="labelTip">Status <span class="tip" data-tip="Filter jobs by current execution state (running/done/paused/backoff/stop).">ⓘ</span></label>
          <select id="fltStatus">
            <option value="all">All</option>
            <option value="running">running</option>
            <option value="done">done</option>
            <option value="paused">paused</option>
            <option value="backoff">backoff</option>
            <option value="stop">stopped</option>
          </select>
        </div>
        <div class="filterCell">
          <label for="fltMode" class="labelTip">Mode <span class="tip" data-tip="Show jobs by bridge polling mode: counts or legacy.">ⓘ</span></label>
          <select id="fltMode">
            <option value="all">All</option>
            <option value="counts">counts</option>
            <option value="legacy">legacy</option>
          </select>
        </div>
        <div class="filterCell">
          <label for="fltRisk" class="labelTip">Risk <span class="tip" data-tip="Highlight jobs with health/risk signals such as stale updates or degraded internals.">ⓘ</span></label>
          <select id="fltRisk">
            <option value="all">All</option>
            <option value="internal_degraded">internal degraded</option>
            <option value="deliverability_high">deliverability high</option>
            <option value="stale">stale</option>
          </select>
        </div>
        <div class="filterCell">
          <label for="fltProvider" class="labelTip">Provider <span class="tip" data-tip="Filter by recipient provider bucket (gmail/yahoo/outlook/icloud/other).">ⓘ</span></label>
          <select id="fltProvider">
            <option value="all">All</option>
            <option value="gmail">gmail</option>
            <option value="yahoo">yahoo</option>
            <option value="outlook">outlook</option>
            <option value="icloud">icloud</option>
            <option value="other">other</option>
          </select>
        </div>
        <div class="filterCell">
          <label for="fltSort" class="labelTip">Sort <span class="tip" data-tip="Control card order: newest first, highest risk first, or stalest first.">ⓘ</span></label>
          <select id="fltSort">
            <option value="newest">newest first</option>
            <option value="highest_risk">highest risk first</option>
            <option value="stalest">stalest first</option>
          </select>
        </div>
        <div class="filterMeta" id="filterMeta">Showing all 1 job.</div>
      </div>
    </aside>

    
      
    

    <div class="job" id="jobsFilteredEmpty" style="">
      <div class="mini">No jobs match the selected filters.</div>
    </div>

    <div class="job" id="jobsListEmpty" style="">
      <div class="mini">No jobs yet.</div>
    </div>

  <div class="job" data-jobid="{{ send_preview.job_id|e }}" data-created="{{ send_preview.created_at|e }}">
        <div class="jobTop">
          <div>
            <div class="titleRow">
              <div style="font-weight:900">Campaign <code>{{ send_preview.campaign_id|e }}</code>{% if send_preview.campaign_name %} · {{ send_preview.campaign_name|e }}{% endif %}</div>
              <div class="pill" data-k="status">Status: {{ send_preview.status|e }}</div>
              <div class="pill" data-k="speed">0 epm</div>
              <div class="pill" data-k="eta">ETA —</div>
            </div>
            <div class="triageRow">
              <div class="triageBadge" data-k="badgeMode"><span class="badgeLabel">—</span><span class="tip" data-tip="Bridge mode not available yet for this job.">ⓘ</span></div>
              <div class="triageBadge" data-k="badgeFreshness"><span class="badgeLabel">—</span><span class="tip" data-tip="Freshness signal: how recent accounting or legacy ingestion updates are for this job.">ⓘ</span></div>
              <div class="triageBadge good" data-k="badgeHealth"><span class="badgeLabel">OK (0)</span><span class="tip" data-tip="Internal health checks are clean (no bridge/runtime failure counters).">ⓘ</span></div>
              <div class="triageBadge" data-k="badgeRisk"><span class="badgeLabel">RISK —</span><span class="tip" data-tip="Deliverability risk derived from bounce, complaint, and deferred rates.">ⓘ</span></div>
              <div class="triageBadge bridgeConnBadge good" data-k="badgeBridgeConn" title="Bridge↔Shiva connected"><span class="statusDot good" aria-hidden="true"></span><span>Bridge↔Shiva connected</span><span class="tip" data-tip="Real-time bridge transport status between PMTA accounting bridge and Shiva receiver. Current endpoint is not available yet.">ⓘ</span></div>
              <div class="triageBadge" data-k="badgeIntegrity" style=""><span class="badgeLabel">INTEGRITY</span><span class="tip" data-tip="Data integrity counters are clean.">ⓘ</span></div>
            </div>
            <div class="mini">Created: <span class="muted">{{ send_preview.created_at|e }}</span></div>
            <div class="mini" data-k="alerts">Current send: {{ send_preview.from_email|e }} via {{ send_preview.smtp_host|e }}</div>
          </div>

          <div class="nav" style="margin-top:0">
            <a class="btn secondary" href="/jobs">Open</a>
            <button class="btn secondary" type="button" data-action="pause" disabled="">⏸ Pause</button>
            <button class="btn secondary" type="button" data-action="resume" disabled="">▶ Resume</button>
            <button class="btn danger" type="button" data-action="stop" disabled="">⛔ Stop</button>
            <button class="btn danger" type="button" data-action="delete">🗑 Delete</button>
          </div>
        </div>

        <!-- 1) Compact KPI + rates -->
        <div class="kpiWrap">
          <div class="kpiRow">
            <div class="kpiCell kpi-sent"><div class="k">Sent</div><div class="v"><span data-k="sent">0</span></div></div>
            <div class="kpiCell"><div class="k">Pending</div><div class="v"><span data-k="pending">0</span><span class="kpiWarn" data-k="pendingWarn" style="" title="Pending was clamped to 0 because Sent is lower than PMTA outcomes.">⚠</span></div></div>
            <div class="kpiCell kpi-del"><div class="k">Del</div><div class="v"><span data-k="delivered">0</span></div></div>
            <div class="kpiCell kpi-bnc"><div class="k">Bnc</div><div class="v"><span data-k="bounced">0</span></div></div>
            <div class="kpiCell kpi-def"><div class="k">Def</div><div class="v"><span data-k="deferred">0</span></div></div>
            <div class="kpiCell kpi-cmp"><div class="k">Cmp</div><div class="v"><span data-k="complained">0</span></div></div>
          </div>
          <div class="ratesRow">
            <div class="rateCell"><div class="k">Bounce %</div><div class="v" data-k="rateBounce">—</div></div>
            <div class="rateCell"><div class="k">Complaint %</div><div class="v" data-k="rateComplaint">—</div></div>
            <div class="rateCell"><div class="k">Deferred %</div><div class="v" data-k="rateDeferred">—</div></div>
          </div>

          <div class="panel" style="margin-top:10px;">
            <h4>PMTA Live Panel</h4>
            <div class="pmtaLive" data-k="pmtaLine">
        <div class="pmtaGrid">
          <div class="pmtaBox"><div class="pmtaTitle"><span>Spool</span><span class="tag good">rcpt</span></div><div class="pmtaHint">Total recipients/messages currently held by PMTA spool.</div><div class="pmtaRow"><span class="pmtaKey">RCPT</span><span class="pmtaVal good pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">MSG</span><span class="pmtaVal good">—</span></div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Queue</span><span class="tag good">rcpt</span></div><div class="pmtaHint">Recipients/messages still queued to be delivered.</div><div class="pmtaRow"><span class="pmtaKey">RCPT</span><span class="pmtaVal good pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">MSG</span><span class="pmtaVal good">—</span></div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Connections</span></div><div class="pmtaHint">Live SMTP sessions used for inbound/outbound traffic.</div><div class="pmtaRow"><span class="pmtaKey">SMTP In</span><span class="pmtaVal good pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">SMTP Out</span><span class="pmtaVal good pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">Total</span><span class="pmtaVal good">—</span></div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Last minute</span></div><div class="pmtaHint">Recent PMTA throughput over the last 60 seconds.</div><div class="pmtaRow"><span class="pmtaKey">In</span><span class="pmtaVal warn pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">Out</span><span class="pmtaVal warn pmtaBig">—</span></div><div class="pmtaSub">traffic recipients / minute</div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Last hour</span></div><div class="pmtaHint">Rolling traffic totals for the previous 60 minutes.</div><div class="pmtaRow"><span class="pmtaKey">In</span><span class="pmtaVal warn pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">Out</span><span class="pmtaVal warn pmtaBig">—</span></div><div class="pmtaSub">traffic recipients / hour</div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Top queues</span></div><div class="pmtaHint">Queues with the highest recipient backlog and latest queue errors.</div><div class="pmtaSub">0=0</div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Time</span></div><div class="pmtaHint">Timestamp of the latest PMTA snapshot used for this panel.</div><div class="pmtaSub">2026-03-22T10:19:41Z</div></div>
        </div>
      </div>
            <div class="mini" style="margin-top:6px" data-k="pmtaNote">Note: <b>sent</b> = accepted by PMTA (client-side). Delivery may still be queued/deferred.</div>
            <div class="chunkMeta" style="margin-top:6px" data-k="pmtaDiag"><span class="chunkMetaPill">Diag: —</span></div>
            <div class="mini" style="margin-top:8px"><b>Error summary</b></div>
            <div class="mini errorSummaryBox" data-k="pmtaErrorSummary" style="display: none;"></div>
          </div>

          <details class="qualityMini">
            <summary>Quality</summary>
            <div class="qualityLine">Final-fail: <span data-k="failed">0</span> · Skipped: <span data-k="skipped">0</span> · Invalid: <span data-k="invalid">0</span> · Total: <span data-k="total">1</span></div>
          </details>
        </div>

        <!-- 4) Progress bars -->
        <div class="bars">
          <div class="panel">
            <h4>Progress</h4>
            <div class="mini" data-k="progressText">Send progress: 0% (0/1)</div>
            <div class="bar"><div data-k="barSend" style="width: 0%;"></div></div>
            <div class="mini" style="margin-top:8px" data-k="chunksText">Chunks: 1/1 done · backoff_events=0 · abandoned=1</div>
            <div class="mini" data-k="attemptsText" style="">—</div>
            <div class="bar"><div data-k="barChunks" style="width: 100%;"></div></div>
            <div class="mini" style="margin-top:8px" data-k="domainsText">Domains: 0% (0/1)</div>
            <div class="bar"><div data-k="barDomains" style="width: 0%;"></div></div>
          </div>
        </div>

        <div class="quickIssues" data-k="quickIssues">Quick issues: ❌ abandoned chunks</div>

        <details class="more" open="">
          <summary>More details</summary>
          <div class="moreBlock twoCol">
            <!-- 2) Current chunk + 3) backoff info -->
            <div class="panel">
              <h4>Current chunk</h4>
              <div class="mini">Current send settings + top active domains in this running chunk.</div>
              <div class="mini" data-k="chunkLine"><div class="mini">Subject: {{ send_preview.subject|e }} · From: {{ send_preview.from_email|e }}</div></div>
              <div class="mini" data-k="chunkDomains"><div class="mini chunkNote chunkNoteDomains">🔥 Top active domains: {{ send_preview.top_domains|e }}</div></div>
            </div>
            <div class="panel">
              <h4>Backoff</h4>
              <div class="mini">Latest retry event when PMTA/provider pressure slows delivery.</div>
              <div class="mini" data-k="backoffLine">—</div>
            </div>
          </div>

          <div class="panel moreBlock">
            <h4>Outcomes (PMTA accounting)</h4>
            <div class="outcomesWrap" data-k="outcomes">
        <div class="outcomesGrid">
          <div class="outChip del"><span class="k">Delivered</span><span class="v">0</span></div>
          <div class="outChip bnc"><span class="k">Bounced</span><span class="v">0</span></div>
          <div class="outChip def"><span class="k">Deferred</span><span class="v">0</span></div>
          <div class="outChip cmp"><span class="k">Complained</span><span class="v">0</span></div>
        </div>
        <div class="outMeta">Pending (sent - final outcomes): <b>0</b> · PMTA queue now: <b>0</b></div>
        <div class="outMeta">Last accounting update: —</div>
      </div>
            <div class="outTrend" data-k="outcomeTrend">Trend · —</div>
          </div>

          <div class="panel moreBlock">
            <h4>Logs</h4>
            <div class="mini" data-k="jobLogs">—</div>
          </div>

          <div class="moreGrid moreBlock">

            <!-- 5) Top domains -->
            <div class="panel">
              <h4 data-k="domainsPanelTitle">Top providers</h4>
              <div class="mini" data-k="topDomains">Current send domains: <b>{{ send_preview.top_domains|e }}</b> · Total recipients: <b>{{ send_preview.total_recipients }}</b></div>
              <div class="mini" style="margin-top: 10px; display: none;"><b>Domain progress (bars)</b></div>
              <div data-k="topDomainsBars"><div style="margin-top:10px"><div class="mini"><b>Gmail</b> · 0</div><div class="smallBar"><div style="width:0%"></div></div></div><div style="margin-top:10px"><div class="mini"><b>Yahoo</b> · 0</div><div class="smallBar"><div style="width:0%"></div></div></div><div style="margin-top:10px"><div class="mini"><b>Outlook</b> · 0</div><div class="smallBar"><div style="width:0%"></div></div></div><div style="margin-top:10px"><div class="mini"><b>iCloud</b> · 0</div><div class="smallBar"><div style="width:0%"></div></div></div><div style="margin-top:10px"><div class="mini"><b>Other</b> · 1</div><div class="smallBar"><div style="width:100%"></div></div></div></div>
            </div>

            <div class="panel">
              <h4>🔴 Send ⇄ Jobs debug monitor</h4>
              <div class="mini">Live terminal-style monitor below top providers. Includes send input snapshot, job state transitions, and all merged logs.</div>
              <div class="debugTerminal">
                <div class="debugTerminalHead">
                  <span>RED SCREEN TERMINAL</span>
                  <span class="muted" data-k="debugTerminalMeta">waiting for logs…</span>
                </div>
                <div class="debugTerminalBody" data-k="sendJobsDebugTerminal">—</div>
              </div>
            </div>

            <div class="panel">
              <h4 class="sopHeader">📌 System / Provider / Integrity</h4>

              <div class="sopBlock">
              <div class="sopLabel system">🖥️ System / Internal</div>
              <div class="sopLine" data-k="systemSummary">🔗 Bridge failures: <b>0</b> · ⏱️ Last bridge success: <b>0m ago</b> · ⚙️ Runtime internal errors: <b>0</b> · 💾 DB write failures: <b>0</b></div>
              <details class="errorFold">
                <summary>View details</summary>
                <div class="mini" style="margin-top:8px" data-k="systemDetails">—</div>
              </details>
              </div>

              <div class="sopBlock">
              <div class="sopLabel provider">📬 Provider / Deliverability</div>
              <div class="sopLine" data-k="providerSummary">✅ Delivered: <b>0</b> (—) · ⏳ Deferred: <b>0</b> (—) · ❌ Bounced: <b>0</b> (—) · 📢 Complained: <b>0</b> (—)</div>
              <div class="sopLine" style="margin-top:6px" data-k="providerBreakdown">🌐 Provider/domain breakdown: —</div>
              <div class="sopLine" style="margin-top:6px" data-k="providerReasons">🧠 Top reason buckets: —</div>
              <details class="errorFold">
                <summary>View details</summary>
                <div class="mini" style="margin-top:8px" data-k="providerDetails">—</div>
              </details>
              </div>

              <div class="sopBlock">
              <div class="sopLabel integrity">🗂️ Data Integrity / Mapping</div>
              <div class="sopLine" data-k="integritySummary">♻️ duplicates_dropped: <b>0</b> · 🔎 job_not_found: <b>0</b> · 🧾 missing_fields: <b>0</b> · 💽 db_write_failures: <b>0</b></div>
              <details class="errorFold">
                <summary>View details</summary>
                <div class="mini" style="margin-top:8px" data-k="integrityDetails">—</div>
              </details>
              </div>

              <div class="legacyDiagnosticsBox">
                <div class="legacyDiagnosticsTitle">📄 Legacy quality + errors (unchanged data)</div>
                <div class="legacySectionLabel">📊 Quality counters</div>
                <div class="mini legacyDataLine" data-k="counters">safe_total=0 · safe_invalid=0 · invalid_filtered=0 · skipped=0 · backoff_events=0 · abandoned_chunks=1 · paused=no · stop_requested=no</div>
                <div class="legacySectionLabel">🚨 Error type</div>
                <div class="mini legacyDataLine" data-k="errorTypes">—</div>
                <div class="legacySectionLabel">⚠️ Error summary</div>
                <div class="mini legacyDataLine" data-k="lastErrors">—</div>
                <div class="mini legacyDataLine" data-k="lastErrors2">—</div>
                <div class="mini legacyDataLine" data-k="internalErrors">—</div>
              </div>
              <div class="bridgeSnapshotBox">
                <div class="legacySectionLabel" style="margin-top:0">🌉 Data source: Bridge snapshot</div>
                <div class="mini legacyDataLine" style="margin-top:8px" data-k="bridgeReceiver">Data source: <b>Bridge snapshot</b><br>Last poll success: <b>2026-03-22T12:33:05Z (just now)</b><br>Last accounting update: <b>—</b></div>
              </div>
            </div>

          </div>

          <!-- 8) Preflight history per chunk -->
          <div class="panel" style="margin-top:10px">
            <h4>Chunk preflight</h4>
            <div class="mini" style="margin-top:6px"><b>Active / Live chunk</b></div>
            <div style="overflow:auto; margin-top:8px">
              <table>
                <thead>
                  <tr>
                    <th>Chunk</th>
                    <th>Status</th>
                    <th>Size</th>
                    <th>Sender mail</th>
                    <th>Receiver domain</th>
                    <th>Spam</th>
                    <th>Blacklist</th>
                  </tr>
                </thead>
                <tbody data-k="chunkLive"><tr><td colspan="7" class="mini">No active chunk right now.</td></tr></tbody>
              </table>
            </div>

            <div class="mini" style="margin-top:10px"><b>History chunk (last 12)</b></div>
            <div style="overflow:auto; margin-top:8px">
              <table>
                <thead>
                  <tr>
                    <th>Chunk</th>
                    <th>Status</th>
                    <th>Size</th>
                    <th>Sender mail</th>
                    <th>Receiver domain</th>
                    <th>Spam</th>
                    <th>Blacklist</th>
                    <th>Attempt</th>
                    <th>Next retry</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody data-k="chunkHist"><tr><td colspan="10" class="mini">No chunk states yet.</td></tr></tbody>
              </table>
            </div>
          </div>
        </details>

    </div>
  </main>

  <div class="toast-wrap" id="toastWrap"></div>

<script>
  const esc = (s) => (s ?? '').toString().replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  const escAttr = (s) => esc(s).replaceAll('"','&quot;');

  function badgeWithTip(label, tip){
    const safeLabel = esc(label || '—');
    const safeTip = escAttr(tip || '—');
    return `<span class="badgeLabel">${safeLabel}</span><span class="tip" data-tip="${safeTip}">ⓘ</span>`;
  }

  function toast(title, msg, kind){
    const wrap = document.getElementById('toastWrap');
    const div = document.createElement('div');
    div.className = `toast ${kind || 'warn'}`;
    const safeMsg = esc(msg).split(/\r?\n/).join("<br>");
    div.innerHTML = `<div class="t">${esc(title)}</div><div>${safeMsg}</div>`;
    wrap.appendChild(div);
    setTimeout(() => {
      div.style.opacity = '0';
      div.style.transform = 'translateY(6px)';
      div.style.transition = 'all .22s ease';
      setTimeout(()=>div.remove(), 260);
    }, 3600);
  }

  function qk(root, key){
    return root.querySelector(`[data-k="${key}"]`);
  }

  function pct(n,d){
    const nn = Number(n||0), dd = Number(d||0);
    return dd ? Math.min(100, Math.round((nn/dd)*100)) : 0;
  }

  function fmtEta(sec){
    if(sec === null || sec === undefined) return 'ETA —';
    const s = Math.max(0, Number(sec||0));
    if(!isFinite(s)) return 'ETA —';
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const ss = Math.floor(s % 60);
    if(h > 0) return `ETA ${h}h ${m}m`;
    if(m > 0) return `ETA ${m}m ${ss}s`;
    return `ETA ${ss}s`;
  }

  function tsToMs(ts){
    const s = (ts || '').toString().trim();
    if(!s) return null;
    const n = Date.parse(s);
    return Number.isFinite(n) ? n : null;
  }

  function ageMin(ts){
    const ms = tsToMs(ts);
    if(ms === null) return null;
    return Math.max(0, Math.floor((Date.now() - ms) / 60000));
  }

  function riskBadgeClass(level){
    const lv = (level || '').toString().toLowerCase();
    if(lv === 'low') return 'triageBadge good';
    if(lv === 'med') return 'triageBadge warn';
    if(lv === 'high') return 'triageBadge bad';
    return 'triageBadge';
  }

  function healthBadgeClass(ok){
    if(ok === true) return 'triageBadge good';
    if(ok === false) return 'triageBadge bad';
    return 'triageBadge';
  }

  function computeDeliverabilityRisk(j){
    const sent = Number(j.sent || 0);
    const delivered = Number(j.delivered || 0);
    const bounced = Number(j.bounced || 0);
    const complained = Number(j.complained || 0);
    const deferred = Number(j.deferred || 0);
    if(sent <= 0) return '—';
    const bRate = bounced / sent;
    const cRate = complained / sent;
    const dRate = deferred / sent;
    if(bRate >= 0.12 || cRate >= 0.01 || (delivered <= 0 && sent >= 30)) return 'HIGH';
    if(bRate >= 0.05 || cRate >= 0.003 || dRate >= 0.2) return 'MED';
    return 'LOW';
  }


  function normalizeJobStatus(j){
    const raw = (j && j.status ? j.status : '').toString().trim().toLowerCase();
    if(raw === 'running' || raw === 'done' || raw === 'paused' || raw === 'backoff') return raw;
    if(raw === 'stop' || raw === 'stopped') return 'stop';
    return 'other';
  }

  function normalizeBridgeMode(j){
    const raw = (j && j.bridge_mode ? j.bridge_mode : 'counts').toString().trim().toLowerCase();
    if(raw === 'legacy') return 'legacy';
    if(raw === 'counts') return 'counts';
    return 'counts';
  }

  function freshnessMinutes(j){
    const mode = normalizeBridgeMode(j);
    if(mode === 'counts'){
      return ageMin(j.accounting_last_update_ts || j.accounting_last_ts);
    }
    const lagSecRaw = Number(j && j.ingestion_lag_seconds);
    if(Number.isFinite(lagSecRaw) && lagSecRaw >= 0){
      return Math.floor(lagSecRaw / 60);
    }
    return ageMin(j.ingestion_last_event_ts || j.accounting_last_ts);
  }

  function hasInternalDegraded(j){
    const failureCount = Number(j && j.bridge_failure_count);
    const failN = Number.isFinite(failureCount) ? failureCount : Number(j && j.internal_health_failures || 0);
    return Number.isFinite(failN) && failN > 0;
  }

  function hasDeliverabilityHigh(j){
    return computeDeliverabilityRisk(j) === 'HIGH';
  }

  function isStaleJob(j){
    const mode = normalizeBridgeMode(j);
    const mins = freshnessMinutes(j);
    if(mins === null || !Number.isFinite(mins)) return false;
    return mode === 'legacy' ? mins > 15 : mins > 10;
  }

  function providerBucketFromDomain(domain){
    const d = (domain || '').toString().trim().toLowerCase();
    if(!d) return 'other';
    if(d.includes('gmail.') || d.includes('googlemail.')) return 'gmail';
    if(d.includes('yahoo.') || d.includes('ymail.') || d.includes('rocketmail.')) return 'yahoo';
    if(d.includes('outlook.') || d.includes('hotmail.') || d.includes('live.') || d.includes('msn.')) return 'outlook';
    if(d.includes('icloud.') || d.includes('me.com') || d.includes('mac.com')) return 'icloud';
    return 'other';
  }

  function detectProviderBucket(j){
    const weighted = {};
    const add = (dom, w) => {
      const b = providerBucketFromDomain(dom);
      weighted[b] = Number(weighted[b] || 0) + Math.max(0, Number(w || 0));
    };
    const plan = (j && j.domain_plan) || {};
    for(const [dom, count] of Object.entries(plan)) add(dom, count);
    if(!Object.keys(plan).length){
      const host = (j && j.smtp_host ? j.smtp_host : '').toString().trim().toLowerCase();
      if(host) add(host, 1);
    }
    let best = 'other';
    let bestW = -1;
    for(const [k,v] of Object.entries(weighted)){
      if(v > bestW){
        best = k;
        bestW = v;
      }
    }
    return best;
  }

  function riskRank(j){
    if(hasInternalDegraded(j)) return 3;
    if(hasDeliverabilityHigh(j)) return 2;
    if(isStaleJob(j)) return 1;
    return 0;
  }

  function renderTriageBadges(card, j){
    const modeRaw = (j.bridge_mode || '—').toString().trim().toLowerCase();
    const isCounts = modeRaw === 'counts';
    const isLegacy = modeRaw === 'legacy';

    const modeEl = qk(card, 'badgeMode');
    if(modeEl){
      const modeLabel = isCounts ? 'COUNTS' : (isLegacy ? 'LEGACY' : '—');
      const modeTip = isCounts
        ? 'Bridge polling mode uses aggregated accounting counters (fast/low overhead).'
        : (isLegacy
          ? 'Bridge polling mode uses legacy event stream with ingestion lag tracking.'
          : 'Bridge mode not available yet for this job.');
      modeEl.innerHTML = badgeWithTip(modeLabel, modeTip);
      modeEl.className = 'triageBadge';
    }

    const freshEl = qk(card, 'badgeFreshness');
    if(freshEl){
      let txt = '—';
      let cls = 'triageBadge';
      if(isCounts){
        const mins = ageMin(j.accounting_last_update_ts || j.accounting_last_ts);
        if(mins === null){
          txt = 'acct: —';
        }else if(mins > 10){
          txt = `STALE: ${mins}m`;
          cls = 'triageBadge warn';
        }else{
          txt = `acct: ${mins}m ago`;
          cls = 'triageBadge good';
        }
      }else if(isLegacy){
        const lagSecRaw = Number(j.ingestion_lag_seconds);
        const mins = Number.isFinite(lagSecRaw) && lagSecRaw >= 0
          ? Math.floor(lagSecRaw / 60)
          : ageMin(j.ingestion_last_event_ts || j.accounting_last_ts);
        if(mins === null){
          txt = 'lag: —';
        }else if(mins <= 1){
          txt = 'caught up';
          cls = 'triageBadge good';
        }else{
          txt = `lag: ${mins}m`;
          cls = mins > 15 ? 'triageBadge warn' : 'triageBadge';
        }
      }
      freshEl.innerHTML = badgeWithTip(txt, 'Freshness signal: how recent accounting or legacy ingestion updates are for this job.');
      freshEl.className = cls;
    }

    const failureCount = Number(j.bridge_failure_count);
    const failN = Number.isFinite(failureCount) ? failureCount : Number(j.internal_health_failures || 0);
    const healthEl = qk(card, 'badgeHealth');
    if(healthEl){
      const known = Number.isFinite(failN);
      const ok = known ? failN <= 0 : null;
      healthEl.className = healthBadgeClass(ok);
      if(known){
        const failures = Math.max(0, Math.floor(failN));
        const label = ok ? 'OK (0)' : `DEGRADED (${failures})`;
        const tip = ok
          ? 'Internal health checks are clean (no bridge/runtime failure counters).'
          : `Internal health degraded: ${failures} bridge/runtime failures were detected.`;
        healthEl.innerHTML = badgeWithTip(label, tip);
      }else{
        healthEl.innerHTML = badgeWithTip('—', 'Internal health state is not available yet.');
      }
    }

    const risk = computeDeliverabilityRisk(j);
    const riskEl = qk(card, 'badgeRisk');
    if(riskEl){
      riskEl.className = riskBadgeClass(risk);
      riskEl.innerHTML = badgeWithTip(`RISK ${risk}`, 'Deliverability risk derived from bounce, complaint, and deferred rates.');
    }

    renderBridgeConnectionBadge(card, state.latestBridgeState, j);

    const dup = Number(j.duplicates_dropped || 0);
    const jnf = Number(j.job_not_found || 0);
    const dbf = Number(j.db_write_failures || 0);
    const miss = Number(j.missing_fields || 0);
    const hasIntegrity = (dup + jnf + dbf + miss) > 0;
    const intEl = qk(card, 'badgeIntegrity');
    if(intEl){
      intEl.style.display = hasIntegrity ? 'inline-flex' : 'none';
      intEl.className = hasIntegrity ? 'triageBadge bad' : 'triageBadge';
      const integrityTotal = dup + jnf + dbf + miss;
      const integrityTip = hasIntegrity
        ? `Data integrity issues found: duplicates=${dup}, job_not_found=${jnf}, missing_fields=${miss}, db_write_failures=${dbf}.`
        : 'Data integrity counters are clean.';
      intEl.innerHTML = badgeWithTip(hasIntegrity ? `INTEGRITY (${integrityTotal})` : 'INTEGRITY', integrityTip);
    }
  }

  function renderBridgeConnectionBadge(card, bridgeState, jobPayload){
    const bridgeEl = qk(card, 'badgeBridgeConn');
    if(!bridgeEl) return;
    const connected = !!(bridgeState && bridgeState.connected === true);
    const bridgeDiag = jobPayload && jobPayload.diagnostics && jobPayload.diagnostics.bridge ? jobPayload.diagnostics.bridge : null;
    const expected = bridgeDiag && typeof bridgeDiag.expected === 'boolean' ? !!bridgeDiag.expected : null;
    const stateLabel = connected ? 'connected' : 'disconnected';
    const expectedLabel = expected === null ? 'unknown expectation' : (expected ? 'expected' : 'abnormal');
    const label = `Bridge↔Shiva ${stateLabel} (${expectedLabel})`;
    const endpoint = (
      (bridgeState && (bridgeState.last_req_url || bridgeState.pull_url_masked || bridgeState.bridge_base_url)) || ''
    ).toString().trim();
    const endpointTip = endpoint
      ? ` Current endpoint: ${endpoint}`
      : ' Current endpoint is not available yet.';
    const diagTip = bridgeDiag && bridgeDiag.reason ? ` Diagnostic: ${bridgeDiag.reason}` : '';
    const tip = `Real-time bridge transport status between PMTA accounting bridge and Shiva receiver.${endpointTip}${diagTip}`;
    bridgeEl.className = `triageBadge bridgeConnBadge ${connected ? 'good' : 'bad'}`;
    bridgeEl.innerHTML = `<span class="statusDot ${connected ? 'good' : 'bad'}" aria-hidden="true"></span><span>${esc(label)}</span><span class="tip" data-tip="${esc(tip)}">ⓘ</span>`;
    bridgeEl.title = endpoint ? `${label} · ${endpoint}` : label;
  }

  function statusPillClass(st){
    const s = (st||'').toString().toLowerCase();
    if(s === 'done') return 'pill good';
    if(s === 'running') return 'pill good';
    if(s === 'paused') return 'pill warn';
    if(s === 'backoff') return 'pill warn';
    if(s === 'stopped') return 'pill warn';
    if(s === 'error') return 'pill bad';
    return 'pill';
  }

  const state = {
    lastStatus: {},
    lastBackoff: {},
    lastAbandoned: {},
    lastFailed: {},
    lastAdaptive: {},
    lastRoute: {},
    lastPmtaMonitor: {},
    lastJobPayload: {},
    latestBridgeState: null,
    latestDiagnostics: [],
    filters: {
      status: 'all',
      mode: 'all',
      risk: 'all',
      provider: 'all',
      sort: 'newest',
    },
  };

  function renderSystemDiagnostics(diags){
    const summaryEl = document.getElementById('jobsDiagnosticsSummary');
    const listEl = document.getElementById('jobsDiagnosticsList');
    const rows = Array.isArray(diags) ? diags : [];
    if(!summaryEl || !listEl) return;
    if(!rows.length){
      summaryEl.textContent = 'Diagnostics not available yet.';
      listEl.innerHTML = '';
      return;
    }
    const bad = rows.filter(x => (x && x.status) === 'bad').length;
    const warn = rows.filter(x => (x && x.status) === 'warn').length;
    summaryEl.textContent = (bad || warn)
      ? `Attention needed: ${bad} bad · ${warn} warning diagnostics.`
      : 'All core diagnostics look healthy.';
    listEl.innerHTML = rows.map((row) => {
      const tone = row.status === 'good' ? '✅' : (row.status === 'warn' ? '⚠️' : '❌');
      return `${tone} <b>${esc((row.key || 'diag').replaceAll('_', ' '))}:</b> ${esc(row.reason || '—')}`;
    }).join('<br>');
  }

  async function controlJob(jobId, action){
    const reason = action === 'stop' ? prompt('Stop reason (optional):') : '';
    try{
      const r = await fetch(`/api/job/${jobId}/control`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({action, reason: reason || ''})
      });
      const j = await r.json().catch(()=>({}));
      if(r.ok && j.ok){
        toast('Job control', `Job ${jobId}: ${action} OK`, 'good');
      }else{
        toast('Job control failed', (j && (j.error||j.detail)) ? (j.error||j.detail) : ('HTTP '+r.status), 'bad');
      }
    }catch(e){
      toast('Job control failed', e?.toString?.() || 'Unknown error', 'bad');
    }
  }

  async function deleteJob(jobId, card){
    const ok = confirm(`Delete job ${jobId}?
This will remove it from Jobs history.`);
    if(!ok) return;
    try{
      const r = await fetch(`/api/job/${jobId}/delete`, { method:'POST' });
      const j = await r.json().catch(()=>({}));
      if(r.ok && j && j.ok){
        toast('Job deleted', `Job ${jobId} deleted.`, 'good');
        if(card) card.remove();
        cards = cards.filter(x => x !== card);
        applyFiltersAndSort();
      }else{
        toast('Delete failed', (j && (j.error||j.detail)) ? (j.error||j.detail) : ('HTTP '+r.status), 'bad');
      }
    }catch(e){
      toast('Delete failed', e?.toString?.() || 'Unknown error', 'bad');
    }
  }

  function renderTopDomains(card, j){
    const plan = j.domain_plan || {};
    const sent = j.domain_sent || {};
    const failed = j.domain_failed || {};
    const currDom = j.current_chunk_domains || {};

    const pmtaDom = j.pmta_domains || {};
    const pmtaOk = !!pmtaDom.ok;
    const pmtaMap = pmtaDom.domains || {};

    const entries = Object.entries(plan).map(([dom, p]) => {
      const pp = Number(p||0);
      const ss = Number(sent[dom]||0);
      const ff = Number(failed[dom]||0);
      const done = ss + ff;
      return {dom, pp, ss, ff, done, pct: pct(done, pp), active: (dom in currDom)};
    }).sort((a,b)=>b.pp - a.pp).slice(0,10);

    const totalRecipients = Number(j.total || 0);
    const domainsCount = Object.keys(plan).length;
    const showProviders = (totalRecipients <= 50) || (domainsCount <= 5);

    const titleEl = qk(card, 'domainsPanelTitle');
    const elLine = qk(card,'topDomains');
    const elBars = qk(card,'topDomainsBars');
    const barsLabelEl = elBars ? elBars.previousElementSibling : null;

    function providerForDomain(dom){
      const d = (dom || '').toString().trim().toLowerCase();
      if(!d) return 'Other';

      if(
        d === 'gmail.com' || d.endsWith('.gmail.com') ||
        d === 'googlemail.com' || d.endsWith('.googlemail.com')
      ) return 'Gmail';

      if(
        d === 'yahoo.com' || d.endsWith('.yahoo.com') ||
        d.endsWith('.yahoo.co.jp') ||
        d === 'ymail.com' || d.endsWith('.ymail.com') ||
        d === 'rocketmail.com' || d.endsWith('.rocketmail.com') ||
        d === 'yahoo.co.jp'
      ) return 'Yahoo';

      if(
        d === 'outlook.com' || d.endsWith('.outlook.com') ||
        d === 'hotmail.com' || d.endsWith('.hotmail.com') ||
        d === 'live.com' || d.endsWith('.live.com') ||
        d === 'msn.com' || d.endsWith('.msn.com') ||
        d === 'passport.com' || d.endsWith('.passport.com')
      ) return 'Outlook';

      if(
        d === 'icloud.com' || d.endsWith('.icloud.com') ||
        d === 'me.com' || d.endsWith('.me.com') ||
        d === 'mac.com' || d.endsWith('.mac.com')
      ) return 'iCloud';

      return 'Other';
    }

    function renderProviderBreakdown(){
      const buckets = {Gmail: 0, Yahoo: 0, Outlook: 0, iCloud: 0, Other: 0};
      const hasPlan = Object.keys(plan).length > 0;
      if(!hasPlan){
        if(elLine) elLine.textContent = '—';
        if(elBars) elBars.innerHTML = '';
        if(titleEl) titleEl.textContent = 'Top providers';
        if(barsLabelEl) barsLabelEl.style.display = 'none';
        return;
      }

      for(const [dom, rawCount] of Object.entries(plan)){
        const cnt = Number(rawCount || 0);
        const provider = providerForDomain(dom);
        buckets[provider] = Number(buckets[provider] || 0) + Math.max(0, cnt);
      }
      const ordered = ['Gmail', 'Yahoo', 'Outlook', 'iCloud', 'Other'].map(name => ({
        name,
        count: Number(buckets[name] || 0)
      }));

      if(titleEl) titleEl.textContent = 'Top providers';
      if(barsLabelEl) barsLabelEl.style.display = 'none';

      if(elLine){
        elLine.innerHTML = ordered.map(x => `${x.name}: <b>${x.count}</b>`).join(' · ');
      }
      if(elBars){
        const maxCount = Math.max(1, ...ordered.map(x => x.count));
        elBars.innerHTML = ordered.map(x => {
          const width = Math.round((x.count / maxCount) * 100);
          return `<div style="margin-top:10px">`+
            `<div class="mini"><b>${x.name}</b> · ${x.count}</div>`+
            `<div class="smallBar"><div style="width:${width}%"></div></div>`+
          `</div>`;
        }).join('');
      }
    }

    if(!entries.length){
      if(elLine) elLine.textContent = '—';
      if(elBars) elBars.innerHTML = '';
      if(titleEl) titleEl.textContent = showProviders ? 'Top providers' : 'Top domains (Top 10)';
      if(barsLabelEl) barsLabelEl.style.display = showProviders ? 'none' : '';
      return;
    }

    if(showProviders){
      renderProviderBreakdown();
      return;
    }

    if(titleEl) titleEl.textContent = 'Top domains (Top 10)';
    if(barsLabelEl) barsLabelEl.style.display = '';

    if(elLine){
      elLine.innerHTML = entries.map(x => {
        const flag = x.active ? ' 🔥' : '';
        const pm = pmtaMap[x.dom] || {};
        const q = (pm && pm.queued !== undefined && pm.queued !== null) ? pm.queued : '—';
        const d = (pm && pm.deferred !== undefined && pm.deferred !== null) ? pm.deferred : '—';
        const a = (pm && pm.active !== undefined && pm.active !== null) ? pm.active : '—';
        const pmInfo = (pmtaOk && (x.dom in pmtaMap)) ? ` · pmta(q=${q} def=${d} act=${a})` : '';
        return `${esc(x.dom)}: <span class="ok">${x.ss}</span>/<b>${x.pp}</b> (final-fail <span class="no">${x.ff}</span>)${flag}${pmInfo}`;
      }).join('<br>');
    }

    if(elBars){
      elBars.innerHTML = entries.map(x => {
        const bar = `<div class="smallBar"><div style="width:${x.pct}%"></div></div>`;
        return `<div style="margin-top:10px">`+
          `<div class="mini"><b>${esc(x.dom)}</b> · ${x.done}/${x.pp} (${x.pct}%)${x.active ? ' · active' : ''}</div>`+
          `${bar}`+
        `</div>`;
      }).join('');
    }
  }

  function renderErrorTypes(card, j){
    const ec = j.accounting_error_counts || {};
    const entries = Object.entries(ec).sort((a,b)=>Number(b[1]||0)-Number(a[1]||0));
    const el = qk(card,'errorTypes');
    if(!el){ return; }

    const labels = {
      accepted: '2XX accepted',
      temporary_error: '4XX temporary',
      blocked: '5XX blocked'
    };

    const rawErrors = Array.isArray(j.accounting_last_errors) ? j.accounting_last_errors : [];
    const onlyErrors = rawErrors.filter(x => (x && x.kind !== 'accepted'));
    const latestError = onlyErrors.length ? onlyErrors[onlyErrors.length - 1] : null;
    const bouncedN = Number(j.bounced || 0);
    const deferredN = Number(j.deferred || 0);
    const complainedN = Number(j.complained || 0);
    const hasOutcomeFailures = (bouncedN + deferredN + complainedN) > 0;

    function errorSignature(detail){
      const txt = (detail || '').toString();
      const m = txt.match(/\b([245]\.\d\.\d{1,3})\b(?:\s*\(([^)]+)\))?/i);
      if(m){
        const code = (m[1] || '').trim();
        const reason = (m[2] || '').trim();
        return reason ? `${code} (${reason})` : code;
      }
      const smtp = txt.match(/\b([245]\d\d)\b/);
      if(smtp) return smtp[1];
      return txt ? txt.slice(0, 120) : 'unknown';
    }

    const sigMap = new Map();
    for(const x of onlyErrors){
      const sig = errorSignature(x.detail);
      if(!sigMap.has(sig)) sigMap.set(sig, {count: 0, sample: x});
      const row = sigMap.get(sig);
      row.count += 1;
    }
    const topSig = Array.from(sigMap.entries()).sort((a,b)=>b[1].count-a[1].count)[0] || null;

    if(!entries.length && !topSig && !latestError){
      if(hasOutcomeFailures){
        const estBlocked = Math.max(0, bouncedN + complainedN);
        const estTemp = Math.max(0, deferredN);
        const parts = [];
        parts.push(`Latest code: <b>${estBlocked > 0 ? '5XX*' : '4XX*'}</b>`);
        parts.push('Most common error: <b>Outcome-only snapshot</b> · <b>1</b>');
        parts.push('Example: Bridge snapshot provides aggregate outcomes only (no SMTP response text).');
        parts.push([
          `4XX temporary: <b>${estTemp}</b>`,
          `5XX blocked: <b>${estBlocked}</b>`
        ].join(' · '));
        el.innerHTML = parts.join('<br>');
      }else{
        el.textContent = '—';
      }
    }else{
      const parts = [];
      if(latestError){
        const latestCode = pickErrorCode(latestError.detail || '') || '—';
        parts.push(`Latest code: <b>${esc(latestCode)}</b>`);
      }
      if(topSig){
        const [sig, info] = topSig;
        parts.push(`Most common error: <b>${esc(sig)}</b> · <b>${Number(info.count||0)}</b>`);
        const sample = (info.sample && info.sample.detail) ? info.sample.detail : '';
        if(sample){
          parts.push(`Example: ${esc(sample)}`);
        }
      }
      if(entries.length){
        parts.push(entries.map(([k,v]) => `${esc(labels[k] || k)}: <b>${Number(v||0)}</b>`).join(' · '));
      }
      el.innerHTML = parts.join('<br>');
    }

    function shortWords(txt, maxWords){
      const words = (txt || '').toString().replace(/\s+/g, ' ').trim().split(' ').filter(Boolean);
      return words.slice(0, Math.max(1, Number(maxWords || 4))).join(' ');
    }

    function pickErrorCode(txt){
      const s = (txt || '').toString();
      let m = s.match(/\b([245]\.\d\.\d{1,3})\b/i);
      if(m) return (m[1] || '').trim();
      m = s.match(/\b([245]\d\d)\b/);
      if(m) return (m[1] || '').trim();
      return '';
    }

    function pickErrorSummary(x){
      if(!x) return '';
      const typ = (x.type || '').toString().trim().toLowerCase();
      const kind = (x.kind || '').toString().trim().toLowerCase();
      if(typ) return typ;
      if(kind === 'temporary_error') return 'deferred';
      if(kind === 'blocked') return 'blocked';
      if(kind === 'accepted') return 'accepted';
      return kind || 'unknown';
    }

    // Error 1 (summary): latest status keyword from PMTA (bounced/deferred/complained/blocked/backoff...)
    const el2 = qk(card,'lastErrors');
    const pmtaErrorSummaryEl = qk(card,'pmtaErrorSummary');
    let errorSummaryLine1 = '—';
    if(el2){
      if(!latestError){
        if(hasOutcomeFailures){
          if(bouncedN + complainedN > 0){
            errorSummaryLine1 = `• [5XX*] bounced/complained · count=${esc(String(bouncedN + complainedN))}`;
          }else{
            errorSummaryLine1 = `• [4XX*] deferred · count=${esc(String(deferredN))}`;
          }
        }else{
          errorSummaryLine1 = '—';
        }
      }
      else{
        const detail = (latestError.detail || '').toString();
        const code = pickErrorCode(detail) || ((latestError.kind === 'temporary_error') ? '4XX' : '5XX');
        const summary = pickErrorSummary(latestError) || shortWords(detail, 4) || 'unknown';
        errorSummaryLine1 = `• [${esc(code)}] ${esc(summary)}`;
      }
      el2.innerHTML = errorSummaryLine1;
    }

    // Error 2 (details): latest full PowerMTA response detail
    const el3 = qk(card,'lastErrors2');
    let errorSummaryLine2 = '';
    if(el3){
      if(!latestError){
        if(hasOutcomeFailures){
          const mode = ((j.bridge_mode || '').toString().toLowerCase() || 'counts');
          const src = (mode === 'legacy') ? 'event ingestion' : 'bridge snapshot';
          errorSummaryLine2 = `• aggregate outcomes present (bounced=${esc(String(bouncedN))} · deferred=${esc(String(deferredN))} · complained=${esc(String(complainedN))}) · source=${esc(src)} · no per-recipient SMTP detail in this mode`;
        }else{
          errorSummaryLine2 = '';
        }
      }
      else{
        const typ = (latestError.type || '').toString();
        const kind = (latestError.kind || '').toString();
        const code = pickErrorCode(latestError.detail || '');
        const codePart = code ? ` · code=${esc(code)}` : '';
        errorSummaryLine2 = `• ${esc(latestError.email || '—')} · type=${esc(typ || 'unknown')} · kind=${esc(kind || 'unknown')}${codePart} · ${esc(latestError.detail || '')}`;
      }
      el3.innerHTML = errorSummaryLine2 || '—';
    }

    if(pmtaErrorSummaryEl){
      const hasErrorSummary = (errorSummaryLine1 && errorSummaryLine1 !== '—') || !!errorSummaryLine2;
      pmtaErrorSummaryEl.innerHTML = hasErrorSummary
        ? [errorSummaryLine1 || '', errorSummaryLine2 || ''].filter(Boolean).join('<br>')
        : '';
      pmtaErrorSummaryEl.style.display = hasErrorSummary ? '' : 'none';
    }

    function isNetworkInternalError(x){
      if(!x) return false;
      const t = (x.type || '').toString().toLowerCase();
      const d = (x.detail || '').toString().toLowerCase();
      const bag = `${t} ${d}`;
      return (
        bag.includes('network') ||
        bag.includes('socket') ||
        bag.includes('timeout') ||
        bag.includes('timed out') ||
        bag.includes('connection refused') ||
        bag.includes('connection reset') ||
        bag.includes('name or service not known') ||
        bag.includes('temporary failure in name resolution') ||
        bag.includes('host unreachable') ||
        bag.includes('no route to host') ||
        bag.includes('broken pipe') ||
        bag.includes('ssl') ||
        bag.includes('tls')
      );
    }

    const allInternalRows = Array.isArray(j.internal_last_errors) ? j.internal_last_errors : [];
    const netInternalRows = allInternalRows.filter(isNetworkInternalError);
    const ieRows = netInternalRows.slice().reverse().slice(0,10);
    const ieAgg = {};
    for(const row of netInternalRows){
      const k = (row && row.type) ? row.type.toString() : 'network_error';
      ieAgg[k] = Number(ieAgg[k] || 0) + 1;
    }
    const ie = qk(card,'internalErrors');
    if(ie){
      const topFixed = Object.entries(ieAgg).sort((a,b)=>Number(b[1]||0)-Number(a[1]||0));
      const countLine = topFixed.length
        ? topFixed.map(([k,v]) => `${esc(k)}: <b>${Number(v||0)}</b>`).join(' · ')
        : '';

      if(!countLine && !ieRows.length){
        ie.textContent = '—';
      }else{
        const lines = [];
        if(countLine) lines.push(countLine);
        if(ieRows.length){
          lines.push(ieRows.map(x => {
            const jid = (x.job_id || '').toString();
            const em = (x.email || '').toString();
            const ts = (x.ts || '').toString();
            const extra = [jid ? `job=${jid}` : '', em ? `email=${em}` : ''].filter(Boolean).join(' · ');
            return `• ${esc(ts)} · [${esc(x.type || 'other')}] ${esc(x.detail || '')}${extra ? ` · ${esc(extra)}` : ''}`;
          }).join('<br>'));
        }
        ie.innerHTML = lines.join('<br>');
      }
    }
  }



  function renderIssueBlocks(card, j){
    const asNum = (v) => {
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };
    const fmtRate = (n, d) => {
      if(n === null || d === null || d <= 0) return '—';
      return `${((n/d)*100).toFixed(1)}%`;
    };

    const bridgeFail = asNum(j.bridge_failure_count);
    const bridgeErr = (j.bridge_last_error_message || '').toString().trim();
    const bridgeAge = ageMin(j.bridge_last_success_ts);
    const internalCounts = j.internal_error_counts || {};
    const runtimeErr = Object.values(internalCounts).reduce((a,v)=>a+Number(v||0),0);
    const dbFail = asNum(j.db_write_failures);

    const sys = qk(card,'systemSummary');
    if(sys){
      const bits = [
        `🔗 Bridge failures: <b>${bridgeFail === null ? '—' : bridgeFail}</b>`,
        `⏱️ Last bridge success: <b>${bridgeAge === null ? '—' : (bridgeAge + 'm ago')}</b>`,
        `⚙️ Runtime internal errors: <b>${runtimeErr || 0}</b>`,
        `💾 DB write failures: <b>${dbFail === null ? '—' : dbFail}</b>`,
      ];
      if(bridgeErr) bits.push(`🚨 Bridge last error: ${esc(bridgeErr.slice(0,140))}`);
      sys.innerHTML = bits.join(' · ');
    }

    const sysRows = [];
    const irows = Array.isArray(j.internal_last_samples) ? j.internal_last_samples : (Array.isArray(j.internal_last_errors) ? j.internal_last_errors : []);
    for(const x of irows.slice().reverse().slice(0,8)){
      sysRows.push(`• ${esc(x.ts || '—')} · [${esc(x.type || 'internal')}] ${esc((x.detail || '').toString().slice(0,180))}`);
    }
    const sysDet = qk(card,'systemDetails');
    if(sysDet) sysDet.innerHTML = sysRows.length ? sysRows.join('<br>') : '—';

    const sent = asNum(j.sent);
    const delivered = asNum(j.delivered);
    const deferred = asNum(j.deferred);
    const bounced = asNum(j.bounced);
    const complained = asNum(j.complained);

    const prov = qk(card,'providerSummary');
    if(prov){
      prov.innerHTML = [
        `✅ Delivered: <b>${delivered ?? '—'}</b> (${fmtRate(delivered, sent)})`,
        `⏳ Deferred: <b>${deferred ?? '—'}</b> (${fmtRate(deferred, sent)})`,
        `❌ Bounced: <b>${bounced ?? '—'}</b> (${fmtRate(bounced, sent)})`,
        `📢 Complained: <b>${complained ?? '—'}</b> (${fmtRate(complained, sent)})`,
      ].join(' · ');
    }

    const pb = qk(card,'providerBreakdown');
    const breakdown = Array.isArray(j.provider_breakdown) ? j.provider_breakdown : [];
    if(pb){
      pb.innerHTML = breakdown.length
        ? ('🌐 Provider/domain breakdown: ' + breakdown.slice(0,6).map(x => `${esc(x.domain || '—')} D=${Number(x.delivered||0)} Def=${Number(x.deferred||0)} B=${Number(x.bounced||0)} C=${Number(x.complained||0)}`).join(' · '))
        : '🌐 Provider/domain breakdown: —';
    }

    const pr = qk(card,'providerReasons');
    const reasons = j.provider_reason_buckets || {};
    const reasonEntries = Object.entries(reasons).sort((a,b)=>Number(b[1]||0)-Number(a[1]||0)).slice(0,4);
    if(pr){
      pr.innerHTML = reasonEntries.length
        ? ('🧠 Top reason buckets: ' + reasonEntries.map(([k,v]) => `${esc(k)}=<b>${Number(v||0)}</b>`).join(' · '))
        : '🧠 Top reason buckets: —';
    }

    const provDet = qk(card,'providerDetails');
    if(provDet){
      const samples = (Array.isArray(j.accounting_last_errors) ? j.accounting_last_errors : []).filter(x => x && x.kind !== 'accepted').slice().reverse().slice(0,8);
      provDet.innerHTML = samples.length
        ? samples.map(x => `• ${esc(x.ts || '—')} · ${esc(x.email || '—')} · ${esc(x.type || '—')} · ${esc((x.detail || '').toString().slice(0,180))}`).join('<br>')
        : '—';
    }

    const dup = asNum(j.duplicates_dropped) || 0;
    const jnf = asNum(j.job_not_found) || 0;
    const miss = asNum(j.missing_fields) || 0;
    const dbwf = asNum(j.db_write_failures) || 0;
    const integ = qk(card,'integritySummary');
    if(integ){
      integ.innerHTML = `♻️ duplicates_dropped: <b>${dup}</b> · 🔎 job_not_found: <b>${jnf}</b> · 🧾 missing_fields: <b>${miss}</b> · 💽 db_write_failures: <b>${dbwf}</b>`;
    }

    const integDet = qk(card,'integrityDetails');
    const integRows = Array.isArray(j.integrity_last_samples) ? j.integrity_last_samples : [];
    if(integDet){
      integDet.innerHTML = integRows.length
        ? integRows.slice().reverse().slice(0,8).map(x => `• ${esc(x.ts || '—')} · ${esc(x.kind || 'integrity')} · job=${esc(x.job_id || '—')} · rcpt=${esc(x.rcpt || '—')}`).join('<br>')
        : '—';
    }
  }


  function renderChunkHist(card, j){
    const tb = qk(card,'chunkHist');
    if(!tb) return;
    const finalized = new Set(['done', 'done_after_backoff', 'abandoned']);
    const cs = (j.chunk_states || [])
      .filter(x => finalized.has((x?.status || '').toString().toLowerCase()))
      .slice()
      .reverse()
      .slice(0,12);
    if(!cs.length){
      tb.innerHTML = `<tr><td colspan="10" class="mini">No chunk states yet.</td></tr>`;
      return;
    }
    tb.innerHTML = cs.map(x => {
      const next = x.next_retry_ts ? new Date(Number(x.next_retry_ts)*1000).toLocaleTimeString() : '';
      const bl = (x.blacklist || '').toString();
      const blShort = bl.length > 30 ? (bl.slice(0,30) + '…') : bl;
      const sender = (x.sender || '').toString();
      const senderShort = sender.length > 30 ? (sender.slice(0,30) + '…') : sender;
      const receiverDomain = (x.target_domain || x.provider_domain || '').toString();
      const spam = (x.spam_score === null || x.spam_score === undefined) ? '' : Number(x.spam_score).toFixed(2);
      const reason = (x.reason || '').toString();
      const reasonShort = reason.length > 40 ? (reason.slice(0,40) + '…') : reason;
      const attempt = (x.attempt === null || x.attempt === undefined || x.attempt === '') ? '—' : String(x.attempt);
      const retryText = next || '—';

      return `<tr>`+
        `<td>${Number(x.chunk)+1}</td>`+
        `<td>${esc(x.status || '')}</td>`+
        `<td>${Number(x.size||0)}</td>`+
        `<td title="${esc(sender)}">${esc(senderShort)}</td>`+
        `<td>${esc(receiverDomain)}</td>`+
        `<td>${esc(spam)}</td>`+
        `<td title="${esc(bl)}">${esc(blShort)}</td>`+
        `<td><b>${esc(attempt)}</b></td>`+
        `<td><span title="${esc(next || '')}">${esc(retryText)}</span></td>`+
        `<td title="${esc(reason)}">${esc(reasonShort || '—')}</td>`+
      `</tr>`;
    }).join('');
  }

  function renderChunkLive(card, j){
    const tb = qk(card,'chunkLive');
    if(!tb) return;
    const active = getLiveChunks(j);
    if(!active.length){
      const isRunning = ['running','backoff'].includes((j.status || '').toString().toLowerCase());
      const snap = (j.debug_parallel_lanes_snapshot && typeof j.debug_parallel_lanes_snapshot === 'object') ? j.debug_parallel_lanes_snapshot : {};
      const laneCount = Number(snap.lanes_active ?? snap.active_lanes ?? snap.lanes ?? 0);
      const v2Active = !!j.v2_parallel_enabled || laneCount > 0;
      if(isRunning && v2Active){
        tb.innerHTML = `<tr><td colspan="7" class="mini">⚠️ No live chunk rows yet from active_chunks_info. This can be a brief telemetry gap in V2 parallel mode (lanes=${Number.isFinite(laneCount) ? laneCount : 0}).</td></tr>`;
      }else{
        tb.innerHTML = `<tr><td colspan="7" class="mini">No active chunk right now.</td></tr>`;
      }
      return;
    }
    tb.innerHTML = active.slice(0,12).map(ci => {
      const sender = (ci.sender_mail || ci.sender || '').toString();
      const senderShort = sender.length > 30 ? (sender.slice(0,30) + '…') : sender;
      const receiverDomain = (ci.receiver_domain || ci.target_domain || '').toString();
      const spam = (ci.spam_score === null || ci.spam_score === undefined) ? '—' : Number(ci.spam_score).toFixed(2);
      const bl = (ci.blacklist || '').toString();
      const blShort = bl.length > 30 ? (bl.slice(0,30) + '…') : bl;
      const status = (ci.status || (((j.status || '').toString().toLowerCase() === 'backoff') ? 'backoff' : 'running'));
      const laneBadge = (ci.lane_id !== undefined && ci.lane_id !== null && ci.lane_id !== '')
        ? ` · lane ${esc(String(ci.lane_id))}`
        : '';
      return `<tr>`+
        `<td>${Number(ci.chunk_id ?? ci.chunk)+1}${laneBadge}</td>`+
        `<td>${esc(status)}</td>`+
        `<td>${Number(ci.size||0)}</td>`+
        `<td title="${esc(sender)}">${esc(senderShort || '—')}</td>`+
        `<td>${esc(receiverDomain || '—')}</td>`+
        `<td>${esc(spam)}</td>`+
        `<td title="${esc(bl)}">${esc(blShort || '—')}</td>`+
      `</tr>`;
    }).join('');
  }

  function normalizeLiveChunkStatus(rawStatus, jobStatus){
    const s = (rawStatus || '').toString().toLowerCase();
    if(s === 'backoff') return 'backoff';
    if(s === 'running') return 'running';
    const js = (jobStatus || '').toString().toLowerCase();
    return js === 'backoff' ? 'backoff' : 'running';
  }

  function isV2ChunkTelemetry(j){
    const source = (j?.telemetry_source || '').toString().toLowerCase();
    if(source === 'v2') return true;
    const runtimeMode = (j?.debug_parallel_lanes_snapshot?.mode || '').toString().toLowerCase();
    return runtimeMode === 'v2' || !!j?.v2_parallel_enabled;
  }

  function hasLiveIdentity(ci){
    if(!ci || typeof ci !== 'object') return false;
    const hasChunk = ci.chunk_id !== undefined && ci.chunk_id !== null && ci.chunk_id !== '';
    const hasChunkAlt = ci.chunk !== undefined && ci.chunk !== null && ci.chunk !== '';
    const hasLane = ci.lane_id !== undefined && ci.lane_id !== null && ci.lane_id !== '';
    const hasLaneAlt = ci.lane !== undefined && ci.lane !== null && ci.lane !== '';
    const hasDomain = !!((ci.target_domain || ci.receiver_domain || '').toString().trim());
    return hasChunk || hasChunkAlt || hasLane || hasLaneAlt || hasDomain;
  }

  function liveChunkSort(a, b){
    const rank = (x) => (normalizeLiveChunkStatus(x?.status, '').toLowerCase() === 'running' ? 0 : 1);
    const byStatus = rank(a) - rank(b);
    if(byStatus !== 0) return byStatus;
    const laneA = Number(a?.lane_id ?? a?.lane ?? Number.MAX_SAFE_INTEGER);
    const laneB = Number(b?.lane_id ?? b?.lane ?? Number.MAX_SAFE_INTEGER);
    if(laneA !== laneB) return laneA - laneB;
    const chunkA = Number(a?.chunk_id ?? a?.chunk ?? Number.MAX_SAFE_INTEGER);
    const chunkB = Number(b?.chunk_id ?? b?.chunk ?? Number.MAX_SAFE_INTEGER);
    return chunkA - chunkB;
  }

  function getLiveChunks(j){
    const isV2 = isV2ChunkTelemetry(j);
    const active = Array.isArray(j.active_chunks_info)
      ? j.active_chunks_info
          .filter(x => hasLiveIdentity(x))
          .map(x => ({
            ...x,
            status: normalizeLiveChunkStatus(x?.status, j?.status),
            lane_id: x?.lane_id ?? x?.lane,
          }))
          .sort(liveChunkSort)
      : [];
    if(active.length) return active;

    const running = Array.isArray(j.chunk_states)
      ? j.chunk_states
          .filter(x => ['running', 'backoff'].includes((x?.status || '').toString().toLowerCase()))
          .slice(-12)
          .map(x => ({
            chunk_id: x.chunk,
            status: x.status,
            size: x.size,
            sender_mail: x.sender,
            receiver_domain: x.target_domain || x.provider_domain || '',
            spam_score: x.spam_score,
            blacklist: x.blacklist,
            lane_id: x.lane_id ?? x.lane,
            target_domain: x.target_domain || x.provider_domain || '',
          }))
          .filter(x => hasLiveIdentity(x))
          .map(x => ({ ...x, status: normalizeLiveChunkStatus(x?.status, j?.status) }))
          .sort(liveChunkSort)
      : [];
    if(running.length) return running;

    const ci = j.current_chunk_info || {};
    const ciStatus = (ci?.status || '').toString().toLowerCase();
    const hasChunkId = ci.chunk_id !== undefined && ci.chunk_id !== null && ci.chunk_id !== '';
    const hasChunkAlt = ci.chunk !== undefined && ci.chunk !== null && ci.chunk !== '';
    const hasLane = !!((ci?.lane_id ?? ci?.lane ?? '').toString());
    const canUseCurrentAsLive = isV2
      ? ((hasChunkId || hasChunkAlt) && hasLane && ['running','backoff'].includes(ciStatus))
      : hasLiveIdentity(ci);
    return canUseCurrentAsLive
      ? [{ ...ci, status: normalizeLiveChunkStatus(ci?.status, j?.status), lane_id: ci?.lane_id ?? ci?.lane }]
      : [];
  }

  function updateCard(card, j){
    const jobId = card.dataset.jobid;

    // Header pills
    const st = (j.status || '').toString();
    const stEl = qk(card,'status');
    if(stEl){
      stEl.className = statusPillClass(st);
      stEl.textContent = `Status: ${st}`;
    }

    const speedEl = qk(card,'speed');
    const spm = Number(j.speed_epm || 0);
    if(speedEl){
      speedEl.className = 'pill';
      speedEl.textContent = `${Math.round(spm)} epm`;
    }

    const etaEl = qk(card,'eta');
    if(etaEl){
      etaEl.className = 'pill';
      etaEl.textContent = fmtEta(j.eta_s);
    }

    renderTriageBadges(card, j);

    // Core counters + compact KPI values
    const asNum = (v) => {
      if(v === null || v === undefined || v === '') return null;
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };
    const fmtNum = (n) => (n === null ? '—' : String(n));
    const fmtRate = (num, den) => {
      if(num === null || den === null || den <= 0) return '—';
      const r = (num / den) * 100;
      return `${r.toFixed(2)}%`;
    };

    const totalN = asNum(j.total);
    const sentN = asNum(j.sent);
    const failedN = asNum(j.failed);
    const skippedN = asNum(j.skipped);
    const invalidN = asNum(j.invalid);
    const deliveredN = asNum(j.delivered);
    const bouncedN = asNum(j.bounced);
    const deferredN = asNum(j.deferred);
    const complainedN = asNum(j.complained);

    qk(card,'total').textContent = fmtNum(totalN);
    qk(card,'sent').textContent = fmtNum(sentN);
    qk(card,'failed').textContent = fmtNum(failedN);
    qk(card,'skipped').textContent = fmtNum(skippedN);
    qk(card,'invalid').textContent = fmtNum(invalidN);

    const elDel = qk(card,'delivered'); if(elDel) elDel.textContent = fmtNum(deliveredN);
    const elBnc = qk(card,'bounced'); if(elBnc) elBnc.textContent = fmtNum(bouncedN);
    const elDef = qk(card,'deferred'); if(elDef) elDef.textContent = fmtNum(deferredN);
    const elCmp = qk(card,'complained'); if(elCmp) elCmp.textContent = fmtNum(complainedN);

    let pendingValue = null;
    let pendingClamped = false;
    if(sentN !== null && deliveredN !== null && bouncedN !== null && deferredN !== null && complainedN !== null){
      pendingValue = sentN - (deliveredN + bouncedN + deferredN + complainedN);
      if(pendingValue < 0){
        pendingValue = 0;
        pendingClamped = true;
      }
    }
    qk(card,'pending').textContent = fmtNum(pendingValue);
    const pendingWarnEl = qk(card,'pendingWarn');
    if(pendingWarnEl) pendingWarnEl.style.display = pendingClamped ? '' : 'none';

    const rateBounceEl = qk(card,'rateBounce');
    const rateComplaintEl = qk(card,'rateComplaint');
    const rateDeferredEl = qk(card,'rateDeferred');
    if(rateBounceEl) rateBounceEl.textContent = fmtRate(bouncedN, sentN);
    if(rateComplaintEl) rateComplaintEl.textContent = fmtRate(complainedN, sentN);
    if(rateDeferredEl) rateDeferredEl.textContent = fmtRate(deferredN, sentN);

    // Progress bars
    const total = Number(j.total||0);
    const sent = Number(j.sent||0);
    const failed = Number(j.failed||0);
    const skipped = Number(j.skipped||0);
    const done = sent + failed + skipped;

    const pSend = pct(done, total);
    qk(card,'barSend').style.width = pSend + '%';
    qk(card,'progressText').textContent = `Send progress: ${pSend}% (${done}/${total})`; 

    const legacyDone = Number(j.chunks_done||0);
    const legacyTotal = Number(j.chunks_total||0);
    let chunkUniqueDone = Number(j.chunk_unique_done);
    if(!Number.isFinite(chunkUniqueDone)) chunkUniqueDone = legacyDone;
    if(!Number.isFinite(chunkUniqueDone) || chunkUniqueDone < 0) chunkUniqueDone = 0;

    let chunkUniqueTotal = Number(j.chunk_unique_total);
    if(!Number.isFinite(chunkUniqueTotal)) chunkUniqueTotal = legacyTotal;
    if(!Number.isFinite(chunkUniqueTotal) || chunkUniqueTotal < 0) chunkUniqueTotal = 0;
    if(chunkUniqueTotal < chunkUniqueDone) chunkUniqueTotal = chunkUniqueDone;

    const pChunks = pct(chunkUniqueDone, chunkUniqueTotal);
    qk(card,'barChunks').style.width = pChunks + '%';
    qk(card,'chunksText').textContent = `Chunks: ${chunkUniqueDone}/${chunkUniqueTotal} done · backoff_events=${Number(j.chunks_backoff||0)} · abandoned=${Number(j.chunks_abandoned||0)}`;
    const attemptsEl = qk(card,'attemptsText');
    if(attemptsEl){
      let attemptsTotal = Number(j.chunk_attempts_total);
      if(!Number.isFinite(attemptsTotal)) attemptsTotal = null;
      if(attemptsTotal !== null && attemptsTotal < 0) attemptsTotal = null;
      if(attemptsTotal !== null && attemptsTotal < chunkUniqueDone) attemptsTotal = chunkUniqueDone;
      const hasRetries = attemptsTotal !== null && attemptsTotal > chunkUniqueDone;
      if(hasRetries){
        attemptsEl.style.display = '';
        attemptsEl.textContent = `Attempts: ${attemptsTotal}`;
      }else{
        attemptsEl.style.display = 'none';
      }
    }

    const plan = j.domain_plan || {};
    const planTotal = Object.values(plan).reduce((a,v)=>a+Number(v||0),0);
    const dSent = j.domain_sent || {};
    const dFail = j.domain_failed || {};
    const domDone = Object.keys(plan).reduce((a,dom)=>a+Number(dSent[dom]||0)+Number(dFail[dom]||0),0);
    const pDom = pct(domDone, planTotal);
    qk(card,'barDomains').style.width = pDom + '%';
    qk(card,'domainsText').textContent = `Domains: ${pDom}% (${domDone}/${planTotal})`; 

    // Current chunk info (parallel-aware)
    const liveChunks = getLiveChunks(j);
    const ci = liveChunks[0] || (j.current_chunk_info || {});
    const cDom = j.current_chunk_domains || {};
    const activeDomainsMap = {};
    for(const row of liveChunks){
      const d = ((row?.target_domain || row?.receiver_domain || '') + '').trim().toLowerCase();
      if(!d) continue;
      activeDomainsMap[d] = Number(activeDomainsMap[d] || 0) + 1;
    }

    let chunkLine = '<div class="mini">—</div>';
    if(ci && ((ci.chunk !== undefined && ci.chunk !== null) || (ci.chunk_id !== undefined && ci.chunk_id !== null)) && Number(ci.size||0) > 0){
      const cnum = Number((ci.chunk_id ?? ci.chunk) || 0) + 1;
      const at = Number(ci.attempt||0);
      const sender = (ci.sender || ci.sender_mail || '').toString();
      const subj = (ci.subject||'').toString();
      const subjShort = subj.length > 70 ? (subj.slice(0,70) + '…') : subj;
      const spam = (ci.spam_score === null || ci.spam_score === undefined) ? '—' : Number(ci.spam_score).toFixed(2);
      const bl = (ci.blacklist || '').toString();
      const blShort = bl.length > 60 ? (bl.slice(0,60) + '…') : bl;
      const pmtaReason = (ci.pmta_reason || '').toString();
      const pmtaReasonShort = pmtaReason.length > 80 ? (pmtaReason.slice(0,80) + '…') : pmtaReason;
      let pmtaSlowShort = '';
      let adaptiveShort = '';
      try{
        const ps = ci.pmta_slow || {};
        const dmin = (ps.delay_min !== undefined && ps.delay_min !== null) ? Number(ps.delay_min) : null;
        const wmax = (ps.workers_max !== undefined && ps.workers_max !== null) ? Number(ps.workers_max) : null;
        if((dmin !== null && !Number.isNaN(dmin)) || (wmax !== null && !Number.isNaN(wmax))){
          const parts = [];
          if(dmin !== null && !Number.isNaN(dmin)) parts.push('delay≥' + dmin);
          if(wmax !== null && !Number.isNaN(wmax)) parts.push('workers≤' + wmax);
          pmtaSlowShort = parts.join(', ');
        }
      }catch(e){ /* ignore */ }

      try{
        const ah = ci.adaptive_health || {};
        if(ah && ah.ok){
          const lvl = Number(ah.level || 0);
          const reduced = !!ah.reduced;
          const action = (ah.action || '').toString();
          const ap = ah.applied || {};
          const bits = [];
          if(ap.workers !== undefined) bits.push(`w=${Number(ap.workers)}`);
          if(ap.chunk_size !== undefined) bits.push(`chunk=${Number(ap.chunk_size)}`);
          if(ap.delay_s !== undefined) bits.push(`delay=${Number(ap.delay_s)}s`);
          adaptiveShort = `health[L${lvl}${reduced ? '↓' : ''}${action ? (':' + action) : ''}${bits.length ? (' ' + bits.join(',')) : ''}]`;
        }
      }catch(e){ /* ignore */ }

      const spamN = Number(ci.spam_score);
      const spamTone = Number.isFinite(spamN) ? (spamN >= 4 ? 'bad' : (spamN >= 2 ? 'warn' : 'good')) : '';
      const hasBl = !!(blShort && blShort.trim());
      const blTone = hasBl ? 'warn' : 'good';

      const cdEntriesInlineSource = Object.keys(activeDomainsMap).length ? activeDomainsMap : cDom;
      const cdEntriesInline = Object.entries(cdEntriesInlineSource).sort((a,b)=>Number(b[1]||0)-Number(a[1]||0)).slice(0,6);
      const activeDomainsTxt = cdEntriesInline.length
        ? cdEntriesInline.map(([d,c]) => `${esc(d)}(${Number(c||0)})`).join(' · ')
        : '—';

      chunkLine = [
        (liveChunks.length > 1)
          ? `<div class="mini" style="margin-bottom:6px"><b>Live chunks:</b> ${Number(liveChunks.length)} parallel lanes active.</div>`
          : '',
        `<div class="chunkMeta">`,
          `<span class="chunkMetaPill">#️⃣ Chunk #${cnum}</span>`,
          `<span class="chunkMetaPill">📦 size=${Number(ci.size||0)}</span>`,
          `<span class="chunkMetaPill">⚙️ workers=${Number(ci.workers||0)}</span>`,
          `<span class="chunkMetaPill">⏱️ delay=${Number(ci.delay_s||0)}s</span>`,
          `<span class="chunkMetaPill">🔁 attempt=${at}</span>`,
        `</div>`,
        `<div class="chunkList">`,
          `<div class="chunkItem"><span class="chunkIcon">📧</span><div><div class="chunkLabel">Sender</div><div class="chunkValue">${esc(sender || '—')}</div></div></div>`,
          `<div class="chunkItem"><span class="chunkIcon">🧪</span><div><div class="chunkLabel">Spam / BL</div><div class="chunkValue ${spamTone}">Spam: ${esc(spam)}</div><div class="chunkValue ${blTone}">BL: ${esc(blShort || '—')}</div></div></div>`,
          `<div class="chunkItem"><span class="chunkIcon">📝</span><div><div class="chunkLabel">Subject</div><div class="chunkValue">${esc(subjShort || '—')}</div></div></div>`,
          `<div class="chunkItem"><span class="chunkIcon">🌐</span><div><div class="chunkLabel">Active domains</div><div class="chunkValue">${activeDomainsTxt}</div></div></div>`,
        `</div>`,
      ].join('') +
      (pmtaReasonShort ? (`<div class="mini chunkNote">🛰️ PMTA reason: ${esc(pmtaReasonShort)}</div>`) : '')+
      (pmtaSlowShort ? (`<div class="mini chunkNote">🐢 PMTA slow: ${esc(pmtaSlowShort)}</div>`) : '')+
      (adaptiveShort ? (`<div class="mini chunkNote chunkNoteAdaptive">🧠 Adaptive: ${esc(adaptiveShort)}</div>`) : '');
    }
    qk(card,'chunkLine').innerHTML = chunkLine;

    // active domains for current chunk
    const cdEntriesSource = Object.keys(activeDomainsMap).length ? activeDomainsMap : cDom;
    const cdEntries = Object.entries(cdEntriesSource).sort((a,b)=>Number(b[1]||0)-Number(a[1]||0)).slice(0,6);
    qk(card,'chunkDomains').innerHTML = cdEntries.length
      ? ('<div class="mini chunkNote chunkNoteDomains">🔥 Top active domains: ' + cdEntries.map(([d,c]) => `${esc(d)}(${Number(c||0)})`).join(' · ') + '</div>')
      : '<div class="mini chunkNote chunkNoteDomains">🔥 Top active domains: —</div>';

    // Backoff info (parallel-aware)
    const liveBackoffs = liveChunks
      .filter(x => normalizeLiveChunkStatus(x?.status, st) === 'backoff')
      .slice(0,5);
    const cs = (j.chunk_states || []).slice().reverse();
    let backLine = '—';
    if(liveBackoffs.length){
      const parts = liveBackoffs.map(x => {
        const next = x.next_retry_ts ? new Date(Number(x.next_retry_ts)*1000).toLocaleTimeString() : '—';
        const dom = (x.target_domain || x.receiver_domain || '').toString();
        const reason = (x.reason || '').toString();
        const reasonShort = reason.length > 64 ? (reason.slice(0,64) + '…') : reason;
        const label = `#${Number((x.chunk_id ?? x.chunk) || 0) + 1}`;
        const meta = `${dom ? (dom + ' · ') : ''}retry=${Number(x.attempt||0)} · next=${next}`;
        return `${label} (${meta}${reasonShort ? (' · ' + reasonShort) : ''})`;
      });
      const suffix = (liveBackoffs.length < (liveChunks.filter(x => normalizeLiveChunkStatus(x?.status, st) === 'backoff').length || 0)) ? ' …' : '';
      backLine = `Active backoff lanes: ${parts.join(' | ')}${suffix}`;
    }else{
      const lastBack = cs.find(x => (x.status || '') === 'backoff');
      if(lastBack){
        const next = lastBack.next_retry_ts ? new Date(Number(lastBack.next_retry_ts)*1000).toLocaleTimeString() : '';
        const rs = (lastBack.reason || '').toString();
        const rshort = rs.length > 120 ? (rs.slice(0,120) + '…') : rs;
        backLine = `Latest backoff: chunk #${Number(lastBack.chunk||0)+1} retry=${Number(lastBack.attempt||0)} · next=${next || '—'} · ${rshort}`;
      } else if((st||'').toLowerCase() === 'backoff'){
        backLine = 'Backoff active across one or more lanes (waiting for retry telemetry)…';
      }
    }
    qk(card,'backoffLine').textContent = backLine;
    // PMTA Live Panel (optional) — richer UI
    const pmEl = qk(card,'pmtaLine');
    const pmCompactEl = qk(card,'pmtaCompact');
    const pmDiagEl = qk(card,'pmtaDiag');
    const pmNoteEl = qk(card,'pmtaNote');
    if(pmNoteEl){
      pmNoteEl.innerHTML = 'Note: <b>sent</b> = accepted by PMTA (client-side). Delivery may still be queued/deferred.';
    }

    function _pmFmt(v){ return (v === null || v === undefined) ? '—' : v; }
    function _pmNum(v){
      const n = Number(v);
      return (Number.isFinite(n) ? n : null);
    }

    function _pmTone(kind, n){
      // kind: 'backlog'|'deferred'|'conns'|'pressure'
      if(n === null) return '';
      const x = Number(n);
      if(kind === 'deferred'){
        if(x >= 100) return 'bad';
        if(x > 0) return 'warn';
        return 'good';
      }
      if(kind === 'backlog'){
        // backlog usually means spool/queue accumulating
        if(x >= 50000) return 'bad';
        if(x > 0) return 'warn';
        return 'good';
      }
      if(kind === 'pressure'){
        if(x >= 3) return 'bad';
        if(x >= 1) return 'warn';
        return 'good';
      }
      // conns
      if(x >= 800) return 'warn';
      return 'good';
    }

    function _pmTrafficTone(inCount, outCount){
      const inN = _pmNum(inCount);
      const outN = _pmNum(outCount);
      if(inN === null || outN === null) return '';
      if(inN <= 0){
        if(outN <= 0) return 'warn';
        return 'good';
      }
      const ratio = outN / inN;
      if(ratio < 0.25) return 'bad';
      if(ratio <= 0.5) return 'warn';
      return 'good';
    }

    function _tagHtml(tone, label){
      const cls = tone ? ('tag ' + tone) : 'tag';
      return `<span class="${cls}">${esc(label)}</span>`;
    }

    function _box(title, tagTone, tagLabel, hint, inner){
      return `<div class="pmtaBox">`+
        `<div class="pmtaTitle"><span>${esc(title)}</span>${tagLabel ? _tagHtml(tagTone, tagLabel) : ''}</div>`+
        (hint ? `<div class="pmtaHint">${esc(hint)}</div>` : '')+
        (inner || '')+
      `</div>`;
    }

    function _kv(k, v, tone, big){
      const cls = 'pmtaVal' + (tone ? (' ' + tone) : '') + (big ? ' pmtaBig' : '');
      return `<div class="pmtaRow"><span class="pmtaKey">${esc(k)}</span><span class="${cls}">${esc(String(v))}</span></div>`;
    }

    function _renderPmtaPanel(pm, pr){
      if(!pm || !pm.enabled){
        const why = (pm && pm.reason) ? String(pm.reason) : '';
        return `<div class="pmtaBanner warn">PMTA: disabled${why ? (`<br><span class="muted">${esc(why)}</span>`) : ''}</div>`;
      }
      if(!pm.ok){
        const why = (pm.reason || 'unreachable').toString();
        return `<div class="pmtaBanner bad">PMTA monitor unreachable<br><span class="muted">${esc(why)}</span></div>`;
      }

      const spR = _pmFmt(pm.spool_recipients);
      const spM = _pmFmt(pm.spool_messages);
      const qR  = _pmFmt(pm.queued_recipients);
      const qM  = _pmFmt(pm.queued_messages);
      const con = _pmFmt(pm.active_connections);
      const conIn = _pmFmt(pm.smtp_in_connections);
      const conOut = _pmFmt(pm.smtp_out_connections);
      const hrIn = _pmFmt(pm.traffic_last_hr_in);
      const hrOut = _pmFmt(pm.traffic_last_hr_out);
      const minIn = _pmFmt(pm.traffic_last_min_in);
      const minOut = _pmFmt(pm.traffic_last_min_out);
      const ts  = pm.ts ? String(pm.ts) : '';

      const spR_n = _pmNum(pm.spool_recipients);
      const qR_n  = _pmNum(pm.queued_recipients);
      const con_n = _pmNum(pm.active_connections);
      const hrIn_n = _pmNum(pm.traffic_last_hr_in);
      const hrOut_n = _pmNum(pm.traffic_last_hr_out);
      const minIn_n = _pmNum(pm.traffic_last_min_in);
      const minOut_n = _pmNum(pm.traffic_last_min_out);

      const toneSp = _pmTone('backlog', spR_n);
      const toneQ  = _pmTone('backlog', qR_n);
      const toneHr = _pmTrafficTone(hrIn_n, hrOut_n);
      const toneMin = _pmTrafficTone(minIn_n, minOut_n);
      const toneC  = _pmTone('conns', con_n);

      // top queues
      let topTxt = '—';
      try{
        const tqs = Array.isArray(pm.top_queues) ? pm.top_queues : [];
        if(tqs.length){
          const top = tqs.slice(0, 4).map(x => {
            const qn = (x.queue ?? '').toString();
            const dm = (x.domain ?? '').toString();
            const rr = (x.recipients ?? 0);
            const dd = (x.deferred ?? 0);
            const le = (x.last_error ?? '').toString();
            const base = `${qn}=${rr}` + (dd ? (`(def:${dd})`) : '');
            const domPart = dm ? (` [${dm}]`) : '';
            const errPart = le ? (` · err: ${le.slice(0,70)}`) : '';
            return base + domPart + errPart;
          });
          topTxt = top.join(' · ');
        }
      }catch(e){ topTxt = '—'; }

      const html = `
        <div class="pmtaGrid">
          ${_box('Spool', toneSp, 'rcpt', 'Total recipients/messages currently held by PMTA spool.', _kv('RCPT', spR, toneSp, true) + _kv('MSG', spM, toneSp, false))}
          ${_box('Queue', toneQ, 'rcpt', 'Recipients/messages still queued to be delivered.', _kv('RCPT', qR, toneQ, true) + _kv('MSG', qM, toneQ, false))}
          ${_box('Connections', toneC, '', 'Live SMTP sessions used for inbound/outbound traffic.', _kv('SMTP In', conIn, toneC, true) + _kv('SMTP Out', conOut, toneC, true) + _kv('Total', con, toneC, false))}
          ${_box('Last minute', toneMin, '', 'Recent PMTA throughput over the last 60 seconds.', _kv('In', minIn, toneMin, true) + _kv('Out', minOut, toneMin, true) + `<div class="pmtaSub">traffic recipients / minute</div>`)}
          ${_box('Last hour', toneHr, '', 'Rolling traffic totals for the previous 60 minutes.', _kv('In', hrIn, toneHr, true) + _kv('Out', hrOut, toneHr, true) + `<div class="pmtaSub">traffic recipients / hour</div>`)}
          ${_box('Top queues', (topTxt === '—' ? 'good' : 'warn'), '', 'Queues with the highest recipient backlog and latest queue errors.', `<div class="pmtaSub">${esc(topTxt)}</div>`)}
          ${_box('Time', 'good', '', 'Timestamp of the latest PMTA snapshot used for this panel.', `<div class="pmtaSub">${esc(ts || '—')}</div>`)}
        </div>
      `;
      return html;
    }

    function _renderPmtaCompact(pm){
      if(!pm || !pm.enabled || !pm.ok) return 'PMTA: —';
      const queue = _pmNum(pm.queued_recipients);
      const minOut = _pmNum(pm.traffic_last_min_out);
      const hrOut = _pmNum(pm.traffic_last_hr_out);
      if(queue === null && minOut === null && hrOut === null) return 'PMTA: —';
      return `Queue: ${_pmFmt(queue)} | last min out: ${_pmFmt(minOut)} | last hour out: ${_pmFmt(hrOut)}`;
    }

    if(pmEl){
      const pm = j.pmta_live || null;
      const pr = j.pmta_pressure || null;
      pmEl.innerHTML = _renderPmtaPanel(pm, pr);
    }
    if(pmCompactEl){
      const pm = j.pmta_live || null;
      pmCompactEl.textContent = _renderPmtaCompact(pm);
    }

    // PMTA diagnostics snapshot (point 7)

    if(pmDiagEl){
      const d = j.pmta_diag || {};
      if(d && d.enabled && d.ok){
        const cls = (d.class || '');
        const dom = (d.domain || '');
        const def = (d.queue_deferrals ?? '—');
        const err = (d.queue_errors ?? '—');
        const hint = (d.remote_hint || '');
        const samp = Array.isArray(d.errors_sample) ? d.errors_sample.slice(0,2).join(' / ') : '';
        pmDiagEl.innerHTML = [
          `<span class="chunkMetaPill">Diag</span>`,
          `<span class="chunkMetaPill">class=${esc(cls || '—')}</span>`,
          `<span class="chunkMetaPill">dom=${esc(dom || '—')}</span>`,
          `<span class="chunkMetaPill">def=${esc(String(def))}</span>`,
          `<span class="chunkMetaPill">err=${esc(String(err))}</span>`,
          hint ? `<span class="chunkMetaPill">hint=${esc(hint)}</span>` : '',
          samp ? `<span class="chunkMetaPill">sample=${esc(samp)}</span>` : ''
        ].join('');
      } else if(d && d.enabled && !d.ok) {
        pmDiagEl.innerHTML = `<span class="chunkMetaPill">Diag: ${esc(String(d.reason || '—'))}</span>`;
      } else {
        pmDiagEl.innerHTML = '<span class="chunkMetaPill">Diag: —</span>';
      }
    }

    // 6) Counters
    const counters = [
      `safe_total=${Number(j.safe_list_total||0)}`,
      `safe_invalid=${Number(j.safe_list_invalid||0)}`,
      `invalid_filtered=${Number(j.invalid||0)}`,
      `skipped=${Number(j.skipped||0)}`,
      `backoff_events=${Number(j.chunks_backoff||0)}`,
      `abandoned_chunks=${Number(j.chunks_abandoned||0)}`,
      `paused=${j.paused ? 'yes' : 'no'}`,
      `stop_requested=${j.stop_requested ? 'yes' : 'no'}`
    ];
    qk(card,'counters').textContent = counters.join(' · ');

    // Outcomes panel + trend (last ~20 minutes)
    const outEl = qk(card,'outcomes');
    const trEl = qk(card,'outcomeTrend');
    if(outEl){
      const ts = (j.accounting_last_ts || '').toString();
      const deliveredN = Number(j.delivered||0);
      const bouncedN = Number(j.bounced||0);
      const deferredN = Number(j.deferred||0);
      const complainedN = Number(j.complained||0);
      const sentN = Number(j.sent||0);
      const pendingByOutcome = Math.max(0, sentN - deliveredN - bouncedN - complainedN);
      const queuedNow = Number((((j.pmta_live || {}).queued_recipients) ?? 0) || 0);
      outEl.innerHTML = `
        <div class="outcomesGrid">
          <div class="outChip del"><span class="k">Delivered</span><span class="v">${deliveredN}</span></div>
          <div class="outChip bnc"><span class="k">Bounced</span><span class="v">${bouncedN}</span></div>
          <div class="outChip def"><span class="k">Deferred</span><span class="v">${deferredN}</span></div>
          <div class="outChip cmp"><span class="k">Complained</span><span class="v">${complainedN}</span></div>
        </div>
        <div class="outMeta">Pending (sent - final outcomes): <b>${pendingByOutcome}</b> · PMTA queue now: <b>${queuedNow}</b></div>
        <div class="outMeta">${ts ? (`Last accounting update: ${esc(ts)}`) : 'Last accounting update: —'}</div>
      `;
    }
    function spark(vals){
      const chars = '▁▂▃▄▅▆▇█';
      const mx = Math.max(1, ...vals.map(v=>Number(v||0)));
      return vals.map(v => {
        const x = Number(v||0);
        const idx = Math.max(0, Math.min(chars.length-1, Math.round((x/mx)*(chars.length-1))));
        return chars[idx];
      }).join('');
    }
    if(trEl){
      const s = Array.isArray(j.outcome_series) ? j.outcome_series : [];
      const tail = s.slice(-20);
      const delV = tail.map(x=>Number(x.delivered||0));
      const bncV = tail.map(x=>Number(x.bounced||0));
      const defV = tail.map(x=>Number(x.deferred||0));
      const cmpV = tail.map(x=>Number(x.complained||0));
      if(tail.length){
        trEl.innerHTML = [
          `<span class="trendHead">Trend</span>`,
          `<span class="trendSeg del"><span class="lbl">DEL</span><span class="spark">${esc(spark(delV))}</span></span>`,
          `<span class="trendSeg bnc"><span class="lbl">BNC</span><span class="spark">${esc(spark(bncV))}</span></span>`,
          `<span class="trendSeg def"><span class="lbl">DEF</span><span class="spark">${esc(spark(defV))}</span></span>`,
          `<span class="trendSeg cmp"><span class="lbl">CMP</span><span class="spark">${esc(spark(cmpV))}</span></span>`
        ].join(' ');
      } else {
        trEl.textContent = 'Trend · —';
      }
    }

    const logsEl = qk(card,'jobLogs');
    if(logsEl){
      const lines = Array.isArray(j.logs) ? j.logs : [];
      if(lines.length){
        logsEl.innerHTML = lines.slice(-20).map((line) => `• ${esc(String(line))}`).join('<br>');
      }else{
        logsEl.textContent = '—';
      }
    }
    renderSendJobsDebugTerminal(card, j);

    // 5) Top domains
    renderTopDomains(card, j);

    // 7) Error types + last errors (legacy section)
    renderErrorTypes(card, j);

    // Structured issue blocks
    renderIssueBlocks(card, j);

    // 8) Chunk history
    renderChunkLive(card, j);
    renderChunkHist(card, j);

    // 10) Alerts (simple)
    const alertsEl = qk(card,'alerts');
    const failRatio = (done > 0) ? (failed / done) : 0;
    const nearSpam = cs.find(x => (x.spam_score !== null && x.spam_score !== undefined && Number(x.spam_score) > (Number(j.spam_threshold||4) * 0.9)));

    const alerts = [];
    if((st||'').toLowerCase() === 'backoff') alerts.push('⚠ backoff');
    if(Number(j.chunks_abandoned||0) > 0) alerts.push('❌ abandoned chunks');
    if(done >= 20 && failRatio >= 0.1) alerts.push('⚠ high fail rate');
    if(nearSpam) alerts.push('⚠ spam near limit');

    const quickEl = qk(card,'quickIssues');
    if(alerts.length){
      const txt = 'Quick issues: ' + alerts.join(' · ');
      alertsEl.textContent = txt;
      alertsEl.style.display = '';
      if(quickEl) quickEl.textContent = txt;
    }else{
      alertsEl.textContent = '';
      alertsEl.style.display = 'none';
      if(quickEl) quickEl.textContent = '';
    }

    // Notifications
    const pm = j.pmta_live || null;
    const pmStateNow = (pm && pm.enabled)
      ? (pm.ok ? 'ok' : 'bad')
      : 'disabled';
    const pmStatePrev = state.lastPmtaMonitor[jobId];
    if(pmStatePrev !== pmStateNow){
      if(pmStateNow === 'ok'){
        toast('✅ PowerMTA Monitor connected', `Job ${jobId}: Live monitor connection is active.`, 'good');
      }else if(pmStateNow === 'bad'){
        toast('❌ PowerMTA Monitor disconnected', `Job ${jobId}: ${pm?.reason || 'Monitor unreachable.'}`, 'bad');
      }
      state.lastPmtaMonitor[jobId] = pmStateNow;
    }

    const prevStatus = state.lastStatus[jobId];
    if(prevStatus && prevStatus !== st){
      if((st||'').toLowerCase() === 'backoff') toast('Backoff', `Job ${jobId} entered backoff.`, 'warn');
      if((st||'').toLowerCase() === 'done') toast('Done', `Job ${jobId} finished.`, 'good');
      if((st||'').toLowerCase() === 'error') toast('Error', `Job ${jobId} errored: ${j.last_error || ''}`, 'bad');
      if((st||'').toLowerCase() === 'stopped') toast('Stopped', `Job ${jobId} stopped: ${j.stop_reason || ''}`, 'warn');
      if((st||'').toLowerCase() === 'paused') toast('Paused', `Job ${jobId} paused.`, 'warn');
      if((st||'').toLowerCase() === 'running' && (prevStatus||'').toLowerCase() === 'paused') toast('Resumed', `Job ${jobId} resumed.`, 'good');
    }
    state.lastStatus[jobId] = st;

    const prevAb = Number(state.lastAbandoned[jobId] || 0);
    const abNow = Number(j.chunks_abandoned || 0);
    if(abNow > prevAb){
      toast('Abandoned chunk', `Job ${jobId}: abandoned_chunks=${abNow}`, 'bad');
    }
    state.lastAbandoned[jobId] = abNow;

    const prevBf = Number(state.lastBackoff[jobId] || 0);
    const bfNow = Number(j.chunks_backoff || 0);
    if(bfNow > prevBf){
      toast('Backoff event', `Job ${jobId}: backoff_events=${bfNow}`, 'warn');
    }
    state.lastBackoff[jobId] = bfNow;

    const prevFail = Number(state.lastFailed[jobId] || 0);
    const failNow = Number(j.failed || 0);
    if(failNow > prevFail && done >= 20 && failRatio >= 0.1){
      toast('High fail rate', `Job ${jobId}: failed=${failNow}/${done} (${Math.round(failRatio*100)}%)`, 'warn');
    }
    state.lastFailed[jobId] = failNow;

    // Adaptive pressure toasts (health/accounting-driven)
    try{
      const liveRef = getLiveChunks(j);
      const adaptiveRef = liveRef.find(x => x && x.adaptive_health && x.adaptive_health.ok) || liveRef[0] || (j.current_chunk_info || {});
      const ah = (adaptiveRef && adaptiveRef.adaptive_health) ? adaptiveRef.adaptive_health : null;
      if(ah && ah.ok){
        const targetDomain = ((adaptiveRef && (adaptiveRef.target_domain || adaptiveRef.receiver_domain)) || '').toString();
        const signature = [
          Number(ah.level || 0),
          !!ah.reduced,
          (ah.action || '').toString(),
          JSON.stringify(ah.applied || {}),
          (ah.reason || '').toString(),
          targetDomain
        ].join('|');
        if(signature && state.lastAdaptive[jobId] !== signature){
          if(ah.reduced){
            const ap = ah.applied || {};
            toast(
              'Adaptive throttle',
              `Job ${jobId}${targetDomain ? (' · ' + targetDomain) : ''}: reduced pressure (L${Number(ah.level||0)}) · workers=${Number(ap.workers||0)} chunk=${Number(ap.chunk_size||0)} delay=${Number(ap.delay_s||0)}s`,
              'warn'
            );
          }else if((ah.action || '') === 'speed_up'){
            toast('Adaptive speed-up', `Job ${jobId}: healthy delivery, increasing throughput gradually.`, 'good');
          }
          state.lastAdaptive[jobId] = signature;
        }
      }
    }catch(e){ /* ignore */ }

    // Route/IP/domain switch toast per provider domain
    try{
      const routeRows = getLiveChunks(j);
      const seenRouteKeys = new Set();
      for(const ci2 of routeRows){
        const pDom = (ci2.target_domain || ci2.receiver_domain || '').toString();
        const senderNow = (ci2.sender || ci2.sender_mail || '').toString();
        if(!pDom || !senderNow) continue;
        const key = `${jobId}:${pDom}`;
        if(seenRouteKeys.has(key)) continue;
        seenRouteKeys.add(key);
        const prevSender = (state.lastRoute[key] || '').toString();
        if(prevSender && prevSender !== senderNow){
          toast('Route switched', `Provider ${pDom}: switched sender/IP from ${prevSender} to ${senderNow}.`, 'warn');
        }
        state.lastRoute[key] = senderNow;
      }
    }catch(e){ /* ignore */ }

    // Disable/enable controls based on state
    const btnPause = card.querySelector('[data-action="pause"]');
    const btnResume = card.querySelector('[data-action="resume"]');
    const btnStop = card.querySelector('[data-action="stop"]');
    if(btnPause) btnPause.disabled = !!j.paused || (st||'').toLowerCase() === 'done' || (st||'').toLowerCase() === 'error' || (st||'').toLowerCase() === 'stopped';
    if(btnResume) btnResume.disabled = !j.resumable || !j.paused || (st||'').toLowerCase() === 'done' || (st||'').toLowerCase() === 'stopped';
    if(btnStop) btnStop.disabled = (st||'').toLowerCase() === 'done' || (st||'').toLowerCase() === 'error' || (st||'').toLowerCase() === 'stopped';

    state.lastJobPayload[jobId] = j;
    renderBridgeReceiver(card, j, state.latestBridgeState);
    applyFiltersAndSort();
  }

  function renderSendJobsDebugTerminal(card, j){
    const bodyEl = qk(card, 'sendJobsDebugTerminal');
    const metaEl = qk(card, 'debugTerminalMeta');
    if(!bodyEl) return;
    const relation = Array.isArray(j.send_job_relation_logs) ? j.send_job_relation_logs : [];
    const logs = Array.isArray(j.logs) ? j.logs : [];
    const sendDbg = (j.send_debug && typeof j.send_debug === 'object') ? j.send_debug : {};
    const headerBits = [];
    if(sendDbg.campaign_id) headerBits.push(`campaign=${sendDbg.campaign_id}`);
    if(sendDbg.job_id) headerBits.push(`job=${sendDbg.job_id}`);
    if(sendDbg.from_email) headerBits.push(`from=${sendDbg.from_email}`);
    if(sendDbg.smtp_host) headerBits.push(`smtp=${sendDbg.smtp_host}`);
    const merged = [];
    if(headerBits.length){
      merged.push(`[DEBUG] [send_job_context] ${headerBits.join(' · ')}`);
    }
    merged.push(...relation);
    merged.push(...logs);
    const unique = [];
    const seen = new Set();
    merged.forEach((line) => {
      const txt = String(line || '').trim();
      if(!txt) return;
      const key = txt.toLowerCase();
      if(seen.has(key)) return;
      seen.add(key);
      unique.push(txt);
    });
    if(unique.length){
      bodyEl.innerHTML = unique.slice(-120).map((line) => `<span class="line">$ ${esc(line)}</span>`).join('');
      if(metaEl){
        metaEl.textContent = `${unique.length} merged debug/log lines`;
      }
    }else{
      bodyEl.textContent = '—';
      if(metaEl){
        metaEl.textContent = 'waiting for logs…';
      }
    }
  }

  async function tickCard(card){
    const jobId = card.dataset.jobid;
    if(!jobId) return;
    try{
      const r = await fetch(`/api/job/${jobId}`);
      const j = await r.json().catch(()=>({}));
      if(r.ok && j && !j.error){
        updateCard(card, j);
      }
    }catch(e){
      // ignore
    }
  }

  function bindControls(card){
    const jobId = card.dataset.jobid;
    if(!jobId) return;
    const btns = card.querySelectorAll('button[data-action]');
    btns.forEach(b => {
      b.addEventListener('click', () => {
        const action = b.getAttribute('data-action');
        if(action === 'delete'){
          deleteJob(jobId, card);
          return;
        }
        controlJob(jobId, action);
      });
    });
  }

  function bindDetailState(card){
    const jobId = card.dataset.jobid;
    const more = card.querySelector('details.more');
    if(!jobId || !more) return;
    const storageKey = `jobs-more-${jobId}`;
    try{
      if(sessionStorage.getItem(storageKey) === '1'){
        more.open = true;
      }
    }catch(e){ /* ignore */ }
    more.addEventListener('toggle', () => {
      try{
        sessionStorage.setItem(storageKey, more.open ? '1' : '0');
      }catch(e){ /* ignore */ }
    });
  }

  function updateFilterUrl(){
    try{
      const u = new URL(window.location.href);
      const keep = (key, val) => {
        if(!val || val === 'all' || (key === 'sort' && val === 'newest')) u.searchParams.delete(key);
        else u.searchParams.set(key, val);
      };
      keep('status', state.filters.status);
      keep('mode', state.filters.mode);
      keep('risk', state.filters.risk);
      keep('provider', state.filters.provider);
      keep('sort', state.filters.sort);
      history.replaceState(null, '', `${u.pathname}?${u.searchParams.toString()}`.replace(/\?$/, ''));
    }catch(e){ /* ignore */ }
  }

  function restoreFiltersFromQuery(){
    try{
      const p = new URLSearchParams(window.location.search || '');
      const get = (k, d) => (p.get(k) || d).toString().trim().toLowerCase();
      const status = get('status', 'all');
      const mode = get('mode', 'all');
      const risk = get('risk', 'all');
      const provider = get('provider', 'all');
      const sort = get('sort', 'newest');
      state.filters.status = ['all','running','done','paused','backoff','stop'].includes(status) ? status : 'all';
      state.filters.mode = ['all','counts','legacy'].includes(mode) ? mode : 'all';
      state.filters.risk = ['all','internal_degraded','deliverability_high','stale'].includes(risk) ? risk : 'all';
      state.filters.provider = ['all','gmail','yahoo','outlook','icloud','other'].includes(provider) ? provider : 'all';
      state.filters.sort = ['newest','highest_risk','stalest'].includes(sort) ? sort : 'newest';
    }catch(e){ /* ignore */ }
  }

  function syncFilterInputs(){
    const bind = (id, key) => {
      const el = document.getElementById(id);
      if(!el) return;
      el.value = state.filters[key];
      el.addEventListener('change', () => {
        state.filters[key] = (el.value || 'all').toString().trim().toLowerCase();
        applyFiltersAndSort();
        updateFilterUrl();
      });
    };
    bind('fltStatus', 'status');
    bind('fltMode', 'mode');
    bind('fltRisk', 'risk');
    bind('fltProvider', 'provider');
    bind('fltSort', 'sort');
  }

  function passesRiskFilter(j){
    if(state.filters.risk === 'all') return true;
    if(state.filters.risk === 'internal_degraded') return hasInternalDegraded(j);
    if(state.filters.risk === 'deliverability_high') return hasDeliverabilityHigh(j);
    if(state.filters.risk === 'stale') return isStaleJob(j);
    return true;
  }

  function applyFiltersAndSort(){
    const rows = cards.map((card, idx) => {
      const jobId = (card.dataset.jobid || '').toString();
      const fallbackStatus = ((qk(card, 'status') && qk(card, 'status').textContent) || '').toString().trim().toLowerCase();
      const j = state.lastJobPayload[jobId] || { status: fallbackStatus, created_at: card.dataset.created || '' };
      return { card, idx, job: j };
    });

    const visible = [];
    for(const row of rows){
      const j = row.job || {};
      const statusOk = state.filters.status === 'all' || normalizeJobStatus(j) === state.filters.status;
      const modeOk = state.filters.mode === 'all' || normalizeBridgeMode(j) === state.filters.mode;
      const riskOk = passesRiskFilter(j);
      const providerOk = state.filters.provider === 'all' || detectProviderBucket(j) === state.filters.provider;
      const keep = statusOk && modeOk && riskOk && providerOk;
      row.card.style.display = keep ? '' : 'none';
      if(keep) visible.push(row);
    }

    const createdMs = (row) => {
      const ms = tsToMs(row.job.created_at || row.card.dataset.created || '');
      return Number.isFinite(ms) ? ms : 0;
    };
    const staleMin = (row) => {
      const v = freshnessMinutes(row.job);
      return Number.isFinite(v) ? v : -1;
    };
    visible.sort((a,b) => {
      if(state.filters.sort === 'highest_risk'){
        const d = riskRank(b.job) - riskRank(a.job);
        if(d !== 0) return d;
      }else if(state.filters.sort === 'stalest'){
        const d = staleMin(b) - staleMin(a);
        if(d !== 0) return d;
      }
      const byNew = createdMs(b) - createdMs(a);
      if(byNew !== 0) return byNew;
      return a.idx - b.idx;
    });

    const parent = cards[0] ? cards[0].parentElement : null;
    if(parent){
      for(const row of visible){ parent.appendChild(row.card); }
    }

    const empty = document.getElementById('jobsFilteredEmpty');
    if(empty) empty.style.display = (cards.length > 0 && visible.length === 0) ? '' : 'none';

    const listEmpty = document.getElementById('jobsListEmpty');
    if(listEmpty){
      listEmpty.style.display = cards.length === 0 ? '' : 'none';
      const mini = listEmpty.querySelector('.mini');
      if(mini && cards.length === 0){
        const important = (state.latestDiagnostics || []).filter(x => x && x.status !== 'good').slice(0, 3);
        if(important.length){
          mini.innerHTML = `No jobs yet.<br>${important.map((row) => `• ${esc((row.key || '').replaceAll('_', ' '))}: ${esc(row.reason || '—')}`).join('<br>')}`;
        }else{
          mini.textContent = 'No jobs yet.';
        }
      }
    }

    const meta = document.getElementById('filterMeta');
    if(meta){
      const total = cards.length;
      const shown = visible.length;
      meta.textContent = shown === total
        ? `Showing all ${total} job${total === 1 ? '' : 's'}.`
        : `Showing ${shown} of ${total} job${total === 1 ? '' : 's'}.`;
    }
  }

  function setFilterDrawerOpen(open){
    const isOpen = !!open;
    document.body.classList.toggle('filterMenuOpen', isOpen);
    const drawer = document.getElementById('jobsFilterDrawer');
    if(drawer) drawer.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
  }

  function bindFilterDrawer(){
    const btn = document.getElementById('btnToggleFilters');
    const backdrop = document.getElementById('jobsFilterBackdrop');
    if(btn){
      btn.addEventListener('click', () => {
        const isOpen = document.body.classList.contains('filterMenuOpen');
        setFilterDrawerOpen(!isOpen);
      });
    }
    if(backdrop){
      backdrop.addEventListener('click', () => setFilterDrawerOpen(false));
    }
    document.addEventListener('keydown', (ev) => {
      if(ev.key === 'Escape') setFilterDrawerOpen(false);
    });
  }

  restoreFiltersFromQuery();
  syncFilterInputs();
  bindFilterDrawer();

  let cards = Array.from(document.querySelectorAll('.job[data-jobid]'));
  cards.forEach(bindControls);
  cards.forEach(bindDetailState);

  async function tickAll(){
    await tickSystemDiagnostics();
    for(const c of cards){
      await tickCard(c);
    }
    applyFiltersAndSort();
  }

  async function tickSystemDiagnostics(){
    try{
      const r = await fetch('/api/jobs');
      const j = await r.json().catch(()=>({}));
      if(r.ok && j){
        state.latestDiagnostics = Array.isArray(j.diagnostics) ? j.diagnostics : [];
        renderSystemDiagnostics(state.latestDiagnostics);
      }
    }catch(e){
      state.latestDiagnostics = [
        {key: 'jobs_api', status: 'bad', reason: 'Unable to fetch /api/jobs diagnostics.'}
      ];
      renderSystemDiagnostics(state.latestDiagnostics);
    }
  }

  async function bridgeDebugTick(){
    try{
      for(const card of cards){
        const jid = (card.dataset.jobid || "").toString();
        if(!jid) continue;
        const r = await fetch(`/api/accounting/ssh/status?job_id=${encodeURIComponent(jid)}`);
        const j = await r.json().catch(()=>({}));
        if(r.ok && j && j.ok && j.bridge){
          const b = j.bridge || {};
          state.latestBridgeState = b;
          const snapshot = state.lastJobPayload[jid];
          renderBridgeConnectionBadge(card, b, snapshot);
          if(snapshot) renderBridgeReceiver(card, snapshot, b);
          console.log('[Bridge↔Shiva Debug]', {
            job_id: jid,
            connected: !!b.connected,
            last_ok: !!b.last_ok,
            last_error: b.last_error || '',
            last_attempt_ts: b.last_attempt_ts || '',
            last_success_ts: b.last_success_ts || '',
            attempts: Number(b.attempts || 0),
            success_count: Number(b.success_count || 0),
            failure_count: Number(b.failure_count || 0),
            req_url: b.last_req_url || b.pull_url_masked || '',
            bridge_return_keys: Array.isArray(b.last_response_keys) ? b.last_response_keys : [],
            bridge_return_count: Number(b.last_bridge_count || 0),
            processed_by_shiva: Number(b.last_processed || 0),
            accepted_by_shiva: Number(b.last_accepted || 0),
            lines_sample: Array.isArray(b.last_lines_sample) ? b.last_lines_sample : [],
            duration_ms: Number(b.last_duration_ms || 0),
          });
        } else {
          console.warn('[Bridge↔Shiva Debug] bridge status failed', {job_id: jid, http_status: r.status, payload: j});
        }
      }
    }catch(e){
      state.latestBridgeState = null;
      cards.forEach(card => {
        const jid = (card.dataset.jobid || "").toString();
        const snapshot = state.lastJobPayload[jid] || {};
        renderBridgeConnectionBadge(card, null, snapshot);
        renderBridgeReceiver(card, snapshot, null);
      });
      console.error('[Bridge↔Shiva Debug] bridge status exception', e);
    }
  }

  function _fmtTsAge(ts){
    const raw = (ts || '').toString().trim();
    if(!raw) return '—';
    const mins = ageMin(raw);
    if(mins === null) return esc(raw);
    if(mins < 1) return `${esc(raw)} (just now)`;
    if(mins < 60) return `${esc(raw)} (${mins}m ago)`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${esc(raw)} (${h}h ${m}m ago)`;
  }

  function _shortCursor(v){
    const raw = (v || '').toString().trim();
    if(!raw) return '—';
    if(raw.length <= 44) return raw;
    return `${raw.slice(0, 22)}…${raw.slice(-16)}`;
  }

  function renderBridgeReceiver(card, j, b){
    const el = qk(card, 'bridgeReceiver');
    if(!el){ return; }

    const modeRaw = (j && j.bridge_mode ? j.bridge_mode : (b && b.bridge_mode ? b.bridge_mode : 'counts')).toString().trim().toLowerCase();
    const isLegacy = modeRaw === 'legacy';
    const isCounts = !isLegacy;

    const pollSuccessTs = (j && j.bridge_last_success_ts) || (b && b.last_success_ts) || '';
    const accountingTs = (j && j.accounting_last_update_ts) || (j && j.accounting_last_ts) || '';

    if(isCounts){
      el.innerHTML = [
        'Data source: <b>Bridge snapshot</b>',
        `Last poll success: <b>${_fmtTsAge(pollSuccessTs)}</b>`,
        `Last accounting update: <b>${_fmtTsAge(accountingTs)}</b>`,
      ].join('<br>');
      return;
    }

    const hasMore = !!(j && j.bridge_has_more);
    const cursorShort = _shortCursor((j && j.bridge_last_cursor) || '');
    const received = Number((j && j.received) || 0);
    const ingested = Number((j && j.ingested) || 0);
    const duplicates = Number((j && j.duplicates_dropped) || 0);
    const notFound = Number((j && j.job_not_found) || 0);
    const lagSecRaw = Number(j && j.ingestion_lag_seconds);
    const lagMins = Number.isFinite(lagSecRaw) && lagSecRaw >= 0
      ? Math.floor(lagSecRaw / 60)
      : ageMin((j && j.ingestion_last_event_ts) || '');
    const lagTxt = (lagMins === null) ? '—' : (lagMins <= 1 ? 'caught up' : `${lagMins}m`);

    el.innerHTML = [
      'Data source: <b>Event ingestion</b>',
      `Cursor progress: has_more=<b>${hasMore ? 'yes' : 'no'}</b> · last_cursor=<code>${esc(cursorShort)}</code>`,
      `Ingestion stats: received=<b>${received}</b> · ingested=<b>${ingested}</b> · duplicates=<b>${duplicates}</b> · job_not_found=<b>${notFound}</b>`,
      `Ingestion last event: <b>${_fmtTsAge((j && j.ingestion_last_event_ts) || '')}</b> · lag: <b>${esc(lagTxt)}</b>`,
    ].join('<br>');
  }


  document.getElementById('btnRefreshAll')?.addEventListener('click', tickAll);

  applyFiltersAndSort();
  tickAll();
  bridgeDebugTick();
  setInterval(tickAll, 1200);
  setInterval(bridgeDebugTick, 5000);
</script>

</body></html>
"""



# ---------------------------------------------------------------------------
# Fake data seed
# ---------------------------------------------------------------------------
NOW = datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


RUNTIME_UPDATES_ENABLED = os.getenv("NIBIRU_RUNTIME_UPDATES", "1").strip().lower() not in {"0", "false", "off", "no"}


def _append_job_event(job: dict, event: str, message: str, level: str = "INFO", min_interval_s: int = 0) -> None:
    if not isinstance(job, dict):
        return
    logs = job.setdefault("runtime_logs", [])
    if not isinstance(logs, list):
        logs = []
        job["runtime_logs"] = logs
    if min_interval_s > 0:
        gate = job.setdefault("_event_last_ts", {})
        if not isinstance(gate, dict):
            gate = {}
            job["_event_last_ts"] = gate
        now_ts = datetime.now(timezone.utc).timestamp()
        last_ts = gate.get(event)
        if isinstance(last_ts, (int, float)) and (now_ts - float(last_ts)) < min_interval_s:
            return
        gate[event] = now_ts
    line = f"[{level}] [{event}] {message}"
    if not logs or logs[-1] != line:
        logs.append(line)
    job["runtime_logs"] = logs[-40:]


def _set_job_diagnostic(job: dict, key: str, status: str, reason: str, expected: bool | None = None) -> None:
    if not isinstance(job, dict):
        return
    diagnostics = job.setdefault("diagnostics", {})
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        job["diagnostics"] = diagnostics
    entry = {"status": str(status or "unknown"), "reason": str(reason or "").strip(), "updated_at": iso(datetime.now(timezone.utc))}
    if expected is not None:
        entry["expected"] = bool(expected)
    diagnostics[key] = entry


PMTA_ACCOUNTING_DIR = Path("/var/log/pmta")
PMTA_ACCOUNTING_FILE = PMTA_ACCOUNTING_DIR / "acct.csv"
PMTA_COMMANDS_REFERENCE = Path(__file__).with_name("pmta_cli_commands_reference.txt")
PMTA_FAKE_ROWS = [
    ["d", "2026-03-22 11:04:12", "2026-03-22 11:04:11", "hello@brand-alpha.com", "mona@gmail.com", "", "success", "250 2.0.0 accepted", "queued for delivery", "gmail-smtp-in.l.google.com", "2.0.0", "smtp", "mx-a", "esmtp", "198.51.100.21", "74.125.27.26", "starttls", "18210", "pool-a", "job-240301-a", "campaign/ramadan"],
    ["d", "2026-03-22 11:05:36", "2026-03-22 11:05:34", "hello@brand-alpha.com", "saad@gmail.com", "", "relayed", "250 2.0.0 relayed", "queued for delivery", "gmail-smtp-in.l.google.com", "2.0.0", "smtp", "mx-a", "esmtp", "198.51.100.21", "74.125.27.27", "starttls", "17642", "pool-a", "job-240301-a", "campaign/ramadan"],
    ["b", "2026-03-22 11:06:05", "2026-03-22 11:06:03", "info@brand-beta.net", "nora@yahoo.com", "", "failed", "550 5.7.1 Message blocked due to spam content", "spam complaint pattern", "mta5.am0.yahoodns.net", "5.7.1", "smtp", "mx-b", "esmtp", "203.0.113.80", "67.195.204.77", "starttls", "16440", "pool-b", "job-240301-b", "campaign/ramadan"],
    ["b", "2026-03-22 11:06:52", "2026-03-22 11:06:50", "info@brand-beta.net", "huda@yahoo.com", "", "failed", "421 4.7.0 Try again later, policy throttle", "temporary throttle", "mta5.am0.yahoodns.net", "4.7.0", "smtp", "mx-b", "esmtp", "203.0.113.80", "67.195.204.78", "starttls", "16310", "pool-b", "job-240301-b", "campaign/ramadan"],
    ["d", "2026-03-22 11:07:41", "2026-03-22 11:07:40", "promo@offers-demo.org", "layla@outlook.com", "", "success", "250 2.6.0 queued", "queued for delivery", "outlook-com.olc.protection.outlook.com", "2.6.0", "smtp", "mx-c", "esmtp", "203.0.113.110", "104.47.14.33", "starttls", "17110", "pool-c", "job-240301-c", "campaign/ramadan"],
    ["b", "2026-03-22 11:08:26", "2026-03-22 11:08:24", "promo@offers-demo.org", "fahad@outlook.com", "", "failed", "550 5.1.1 user unknown", "hard bounce", "outlook-com.olc.protection.outlook.com", "5.1.1", "smtp", "mx-c", "esmtp", "203.0.113.110", "104.47.14.34", "starttls", "17098", "pool-c", "job-240301-c", "campaign/ramadan"],
    ["d", "2026-03-22 11:09:58", "2026-03-22 11:09:56", "hello@brand-alpha.com", "reem@icloud.com", "", "success", "250 2.1.5 delivered", "queued for delivery", "mx01.mail.icloud.com", "2.1.5", "smtp", "mx-d", "esmtp", "198.51.100.22", "17.57.155.14", "starttls", "18103", "pool-a", "job-240301-a", "campaign/ramadan"],
    ["b", "2026-03-22 11:10:34", "2026-03-22 11:10:33", "hello@brand-alpha.com", "sami@gmail.com", "", "failed", "452 4.2.2 mailbox full", "mailbox full", "gmail-smtp-in.l.google.com", "4.2.2", "smtp", "mx-a", "esmtp", "198.51.100.21", "74.125.27.28", "starttls", "18001", "pool-a", "job-240301-a", "campaign/ramadan"],
]


def pmta_clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def pmta_normalize_email(value: str) -> str:
    value = pmta_clean(value).lower()
    return value if "@" in value else ""


def pmta_extract_domain(email_value: str) -> str:
    email_value = pmta_normalize_email(email_value)
    return email_value.split("@", 1)[1] if "@" in email_value else "unknown"


def pmta_classify_row(row: list[str]) -> str:
    code = pmta_clean(row[0] if len(row) > 0 else "").lower()
    status_word = pmta_clean(row[6] if len(row) > 6 else "").lower()
    smtp_status = pmta_clean(row[7] if len(row) > 7 else "").lower()
    if code == "d" or "success" in status_word or "relayed" in status_word or "2.0.0" in smtp_status:
        return "delivered"
    if smtp_status.startswith("4"):
        return "deferred"
    if code == "b" or "fail" in status_word or smtp_status.startswith("5"):
        return "bounced"
    return "unknown"


def pmta_bounce_bucket(reason: str, smtp_status: str) -> str:
    hay = f"{reason} {smtp_status}".lower()
    if "spam" in hay or "block" in hay:
        return "spam-related"
    if "user unknown" in hay or "5.1.1" in hay:
        return "bad-mailbox"
    if "mailbox full" in hay or "4.2.2" in hay:
        return "mailbox-full"
    if "try again later" in hay or "4.7.0" in hay or "tempor" in hay:
        return "temporary-or-remote-rejection"
    return "other"


def pmta_row_to_record(row: list[str]) -> dict:
    row = list(row)
    while len(row) < 21:
        row.append("")
    result = pmta_classify_row(row)
    reason = pmta_clean(row[8] or row[7])
    return {
        "type_code": pmta_clean(row[0]),
        "log_time": pmta_clean(row[1]),
        "arrival_time": pmta_clean(row[2]),
        "sender": pmta_normalize_email(row[3]),
        "recipient": pmta_normalize_email(row[4]),
        "result": result,
        "result_word": pmta_clean(row[6]),
        "smtp_status": pmta_clean(row[7]),
        "response_text": reason,
        "mx_host": pmta_clean(row[9]) or "-",
        "dsn_group": pmta_clean(row[10]),
        "protocol": pmta_clean(row[11]),
        "source_host": pmta_clean(row[12]),
        "source_protocol": pmta_clean(row[13]),
        "source_ip": pmta_clean(row[14]),
        "target_ip": pmta_clean(row[15]),
        "smtp_features": pmta_clean(row[16]),
        "size": pmta_clean(row[17]),
        "pool": pmta_clean(row[18]) or "default",
        "job_id": pmta_clean(row[19]) or "unassigned",
        "category_path": pmta_clean(row[20]),
        "sender_domain": pmta_extract_domain(row[3]),
        "recipient_domain": pmta_extract_domain(row[4]),
        "bounce_bucket": pmta_bounce_bucket(reason, row[7]),
    }


def load_pmta_records() -> tuple[list[dict], dict]:
    source = {
        "accounting_file": str(PMTA_ACCOUNTING_FILE),
        "accounting_dir": str(PMTA_ACCOUNTING_DIR),
        "commands_file": str(PMTA_COMMANDS_REFERENCE.name),
        "platform": sys.platform,
        "source_type": "fake-sample",
    }
    if PMTA_ACCOUNTING_FILE.exists():
        records = []
        with PMTA_ACCOUNTING_FILE.open("r", encoding="utf-8", newline="", errors="replace") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = csv.excel
            for row in csv.reader(handle, dialect):
                if row:
                    records.append(pmta_row_to_record(row))
        if records:
            source["source_type"] = "pmta-accounting-file"
            return records, source
    return [pmta_row_to_record(row) for row in PMTA_FAKE_ROWS], source


def load_pmta_commands(limit: int = 8) -> list[dict]:
    commands = []
    if PMTA_COMMANDS_REFERENCE.exists():
        lines = PMTA_COMMANDS_REFERENCE.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("pmta "):
                continue
            description = ""
            for next_line in lines[idx + 1: idx + 6]:
                if next_line.startswith("Description:"):
                    description = next_line.split(":", 1)[1].strip()
                    break
            commands.append({"command": stripped, "description": description or "PowerMTA CLI reference command."})
            if len(commands) >= limit:
                break
    return commands


def load_pmta_reference_commands() -> list[str]:
    commands: list[str] = []
    if not PMTA_COMMANDS_REFERENCE.exists():
        return commands
    for line in PMTA_COMMANDS_REFERENCE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("pmta "):
            continue
        commands.append(stripped)
    return commands


def _extract_first_int(patterns: list[str], text: str) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if not match:
            continue
        try:
            return int(match.group(1).replace(",", ""))
        except Exception:
            continue
    return None


def _pick_reference_command(reference_commands: list[str], marker: str, fallback: str) -> str:
    marker = marker.lower().strip()
    for command in reference_commands:
        normalized = command.lower().strip()
        if marker in normalized and "[" not in command and "]" not in command:
            return command
    return fallback


def _extract_runtime_form_subset(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {}
    keys = (
        "ssh_host",
        "ssh_user",
        "ssh_port",
        "ssh_key_path",
        "ssh_pass",
        "ssh_timeout",
        "pmta_accounting_file",
    )
    subset: dict[str, object] = {}
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        subset[key] = value
    return subset


def _resolve_ssh_mode_summary(runtime_config: dict) -> dict:
    host = str(runtime_config.get("ssh_host") or "").strip()
    user = str(runtime_config.get("ssh_user") or "").strip()
    port = str(runtime_config.get("ssh_port") or "").strip()
    key_path = str(runtime_config.get("ssh_key_path") or "").strip()
    has_password = bool(str(runtime_config.get("ssh_pass") or "").strip())
    auth_mode = "key" if key_path else ("password" if has_password else "agent/default")
    return {
        "enabled": bool(runtime_config.get("ssh_enabled")),
        "target": f"{user}@{host}:{port}" if host and user else "",
        "port": port or "22",
        "auth_mode": auth_mode,
        "has_key_path": bool(key_path),
        "has_password": has_password,
        "timeout_s": int(runtime_config.get("ssh_timeout") or 0),
    }


def _classify_pmta_failure_reason(runtime_config: dict, command_errors: list[str], *, status_ok: bool) -> str:
    if status_ok:
        return ""
    if not runtime_config.get("ssh_enabled"):
        return "missing SSH config"
    combined = " ".join(str(item or "").strip().lower() for item in command_errors if str(item or "").strip())
    if not combined:
        return "PMTA command failure"
    if "password-based ssh is not supported" in combined:
        return "wrong SSH config"
    wrong_tokens = ("permission denied", "authentication failed", "publickey", "invalid format", "bad configuration option")
    if any(token in combined for token in wrong_tokens):
        return "wrong SSH config"
    unreachable_tokens = ("name or service not known", "could not resolve hostname", "connection timed out", "no route to host", "connection refused")
    if any(token in combined for token in unreachable_tokens):
        return "unreachable SSH host"
    return "PMTA command failure"


def resolve_pmta_runtime_for_job(job: dict) -> dict:
    campaign_id = str((job or {}).get("campaign_id") or "").strip()
    source = "environment"
    source_detail = "environment fallback"
    candidate = {}

    job_runtime = _extract_runtime_form_subset((job or {}).get("runtime_config"))
    if job_runtime:
        source = "job.runtime_config"
        source_detail = "job.runtime_config.ssh_*"
        candidate = job_runtime
    else:
        campaign_form = _extract_runtime_form_subset(CAMPAIGN_FORMS_STATE.get(campaign_id, {}))
        if not campaign_form:
            campaign = get_campaign(campaign_id) if campaign_id else None
            campaign_form = _extract_runtime_form_subset((campaign or {}).get("form_snapshot") if isinstance(campaign, dict) else {})
        if campaign_form:
            source = "campaign_form_snapshot"
            source_detail = f"campaign form snapshot ({campaign_id or 'unknown'})"
            candidate = campaign_form

    runtime_config = script6.build_runtime_config(candidate)
    return {
        "runtime_config": runtime_config,
        "source": source,
        "source_detail": source_detail,
    }


def load_pmta_monitor_snapshot(job: dict) -> dict:
    _append_job_event(job, "pmta_fetch_attempted", "Attempting PMTA live/accounting fetch.", min_interval_s=20)
    _append_job_event(job, "accounting_fetch_attempted", "Attempting accounting counters fetch.", min_interval_s=20)
    fallback_queue = max(int(job.get("queued") or 0), int(job.get("deferred") or 0))
    fallback_sent = max(int(job.get("sent") or 0), 0)
    fallback_min_out = max(1, fallback_sent // 15) if fallback_sent else 0
    fallback_hr_out = max(fallback_min_out, fallback_sent // 2) if fallback_sent else 0

    resolved_runtime = resolve_pmta_runtime_for_job(job if isinstance(job, dict) else {})
    runtime_config = resolved_runtime.get("runtime_config") if isinstance(resolved_runtime.get("runtime_config"), dict) else {}
    runtime_source = str(resolved_runtime.get("source") or "environment")
    runtime_source_detail = str(resolved_runtime.get("source_detail") or "environment fallback")
    ssh_mode_summary = _resolve_ssh_mode_summary(runtime_config)

    base_live = {
        "enabled": True,
        "ok": False,
        "source": "fallback",
        "reason": "missing SSH config",
        "reason_detail": "SSH not configured",
        "runtime_source": runtime_source,
        "runtime_source_detail": runtime_source_detail,
        "resolved_ssh_mode": ssh_mode_summary,
        "spool_recipients": fallback_queue,
        "spool_messages": max(1, fallback_queue // 4) if fallback_queue else 0,
        "queued_recipients": fallback_queue,
        "queued_messages": max(1, fallback_queue // 5) if fallback_queue else 0,
        "smtp_in_connections": 0,
        "smtp_out_connections": 0,
        "active_connections": 0,
        "traffic_last_min_in": max(0, fallback_min_out // 2),
        "traffic_last_min_out": fallback_min_out,
        "traffic_last_hr_in": max(0, fallback_hr_out // 2),
        "traffic_last_hr_out": fallback_hr_out,
        "top_queues": [],
        "ts": iso(datetime.now(timezone.utc)),
    }
    base_diag = {"enabled": True, "ok": False, "queue_deferrals": 0, "queue_errors": 0, "errors_sample": []}
    base_bridge_state = {
        "connected": False,
        "last_ok": False,
        "last_error": "SSH not configured",
        "last_attempt_ts": "",
        "last_success_ts": "",
        "attempts": 0,
        "success_count": 0,
        "failure_count": 0,
        "bridge_base_url": "",
        "last_req_url": "",
        "pull_url_masked": "",
        "last_response_keys": [],
        "last_bridge_count": 0,
        "last_processed": 0,
        "last_accepted": 0,
        "last_lines_sample": [],
        "last_duration_ms": 0,
    }
    base_outcomes = {
        "sent": None,
        "delivered": None,
        "bounced": None,
        "deferred": None,
        "complained": None,
    }
    commands_used: list[dict] = []

    reference_commands = load_pmta_reference_commands()
    status_command = _pick_reference_command(reference_commands, "show status", "pmta show status")
    topqueues_command = _pick_reference_command(reference_commands, "show topqueues", "pmta show topqueues")
    backoff_command = _pick_reference_command(reference_commands, "show que --mode=backoff", "pmta show queues --mode=backoff")

    if not runtime_config.get("ssh_enabled"):
        missing = []
        for key in ("ssh_host", "ssh_user", "ssh_port"):
            if not str(runtime_config.get(key) or "").strip():
                missing.append(key)
        reason = "SSH settings missing: " + (", ".join(missing) if missing else "ssh_enabled is false")
        base_live["reason"] = "missing SSH config"
        base_live["reason_detail"] = reason
        _set_job_diagnostic(job, "ssh", "bad", reason)
        _set_job_diagnostic(job, "pmta_live", "bad", reason)
        _set_job_diagnostic(job, "accounting", "warn", "Accounting data unavailable because PMTA live is unavailable.")
        _set_job_diagnostic(job, "bridge", "warn", "Bridge disconnected because SSH is not configured.", expected=True)
        _append_job_event(job, "pmta_fetch_failed", reason, "WARN", min_interval_s=20)
        return {
            "pmta_live": base_live,
            "pmta_diag": base_diag,
            "monitor_commands_used": commands_used,
            "bridge_state": base_bridge_state,
            "pmta_outcomes": base_outcomes,
        }

    outputs: dict[str, str] = {}
    attempt_started = datetime.now(timezone.utc)
    base_bridge_state["attempts"] = 1
    base_bridge_state["last_attempt_ts"] = iso(attempt_started)
    base_bridge_state["bridge_base_url"] = f"ssh://{runtime_config.get('ssh_user')}@{runtime_config.get('ssh_host')}:{runtime_config.get('ssh_port')}"
    base_bridge_state["last_req_url"] = f"{base_bridge_state['bridge_base_url']}#pmta-cli"
    base_bridge_state["pull_url_masked"] = f"{runtime_config.get('ssh_user')}@{runtime_config.get('ssh_host')}:{runtime_config.get('ssh_port')}"
    for label, command in [
        ("status", status_command),
        ("topqueues", topqueues_command),
        ("queues_backoff", backoff_command),
    ]:
        try:
            result = script6.run_ssh_command(runtime_config, command)
            stdout = (result.get("stdout") or "").strip()
            outputs[label] = stdout
            commands_used.append({"label": label, "command": command, "ok": True})
        except Exception as exc:
            outputs[label] = ""
            commands_used.append({"label": label, "command": command, "ok": False, "error": str(exc)})

    status_output = outputs.get("status", "")
    if status_output:
        base_live["ok"] = True
        base_live["source"] = "live"
        base_live["reason"] = ""
        base_live["reason_detail"] = ""
        base_bridge_state["connected"] = True
        base_bridge_state["last_ok"] = True
        base_bridge_state["last_error"] = ""
        base_bridge_state["last_success_ts"] = iso(datetime.now(timezone.utc))
        base_bridge_state["success_count"] = 1
        _set_job_diagnostic(job, "pmta_live", "good", "PMTA live fetch succeeded over SSH.")
        _append_job_event(job, "pmta_fetch_succeeded", "PMTA live fetch succeeded.", min_interval_s=20)
    else:
        command_errors = [str(row.get("error") or "").strip() for row in commands_used if not row.get("ok")]
        failure_reason = _classify_pmta_failure_reason(runtime_config, command_errors, status_ok=False)
        first_error = next((row.get("error") for row in commands_used if not row.get("ok") and row.get("error")), "")
        base_bridge_state["failure_count"] = 1
        base_bridge_state["last_error"] = str(first_error or "Unable to run PMTA commands over SSH.").strip()
        base_live["source"] = "fallback"
        base_live["reason"] = failure_reason
        base_live["reason_detail"] = base_bridge_state["last_error"]
        _set_job_diagnostic(job, "pmta_live", "bad", base_bridge_state["last_error"])
        _append_job_event(job, "pmta_fetch_failed", base_bridge_state["last_error"], "WARN", min_interval_s=20)

    spool_rcpt = _extract_first_int([r"spool[^\n]*?rcpt[^0-9]*(\d+)", r"spool[^\n]*?recipients?[^0-9]*(\d+)"], status_output)
    spool_msg = _extract_first_int([r"spool[^\n]*?msg[^0-9]*(\d+)", r"spool[^\n]*?messages?[^0-9]*(\d+)"], status_output)
    queue_rcpt = _extract_first_int([r"queue[^\n]*?rcpt[^0-9]*(\d+)", r"queued[^\n]*?recipients?[^0-9]*(\d+)"], status_output)
    queue_msg = _extract_first_int([r"queue[^\n]*?msg[^0-9]*(\d+)", r"queued[^\n]*?messages?[^0-9]*(\d+)"], status_output)
    smtp_in = _extract_first_int([r"smtp[^\n]*?in[^0-9]*(\d+)", r"inbound[^\n]*?connections?[^0-9]*(\d+)"], status_output)
    smtp_out = _extract_first_int([r"smtp[^\n]*?out[^0-9]*(\d+)", r"outbound[^\n]*?connections?[^0-9]*(\d+)"], status_output)
    active = _extract_first_int([r"active[^\n]*?connections?[^0-9]*(\d+)", r"connections?[^0-9]*(\d+)"], status_output)
    last_min_in = _extract_first_int([r"last\s*min(?:ute)?[^\n]*?in[^0-9]*(\d+)"], status_output)
    last_min_out = _extract_first_int([r"last\s*min(?:ute)?[^\n]*?out[^0-9]*(\d+)"], status_output)
    last_hr_in = _extract_first_int([r"last\s*(?:hour|hr)[^\n]*?in[^0-9]*(\d+)"], status_output)
    last_hr_out = _extract_first_int([r"last\s*(?:hour|hr)[^\n]*?out[^0-9]*(\d+)"], status_output)

    if spool_rcpt is not None:
        base_live["spool_recipients"] = spool_rcpt
    if spool_msg is not None:
        base_live["spool_messages"] = spool_msg
    if queue_rcpt is not None:
        base_live["queued_recipients"] = queue_rcpt
    if queue_msg is not None:
        base_live["queued_messages"] = queue_msg
    if smtp_in is not None:
        base_live["smtp_in_connections"] = smtp_in
    if smtp_out is not None:
        base_live["smtp_out_connections"] = smtp_out
    if active is not None:
        base_live["active_connections"] = active
    else:
        base_live["active_connections"] = int(base_live["smtp_in_connections"]) + int(base_live["smtp_out_connections"])
    if last_min_in is not None:
        base_live["traffic_last_min_in"] = last_min_in
    if last_min_out is not None:
        base_live["traffic_last_min_out"] = last_min_out
    if last_hr_in is not None:
        base_live["traffic_last_hr_in"] = last_hr_in
    if last_hr_out is not None:
        base_live["traffic_last_hr_out"] = last_hr_out

    outcomes_sent = _extract_first_int(
        [
            r"(?:sent|submit(?:ted)?|accepted)[^\n]*?[^0-9](\d+)",
            r"total[^\n]*?(?:rcpt|recipients?)[^0-9]*(\d+)",
        ],
        status_output,
    )
    outcomes_delivered = _extract_first_int([r"deliver(?:ed|y)[^\n]*?[^0-9](\d+)"], status_output)
    outcomes_bounced = _extract_first_int([r"bounc(?:ed|es)[^\n]*?[^0-9](\d+)"], status_output)
    outcomes_deferred = _extract_first_int([r"defer(?:red|rals?)[^\n]*?[^0-9](\d+)"], status_output)
    outcomes_complained = _extract_first_int([r"complain(?:ed|ts?)[^\n]*?[^0-9](\d+)"], status_output)

    if outcomes_sent is not None:
        base_outcomes["sent"] = outcomes_sent
    if outcomes_delivered is not None:
        base_outcomes["delivered"] = outcomes_delivered
    if outcomes_bounced is not None:
        base_outcomes["bounced"] = outcomes_bounced
    if outcomes_deferred is not None:
        base_outcomes["deferred"] = outcomes_deferred
    if outcomes_complained is not None:
        base_outcomes["complained"] = outcomes_complained

    top_queues_output = outputs.get("topqueues", "")
    top_queues = []
    for raw_line in top_queues_output.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith(("queue", "domain", "name", "----")):
            continue
        match = re.match(r"(?P<queue>[\w./:-]+).*?(?P<rcpt>\d+)", line)
        if not match:
            continue
        top_queues.append(
            {
                "queue": match.group("queue"),
                "domain": match.group("queue").split("/", 1)[0],
                "recipients": int(match.group("rcpt")),
                "deferred": 0,
                "last_error": "",
            }
        )
        if len(top_queues) >= 4:
            break
    base_live["top_queues"] = top_queues

    backoff_output = outputs.get("queues_backoff", "")
    backoff_lines = [line.strip() for line in backoff_output.splitlines() if line.strip()]
    backoff_errors = [line for line in backoff_lines if any(token in line.lower() for token in ["error", "defer", "4.", "5."])]
    base_diag.update(
        {
            "ok": bool(backoff_output or status_output),
            "domain": str(job.get("provider") or "mixed"),
            "class": "remote",
            "queue_deferrals": len([line for line in backoff_lines if "defer" in line.lower()]),
            "queue_errors": len(backoff_errors),
            "errors_sample": backoff_errors[:3],
            "remote_hint": "ssh/pmta-cli",
        }
    )
    base_live["ts"] = iso(datetime.now(timezone.utc))
    _set_job_diagnostic(job, "ssh", "good", "SSH settings are configured.")
    if base_bridge_state.get("connected"):
        _set_job_diagnostic(job, "bridge", "good", "Bridge connected to PMTA.", expected=True)
    else:
        _set_job_diagnostic(job, "bridge", "bad", "Bridge disconnected while SSH is configured (abnormal).", expected=False)
    if base_outcomes["sent"] is None and base_outcomes["delivered"] is None and base_outcomes["bounced"] is None:
        _set_job_diagnostic(job, "accounting", "warn", "Accounting data unavailable from PMTA status output.")
        _append_job_event(job, "accounting_fetch_failed", "Accounting counters were not present in PMTA status output.", "WARN", min_interval_s=20)
    else:
        _set_job_diagnostic(job, "accounting", "good", "Accounting counters available from PMTA status output.")
        _append_job_event(job, "accounting_fetch_succeeded", "Accounting counters parsed from PMTA status output.", min_interval_s=20)
    return {
        "pmta_live": base_live,
        "pmta_diag": base_diag,
        "monitor_commands_used": commands_used,
        "bridge_state": base_bridge_state,
        "pmta_outcomes": base_outcomes,
    }


def load_pmta_ssh_preview() -> dict:
    host = os.getenv("PMTA_SSH_HOST", DASHBOARD_DATA["message_form"]["ssh_host"] if "DASHBOARD_DATA" in globals() else "ops.demo.internal")
    user = os.getenv("PMTA_SSH_USER", DASHBOARD_DATA["message_form"]["ssh_user"] if "DASHBOARD_DATA" in globals() else "pmtaops")
    command = ["ssh", f"{user}@{host}", "pmta show status"]
    preview = {
        "command": " ".join(command),
        "status": "not-configured",
        "output": "Set PMTA_SSH_HOST / PMTA_SSH_USER to allow a real SSH status probe.",
    }
    if not os.getenv("PMTA_SSH_HOST"):
        return preview
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
        preview["status"] = "ok" if result.returncode == 0 else f"exit-{result.returncode}"
        preview["output"] = (result.stdout or result.stderr or "No SSH output returned.").strip()[:280]
    except Exception as exc:
        preview["status"] = "error"
        preview["output"] = str(exc)
    return preview


def build_accounting_summary() -> dict:
    records, source = load_pmta_records()
    ssh_preview = load_pmta_ssh_preview()
    commands = load_pmta_commands()
    totals = Counter(record["result"] for record in records)
    recipient_domains: dict[str, dict] = defaultdict(lambda: {"total": 0, "delivered": 0, "bounced": 0, "deferred": 0, "unknown": 0, "reasons": Counter(), "mx": Counter(), "jobs": Counter()})
    pools = Counter()
    jobs = Counter()
    reasons = Counter()
    for record in records:
        domain = record["recipient_domain"]
        bucket = recipient_domains[domain]
        bucket["total"] += 1
        bucket[record["result"]] += 1
        if record["response_text"]:
            bucket["reasons"][record["response_text"]] += 1
            reasons[record["response_text"]] += 1
        bucket["mx"][record["mx_host"]] += 1
        bucket["jobs"][record["job_id"]] += 1
        pools[record["pool"]] += 1
        jobs[record["job_id"]] += 1
    domain_rows = []
    for domain, values in recipient_domains.items():
        total = values["total"] or 1
        domain_rows.append({
            "domain": domain,
            "total": values["total"],
            "delivered": values["delivered"],
            "bounced": values["bounced"],
            "deferred": values["deferred"],
            "delivery_rate": round(values["delivered"] * 100 / total, 2),
            "bounce_rate": round(values["bounced"] * 100 / total, 2),
            "top_reason": values["reasons"].most_common(1)[0][0] if values["reasons"] else "-",
            "top_mx": values["mx"].most_common(1)[0][0] if values["mx"] else "-",
            "job_hint": values["jobs"].most_common(1)[0][0] if values["jobs"] else "-",
        })
    domain_rows.sort(key=lambda item: (-item["total"], item["domain"]))
    recent_records = sorted(records, key=lambda item: item["log_time"], reverse=True)[:8]
    total_records = len(records) or 1
    snapshot_time = recent_records[0]["log_time"] if recent_records else iso(datetime.now(timezone.utc))
    return {
        "source": source,
        "ssh_preview": ssh_preview,
        "commands": commands,
        "records": recent_records,
        "top_domains": domain_rows[:8],
        "top_reasons": reasons.most_common(6),
        "totals": {
            "total": len(records),
            "delivered": totals.get("delivered", 0),
            "bounced": totals.get("bounced", 0),
            "deferred": totals.get("deferred", 0),
            "unknown": totals.get("unknown", 0),
            "delivery_rate": round(totals.get("delivered", 0) * 100 / total_records, 2),
            "bounce_rate": round(totals.get("bounced", 0) * 100 / total_records, 2),
            "deferred_rate": round(totals.get("deferred", 0) * 100 / total_records, 2),
        },
        "queue_snapshot": {
            "live_queue": totals.get("deferred", 0) + totals.get("unknown", 0),
            "active_jobs": len(jobs),
            "active_pools": len(pools),
            "top_pool": pools.most_common(1)[0][0] if pools else "-",
            "snapshot_time": snapshot_time,
        },
    }


DASHBOARD_DATA = {
    "app_name": "Shiva Frontend Sandbox",
    "campaign": {
        "id": "cmp-demo-001",
        "name": "Ramadan Promo · 💀 SHIVA THUNDER",
        "status": "running",
        "owner": "demo@shivamini.local",
        "created_at": iso(NOW - timedelta(days=4, hours=2)),
        "updated_at": iso(NOW - timedelta(minutes=3)),
    },
    "kpis": [
        {"label": "Total Recipients", "value": "48,250", "tone": "neutral", "hint": "Loaded from fake campaign audience."},
        {"label": "Delivered", "value": "41,932", "tone": "good", "hint": "Simulated delivered outcomes."},
        {"label": "Deferred", "value": "2,104", "tone": "warn", "hint": "Temporary soft deferrals."},
        {"label": "Bounced", "value": "1,188", "tone": "bad", "hint": "Hard/soft bounce sample total."},
        {"label": "Complaints", "value": "67", "tone": "bad", "hint": "Complaint placeholder metric."},
        {"label": "Spam Score", "value": "2.6 / 10", "tone": "good", "hint": "Fake preflight result."},
        {"label": "Blacklist Health", "value": "2 listed", "tone": "warn", "hint": "Demo DNSBL result."},
        {"label": "Live Queue", "value": "3,842", "tone": "accent", "hint": "Simulated PMTA queue count."},
    ],
    "progress": {
        "overall": 86,
        "domain": 79,
        "chunks": 68,
        "warmup": 91,
    },
    "alerts": [
        {"title": "Adaptive throttle active", "body": "Yahoo lane was slowed down after repeated 4xx responses.", "tone": "warn"},
        {"title": "Bridge connected", "body": "Accounting bridge last synced 22 seconds ago.", "tone": "good"},
        {"title": "Two sender domains listed", "body": "mail-demo.net appears in a fake DNSBL sample.", "tone": "bad"},
    ],
    "ops_snapshot": [
        {"label": "Active operators", "value": "4", "tone": "accent", "hint": "Fake dashboard staffing info for the current shift."},
        {"label": "Bridge poll", "value": "5s", "tone": "good", "hint": "Preview-only bridge polling interval."},
        {"label": "Warmup profile", "value": "Tier B", "tone": "warn", "hint": "Demo sender warmup cohort for this campaign."},
        {"label": "Inbox seed tests", "value": "18/20", "tone": "good", "hint": "Sample seed inbox placement result."},
    ],
    "dashboard_notes": [
        {"title": "Shift owner", "body": "Maya (deliverability) is monitoring Gmail and Outlook lanes for this demo job.", "tone": "accent"},
        {"title": "Next milestone", "body": "The board switches to reconciliation mode after the live queue drops below 1,000 recipients.", "tone": "good"},
        {"title": "Demo caveat", "body": "All numbers on this dashboard are fake placeholders for frontend preview only.", "tone": "warn"},
    ],
    "preflight": {
        "spam_score": 2.6,
        "spam_limit": 4.0,
        "backend": "SpamAssassin (fake)",
        "smtp_host": "pmta.demo.internal",
        "sender_domains": [
            {"domain": "brand-alpha.com", "ips": ["198.51.100.21", "198.51.100.22"], "status": "Not listed", "spam_score": 2.1},
            {"domain": "brand-beta.net", "ips": ["203.0.113.80"], "status": "Listed", "spam_score": 4.4},
            {"domain": "offers-demo.org", "ips": ["203.0.113.110"], "status": "Not listed", "spam_score": 3.0},
        ],
    },
    "excel_info": {
        "file_name": "ramadan-demo-recipients.xlsx",
        "sheet_name": "Audience_Master",
        "rows_total": "48,250",
        "validated_rows": "47,901",
        "suppressed_rows": "349",
        "columns": [
            {"name": "email", "description": "Primary recipient email used to build the fake send queue."},
            {"name": "first_name", "description": "Used with [NAME] and personalization previews inside the HTML body."},
            {"name": "segment", "description": "Maps each row to a campaign slice such as VIP, warm, or re-engagement."},
            {"name": "sender_hint", "description": "Optional sender-domain hint used by the routing preview in Mini Shiva."},
        ],
        "checks": [
            "Accepts .xlsx uploads with one audience sheet or multiple segment sheets.",
            "Normalizes headers automatically before fake preview mapping.",
            "Flags duplicate emails, missing domains, and suppressed rows before send.",
            "Exports a cleaned CSV snapshot for operators to review before starting jobs.",
        ],
    },
    "message_form": {
        "smtp_host": "pmta.demo.internal",
        "smtp_port": 2525,
        "smtp_security": "starttls",
        "smtp_user": "mailer-demo",
        "smtp_timeout": 25,
        "ssh_host": "ops.demo.internal",
        "ssh_port": 22,
        "ssh_user": "pmtaops",
        "ssh_timeout": 8,
        "from_name": "Shiva Team\nOffers Robot",
        "from_email": "hello@brand-alpha.com\ninfo@brand-beta.net",
        "subject": "Your dashboard demo is ready\nLast chance to review the sandbox",
        "body_format": "html",
        "reply_to": "support@brand-alpha.com",
        "score_range": 4.0,
        "body": "<h1>Hello [NAME]</h1><p>This is a fake preview body for the Shiva frontend skeleton.</p>",
        "urls_list": "https://brand-alpha.com/demo\nhttps://brand-beta.net/offer",
        "src_list": "https://picsum.photos/seed/shivamini-1/600/240\nhttps://picsum.photos/seed/shivamini-2/600/240",
        "recipients": "amira@example.com\nomar@example.com\nlayla@example.com",
        "maillist_safe": "amira@example.com\nlayla@example.com",
        "delay_s": 0.2,
        "max_rcpt": 50000,
        "chunk_size": 250,
        "thread_workers": 8,
        "sleep_chunks": 1.5,
    },
}

CAMPAIGNS = [
    {
        "id": "cmp-demo-001",
        "name": "Ramadan Promo · 💀 SHIVA THUNDER",
        "created_at": iso(NOW - timedelta(days=4, hours=2)),
        "updated_at": iso(NOW - timedelta(minutes=3)),
        "jobs": 5,
        "status": "running",
    },
    {
        "id": "cmp-demo-002",
        "name": "Eid Launch · Sample Campaign",
        "created_at": iso(NOW - timedelta(days=10)),
        "updated_at": iso(NOW - timedelta(hours=4)),
        "jobs": 2,
        "status": "paused",
    },
    {
        "id": "cmp-demo-003",
        "name": "Winback Flow · Skeleton",
        "created_at": iso(NOW - timedelta(days=18)),
        "updated_at": iso(NOW - timedelta(days=1, hours=6)),
        "jobs": 9,
        "status": "done",
    },
]

CAMPAIGNS_FILE = database_path("campaigns.json")
CAMPAIGN_FORM_FILE = database_path("campaign_forms.json")
DEFAULT_CAMPAIGN_ID = CAMPAIGNS[0]["id"] if CAMPAIGNS else "cmp-default"


def _load_json_file(path: Path, fallback):
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except Exception:
        return copy.deepcopy(fallback)


def _save_json_file(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_campaigns() -> list[dict]:
    loaded = _load_json_file(CAMPAIGNS_FILE, CAMPAIGNS)
    if not isinstance(loaded, list) or not loaded:
        loaded = copy.deepcopy(CAMPAIGNS)
    normalized: list[dict] = []
    for row in loaded:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "").strip()
        if not cid:
            continue
        normalized.append(
            {
                "id": cid,
                "name": str(row.get("name") or f"Campaign {cid}"),
                "created_at": str(row.get("created_at") or iso(datetime.now(timezone.utc))),
                "updated_at": str(row.get("updated_at") or iso(datetime.now(timezone.utc))),
                "jobs": int(row.get("jobs") or 0),
                "status": str(row.get("status") or "draft"),
                "total_recipients": int(row.get("total_recipients") or 0),
                "start_clicks": int(row.get("start_clicks") or 0),
            }
        )
    if not normalized:
        normalized = copy.deepcopy(CAMPAIGNS)
    return normalized


def save_campaigns(campaigns: list[dict]) -> None:
    _save_json_file(CAMPAIGNS_FILE, campaigns)


def load_campaign_forms() -> dict[str, dict]:
    data = _load_json_file(CAMPAIGN_FORM_FILE, {})
    if not isinstance(data, dict):
        return {}
    cleaned: dict[str, dict] = {}
    for cid, payload in data.items():
        if not isinstance(cid, str) or not isinstance(payload, dict):
            continue
        cleaned[cid] = payload
    return cleaned


def save_campaign_forms(data: dict[str, dict]) -> None:
    _save_json_file(CAMPAIGN_FORM_FILE, data)


CAMPAIGNS_STATE = load_campaigns()
CAMPAIGN_FORMS_STATE = load_campaign_forms()


def get_campaign(campaign_id: str) -> dict | None:
    for campaign in CAMPAIGNS_STATE:
        if campaign.get("id") == campaign_id:
            return campaign
    return None


def get_or_create_campaign(campaign_id: str) -> dict:
    existing = get_campaign(campaign_id)
    if existing:
        return existing
    now_iso = iso(datetime.now(timezone.utc))
    created = {
        "id": campaign_id,
        "name": f"Campaign {campaign_id}",
        "created_at": now_iso,
        "updated_at": now_iso,
        "jobs": 0,
        "status": "draft",
        "total_recipients": 0,
        "start_clicks": 0,
    }
    CAMPAIGNS_STATE.insert(0, created)
    save_campaigns(CAMPAIGNS_STATE)
    return created


def campaign_heading_suffix(campaign_id: str) -> str:
    campaign = get_campaign(campaign_id)
    if not campaign:
        return ""
    name = str(campaign.get("name") or "").strip()
    return f" · {name}" if name else ""


def campaign_monitoring_snapshot(campaign: dict) -> dict:
    campaign_id = str(campaign.get("id") or "").strip()
    campaign_jobs = [row for row in JOBS if row.get("campaign_id") == campaign_id]
    sent = sum(int(row.get("sent") or 0) for row in campaign_jobs)
    delivered = sum(int(row.get("delivered") or 0) for row in campaign_jobs)
    failed = sum(int(row.get("failed") or 0) for row in campaign_jobs)
    deferred = sum(int(row.get("deferred") or 0) for row in campaign_jobs)
    queued = sum(int(row.get("queued") or 0) for row in campaign_jobs)
    inferred_total = sent + failed + queued
    total_recipients = max(int(campaign.get("total_recipients") or 0), inferred_total)
    if total_recipients <= 0:
        total_recipients = 0
    not_sent = max(total_recipients - sent, 0)
    start_clicks = max(int(campaign.get("start_clicks") or 0), len(campaign_jobs))
    return {
        "jobs_count": len(campaign_jobs),
        "sent": sent,
        "delivered": delivered,
        "failed": failed,
        "deferred": deferred,
        "queued": queued,
        "total_recipients": total_recipients,
        "not_sent": not_sent,
        "start_clicks": start_clicks,
        "started": start_clicks > 0,
    }


def get_job(job_id: str) -> dict | None:
    target = (job_id or "").strip()
    if not target:
        return None
    for row in JOBS:
        if str(row.get("id") or "").strip() == target:
            return row
    return None


def _parse_iso_utc(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _safe_int(value, default: int = 0, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    if minimum is not None:
        parsed = max(int(minimum), parsed)
    return parsed


def _seed_job_runtime_defaults(job: dict) -> None:
    now = datetime.now(timezone.utc)
    sent_now = _safe_int(job.get("sent"), 0, minimum=0)
    failed_now = _safe_int(job.get("failed"), 0, minimum=0)
    queued_now = _safe_int(job.get("queued"), 0, minimum=0)
    total = _safe_int(job.get("total"), sent_now + failed_now + queued_now, minimum=0)
    if not job.get("started_at"):
        job["started_at"] = iso(now)
    if not job.get("created_at"):
        job["created_at"] = job.get("started_at")
    if not job.get("updated_at"):
        job["updated_at"] = job.get("started_at")
    if not job.get("bridge_mode"):
        job["bridge_mode"] = "counts"
    if not job.get("phase"):
        job["phase"] = "queued"
    if not isinstance(job.get("runtime_logs"), list):
        job["runtime_logs"] = [f"[INFO] Job {job.get('id')} created and waiting to run."]
    if not isinstance(job.get("diagnostics"), dict):
        job["diagnostics"] = {}
    if not isinstance(job.get("top_domains"), list) or not job.get("top_domains"):
        sender = str((job.get("send_snapshot") or {}).get("from_email") or "").strip().lower()
        sender_domain = sender.split("@", 1)[1] if "@" in sender else ""
        job["top_domains"] = [sender_domain] if sender_domain else ["unknown.local"]
    job["total"] = total
    job["queued"] = _safe_int(job.get("queued"), total - sent_now, minimum=0)


def _advance_job_runtime(job: dict) -> None:
    _seed_job_runtime_defaults(job)
    if not RUNTIME_UPDATES_ENABLED:
        _set_job_diagnostic(job, "runtime_updates", "bad", "Runtime updates are disabled (NIBIRU_RUNTIME_UPDATES=0).")
        _append_job_event(job, "runtime_update", "Runtime update skipped because runtime updates are disabled.", "WARN")
        return
    _set_job_diagnostic(job, "runtime_updates", "good", "Runtime updates are running.")
    if not job.get("_runtime_update_started"):
        _append_job_event(job, "runtime_update_started", "Runtime update loop started for this job.")
        job["_runtime_update_started"] = True
    locked_status = str(job.get("status") or "").strip().lower()
    if locked_status in {"paused", "stopped"}:
        job["updated_at"] = iso(datetime.now(timezone.utc))
        return
    now = datetime.now(timezone.utc)
    started_at = _parse_iso_utc(str(job.get("started_at") or "")) or now
    elapsed = max(0, int((now - started_at).total_seconds()))
    total = _safe_int(job.get("total"), 0, minimum=0)
    chunk_size = _safe_int((job.get("send_snapshot") or {}).get("chunk_size"), 250, minimum=1)
    throughput = max(1, chunk_size // 6)
    warmup_seconds = 2
    if total == 0:
        target_sent = 0
    elif elapsed <= warmup_seconds:
        target_sent = min(total, max(_safe_int(job.get("sent"), 0, minimum=0), 1))
    else:
        target_sent = min(total, (elapsed - warmup_seconds) * throughput)

    target_failed = min(target_sent, int(round(target_sent * 0.02)))
    target_deferred = min(max(target_sent - target_failed, 0), int(round(target_sent * 0.05)))
    target_delivered = max(target_sent - target_failed - target_deferred, 0)
    target_queued = max(total - target_sent, 0)
    target_status = "done" if total > 0 and target_sent >= total else ("running" if target_sent > 0 else "queued")
    target_phase = "completed" if target_status == "done" else ("sending" if target_status == "running" else "queued")
    target_chunk = 0 if total == 0 else min((target_sent // chunk_size) + 1, max(1, (total + chunk_size - 1) // chunk_size))

    prev_status = str(job.get("status") or "queued")
    prev_chunk = _safe_int(job.get("current_chunk"), 0, minimum=0)
    prev_sent = _safe_int(job.get("sent"), 0, minimum=0)

    job["status"] = target_status
    job["phase"] = target_phase
    job["current_chunk"] = target_chunk
    job["sent"] = target_sent
    job["failed"] = target_failed
    job["deferred"] = target_deferred
    job["delivered"] = target_delivered
    job["queued"] = target_queued
    job["progress"] = 100 if total <= 0 else min(100, int(round((target_sent / total) * 100)))
    job["updated_at"] = iso(now)

    if prev_status != target_status:
        _append_job_event(job, "job_state_updated", f"Status changed: {prev_status} → {target_status}.")
    if target_status == "running" and prev_chunk != target_chunk and target_chunk > 0:
        _append_job_event(job, "job_state_updated", f"Processing chunk {target_chunk} ({min(target_sent, total)}/{total}).")
    if target_status == "done" and prev_sent < total:
        _append_job_event(job, "job_state_updated", "Send job reached completion.")


def build_job_detail(job_id: str) -> dict | None:
    job = get_job(job_id)
    if not job:
        return None
    _advance_job_runtime(job)
    send_snapshot = job.get("send_snapshot") if isinstance(job.get("send_snapshot"), dict) else {}
    sender_from_snapshot = str(send_snapshot.get("from_email") or "").strip()
    sender_label = sender_from_snapshot or "campaign sender"
    smtp_host = str(send_snapshot.get("smtp_host") or "").strip()
    subject = str(send_snapshot.get("subject") or "").strip()
    sent = int(job.get("sent") or 0)
    failed = int(job.get("failed") or 0)
    queued = int(job.get("queued") or 0)
    delivered = int(job.get("delivered") or 0)
    deferred = int(job.get("deferred") or 0)
    total = sent + failed + queued
    safe_total = total if total > 0 else 1
    progress = int(job.get("progress") or round((sent / safe_total) * 100))
    provider = str(job.get("provider") or "unknown")
    top_domains = [str(item) for item in (job.get("top_domains") or []) if str(item).strip()]
    if not top_domains:
        top_domains = [f"{provider}.com"]
    domain_state = []
    sent_remaining = sent
    failed_remaining = failed
    for idx, domain in enumerate(top_domains):
        weight = max(len(top_domains) - idx, 1)
        planned = max(int(round((total * weight) / sum(range(1, len(top_domains) + 1)))), 0)
        domain_sent = min(sent_remaining, planned)
        sent_remaining = max(sent_remaining - domain_sent, 0)
        domain_failed = min(failed_remaining, max(planned - domain_sent, 0))
        failed_remaining = max(failed_remaining - domain_failed, 0)
        pct = round((domain_sent / planned) * 100) if planned else 0
        domain_state.append(
            {"domain": domain, "planned": planned, "sent": domain_sent, "failed": domain_failed, "pct": pct}
        )
    domain_plan = {str(row.get("domain")): int(row.get("planned") or 0) for row in domain_state if row.get("domain")}
    domain_sent_map = {str(row.get("domain")): int(row.get("sent") or 0) for row in domain_state if row.get("domain")}
    domain_failed_map = {str(row.get("domain")): int(row.get("failed") or 0) for row in domain_state if row.get("domain")}

    chunk_size = max(1, int(send_snapshot.get("chunk_size") or 250))
    chunk_unique_total = max(1, (total + chunk_size - 1) // chunk_size) if total > 0 else 0
    if str(job.get("status") or "").strip().lower() == "done":
        chunk_unique_done = chunk_unique_total
    else:
        chunk_unique_done = min(chunk_unique_total, sent // chunk_size if chunk_size > 0 else 0)
    chunk_current_idx = max(0, int(job.get("current_chunk") or 1) - 1) if chunk_unique_total else 0
    chunk_current_size = chunk_size
    if chunk_unique_total and chunk_current_idx == max(chunk_unique_total - 1, 0):
        remainder = total - (chunk_current_idx * chunk_size)
        if remainder > 0:
            chunk_current_size = remainder
    dominant_domain = str(top_domains[0] if top_domains else f"{provider}.com")
    now_dt = datetime.now(timezone.utc)
    next_retry_epoch = int((now_dt + timedelta(minutes=2)).timestamp())
    base_chunk = {
        "chunk": chunk_current_idx,
        "status": str(job.get("status") or "queued"),
        "size": int(chunk_current_size),
        "sender": sender_label,
        "target_domain": dominant_domain,
        "provider_domain": dominant_domain,
        "spam_score": 1.8 if str(job.get("status") or "").lower() != "backoff" else 3.9,
        "blacklist": "",
        "attempt": 2 if str(job.get("status") or "").lower() == "backoff" else 1,
        "next_retry": "—",
        "next_retry_ts": next_retry_epoch if str(job.get("status") or "").lower() == "backoff" else None,
        "reason": "provider temp pressure" if str(job.get("status") or "").lower() == "backoff" else "",
    }
    chunk_states = []
    if chunk_unique_done > 0:
        chunk_states.append(
            {
                "chunk": max(chunk_current_idx - 1, 0),
                "status": "done",
                "size": int(chunk_size),
                "sender": sender_label,
                "target_domain": dominant_domain,
                "provider_domain": dominant_domain,
                "spam_score": 1.4,
                "blacklist": "",
                "attempt": 1,
                "next_retry": "—",
                "next_retry_ts": None,
                "reason": "",
            }
        )
    chunk_states.append(base_chunk)
    current_chunk_info = {
        "chunk_id": int(base_chunk["chunk"]),
        "chunk": int(base_chunk["chunk"]),
        "status": str(base_chunk["status"]),
        "size": int(base_chunk["size"]),
        "attempt": int(base_chunk["attempt"]),
        "next_retry_ts": base_chunk["next_retry_ts"],
        "reason": str(base_chunk["reason"] or ""),
        "sender": sender_label,
        "sender_mail": sender_label,
        "target_domain": dominant_domain,
        "receiver_domain": dominant_domain,
        "spam_score": base_chunk["spam_score"],
        "blacklist": base_chunk["blacklist"],
        "delay_s": 0 if str(base_chunk["status"]).lower() != "backoff" else 30,
        "workers": 1,
        "subject": subject,
    }
    current_chunk_domains = {dominant_domain: 1} if dominant_domain else {}

    logs = [
        f"[INFO] Job {job.get('id')} status is {job.get('status')}.",
        f"[INFO] Updated at {job.get('updated_at')}.",
        f"[INFO] Campaign {job.get('campaign_id')} send counters synced.",
    ]
    send_debug = {
        "job_id": str(job.get("id") or ""),
        "campaign_id": str(job.get("campaign_id") or ""),
        "from_email": sender_from_snapshot,
        "from_name": str(send_snapshot.get("from_name") or "").strip(),
        "subject": subject,
        "smtp_host": smtp_host,
        "smtp_port": str(send_snapshot.get("smtp_port") or "").strip(),
        "chunk_size": str(send_snapshot.get("chunk_size") or "").strip(),
        "has_send_snapshot": bool(send_snapshot),
    }
    logs.append(
        f"[DEBUG] send→job link: campaign={send_debug['campaign_id'] or '-'} · job={send_debug['job_id'] or '-'} · from={send_debug['from_email'] or '-'} · smtp={send_debug['smtp_host'] or '-'}."
    )
    if deferred:
        logs.append(f"[WARN] Deferred events recorded: {deferred}.")
    if int(job.get("complained") or 0):
        logs.append(f"[WARN] Complaint events recorded: {int(job.get('complained') or 0)}.")
    if subject:
        logs.append(f"[INFO] Subject snapshot: {subject}.")
    if smtp_host:
        logs.append(f"[INFO] SMTP host snapshot: {smtp_host}.")
    runtime_logs = [str(x) for x in (job.get("runtime_logs") or []) if str(x).strip()]
    relation_debug = [str(x) for x in (job.get("send_job_debug") or []) if str(x).strip()]
    logs.extend(relation_debug[-12:])
    logs.extend(runtime_logs[-8:])

    monitor_snapshot = load_pmta_monitor_snapshot(job)
    pmta_live = monitor_snapshot.get("pmta_live", {})
    pmta_diag = monitor_snapshot.get("pmta_diag", {})
    monitor_commands_used = monitor_snapshot.get("monitor_commands_used", [])
    bridge_state = monitor_snapshot.get("bridge_state", {})
    pmta_outcomes = monitor_snapshot.get("pmta_outcomes", {})

    sent_live = pmta_outcomes.get("sent")
    delivered_live = pmta_outcomes.get("delivered")
    bounced_live = pmta_outcomes.get("bounced")
    deferred_live = pmta_outcomes.get("deferred")
    complained_live = pmta_outcomes.get("complained")

    sent_for_ui = int(sent_live) if isinstance(sent_live, int) and sent_live >= 0 else int(job.get("sent") or 0)
    delivered_for_ui = int(delivered_live) if isinstance(delivered_live, int) and delivered_live >= 0 else int(job.get("delivered") or 0)
    bounced_for_ui = int(bounced_live) if isinstance(bounced_live, int) and bounced_live >= 0 else int(job.get("failed") or 0)
    deferred_for_ui = int(deferred_live) if isinstance(deferred_live, int) and deferred_live >= 0 else int(job.get("deferred") or 0)
    complained_for_ui = int(complained_live) if isinstance(complained_live, int) and complained_live >= 0 else int(job.get("complained") or 0)

    def _series_point(ts_dt: datetime, ratio: float) -> dict:
        ratio_safe = min(1.0, max(0.0, ratio))
        return {
            "ts": iso(ts_dt),
            "delivered": int(round(delivered_for_ui * ratio_safe)),
            "bounced": int(round(bounced_for_ui * ratio_safe)),
            "deferred": int(round(deferred_for_ui * ratio_safe)),
            "complained": int(round(complained_for_ui * ratio_safe)),
        }

    outcome_series = []
    for idx in range(10):
        r = (idx + 1) / 10.0
        ts_point = now_dt - timedelta(minutes=(9 - idx))
        outcome_series.append(_series_point(ts_point, r))

    pmta_pressure = {
        "pressure_score": min(4, max(0, int((int(pmta_live.get("queued_recipients") or 0) / 1000)))),
        "signal": "queue-based",
    }
    pmta_domains = {
        "ok": True,
        "domains": {
            domain_item.get("domain", "unknown"): {
                "queued": max(0, int(domain_item.get("planned", 0) - domain_item.get("sent", 0))),
                "deferred": domain_item.get("failed", 0),
                "active": domain_item.get("sent", 0),
            }
            for domain_item in domain_state
        },
    }

    return {
        "job_id": str(job.get("id") or job_id),
        "status": str(job.get("status") or "queued"),
        "phase": str(job.get("phase") or "queued"),
        "campaign_id": str(job.get("campaign_id") or ""),
        "totals": {
            "total": total,
            "sent": sent_for_ui,
            "failed": int(job.get("failed") or 0),
            "skipped": 0,
            "invalid": 0,
        },
        "total": total,
        "sent": sent_for_ui,
        "failed": int(job.get("failed") or 0),
        "skipped": 0,
        "invalid": 0,
        "delivered": delivered_for_ui,
        "bounced": bounced_for_ui,
        "deferred": deferred_for_ui,
        "complained": complained_for_ui,
        "domain_state": domain_state,
        "chunks": [
            {
                "chunk": int(base_chunk["chunk"]),
                "status": str(base_chunk["status"]),
                "size": int(base_chunk["size"]),
                "sender": sender_label,
                "spam": base_chunk["spam_score"],
                "blacklist": base_chunk["blacklist"] or "clean",
                "attempt": int(base_chunk["attempt"]),
                "next_retry": "—" if not base_chunk["next_retry_ts"] else iso(datetime.fromtimestamp(base_chunk["next_retry_ts"], timezone.utc)),
            }
        ],
        "chunk_states": chunk_states,
        "current_chunk_info": current_chunk_info,
        "current_chunk_domains": current_chunk_domains,
        "domain_plan": domain_plan,
        "domain_sent": domain_sent_map,
        "domain_failed": domain_failed_map,
        "chunk_unique_total": chunk_unique_total,
        "chunk_unique_done": chunk_unique_done,
        "chunks_total": chunk_unique_total,
        "chunks_done": chunk_unique_done,
        "chunks_backoff": 1 if str(job.get("status") or "").lower() == "backoff" else 0,
        "chunks_abandoned": 0,
        "chunk_attempts_total": max(chunk_unique_done, sum(int(row.get("attempt") or 1) for row in chunk_states)),
        "recent_results": [
            {
                "ts": str(job.get("updated_at") or ""),
                "email": "live aggregate",
                "ok": str(job.get("status") or "").lower() not in {"error", "stopped"},
                "detail": f"Delivered {delivered} · Failed {int(job.get('failed') or 0)} · Deferred {deferred}",
            }
        ],
        "logs": logs,
        "send_debug": send_debug,
        "send_job_relation_logs": relation_debug[-50:],
        "outcome_series": outcome_series,
        "telemetry": {
            "mode": str(job.get("bridge_mode") or "counts"),
            "parallel_lanes": [
                {
                    "lane": "lane-1",
                    "sender": sender_label,
                    "provider": provider,
                    "state": str(job.get("status") or "queued"),
                    "processed": int(job.get("sent") or 0),
                    "success": delivered,
                    "temp_fail": deferred,
                    "hard_fail": int(job.get("failed") or 0),
                    "workers": 1,
                }
            ],
        },
        "pmta_live": pmta_live,
        "pmta_diag": pmta_diag,
        "pmta_pressure": pmta_pressure,
        "pmta_domains": pmta_domains,
        "monitor_commands_used": monitor_commands_used,
        "bridge_state": bridge_state,
        "bridge_mode": str(job.get("bridge_mode") or "counts"),
        "bridge_last_success_ts": str(bridge_state.get("last_success_ts") or ""),
        "accounting_last_update_ts": str(pmta_live.get("ts") or ""),
        "accounting_last_ts": str(pmta_live.get("ts") or ""),
        "progress": progress,
        "current_chunk": int(job.get("current_chunk") or 1),
        "bridge_failure_count": int(bridge_state.get("failure_count") or 0),
        "bridge_last_error_message": str(bridge_state.get("last_error") or ""),
        "diagnostics": job.get("diagnostics") if isinstance(job.get("diagnostics"), dict) else {},
    }

JOBS = [
    {
        "id": "job-240301-a",
        "campaign_id": "cmp-demo-001",
        "status": "running",
        "bridge_mode": "counts",
        "provider": "gmail",
        "risk": "deliverability_high",
        "created_at": iso(NOW - timedelta(hours=7)),
        "updated_at": iso(NOW - timedelta(seconds=30)),
        "sent": 22144,
        "failed": 824,
        "delivered": 21400,
        "deferred": 612,
        "complained": 18,
        "queued": 3842,
        "progress": 84,
        "top_domains": ["gmail.com", "yahoo.com", "outlook.com"],
    },
    {
        "id": "job-240301-b",
        "campaign_id": "cmp-demo-001",
        "status": "backoff",
        "bridge_mode": "legacy",
        "provider": "yahoo",
        "risk": "stale",
        "created_at": iso(NOW - timedelta(days=1, hours=2)),
        "updated_at": iso(NOW - timedelta(minutes=18)),
        "sent": 14488,
        "failed": 1350,
        "delivered": 13002,
        "deferred": 904,
        "complained": 22,
        "queued": 910,
        "progress": 63,
        "top_domains": ["yahoo.com", "aol.com", "icloud.com"],
    },
    {
        "id": "job-240301-c",
        "campaign_id": "cmp-demo-002",
        "status": "paused",
        "bridge_mode": "counts",
        "provider": "outlook",
        "risk": "internal_degraded",
        "created_at": iso(NOW - timedelta(days=2)),
        "updated_at": iso(NOW - timedelta(hours=2, minutes=12)),
        "sent": 6014,
        "failed": 388,
        "delivered": 5701,
        "deferred": 211,
        "complained": 8,
        "queued": 220,
        "progress": 47,
        "top_domains": ["hotmail.com", "outlook.com", "live.com"],
    },
]

JOB_DETAIL = {
    "job_id": "job-240301-a",
    "status": "running",
    "campaign_id": "cmp-demo-001",
    "totals": {"total": 48250, "sent": 42990, "failed": 1188, "skipped": 903, "invalid": 211},
    "domain_state": [
        {"domain": "gmail.com", "planned": 22000, "sent": 19750, "failed": 411, "pct": 92},
        {"domain": "yahoo.com", "planned": 9800, "sent": 7210, "failed": 502, "pct": 78},
        {"domain": "outlook.com", "planned": 8700, "sent": 7440, "failed": 190, "pct": 87},
        {"domain": "icloud.com", "planned": 4200, "sent": 3590, "failed": 85, "pct": 88},
    ],
    "chunks": [
        {"chunk": 188, "status": "running", "size": 250, "sender": "hello@brand-alpha.com", "spam": 2.2, "blacklist": "clean", "attempt": 1, "next_retry": "—"},
        {"chunk": 187, "status": "backoff", "size": 250, "sender": "info@brand-beta.net", "spam": 4.4, "blacklist": "listed", "attempt": 2, "next_retry": "00:02:20"},
        {"chunk": 186, "status": "done", "size": 250, "sender": "hello@brand-alpha.com", "spam": 2.0, "blacklist": "clean", "attempt": 1, "next_retry": "—"},
    ],
    "recent_results": [
        {"ts": iso(NOW - timedelta(minutes=1)), "email": "mona@gmail.com", "ok": True, "detail": "250 2.0.0 Accepted"},
        {"ts": iso(NOW - timedelta(minutes=2)), "email": "saad@yahoo.com", "ok": False, "detail": "421 4.7.0 Temporarily deferred"},
        {"ts": iso(NOW - timedelta(minutes=3)), "email": "nour@outlook.com", "ok": True, "detail": "250 2.6.0 Queued"},
        {"ts": iso(NOW - timedelta(minutes=4)), "email": "huda@icloud.com", "ok": False, "detail": "550 5.1.1 User unknown"},
    ],
    "logs": [
        "[INFO] Chunk 188 started on gmail lane.",
        "[WARN] Yahoo provider triggered adaptive slow mode.",
        "[INFO] Accounting bridge synced 782 events.",
        "[INFO] Preview-only dashboard using fake data.",
    ],
    "telemetry": {
        "mode": "v2 parallel sender lanes",
        "parallel_lanes": [
            {"lane": "lane-1", "sender": "hello@brand-alpha.com", "provider": "gmail.com", "state": "running", "processed": 8400, "success": 8160, "temp_fail": 166, "hard_fail": 74, "workers": 6},
            {"lane": "lane-2", "sender": "info@brand-beta.net", "provider": "yahoo.com", "state": "backoff", "processed": 5220, "success": 4488, "temp_fail": 601, "hard_fail": 131, "workers": 3},
            {"lane": "lane-3", "sender": "promo@offers-demo.org", "provider": "outlook.com", "state": "running", "processed": 6310, "success": 6122, "temp_fail": 110, "hard_fail": 78, "workers": 4},
        ],
    },
}

CONFIG_GROUPS = [
    {"group": "SMTP", "items": [
        {"key": "SHIVA_HOST", "value": "0.0.0.0", "type": "str", "source": "ui", "restart": True, "desc": "Flask bind host"},
        {"key": "SHIVA_PORT", "value": "5001", "type": "int", "source": "ui", "restart": True, "desc": "Flask bind port"},
        {"key": "SPAMCHECK_BACKEND", "value": "spamd", "type": "choice", "source": "env", "restart": False, "desc": "Spam score backend"},
    ]},
    {"group": "PMTA", "items": [
        {"key": "PMTA_QUEUE_BACKOFF", "value": "1", "type": "bool", "source": "ui", "restart": False, "desc": "Enable queue-based backoff"},
        {"key": "PMTA_PRESSURE_CONTROL", "value": "1", "type": "bool", "source": "default", "restart": False, "desc": "Enable pressure monitoring"},
        {"key": "PMTA_LIVE_POLL_S", "value": "5", "type": "int", "source": "ui", "restart": False, "desc": "Refresh interval for fake live stats"},
    ]},
    {"group": "Scheduler", "items": [
        {"key": "SHIVA_SCHEDULER_MODE", "value": "v2", "type": "choice", "source": "ui", "restart": False, "desc": "Fake scheduler mode"},
        {"key": "SHIVA_MAX_PARALLEL_LANES", "value": "8", "type": "int", "source": "ui", "restart": False, "desc": "Max parallel lanes"},
        {"key": "SHIVA_RESOURCE_GOVERNOR", "value": "1", "type": "bool", "source": "default", "restart": False, "desc": "Resource governor status"},
    ]},
]

JOBS_NAV_ITEMS = [
    {"label": "Overview", "href": "#job-overview"},
    {"label": "PMTA Live", "href": "#job-pmta-live"},
    {"label": "Outcomes", "href": "#job-outcomes"},
    {"label": "Providers", "href": "#job-providers"},
    {"label": "Chunk preflight", "href": "#job-chunk-preflight"},
]

JOBS_SHOWCASE_HTML = r"""
<div class="job" id="job-overview" data-jobid="83b5cd63007e" data-created="2026-03-22T10:19:10Z">
  <div class="jobTop">
    <div>
      <div class="titleRow">
        <div style="font-weight:900">Job <code>83b5cd63007e</code></div>
        <div class="pill bad" data-k="status">Status: error</div>
        <div class="pill" data-k="speed">0 epm</div>
        <div class="pill" data-k="eta">ETA —</div>
      </div>
      <div class="triageRow">
        <div class="triageBadge" data-k="badgeMode"><span class="badgeLabel">—</span><span class="tip" data-tip="Bridge mode not available yet for this job.">ⓘ</span></div>
        <div class="triageBadge" data-k="badgeFreshness"><span class="badgeLabel">—</span><span class="tip" data-tip="Freshness signal: how recent accounting or legacy ingestion updates are for this job.">ⓘ</span></div>
        <div class="triageBadge good" data-k="badgeHealth"><span class="badgeLabel">OK (0)</span><span class="tip" data-tip="Internal health checks are clean (no bridge/runtime failure counters).">ⓘ</span></div>
        <div class="triageBadge" data-k="badgeRisk"><span class="badgeLabel">RISK —</span><span class="tip" data-tip="Deliverability risk derived from bounce, complaint, and deferred rates.">ⓘ</span></div>
        <div class="triageBadge bridgeConnBadge bad" data-k="badgeBridgeConn" title="Bridge↔Shiva disconnected"><span class="statusDot bad" aria-hidden="true"></span><span>Bridge↔Shiva disconnected</span><span class="tip" data-tip="Real-time bridge transport status between PMTA accounting bridge and Shiva receiver. Current endpoint is not available yet.">ⓘ</span></div>
        <div class="triageBadge" data-k="badgeIntegrity" style="display:none"><span class="badgeLabel">INTEGRITY</span><span class="tip" data-tip="Data integrity counters are clean.">ⓘ</span></div>
      </div>
      <div class="mini">Created: <span class="muted">2026-03-22T10:19:10Z</span></div>
      <div class="mini" data-k="alerts">Quick issues: ❌ abandoned chunks</div>
    </div>

    <div class="nav jobActionNav" style="margin-top:0">
      <a class="btn secondary" href="/jobs">Open</a>
      <button class="btn secondary" type="button" data-action="pause" disabled>⏸ Pause</button>
      <button class="btn secondary" type="button" data-action="resume" disabled>▶ Resume</button>
      <button class="btn danger" type="button" data-action="stop" disabled>⛔ Stop</button>
      <button class="btn danger" type="button" data-action="delete">🗑 Delete</button>
    </div>
  </div>

  <div class="kpiWrap">
    <div class="kpiRow">
      <div class="kpiCell kpi-sent"><div class="k">Sent</div><div class="v"><span data-k="sent">0</span></div></div>
      <div class="kpiCell"><div class="k">Pending</div><div class="v"><span data-k="pending">0</span><span class="kpiWarn" data-k="pendingWarn" style="display:none" title="Pending was clamped to 0 because Sent is lower than PMTA outcomes.">⚠</span></div></div>
      <div class="kpiCell kpi-del"><div class="k">Del</div><div class="v"><span data-k="delivered">0</span></div></div>
      <div class="kpiCell kpi-bnc"><div class="k">Bnc</div><div class="v"><span data-k="bounced">0</span></div></div>
      <div class="kpiCell kpi-def"><div class="k">Def</div><div class="v"><span data-k="deferred">0</span></div></div>
      <div class="kpiCell kpi-cmp"><div class="k">Cmp</div><div class="v"><span data-k="complained">0</span></div></div>
    </div>
    <div class="ratesRow">
      <div class="rateCell"><div class="k">Bounce %</div><div class="v" data-k="rateBounce">—</div></div>
      <div class="rateCell"><div class="k">Complaint %</div><div class="v" data-k="rateComplaint">—</div></div>
      <div class="rateCell"><div class="k">Deferred %</div><div class="v" data-k="rateDeferred">—</div></div>
    </div>

    <div class="panel" id="job-pmta-live" style="margin-top:10px;">
      <h4>PMTA Live Panel</h4>
      <div class="pmtaLive" data-k="pmtaLine">
        <div class="pmtaGrid">
          <div class="pmtaBox"><div class="pmtaTitle"><span>Spool</span><span class="tag good">rcpt</span></div><div class="pmtaHint">Total recipients/messages currently held by PMTA spool.</div><div class="pmtaRow"><span class="pmtaKey">RCPT</span><span class="pmtaVal good pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">MSG</span><span class="pmtaVal good">—</span></div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Queue</span><span class="tag good">rcpt</span></div><div class="pmtaHint">Recipients/messages still queued to be delivered.</div><div class="pmtaRow"><span class="pmtaKey">RCPT</span><span class="pmtaVal good pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">MSG</span><span class="pmtaVal good">—</span></div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Connections</span></div><div class="pmtaHint">Live SMTP sessions used for inbound/outbound traffic.</div><div class="pmtaRow"><span class="pmtaKey">SMTP In</span><span class="pmtaVal good pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">SMTP Out</span><span class="pmtaVal good pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">Total</span><span class="pmtaVal good">—</span></div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Last minute</span></div><div class="pmtaHint">Recent PMTA throughput over the last 60 seconds.</div><div class="pmtaRow"><span class="pmtaKey">In</span><span class="pmtaVal warn pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">Out</span><span class="pmtaVal warn pmtaBig">—</span></div><div class="pmtaSub">traffic recipients / minute</div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Last hour</span></div><div class="pmtaHint">Rolling traffic totals for the previous 60 minutes.</div><div class="pmtaRow"><span class="pmtaKey">In</span><span class="pmtaVal warn pmtaBig">—</span></div><div class="pmtaRow"><span class="pmtaKey">Out</span><span class="pmtaVal warn pmtaBig">—</span></div><div class="pmtaSub">traffic recipients / hour</div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Top queues</span></div><div class="pmtaHint">Queues with the highest recipient backlog and latest queue errors.</div><div class="pmtaSub">0=0</div></div>
          <div class="pmtaBox"><div class="pmtaTitle"><span>Time</span></div><div class="pmtaHint">Timestamp of the latest PMTA snapshot used for this panel.</div><div class="pmtaSub">2026-03-22T10:19:41Z</div></div>
        </div>
      </div>
      <div class="mini" style="margin-top:6px" data-k="pmtaNote">Note: <b>sent</b> = accepted by PMTA (client-side). Delivery may still be queued/deferred.</div>
      <div class="chunkMeta" style="margin-top:6px" data-k="pmtaDiag"><span class="chunkMetaPill">Diag: —</span></div>
      <div class="mini" style="margin-top:8px"><b>Error summary</b></div>
      <div class="mini errorSummaryBox" data-k="pmtaErrorSummary" style="display: none;"></div>
    </div>

    <details class="qualityMini">
      <summary>Quality</summary>
      <div class="qualityLine">Final-fail: <span data-k="failed">0</span> · Skipped: <span data-k="skipped">0</span> · Invalid: <span data-k="invalid">0</span> · Total: <span data-k="total">1</span></div>
    </details>
  </div>

  <div class="bars">
    <div class="panel">
      <h4>Progress</h4>
      <div class="mini" data-k="progressText">Send progress: 0% (0/1)</div>
      <div class="bar"><div data-k="barSend" style="width: 0%;"></div></div>
      <div class="mini" style="margin-top:8px" data-k="chunksText">Chunks: 1/1 done · backoff_events=0 · abandoned=1</div>
      <div class="mini" data-k="attemptsText" style="display:none">—</div>
      <div class="bar"><div data-k="barChunks" style="width: 100%;"></div></div>
      <div class="mini" style="margin-top:8px" data-k="domainsText">Domains: 0% (0/1)</div>
      <div class="bar"><div data-k="barDomains" style="width: 0%;"></div></div>
    </div>
  </div>

  <div class="quickIssues" data-k="quickIssues">Quick issues: ❌ abandoned chunks</div>

  <details class="more" open>
    <summary>More details</summary>
    <div class="moreBlock twoCol">
      <div class="panel">
        <h4>Current chunk</h4>
        <div class="mini">Current send settings + top active domains in this running chunk.</div>
        <div class="mini" data-k="chunkLine"><div class="mini">—</div></div>
        <div class="mini" data-k="chunkDomains"><div class="mini chunkNote chunkNoteDomains">🔥 Top active domains: —</div></div>
      </div>
      <div class="panel">
        <h4>Backoff</h4>
        <div class="mini">Latest retry event when PMTA/provider pressure slows delivery.</div>
        <div class="mini" data-k="backoffLine">—</div>
      </div>
    </div>

    <div class="panel moreBlock" id="job-outcomes">
      <h4>Outcomes (PMTA accounting)</h4>
      <div class="outcomesWrap" data-k="outcomes">
        <div class="outcomesGrid">
          <div class="outChip del"><span class="k">Delivered</span><span class="v">0</span></div>
          <div class="outChip bnc"><span class="k">Bounced</span><span class="v">0</span></div>
          <div class="outChip def"><span class="k">Deferred</span><span class="v">0</span></div>
          <div class="outChip cmp"><span class="k">Complained</span><span class="v">0</span></div>
        </div>
        <div class="outMeta">Pending (sent - final outcomes): <b>0</b> · PMTA queue now: <b>0</b></div>
        <div class="outMeta">Last accounting update: —</div>
      </div>
      <div class="outTrend" data-k="outcomeTrend">Trend · —</div>
    </div>

    <div class="panel moreBlock" id="job-logs">
      <h4>Logs</h4>
      <div class="mini" data-k="jobLogs">—</div>
    </div>

    <div class="moreGrid moreBlock">
      <div class="panel" id="job-providers">
        <h4 data-k="domainsPanelTitle">Top providers</h4>
        <div class="mini" data-k="topDomains">Gmail: <b>0</b> · Yahoo: <b>0</b> · Outlook: <b>0</b> · iCloud: <b>0</b> · Other: <b>1</b></div>
        <div class="mini" style="margin-top: 10px; display: none;"><b>Domain progress (bars)</b></div>
        <div data-k="topDomainsBars"><div style="margin-top:10px"><div class="mini"><b>Gmail</b> · 0</div><div class="smallBar"><div style="width:0%"></div></div></div><div style="margin-top:10px"><div class="mini"><b>Yahoo</b> · 0</div><div class="smallBar"><div style="width:0%"></div></div></div><div style="margin-top:10px"><div class="mini"><b>Outlook</b> · 0</div><div class="smallBar"><div style="width:0%"></div></div></div><div style="margin-top:10px"><div class="mini"><b>iCloud</b> · 0</div><div class="smallBar"><div style="width:0%"></div></div></div><div style="margin-top:10px"><div class="mini"><b>Other</b> · 1</div><div class="smallBar"><div style="width:100%"></div></div></div></div>
      </div>

      <div class="panel">
        <h4 class="sopHeader">📌 System / Provider / Integrity</h4>

        <div class="sopBlock">
          <div class="sopLabel system">🖥️ System / Internal</div>
          <div class="sopLine" data-k="systemSummary">🔗 Bridge failures: <b>0</b> · ⏱️ Last bridge success: <b>0m ago</b> · ⚙️ Runtime internal errors: <b>0</b> · 💾 DB write failures: <b>0</b></div>
          <details class="errorFold">
            <summary>View details</summary>
            <div class="mini" style="margin-top:8px" data-k="systemDetails">—</div>
          </details>
        </div>

        <div class="sopBlock">
          <div class="sopLabel provider">📬 Provider / Deliverability</div>
          <div class="sopLine" data-k="providerSummary">✅ Delivered: <b>0</b> (—) · ⏳ Deferred: <b>0</b> (—) · ❌ Bounced: <b>0</b> (—) · 📢 Complained: <b>0</b> (—)</div>
          <div class="sopLine" style="margin-top:6px" data-k="providerBreakdown">🌐 Provider/domain breakdown: —</div>
          <div class="sopLine" style="margin-top:6px" data-k="providerReasons">🧠 Top reason buckets: —</div>
          <details class="errorFold">
            <summary>View details</summary>
            <div class="mini" style="margin-top:8px" data-k="providerDetails">—</div>
          </details>
        </div>

        <div class="sopBlock">
          <div class="sopLabel integrity">🗂️ Data Integrity / Mapping</div>
          <div class="sopLine" data-k="integritySummary">♻️ duplicates_dropped: <b>0</b> · 🔎 job_not_found: <b>0</b> · 🧾 missing_fields: <b>0</b> · 💽 db_write_failures: <b>0</b></div>
          <details class="errorFold">
            <summary>View details</summary>
            <div class="mini" style="margin-top:8px" data-k="integrityDetails">—</div>
          </details>
        </div>

        <div class="legacyDiagnosticsBox">
          <div class="legacyDiagnosticsTitle">📄 Legacy quality + errors (unchanged data)</div>
          <div class="legacySectionLabel">📊 Quality counters</div>
          <div class="mini legacyDataLine" data-k="counters">safe_total=0 · safe_invalid=0 · invalid_filtered=0 · skipped=0 · backoff_events=0 · abandoned_chunks=1 · paused=no · stop_requested=no</div>
          <div class="legacySectionLabel">🚨 Error type</div>
          <div class="mini legacyDataLine" data-k="errorTypes">—</div>
          <div class="legacySectionLabel">⚠️ Error summary</div>
          <div class="mini legacyDataLine" data-k="lastErrors">—</div>
          <div class="mini legacyDataLine" data-k="lastErrors2">—</div>
          <div class="mini legacyDataLine" data-k="internalErrors">—</div>
        </div>
        <div class="bridgeSnapshotBox">
          <div class="legacySectionLabel" style="margin-top:0">🌉 Data source: Bridge snapshot</div>
          <div class="mini legacyDataLine" style="margin-top:8px" data-k="bridgeReceiver">Data source: <b>Bridge snapshot</b><br>Last poll success: <b>2026-03-22T11:55:02Z (2m ago)</b><br>Last accounting update: <b>—</b></div>
        </div>
      </div>
    </div>

    <div class="panel" id="job-chunk-preflight" style="margin-top:10px">
      <h4>Chunk preflight</h4>
      <div class="mini" style="margin-top:6px"><b>Active / Live chunk</b></div>
      <div style="overflow:auto; margin-top:8px">
        <table>
          <thead>
            <tr>
              <th>Chunk</th>
              <th>Status</th>
              <th>Size</th>
              <th>Sender mail</th>
              <th>Receiver domain</th>
              <th>Spam</th>
              <th>Blacklist</th>
            </tr>
          </thead>
          <tbody data-k="chunkLive"><tr><td colspan="7" class="mini">No active chunk right now.</td></tr></tbody>
        </table>
      </div>

      <div class="mini" style="margin-top:10px"><b>History chunk (last 12)</b></div>
      <div style="overflow:auto; margin-top:8px">
        <table>
          <thead>
            <tr>
              <th>Chunk</th>
              <th>Status</th>
              <th>Size</th>
              <th>Sender mail</th>
              <th>Receiver domain</th>
              <th>Spam</th>
              <th>Blacklist</th>
              <th>Attempt</th>
              <th>Next retry</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody data-k="chunkHist"><tr><td colspan="10" class="mini">No chunk states yet.</td></tr></tbody>
        </table>
      </div>
    </div>
  </details>
</div>
"""


def build_live_snapshot() -> dict:
    snapshot = copy.deepcopy(DASHBOARD_DATA)
    accounting = build_accounting_summary()
    jitter = random.randint(-80, 80)
    queue_jitter = random.randint(-120, 120)
    snapshot["kpis"] = copy.deepcopy(DASHBOARD_DATA["kpis"])
    snapshot["kpis"][1]["value"] = f"{41932 + jitter:,}"
    snapshot["kpis"][3]["value"] = f"{accounting['totals']['bounced'] + abs(jitter // 4):,}"
    snapshot["kpis"][7]["value"] = f"{max(0, accounting['queue_snapshot']['live_queue'] + queue_jitter):,}"
    snapshot["progress"] = {
        "overall": max(10, min(100, DASHBOARD_DATA["progress"]["overall"] + random.randint(-2, 2))),
        "domain": max(10, min(100, DASHBOARD_DATA["progress"]["domain"] + random.randint(-2, 2))),
        "chunks": max(10, min(100, DASHBOARD_DATA["progress"]["chunks"] + random.randint(-3, 3))),
        "warmup": max(10, min(100, DASHBOARD_DATA["progress"]["warmup"] + random.randint(-1, 1))),
    }
    snapshot["campaign"]["updated_at"] = iso(datetime.now(timezone.utc))
    snapshot["accounting"] = accounting
    return snapshot


def _pick_latest_job_for_campaign(campaign_id: str) -> dict | None:
    target_campaign_id = str(campaign_id or "").strip()
    if not target_campaign_id:
        return None
    campaign_jobs = [row for row in JOBS if str(row.get("campaign_id") or "").strip() == target_campaign_id]
    if not campaign_jobs:
        return None
    return sorted(
        campaign_jobs,
        key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
        reverse=True,
    )[0]


def _build_jobs_send_preview(preferred_job_id: str = "") -> dict:
    campaigns = sorted(
        CAMPAIGNS_STATE,
        key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
        reverse=True,
    )
    campaign = campaigns[0] if campaigns else {}
    campaign_id = str(campaign.get("id") or "preview").strip() or "preview"
    campaign_name = str(campaign.get("name") or "").strip()
    created_at = str(campaign.get("updated_at") or campaign.get("created_at") or iso(datetime.now(timezone.utc)))

    form_state = CAMPAIGN_FORMS_STATE.get(campaign_id, {}) if campaign_id else {}
    from_email = str(form_state.get("from_email") or "").strip() or "—"
    smtp_host = str(form_state.get("smtp_host") or "").strip() or "—"
    subject = str(form_state.get("subject") or "").strip() or "—"
    domain_plan = form_state.get("domain_plan") if isinstance(form_state.get("domain_plan"), dict) else {}
    domain_items = [str(domain).strip() for domain in domain_plan.keys() if str(domain).strip()]
    if not domain_items:
        domain_items = _extract_domains_from_from_email(from_email)
    top_domains = ", ".join(domain_items[:5]) if domain_items else "—"
    total_recipients = int(campaign.get("total_recipients") or 0)

    preferred_job = get_job(preferred_job_id) if preferred_job_id else None
    latest_campaign_job = _pick_latest_job_for_campaign(campaign_id)
    selected_job = preferred_job or latest_campaign_job
    job_id = str((selected_job or {}).get("id") or "").strip()
    status = str((selected_job or {}).get("status") or campaign.get("status") or "draft")

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "job_id": job_id,
        "created_at": created_at,
        "status": status,
        "from_email": from_email,
        "smtp_host": smtp_host,
        "subject": subject,
        "top_domains": top_domains,
        "total_recipients": total_recipients,
    }


PAGE = r"""
<!doctype html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{{ title }}</title>
  <style>
    :root{
      --bg1:#081120; --bg2:#0b1730;
      --card: rgba(255,255,255,.08);
      --card2: rgba(255,255,255,.05);
      --border: rgba(145,164,201,.18);
      --text: #e6edf7;
      --muted: #9ca9c4;
      --good: #35e49a;
      --bad: #ff5e73;
      --warn: #ffc14d;
      --accent:#7394e6;
      --shadow: 0 20px 60px rgba(0,0,0,.35);
      --radius: 18px;
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      font-family: system-ui, -apple-system, "Segoe UI", Tahoma, Arial;
      color: var(--text);
      background:
        radial-gradient(1000px 700px at 80% 20%, rgba(122,167,255,.22), transparent 60%),
        radial-gradient(900px 700px at 20% 30%, rgba(53,228,154,.16), transparent 60%),
        linear-gradient(180deg, var(--bg1), var(--bg2));
      min-height:100vh;
    }
    a{color:var(--accent); text-decoration:none}
    .content{padding:28px 18px 28px}
    .wrap{max-width: 1100px; margin: 0 auto;}
    .top{
      display:flex; gap:14px; align-items:flex-start; justify-content:space-between;
      flex-wrap:wrap; margin-bottom: 18px;
    }
    h1,.title{ margin:0; font-size: 22px; letter-spacing: .2px; }
    .title{font-size:28px}
    .sub,.subtitle{
      margin-top:6px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
      max-width: 980px;
    }
    .subtitle{font-size:14px; line-height:1.7}
    .badge,.pill,.tag{
      display:inline-flex; align-items:center; gap:8px;
      padding: 10px 12px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 999px;
      box-shadow: var(--shadow);
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      text-decoration:none;
    }
    .tag{padding:5px 10px; font-weight:800; box-shadow:none; background:rgba(255,255,255,.06)}
    .tag.good,.tone-good{color:var(--good); border-color:rgba(53,228,154,.35)}
    .tag.bad,.tone-bad{color:var(--bad); border-color:rgba(255,94,115,.35)}
    .tag.warn,.tone-warn{color:var(--warn); border-color:rgba(255,193,77,.35)}
    .tag.accent,.tone-accent{color:var(--accent); border-color:rgba(122,167,255,.35)}
    .campaignState{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      padding:6px 12px;
      border-radius:999px;
      border:1px solid transparent;
      font-size:12px;
      font-weight:800;
      letter-spacing:.01em;
      text-transform:capitalize;
      box-shadow:none;
      min-width:92px;
    }
    .campaignState.draft{background:rgba(191,140,255,.14); color:#d8bcff; border-color:rgba(191,140,255,.36)}
    .campaignState.running{background:rgba(39,194,129,.12); color:#7ff0bb; border-color:rgba(39,194,129,.35)}
    .campaignState.paused{background:rgba(244,183,64,.12); color:#ffd97d; border-color:rgba(244,183,64,.35)}
    .campaignState.done{background:rgba(122,167,255,.12); color:#b9d0ff; border-color:rgba(122,167,255,.35)}
    .campaignState.backoff{background:rgba(255,150,78,.12); color:#ffc48c; border-color:rgba(255,150,78,.35)}
    .campaignState.stop,.campaignState.stopped,.campaignState.error{background:rgba(255,107,107,.12); color:#ff9d9d; border-color:rgba(255,107,107,.35)}
    .topActions{ display:flex; flex-direction:column; gap:10px; align-items:flex-end; }
    .topLinks{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
    .grid{ display:grid; gap: 14px; }
    .grid.kpis{grid-template-columns:repeat(4,minmax(0,1fr))}
    .grid.two{grid-template-columns:1.2fr .8fr}
    .grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}
    .grid.send-layout{grid-template-columns: minmax(340px, .95fr) minmax(0, 1.05fr)}
    .stack{ display:flex; flex-direction:column; gap:14px; }
    .card{
      background: linear-gradient(180deg, var(--card), var(--card2));
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 16px;
      backdrop-filter: blur(10px);
    }
    .card h2,.card h3,.card h4{ margin:0 0 10px; font-size: 16px; color: rgba(255,255,255,.88); }
    label{ display:block; margin: 10px 0 6px; color: var(--muted); font-size: 12px; font-weight:700; }
    input, select, textarea{
      width:100%;
      padding: 11px 12px;
      border-radius: 12px;
      border: 1px solid rgba(255,255,255,.16);
      background: rgba(0,0,0,.18);
      color: var(--text);
      outline: none;
      font: inherit;
    }
    input::placeholder, textarea::placeholder{color: rgba(255,255,255,.35)}
    textarea{min-height: 130px; resize: vertical}
    .row,.split,.telemetryRow{ display:grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .hint,.alert,.laneBox,.emptyState,.check{
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.06);
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }
    .alert{margin-bottom:10px}
    .alert.good{ border-color: rgba(53,228,154,.35); background: rgba(53,228,154,.08); }
    .alert.warn{ border-color: rgba(255,193,77,.35); background: rgba(255,193,77,.08); }
    .alert.bad{ border-color: rgba(255,94,115,.35); background: rgba(255,94,115,.08); }
    .alert.accent{ border-color: rgba(122,167,255,.35); background: rgba(122,167,255,.08); }
    .actions{display:flex; gap:10px; align-items:center; justify-content:flex-start; flex-wrap: wrap; margin-top: 14px;}
    .btn, button{
      border: 1px solid rgba(255,255,255,.18);
      background: rgba(122,167,255,.18);
      color: var(--text);
      padding: 12px 14px;
      border-radius: 14px;
      cursor:pointer;
      font-weight: 600;
      letter-spacing:.2px;
      font:inherit;
    }
    .btn:hover, button:hover{filter: brightness(1.06)}
    .btn.secondary, button.secondary{ background: rgba(255,255,255,.08); }
    .btn:disabled, button:disabled{ opacity:.55; cursor:not-allowed; }
    .check{display:flex; gap: 8px; align-items:flex-start; margin-top: 12px; background: rgba(0,0,0,.12)}
    .check input{width:auto; margin-top: 2px;}
    .foot,.footerNote{ margin-top: 16px; color: rgba(255,255,255,.45); font-size: 12px; line-height: 1.7; }
    .mini,.muted{ font-size: 12px; color: var(--muted); margin-top: 8px; }
    code{background:rgba(255,255,255,.08); padding:2px 6px; border-radius:8px;}
    .smallBar,.bar{height:10px; border-radius:999px; background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.12); overflow:hidden}
    .smallBar > div,.bar > div{height:100%; width:0%; background: linear-gradient(90deg, var(--accent), rgba(53,228,154,.75));}
    .nav{display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin:8px 0 14px;}
    .nav a, .nav button{display:inline-flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid rgba(255,255,255,.14); background: rgba(255,255,255,.06); border-radius: 12px; text-decoration:none;}
    .nav a:hover{filter:brightness(1.06)}
    .nav a.primary{ background: rgba(122,167,255,.14); font-weight:800; }
    table{width:100%; border-collapse:collapse; font-size: 12px;}
    th,td{padding:8px; border-bottom:1px solid rgba(255,255,255,.10); text-align:left; vertical-align:top}
    .statsList{display:grid; gap:10px}
    .kpi .label{font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.4px}
    .kpi .value{font-size:28px; font-weight:900; margin-top:6px}
    .progressLine{margin-top:10px}
    .field{margin-bottom:12px}
    .toast-wrap{ position: fixed; right: 16px; bottom: 16px; z-index: 9999; display:flex; flex-direction:column; gap:10px; }
    .toast{ min-width: 280px; max-width: 420px; background: rgba(0,0,0,.55); border: 1px solid rgba(255,255,255,.18); box-shadow: 0 18px 55px rgba(0,0,0,.35); backdrop-filter: blur(10px); border-radius: 14px; padding: 12px 14px; color: rgba(255,255,255,.92); font-size: 13px; line-height: 1.5; animation: pop .18s ease-out; }
    @keyframes pop{ from{ transform: translateY(6px); opacity: .2; } to{ transform: translateY(0); opacity: 1; } }
    .toast .t{font-weight:800; margin-bottom:4px}
    .toast.good{ border-color: rgba(53,228,154,.35); }
    .toast.bad{ border-color: rgba(255,94,115,.35); }
    .toast.warn{ border-color: rgba(255,193,77,.35); }
    .inline-status{ margin-top: 10px; padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(255,255,255,.14); background: rgba(0,0,0,.12); color: var(--muted); font-size: 12px; line-height: 1.6; display:none; }
    .inline-status.show{ display:block; }
    .inline-status b{ color: rgba(255,255,255,.88); }
    .sectionNav{display:flex; gap:10px; flex-wrap:wrap; margin:14px 0 18px}
    .sectionNav a{display:inline-flex; align-items:center; gap:8px; padding:10px 12px; border-radius:999px; border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.05)}
    .job{padding:18px; border-radius:22px; border:1px solid var(--border); background:linear-gradient(180deg, rgba(9,16,28,.92), rgba(11,24,38,.84)); box-shadow:var(--shadow)}
    .jobTop{display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap}
    .titleRow,.triageRow,.kpiRow,.ratesRow,.outcomesGrid,.pmtaGrid,.moreGrid{display:grid; gap:10px}
    .titleRow{grid-template-columns:repeat(auto-fit,minmax(120px,max-content)); align-items:center}
    .triageRow{grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); margin-top:12px}
    .triageBadge,.chunkMetaPill,.outChip,.pmtaBox,.rateCell,.kpiCell,.sopBlock,.legacyDiagnosticsBox,.bridgeSnapshotBox{border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.05); border-radius:16px}
    .triageBadge{display:flex; align-items:center; gap:8px; padding:10px 12px; color:var(--muted)}
    .triageBadge.good{border-color:rgba(53,228,154,.3); color:var(--good)}
    .triageBadge.bad{border-color:rgba(255,94,115,.3); color:var(--bad)}
    .statusDot{width:10px; height:10px; border-radius:999px; display:inline-block; background:currentColor}
    .badgeLabel{font-weight:700}
    .tip{cursor:help; opacity:.8}
    .jobActionNav{align-self:flex-start}
    .kpiWrap,.bars,.quickIssues,.moreBlock{margin-top:14px}
    .kpiRow{grid-template-columns:repeat(auto-fit,minmax(120px,1fr))}
    .ratesRow{grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); margin-top:10px}
    .kpiCell,.rateCell,.outChip{padding:12px}
    .kpiCell .k,.rateCell .k,.outChip .k,.pmtaKey,.pmtaHint,.pmtaSub,.sopLine,.legacyDataLine{color:var(--muted); font-size:12px}
    .kpiCell .v,.rateCell .v,.outChip .v{font-size:24px; font-weight:900; margin-top:6px}
    .kpi-del .v,.outChip.del .v,.pmtaVal.good{color:var(--good)}
    .kpi-bnc .v,.outChip.bnc .v,.bridgeConnBadge.bad{color:var(--bad)}
    .kpi-def .v,.outChip.def .v,.pmtaVal.warn{color:var(--warn)}
    .kpi-cmp .v,.outChip.cmp .v{color:#ff97cf}
    .kpi-sent .v{color:var(--accent)}
    .kpiWarn{margin-left:6px; color:var(--warn)}
    .panel{padding:16px; border-radius:18px; border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.04)}
    .pmtaGrid{grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); margin-top:12px}
    .pmtaBox{padding:12px}
    .pmtaTitle{display:flex; justify-content:space-between; gap:8px; align-items:center; font-weight:800}
    .pmtaRow{display:flex; justify-content:space-between; gap:8px; margin-top:10px}
    .pmtaBig{font-size:22px; font-weight:900}
    .qualityMini{margin-top:12px}
    .qualityLine,.outMeta,.outTrend{margin-top:10px; color:var(--muted); font-size:12px}
    .quickIssues{padding:12px 14px; border:1px solid rgba(255,94,115,.25); background:rgba(255,94,115,.08); border-radius:14px; color:#ffd8df}
    .more summary,.errorFold summary,.qualityMini summary{cursor:pointer; font-weight:800}
    .twoCol{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px}
    .outcomesGrid{grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); margin-top:12px}
    .moreGrid{grid-template-columns:minmax(260px,.9fr) minmax(320px,1.1fr)}
    .sopHeader{margin-bottom:12px}
    .sopBlock,.legacyDiagnosticsBox,.bridgeSnapshotBox{padding:12px; margin-top:12px}
    .sopLabel,.legacyDiagnosticsTitle,.legacySectionLabel{font-weight:800; margin-bottom:8px}
    .sopLabel.system{color:var(--accent)}
    .sopLabel.provider{color:var(--warn)}
    .sopLabel.integrity{color:var(--good)}
    .errorSummaryBox{padding:10px 12px; border-radius:14px; border:1px dashed rgba(255,255,255,.14)}
    @media (max-width: 1200px){ .grid.kpis{grid-template-columns:repeat(2,minmax(0,1fr))} .grid.two,.grid.send-layout,.split,.telemetryRow,.twoCol,.moreGrid{grid-template-columns:1fr} }
    @media (max-width: 920px){ .grid.three{grid-template-columns:1fr} }
    @media (max-width: 520px){ .row{grid-template-columns: 1fr;} .topActions{ align-items:stretch; width:100%; } .topLinks{ justify-content:flex-start; } .content{padding:18px 14px 24px} .sectionNav a{width:100%; justify-content:center} }
  </style>
</head>
<body>
  <main class="content">
    <div class="wrap">
      {{ body|safe }}
      <div class="footerNote">All frontend surfaces now inherit the same Shiva Mini Sand dashboard visual language from this single Python file, including the embedded utility workbenches.</div>
    </div>
  </main>
<script>
async function hydrateDashboard(){
  const root = document.getElementById('liveDashboardRoot');
  if(!root) return;
  try{
    const res = await fetch('{{ url_for('api_dashboard') }}');
    const data = await res.json();
    const kpiNodes = root.querySelectorAll('[data-kpi-value]');
    kpiNodes.forEach((node, idx) => {
      if(data.kpis && data.kpis[idx]) node.textContent = data.kpis[idx].value;
    });
    Object.entries(data.progress || {}).forEach(([name, value]) => {
      const bar = root.querySelector(`[data-progress="${name}"]`);
      const text = root.querySelector(`[data-progress-text="${name}"]`);
      if(bar) bar.style.width = value + '%';
      if(text) text.textContent = value + '%';
    });
    const stamp = document.getElementById('liveStamp');
    if(stamp) stamp.textContent = data.campaign.updated_at;
  }catch(err){
    console.warn('Dashboard hydrate failed', err);
  }
}
setInterval(hydrateDashboard, 4000);
hydrateDashboard();
</script>
{{ page_script|safe }}
</body>
</html>
"""


def render(page: str, title: str, body: str, page_script: str = "") -> Response:

    html = render_template_string(
        PAGE,
        page=page,
        title=title,
        body=body,
        page_script=page_script,
        sidebar_campaign=DASHBOARD_DATA["campaign"],
    )
    return render_tool_page(html, page)



@app.get("/")
def dashboard():
    accounting = build_accounting_summary()
    body = render_template_string(
        """
        <div class="top">
          <div>
            <h1 class="title">Dashboard frontend skeleton</h1>
            <div class="subtitle">A full Flask-only mock frontend that mirrors the core dashboard surfaces: overview KPIs, alerts, campaign form, preflight summary, jobs, telemetry, config, and campaign operations — all backed by fake data.</div>
          </div>
          <div class="actions">
            <a class="btn" href="{{ url_for('jobs_page') }}">Open Jobs</a>
            <a class="btn secondary" href="{{ url_for('config_page') }}">Open Config</a>
            <span class="pill">Live fake refresh: <b id="liveStamp">{{ data.campaign.updated_at }}</b></span>
          </div>
        </div>

        <div id="liveDashboardRoot">
          <div class="grid kpis">
            {% for item in data.kpis %}
            <div class="card kpi">
              <div class="label">{{ item.label }}</div>
              <div class="value tone-{{ item.tone if item.tone in ['good','bad','warn','accent'] else 'accent' }}" data-kpi-value>{{ item.value }}</div>
              <div class="mini">{{ item.hint }}</div>
            </div>
            {% endfor %}
          </div>

          <div class="grid two" style="margin-top:14px">
            <div class="card">
              <h2>Campaign summary</h2>
              <div class="split">
                <div class="statsList">
                  <div><span class="mini">Campaign</span><div><b>{{ data.campaign.name }}</b></div></div>
                  <div><span class="mini">Owner</span><div>{{ data.campaign.owner }}</div></div>
                  <div><span class="mini">Campaign ID</span><div><code>{{ data.campaign.id }}</code></div></div>
                  <div><span class="mini">Status</span><div><span class="tag good">{{ data.campaign.status }}</span></div></div>
                </div>
                <div class="statsList">
                  {% for key, value in data.progress.items() %}
                  <div class="progressLine">
                    <div style="display:flex; justify-content:space-between; gap:8px; margin-bottom:6px">
                      <span style="text-transform:capitalize">{{ key }}</span>
                      <b data-progress-text="{{ key }}">{{ value }}%</b>
                    </div>
                    <div class="bar"><div data-progress="{{ key }}" style="width:{{ value }}%"></div></div>
                  </div>
                  {% endfor %}
                </div>
              </div>
            </div>
            <div class="card">
              <h2>Alerts & notices</h2>
              {% for alert in data.alerts %}
              <div class="alert {{ alert.tone }}">
                <div style="font-weight:800">{{ alert.title }}</div>
                <div class="mini" style="margin-top:6px">{{ alert.body }}</div>
              </div>
              {% endfor %}
            </div>
          </div>

          <div class="grid two" style="margin-top:14px">
            <div class="card">
              <h2>Excel audience workflow</h2>
              <div class="mini">Mini Shiva now highlights how the Excel import is prepared before operators open the dedicated Send surface.</div>
              <div style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap">
                <span class="tag accent">Workbook {{ data.excel_info.file_name }}</span>
                <span class="tag good">Sheet {{ data.excel_info.sheet_name }}</span>
                <span class="tag">Rows {{ data.excel_info.rows_total }}</span>
                <span class="tag good">Validated {{ data.excel_info.validated_rows }}</span>
                <span class="tag warn">Suppressed {{ data.excel_info.suppressed_rows }}</span>
              </div>
              <div class="grid two" style="margin-top:12px">
                <div>
                  <h3 style="margin:0 0 10px">Mapped columns</h3>
                  <table>
                    <thead><tr><th>Column</th><th>Usage</th></tr></thead>
                    <tbody>
                      {% for column in data.excel_info.columns %}
                      <tr>
                        <td><code>{{ column.name }}</code></td>
                        <td>{{ column.description }}</td>
                      </tr>
                      {% endfor %}
                    </tbody>
                  </table>
                </div>
                <div>
                  <h3 style="margin:0 0 10px">Preparation checks</h3>
                  <div class="statsList">
                    {% for item in data.excel_info.checks %}
                    <div class="alert accent" style="margin:0">{{ item }}</div>
                    {% endfor %}
                  </div>
                </div>
              </div>
            </div>
            <div class="card">
              <h2>Preflight summary</h2>
              <div class="mini">SMTP host: <code>{{ data.preflight.smtp_host }}</code> · Backend: {{ data.preflight.backend }}</div>
              <div style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap">
                <span class="tag good">Spam {{ data.preflight.spam_score }}</span>
                <span class="tag warn">Limit {{ data.preflight.spam_limit }}</span>
                <span class="tag accent">{{ data.preflight.sender_domains|length }} sender domains</span>
              </div>
              <div style="overflow:auto; margin-top:12px">
                <table>
                  <thead><tr><th>Domain</th><th>IPs</th><th>Status</th><th>Spam</th></tr></thead>
                  <tbody>
                    {% for item in data.preflight.sender_domains %}
                    <tr>
                      <td>{{ item.domain }}</td>
                      <td>{{ item.ips|join(', ') }}</td>
                      <td><span class="tag {{ 'bad' if item.status == 'Listed' else 'good' }}">{{ item.status }}</span></td>
                      <td>{{ item.spam_score }}</td>
                    </tr>
                    {% endfor %}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="grid two" style="margin-top:14px">
            <div class="card">
              <h2>Accounting summary</h2>
              <div class="mini">Live PMTA accounting feed wired into Shiva from <code>{{ accounting.source.accounting_file }}</code>. When the file is unavailable, the page falls back to bundled fake rows that mirror PMTA accounting columns.</div>
              <div class="grid two" style="margin-top:12px">
                <div class="alert good" style="margin:0">
                  <div style="font-weight:800">Delivered</div>
                  <div style="font-size:22px; font-weight:900; margin-top:8px">{{ accounting.totals.delivered }}</div>
                  <div class="mini">{{ accounting.totals.delivery_rate }}% delivery rate</div>
                </div>
                <div class="alert {{ 'warn' if accounting.totals.bounced else 'accent' }}" style="margin:0">
                  <div style="font-weight:800">Bounced / Deferred</div>
                  <div style="font-size:22px; font-weight:900; margin-top:8px">{{ accounting.totals.bounced }} / {{ accounting.totals.deferred }}</div>
                  <div class="mini">Queue now {{ accounting.queue_snapshot.live_queue }} · active jobs {{ accounting.queue_snapshot.active_jobs }}</div>
                </div>
              </div>
              <div class="statsList" style="margin-top:12px">
                {% for row in accounting.top_domains[:4] %}
                <div class="alert accent" style="margin:0">
                  <div style="display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap">
                    <b>{{ row.domain }}</b>
                    <span>{{ row.delivery_rate }}% delivered</span>
                  </div>
                  <div class="mini">Total {{ row.total }} · Bounced {{ row.bounced }} · Deferred {{ row.deferred }} · MX {{ row.top_mx }}</div>
                </div>
                {% endfor %}
              </div>
              <div class="actions">
                <a class="btn" href="{{ url_for('accounting_page') }}">Open Accounting Summary</a>
              </div>
            </div>
            <div class="card">
              <h2>Operations snapshot</h2>
              <div class="grid two" style="margin-top:12px">
                {% for item in data.ops_snapshot %}
                <div class="alert {{ item.tone }}" style="margin:0">
                  <div style="font-weight:800">{{ item.label }}</div>
                  <div style="font-size:22px; font-weight:900; margin-top:8px">{{ item.value }}</div>
                  <div class="mini">{{ item.hint }}</div>
                </div>
                {% endfor %}
              </div>
            </div>
            <div class="card">
              <h2>Dashboard fake notes</h2>
              <div class="statsList" style="margin-top:12px">
                {% for note in data.dashboard_notes %}
                <div class="alert {{ note.tone }}" style="margin:0">
                  <div style="font-weight:800">{{ note.title }}</div>
                  <div class="mini" style="margin-top:6px">{{ note.body }}</div>
                </div>
                {% endfor %}
              </div>
            </div>
          </div>
        </div>
        """,
        data=DASHBOARD_DATA,
        accounting=accounting,
    )
    return render("dashboard", "Shiva Dashboard", body)


@app.get("/send")
def send_page():
    requested_campaign_id = (request.args.get("campaign_id") or "").strip()
    create_new = (request.args.get("new") or "").strip().lower() in {"1", "true", "yes"}
    if create_new or not requested_campaign_id:
        campaign_id = f"cmp-{uuid.uuid4().hex[:10]}"
    else:
        campaign_id = requested_campaign_id
    campaign = get_or_create_campaign(campaign_id)
    body, page_script = script4.render_send_page(
        NOW.strftime("%Y-%m-%d %H:%M:%S"),
        campaign_id=campaign_id,
        campaign_name_suffix=campaign_heading_suffix(campaign_id),
    )
    campaign["updated_at"] = iso(datetime.now(timezone.utc))
    save_campaigns(CAMPAIGNS_STATE)
    return render("send", "Shiva Send", body, page_script=page_script)


def _extract_domains_from_from_email(from_email_value: str) -> list[str]:
    text = str(from_email_value or "").strip()
    if not text:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    tokens = re.split(r"[\n,;]+", text)
    for token in tokens:
        candidate = token.strip().strip("<>").strip()
        if not candidate:
            continue
        if "@" in candidate:
            candidate = candidate.rsplit("@", 1)[-1].strip()
        candidate = candidate.lower().strip(".")
        if not candidate or "." not in candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _resolve_domain_ips(domain: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP)
    except Exception:
        return []

    ips: list[str] = []
    seen: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip = str(sockaddr[0]).strip()
        if not ip or ip in seen:
            continue
        seen.add(ip)
        ips.append(ip)
    return ips


@app.post("/api/preflight")
def api_preflight():
    payload = request.get_json(silent=True) or {}
    from_email = payload.get("from_email", "")
    sender_domains = _extract_domains_from_from_email(from_email)
    try:
        spam_threshold = float(payload.get("spam_limit") or 4)
    except Exception:
        spam_threshold = 4.0

    sender_domain_ips: dict[str, list[str]] = {}
    sender_domain_ip_listings: dict[str, dict[str, list[dict]]] = {}
    sender_domain_dbl_listings: dict[str, list[dict]] = {}
    sender_domain_scores: dict[str, float] = {}
    sender_domain_auth: dict[str, dict[str, dict[str, str]]] = {}
    provider_errors: list[str] = []

    rotator = None
    if sender_domains:
        try:
            rotator = script1.AccountRotator(script1.ACCOUNTS, script1.MAX_REQUESTS_PER_ACCOUNT)
        except Exception as exc:
            provider_errors.append(f"Spamhaus account init failed: {exc}")

    for domain in sender_domains:
        sender_domain_ips[domain] = _resolve_domain_ips(domain)
        sender_domain_ip_listings[domain] = {}
        sender_domain_dbl_listings[domain] = []
        sender_domain_auth[domain] = {
            "spf": {"status": "pass"},
            "dkim": {"status": "pass"},
            "dmarc": {"status": "pass"},
        }

        if not rotator:
            continue

        try:
            general = rotator.get_domain_general(domain) or {}
            listing = rotator.get_domain_listing(domain) or {}
            raw_score = general.get("score")
            if isinstance(raw_score, (int, float)):
                sender_domain_scores[domain] = float(raw_score)

            is_listed = bool(
                listing.get("is-listed", False)
                or listing.get("is_listed", False)
                or listing.get("listed", False)
            )
            if is_listed:
                sender_domain_dbl_listings[domain] = [{"zone": "dbl.spamhaus.org"}]
        except Exception as exc:
            provider_errors.append(f"{domain}: {exc}")

    response = {
        "ok": True,
        "spam_score": 0.0,
        "spam_threshold": spam_threshold,
        "spam_backend": "spamhaus-intel",
        "ip_listings": {},
        "domain_listings": [],
        "sender_domains": sender_domains,
        "sender_domain_ips": sender_domain_ips,
        "sender_domain_ip_listings": sender_domain_ip_listings,
        "sender_domain_dbl_listings": sender_domain_dbl_listings,
        "sender_domain_spam_scores": sender_domain_scores,
        "sender_domain_scores": sender_domain_scores,
        "sender_domain_auth": sender_domain_auth,
    }
    if provider_errors:
        response["warnings"] = provider_errors
        response["spam_backend"] = "spamhaus-intel (degraded)"
    return jsonify(response)


@app.get("/campaigns")
def campaigns_page():
    status_filter = (request.args.get("status") or "all").strip().lower()
    search_query = (request.args.get("q") or "").strip().lower()
    allowed_statuses = {"all", "draft", "running", "paused", "done", "backoff", "error", "stopped"}
    if status_filter not in allowed_statuses:
        status_filter = "all"

    campaigns_with_metrics: list[dict] = []
    for row in CAMPAIGNS_STATE:
        campaign = dict(row)
        campaign["monitoring"] = campaign_monitoring_snapshot(campaign)
        campaigns_with_metrics.append(campaign)

    filtered_campaigns = []
    for campaign in campaigns_with_metrics:
        state = str(campaign.get("status") or "draft").strip().lower()
        name = str(campaign.get("name") or "").lower()
        cid = str(campaign.get("id") or "").lower()
        if status_filter != "all" and state != status_filter:
            continue
        if search_query and search_query not in name and search_query not in cid:
            continue
        filtered_campaigns.append(campaign)

    monitoring_summary = {
        "total": len(campaigns_with_metrics),
        "drafts": sum(1 for campaign in campaigns_with_metrics if str(campaign.get("status") or "").lower() == "draft"),
        "active": sum(1 for campaign in campaigns_with_metrics if str(campaign.get("status") or "").lower() in {"running", "backoff", "paused"}),
        "total_sent": sum(int(campaign["monitoring"]["sent"]) for campaign in campaigns_with_metrics),
    }

    body = render_template_string(
        """
        <div class="top" style="align-items:flex-end">
          <div>
            <h1 class="title">Campaigns</h1>
            <div class="subtitle">Manage campaign lifecycle with draft filtering, inline rename, and quick monitoring insights that match the rest of Shiva surfaces.</div>
          </div>
        </div>

        <div class="grid three" style="margin-bottom:14px">
          <div class="card"><div class="mini">All Campaigns</div><div class="value" style="font-size:28px; font-weight:900">{{ summary.total }}</div></div>
          <div class="card"><div class="mini">Draft</div><div class="value tone-warn" style="font-size:28px; font-weight:900">{{ summary.drafts }}</div></div>
          <div class="card"><div class="mini">Total Sent</div><div class="value tone-good" style="font-size:28px; font-weight:900">{{ "{:,}".format(summary.total_sent) }}</div></div>
        </div>

        <div class="card" style="margin-bottom:14px">
          <div style="display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap;">
          <form id="campaignFiltersForm" method="get" action="{{ url_for('campaigns_page') }}" style="display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap; flex:1; min-width:320px;">
            <div style="min-width:220px; flex:1">
              <label style="margin:0 0 6px">Search</label>
              <input type="search" name="q" value="{{ filters.q }}" placeholder="Campaign name or id" data-filter-q>
            </div>
            <div>
              <label style="margin:0 0 6px">Status</label>
              <select name="status" style="min-width:170px" data-filter-status>
                {% for item in status_options %}
                <option value="{{ item.value }}" {% if item.value == filters.status %}selected{% endif %}>{{ item.label }}</option>
                {% endfor %}
              </select>
            </div>
            <a class="btn secondary" href="{{ url_for('campaigns_page') }}">Reset</a>
          </form>
          <form method="post" action="{{ url_for('campaigns_delete_filtered') }}" onsubmit="return confirm('Delete all campaigns matching current filters?');" style="display:flex; gap:8px; align-items:flex-end;">
            <input type="hidden" name="status" value="{{ filters.status }}">
            <input type="hidden" name="q" value="{{ filters.q }}">
            <button class="btn danger" type="submit">Delete Filtered</button>
          </form>
          <form method="post" action="{{ url_for('campaigns_create') }}">
            <button type="submit">➕ New Campaign</button>
          </form>
          </div>
        </div>

        <div class="grid">
          {% if campaigns %}
            {% for campaign in campaigns %}
            <div class="card">
              <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; align-items:flex-start">
                <div style="flex:1; min-width:280px">
                  <div style="display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; align-items:center">
                    <h3 style="margin:0; flex:1; min-width:220px">
                      <span data-campaign-name="{{ campaign.id }}">{{ campaign.name }}</span>
                      <form method="post" action="{{ url_for('campaigns_rename', campaign_id=campaign.id) }}" data-rename-form="{{ campaign.id }}" style="display:none; gap:8px; align-items:center; flex-wrap:wrap;">
                        <input name="name" value="{{ campaign.name }}" required style="min-width:220px">
                        <button class="btn secondary" type="submit">Save</button>
                        <button class="btn secondary" type="button" data-rename-cancel="{{ campaign.id }}">Cancel</button>
                      </form>
                    </h3>
                    <div class="campaignState {{ campaign.status|lower }}">{{ campaign.status }}</div>
                  </div>
                  <div class="mini">ID: <code>{{ campaign.id }}</code> · Created: {{ campaign.created_at }} · Updated: {{ campaign.updated_at }}</div>
                </div>
              </div>

              <div class="grid three" style="margin-top:12px">
                <div class="alert accent" style="margin:0">
                  <div style="font-weight:800">Monitoring</div>
                  <div class="mini">Jobs: {{ campaign.monitoring.jobs_count }} · Start Sending clicks: {{ campaign.monitoring.start_clicks }}</div>
                </div>
                <div class="alert good" style="margin:0">
                  <div style="font-weight:800">Sent / Not Sent</div>
                  <div class="mini">{{ "{:,}".format(campaign.monitoring.sent) }} sent · {{ "{:,}".format(campaign.monitoring.not_sent) }} pending</div>
                </div>
                <div class="alert {{ 'warn' if campaign.monitoring.failed else 'accent' }}" style="margin:0">
                  <div style="font-weight:800">Delivery health</div>
                  <div class="mini">Delivered {{ "{:,}".format(campaign.monitoring.delivered) }} · Failed {{ "{:,}".format(campaign.monitoring.failed) }} · Deferred {{ "{:,}".format(campaign.monitoring.deferred) }}</div>
                </div>
              </div>

              <div class="actions" style="margin-top:12px">
                <a class="btn" href="{{ url_for('send_page', campaign_id=campaign.id) }}">Open Send</a>
                <button class="btn secondary" type="button" data-rename-trigger="{{ campaign.id }}">Rename</button>
                <form method="post" action="{{ url_for('campaigns_delete', campaign_id=campaign.id) }}" onsubmit="return confirm('Delete this campaign?');">
                  <button class="btn danger" type="submit">Delete</button>
                </form>
              </div>
            </div>
            {% endfor %}
          {% else %}
            <div class="card">
              <h3 style="margin:0">No campaigns match these filters</h3>
              <div class="mini">Try clearing filters or create a new campaign.</div>
            </div>
          {% endif %}
        </div>
        <script>
          document.querySelectorAll("[data-rename-trigger]").forEach((button) => {
            button.addEventListener("click", () => {
              const campaignId = button.getAttribute("data-rename-trigger");
              const renameForm = document.querySelector(`[data-rename-form="${campaignId}"]`);
              const nameLabel = document.querySelector(`[data-campaign-name="${campaignId}"]`);
              if (!renameForm || !nameLabel) return;
              renameForm.style.display = "flex";
              nameLabel.style.display = "none";
              const input = renameForm.querySelector("input[name='name']");
              if (input) {
                input.focus();
                input.select();
              }
            });
          });

          document.querySelectorAll("[data-rename-cancel]").forEach((button) => {
            button.addEventListener("click", () => {
              const campaignId = button.getAttribute("data-rename-cancel");
              const renameForm = document.querySelector(`[data-rename-form="${campaignId}"]`);
              const nameLabel = document.querySelector(`[data-campaign-name="${campaignId}"]`);
              if (!renameForm || !nameLabel) return;
              renameForm.style.display = "none";
              nameLabel.style.display = "";
            });
          });

          const filtersForm = document.getElementById("campaignFiltersForm");
          if (filtersForm) {
            const searchInput = filtersForm.querySelector("[data-filter-q]");
            const statusSelect = filtersForm.querySelector("[data-filter-status]");
            let filterTimer = null;

            if (searchInput) {
              searchInput.addEventListener("input", () => {
                if (filterTimer) window.clearTimeout(filterTimer);
                filterTimer = window.setTimeout(() => filtersForm.submit(), 260);
              });
            }

            if (statusSelect) {
              statusSelect.addEventListener("change", () => {
                filtersForm.submit();
              });
            }
          }
        </script>
        """,
        campaigns=filtered_campaigns,
        summary=monitoring_summary,
        filters={"status": status_filter, "q": request.args.get("q", "")},
        status_options=[
            {"value": "all", "label": "All statuses"},
            {"value": "draft", "label": "Draft"},
            {"value": "running", "label": "Running"},
            {"value": "paused", "label": "Paused"},
            {"value": "backoff", "label": "Backoff"},
            {"value": "done", "label": "Done"},
            {"value": "error", "label": "Error"},
            {"value": "stopped", "label": "Stopped"},
        ],
    )
    return render("campaigns", "Shiva Campaigns", body)


@app.post("/campaigns/create")
def campaigns_create():
    raw_name = (request.form.get("name") or "").strip()
    campaign_id = f"cmp-{uuid.uuid4().hex[:10]}"
    campaign_name = raw_name or f"Campaign {campaign_id}"
    now_iso = iso(datetime.now(timezone.utc))
    CAMPAIGNS_STATE.insert(
        0,
        {
            "id": campaign_id,
            "name": campaign_name,
            "created_at": now_iso,
            "updated_at": now_iso,
            "jobs": 0,
            "status": "draft",
            "total_recipients": 0,
            "start_clicks": 0,
        },
    )
    save_campaigns(CAMPAIGNS_STATE)
    return redirect(url_for("send_page", campaign_id=campaign_id))


@app.post("/campaigns/<campaign_id>/rename")
def campaigns_rename(campaign_id: str):
    campaign_id = (campaign_id or "").strip()
    new_name = (request.form.get("name") or "").strip()
    if not campaign_id or not new_name:
        return redirect(url_for("campaigns_page"))
    campaign = get_campaign(campaign_id)
    if campaign:
        campaign["name"] = new_name
        campaign["updated_at"] = iso(datetime.now(timezone.utc))
        save_campaigns(CAMPAIGNS_STATE)
    return redirect(url_for("campaigns_page"))


@app.post("/campaigns/<campaign_id>/delete")
def campaigns_delete(campaign_id: str):
    campaign_id = (campaign_id or "").strip()
    if not campaign_id:
        return redirect(url_for("campaigns_page"))
    original_count = len(CAMPAIGNS_STATE)
    CAMPAIGNS_STATE[:] = [row for row in CAMPAIGNS_STATE if row.get("id") != campaign_id]
    if len(CAMPAIGNS_STATE) != original_count:
        save_campaigns(CAMPAIGNS_STATE)
    if campaign_id in CAMPAIGN_FORMS_STATE:
        del CAMPAIGN_FORMS_STATE[campaign_id]
        save_campaign_forms(CAMPAIGN_FORMS_STATE)
    return redirect(url_for("campaigns_page"))


@app.post("/campaigns/delete-filtered")
def campaigns_delete_filtered():
    status_filter = (request.form.get("status") or "all").strip().lower()
    search_query = (request.form.get("q") or "").strip().lower()
    allowed_statuses = {"all", "draft", "running", "paused", "done", "backoff", "error", "stopped"}
    if status_filter not in allowed_statuses:
        status_filter = "all"

    to_delete_ids: set[str] = set()
    for campaign in CAMPAIGNS_STATE:
        state = str(campaign.get("status") or "draft").strip().lower()
        name = str(campaign.get("name") or "").lower()
        cid = str(campaign.get("id") or "").lower()
        if status_filter != "all" and state != status_filter:
            continue
        if search_query and search_query not in name and search_query not in cid:
            continue
        campaign_id = str(campaign.get("id") or "").strip()
        if campaign_id:
            to_delete_ids.add(campaign_id)

    if to_delete_ids:
        CAMPAIGNS_STATE[:] = [row for row in CAMPAIGNS_STATE if str(row.get("id") or "").strip() not in to_delete_ids]
        save_campaigns(CAMPAIGNS_STATE)

        removed_form = False
        for campaign_id in list(CAMPAIGN_FORMS_STATE.keys()):
            if campaign_id in to_delete_ids:
                del CAMPAIGN_FORMS_STATE[campaign_id]
                removed_form = True
        if removed_form:
            save_campaign_forms(CAMPAIGN_FORMS_STATE)

    return redirect(url_for("campaigns_page"))


@app.get("/campaign/<campaign_id>")
def campaign_open(campaign_id: str):
    campaign_id = (campaign_id or "").strip() or DEFAULT_CAMPAIGN_ID
    get_or_create_campaign(campaign_id)
    return redirect(url_for("send_page", campaign_id=campaign_id))


@app.get("/jobs")
def jobs_page():
    created_job = (request.args.get("created_job") or "").strip()
    preview = _build_jobs_send_preview(created_job)
    html = render_template_string(JOBS_PAGE_HTML, send_preview=preview)
    return render_tool_page(html, "jobs")


@app.get("/job/<job_id>")
def job_page(job_id: str):
    return redirect(url_for("jobs_page"))


@app.get("/config")
def config_page():
    body = render_template_string(
        """
        <div class="top">
          <div>
            <h1 class="title">Config surface</h1>
            <div class="subtitle">Static config table intended for frontend extraction and future replacement with your real settings API.</div>
          </div>
          <div class="actions">
            <button>💾 Save all</button>
            <button class="secondary">🔄 Reload</button>
          </div>
        </div>
        <div class="grid">
          {% for group in groups %}
          <div class="card">
            <h2>{{ group.group }}</h2>
            <table>
              <thead><tr><th>Key</th><th>Value</th><th>Type</th><th>Source</th><th>Restart</th><th>Description</th></tr></thead>
              <tbody>
                {% for item in group["items"] %}
                <tr>
                  <td><code>{{ item.key }}</code></td>
                  <td>{{ item.value }}</td>
                  <td>{{ item.type }}</td>
                  <td><span class="tag {{ 'good' if item.source == 'ui' else ('warn' if item.source == 'env' else 'accent') }}">{{ item.source }}</span></td>
                  <td>{{ 'yes' if item.restart else 'no' }}</td>
                  <td>{{ item.desc }}</td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          {% endfor %}
        </div>
        """,
        groups=CONFIG_GROUPS,
    )
    return render("config", "Shiva Config", body)


@app.get("/accounting")
def accounting_page():
    html = script6.render_dashboard_page(
        namespace="nibiru_accounting",
        external_config=DASHBOARD_DATA.get("message_form", {}),
        route_urls={
            "index": url_for("accounting_page"),
            "select_folder": url_for("accounting_select_folder"),
            "refresh": url_for("accounting_refresh"),
            "use_ssh": url_for("accounting_use_ssh"),
            "use_local": url_for("accounting_use_local"),
            "download_base": "/accounting/download",
            "dashboard": url_for("dashboard"),
            "campaigns": url_for("campaigns_page"),
            "send": url_for("send_page"),
            "jobs": url_for("jobs_page"),
            "job": url_for("jobs_page"),
            "config": url_for("config_page"),
            "accounting": url_for("accounting_page"),
            "spamhaus": url_for("spamhaus_page"),
            "extractor": url_for("extractor_page"),
            "infra": url_for("infra_page"),
            "tracker": url_for("tracker_page"),
        },
    )
    return render_tool_page(html, "accounting")


@app.get("/accounting/select-folder")
def accounting_select_folder():
    script6.select_folder_action("nibiru_accounting")
    return redirect(url_for("accounting_page"))


@app.get("/accounting/refresh")
def accounting_refresh():
    try:
        script6.refresh_action("nibiru_accounting", DASHBOARD_DATA.get("message_form", {}))
    except Exception:
        pass
    return redirect(url_for("accounting_page"))


@app.get("/accounting/use-ssh")
def accounting_use_ssh():
    script6.set_source_mode("ssh", "nibiru_accounting")
    try:
        script6.refresh_action("nibiru_accounting", DASHBOARD_DATA.get("message_form", {}))
    except Exception:
        script6.set_analysis(None, "nibiru_accounting")
    return redirect(url_for("accounting_page"))


@app.get("/accounting/use-local")
def accounting_use_local():
    script6.set_source_mode("local", "nibiru_accounting")
    script6.refresh_action("nibiru_accounting", DASHBOARD_DATA.get("message_form", {}))
    return redirect(url_for("accounting_page"))


@app.get("/accounting/download/<kind>")
def accounting_download(kind: str):
    response = script6.download_action(kind, "nibiru_accounting")
    if response is None or response is False:
        return redirect(url_for("accounting_page"))
    return response


@app.get("/spamhaus")
def spamhaus_page():
    return render_tool_page(script1.render_index(api_base="/tools/spamhaus"), "spamhaus")


@app.get("/tools/spamhaus/")
def spamhaus_raw():
    return redirect(url_for("spamhaus_page"))


@app.post("/tools/spamhaus/api/start")
def spamhaus_api_start():
    return script1.api_start()


@app.get("/tools/spamhaus/api/job/<job_id>")
def spamhaus_api_job(job_id: str):
    return script1.api_job(job_id)


@app.post("/tools/spamhaus/api/poll-infra")
def spamhaus_api_poll_infra():
    return script1.api_poll_infra()


@app.get("/tools/spamhaus/api/cache-results")
def spamhaus_api_cache_results():
    return script1.api_cache_results()


@app.get("/tools/spamhaus/api/export/<job_id>")
def spamhaus_api_export(job_id: str):
    return script1.api_export(job_id)


@app.get("/extractor")
def extractor_page():
    return render_tool_page(script2.render_index(api_base="/tools/extractor"), "extractor")


@app.get("/tools/extractor/")
def extractor_raw():
    return redirect(url_for("extractor_page"))


@app.get("/tools/extractor/api/settings")
def extractor_api_get_settings():
    return script2.api_get_settings()


@app.post("/tools/extractor/api/settings")
def extractor_api_save_settings():
    return script2.api_save_settings()


@app.delete("/tools/extractor/api/settings")
def extractor_api_delete_settings():
    return script2.api_delete_settings()


@app.get("/tools/extractor/api/extraction-runs")
def extractor_api_list_extraction_runs():
    return script2.api_list_extraction_runs()


@app.post("/tools/extractor/api/extraction-runs")
def extractor_api_save_extraction_run():
    return script2.api_save_extraction_run()


@app.get("/tools/extractor/api/extraction-runs/<int:run_id>")
def extractor_api_get_extraction_run(run_id: int):
    return script2.api_get_extraction_run(run_id)


@app.delete("/tools/extractor/api/extraction-runs/<int:run_id>")
def extractor_api_delete_extraction_run(run_id: int):
    return script2.api_delete_extraction_run(run_id)


@app.get("/infra")
def infra_page():
    return render_tool_page(script3.render_index(api_base="/tools/infra"), "infra")


@app.get("/tools/infra/")
def infra_raw():
    return redirect(url_for("infra_page"))


@app.get("/tools/infra/api/data")
def infra_api_get_data():
    return script3.api_get_data()


@app.post("/tools/infra/api/data")
def infra_api_post_data():
    return script3.api_post_data()


@app.delete("/tools/infra/api/data")
def infra_api_delete_data():
    return script3.api_delete_data()


@app.post("/tools/infra/api/dkim/check-ssh")
def infra_api_check_ssh():
    return script3.api_check_ssh()


@app.post("/tools/infra/api/dkim/generate")
def infra_api_generate_dkim():
    return script3.api_generate_dkim()


@app.post("/tools/infra/api/pmta/poll-config")
def infra_api_poll_pmta_config():
    return script3.api_poll_pmta_config()


@app.post("/tools/infra/api/namecheap/test")
def infra_api_namecheap_test():
    return script3.api_namecheap_test()


@app.post("/tools/infra/api/namecheap/poll-domain")
def infra_api_namecheap_poll_domain():
    return script3.api_namecheap_poll_domain()


@app.post("/tools/infra/api/namecheap/verify-domain")
def infra_api_namecheap_verify_domain():
    return script3.api_namecheap_verify_domain()


@app.get("/tools/infra/api/spamhaus-queue")
def infra_api_spamhaus_queue():
    return script3.api_get_spamhaus_queue()


@app.post("/tools/infra/api/spamhaus-queue/import")
def infra_api_import_spamhaus_queue():
    return script3.api_import_spamhaus_queue()


@app.get("/tracker")
def tracker_page():
    return render_tool_page(script5.render_dashboard_page(
        "packager",
        route_urls=script5.build_route_urls("/tools/tracker"),
        emails="",
        valid_count=0,
        unique_count=0,
        db_total=len(script5.get_all_email_mappings()),
        error="",
    ), "tracker")


@app.get("/tools/tracker/")
def tracker_raw():
    return redirect(url_for("tracker_page"))


@app.post("/tools/tracker/generate")
def tracker_generate():
    raw_emails = request.form.get("emails", "")
    emails = script5.parse_emails(raw_emails)
    if not emails:
        return render_tool_page(script5.render_dashboard_page(
            "packager",
            route_urls=script5.build_route_urls("/tools/tracker"),
            emails=raw_emails,
            valid_count=0,
            unique_count=0,
            db_total=len(script5.get_all_email_mappings()),
            error="No valid emails were found.",
        ), "tracker")
    script5.upsert_email_mappings(emails)
    zip_buffer = script5.build_zip(emails)
    return script5.send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="email_image_bundle.zip",
    )


@app.route("/tools/tracker/stay", methods=["GET", "POST"])
def tracker_stay():
    if request.method == "GET":
        return render_tool_page(script5.render_dashboard_page(
            "stay",
            route_urls=script5.build_route_urls("/tools/tracker"),
            stay_urls="",
            stay_email_count=len(script5.get_all_email_mappings()),
            stay_url_count=0,
            stay_found_count=0,
            stay_matched_count=0,
            stay_matches=[],
            stay_unmatched_ids=[],
            stay_errors=[],
            stay_mappings=script5.get_all_email_mappings()[: script5.PAGE_SIZE],
            stay_domain_stats=[],
            stay_run_at="-",
        ), "tracker")
    raw_urls = request.form.get("urls", "")
    analysis = script5.analyze_stay_data(raw_urls)
    return render_tool_page(script5.render_dashboard_page(
        "stay",
        route_urls=script5.build_route_urls("/tools/tracker"),
        stay_urls=raw_urls,
        stay_email_count=analysis["stored_email_count"],
        stay_url_count=analysis["url_count"],
        stay_found_count=analysis["found_count"],
        stay_matched_count=analysis["matched_count"],
        stay_matches=analysis["matches_page"]["items"],
        stay_unmatched_ids=analysis["unmatched_ids"],
        stay_errors=analysis["errors"],
        stay_mappings=analysis["stored_mappings_page"]["items"],
        stay_domain_stats=analysis["domain_stats_page"]["items"],
        stay_run_at=analysis["run_at"],
    ), "tracker")


@app.post("/tools/tracker/stay/analyze")
def tracker_stay_analyze():
    return script5.stay_analyze_api()


@app.get("/api/campaign/<campaign_id>/form")
def api_campaign_form_get(campaign_id: str):
    campaign_id = (campaign_id or "").strip() or DEFAULT_CAMPAIGN_ID
    data = CAMPAIGN_FORMS_STATE.get(campaign_id, {})
    if not isinstance(data, dict):
        data = {}
    return jsonify({"ok": True, "data": data})


@app.post("/api/campaign/<campaign_id>/form")
def api_campaign_form_save(campaign_id: str):
    campaign_id = (campaign_id or "").strip() or DEFAULT_CAMPAIGN_ID
    payload = request.get_json(silent=True) or {}
    data = payload.get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        data = {}
    CAMPAIGN_FORMS_STATE[campaign_id] = data
    save_campaign_forms(CAMPAIGN_FORMS_STATE)
    campaign = get_or_create_campaign(campaign_id)
    campaign["form_snapshot"] = data
    campaign["form_snapshot_updated_at"] = iso(datetime.now(timezone.utc))
    campaign["updated_at"] = iso(datetime.now(timezone.utc))
    save_campaigns(CAMPAIGNS_STATE)
    return jsonify({"ok": True})


@app.post("/api/campaign/<campaign_id>/clear")
def api_campaign_form_clear(campaign_id: str):
    campaign_id = (campaign_id or "").strip() or DEFAULT_CAMPAIGN_ID
    if campaign_id in CAMPAIGN_FORMS_STATE:
        del CAMPAIGN_FORMS_STATE[campaign_id]
        save_campaign_forms(CAMPAIGN_FORMS_STATE)
    campaign = get_or_create_campaign(campaign_id)
    campaign.pop("form_snapshot", None)
    campaign.pop("form_snapshot_updated_at", None)
    campaign["updated_at"] = iso(datetime.now(timezone.utc))
    save_campaigns(CAMPAIGNS_STATE)
    return jsonify({"ok": True})


@app.get("/api/campaign/<campaign_id>/latest_job")
def api_campaign_latest_job(campaign_id: str):
    campaign_id = (campaign_id or "").strip() or DEFAULT_CAMPAIGN_ID
    jobs = [row for row in JOBS if row.get("campaign_id") == campaign_id]
    if not jobs:
        return jsonify({"ok": True, "job": None})
    latest = sorted(jobs, key=lambda row: row.get("updated_at", ""), reverse=True)[0]
    return jsonify({"ok": True, "job": latest})


@app.get("/api/campaign/<campaign_id>/domains_stats")
def api_campaign_domains_stats(campaign_id: str):
    _ = (campaign_id or "").strip() or DEFAULT_CAMPAIGN_ID
    sender_domains = DASHBOARD_DATA.get("preflight", {}).get("sender_domains", [])
    rows = []
    for row in sender_domains:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").lower()
        rows.append(
            {
                "domain": row.get("domain") or "unknown.local",
                "mx": [f"mx.{row.get('domain') or 'unknown.local'}"],
                "ips": row.get("ips") or [],
                "listed": status == "listed",
                "any_listed": status == "listed",
                "spf": {"status": "pass"},
                "dkim": {"status": "pass"},
                "dmarc": {"status": "pass"},
            }
        )
    return jsonify({"ok": True, "domains": rows})


@app.get("/api/dashboard")
def api_dashboard():
    return jsonify(build_live_snapshot())


@app.get("/api/accounting/ssh/status")
def api_accounting_ssh_status():
    requested_job_id = (request.args.get("job_id") or "").strip()
    target_job = get_job(requested_job_id) if requested_job_id else (JOBS[0] if JOBS else {})
    snapshot = load_pmta_monitor_snapshot(target_job if isinstance(target_job, dict) else {})
    bridge = snapshot.get("bridge_state") if isinstance(snapshot, dict) else {}
    if not isinstance(bridge, dict):
        bridge = {}
    if not bridge.get("last_attempt_ts"):
        bridge["last_attempt_ts"] = iso(datetime.now(timezone.utc))
    return jsonify({"ok": bool(bridge.get("connected")), "job_id": str((target_job or {}).get("id") or ""), "bridge": bridge})


@app.get("/api/jobs")
def api_jobs():
    for row in JOBS:
        if isinstance(row, dict):
            try:
                _advance_job_runtime(row)
            except Exception as exc:
                _append_job_event(row, "runtime_update_failed", f"Runtime update failed: {exc}", "ERROR", min_interval_s=5)
                _set_job_diagnostic(row, "runtime_updates", "bad", f"Runtime update failed: {exc}")
    sample_job = JOBS[0] if JOBS else {}
    runtime_snapshot = resolve_pmta_runtime_for_job(sample_job if isinstance(sample_job, dict) else {})
    runtime_config = runtime_snapshot.get("runtime_config") if isinstance(runtime_snapshot.get("runtime_config"), dict) else {}
    sample_diag = sample_job.get("diagnostics") if isinstance(sample_job, dict) else {}
    if not isinstance(sample_diag, dict):
        sample_diag = {}
    bridge_diag = sample_diag.get("bridge") if isinstance(sample_diag.get("bridge"), dict) else {}
    bridge_expected = bool(runtime_config.get("ssh_enabled"))
    bridge_reason = str(bridge_diag.get("reason") or "Bridge status not available yet.")
    bridge_status = "good" if bridge_diag.get("status") == "good" else ("warn" if bridge_diag.get("expected") else "bad")
    diagnostics = [
        {
            "key": "pmta_live",
            "status": str((sample_diag.get("pmta_live") or {}).get("status") or "warn"),
            "reason": str((sample_diag.get("pmta_live") or {}).get("reason") or "PMTA live diagnostics pending."),
        },
        {
            "key": "ssh_settings",
            "status": "good" if runtime_config.get("ssh_enabled") else "bad",
            "reason": "SSH settings configured." if runtime_config.get("ssh_enabled") else "SSH settings missing or disabled.",
        },
        {
            "key": "runtime_updates",
            "status": "good" if RUNTIME_UPDATES_ENABLED else "bad",
            "reason": "Job runtime updates are running." if RUNTIME_UPDATES_ENABLED else "Job runtime updates are disabled (NIBIRU_RUNTIME_UPDATES=0).",
        },
        {
            "key": "accounting",
            "status": str((sample_diag.get("accounting") or {}).get("status") or "warn"),
            "reason": str((sample_diag.get("accounting") or {}).get("reason") or "Accounting diagnostics pending."),
        },
        {
            "key": "bridge",
            "status": bridge_status,
            "reason": f"{bridge_reason} ({'expected' if bridge_expected and bridge_diag.get('expected') else ('abnormal' if bridge_expected else 'expected')})",
        },
    ]
    return jsonify({"jobs": JOBS, "diagnostics": diagnostics, "runtime_updates_enabled": RUNTIME_UPDATES_ENABLED})


@app.get("/api/job/<job_id>")
def api_job(job_id: str):
    try:
        detail = build_job_detail(job_id)
    except Exception as exc:
        job = get_job(job_id)
        if isinstance(job, dict):
            _append_job_event(job, "job_detail_failed", f"Failed to build job detail: {exc}", "ERROR", min_interval_s=5)
            _set_job_diagnostic(job, "job_detail", "bad", f"Failed to build job detail: {exc}")
        return jsonify({"error": f"Failed to build job detail for {job_id}: {exc}"}), 500
    if not detail:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(detail)


@app.post("/api/job/<job_id>/control")
def api_job_control(job_id: str):
    job = get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    action = str(request.json.get("action") if request.is_json else request.form.get("action") or "").strip().lower()
    now = iso(datetime.now(timezone.utc))
    if action == "pause":
        job["status"] = "paused"
        job["phase"] = "paused"
        _append_job_event(job, "job_state_updated", "Job paused by operator.", "WARN")
    elif action == "resume":
        job["status"] = "running"
        job["phase"] = "sending"
        _append_job_event(job, "job_state_updated", "Job resumed by operator.")
    elif action in {"stop", "cancel"}:
        job["status"] = "stopped"
        job["phase"] = "stopped"
        _append_job_event(job, "job_state_updated", "Job stopped by operator.", "WARN")
    else:
        return jsonify({"ok": False, "error": "Unsupported action"}), 400
    job["updated_at"] = now
    return jsonify({"ok": True, "job_id": job_id, "status": job.get("status"), "phase": job.get("phase")})


@app.post("/api/job/<job_id>/delete")
def api_job_delete(job_id: str):
    for idx, row in enumerate(JOBS):
        if str(row.get("id") or "").strip() == (job_id or "").strip():
            del JOBS[idx]
            return jsonify({"ok": True, "job_id": job_id})
    return jsonify({"ok": False, "error": "Job not found"}), 404


@app.post("/start")
def start_send_job():
    campaign_id = (request.form.get("campaign_id") or "").strip() or DEFAULT_CAMPAIGN_ID
    campaign = get_or_create_campaign(campaign_id)

    permission_ok = str(request.form.get("permission_ok") or "").strip().lower()
    if permission_ok not in {"on", "1", "true", "yes"}:
        return ("Permission confirmation is required before starting.", 400)

    now = datetime.now(timezone.utc)
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    maillist_raw = str(request.form.get("maillist") or "")
    recipients_total = len(
        [
            row
            for row in re.split(r"[\n,;]+", maillist_raw)
            if row and row.strip()
        ]
    )
    send_snapshot = {
        "from_email": str(request.form.get("from_email") or "").strip(),
        "from_name": str(request.form.get("from_name") or "").strip(),
        "subject": str(request.form.get("subject") or "").strip(),
        "smtp_host": str(request.form.get("smtp_host") or "").strip(),
        "smtp_port": str(request.form.get("smtp_port") or "").strip(),
        "chunk_size": str(request.form.get("chunk_size") or "").strip(),
    }
    runtime_config_snapshot = _extract_runtime_form_subset(request.form.to_dict(flat=True))
    if not runtime_config_snapshot:
        runtime_config_snapshot = _extract_runtime_form_subset(CAMPAIGN_FORMS_STATE.get(campaign_id, {}))
    if not runtime_config_snapshot and isinstance(campaign.get("form_snapshot"), dict):
        runtime_config_snapshot = _extract_runtime_form_subset(campaign.get("form_snapshot"))
    relation_logs = [
        f"[DEBUG] [send_form_received] campaign={campaign_id} recipients={recipients_total} from={send_snapshot.get('from_email') or '-'} smtp={send_snapshot.get('smtp_host') or '-'}",
        f"[DEBUG] [send_runtime_snapshot] runtime_keys={','.join(sorted(runtime_config_snapshot.keys())) if runtime_config_snapshot else 'none'}",
    ]
    new_job = {
        "id": job_id,
        "campaign_id": campaign_id,
        "status": "queued",
        "phase": "queued",
        "bridge_mode": "counts",
        "provider": "custom",
        "progress": 0,
        "total": recipients_total,
        "sent": 0,
        "delivered": 0,
        "failed": 0,
        "deferred": 0,
        "complained": 0,
        "current_chunk": 0,
        "top_domains": _extract_domains_from_from_email(str(send_snapshot.get("from_email") or "")),
        "queued": recipients_total,
        "send_snapshot": send_snapshot,
        "runtime_config": runtime_config_snapshot,
        "runtime_logs": [f"[INFO] [job_created] Job {job_id} accepted and queued for send start."],
        "send_job_debug": relation_logs,
        "created_at": iso(now),
        "started_at": iso(now),
        "updated_at": iso(now),
    }
    required_preflight = {
        "from_email": bool(send_snapshot.get("from_email")),
        "smtp_host": bool(send_snapshot.get("smtp_host")),
        "maillist": recipients_total > 0,
    }
    failed_checks = [k for k, ok in required_preflight.items() if not ok]
    if failed_checks:
        _append_job_event(new_job, "preflight_failed", f"Missing required settings: {', '.join(failed_checks)}.", "WARN")
        relation_logs.append(f"[DEBUG] [send_preflight_failed] job={job_id} failed_checks={','.join(failed_checks)}")
    else:
        _append_job_event(new_job, "preflight_passed", "Basic preflight checks passed.")
        relation_logs.append(f"[DEBUG] [send_preflight_passed] job={job_id} required fields validated")
    relation_logs.append(f"[DEBUG] [job_linked] send campaign {campaign_id} is now linked to job {job_id}")
    JOBS.insert(0, new_job)

    campaign["start_clicks"] = int(campaign.get("start_clicks") or 0) + 1
    campaign["status"] = "running"
    campaign["updated_at"] = iso(now)
    save_campaigns(CAMPAIGNS_STATE)

    return redirect(url_for("jobs_page", created_job=job_id))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5099, debug=True)
