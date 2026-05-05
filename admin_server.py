from fastapi import FastAPI, Header, Request  # type: ignore
from fastapi.responses import HTMLResponse, StreamingResponse  # type: ignore
from pydantic import BaseModel  # type: ignore
import httpx  # type: ignore
import json, os, asyncio
from collections import deque
from datetime import datetime

app = FastAPI(title="ZeroTrace Central Command 🌐")

AGENT_URL = "http://127.0.0.1:8000"
API_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_key.json")
DESTRUCTION_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "destruction_log.json")

# In-memory log queue for SSE streaming (shared across requests)
_log_buffer: deque = deque(maxlen=500)
_log_buffer.append(f"[{datetime.now().isoformat()}] ZeroTrace Central Command v3.0 started.")
_log_buffer.append(f"[{datetime.now().isoformat()}] Admin server online. Awaiting commands.")

def _push_log(msg: str):
    _log_buffer.append(f"[{datetime.now().isoformat()}] {msg}")

def _get_agent_key() -> str:
    try:
        with open(API_KEY_FILE, "r") as f:
            return json.load(f)["api_key"]
    except Exception:
        return ""

class WipePayload(BaseModel):
    target_path: str
    standard: str = "DoD 5220.22-M (3-pass)"

# ---- SERVE DASHBOARD ----
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

# ---- AGENT KEY ----
@app.get("/agent-key")
async def get_key():
    return {"api_key": _get_agent_key()}

# ---- AGENT STATUS (proxy) ----
@app.get("/agent-status")
async def agent_status():
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{AGENT_URL}/status")
            data = r.json()
            _push_log(f"Agent status polled — uptime {data.get('uptime_seconds', '?')}s")
            return data
        except Exception as e:
            _push_log(f"[WARNING] Agent unreachable: {e}")
            return {"status": "offline", "error": str(e)}

# ---- DESTRUCTION HISTORY ----
@app.get("/logs")
async def get_logs():
    try:
        if not os.path.exists(DESTRUCTION_LOG):
            return {"logs": [], "count": 0}
        with open(DESTRUCTION_LOG, "r") as f:
            logs = json.load(f)
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        return {"logs": [], "count": 0, "error": str(e)}

# ---- SSE LOG STREAM ----
@app.get("/stream-logs")
async def stream_logs():
    """Server-Sent Events endpoint streaming central command log lines."""
    async def generator():
        sent = 0
        for _ in range(3600):  # stream for up to 1 hour
            await asyncio.sleep(1)
            current = list(_log_buffer)
            new_lines = current[sent:]
            sent = len(current)
            for line in new_lines:
                payload = json.dumps({"log": line})
                yield f"data: {payload}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ---- EXECUTE REMOTE WIPE ----
@app.post("/execute-remote-wipe")
async def execute_remote_wipe(payload: WipePayload, x_api_key: str = Header(None)):
    key = x_api_key or _get_agent_key()
    _push_log(f"WIPE COMMAND → {payload.target_path} [{payload.standard}]")
    print(f"\n[ADMIN] Remote wipe → {payload.target_path} [{payload.standard}]")
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            response = await client.post(
                f"{AGENT_URL}/wipe",
                json={"target_path": payload.target_path, "standard": payload.standard},
                headers={"x-api-key": key}
            )
            data = response.json()
            if data.get("status") == "success":
                cert = data.get("certificate", {})
                _push_log(f"WIPE SUCCESS — {cert.get('files_destroyed', 0)} files destroyed. CERT: {cert.get('certificate_id', '?')}")
            else:
                _push_log(f"WIPE FAILED — {data.get('message', 'Unknown error')}")
            return data
        except Exception as e:
            _push_log(f"[CRITICAL] Agent connection failed: {e}")
            print(f"[ADMIN ERROR] {e}")
            return {"status": "error", "message": f"Could not connect to Agent: {str(e)}"}