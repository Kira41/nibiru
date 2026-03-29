from __future__ import annotations

import hashlib
import random
import re
import smtplib
import ssl
import threading
from datetime import datetime, timezone
from email.message import EmailMessage

from flask import render_template_string

SEND_PAGE_BODY = r"""
<div class="wrap">
  <div class="top">
    <div>
      <h1>💀 SHIVA - {{ campaign_name_suffix }}</h1>
      <div class="sub">
        A simple, clean UI to send email via SMTP with a progress bar and logs.
        <br>
        <b style="color: var(--warn)">⚠️ Legal use only:</b> send to opt-in/permission-based recipients.
      </div>
    </div>
    <div class="topActions">
      <button class="shiva-toggle-btn" type="button" id="btnManualMode" aria-pressed="false">
        <span class="switch-track"><span class="switch-thumb"></span></span>
        <span class="switch-text">🧰 MANUAL SEND: OFF</span>
      </button>
    </div>
  </div>

  <style>
    .shiva-toggle-btn{
      border-radius:999px;
      padding:6px 12px 6px 8px;
      min-height:40px;
      display:inline-flex;
      align-items:center;
      gap:10px;
      background:rgba(255,255,255,.06);
      border:1px solid rgba(255,255,255,.18);
      color:var(--text);
      box-shadow:none;
      font-weight:800;
      cursor:pointer;
    }
    .shiva-toggle-btn .switch-track{
      width:52px;
      height:30px;
      border-radius:999px;
      border:1px solid rgba(255,255,255,.18);
      background:rgba(255,255,255,.12);
      position:relative;
      transition:.2s ease;
    }
    .shiva-toggle-btn .switch-thumb{
      width:24px;
      height:24px;
      border-radius:999px;
      position:absolute;
      top:2px;
      left:2px;
      background:#f2f6ff;
      box-shadow:0 2px 8px rgba(0,0,0,.35);
      transition:.2s ease;
    }
    .shiva-toggle-btn.active{
      border-color:rgba(255,209,106,.55);
      background:rgba(255,209,106,.15);
      color:#ffe5a5;
    }
    .shiva-toggle-btn.active .switch-track{
      background:rgba(244,183,64,.95);
      border-color:rgba(255,209,106,.8);
    }
    .shiva-toggle-btn.active .switch-thumb{
      transform:translateX(22px);
      background:#fff7e6;
    }
  </style>

  <form class="grid send-layout" method="post" action="/start" enctype="multipart/form-data" id="mainForm">
    <input type="hidden" name="campaign_id" value="{{ campaign_id }}">
    <input type="hidden" name="infra_payload" id="infraPayloadInput" value="">
    <input type="hidden" name="manual_send_mode" value="0">
    <input type="hidden" name="banished_ips" id="banishedIpsInput" value="">
    <input type="hidden" name="banished_domains" id="banishedDomainsInput" value="">
    <div class="stack">
      <div class="card" id="infraCard" style="display:none">
        <h2>Shiva Infrastructure Bridge</h2>
        <div class="mini" id="infraMeta">Waiting for infrastructure payload from script3.</div>
        <div id="infraDetails" style="margin-top:10px"></div>
      </div>

      <div class="card manual-only" id="smtpCard">
      <h2>SMTP Settings</h2>

      <div class="row">
        <div>
          <label>SMTP Host</label>
          <input name="smtp_host" placeholder="Example: mail.example.com or an IP" required="">
        </div>
        <div>
          <label>Port</label>
          <input name="smtp_port" type="number" placeholder="Example: 25 / 2525 / 587 / 465" required="" value="2525">
        </div>
      </div>

      <div class="row">
        <div>
          <label>Security</label>
          <select name="smtp_security">
            <option value="starttls">STARTTLS (587)</option>
            <option value="ssl">SSL/TLS (465)</option>
            <option value="none" selected="">None (not recommended)</option>
          </select>
        </div>
        <div>
          <label>Timeout (seconds)</label>
          <input name="smtp_timeout" type="number" value="25" min="5" max="120">
        </div>
      </div>

      <div class="row">
        <div>
          <label>SMTP Username (optional)</label>
          <input name="smtp_user" placeholder="Example: user@example.com">
        </div>
        <div>
          <label>SMTP Password (optional)</label>
          <input name="smtp_pass" type="password" placeholder="••••••••">
        </div>
      </div>

      <div class="check" style="margin-top:10px">
        <input type="checkbox" id="remember_pass" name="remember_pass">
        <div>
          Remember SMTP password on this browser (saved in server database (SQLite)). <b style="color: var(--warn)">Not recommended</b> on shared PCs.
        </div>
      </div>

      <div class="hint">
        <b>Note:</b> If you use PowerMTA or a custom SMTP server, set the correct host and port.
        Usually: <code>587 + STARTTLS</code> or <code>465 + SSL/TLS</code>.
        <br>
        ✅ <b>Test SMTP</b> only connects (and authenticates if provided) — <b>it does not send any email</b>.
      </div>

      <div class="actions">
        <button class="btn secondary" type="button" id="btnTest">🔌 Test SMTP</button>
        <div class="mini" id="testMini">Test the connection before sending.</div>
      </div>
      <div class="inline-status" id="smtpTestInline"></div>
      </div>

      <div class="card manual-only" id="sshCard">
      <h2>SSH Connection</h2>

      <div class="row">
        <div>
          <label>SSH Host</label>
          <input name="ssh_host" placeholder="Example: same PMTA server host/IP">
        </div>
        <div>
          <label>SSH Port</label>
          <input name="ssh_port" type="number" placeholder="22" value="22">
        </div>
      </div>

      <div class="row">
        <div>
          <label>SSH Username</label>
          <input name="ssh_user" placeholder="Example: root or pmtaops">
        </div>
        <div>
          <label>SSH Key Path (optional)</label>
          <input name="ssh_key_path" placeholder="/home/app/.ssh/id_rsa">
        </div>
      </div>

      <div class="row">
        <div>
          <label>SSH Password (optional)</label>
          <input name="ssh_pass" type="password" placeholder="Password auth supported directly by Shiva">
        </div>
        <div>
          <label>SSH Timeout (seconds)</label>
          <input name="ssh_timeout" type="number" value="8" min="3" max="120">
        </div>
      </div>

      <div class="check" style="margin-top:10px">
        <input type="checkbox" id="remember_ssh_pass" name="remember_ssh_pass">
        <div>
          Remember SSH password on this browser (saved in server database (SQLite)). <b style="color: var(--warn)">Not recommended</b> on shared PCs.
        </div>
      </div>

      <div class="hint">
        <b>PMTA monitoring/accounting now uses SSH only.</b> Shiva runs commands such as <code>pmta show status</code> and tails the remote accounting CSV via SSH.
      </div>

      <div class="actions">
        <button class="btn secondary" type="button" id="btnSshTest">🖧 Test SSH</button>
        <div class="mini">Checks SSH access and runs <code>pmta show status</code>.</div>
      </div>
      <div class="inline-status" id="sshTestInline"></div>
      </div>

      <div class="card">
        <h2>Preflight &amp; Send Controls</h2>

        <div class="check">
        <input type="checkbox" name="permission_ok" required="">
        <div>
          I confirm this recipient list is <b>permission-based (opt-in)</b> and this usage is lawful.
          (Sending is blocked without this confirmation.)
        </div>
      </div>

      <div class="hint" id="preflightBox" style="margin-top:12px">
        <b>Preflight stats (optional):</b> get the <b>Spam score</b> + check if the <b>sender domain / SMTP IP</b> is blacklisted.
        <div class="row" style="margin-top:10px">
          <div>
            <div class="mini"><b>Spam score:</b> <span id="pfSpam">—</span></div>
            <div class="mini" id="pfSpamMore" style="display:none"></div>
          </div>
          <div>
            <div class="mini"><b>Blacklist:</b> <span id="pfBl">—</span></div>
            <div class="mini" id="pfBlMore" style="display:none"></div>
          </div>
        </div>
        <div class="mini" style="margin-top:10px"><b>Sender domains status:</b> Domain → IP(s) → Listed/Not listed</div>
        <div style="overflow:auto; margin-top:8px">
          <table style="width:100%; border-collapse:collapse; font-size:12px">
            <thead>
              <tr>
                <th style="text-align:left; padding:6px; border-bottom:1px solid rgba(255,255,255,.10)">Domain</th>
                <th style="text-align:left; padding:6px; border-bottom:1px solid rgba(255,255,255,.10)">IP(s)</th>
                <th style="text-align:left; padding:6px; border-bottom:1px solid rgba(255,255,255,.10)">Status</th>
                <th style="text-align:left; padding:6px; border-bottom:1px solid rgba(255,255,255,.10)">Spam score (per domain)</th>
                <th style="text-align:left; padding:6px; border-bottom:1px solid rgba(255,255,255,.10)">Auth</th>
                <th style="text-align:left; padding:6px; border-bottom:1px solid rgba(255,255,255,.10)">Banish</th>
              </tr>
            </thead>
            <tbody id="pfDomains">
              <tr><td colspan="6" class="muted" style="padding:6px">Run Preflight to see sender domains.</td></tr>
            </tbody>
          </table>
        </div>

        <div class="actions" style="margin-top:10px">
          <button class="btn secondary manual-only-inline" type="button" id="btnPreflight" style="display:none">📊 Preflight Check</button>
          <div class="mini">Uses SpamAssassin backend (if available) + DNSBL checks (server-side).</div>
        </div>

        <div class="hint" style="margin-top:10px">
          <b>Sending controls:</b> these settings affect the real sending job.
          <div class="mini">Rule: <b>one chunk uses one sender email</b> (rotated by chunk index). Each chunk can use many workers.</div>

          <div class="row" style="margin-top:10px">
            <div>
              <label>Delay between messages (seconds)</label>
              <input name="delay_s" type="number" value="0.0" step="0.1" min="0" max="10">
            </div>
            <div>
              <label>Max Recipients (safety)</label>
              <input name="max_rcpt" type="number" value="300" min="1" max="200000">
            </div>
          </div>

          <div class="row" style="margin-top:10px">
            <div>
              <label>Thread chunk size</label>
              <input name="chunk_size" type="number" value="50" min="1" max="50000">
              <div class="mini">Recipients are split into chunks of this size. Each chunk picks one sender email.</div>
            </div>
            <div>
              <label>Thread workers</label>
              <input name="thread_workers" type="number" value="5" min="1" max="200">
              <div class="mini">Workers send in parallel inside the same chunk (one SMTP connection per worker).</div>
            </div>
          </div>

          <div class="row" style="margin-top:10px">
            <div>
              <label>Sleep between chunks (seconds)</label>
              <input name="sleep_chunks" type="number" value="0.0" step="0.1" min="0" max="120">
            </div>
            <div>
              <div class="mini" style="margin-top:26px">Tip: start with <b>chunk size 20–100</b> and <b>workers 2–10</b>.</div>
            </div>
          </div>

          <div class="check" style="margin-top:12px">
            <input type="checkbox" name="use_blacklist_ip" id="use_blacklist_ip">
            <div>
              Use blacklisted sender IPs anyway (not recommended). If disabled, listed sender IPs are banished automatically.
            </div>
          </div>
          <div class="check" style="margin-top:10px">
            <input type="checkbox" name="use_blacklist_domain" id="use_blacklist_domain">
            <div>
              Use blacklisted sender domains anyway (not recommended). If disabled, Spamhaus-listed domains are banished automatically.
            </div>
          </div>
        </div>

        <div class="hint" style="margin-top:10px">
            <b>AI rewrite (optional):</b> rewrite subject/body for clarity (requires OpenRouter token).
            <div class="row" style="margin-top:10px">
              <div>
                <label>AI Token (OpenRouter)</label>
                <input name="ai_token" type="password" placeholder="sk-or-..." autocomplete="off">
                <div class="mini">Token is not saved unless you enable the checkbox below.</div>
              </div>
              <div>
                <label>&nbsp;</label>
                <div class="check" style="margin-top:0">
                  <input type="checkbox" name="use_ai" id="use_ai">
                  <div>
                    Use AI rewrite before sending (applies once per job).
                  </div>
                </div>
                <div class="check" style="margin-top:10px">
                  <input type="checkbox" id="remember_ai" name="remember_ai">
                  <div>
                    Remember AI token on this browser (server database / SQLite). <b style="color: var(--warn)">Not recommended</b> on shared PCs.
                  </div>
                </div>
              </div>
            </div>
            <div class="actions" style="margin-top:10px">
              <button class="btn secondary" type="button" id="btnAiRewrite">🤖 Rewrite Now</button>
              <div class="mini" id="aiMini">Rewrites the current Subject lines + Body and fills the fields (review before sending).</div>
            </div>
          </div>

        
      </div>
      </div>
    </div>

    <div class="card">
      <h2>Message</h2>

      <div class="row sender-manual">
        <div>
          <label>Sender Name</label>
          <textarea name="from_name" placeholder="Example: Ahmed (one per line)" required="" style="min-height:48px"></textarea>
        </div>
        <div>
          <label>Sender Email</label>
          <textarea name="from_email" placeholder="Example: sender@domain.com (one per line)" required="" style="min-height:48px"></textarea>
        </div>
      </div>

      <label>Subject</label>
      <textarea name="subject" placeholder="Email subject (one per line)" required="" style="min-height:48px"></textarea>

      <div class="row">
        <div>
          <label>Format</label>
          <select name="body_format">
            <option value="text" selected="">Text</option>
            <option value="html">HTML</option>
          </select>
          <div class="mini">If you choose HTML, the email will be sent as HTML.</div>
        </div>
        <div>
          <label>Reply-To (optional)</label>
          <input name="reply_to" placeholder="reply@domain.com">
        </div>
      </div>

      <label>Spam score limit</label>
      <input type="range" class="form-range" min="1" max="10" value="4" step="0.5" style="width: 100%;" name="score_range" id="score_range">
      <div class="mini">Current limit: <b id="score_range_val">4.0</b> (sending is blocked if spam score is higher)</div>

      <label style="margin-top:10px">Domain score limit (Spamhaus)</label>
      <input type="range" class="form-range" min="-10" max="20" value="10" step="1" style="width: 100%;" name="domain_score_limit" id="domain_score_limit">
      <div class="mini">Current limit: <b id="domain_score_limit_val">10</b> (domain is banished if score is above this limit)</div>

      <label>Body</label>
      <textarea name="body" placeholder="Write your message here..." required=""></textarea>

      <div class="row" style="margin-top:10px">
        <div>
          <label>URL list (one per line)</label>
          <textarea name="urls_list" placeholder="https://example.com/a
https://example.com/b" style="min-height:90px"></textarea>
          <div class="mini">Use <code>[URL]</code> in body. Replaced with a random URL from this list per send request.</div>
        </div>
        <div>
          <label>SRC list (one per line)</label>
          <textarea name="src_list" placeholder="https://cdn.example.com/img1.png
https://cdn.example.com/img2.png" style="min-height:90px"></textarea>
          <div class="mini">Use <code>[SRC]</code> in body. Replaced with <code>{link_src}/{identifier}.png</code> where identifier = 10-digit hash of recipient email. Use <code>[MAIL]</code> or <code>[EMAIL]</code> for recipient email, and <code>[NAME]</code> for the part before @.</div>
        </div>
      </div>

      <h2 style="margin-top:14px">Recipients</h2>

      <label>Recipients (newline / comma / semicolon)</label>
      <textarea name="recipients" placeholder="a@x.com
b@y.com
c@z.com"></textarea>

      <label>Or upload a .txt or .csv file (single column or multiple columns)</label>
      <input type="file" name="recipients_file" accept=".txt,.csv">

      <label>Maillist Safe (optional whitelist)</label>
      <textarea name="maillist_safe" placeholder="If set, ONLY these emails will receive (newline / comma / semicolon)"></textarea>
      <div class="mini">If this field is filled, recipients not in this list will be skipped.</div>

      <div class="hint">
        ✅ This tool will:
        <ul style="margin:8px 0 0; padding:0 18px; color: rgba(255,255,255,.62)">
          <li>Clean &amp; deduplicate recipients</li>
          <li>Filter invalid emails</li>
          <li>Show progress + logs</li>
        </ul>
      </div>

      <div class="actions">
        <button class="btn" type="submit" id="btnStart">🚀 Start Sending</button>
              </div>

      <div class="foot">
        Tip: test first with 2–5 emails to confirm SMTP settings before sending large batches.
      </div>
    </div>
  </form>

  <div class="card" id="domainsCard" style="margin-top:14px">
    <h2>In use domains</h2>

    <div class="actions" style="margin-top:12px">
      <input id="domQ" placeholder="Search domain..." style="max-width:320px">
      <button class="btn secondary" type="button" id="btnDomains" disabled="">🌐 Refresh</button>
      <div class="mini" id="domStatus">Loading...</div>
    </div>

    <div class="hint" style="margin-top:12px">
      <div class="mini"><b>Safe domains:</b> <span id="domSafeTotals">—</span></div>
    </div>

    <div style="overflow:auto; margin-top:12px">
      <table>
        <thead>
          <tr>
            <th>Sender domain</th>
            <th>MX</th>
            <th>MX hosts</th>
            <th>Mail IP(s)</th>
            <th>Listed</th>
            <th>SPF</th>
            <th>DKIM</th>
            <th>DMARC</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody id="domTblSafe">
          <tr><td colspan="9" class="muted">—</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<div class="toast-wrap" id="toastWrap"></div>
"""

