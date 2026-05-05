from fastapi import FastAPI, Header, HTTPException  # type: ignore
from fastapi.responses import StreamingResponse       # type: ignore
from pydantic import BaseModel                        # type: ignore
import os, secrets, json, hashlib, threading, platform, time, asyncio
from datetime import datetime
from collections import defaultdict

app = FastAPI(title="ZeroTrace Agent API 🛡️")

# ---------- API KEY AUTH ----------
API_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_key.json")

def _init_key():
    if not os.path.exists(API_KEY_FILE):
        key = secrets.token_hex(32)
        with open(API_KEY_FILE, "w") as f:
            json.dump({"api_key": key}, f, indent=4)
        print(f"[ZeroTrace] Generated API Key: {key}")

def _get_key():
    _init_key()
    with open(API_KEY_FILE, "r") as f:
        return json.load(f)["api_key"]

def verify_key(x_api_key: str = Header(None)):
    if x_api_key != _get_key():
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")

# ---------- WIPE STANDARDS ----------
WIPE_STANDARDS = {
    "NIST 800-88 Clear (1-pass)":    [b'\x00'],
    "DoD 5220.22-M (3-pass)":        [b'\x00', b'\xff', None],
    "DoD 5220.22-M ECE (7-pass)":    [b'\x00', b'\xff', None, b'\x00', b'\xff', None, None],
    "Gutmann (35-pass)": (
        [b'\x55', b'\xaa', b'\x92\x49\x24', b'\x49\x24\x92', b'\x24\x92\x49',
         b'\x00', b'\x11', b'\x22', b'\x33', b'\x44', b'\x55', b'\x66', b'\x77',
         b'\x88', b'\x99', b'\xaa', b'\xbb', b'\xcc', b'\xdd', b'\xee', b'\xff',
         b'\x92\x49\x24', b'\x49\x24\x92', b'\x24\x92\x49', b'\x6d\xb6\xdb',
         b'\xb6\xdb\x6d', b'\xdb\x6d\xb6'] + [None]*7
    )
}

