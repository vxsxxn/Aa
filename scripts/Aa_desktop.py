#!/usr/bin/env python3
"""Untitled Desktop — lean local web UI for Untitled.

`Untitled desktop` starts this: one stdlib HTTP server, one light chat page.
Runs each turn in-process through the gateway engine (hermes_cli gateway
path; a warm gateway daemon, one WS round trip per message). No frameworks.

Repo-internal experiment; not yet part of the published install types.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import queue
import socket
import socketserver
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)  # engine imports (hermes_cli, agent) live at the repo root

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Untitled</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root{--bg:#fafaf8;--fg:#3a3a3a;--muted:#8a8a8a;--line:#e4e2de;
  --card:#fff;--soft:#f0efec;--panel:#fdfdfc;--aai:#f0efec;
  --me:#dcdcdc;--dim:#a3a3a3}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);
       font:15px/1.5 -apple-system,"Segoe UI",Roboto,sans-serif;
       display:flex;flex-direction:column;height:100vh}
  header{padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--line);
         font-weight:600;letter-spacing:.3px;display:flex;align-items:center}
  header small{color:var(--dim);font-weight:400;margin-left:8px}
  #gear{margin-left:auto;background:none;border:0;color:var(--dim);font-size:18px;
        cursor:pointer;padding:2px 6px}
  #gear:hover{color:var(--fg)}
  .modal{position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;
         align-items:center;justify-content:center;z-index:10}
  .modal.open{display:flex}
  .modal .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
               padding:20px;width:min(420px,92vw);display:flex;flex-direction:column;gap:12px}
  .modal h2{margin:0;font-size:16px}
  .modal label{color:var(--dim);font-size:12px;display:block;margin-bottom:4px}
  .modal input{width:100%;background:var(--soft);color:var(--fg);border:1px solid var(--line);
               border-radius:8px;padding:9px 11px;font:inherit}
  .modal input:focus{outline:none;border-color:var(--fg)}
  .modal .row{display:flex;gap:10px;justify-content:flex-end;margin-top:4px}
  .modal .row button.secondary{background:var(--line)}
  #settingsMsg{color:var(--dim);font-size:12px;min-height:1em}
  #log{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px}
  .m{max-width:78%;padding:9px 13px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}
  .me{align-self:flex-end;background:var(--me)}
  .Untitled{align-self:flex-start;background:var(--aai);border:1px solid var(--line)}
  .Untitled.pending::after{content:"…";color:var(--dim);animation:bl 1s steps(2) infinite}
  @keyframes bl{50%{opacity:.3}}
  form{display:flex;gap:8px;padding:12px;background:var(--panel);border-top:1px solid var(--line)}
  textarea{flex:1;background:var(--soft);color:var(--fg);border:1px solid var(--line);
           border-radius:10px;padding:10px 12px;font:inherit;resize:none;height:44px}
  textarea:focus{outline:none;border-color:var(--fg)}
  button{background:#9c9c9c;color:#fff;border:0;border-radius:10px;padding:0 18px;
         font:inherit;font-weight:600;cursor:pointer}
  .hbtn{padding:6px 12px;margin-left:6px;font-size:14px}
  #modsList div{display:flex;align-items:center;gap:10px;padding:8px 4px;border-bottom:1px solid var(--soft)}
  #modsList small{color:var(--dim)}
  button:disabled{opacity:.5;cursor:default}
  #st{width:9px;height:9px;border-radius:50%;margin-left:10px;background:#666;flex:none}
  #st.ready{background:#3ecf6e}#st.warming{background:#e6b23e}#st.degraded{background:#d05050}
</style></head>
<body>
<header>Untitled<small>desktop</small><span id="st" title="checking engine…"></span><button class="hbtn" id="modsBtn" title="Mods" onclick="openMods()">&#128268;</button><button class="hbtn" id="gear" title="Settings" onclick="openSettings()">&#9881;</button></header>
<div id="log"></div>
<form id="f"><textarea id="t" placeholder="Message Untitled…" autofocus></textarea><button>Send</button></form>
<div id="modal" class="modal"><div class="card">
  <h2>Settings</h2>
  <div><label>OpenRouter API key</label>
    <input id="sKey" type="password" placeholder="sk-or-… (leave blank to keep)"></div>
  <div><label>Model</label>
    <input id="sModel" placeholder="e.g. z-ai/glm-5.3-flash"></div>
  <div><label>Approval mode</label>
    <select id="sMode" style="width:100%;background:var(--soft);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:9px 11px;font:inherit">
      <option value="manual">manual — ask every time</option>
      <option value="smart">smart — only risky commands</option>
      <option value="off">off — never ask</option>
    </select></div>
  <div><label>Auto-approved commands (one pattern per line, e.g. git status*)</label>
    <textarea id="sAllow" rows="4" style="width:100%;background:var(--soft);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:9px 11px;font:inherit;font-family:monospace"></textarea></div>
  <div id="settingsMsg"></div>
  <div class="row"><button type="button" class="secondary" onclick="closeSettings()">Cancel</button>
    <button type="button" onclick="saveSettings()">Save</button></div>
</div></div>
<div id="mmodal" class="modal"><div class="card">
  <h2>Mods</h2>
  <div id="modsList"></div>
  <div id="modsMsg" style="color:var(--dim);font-size:13px;margin-top:6px"></div>
  <div class="row"><button type="button" class="secondary" onclick="closeMods()">Close</button></div>
</div></div>
<script>
const log=document.getElementById('log'),t=document.getElementById('t'),f=document.getElementById('f');
let busy=false;
async function openMods(){
  document.getElementById('mmodal').classList.add('open');
  document.getElementById('modsMsg').textContent='';
  const list=document.getElementById('modsList');
  try{
    const r=await fetch('/mods');const d=await r.json();
    list.innerHTML=d.mods.length?'':'<div><small>No mods found. Drop .py files in ~/.untitled/mods/ (hooks: on_message, on_reply).</small></div>';
    for(const m of d.mods){
      const row=document.createElement('div');
      const cb=document.createElement('input');cb.type='checkbox';cb.checked=m.enabled;
      cb.onchange=()=>toggleMod(m.name,cb.checked,row);
      const name=document.createElement('span');name.textContent=m.name;
      const desc=document.createElement('small');desc.textContent=m.description||'';
      row.append(cb,name,desc);list.appendChild(row);
    }
  }catch(e){document.getElementById('modsMsg').textContent='load failed: '+e;}
}
function closeMods(){document.getElementById('mmodal').classList.remove('open');}
async function toggleMod(name,on,row){
  const msgEl=document.getElementById('modsMsg');msgEl.textContent='saving…';
  try{
    const r=await fetch('/mods',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:name,enabled:on})});
    const d=await r.json();
    msgEl.textContent=d.error?('error: '+d.error):(on?'enabled.':'disabled.');
  }catch(e){msgEl.textContent='error: '+e;}
}
const st=document.getElementById('st');
function poll(){fetch('/health').then(r=>r.json()).then(h=>{st.className=h.state;st.title='engine: '+h.state+(h.detail?' — '+h.detail:'')}).catch(()=>{st.className='degraded';st.title='engine unreachable'})}
poll();setInterval(poll,5000);
async function openSettings(){
  document.getElementById('modal').classList.add('open');
  document.getElementById('settingsMsg').textContent='';
  try{
    const r=await fetch('/settings');const s=await r.json();
    document.getElementById('sModel').value=s.model||'';
    if(s.mode)document.getElementById('sMode').value=s.mode;
    if('allowlist' in s)document.getElementById('sAllow').value=(s.allowlist||[]).join(String.fromCharCode(10));
    document.getElementById('sKey').value='';document.getElementById('sKey').placeholder=
      s.api_key_set?'Saved — leave blank to keep':'sk-or-…';
  }catch(e){document.getElementById('settingsMsg').textContent='load failed: '+e;}
}
function closeSettings(){document.getElementById('modal').classList.remove('open');}
async function saveSettings(){
  const msgEl=document.getElementById('settingsMsg');msgEl.textContent='saving…';
  try{
    const r=await fetch('/settings',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({api_key:document.getElementById('sKey').value.trim(),
                           model:document.getElementById('sModel').value.trim()})});
    const d=await r.json();
    if(d.error){msgEl.textContent='error: '+d.error;return;}
    msgEl.textContent='saved.';setTimeout(closeSettings,600);
  }catch(e){msgEl.textContent='error: '+e;}
}
function add(cls,text){const d=document.createElement('div');d.className='m '+cls;
  d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
f.onsubmit=async e=>{
  e.preventDefault();
  if(busy||!t.value.trim())return;
  busy=true;f.querySelector('button').disabled=true;
  add('me',t.value);
  const bubble=add('Untitled pending',''),msg=t.value;t.value='';
  try{
    const r=await fetch('/send',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    const data=await r.json();
    bubble.textContent=data.reply||('error: '+(data.error||r.status));
  }catch(err){bubble.textContent='error: '+err;}
  bubble.classList.remove('pending');
  busy=false;f.querySelector('button').disabled=false;t.focus();
};
</script></body></html>"""


