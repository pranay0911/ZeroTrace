from fastapi import FastAPI # type: ignore
from fastapi.responses import HTMLResponse # type: ignore
import httpx  # type: ignore

app = FastAPI(title="ZeroTrace Central Command 🌐")

AGENT_URL = "http://127.0.0.1:8000"

# --- NEW: Serve the Dashboard UI ---
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/execute-remote-wipe")
async def execute_remote_wipe(target_folder: str):
    print(f"\n[ADMIN] Initiating remote wipe protocol...")
    print(f"[ADMIN] Target: {target_folder}")
    
    payload = {"target_path": target_folder}
    
    # Using the 300-second timeout we added earlier!
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(f"{AGENT_URL}/wipe", json=payload)
            return response.json()
        except Exception as e:
            print(f"[ADMIN ERROR] Connection failed: {str(e)}")
            return {"status": "error", "message": "Could not connect to Agent. Is it running?"}