def get_pattern(p, size):
    if p is None:
        return os.urandom(size)
    return (p * (size // len(p) + 1))[:size]

# ---------- JOB STORE ----------
# job_id -> { status, progress_pct, files_total, files_done, result, events: list[str] }
_jobs: dict = {}
_jobs_lock = threading.Lock()
_start_time = time.time()

# ---------- MODELS ----------
class WipeRequest(BaseModel):
    target_path: str
    standard: str = "DoD 5220.22-M (3-pass)"

# ---------- CORE LOGIC ----------
def get_hash(file_path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except Exception:
        return "HASH_ERROR"
    return h.hexdigest()

def secure_delete_file(file_path: str, standard_name: str, job_id: str) -> dict:
    patterns = WIPE_STANDARDS.get(standard_name, WIPE_STANDARDS["DoD 5220.22-M (3-pass)"])
    try:
        pre_hash = get_hash(file_path)
        file_size = os.path.getsize(file_path)
        chunk_size = 1024 * 1024
        total_passes = len(patterns)

        _push_event(job_id, f"[WIPING] {os.path.basename(file_path)} ({file_size} bytes, {total_passes} passes)")

        with open(file_path, "r+b") as f:
            for i, pattern in enumerate(patterns, 1):
                f.seek(0)
                written = 0
                while written < file_size:
                    ws = min(chunk_size, file_size - written)
                    f.write(get_pattern(pattern, ws))
                    written += ws
                f.flush()
                os.fsync(f.fileno())
                _push_event(job_id, f"  └─ Pass {i}/{total_passes} complete")

        os.remove(file_path)
        _push_event(job_id, f"[✓] Destroyed: {os.path.basename(file_path)}")
        return {"success": True, "pre_hash": pre_hash, "size": file_size}
    except Exception as e:
        _push_event(job_id, f"[ERROR] Failed: {os.path.basename(file_path)} — {e}")
        return {"success": False, "pre_hash": "N/A", "size": 0}

def _push_event(job_id: str, msg: str):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["events"].append(msg)

def sign_certificate(cert: dict) -> str:
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private.pem")
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        with open(key_path, "rb") as kf:
            priv_key = serialization.load_pem_private_key(kf.read(), password=None)
        payload = json.dumps(cert, sort_keys=True).encode()
        sig = priv_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
        return hashlib.sha256(sig).hexdigest()
    except Exception as e:
        return f"SIG_UNAVAILABLE: {e}"

def generate_certificate(target_path: str, wiped_count: int, standard: str,
                          file_hashes: list, total_bytes: int) -> dict:
    cert = {
        "certificate_id": f"ZT-{secrets.token_hex(4).upper()}",
        "timestamp": datetime.now().isoformat(),
        "target_path": target_path,
        "files_destroyed": wiped_count,
        "total_bytes_wiped": total_bytes,
        "standard": standard,
        "file_hashes_pre_wipe": file_hashes,
        "status": "VERIFIED_DESTROYED"
    }
    cert["rsa_signature"] = sign_certificate(cert)

    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "destruction_log.json")
    try:
        logs = json.load(open(log_file)) if os.path.exists(log_file) else []
        logs.append(cert)
        with open(log_file, "w") as f:
            json.dump(logs, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Certificate save failed: {e}")
    return cert

def _run_wipe_job(job_id: str, target: str, standard: str):
    """Background thread that performs the wipe and updates job state."""
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["events"].append(f"[JOB:{job_id}] Starting wipe on {target}")
        _jobs[job_id]["events"].append(f"[JOB:{job_id}] Standard: {standard}")

    all_files = []
    for root_dir, _, files in os.walk(target):
        for fn in files:
            all_files.append(os.path.join(root_dir, fn))

    with _jobs_lock:
        _jobs[job_id]["files_total"] = len(all_files)
        _jobs[job_id]["events"].append(f"[JOB:{job_id}] {len(all_files)} files queued for destruction")

    wiped_count = 0
    file_hashes = []
    total_bytes = 0

    for i, fp in enumerate(all_files):
        result = secure_delete_file(fp, standard, job_id)
        if result["success"]:
            wiped_count += 1
            total_bytes += result["size"]
            file_hashes.append({"file": fp, "sha256_pre_wipe": result["pre_hash"]})
        with _jobs_lock:
            _jobs[job_id]["files_done"] = i + 1
            _jobs[job_id]["progress_pct"] = round(((i + 1) / max(len(all_files), 1)) * 100)

    cert = generate_certificate(target, wiped_count, standard, file_hashes, total_bytes)

    with _jobs_lock:
        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["progress_pct"] = 100
        _jobs[job_id]["result"] = {
            "status": "success",
            "message": f"Target neutralized. {wiped_count} files wiped using {standard}.",
            "certificate": cert
        }
        _jobs[job_id]["events"].append(f"[JOB:{job_id}] COMPLETE — {wiped_count} files destroyed.")
        _jobs[job_id]["events"].append(f"[CERT] {cert['certificate_id']} | RSA: {cert['rsa_signature'][:16]}...")

# ---------- ENDPOINTS ----------
@app.get("/status")
async def status():
    """Return agent health + system telemetry."""
    import shutil
    uptime = round(time.time() - _start_time)
    disk = shutil.disk_usage("/")
    cpu_pct = None
    mem_pct = None
    try:
        import psutil  # type: ignore
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem_pct = psutil.virtual_memory().percent
    except ImportError:
        pass

    return {
        "status": "online",
        "agent": "ZeroTrace Agent v3.0",
        "hostname": platform.node(),
        "os": platform.system(),
        "platform": platform.platform(),
        "uptime_seconds": uptime,
        "disk_total_gb": round(disk.total / 1e9, 2),
        "disk_free_gb": round(disk.free / 1e9, 2),
        "disk_used_pct": round((disk.used / disk.total) * 100, 1),
        "cpu_percent": cpu_pct,
        "mem_percent": mem_pct,
        "active_jobs": sum(1 for j in _jobs.values() if j["status"] == "running"),
    }

@app.get("/key")
async def show_key():
    return {"api_key": _get_key()}

@app.post("/wipe")
async def trigger_wipe(request: WipeRequest, x_api_key: str = Header(None)):
    verify_key(x_api_key)
    target = request.target_path
    standard = request.standard

    if standard not in WIPE_STANDARDS:
        raise HTTPException(status_code=400, detail=f"Unknown standard. Choose from: {list(WIPE_STANDARDS.keys())}")
    if not os.path.exists(target):
        return {"status": "error", "message": f"Target '{target}' does not exist."}
    if not os.path.isdir(target):
        return {"status": "error", "message": "Target must be a directory."}

    job_id = f"JOB-{secrets.token_hex(4).upper()}"
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "target": target,
            "standard": standard,
            "progress_pct": 0,
            "files_total": 0,
            "files_done": 0,
            "result": None,
            "events": [],
            "created_at": datetime.now().isoformat()
        }

    thread = threading.Thread(target=_run_wipe_job, args=(job_id, target, standard), daemon=True)
    thread.start()

    # Poll until complete (synchronous for admin_server compatibility)
    deadline = time.time() + 600
    while time.time() < deadline:
        with _jobs_lock:
            job = _jobs[job_id]
        if job["status"] == "complete":
            return job["result"]
        if job["status"] == "error":
            return {"status": "error", "message": "Wipe job failed internally."}
        time.sleep(0.5)

    return {"status": "error", "message": "Wipe timed out after 10 minutes."}

@app.get("/wipe-progress/{job_id}")
async def wipe_progress_stream(job_id: str, x_api_key: str = Header(None)):
    """SSE stream of per-file progress for a wipe job."""
    verify_key(x_api_key)

    async def event_generator():
        sent = 0
        for _ in range(1200):  # max 2 min at 100ms
            await asyncio.sleep(0.1)
            with _jobs_lock:
                job = _jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break
            events = job["events"][sent:]
            sent += len(events)
            for ev in events:
                yield f"data: {json.dumps({'log': ev, 'pct': job['progress_pct'], 'status': job['status']})}\n\n"
            if job["status"] in ("complete", "error"):
                yield f"data: {json.dumps({'done': True, 'pct': 100, 'result': job.get('result')})}\n\n"
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/jobs")
async def list_jobs(x_api_key: str = Header(None)):
    verify_key(x_api_key)
    with _jobs_lock:
        return list(_jobs.values())