_turn_lock = threading.Lock()


_engine_state = {"state": "starting", "detail": ""}  # updated by _prewarm


def run_turn(message: str) -> str:
    """One chat turn through the engine, in-process via the gateway.

    The gateway daemon stays warm between turns (started once, reused), so a
    turn is one WebSocket round trip — not a fresh interpreter per message.
    Falls back to the subprocess one-shot path if the engine cannot load.
    """
    try:
        import contextlib
        import io

        from hermes_cli._parser import build_top_level_parser
        from hermes_cli.gateway_chat import launch_from_args
    except Exception as exc:  # engine deps missing where this server runs
        return _run_turn_subprocess(message, f"engine import failed ({exc}); used one-shot fallback")

    # Load keys saved via the Settings UI (HERMES_HOME/.env) before the engine's
    # first-run guard runs — it checks os.environ, not the .env file.
    _env_path = os.path.join(_hermes_home(), ".env")
    if os.path.isfile(_env_path):
        for _line in open(_env_path):
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

    # The engine's first-run guard calls sys.exit(1) when it thinks no key is
    # configured — a SystemExit must not kill the request thread silently.
    parser, _subparsers, _chat = build_top_level_parser()

    args = parser.parse_args(["-z", message])
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), _turn_lock:
            code = launch_from_args(args)
    except SystemExit as exc:
        return ("error: engine not configured yet — open ⚙ Settings and paste your OpenRouter API key")
    except Exception as exc:
        return f"error: engine turn failed ({exc})"
    reply = out.getvalue().strip()
    if code == 0 and reply:
        return reply
    detail = err.getvalue().strip().splitlines()
    return reply or (f"error: exit {code}" + (f" — {detail[-1]}" if detail else ""))


