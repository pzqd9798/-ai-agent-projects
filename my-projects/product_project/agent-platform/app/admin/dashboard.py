"""Admin Dashboard — 静态 HTML 页面，FastAPI 直接渲染."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.models.database import AGENT_TEMPLATES

router = APIRouter(prefix="/admin", tags=["dashboard"])

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ClawBot Admin</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --border:#334155; --text:#e2e8f0; --accent:#38bdf8; --green:#4ade80; --red:#f87171; --dim:#94a3b8; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,sans-serif; line-height:1.6; }
  .layout { display:flex; min-height:100vh; }
  .sidebar { width:240px; background:var(--card); border-right:1px solid var(--border); padding:24px 16px; display:flex; flex-direction:column; }
  .sidebar h1 { font-size:20px; margin-bottom:32px; color:var(--accent); }
  .sidebar nav a { display:block; padding:8px 12px; color:var(--dim); text-decoration:none; border-radius:6px; margin-bottom:4px; font-size:14px; }
  .sidebar nav a:hover,.sidebar nav a.active { background:#334155; color:var(--text); }
  .main { flex:1; padding:32px; overflow-y:auto; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:24px; margin-bottom:24px; }
  .card h2 { font-size:18px; margin-bottom:16px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:16px; }
  .stat { text-align:center; padding:20px; }
  .stat .num { font-size:36px; font-weight:700; color:var(--accent); }
  .stat .label { color:var(--dim); font-size:14px; margin-top:4px; }
  .btn { padding:8px 16px; border-radius:6px; border:none; cursor:pointer; font-size:14px; font-weight:500; }
  .btn-primary { background:var(--accent); color:#0f172a; }
  .btn-danger { background:var(--red); color:#fff; }
  .btn-sm { padding:4px 10px; font-size:12px; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th { text-align:left; color:var(--dim); font-weight:500; padding:8px 12px; border-bottom:1px solid var(--border); }
  td { padding:8px 12px; border-bottom:1px solid var(--border); }
  .badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; }
  .badge-green { background:#14532d; color:var(--green); }
  .badge-blue { background:#1e3a5f; color:var(--accent); }
  input,select,textarea { width:100%; padding:8px 12px; background:var(--bg); border:1px solid var(--border); border-radius:6px; color:var(--text); font-size:14px; margin-bottom:12px; }
  textarea { min-height:120px; font-family:monospace; }
  label { display:block; font-size:13px; color:var(--dim); margin-bottom:4px; }
  .toast { position:fixed; top:16px; right:16px; padding:12px 20px; border-radius:8px; font-size:14px; z-index:1000; animation:fadeIn 0.3s; }
  .toast-success { background:#14532d; color:var(--green); border:1px solid #22c55e; }
  .toast-error { background:#7f1d1d; color:var(--red); border:1px solid #ef4444; }
  @keyframes fadeIn { from{opacity:0;transform:translateY(-8px)} to{opacity:1;transform:translateY(0)} }
  .section { display:none; }
  .section.active { display:block; }
  .template-card { cursor:pointer; border:2px solid var(--border); border-radius:10px; padding:16px; transition:all 0.2s; }
  .template-card:hover { border-color:var(--accent); }
  .template-card.selected { border-color:var(--accent); background:#1e3a5f; }
  .template-card .icon { font-size:28px; margin-bottom:8px; }
  .template-card .name { font-weight:600; margin-bottom:4px; }
  .template-card .desc { font-size:12px; color:var(--dim); }
</style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <h1>🤖 ClawBot</h1>
    <nav>
      <a href="#" class="active" data-section="overview">📊 概览</a>
      <a href="#" data-section="agents">🤖 Agent 管理</a>
      <a href="#" data-section="create">➕ 新建 Agent</a>
      <a href="#" data-section="users">👥 用户管理</a>
      <a href="#" data-section="api">🔑 API 文档</a>
    </nav>
    <div style="margin-top:auto;font-size:12px;color:var(--dim);">
      v0.2.0 · ClawBot
    </div>
  </aside>
  <main class="main" id="app">
    <!-- Dynamic content loaded by JS -->
  </main>
</div>
<div id="toast"></div>

<script>
const API = '/api/admin';
let apiKey = localStorage.getItem('clawbot_admin_key') || '';

// ── Init ──────────────────────────────────
document.querySelectorAll('nav a').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    document.querySelectorAll('nav a').forEach(x => x.classList.remove('active'));
    a.classList.add('active');
    loadSection(a.dataset.section);
  });
});

if (!apiKey) {
  apiKey = prompt('Enter Admin API Key:');
  if (apiKey) localStorage.setItem('clawbot_admin_key', apiKey);
}
loadSection('overview');

// ── Section Loader ─────────────────────────
async function loadSection(name) {
  const app = document.getElementById('app');
  try {
    switch(name) {
      case 'overview': app.innerHTML = await renderOverview(); break;
      case 'agents': app.innerHTML = await renderAgents(); break;
      case 'create': app.innerHTML = await renderCreate(); break;
      case 'users': app.innerHTML = await renderUsers(); break;
      case 'api': app.innerHTML = renderApiDocs(); break;
    }
  } catch(e) {
    app.innerHTML = `<div class="card"><h2>Error</h2><p>${e.message}</p></div>`;
  }
}

// ── Overview ──────────────────────────────
async function renderOverview() {
  let stats = {users:0,agents:0,audit_logs:0};
  try { stats = await fetch(API+'/stats',{headers:{'X-API-Key':apiKey}}).then(r=>r.json()); } catch(e){}
  let agents = [];
  try { agents = await fetch(API+'/agents',{headers:{'X-API-Key':apiKey}}).then(r=>r.json()); } catch(e){}

  const agentRows = agents.slice(0,10).map(a =>
    `<tr><td>${a.name}</td><td><span class="badge badge-blue">${a.template||'custom'}</span></td><td><span class="badge badge-green">${a.status}</span></td><td>${a.username}</td></tr>`
  ).join('');

  return `
    <h2 style="margin-bottom:24px;">📊 系统概览</h2>
    <div class="grid">
      <div class="card stat"><div class="num">${stats.users}</div><div class="label">用户数</div></div>
      <div class="card stat"><div class="num">${stats.agents}</div><div class="label">Agent 数量</div></div>
      <div class="card stat"><div class="num">${stats.audit_logs}</div><div class="label">审计日志</div></div>
    </div>
    <div class="card">
      <h2>最近 Agent</h2>
      <table><thead><tr><th>名称</th><th>模板</th><th>状态</th><th>用户</th></tr></thead><tbody>${agentRows||'<tr><td colspan="4">暂无数据</td></tr>'}</tbody></table>
    </div>`;
}

// ── Agent List ────────────────────────────
async function renderAgents() {
  const agents = await fetch(API+'/agents',{headers:{'X-API-Key':apiKey}}).then(r=>r.json());
  const rows = agents.map(a => `
    <tr>
      <td>${a.name}</td>
      <td><span class="badge badge-blue">${a.template||'custom'}</span></td>
      <td>${a.username}</td>
      <td>${(a.tools||'[]').substring(0,60)}</td>
      <td><span class="badge badge-green">${a.status}</span></td>
      <td><button class="btn btn-danger btn-sm" onclick="deleteAgent('${a.id}')">删除</button></td>
    </tr>`).join('');
  return `<div class="card"><h2>🤖 Agent 管理</h2><table><thead><tr><th>名称</th><th>模板</th><th>用户</th><th>工具</th><th>状态</th><th>操作</th></tr></thead><tbody>${rows||'<tr><td colspan="6">暂无</td></tr>'}</tbody></table></div>`;
}

// ── Create Agent ──────────────────────────
async function renderCreate() {
  let templates = {};
  try { templates = await fetch(API+'/templates',{headers:{'X-API-Key':apiKey}}).then(r=>r.json()); } catch(e){}
  const tmplCards = Object.entries(templates).map(([k,v]) =>
    `<div class="template-card" data-key="${k}" onclick="selectTemplate(this,'${k}')">
      <div class="icon">${v.icon}</div>
      <div class="name">${v.name}</div>
      <div class="desc">${v.description}</div>
    </div>`).join('');

  return `
    <h2 style="margin-bottom:24px;">➕ 新建 Agent</h2>
    <div class="card"><h2>选择模板</h2><div class="grid">${tmplCards}</div></div>
    <div class="card">
      <h2>Agent 配置</h2>
      <form onsubmit="createAgent(event)">
        <input type="hidden" id="tmpl" value="custom">
        <label>Agent 名称</label><input id="name" placeholder="例如: 我的代码助手" required>
        <label>系统提示词</label><textarea id="sprompt" placeholder="定义 Agent 的角色和行为..."></textarea>
        <label>工具列表 (逗号分隔)</label><input id="tools" placeholder="bash,read_file,write_file,web_fetch">
        <button type="submit" class="btn btn-primary">创建 Agent</button>
      </form>
    </div>`;
}

function selectTemplate(el, key) {
  document.querySelectorAll('.template-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  document.getElementById('tmpl').value = key;
  fetch(API+'/templates',{headers:{'X-API-Key':apiKey}})
    .then(r=>r.json()).then(tmpls => {
      if (tmpls[key]) {
        document.getElementById('sprompt').value = tmpls[key].system_prompt;
        document.getElementById('tools').value = (tmpls[key].tools||[]).join(',');
      }
    });
}

async function createAgent(e) {
  e.preventDefault();
  const body = {
    name: document.getElementById('name').value,
    template: document.getElementById('tmpl').value,
    system_prompt: document.getElementById('sprompt').value,
    tools: document.getElementById('tools').value.split(',').map(s=>s.trim()).filter(Boolean),
  };
  try {
    const r = await fetch(API+'/agents',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':apiKey},body:JSON.stringify(body)});
    if (r.ok) { toast('Agent 创建成功!','success'); loadSection('agents'); }
    else { toast('创建失败: '+(await r.json()).detail,'error'); }
  } catch(err) { toast('网络错误','error'); }
}

async function deleteAgent(id) {
  if (!confirm('确定删除？')) return;
  await fetch(API+'/agents/'+id,{method:'DELETE',headers:{'X-API-Key':apiKey}});
  loadSection('agents');
}

// ── Users ─────────────────────────────────
async function renderUsers() {
  const users = await fetch(API+'/users',{headers:{'X-API-Key':apiKey}}).then(r=>r.json());
  const rows = users.map(u => `
    <tr>
      <td>${u.username}</td>
      <td><span class="badge ${u.role==='admin'?'badge-green':'badge-blue'}">${u.role}</span></td>
      <td>${new Date(u.created_at*1000).toLocaleDateString('zh-CN')}</td>
      <td><button class="btn btn-primary btn-sm" onclick="createKey('${u.id}')">生成 API Key</button></td>
    </tr>`).join('');
  return `<div class="card"><h2>👥 用户管理</h2><table><thead><tr><th>用户名</th><th>角色</th><th>创建时间</th><th>操作</th></tr></thead><tbody>${rows||'<tr><td colspan="4">暂无</td></tr>'}</tbody></table></div>`;
}

async function createKey(uid) {
  const name = prompt('Key 名称:') || '';
  const r = await fetch(API+'/api-keys',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':apiKey},body:JSON.stringify({user_id:uid,name})});
  const data = await r.json();
  if (data.key) { prompt('复制此 API Key (仅显示一次):', data.key); }
}

// ── API Docs ──────────────────────────────
function renderApiDocs() {
  return `
    <div class="card"><h2>🔑 API 文档</h2><p>完整的 REST API 文档请访问:</p>
    <p><a href="/docs" style="color:var(--accent)">/docs</a> — Swagger UI</p>
    <p><a href="/redoc" style="color:var(--accent)">/redoc</a> — ReDoc</p></div>
    <div class="card"><h2>快速开始</h2>
    <pre style="background:var(--bg);padding:16px;border-radius:8px;font-size:13px;overflow-x:auto;">
# 1. 获取 API Key (在 Admin Dashboard 中生成)
# 2. 调用 Agent API

curl -X POST http://localhost:8000/agent \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: clawbot-xxxxx" \\
  -d '{"message": "你好，帮我审查这段代码"}'

# 3. 流式调用
curl -X POST http://localhost:8000/agent/stream \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: clawbot-xxxxx" \\
  -d '{"message": "解释Python装饰器"}'
    </pre></div>`;
}

// ── Toast ─────────────────────────────────
function toast(msg, type) {
  const el = document.getElementById('toast');
  el.className = 'toast toast-'+(type||'success');
  el.textContent = msg;
  setTimeout(() => el.textContent='', 3000);
}
</script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard():
    return ADMIN_HTML
