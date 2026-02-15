from __future__ import annotations


def logo_svg() -> str:
    return """<svg xmlns='http://www.w3.org/2000/svg' width='220' height='90' viewBox='0 0 220 90' fill='none'>
  <rect x='0' y='0' width='220' height='90' rx='16' fill='#0f172a'/>
  <circle cx='45' cy='45' r='28' fill='#2dd4bf'/>
  <circle cx='37' cy='39' r='9' fill='white'/>
  <circle cx='53' cy='39' r='9' fill='white'/>
  <circle cx='39' cy='40' r='4' fill='#0f172a'/>
  <circle cx='52' cy='40' r='4' fill='#0f172a'/>
  <path d='M33 54C38 59 52 59 57 54' stroke='#0f172a' stroke-width='4' stroke-linecap='round'/>
  <circle cx='31' cy='51' r='3' fill='#0f172a'/>
  <circle cx='57' cy='49' r='2.5' fill='#0f172a'/>
  <circle cx='49' cy='56' r='2' fill='#0f172a'/>
  <text x='82' y='42' fill='white' font-size='20' font-family='Verdana, sans-serif' font-weight='700'>CookieMonster</text>
  <text x='82' y='62' fill='#93c5fd' font-size='12' font-family='Verdana, sans-serif'>Encrypted Auth Cache Inspector</text>
</svg>"""


def page_html() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>CookieMonster UI</title>
  <style>
    :root { --bg:#f3f4f6; --card:#ffffff; --ink:#111827; --sub:#6b7280; --accent:#0ea5e9; }
    body { margin:0; font-family: 'Avenir Next', 'Segoe UI', sans-serif; background: radial-gradient(circle at top, #dbeafe, var(--bg)); color:var(--ink); }
    .wrap { max-width: 980px; margin: 30px auto; padding: 0 20px; }
    .card { background:var(--card); border-radius:16px; padding:20px; box-shadow:0 10px 30px rgba(2,6,23,.08); margin-bottom:16px; }
    .row { display:flex; gap:12px; flex-wrap:wrap; }
    input,select,button,textarea { padding:10px; border-radius:10px; border:1px solid #d1d5db; font-size:14px; }
    input,select { min-width: 240px; }
    button { background:var(--accent); color:white; border:none; cursor:pointer; font-weight:600; }
    button.secondary { background:#374151; }
    pre { background:#0b1020; color:#e5e7eb; padding:12px; border-radius:12px; max-height:340px; overflow:auto; }
    .muted{ color:var(--sub); font-size:13px; }
    .ok { color:#047857; font-weight:700; }
    .bad { color:#b91c1c; font-weight:700; }
  </style>
</head>
<body>
<div class='wrap'>
  <div class='card'>
    <img src='/ui/logo.svg' alt='CookieMonster logo' style='max-width:100%; height:auto;' />
    <p class='muted'>Enter a URL, cache auth from your browser profile into an encrypted local file, and inspect if auth looks available.</p>
  </div>

  <div class='card'>
    <h3>1) Cache Auth For URL</h3>
    <div class='row'>
      <input id='url' placeholder='https://supabase.com/dashboard/project/...' style='flex:1; min-width:420px' />
      <select id='browser'><option value='chrome'>chrome</option><option value='edge'>edge</option></select>
      <input id='profileDir' placeholder='Default' value='Default' />
      <button onclick='cacheAuth()'>Cache Encrypted Auth</button>
    </div>
    <p class='muted'>Uses your local browser profile, captures for ~12s, saves encrypted cache under ~/.cookie_monster/ui/</p>
  </div>

  <div class='card'>
    <h3>2) Check Auth Cache For URL</h3>
    <div class='row'>
      <button class='secondary' onclick='checkAuth()'>Check Cached Auth</button>
      <button class='secondary' onclick='inspectAuth()'>Inspect Redacted Records</button>
    </div>
    <p id='status' class='muted'></p>
    <pre id='out'>Ready.</pre>
  </div>
</div>
<script>
async function post(path, body){
  const res = await fetch(path, {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify(body)});
  return await res.json();
}
function hostFromUrl(u){ try{return new URL(u).hostname;}catch(_){return '';} }
async function cacheAuth(){
  const url = document.getElementById('url').value.trim();
  const browser = document.getElementById('browser').value;
  const profileDirectory = document.getElementById('profileDir').value.trim() || 'Default';
  const data = await post('/ui/cache-auth', {url, browser, profile_directory: profileDirectory});
  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
  document.getElementById('status').innerHTML = data.error ? `<span class='bad'>${data.error}</span>` : `<span class='ok'>Cached ${data.captured || 0} records.</span>`;
}
async function checkAuth(){
  const url = document.getElementById('url').value.trim();
  const data = await post('/ui/check-auth', {url});
  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
  const ok = data.has_cached_auth;
  document.getElementById('status').innerHTML = ok ? `<span class='ok'>Auth appears cached for ${hostFromUrl(url)}</span>` : `<span class='bad'>No cached auth found for ${hostFromUrl(url)}</span>`;
}
async function inspectAuth(){
  const url = document.getElementById('url').value.trim();
  const data = await post('/ui/inspect-auth', {url});
  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
}
</script>
</body>
</html>
"""