SEND_PAGE_SCRIPT = r"""
function q(name){ return document.querySelector(`[name="${name}"]`); }

  function labelForElement(el){
    if(!el) return '';
    const raw = (el.textContent || '').replace(/\s+/g, ' ').trim();
    return raw.replace(/^[-•\s]+/, '');
  }

  // -------------------------
  // Persist form values (SQLite via server API)
  // -------------------------

  const CAMPAIGN_ID = {{ campaign_id|tojson }};
  let __sendSubmitting = false;  // prevent double-submit while a job is being created
  let __manualSendMode = false;
  let __infraPayload = null;
  let __bridgeAutoSendAllowed = false;
  let __lastPreflightResult = null;

  function parseLines(raw){
    return (raw || '')
      .split(/\r?\n/)
      .map(x => x.trim())
      .filter(Boolean);
  }

  function pickRandom(arr){
    if(!Array.isArray(arr) || !arr.length) return '';
    return arr[Math.floor(Math.random() * arr.length)] || '';
  }

  function normalizeEmail(email){
    return (email || '').toString().trim().toLowerCase();
  }

  async function emailTo10Digits(email){
    const normalized = normalizeEmail(email);
    const enc = new TextEncoder();
    const buf = await crypto.subtle.digest('SHA-256', enc.encode(normalized));
    const bytes = new Uint8Array(buf).slice(0, 8);
    let n = 0n;
    for(const b of bytes){
      n = (n << 8n) + BigInt(b);
    }
    const mod = (n % 10000000000n).toString();
    return mod.padStart(10, '0');
  }

  function extractDomainsFromFromEmails(rawFrom){
    const domains = new Set();
    parseLines(rawFrom).forEach((line) => {
      const parts = line.split('@');
      if(parts.length === 2){
        const d = (parts[1] || '').trim().toLowerCase();
        if(d) domains.add(d);
      }
    });
    return Array.from(domains);
  }

  function setManualSendMode(enabled){
    __manualSendMode = !!enabled;
    const manualModeInput = q('manual_send_mode');
    if(manualModeInput){
      manualModeInput.value = __manualSendMode ? '1' : '0';
    }
    document.querySelectorAll('.manual-only').forEach((el)=>{
      el.style.display = __manualSendMode ? "block" : "none";
    });
    document.querySelectorAll('.manual-only-inline').forEach((el)=>{
      el.style.display = __manualSendMode ? "inline-flex" : "none";
    });
    document.querySelectorAll('.sender-manual').forEach((el)=>{
      el.style.display = (__manualSendMode || !__infraPayload) ? "grid" : "none";
    });
    const btn = document.getElementById('btnManualMode');
    if(btn){
      btn.classList.toggle('active', __manualSendMode);
      btn.setAttribute('aria-pressed', __manualSendMode ? 'true' : 'false');
      const txt = btn.querySelector('.switch-text');
      if(txt){ txt.textContent = __manualSendMode ? "🧰 MANUAL SEND: ON" : "🧰 MANUAL SEND: OFF"; }
    }

    const infraCard = document.getElementById('infraCard');
    if(infraCard){
      // Hide bridge card while manual mode is ON, even if payload exists.
      infraCard.style.display = (__manualSendMode || !__infraPayload) ? "none" : "block";
    }
    const payloadInput = document.getElementById('infraPayloadInput');
    if(payloadInput){
      payloadInput.value = (!__manualSendMode && __infraPayload) ? JSON.stringify(__infraPayload) : '';
    }
  }

  function loadInfrastructurePayload(){
    try{
      const raw = window.localStorage.getItem('shivaBridgePayloadV1');
      if(!raw) return null;
      const parsed = JSON.parse(raw);
      if(!parsed || !Array.isArray(parsed.servers) || !parsed.servers.length) return null;
      return parsed;
    }catch(_e){
      return null;
    }
  }

  function consumeBridgeLaunchMarker(){
    const markerKey = 'shivaBridgeLaunchV1';
    const maxAgeMs = 2 * 60 * 1000; // only allow auto mode right after script3 -> Send to Shiva
    try{
      const raw = window.localStorage.getItem(markerKey);
      if(!raw) return false;
      let parsed = null;
      try{
        parsed = JSON.parse(raw);
      }catch(_e){
        parsed = null;
      }
      const ts = Number((parsed || {}).createdAtMs || 0);
      const source = String((parsed || {}).source || '');
      const fresh = Number.isFinite(ts) && (Date.now() - ts) <= maxAgeMs;
      const allowed = (source === 'script3-send-to-shiva') && fresh;
      window.localStorage.removeItem(markerKey); // one-time marker; direct opens after that are manual
      return allowed;
    }catch(_e){
      try{ window.localStorage.removeItem(markerKey); }catch(_ignored){}
      return false;
    }
  }

  function renderInfrastructureCard(payload){
    const card = document.getElementById('infraCard');
    const meta = document.getElementById('infraMeta');
    const details = document.getElementById('infraDetails');
    const payloadInput = document.getElementById('infraPayloadInput');
    if(!card || !meta || !details || !payloadInput) return;
    if(!payload){
      __infraPayload = null;
      card.style.display = 'none';
      payloadInput.value = '';
      return;
    }
    __infraPayload = payload;
    payloadInput.value = JSON.stringify(payload);
    card.style.display = __manualSendMode ? 'none' : 'block';
    const generatedAt = payload.createdAt || 'unknown time';
    meta.innerHTML = `
      <span>🧩 <b>Bridge Summary:</b></span>
      <span style="margin-inline:6px">🖥️ Servers: <b>${escHtml(payload.servers.length)}</b></span>
      <span>🕒 Generated: <b>${escHtml(generatedAt)}</b></span>
    `;
    details.innerHTML = payload.servers.map((srv) => {
      const smtpOk = srv.smtp && srv.smtp.host ? 'Configured' : 'Missing';
      const sshOk = srv.ssh && srv.ssh.sshHost ? 'Configured' : 'Missing';
      const statusSmtp = smtpOk === 'Configured' ? '✅ Configured' : '❌ Missing';
      const statusSsh = sshOk === 'Configured' ? '✅ Configured' : '❌ Missing';
      return `<div class="hint" style="margin-top:10px">
        <div style="font-weight:800; margin-bottom:8px">🖥️ ${escHtml(srv.serverName || srv.serverId || 'Server')}</div>
        <div class="mini">🌐 <b>IP(s):</b> ${escHtml((srv.ips || []).join(', ') || '—')}</div>
        <div class="mini">🏷️ <b>Domains:</b> ${escHtml((srv.domains || []).join(', ') || '—')}</div>
        <div class="mini">📧 <b>Sender emails:</b> ${escHtml((srv.senderEmails || []).join(', ') || '—')}</div>
        <div class="mini">👤 <b>Sender names:</b> ${escHtml((srv.senderNames || []).join(', ') || '—')}</div>
        <div class="mini" style="margin-top:6px">⚙️ <b>SMTP:</b> ${escHtml(statusSmtp)} &nbsp;|&nbsp; 🔐 <b>SSH:</b> ${escHtml(statusSsh)}</div>
              </div>`;
    }).join('');

    const first = payload.servers[0] || {};
    if(first.smtp){
      if(q('smtp_host')) q('smtp_host').value = first.smtp.host || '';
      if(q('smtp_port')) q('smtp_port').value = first.smtp.port || '2525';
      if(q('smtp_security')) q('smtp_security').value = first.smtp.security || 'none';
      if(q('smtp_timeout')) q('smtp_timeout').value = first.smtp.timeout || '25';
      if(q('smtp_user')) q('smtp_user').value = first.smtp.user || '';
      if(q('smtp_pass')) q('smtp_pass').value = first.smtp.pass || '';
    }
    if(first.ssh){
      if(q('ssh_host')) q('ssh_host').value = first.ssh.sshHost || '';
      if(q('ssh_port')) q('ssh_port').value = first.ssh.sshPort || '22';
      if(q('ssh_user')) q('ssh_user').value = first.ssh.sshUser || '';
      if(q('ssh_pass')) q('ssh_pass').value = first.ssh.sshPass || '';
      if(q('ssh_timeout')) q('ssh_timeout').value = first.ssh.sshTimeout || '8';
    }
    const allSenderEmails = payload.servers.flatMap(s => Array.isArray(s.senderEmails) ? s.senderEmails : []);
    const allSenderNames = payload.servers.flatMap(s => Array.isArray(s.senderNames) ? s.senderNames : []);
    if(q('from_email')) q('from_email').value = allSenderEmails.join('\n');
    if(q('from_name')) q('from_name').value = allSenderNames.join('\n');
  }

  async function apiGetForm(){
    try{
      const r = await fetch(`/api/campaign/${CAMPAIGN_ID}/form`);
      const j = await r.json().catch(()=>({}));
      if(r.ok && j && j.ok && j.data && typeof j.data === 'object'){
        return j.data;
      }
    }catch(e){ /* ignore */ }
    return {};
  }

  async function apiSaveForm(data){
    try{
      await fetch(`/api/campaign/${CAMPAIGN_ID}/form`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({data: data || {}})
      });
    }catch(e){ /* ignore */ }
  }

  async function apiClearForm(scope){
    try{
      await fetch(`/api/campaign/${CAMPAIGN_ID}/clear`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({scope: scope || 'mine'})
      });
    }catch(e){ /* ignore */ }
  }

  function formFields(){
    return document.querySelectorAll('#mainForm input, #mainForm textarea, #mainForm select');
  }

  async function loadSavedForm(){
    const data = await apiGetForm();
    let savedInfraPayload = null;
    for(const [k,v] of Object.entries(data || {})){
      if(k === 'manual_send_mode') continue;
      if(k === 'infra_payload'){
        if(v){
          try{
            const parsed = (typeof v === 'string') ? JSON.parse(v) : v;
            if(parsed && typeof parsed === 'object' && Array.isArray(parsed.servers) && parsed.servers.length){
              savedInfraPayload = parsed;
            }
          }catch(_e){
            savedInfraPayload = null;
          }
        }
        continue;
      }
      const el = q(k);
      if(!el) continue;
      if(el.type === 'file') continue;
      if(el.type === 'checkbox'){
        el.checked = !!v;
      }else{
        el.value = (v ?? '').toString();
      }
    }
    if(savedInfraPayload){
      renderInfrastructureCard(savedInfraPayload);
    }
    return data || {};
  }

  async function saveFormNow(){
    const data = {};
    const rememberPass = document.getElementById('remember_pass')?.checked;

    formFields().forEach(el => {
      const name = el.name;
      if(!name) return;
      if(el.type === 'file') return;

      if(el.type === 'password'){
        // Only store secrets if user explicitly opts in.
        if(name === 'smtp_pass'){
          data[name] = rememberPass ? (el.value || '') : '';
          return;
        }
        if(name === 'ssh_pass'){
          const rememberSsh = document.getElementById('remember_ssh_pass')?.checked;
          data[name] = rememberSsh ? (el.value || '') : '';
          return;
        }
        if(name === 'ai_token'){
          const rememberAi = document.getElementById('remember_ai')?.checked;
          data[name] = rememberAi ? (el.value || '') : '';
          return;
        }
        data[name] = '';
        return;
      }

      if(el.type === 'checkbox'){
        data[name] = !!el.checked;
        return;
      }

      data[name] = (el.value ?? '').toString();
    });

    data.__ts = Date.now();
    await apiSaveForm(data);
  }

  let _saveTimer = null;
  function scheduleSave(){
    if(_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(() => { saveFormNow(); }, 250);
  }

  function bindOnChangeAutoSave(){
    formFields().forEach((el) => {
      if(el.type === 'file') return;
      el.addEventListener('change', () => { saveFormNow(); });
    });
  }

  function escHtml(s){
    return (s ?? '').toString()
      .replaceAll('&','&amp;')
      .replaceAll('<','&lt;')
      .replaceAll('>','&gt;')
      .replaceAll('"','&quot;')
      .replaceAll("'",'&#39;');
  }

  function toast(title, msg, kind){
    const wrap = document.getElementById('toastWrap');
    const div = document.createElement('div');
    div.className = `toast ${kind || 'warn'}`;
    const safeTitle = escHtml(title);
    const safeMsg = escHtml(msg).split(/\r?\n/).join("<br>");
    div.innerHTML = `<div class="t">${safeTitle}</div><div>${safeMsg}</div>`;
    wrap.appendChild(div);
    setTimeout(() => {
      div.style.opacity = '0';
      div.style.transform = 'translateY(6px)';
      div.style.transition = 'all .22s ease';
      setTimeout(()=>div.remove(), 260);
    }, 3600);
  }

  function setInline(html, kind){
    const box = document.getElementById('smtpTestInline');
    box.classList.add('show');
    box.style.borderColor = kind === 'good' ? 'rgba(53,228,154,.35)' : (kind === 'bad' ? 'rgba(255,94,115,.35)' : 'rgba(255,193,77,.35)');
    box.innerHTML = html;
  }

  async function doSmtpTest(){
    const btn = document.getElementById('btnTest');
    btn.disabled = true;

    const payload = {
      smtp_host: (q('smtp_host')?.value || '').trim(),
      smtp_port: (q('smtp_port')?.value || '').trim(),
      smtp_security: (q('smtp_security')?.value || 'none').trim(),
      smtp_timeout: (q('smtp_timeout')?.value || '25').trim(),
      smtp_user: (q('smtp_user')?.value || '').trim(),
      smtp_pass: (q('smtp_pass')?.value || '').trim(),
    };

    if(!payload.smtp_host || !payload.smtp_port){
      toast('SMTP Test', 'Please enter Host and Port first.', 'warn');
      setInline('<b>SMTP Test:</b> Please enter Host and Port first.', 'warn');
      btn.disabled = false;
      return;
    }

    toast('SMTP Test', 'Testing connection...', 'warn');
    setInline('<b>SMTP Test:</b> Testing connection...', 'warn');

    try{
      const r = await fetch('/api/smtp_test', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const j = await r.json().catch(()=>({}));

      if(r.ok && j.ok){
        toast('✅ SMTP OK', j.detail || 'Connection successful', 'good');
        setInline(`<b>SMTP OK</b><br>• ${j.detail || ''}<br>• Time: <b>${j.time_ms || 0}ms</b>`, 'good');
      } else {
        const msg = (j && (j.detail || j.error)) ? (j.detail || j.error) : `HTTP ${r.status}`;
        toast('❌ SMTP Failed', msg, 'bad');
        setInline(`<b>SMTP Failed</b><br>• ${msg}`, 'bad');
      }

    }catch(e){
      toast('❌ SMTP Failed', e?.toString?.() || 'Unknown error', 'bad');
      setInline(`<b>SMTP Failed</b><br>• ${(e?.toString?.() || 'Unknown error')}`, 'bad');
    }finally{
      btn.disabled = false;
    }
  }

  document.getElementById('btnTest').addEventListener('click', doSmtpTest);

  async function doSshTest(){
    const btn = document.getElementById('btnSshTest');
    const box = document.getElementById('sshTestInline');
    const setBox = (html, kind) => {
      box.classList.add('show');
      box.style.borderColor = kind === 'good' ? 'rgba(53,228,154,.35)' : (kind === 'bad' ? 'rgba(255,94,115,.35)' : 'rgba(255,193,77,.35)');
      box.innerHTML = html;
    };

    btn.disabled = true;
    const payload = {
      smtp_host: (q('smtp_host')?.value || '').trim(),
      ssh_host: (q('ssh_host')?.value || '').trim(),
      ssh_port: (q('ssh_port')?.value || '22').trim(),
      ssh_user: (q('ssh_user')?.value || '').trim(),
      ssh_key_path: (q('ssh_key_path')?.value || '').trim(),
      ssh_pass: (q('ssh_pass')?.value || '').trim(),
      ssh_timeout: (q('ssh_timeout')?.value || '8').trim(),
    };

    try{
      const r = await fetch('/api/ssh_test', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const j = await r.json().catch(()=>({}));
      if(r.ok && j.ok){
        toast('✅ SSH OK', j.detail || 'SSH connection successful', 'good');
        setBox(`<b>SSH OK</b><br>• ${(j.detail || '')}<br>• Target: <b>${escHtml(j.target || '—')}</b>`, 'good');
      }else{
        const msg = (j && (j.detail || j.error)) ? (j.detail || j.error) : `HTTP ${r.status}`;
        toast('❌ SSH Failed', msg, 'bad');
        setBox(`<b>SSH Failed</b><br>• ${escHtml(msg)}`, 'bad');
      }
    }catch(e){
      const msg = e?.toString?.() || 'Unknown error';
      toast('❌ SSH Failed', msg, 'bad');
      setBox(`<b>SSH Failed</b><br>• ${escHtml(msg)}`, 'bad');
    }finally{
      btn.disabled = false;
    }
  }

  document.getElementById('btnSshTest').addEventListener('click', doSshTest);

  async function doAiRewrite(){
    const btn = document.getElementById('btnAiRewrite');
    if(btn) btn.disabled = true;

    const token = (q('ai_token')?.value || '').trim();

    if(!token){
      toast('AI rewrite', 'Please paste your OpenRouter token first.', 'warn');
      if(btn) btn.disabled = false;
      return;
    }

    const subjText = (q('subject')?.value || '');
    const body = (q('body')?.value || '');
    const body_format = (q('body_format')?.value || 'text');

    toast('AI rewrite', 'Rewriting subject/body...', 'warn');

    try{
      const r = await fetch('/api/ai_rewrite', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          token,
          subjects: subjText.split('\n').map(x=>x.trim()).filter(Boolean),
          body,
          body_format
        })
      });
      const j = await r.json().catch(()=>({}));
      if(r.ok && j.ok){
        const subjEl = q('subject');
        const bodyEl = q('body');

        // Subjects: accept array or string, sanitize, fallback to current text
        const subjArr = Array.isArray(j.subjects)
          ? j.subjects
          : (typeof j.subjects === 'string' ? [j.subjects] : []);

        const cleaned = subjArr
          .map(x => (x ?? '').toString().trim())
          .filter(x => x && !['undefined','null','none'].includes(x.toLowerCase()));

        if(subjEl){
          if(cleaned.length){
            subjEl.value = cleaned.join('\n');
          } else {
            // keep existing subject if AI didn't return subjects
            subjEl.value = subjText;
          }
        }

        if(bodyEl && typeof j.body === 'string'){
          bodyEl.value = j.body;
        }

        scheduleSave();
        toast('✅ AI rewrite', 'Updated Subject + Body. Review, then send.', 'good');
      } else {
        const msg = (j && (j.error || j.detail)) ? (j.error || j.detail) : ('HTTP ' + r.status);
        toast('❌ AI rewrite failed', msg, 'bad');
      }
    }catch(e){
      toast('❌ AI rewrite failed', (e?.toString?.() || 'Unknown error'), 'bad');
    }finally{
      if(btn) btn.disabled = false;
    }
  }

  const _aiBtn = document.getElementById('btnAiRewrite');
  if(_aiBtn){ _aiBtn.addEventListener('click', doAiRewrite); }

  function buildPreflightPayload(){
    return {
      smtp_host: (q('smtp_host')?.value || '').trim(),
      from_email: (q('from_email')?.value || ''),
      subject: (q('subject')?.value || ''),
      body_format: (q('body_format')?.value || 'text'),
      body: (q('body')?.value || ''),
      spam_limit: (q('score_range')?.value || '4'),
      domain_score_limit: (q('domain_score_limit')?.value || '10'),
      use_blacklist_ip: !!(q('use_blacklist_ip')?.checked),
      use_blacklist_domain: !!(q('use_blacklist_domain')?.checked),
    };
  }

  function evaluatePreflightPolicies(result){
    const j = result || {};
    const bannedIps = new Set();
    const bannedDomains = new Set();
    const notes = [];
    const bannedDomainReasons = {};
    const useBlacklistIp = !!(q('use_blacklist_ip')?.checked);
    const useBlacklistDomain = !!(q('use_blacklist_domain')?.checked);
    const domainLimit = Number(q('domain_score_limit')?.value || '10');

    const senderDomainIpListings = j.sender_domain_ip_listings || {};
    const senderDomainDblListings = j.sender_domain_dbl_listings || {};
    const senderDomainScores = j.sender_domain_scores || j.sender_domain_spam_scores || {};
    const senderDomainAuth = j.sender_domain_auth || {};

    function addReason(dom, reason){
      const key = (dom || '').toString().trim().toLowerCase();
      if(!key || !reason) return;
      if(!bannedDomainReasons[key]) bannedDomainReasons[key] = [];
      if(!bannedDomainReasons[key].includes(reason)) bannedDomainReasons[key].push(reason);
    }

    for(const [dom, ipMap] of Object.entries(senderDomainIpListings)){
      for(const [ip, listings] of Object.entries(ipMap || {})){
        if(Array.isArray(listings) && listings.length && !useBlacklistIp){
          bannedIps.add(ip);
          bannedDomains.add(dom);
          notes.push(`banished IP ${ip} (${dom}) by Spamhaus DNSBL`);
          addReason(dom, `Blacklist Spamhaus DNSBL (${ip})`);
        }
      }
    }

    for(const [dom, listings] of Object.entries(senderDomainDblListings)){
      if(Array.isArray(listings) && listings.length && !useBlacklistDomain){
        bannedDomains.add(dom);
        notes.push(`banished domain ${dom} by Spamhaus DBL`);
        addReason(dom, 'Blacklist Spamhaus DBL');
      }
    }

    for(const [dom, rawScore] of Object.entries(senderDomainScores)){
      const score = Number(rawScore);
      if(Number.isFinite(score) && (score < -10 || score > 20 || score > domainLimit)){
        bannedDomains.add(dom);
        notes.push(`banished domain ${dom} by score ${score}`);
        addReason(dom, `Limit score (${score} > ${domainLimit})`);
      }
    }

    for(const [dom, auth] of Object.entries(senderDomainAuth)){
      const spfMissing = ((auth.spf || {}).status || '').toLowerCase() !== 'pass';
      const dkimMissing = ((auth.dkim || {}).status || '').toLowerCase() !== 'pass';
      const dmarcMissing = ((auth.dmarc || {}).status || '').toLowerCase() !== 'pass';
      if(spfMissing || dkimMissing || dmarcMissing){
        bannedDomains.add(dom);
        notes.push(`banished domain ${dom} due to SPF/DKIM/DMARC`);
        if(spfMissing) addReason(dom, 'SPF missing/invalid');
        if(dkimMissing) addReason(dom, 'DKIM missing/invalid');
        if(dmarcMissing) addReason(dom, 'DMARC missing/invalid');
      }
    }

    return {
      bannedIps: Array.from(bannedIps),
      bannedDomains: Array.from(bannedDomains),
      bannedDomainReasons,
      notes,
    };
  }

  async function applyMessageMacrosBeforeSend(){
    const bodyEl = q('body');
    if(!bodyEl) return;
    let body = bodyEl.value || '';
    const urls = parseLines(q('urls_list')?.value || '');
    const srcRoots = parseLines(q('src_list')?.value || '');
    const rcpts = parseLines(q('recipients')?.value || '');
    const firstRecipient = rcpts[0] || '';

    if(body.includes('[URL]') && urls.length){
      body = body.replace(/\[URL\]/g, pickRandom(urls));
    }

    if(body.includes('[SRC]') && srcRoots.length && firstRecipient){
      const srcRoot = pickRandom(srcRoots).replace(/\/+$/,'');
      const identifier = await emailTo10Digits(firstRecipient);
      body = body.replace(/\[SRC\]/g, `${srcRoot}/${identifier}.png`);
    }

    bodyEl.value = body;
  }

  async function doPreflight(){
    const btn = document.getElementById('btnPreflight');
    if(btn) btn.disabled = true;
    const payload = buildPreflightPayload();

    toast('Preflight', 'Checking spam score + blacklist...', 'warn');

    try{
      const r = await fetch('/api/preflight', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const j = await r.json().catch(()=>({}));

      const spamEl = document.getElementById('pfSpam');
      const spamMore = document.getElementById('pfSpamMore');
      const blEl = document.getElementById('pfBl');
      const blMore = document.getElementById('pfBlMore');

      if(!spamEl || !blEl){
        toast('Preflight UI error', 'Missing elements: pfSpam/pfBl. Please refresh the page.', 'bad');
        return;
      }

      if(r.ok && j.ok){
        // spam
        if(j.spam_score !== null && j.spam_score !== undefined){
          const s = Number(j.spam_score);
          const lim = Number(j.spam_threshold);
          spamEl.textContent = s.toFixed(2) + ' (limit ' + lim.toFixed(1) + ')';
          spamEl.style.color = (s <= lim) ? 'var(--good)' : 'var(--bad)';
        }else{
          spamEl.textContent = 'unavailable';
          spamEl.style.color = 'var(--warn)';
        }

        if(j.spam_backend){
          spamMore.style.display = 'block';
          spamMore.textContent = 'Backend: ' + j.spam_backend;
        }else{
          spamMore.style.display = 'none';
        }

        // blacklist summary
        const ipListings = j.ip_listings || {};
        const domListings = j.domain_listings || [];

        // IPs from SMTP host
        const listedIpLines = [];
        for(const [ip, arr] of Object.entries(ipListings)){
          if(arr && arr.length){
            listedIpLines.push(ip + ': ' + arr.map(x=>x.zone).join(', '));
          }
        }

        // Domain DBL (domain-level)
        const domZones = (domListings || []).map(x=>x.zone).filter(Boolean);

        // NEW: Sender domains -> resolve IPs -> check IP DNSBL
        const senderDomainIps = j.sender_domain_ips || {};
        const senderDomainIpListings = j.sender_domain_ip_listings || {};
        const senderDomainDblListings = j.sender_domain_dbl_listings || {};
        const senderDomainSpamScores = j.sender_domain_spam_scores || {};
        const senderDomainSpamBackends = j.sender_domain_spam_backends || {};
        const senderDomainAuth = j.sender_domain_auth || {};
        const senderDomainScores = j.sender_domain_scores || senderDomainSpamScores || {};
        const domainScoreLimit = Number(q('domain_score_limit')?.value || '10');

        // DBL listings for ALL sender domains
        const senderDblListedLines = [];
        for(const [dom, arr] of Object.entries(senderDomainDblListings)){
          if(arr && arr.length){
            const zones = arr.map(x => (x && x.zone) ? x.zone : '').filter(Boolean);
            if(zones.length){
              senderDblListedLines.push(dom + ': ' + zones.join(', '));
            } else {
              senderDblListedLines.push(dom + ': listed');
            }
          }
        }

        const senderListedLines = [];
        const senderAllLines = [];

        for(const [dom, ips] of Object.entries(senderDomainIps)){
          const ipArr = Array.isArray(ips) ? ips : [];
          if(ipArr.length){
            senderAllLines.push(dom + ' => ' + ipArr.join(', '));
          }
        }

        for(const [dom, ipmap] of Object.entries(senderDomainIpListings)){
          const m = ipmap || {};
          for(const [ip, arr] of Object.entries(m)){
            if(arr && arr.length){
              senderListedLines.push(dom + ' / ' + ip + ': ' + arr.map(x=>x.zone).join(', '));
            }
          }
        }

        // Render table: all sender domains -> resolved IPs -> blacklist status + spam score
        const tb = document.getElementById('pfDomains');
        let anyDomainSpamHigh = false;
        const verdict = evaluatePreflightPolicies(j);

        if(tb){
          const domains = Array.isArray(j.sender_domains) ? j.sender_domains : [];
          if(!domains.length){
            tb.innerHTML = `<tr><td colspan="6" class="muted" style="padding:6px">No sender domains found.</td></tr>`;
          } else {
            const rows = [];
            for(const dom of domains){
              const ips = Array.isArray(senderDomainIps[dom]) ? senderDomainIps[dom] : [];
              const ipMap = senderDomainIpListings[dom] || {};
              const dblArr = Array.isArray(senderDomainDblListings[dom]) ? senderDomainDblListings[dom] : [];

              // Blacklist status (Listed/Not listed/Unknown)
              let listed = false;
              if(dblArr && dblArr.length){
                listed = true;
              }
              for(const [ip, arr] of Object.entries(ipMap)){
                if(arr && arr.length){
                  listed = true;
                }
              }

              const status = listed ? 'Listed' : (ips.length ? 'Not listed' : 'Unknown');
              const color = listed ? 'var(--bad)' : (ips.length ? 'var(--good)' : 'var(--warn)');
              const ipText = ips.length ? ips.join(', ') : '—';

              // Spam score per domain
              const scRaw = senderDomainSpamScores[dom];
              let spamText = '—';
              let spamColor = 'var(--warn)';
              if(scRaw !== null && scRaw !== undefined && scRaw !== ''){
                const sc = Number(scRaw);
                const lim = Number(j.spam_threshold);
                if(!Number.isNaN(sc)){
                  spamText = sc.toFixed(2);
                  spamColor = (sc <= lim) ? 'var(--good)' : 'var(--bad)';
                  if(sc > lim) anyDomainSpamHigh = true;
                }
              }
              const domainScoreRaw = senderDomainScores[dom];
              const domainScoreN = Number(domainScoreRaw);
              if(Number.isFinite(domainScoreN) && domainScoreN > domainScoreLimit){
                anyDomainSpamHigh = true;
              }

              const auth = senderDomainAuth[dom] || {};
              const authPass = ['spf', 'dkim', 'dmarc'].every((k) => ((auth[k] || {}).status || '').toLowerCase() === 'pass');
              const authText = authPass ? 'PASS' : 'MISSING';
              const authColor = authPass ? 'var(--good)' : 'var(--bad)';
              const isBanished = verdict.bannedDomains.includes(dom);
              const banishText = isBanished ? 'BANISHED' : 'OK';
              const banishColor = isBanished ? 'var(--bad)' : 'var(--good)';

              rows.push(
                `<tr>`+
                  `<td style="padding:6px; border-bottom:1px solid rgba(255,255,255,.10)">${escHtml(dom)}</td>`+
                  `<td style="padding:6px; border-bottom:1px solid rgba(255,255,255,.10)">${escHtml(ipText)}</td>`+
                  `<td style="padding:6px; border-bottom:1px solid rgba(255,255,255,.10); color:${color}; font-weight:800">${escHtml(status)}</td>`+
                  `<td style="padding:6px; border-bottom:1px solid rgba(255,255,255,.10); color:${spamColor}; font-weight:800">${escHtml(spamText)}</td>`+
                  `<td style="padding:6px; border-bottom:1px solid rgba(255,255,255,.10); color:${authColor}; font-weight:800">${escHtml(authText)}</td>`+
                  `<td style="padding:6px; border-bottom:1px solid rgba(255,255,255,.10); color:${banishColor}; font-weight:800">${escHtml(banishText)}</td>`+
                `</tr>`
              );
            }
            tb.innerHTML = rows.join('');
          }
        }

        __lastPreflightResult = j;
        const banIpInput = document.getElementById('banishedIpsInput');
        const banDomInput = document.getElementById('banishedDomainsInput');
        if(banIpInput) banIpInput.value = verdict.bannedIps.join('\n');
        if(banDomInput) banDomInput.value = verdict.bannedDomains.join('\n');

        const anyListed = (listedIpLines.length > 0) || (domZones.length > 0) || (senderListedLines.length > 0) || (senderDblListedLines.length > 0);

        if(!anyListed){
          blEl.textContent = 'Not listed';
          blEl.style.color = 'var(--good)';
          // Still show resolved domain IPs if available
          if(senderAllLines.length){
            blMore.style.display = 'block';
            blMore.textContent = 'Resolved sender domain IPs: ' + senderAllLines.join(' | ');
          } else {
            blMore.style.display = 'none';
          }
        } else {
          blEl.textContent = 'Listed';
          blEl.style.color = 'var(--bad)';
          const parts = [];
          if(listedIpLines.length){ parts.push('SMTP Host IP: ' + listedIpLines.join(' | ')); }
          if(domZones.length){ parts.push('Sender Domain (DBL): ' + domZones.join(', ')); }
          if(senderDblListedLines.length){ parts.push('All sender domains (DBL): ' + senderDblListedLines.join(' | ')); }
          if(senderListedLines.length){ parts.push('Sender Domain IP (DNSBL): ' + senderListedLines.join(' | ')); }
          if(!senderListedLines.length && senderAllLines.length){ parts.push('Resolved sender domain IPs: ' + senderAllLines.join(' | ')); }
          blMore.style.display = 'block';
          blMore.textContent = parts.join(' · ');
        }

        // toast
        const warn = (j.spam_score !== null && j.spam_score !== undefined && Number(j.spam_score) > Number(j.spam_threshold))
          || anyDomainSpamHigh
          || (listedIpLines.length > 0) || (domZones.length > 0) || (senderListedLines.length > 0) || (senderDblListedLines.length > 0);
        const noteSuffix = verdict.notes.length ? ` · ${verdict.notes.length} banish rule(s) applied` : '';
        toast('Preflight done', (warn ? 'Issues detected. See stats below.' : 'Looks good.') + noteSuffix, warn ? 'warn' : 'good');

      } else {
        const msg = (j && (j.error || j.detail)) ? (j.error || j.detail) : ('HTTP ' + r.status);
        toast('Preflight failed', msg, 'bad');
      }

    }catch(e){
      toast('Preflight failed', (e?.toString?.() || 'Unknown error'), 'bad');
    }finally{
      if(btn) btn.disabled = false;
    }
  }

  const _pf = document.getElementById('btnPreflight');
  if(_pf){ _pf.addEventListener('click', doPreflight); }

  const manualModeBtn = document.getElementById('btnManualMode');
  if(manualModeBtn){
    manualModeBtn.addEventListener('click', () => {
      setManualSendMode(!__manualSendMode);
      saveFormNow();
    });
  }
  __bridgeAutoSendAllowed = consumeBridgeLaunchMarker();
  renderInfrastructureCard(__bridgeAutoSendAllowed ? loadInfrastructurePayload() : null);

  // Load saved values on page open
  loadSavedForm().then((savedData) => {
    const rawSavedManual = ((savedData || {}).manual_send_mode ?? '').toString().trim().toLowerCase();
    const hasSavedManual = rawSavedManual !== '';
    const savedManual = ['1', 'true', 'yes', 'on'].includes(rawSavedManual);
    const manualByDefault = !__bridgeAutoSendAllowed || !__infraPayload; // direct/opened manually => force manual
    // If campaign already has a saved mode, restore it exactly.
    // Otherwise use launch defaults: direct /send => manual ON, bridge launch => auto.
    const initialManualMode = hasSavedManual ? savedManual : manualByDefault;
    setManualSendMode(initialManualMode);

    // One quick save after initial load (helps keep DB in sync with defaults)
    setTimeout(()=>{ saveFormNow(); }, 200);
  });
  bindOnChangeAutoSave();

  // Auto-save on change/input + AJAX submit (stay on page, show toast on errors)
  const form = document.getElementById('mainForm');
  if(form){
    form.addEventListener('input', scheduleSave);
    form.addEventListener('change', scheduleSave);

    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();

      // Hard guard: if we are already submitting, do NOTHING.
      if(__sendSubmitting){
        toast('Please wait', 'A send request is already in progress. Wait until the job is created.', 'warn');
        return;
      }

      const btn = document.getElementById('btnStart');
      __sendSubmitting = true;
      if(btn) btn.disabled = true;

      try{
        await saveFormNow();
        await applyMessageMacrosBeforeSend();

        // Always re-run preflight right before start to enforce score/blacklist/domain policies.
        const pfResponse = await fetch('/api/preflight', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify(buildPreflightPayload())
        });
        const pf = await pfResponse.json().catch(()=>({}));
        if(!(pfResponse.ok && pf.ok)){
          toast('Blocked', 'Preflight check failed. Please run Preflight and fix issues.', 'bad');
          return;
        }
        __lastPreflightResult = pf;
        const verdict = evaluatePreflightPolicies(pf);
        const spamScore = Number(pf.spam_score);
        const spamLimit = Number((pf.spam_threshold ?? q('score_range')?.value) || '4');
        if(Number.isFinite(spamScore) && Number.isFinite(spamLimit) && spamScore > spamLimit){
          toast('Blocked', `Spam score ${spamScore.toFixed(2)} is above limit ${spamLimit.toFixed(1)}.`, 'bad');
          return;
        }
        if(verdict.bannedDomains.length || verdict.bannedIps.length){
          const banIpInput = document.getElementById('banishedIpsInput');
          const banDomInput = document.getElementById('banishedDomainsInput');
          if(banIpInput) banIpInput.value = verdict.bannedIps.join('\n');
          if(banDomInput) banDomInput.value = verdict.bannedDomains.join('\n');
          renderDomainsTables();
          toast('Blocked', `Banish policy blocked sending (${verdict.bannedDomains.length} domains, ${verdict.bannedIps.length} IPs).`, 'bad');
          return;
        }

        // If campaign already has jobs (stopped/running/etc), confirm with the user.
        let latest = null;
        try{
          const r0 = await fetch(`/api/campaign/${CAMPAIGN_ID}/latest_job`);
          const j0 = await r0.json().catch(()=>({}));
          if(r0.ok && j0 && j0.ok && j0.job){ latest = j0.job; }
        }catch(e){ /* ignore */ }

        let forceNew = false;
        if(latest){
          const st = (latest.status || '').toString().toLowerCase();
          const active = (st === 'queued' || st === 'running' || st === 'backoff' || st === 'paused');
          const msg = active
            ? (`This campaign already has a job in progress:\n`+
               `- ID: ${latest.id}\n`+
               `- Status: ${latest.status}\n\n`+
               `Do you want another job?`)
            : (`This campaign already has job history (latest):\n`+
               `- ID: ${latest.id}\n`+
               `- Status: ${latest.status}\n\n`+
               `Do you want to start a new job?`);

          const yes = confirm(msg);
          if(!yes){
            toast('Cancelled', 'Start sending cancelled.', 'warn');
            return;
          }
          if(active){ forceNew = true; }
        }

        // Start recipient pre-send filter before submitting.
        toast('Maillist filter', 'The filter started verifying addresses before sending....', 'warn');

        // Only NOW show submitting toast (and lock start button) — job creation in progress.
        toast('Sending', 'Submitting... please wait', 'warn');

        const fd = new FormData(form);
        // Mark as ajax so server-side can differentiate if needed.
        fd.append('_ajax', '1');
        if(forceNew){ fd.append('force_new_job', '1'); }

        const r = await fetch('/start', {
          method: 'POST',
          body: fd,
          headers: { 'X-Requested-With': 'fetch' }
        });

        const txt = await r.text();

        if(r.ok){
          // Success: /start redirects to /jobs (with created_job query). fetch follows redirects.
          if(r.url && r.url.includes('/jobs')){
            window.location.href = r.url;
            return;
          }
          toast('✅ Started', 'Job started successfully.', 'good');
          return;
        }

        // If server blocked due to active job, show a clearer message.
        if(r.status === 409){
          toast('Blocked', txt || 'Active job already running. Please confirm to create another job.', 'warn');
        } else {
          // Error: show toast, stay on the form
          toast('❌ Blocked', txt || ('HTTP ' + r.status), 'bad');
        }

      }catch(e){
        toast('❌ Error', (e?.toString?.() || 'Unknown error'), 'bad');
      }finally{
        __sendSubmitting = false;
        if(btn) btn.disabled = false;
      }
    });
  }

  // Clear-saved button removed (campaign data is auto-saved in SQLite).

  // -------------------------
  // Save domains stats (in-page)
  // -------------------------
  let _domCache = null;

  function domStatusBadge(mx){
    if(mx === 'mx') return '<span style="color:var(--good); font-weight:800">MX</span>';
    if(mx === 'a_fallback') return '<span style="color:var(--warn); font-weight:800">A</span>';
    if(mx === 'none') return '<span style="color:var(--bad); font-weight:800">NONE</span>';
    return '<span style="color:var(--warn); font-weight:800">UNKNOWN</span>';
  }

  function domListedBadge(v){
    return v ? '<span style="color:var(--bad); font-weight:800">Listed</span>' : '<span style="color:var(--good); font-weight:800">Not listed</span>';
  }

  function domPolicyBadge(v){
    const st = (v || '').toString().toLowerCase();
    if(st === 'pass') return '<span style="color:var(--good); font-weight:800">PASS</span>';
    if(st === 'missing') return '<span style="color:var(--warn); font-weight:800">MISSING</span>';
    if(st === 'unknown_selector') return '<span style="color:var(--warn); font-weight:800">UNKNOWN SELECTOR</span>';
    return '<span style="color:var(--warn); font-weight:800">UNKNOWN</span>';
  }

  function renderDomainsTables(){
    const qv = (document.getElementById('domQ')?.value || '').trim().toLowerCase();
    const safeBody = document.getElementById('domTblSafe');
    const safeTotals = document.getElementById('domSafeTotals');

    if(!_domCache || !_domCache.ok){
      if(safeBody) safeBody.innerHTML = `<tr><td colspan="9" class="muted">—</td></tr>`;
      if(safeTotals) safeTotals.textContent = '—';
      return;
    }

    const safe = _domCache.safe || {};
    if(safeTotals){
      safeTotals.textContent = `${safe.total_emails || 0} emails · ${safe.unique_domains || 0} domains · invalid=${safe.invalid_emails || 0}`;
    }
    function safeRows(items){
      const arr = Array.isArray(items) ? items : [];
      const localSenderDomains = extractDomainsFromFromEmails(q('from_email')?.value || '');
      const localMap = {};
      for(const dom of localSenderDomains){
        localMap[dom] = { domain: dom, mx_status: 'unknown', mx_hosts: [], mail_ips: [], listed: false, spf: {status:'unknown'}, dkim: {status:'unknown'}, dmarc: {status:'unknown'}, reason: '' };
      }
      for(const it of arr){
        const dom = (it.domain || '').toString().toLowerCase();
        if(dom && localMap[dom]){
          localMap[dom] = { ...localMap[dom], ...it };
        }
      }
      const merged = [...arr];
      for(const extra of Object.values(localMap)){
        if(!arr.find((x) => ((x.domain || '').toString().toLowerCase() === (extra.domain || '').toString().toLowerCase()))){
          merged.push(extra);
        }
      }
      const out = [];
      const preVerdict = evaluatePreflightPolicies(__lastPreflightResult || {});
      for(const it of merged){
        const dom = (it.domain || '').toString();
        if(qv && !dom.toLowerCase().includes(qv)) continue;
        const mxHosts = (it.mx_hosts || []).slice(0,4).join(', ');
        const ips = (it.mail_ips || []).join(', ');
        const isBanished = preVerdict.bannedDomains.includes(dom.toLowerCase()) || preVerdict.bannedDomains.includes(dom);
        const listedCell = isBanished ? '<span style="color:var(--bad); font-weight:800">Banished</span>' : domListedBadge(!!(it.listed ?? it.any_listed));
        const domainReason = isBanished
          ? ((preVerdict.bannedDomainReasons || {})[(dom || '').toLowerCase()] || []).join(' | ')
          : ((it.reason || '').toString().trim() || '—');
        out.push(
          `<tr>`+
            `<td><code>${escHtml(dom)}</code></td>`+
            `<td>${domStatusBadge(it.mx_status)}</td>`+
            `<td class="muted">${escHtml(mxHosts || '—')}</td>`+
            `<td class="muted">${escHtml(ips || '—')}</td>`+
            `<td>${listedCell}</td>`+
            `<td>${domPolicyBadge((it.spf || {}).status)}</td>`+
            `<td>${domPolicyBadge((it.dkim || {}).status)}</td>`+
            `<td>${domPolicyBadge((it.dmarc || {}).status)}</td>`+
            `<td class="muted">${escHtml(domainReason || '—')}</td>`+
          `</tr>`
        );
      }
      return out.join('') || `<tr><td colspan="9" class="muted">No results.</td></tr>`;
    }

    if(safeBody) safeBody.innerHTML = safeRows(safe.domains);
  }

  async function refreshDomainsStats(){
    const btn = document.getElementById('btnDomains');
    const status = document.getElementById('domStatus');

    if(btn) btn.disabled = true;
    if(status) status.textContent = 'Loading...';

    try{
      const r = await fetch(`/api/campaign/${CAMPAIGN_ID}/domains_stats`);
      const j = await r.json().catch(()=>({}));
      if(r.ok && j && j.ok){
        _domCache = j;
        if(status) status.textContent = `OK · ${new Date().toLocaleTimeString()}`;
        renderDomainsTables();
        toast('In use domains', 'Updated safe domains.', 'good');
      } else {
        const msg = (j && (j.error || j.detail)) ? (j.error || j.detail) : ('HTTP ' + r.status);
        if(status) status.textContent = 'Failed';
        toast('In use domains failed', msg, 'bad');
      }
    }catch(e){
      if(status) status.textContent = 'Failed';
      toast('Domains stats failed', (e?.toString?.() || 'Unknown error'), 'bad');
    }finally{
      if(btn) btn.disabled = false;
    }
  }

  const domBtn = document.getElementById('btnDomains');
  if(domBtn){ domBtn.addEventListener('click', refreshDomainsStats); }
  const domQ = document.getElementById('domQ');
  if(domQ){ domQ.addEventListener('input', renderDomainsTables); }

  // auto-load safe domains stats once
  refreshDomainsStats();

  // Range value UI
  const scoreEl = document.getElementById('score_range');
  const scoreVal = document.getElementById('score_range_val');
  if(scoreEl && scoreVal){
    const sync = () => { scoreVal.textContent = Number(scoreEl.value).toFixed(1); };
    sync();
    scoreEl.addEventListener('input', sync);
  }
  const domainScoreEl = document.getElementById('domain_score_limit');
  const domainScoreVal = document.getElementById('domain_score_limit_val');
  if(domainScoreEl && domainScoreVal){
    const sync = () => { domainScoreVal.textContent = String(Number(domainScoreEl.value)); };
    sync();
    domainScoreEl.addEventListener('input', sync);
  }
  const fromEmailEl = q('from_email');
  if(fromEmailEl){
    fromEmailEl.addEventListener('input', renderDomainsTables);
    fromEmailEl.addEventListener('change', renderDomainsTables);
  }
"""


