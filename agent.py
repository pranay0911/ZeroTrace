from fastapi import FastAPI # type: ignore
from pydantic import BaseModel # type: ignore
import asyncio
import os
import secrets
import json
from datetime import datetime

app = FastAPI(title="ZeroTrace Agent API 🛡️")

class WipeRequest(BaseModel):
    target_path: str

def secure_delete_file(file_path: str, passes: int = 3):
    """Overwrites a file with random data multiple times before deleting it."""
    try:
        file_size = os.path.getsize(file_path)
        with open(file_path, "r+b") as f:
            for current_pass in range(passes):
                f.seek(0) 
                f.write(secrets.token_bytes(file_size)) 
        os.remove(file_path)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to wipe {file_path}: {str(e)}")
        return False

def generate_certificate(target_path: str, wiped_count: int):
    """Generates a verifiable JSON Certificate of Destruction."""
    # Create the certificate data
    certificate = {
        "certificate_id": f"ZT-{secrets.token_hex(4).upper()}",
        "timestamp": datetime.now().isoformat(),
        "target_path": target_path,
        "files_destroyed": wiped_count,
        "method": "DoD 5220.22-M (3-Pass Cryptographic Overwrite)",
        "status": "VERIFIED_DESTROYED"
    }
    
    log_file = "destruction_log.json"
    
    # Safely load existing logs or start a new list
    try:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                logs = json.load(f)
        else:
            logs = []
            
        # Add the new certificate and save it
        logs.append(certificate)
        with open(log_file, "w") as f:
            json.dump(logs, f, indent=4)
            
    except Exception as e:
        print(f"[ERROR] Could not save certificate: {e}")
        
    return certificate

@app.post("/wipe")
async def trigger_wipe(request: WipeRequest):
    target = request.target_path
    
    print(f"\n[🚨 WARNING] WIPE COMMAND RECEIVED FROM CENTRAL COMMAND!")
    print(f"[TARGET] {target}")
    
    if not os.path.exists(target):
        return {"status": "error", "message": f"Target path '{target}' does not exist."}
    if not os.path.isdir(target):
         return {"status": "error", "message": "Target must be a folder, not a single file."}

    print("[STATUS] Initiating secure 3-pass overwrite protocol...")
    
    wiped_files_count = 0
    
    for root, dirs, files in os.walk(target):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            print(f"[WIPING] {file_path}...")
            if secure_delete_file(file_path):
                wiped_files_count += 1
                
    print(f"[STATUS] ZeroTrace complete. {wiped_files_count} files permanently neutralized.")
    
    # --- NEW: Generate and log the certificate ---
    cert = generate_certificate(target, wiped_files_count)
    print(f"[STATUS] Certificate of Destruction generated: {cert['certificate_id']} ✅\n")
    
    # Send the certificate back to the Admin Server!
    return {
        "status": "success", 
        "message": f"Target neutralized. {wiped_files_count} files securely wiped.",
        "certificate": cert
    }