def _run_turn_subprocess(message: str, note: str) -> str:
    """Fallback: the original one-shot spawn (slow, only if in-process import fails)."""
    _venv_py = os.path.join(ROOT, ".venv", "bin", "python")
    py = _venv_py if os.path.isfile(_venv_py) else sys.executable
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    try:
        result = subprocess.run(
            [py, "-m", "hermes_cli.main", "-z", message],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=600,
        )
    except Exception as exc:
        return f"error: {exc}"
    reply = result.stdout.strip()
    if result.returncode == 0 and reply:
        return reply
    detail = (result.stderr or "").strip().splitlines()
    return reply or (f"error: exit {result.returncode}" + (f" — {detail[-1]}" if detail else ""))


_SETTINGS_KEY = "openrouter_api_key"


def _hermes_home() -> str:
    return os.environ.get("HERMES_HOME") or os.path.join(os.path.expanduser("~"), ".untitled")


def _load_saved_env() -> None:
    """Copy HERMES_HOME/.env keys into os.environ (once) for the engine."""
    path = os.path.join(_hermes_home(), ".env")
    if not os.path.isfile(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _config_path() -> str:
    return os.path.join(_hermes_home(), "config.yaml")


def _read_model() -> str:
    try:
        with open(_config_path()) as fh:
            in_model = False
            for line in fh:
                s = line.strip()
                indented = line[:1] in (" ", "\t")
                if s == "model:":
                    in_model = True
                elif in_model and s and not indented and not s.startswith(("#", "-")):
                    break
                elif in_model and s.startswith("default:"):
                    return s.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def _write_model(model: str) -> None:
    path = _config_path()
    try:
        lines = open(path).read().splitlines(True)
    except OSError:
        lines = []
    out, in_model, replaced = [], False, False
    for line in lines:
        s = line.strip()
        indented = line[:1] in (" ", "\t")
        if s == "model:":
            in_model = True
            out.append(line)
            continue
        if in_model and s.startswith("default:") and indented and not replaced:
            out.append(f"  default: {model}\n")
            replaced = True
            continue
        if in_model and s and not indented and not s.startswith(("#", "-")):
            in_model = False
            if not replaced:
                out.append(f"  default: {model}\n")
                replaced = True
        out.append(line)
    if not replaced:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        out = lines + ["model:\n", f"  default: {model}\n"]
    with open(path, "w") as fh:
        fh.writelines(out)


def _write_env_key(api_key: str) -> None:
    """Persist the key where the engine picks it up (HERMES_HOME/.env)."""
    path = os.path.join(_hermes_home(), ".env")
    try:
        lines = [l for l in open(path).read().splitlines(True)
                 if not l.startswith("OPENROUTER_API_KEY=")]
    except OSError:
        lines = []
    lines.append(f"OPENROUTER_API_KEY={api_key}\n")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.writelines(lines)


def _settings_get(self) -> None:
    try:
        from tools.secret_store import get as secret_get
        key_set = bool(secret_get(_SETTINGS_KEY))
    except Exception:
        key_set = False
    if not key_set:
        env_key = os.environ.get("OPENROUTER_API_KEY")
        env_path = os.path.join(_hermes_home(), ".env")
        if not env_key and os.path.isfile(env_path):
            try:
                for line in open(env_path):
                    if line.startswith("OPENROUTER_API_KEY="):
                        env_key = line.split("=", 1)[1].strip()
            except OSError:
                pass
        key_set = bool(env_key)
    body = json.dumps({"api_key_set": key_set, "model": _read_model(), **_approvals_get()}).encode()
    self._send(200, body, "application/json")


def _settings_post(self, payload: dict) -> None:
    api_key = (payload.get("api_key") or "").strip()
    model = (payload.get("model") or "").strip()
    has_appr = bool((payload.get("approval_mode") or "").strip()) or "allowlist" in payload
    if not api_key and not model and not has_appr:
        return self._send(400, b'{"error":"nothing to save"}', "application/json")
    if api_key:
        _write_env_key(api_key)
        os.environ["OPENROUTER_API_KEY"] = api_key
        try:
            from tools.secret_store import set as secret_set
            secret_set(_SETTINGS_KEY, api_key)
        except Exception:
            pass  # .env copy already persisted; vault is best-effort here
    if model:
        _write_model(model)
    err = _approvals_post({"approval_mode": payload.get("approval_mode", ""),
                           "allowlist": payload.get("allowlist")} if "allowlist" in payload
                          else {"approval_mode": payload.get("approval_mode", "")})
    if err:
        return self._send(400, json.dumps({"error": err}).encode(), "application/json")
    self._send(200, b'{"ok":true}', "application/json")


def _approvals_get() -> dict:
    try:
        from hermes_cli.config import load_config_readonly
        cfg = load_config_readonly() or {}
    except Exception:
        try:
            import yaml
            with open(_config_path()) as fh:
                cfg = yaml.safe_load(fh) or {}
        except Exception:
            cfg = {}
    al = cfg.get("command_allowlist") or []
    if isinstance(al, str):
        al = [al]
    mode = cfg.get("approvals", {}).get("mode", "manual") if isinstance(cfg.get("approvals"), dict) else "manual"
    return {"mode": str(mode), "allowlist": [str(x) for x in al]}


def _approvals_post(payload: dict) -> Optional[str]:
    """Apply approval-mode / allowlist edits. Returns an error string or None."""
    try:
        from hermes_cli.config import load_config, save_config
        cfg = load_config()
    except Exception as exc:
        return f"config load failed: {exc}"
    mode = (payload.get("approval_mode") or "").strip().lower()
    if mode:
        if mode not in ("manual", "smart", "off"):
            return "approval mode must be manual, smart or off"
        ap = cfg.get("approvals")
        if not isinstance(ap, dict):
            ap = {}
            cfg["approvals"] = ap
        ap["mode"] = mode
    if "allowlist" in payload:
        entries = [l.strip() for l in str(payload.get("allowlist") or "").splitlines() if l.strip()]
        cfg["command_allowlist"] = entries
    try:
        save_config(cfg)
    except Exception as exc:
        return f"config save failed: {exc}"
    return None


def _mods_dir() -> str:
    path = os.path.join(_hermes_home(), "mods")
    os.makedirs(path, exist_ok=True)
    return path


def _mods_state_path() -> str:
    return os.path.join(_mods_dir(), "mods.json")


def _mods_enabled() -> set:
    try:
        data = json.load(open(_mods_state_path()))
        return {str(x) for x in data.get("enabled", [])}
    except Exception:
        return set()


def _mods_set_enabled(enabled: list) -> None:
    fd = os.open(_mods_state_path(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"enabled": enabled}, fh, indent=2)


def _list_mods() -> list:
    """Scan the mods dir: [{name, description, enabled}]."""
    try:
        files = sorted(f for f in os.listdir(_mods_dir()) if f.endswith(".py"))
    except OSError:
        files = []
    enabled = _mods_enabled()
    mods = []
    for name in files:
        desc = ""
        try:
            for line in open(os.path.join(_mods_dir(), name)):
                s = line.strip()
                if s.startswith("DESCRIPTION") and "=" in s:
                    desc = s.split("=", 1)[1].strip().strip("\"'")
                    break
                if s and not s.startswith(("#", '"""', "'''", "from ", "import ")):
                    break
        except OSError:
            pass
        mods.append({"name": name, "description": desc, "enabled": name in enabled})
    return mods


_MOD_ATTR = "hook_cache"


def _run_hook(hook: str, text: str) -> str:
    """Apply each enabled mod's hook to text. A mod that fails is skipped."""
    import importlib.util

    current = text
    for mod in _list_mods():
        if not mod["enabled"]:
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"aa_mod_{hook}_{mod['name']}",
                                                          os.path.join(_mods_dir(), mod["name"]))
            if spec is None or spec.loader is None:
                continue
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            fn = getattr(m, hook, None)
            if callable(fn):
                out = fn(current)
                if isinstance(out, str):
                    current = out
        except Exception as exc:
            print(f"mod {mod['name']} {hook} failed: {exc}", flush=True)
    return current