def split_multivalue_field(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[\n,;]+", str(value)) if part and part.strip()]


def pick_first_nonempty_line(value: str) -> str:
    items = split_multivalue_field(value)
    return items[0] if items else ""


def is_valid_email(candidate: str) -> bool:
    text = str(candidate or "").strip()
    if not text or "@" not in text:
        return False
    local, domain = text.rsplit("@", 1)
    return bool(local and "." in domain)


def email_to_10_digits(email: str) -> str:
    normalized = email.strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    num = int.from_bytes(digest[:8], "big") % 10_000_000_000
    return str(num).zfill(10)


def smtp_send_worker(job_id: str, payload: dict, *, get_job, append_job_event, safe_int, iso_fn) -> None:
    job = get_job(job_id)
    if not isinstance(job, dict):
        return
    recipients = [x for x in payload.get("recipients", []) if is_valid_email(x)]
    total = len(recipients)
    job["phase"] = "sending" if total > 0 else "completed"
    job["status"] = "running" if total > 0 else "done"
    job["runtime_mode"] = "smtp_real"
    job["updated_at"] = iso_fn(datetime.now(timezone.utc))
    if total == 0:
        append_job_event(job, "smtp_send_skipped", "No valid recipients were found.", "WARN")
        job["progress"] = 100
        return

    smtp_host = str(payload.get("smtp_host") or "").strip()
    smtp_port = safe_int(payload.get("smtp_port"), 25, minimum=1)
    smtp_security = str(payload.get("smtp_security") or "none").strip().lower()
    smtp_timeout = max(5, safe_int(payload.get("smtp_timeout"), 25, minimum=1))
    smtp_user = str(payload.get("smtp_user") or "").strip()
    smtp_pass = str(payload.get("smtp_pass") or "")
    from_name = str(payload.get("from_name") or "").strip()
    from_email = str(payload.get("from_email") or "").strip()
    subject = str(payload.get("subject") or "").strip() or "No Subject"
    body = str(payload.get("body") or "")
    body_format = str(payload.get("body_format") or "text").strip().lower()
    urls_list = [line.strip() for line in str(payload.get("urls_list") or "").splitlines() if line.strip()]
    src_list = [line.strip().rstrip("/") for line in str(payload.get("src_list") or "").splitlines() if line.strip()]
    reply_to = str(payload.get("reply_to") or "").strip()
    delay_s = max(0.0, float(payload.get("delay_s") or 0.0))

    smtp_client = None
    try:
        append_job_event(job, "smtp_connecting", f"Connecting to SMTP {smtp_host}:{smtp_port} ({smtp_security or 'none'}).")
        if smtp_security == "ssl":
            smtp_client = smtplib.SMTP_SSL(
                host=smtp_host,
                port=smtp_port,
                timeout=smtp_timeout,
                context=ssl.create_default_context(),
            )
        else:
            smtp_client = smtplib.SMTP(host=smtp_host, port=smtp_port, timeout=smtp_timeout)
            smtp_client.ehlo()
            if smtp_security == "starttls":
                smtp_client.starttls(context=ssl.create_default_context())
                smtp_client.ehlo()
        if smtp_user:
            smtp_client.login(smtp_user, smtp_pass)
        append_job_event(job, "smtp_connected", "SMTP session is ready; starting recipient loop.")

        for idx, rcpt in enumerate(recipients, start=1):
            live_job = get_job(job_id)
            if not isinstance(live_job, dict):
                break
            if str(live_job.get("status") or "").lower() in {"paused", "stopped"}:
                append_job_event(live_job, "smtp_send_halted", f"Send halted by operator at recipient {idx}/{total}.", "WARN")
                break

            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
            msg["To"] = rcpt
            if reply_to:
                msg["Reply-To"] = reply_to
            rendered_body = body
            if "[URL]" in rendered_body and urls_list:
                rendered_body = rendered_body.replace("[URL]", random.choice(urls_list))
            if "[SRC]" in rendered_body and src_list:
                src_root = random.choice(src_list)
                identifier = email_to_10_digits(rcpt)
                rendered_body = rendered_body.replace("[SRC]", f"{src_root}/{identifier}.png")
            if body_format == "html":
                msg.set_content("This message requires an HTML-capable client.")
                msg.add_alternative(rendered_body, subtype="html")
            else:
                msg.set_content(rendered_body)

            try:
                smtp_client.send_message(msg, from_addr=from_email, to_addrs=[rcpt])
                live_job["sent"] = safe_int(live_job.get("sent"), 0, minimum=0) + 1
                live_job["delivered"] = safe_int(live_job.get("delivered"), 0, minimum=0) + 1
                append_job_event(live_job, "smtp_send_ok", f"Accepted by SMTP: {rcpt}")
            except Exception as exc:
                live_job["failed"] = safe_int(live_job.get("failed"), 0, minimum=0) + 1
                append_job_event(live_job, "smtp_send_fail", f"Failed for {rcpt}: {exc}", "WARN")

            processed = safe_int(live_job.get("sent"), 0, minimum=0) + safe_int(live_job.get("failed"), 0, minimum=0)
            live_job["queued"] = max(total - processed, 0)
            live_job["progress"] = min(100, int(round((processed / max(total, 1)) * 100)))
            live_job["current_chunk"] = max(1, idx)
            live_job["updated_at"] = iso_fn(datetime.now(timezone.utc))
            if delay_s > 0:
                threading.Event().wait(delay_s)

        final_job = get_job(job_id)
        if isinstance(final_job, dict):
            if str(final_job.get("status") or "").lower() not in {"paused", "stopped"}:
                final_job["status"] = "done"
                final_job["phase"] = "completed"
                final_job["queued"] = 0
                final_job["progress"] = 100
            final_job["updated_at"] = iso_fn(datetime.now(timezone.utc))
            append_job_event(final_job, "smtp_send_completed", "SMTP send worker finished.")
    except Exception as exc:
        job["status"] = "error"
        job["phase"] = "error"
        job["updated_at"] = iso_fn(datetime.now(timezone.utc))
        append_job_event(job, "smtp_send_worker_failed", f"SMTP worker failed: {exc}", "ERROR")
    finally:
        if smtp_client is not None:
            try:
                smtp_client.quit()
            except Exception:
                pass


def render_send_page(campaign_ts: str, campaign_id: str, campaign_name_suffix: str = "") -> tuple[str, str]:
    body = render_template_string(
        SEND_PAGE_BODY,
        campaign_ts=campaign_ts,
        campaign_id=campaign_id,
        campaign_name_suffix=campaign_name_suffix,
    )
    script = render_template_string(
        SEND_PAGE_SCRIPT,
        campaign_id=campaign_id,
    )
    page_script = "<script>\n" + script + "\n</script>"
    return body, page_script