def _mods_post(payload: dict) -> Optional[str]:
    name = str(payload.get("name") or "")
    if os.path.basename(name) != name or not name.endswith(".py"):
        return "invalid mod name"
    if not os.path.isfile(os.path.join(_mods_dir(), name)):
        return "no such mod"
    enabled = [n for n in _mods_enabled() if n != name]
    if payload.get("enabled"):
        enabled.append(name)
    try:
        _mods_set_enabled(sorted(set(enabled)))
    except Exception as exc:
        return f"save failed: {exc}"
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence request noise
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, json.dumps(_engine_state).encode(), "application/json")
        if self.path == "/settings":
            return _settings_get(self)
        if self.path == "/mods":
            return self._send(200, json.dumps({"mods": _list_mods()}).encode(), "application/json")
        self._send(200, PAGE.encode(), "text/html; charset=utf-8")

    def do_POST(self):
        if self.path == "/settings":
            try:
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._send(400, b'{"error":"bad request"}', "application/json")
            return _settings_post(self, payload)
        if self.path == "/mods":
            try:
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._send(400, b'{"error":"bad request"}', "application/json")
            err = _mods_post(payload)
            if err:
                return self._send(400, json.dumps({"error": err}).encode(), "application/json")
            return self._send(200, b'{"ok":true}', "application/json")
        if self.path != "/send":
            return self._send(404, b'{"error":"not found"}', "application/json")
        try:
            n = int(self.headers.get("Content-Length", 0))
            msg = json.loads(self.rfile.read(n) or b"{}").get("message", "")
        except Exception:
            return self._send(400, b'{"error":"bad request"}', "application/json")
        if not msg.strip():
            return self._send(400, b'{"error":"empty message"}', "application/json")
        # One worker at a time: a turn holds the agent lock anyway.
        msg = _run_hook("on_message", msg)
        out = _run_hook("on_reply", run_turn(msg))
        body = json.dumps({"reply": out.strip() or "(no output)"}).encode()
        self._send(200, body, "application/json")


def _prewarm():
    """Start the engine imports + gateway daemon in the background at boot, so
    the first real message pays only model latency, not 40s of cold start."""
    def go():
        _engine_state["state"] = "warming"
        # Load keys saved via the Settings UI so the gateway daemon sees them.
        try:
            _load_saved_env()
        except Exception:
            pass
        try:
            from hermes_cli._parser import build_top_level_parser  # noqa: F401  (imports engine)
            from hermes_cli.gateway_runtime import ensure_gateway_runtime
            from hermes_constants import get_hermes_home
            ensure_gateway_runtime(get_hermes_home(), idle_exit=True)
            _engine_state.update(state="ready", detail="gateway warm")
            print("Untitled desktop engine warmed", flush=True)
        except Exception as exc:
            _engine_state.update(state="degraded", detail=str(exc))
            print(f"Untitled desktop prewarm skipped: {exc}", flush=True)
    threading.Thread(target=go, daemon=True).start()


def main():
    ap = argparse.ArgumentParser(description="Untitled Desktop — lean local web UI")
    ap.add_argument("--port", type=int, default=0, help="port (default: pick free)")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = ap.parse_args()
    _load_saved_env()
    _prewarm()

    port = args.port
    srv = ThreadingHTTPServer(("127.0.0.1", port if port else 0), Handler)
    port = srv.server_address[1]
    url = f"http://127.0.0.1:{port}"
    print(f"Untitled desktop listening on {url}", flush=True)
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
