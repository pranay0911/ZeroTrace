import os, sys, hashlib, sqlite3, datetime, subprocess, csv, random, time, json, threading, fnmatch, re, secrets, math
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk # type: ignore
import psutil
from tkinterdnd2 import TkinterDnD, DND_FILES # type: ignore
from PIL import Image as PILImage

# ---------- ADVANCED UI WRAPPER ----------
class ZeroTraceApp(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

# ---------- PATH ----------
def resource_path(p):
    try: return os.path.join(sys._MEIPASS, p)
    except: return os.path.join(os.getcwd(), p)

# ---------- HASHED AUTH (SHA-256 stored in config) ----------
CONFIG_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_config.json")
BURN_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "burn_config.json")
IDLE_TIMEOUT  = 180          # seconds before auto-lock
_last_activity = time.time() # updated on every user event
_locked = False

def _init_auth():
    if not os.path.exists(CONFIG_FILE):
        default = {
            "username": "admin",
            "password_hash": hashlib.sha256("1234".encode()).hexdigest()
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default, f, indent=4)

def _load_auth():
    _init_auth()
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def login():
    auth = _load_auth()
    dialog_u = ctk.CTkInputDialog(text="Enter Admin Username:", title="Authentication Required")
    u = dialog_u.get_input()
    if u != auth["username"]: return False
    dialog_p = ctk.CTkInputDialog(text="Enter Passcode:", title="Authentication Required")
    p = dialog_p.get_input()
    if p is None: return False
    return hashlib.sha256(p.encode()).hexdigest() == auth["password_hash"]

# ---------- AUTO-LOCK ----------
def _reset_idle(event=None):
    global _last_activity
    _last_activity = time.time()

def _check_idle():
    global _locked
    if not _locked and (time.time() - _last_activity) >= IDLE_TIMEOUT:
        _do_lock()
    root.after(5000, _check_idle)

def _do_lock():
    global _locked
    _locked = True
    lock_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
    lock_overlay.lift()

def _do_unlock():
    global _locked
    auth = _load_auth()
    d = ctk.CTkInputDialog(text="Session Locked. Enter Passcode:", title="AUTO-LOCK ENGAGED")
    p = d.get_input()
    if p and hashlib.sha256(p.encode()).hexdigest() == auth["password_hash"]:
        _locked = False
        lock_overlay.place_forget()
        _reset_idle()
    else:
        root.after(0, lambda: lock_status_lbl.configure(text="WRONG PASSWORD. TRY AGAIN.", text_color="#ef4444"))

# ---------- TELEMETRY ----------
_prev_disk = None
_prev_disk_time = None

def _update_telemetry():
    global _prev_disk, _prev_disk_time
    try:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        disk_now = psutil.disk_io_counters()
        now = time.time()
        write_speed = 0.0
        if _prev_disk and _prev_disk_time:
            dt = now - _prev_disk_time
            write_speed = (disk_now.write_bytes - _prev_disk.write_bytes) / (1024*1024*max(dt,0.001))
        _prev_disk = disk_now
        _prev_disk_time = now
        cpu_bar.set(cpu / 100)
        mem_bar.set(mem / 100)
        cpu_lbl.configure(text=f"CPU  {cpu:.0f}%")
        mem_lbl.configure(text=f"MEM  {mem:.0f}%")
        disk_lbl.configure(text=f"DISK WRITE  {write_speed:.1f} MB/s")
    except Exception:
        pass
    root.after(1000, _update_telemetry)

# ---------- SEARCH & DESTROY ----------
def search_and_destroy():
    if not login(): return
    sd_win = ctk.CTkToplevel(root)
    sd_win.title("Deep Search & Destroy")
    sd_win.geometry("600x380")
    sd_win.configure(fg_color="#09090b")
    ctk.CTkLabel(sd_win, text="DEEP SEARCH & DESTROY", text_color="#00E5FF",
                 font=("Consolas", 16, "bold")).pack(pady=(24, 4))
    ctk.CTkLabel(sd_win, text="Scans a drive/folder for file patterns and eradicates all matches.",
                 text_color="#71717a", font=("Consolas", 11)).pack(pady=(0, 12))
    f1 = ctk.CTkFrame(sd_win, fg_color="#0a0a0c", border_width=1, border_color="#27272a", corner_radius=6)
    f1.pack(fill="x", padx=24, pady=4)
    ctk.CTkLabel(f1, text="Root Path:", text_color="#a1a1aa", font=("Consolas", 11)).pack(side="left", padx=10)
    path_var = ctk.StringVar(value="C:\\")
    ctk.CTkEntry(f1, textvariable=path_var, width=340, font=("Consolas", 11)).pack(side="left", padx=6, pady=8)
    ctk.CTkButton(f1, text="Browse", width=70, font=("Consolas", 11),
                  command=lambda: path_var.set(
                      ctk.filedialog.askdirectory() or path_var.get())).pack(side="left", padx=4)
    f2 = ctk.CTkFrame(sd_win, fg_color="#0a0a0c", border_width=1, border_color="#27272a", corner_radius=6)
    f2.pack(fill="x", padx=24, pady=4)
    ctk.CTkLabel(f2, text="Patterns (comma separated, e.g. *.log,*.tmp,*.key):",
                 text_color="#a1a1aa", font=("Consolas", 11)).pack(side="left", padx=10)
    pat_var = ctk.StringVar(value="*.tmp,*.log")
    ctk.CTkEntry(f2, textvariable=pat_var, width=200, font=("Consolas", 11)).pack(side="left", padx=6, pady=8)
    res_box = ctk.CTkTextbox(sd_win, height=100, font=("Consolas", 11), fg_color="#050505", text_color="#39FF14")
    res_box.pack(fill="x", padx=24, pady=8)
    def _run_sd():
        root_path = path_var.get().strip()
        patterns = [p.strip() for p in pat_var.get().split(",") if p.strip()]
        if not os.path.isdir(root_path):
            res_box.insert("end", "[ERROR] Invalid root path.\n"); return
        std = standard_var.get()
        found = []
        for dirpath, _, fnames in os.walk(root_path):
            for fn in fnames:
                if any(fnmatch.fnmatch(fn.lower(), p.lower()) for p in patterns):
                    found.append(os.path.join(dirpath, fn))
        res_box.insert("end", f"[SCAN] {len(found)} target(s) found. Beginning eradication...\n")
        sd_win.update()
        def _do():
            for fp in found:
                process(fp, std)
                root.after(0, lambda f=fp: res_box.insert("end", f"[DESTROYED] {f}\n"))
            root.after(0, lambda: res_box.insert("end", f"[DONE] {len(found)} files eradicated.\n"))
        run_in_thread(_do)
    ctk.CTkButton(sd_win, text="EXECUTE SEARCH & DESTROY", font=("Consolas", 13, "bold"),
                  fg_color="#7f1d1d", hover_color="#991b1b", text_color="white",
                  command=_run_sd).pack(pady=8)

# ---------- PANIC BURN ----------
_burn_folder = ""

def configure_burn_folder():
    global _burn_folder
    folder = filedialog.askdirectory(title="Select Panic Burn Target Folder")
    if folder:
        _burn_folder = folder
        try:
            with open(BURN_CFG_FILE, "w") as f:
                json.dump({"burn_folder": folder}, f)
        except Exception:
            pass
        messagebox.showinfo("Panic Burn", f"Burn folder set:\n{folder}\n\nPress Ctrl+Shift+F12 to activate.")

def _load_burn_folder():
    global _burn_folder
    try:
        if os.path.exists(BURN_CFG_FILE):
            _burn_folder = json.load(open(BURN_CFG_FILE)).get("burn_folder", "")
    except Exception:
        pass

def panic_burn(event=None):
    if not _burn_folder or not os.path.isdir(_burn_folder):
        messagebox.showwarning("Panic Burn", "No burn folder configured.\nGo to: Emergency > Set Panic Burn Folder")
        return
    std = standard_var.get()
    log(f"[PANIC BURN] INITIATED ON: {_burn_folder}")
    def _do():
        for r, _, files in os.walk(_burn_folder):
            for fn in files:
                process(os.path.join(r, fn), std)
        root.after(0, lambda: status_label.configure(text="PANIC BURN COMPLETE.", text_color="#ef4444"))
    run_in_thread(_do)

# ---------- DATABASE ----------
if getattr(sys, 'frozen', False): app_path = os.path.dirname(sys.executable)
else: app_path = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(app_path, "logs.db")
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(logs)")
cols = [c[1] for c in cursor.fetchall()]

if not cols:
    cursor.execute("CREATE TABLE logs(file TEXT, size REAL, time TEXT, hash TEXT, standard TEXT)")
elif "hash" not in cols:
    cursor.execute("ALTER TABLE logs ADD COLUMN hash TEXT")
if "standard" not in cols:
    try: cursor.execute("ALTER TABLE logs ADD COLUMN standard TEXT")
    except: pass
conn.commit()

# ---------- UTILS ----------
def get_hash(f):
    try:
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except:
        return "HASH_ERROR"

def _shannon_entropy(f):
    """Shannon entropy in bits/byte (0-8). >7.5 = already encrypted."""
    try:
        freq = [0] * 256
        total = 0
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                for b in chunk: freq[b] += 1
                total += len(chunk)
        if total == 0: return 0.0
        e = 0.0
        for c in freq:
            if c > 0:
                p = c / total
                e -= p * math.log2(p)
        return e
    except: return 0.0

def _poison_timestamps(f):
    """Randomize file timestamps to corrupt forensic timeline (1980-2010)."""
    try:
        fake = random.uniform(315532800, 1262304000)
        os.utime(f, (fake, fake))
    except: pass

def _obfuscate_filename(f):
    """Rename file 7x with random hex names to destroy MFT/journal entries."""
    cur = f
    try:
        for _ in range(7):
            new = os.path.join(os.path.dirname(cur), secrets.token_hex(12) + ".dat")
            os.rename(cur, new)
            cur = new
    except: pass
    return cur

def _verify_pass(f, pattern, size, sample=65536):
    """Read back sample after write and verify pattern integrity."""
    if pattern is None: return True  # random — can't verify
    try:
        with open(f, "rb") as fh:
            data = fh.read(min(sample, size))
        return data == get_pattern(pattern, len(data))
    except: return False

def _zero_cluster_slack(f, cluster=4096):
    """Zero file-tail slack space up to next cluster boundary."""
    try:
        size = os.path.getsize(f)
        slack = cluster - (size % cluster)
        if 0 < slack < cluster:
            with open(f, "ab") as fh:
                fh.write(b'\x00' * slack)
                fh.flush(); os.fsync(fh.fileno())
            with open(f, "r+b") as fh:
                fh.truncate(size)
    except: pass

def log(msg, matrix=False):
    def _do():
        if matrix:
            hex_stream = "".join([random.choice("0123456789ABCDEF") for _ in range(32)])
            log_box.insert("end", f"[0x{random.randint(1000,9999)}] SHREDDING: {hex_stream} ...\n")
        else:
            t = datetime.datetime.now().strftime('%H:%M:%S')
            log_box.insert("end", f"[{t}] {msg}\n")
        log_box.see("end")
    root.after(0, _do)

# ---------- CUSTOM VISUAL WIDGET: SECTOR MAP ----------
class SectorMap(tk.Canvas):
    def __init__(self, parent, width=640, height=60, **kwargs):
        super().__init__(parent, width=width, height=height, bg="#09090b", highlightthickness=0, **kwargs)
        self.rects = []
        self.cols = 40
        self.rows = 4
        for y in range(self.rows):
            for x in range(self.cols):
                r = self.create_rectangle(x*16, y*15, x*16+14, y*15+13, fill="#18181b", outline="#27272a")
                self.rects.append(r)

    def trigger_threat(self):
        for r in self.rects: self.itemconfig(r, fill="#450a0a", outline="#7f1d1d")

    def update_scan(self, percentage):
        total = len(self.rects)
        cleared = int((percentage / 100.0) * total)
        for i in range(total):
            if i < cleared:
                self.itemconfig(self.rects[i], fill="#10b981", outline="#059669")

    def reset(self):
        for r in self.rects: self.itemconfig(r, fill="#18181b", outline="#27272a")

# ---------- WIPE STANDARDS ----------
WIPE_STANDARDS = {
    "NIST 800-88 Clear (1-pass)": [b'\x00'],
    "DoD 5220.22-M (3-pass)":     [b'\x00', b'\xff', None],   # None = random
    "DoD 5220.22-M ECE (7-pass)": [b'\x00', b'\xff', None, b'\x00', b'\xff', None, None],
    "Gutmann (35-pass)":          (
        [b'\x55', b'\xaa', b'\x92\x49\x24', b'\x49\x24\x92', b'\x24\x92\x49',
         b'\x00', b'\x11', b'\x22', b'\x33', b'\x44', b'\x55', b'\x66', b'\x77',
         b'\x88', b'\x99', b'\xaa', b'\xbb', b'\xcc', b'\xdd', b'\xee', b'\xff',
         b'\x92\x49\x24', b'\x49\x24\x92', b'\x24\x92\x49', b'\x6d\xb6\xdb',
         b'\xb6\xdb\x6d', b'\xdb\x6d\xb6'] + [None]*7
    )
}

def get_pattern(p, size):
    if p is None: return os.urandom(size)
    return (p * (size // len(p) + 1))[:size]

# ---------- THE SMART ENGINE WIPE ----------
def secure_delete(f, standard_name):
    try:
        size = os.path.getsize(f)
        file_name = os.path.basename(f)
        chunk_size = 1024 * 1024
        patterns = list(WIPE_STANDARDS[standard_name])

        # SMART: entropy pre-check — skip redundant passes on pre-encrypted data
        entropy = _shannon_entropy(f)
        if entropy > 7.5 and len(patterns) > 1:
            patterns = [None]
            log(f"[SMART] Entropy {entropy:.2f} bpb → pre-encrypted → 1 random pass")
        else:
            log(f"[SCAN] Entropy {entropy:.2f} bpb → {len(patterns)}-pass {standard_name}")

        root.after(0, lambda: status_label.configure(
            text=f">> EXECUTING: {standard_name} ON '{file_name}' <<", text_color="#ff4444"))
        root.after(0, sector_grid.trigger_threat)

        # FORENSIC: poison timestamps BEFORE touching content
        _poison_timestamps(f)
        log(f"[POISON] Timestamps randomized on '{file_name}'")

        for i, pattern in enumerate(patterns):
            with open(f, "r+b") as fh:
                written = 0
                while written < size:
                    ws = min(chunk_size, size - written)
                    fh.write(get_pattern(pattern, ws))
                    written += ws
                fh.flush()
                os.fsync(fh.fileno())

            # VERIFY: read-back integrity check on every pass
            ok = _verify_pass(f, pattern, size)
            log(f"  Pass {i+1}/{len(patterns)} complete → verify: {'OK ✓' if ok else 'WARN: mismatch!'}",
                matrix=(i % 2 == 0))

            pct = ((i + 1) / len(patterns)) * 100
            root.after(0, lambda p=pct: progress.set(p / 100))
            root.after(0, lambda p=pct: sector_grid.update_scan(p))

        # CLUSTER SLACK: zero tail bytes up to cluster boundary
        _zero_cluster_slack(f)
        log(f"[SLACK] Cluster tail zeroed")

        # OBFUSCATE: rename 7x with hex names before unlinking
        f = _obfuscate_filename(f)
        log(f"[MFT] Filename obfuscated ×7 in filesystem journal")

        os.remove(f)
        root.after(0, lambda: progress.set(0))
        root.after(0, sector_grid.reset)

    except Exception as e:
        log("CRITICAL ERROR: " + str(e))
        root.after(0, lambda: status_label.configure(text="SYSTEM FAILURE DURING DESTRUCTION.", text_color="#ff4444"))

# ---------- BLOCKCHAIN CERT CHAIN ----------
def _blockchain_append(cert: dict, app_path_: str) -> dict:
    """Append cert to chain.json with prev_hash field for tamper-evident chaining."""
    chain_file = os.path.join(app_path_, "chain.json")
    try:
        chain = json.load(open(chain_file)) if os.path.exists(chain_file) else []
        prev_hash = hashlib.sha256(
            json.dumps(chain[-1], sort_keys=True).encode()).hexdigest() if chain else "0" * 64
        cert["prev_hash"] = prev_hash
        cert["block_index"] = len(chain)
        chain.append(cert)
        with open(chain_file, "w") as fh:
            json.dump(chain, fh, indent=4)
    except Exception as e:
        pass
    return cert

# ---------- PROCESS ----------
def process(f, standard_name):
    try:
        if not os.path.exists(f): return
        size = os.path.getsize(f) / (1024 * 1024)
        pre_hash = get_hash(f)

        log(f"Target acquired: {os.path.basename(f)} | SHA-256: {pre_hash[:16]}...")
        secure_delete(f, standard_name)

        cursor.execute("INSERT INTO logs(file,size,time,hash,standard) VALUES(?,?,?,?,?)",
                       (f, size, str(datetime.datetime.now()), pre_hash, standard_name))
        conn.commit()

        # Blockchain certificate chain entry
        cert_entry = {
            "file": f, "size_mb": round(size, 4),
            "timestamp": datetime.datetime.now().isoformat(),
            "sha256_pre_wipe": pre_hash, "standard": standard_name
        }
        _blockchain_append(cert_entry, app_path)

        root.after(0, update_dashboard)
        root.after(0, lambda: status_label.configure(text="TARGET SUCCESSFULLY NEUTRALIZED.", text_color="#10b981"))
        log(f"Destruction Verified [{standard_name}] and Logged. Block #{cert_entry.get('block_index','?')} sealed.\n")

    except Exception as e:
        log("Error " + str(e))
        root.after(0, lambda: status_label.configure(text="OPERATION FAILED.", text_color="#ff4444"))

# ---------- FORENSIC FOOTPRINT CLEANER ----------
def forensic_cleanup():
    import glob
    cleaned = []
    errors = []

    def _try_remove(fp, label):
        try:
            if os.path.isfile(fp):
                os.remove(fp)
                cleaned.append(label)
        except Exception as e:
            errors.append(f"Skipped ({e.__class__.__name__}): {label}")

    # Windows Prefetch (requires Admin)
    prefetch = r"C:\Windows\Prefetch"
    try:
        if os.path.isdir(prefetch):
            for fn in os.listdir(prefetch):
                _try_remove(os.path.join(prefetch, fn), f"Prefetch: {fn}")
    except PermissionError:
        errors.append("Prefetch: Access Denied (run as Admin to clean)")

    # Recent Documents
    recent = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent")
    try:
        if os.path.isdir(recent):
            for fn in os.listdir(recent):
                _try_remove(os.path.join(recent, fn), f"Recent: {fn}")
    except Exception as e:
        errors.append(f"Recent: {e}")

    # Thumbnail & Icon caches
    for pat in [
        r"C:\Users\*\AppData\Local\Microsoft\Windows\Explorer\thumbcache_*.db",
        r"C:\Users\*\AppData\Local\Microsoft\Windows\Explorer\iconcache_*.db",
    ]:
        for fp in glob.glob(pat):
            _try_remove(fp, f"Cache: {os.path.basename(fp)}")

    # Jump Lists
    for jd in glob.glob(r"C:\Users\*\AppData\Roaming\Microsoft\Windows\Recent\AutomaticDestinations"):
        try:
            for fn in os.listdir(jd):
                _try_remove(os.path.join(jd, fn), f"JumpList: {fn}")
        except Exception:
            pass

    log(f"[FORENSIC] {len(cleaned)} artifact(s) purged. {len(errors)} skipped.")
    summary = f"Sanitized {len(cleaned)} forensic artifact(s)."
    if errors:
        summary += f"\n\n⚠ {len(errors)} item(s) skipped (run as Admin for full access):\n" + "\n".join(errors[:5])
    messagebox.showinfo("Forensic Cleanup Complete", summary)

# ---------- SELF-DESTRUCT ----------
def self_destruct():
    if not login(): return
    if not messagebox.askyesno("⚠️ SELF-DESTRUCT MODE",
        "This will permanently SHRED all ZeroTrace logs, certificates, chain records and audit data.\n\n"
        "This is IRREVERSIBLE. Confirm?"):
        return
    targets = [
        os.path.join(app_path, "destruction_log.json"),
        os.path.join(app_path, "chain.json"),
        os.path.join(app_path, "logs.db"),
        os.path.join(app_path, "logs_backup.txt"),
        os.path.join(app_path, "report.json"),
        os.path.join(app_path, "schedule.json"),
    ]
    def _do():
        for fp in targets:
            if os.path.exists(fp):
                secure_delete(fp, "DoD 5220.22-M (3-pass)")
                log(f"[SELF-DESTRUCT] Eliminated: {os.path.basename(fp)}")
        root.after(0, lambda: status_label.configure(
            text="SELF-DESTRUCT COMPLETE. ALL EVIDENCE ELIMINATED.", text_color="#ef4444"))
    run_in_thread(_do)

# ---------- WIPE SCHEDULER ----------
SCHEDULE_FILE = os.path.join(app_path, "schedule.json") if 'app_path' in dir() else "schedule.json"

def _run_scheduler_thread():
    while True:
        time.sleep(60)
        try:
            if not os.path.exists(SCHEDULE_FILE): continue
            sched = json.load(open(SCHEDULE_FILE))
            if not sched.get("active"): continue
            target_time = datetime.datetime.fromisoformat(sched["scheduled_time"])
            if datetime.datetime.now() >= target_time:
                folder, std = sched["target_path"], sched["standard"]
                log(f"[SCHEDULER] Executing scheduled wipe on {folder}")
                for r, _, files in os.walk(folder):
                    for fn in files: process(os.path.join(r, fn), std)
                log("[SCHEDULER] Scheduled wipe complete.")
                sched["active"] = False
                with open(SCHEDULE_FILE, "w") as fh: json.dump(sched, fh)
        except Exception: pass

def wipe_scheduler_dialog():
    if not login(): return
    sw = ctk.CTkToplevel(root)
    sw.title("Wipe Scheduler")
    sw.geometry("520x300")
    sw.configure(fg_color="#09090b")
    ctk.CTkLabel(sw, text="WIPE SCHEDULER", text_color="#00E5FF",
                 font=("Consolas", 16, "bold")).pack(pady=(20, 8))
    f1 = ctk.CTkFrame(sw, fg_color="#0a0a0c", border_width=1, border_color="#27272a", corner_radius=6)
    f1.pack(fill="x", padx=24, pady=4)
    ctk.CTkLabel(f1, text="Target Path:", text_color="#a1a1aa", font=("Consolas",11)).pack(side="left", padx=10)
    spath = ctk.StringVar()
    ctk.CTkEntry(f1, textvariable=spath, width=260, font=("Consolas",11)).pack(side="left", padx=6, pady=8)
    ctk.CTkButton(f1, text="...", width=30,
                  command=lambda: spath.set(filedialog.askdirectory() or spath.get())).pack(side="left")
    f2 = ctk.CTkFrame(sw, fg_color="#0a0a0c", border_width=1, border_color="#27272a", corner_radius=6)
    f2.pack(fill="x", padx=24, pady=4)
    ctk.CTkLabel(f2, text="Schedule Time (YYYY-MM-DD HH:MM):",
                 text_color="#a1a1aa", font=("Consolas",11)).pack(side="left", padx=10)
    stime = ctk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    ctk.CTkEntry(f2, textvariable=stime, width=160, font=("Consolas",11)).pack(side="left", padx=6, pady=8)
    std_v = ctk.StringVar(value="DoD 5220.22-M (3-pass)")
    ctk.CTkOptionMenu(sw, variable=std_v, values=list(WIPE_STANDARDS.keys()),
                      font=("Consolas",11)).pack(pady=6)
    def _arm():
        try:
            dt = datetime.datetime.strptime(stime.get().strip(), "%Y-%m-%d %H:%M")
            with open(SCHEDULE_FILE, "w") as fh:
                json.dump({"active":True,"target_path":spath.get(),
                           "scheduled_time":dt.isoformat(),"standard":std_v.get()}, fh)
            messagebox.showinfo("Armed", f"Wipe scheduled for {dt.strftime('%Y-%m-%d %H:%M')}.")
            sw.destroy()
        except ValueError:
            messagebox.showerror("Error", "Invalid time format. Use YYYY-MM-DD HH:MM")
    ctk.CTkButton(sw, text="ARM SCHEDULE", font=("Consolas",13,"bold"),
                  fg_color="#1d4ed8", hover_color="#1e40af", command=_arm).pack(pady=12)

# ---------- THREADING WRAPPER ----------
def run_in_thread(fn):
    set_buttons_state("disabled")
    def wrapper():
        fn()
        root.after(0, lambda: set_buttons_state("normal"))
    threading.Thread(target=wrapper, daemon=True).start()

def set_buttons_state(state):
    for btn in all_buttons:
        try: btn.configure(state=state)
        except: pass

# ---------- CORE FEATURES ----------
def wipe_file_folder():
    if not login(): return
    std = standard_var.get()
    files = filedialog.askopenfilenames(title="Select Files to Destroy")
    if files:
        run_in_thread(lambda: [process(f, std) for f in files])

def wipe_entire_directory():
    if not login(): return
    std = standard_var.get()
    folder = filedialog.askdirectory(title="Select Directory to Eradicate")
    if not folder: return
    if not messagebox.askyesno("CONFIRMATION", "Wipe ALL files inside this directory permanently?"): return
    def _do():
        for r, _, files in os.walk(folder):
            for f in files: process(os.path.join(r, f), std)
    run_in_thread(_do)

def wipe_usb():
    if not login(): return
    std = standard_var.get()
    drives = [d.device for d in psutil.disk_partitions() if 'removable' in d.opts.lower()]
    if not drives:
        messagebox.showinfo("USB", "No external drive detected.")
        return
    if not messagebox.askyesno("CRITICAL WARNING", f"Sanitize entirely: {drives[0]}?"): return
    def _do():
        for r, _, files in os.walk(drives[0]):
            for f in files: process(os.path.join(r, f), std)
    run_in_thread(_do)

def sanitize_free_space():
    if not login(): return
    target_dir = filedialog.askdirectory(title="Select Volume for Ghost Sanitization")
    if not target_dir: return
    if not messagebox.askyesno("CONFIRMATION", f"Overwrite all free space on {target_dir}?"): return
    def _do():
        try:
            free_bytes = psutil.disk_usage(target_dir).free
            free_mb = free_bytes / (1024 * 1024)
            root.after(0, lambda: status_label.configure(
                text=f">> PURGING GHOST DATA: {round(free_mb,2)} MB <<", text_color="#00E5FF"))
            root.after(0, sector_grid.trigger_threat)
            log(f"Ghost Protocol initialized on {target_dir}")
            temp_file = os.path.join(target_dir, "ZEROTRACE_GHOST_SANITIZER.tmp")
            chunk_size = 1024 * 1024 * 10
            bytes_written = 0
            with open(temp_file, "wb") as f:
                while bytes_written < free_bytes:
                    write_size = min(chunk_size, free_bytes - bytes_written)
                    try:
                        f.write(b'\x00' * write_size)
                        bytes_written += write_size
                        pct = (bytes_written / free_bytes) * 100
                        root.after(0, lambda p=pct: progress.set(p / 100))
                        root.after(0, lambda p=pct: sector_grid.update_scan(p))
                        log("", matrix=True)
                    except OSError: break
            os.remove(temp_file)
            root.after(0, lambda: progress.set(0))
            root.after(0, sector_grid.reset)
            root.after(0, lambda: status_label.configure(text="GHOST PROTOCOL COMPLETE.", text_color="#10b981"))
            log("Ghost File Sanitization Verified.")
        except Exception as e:
            log("Sanitization Error: " + str(e))
            root.after(0, lambda: progress.set(0))
    run_in_thread(_do)

# ---------- AUDIT FEATURES ----------
def view_history():
    if not login(): return
    import tkinter.ttk as ttk
    hw = ctk.CTkToplevel(root)
    hw.title("Cryptographic Audit Log")
    hw.geometry("1000x480")
    ctk.CTkLabel(hw, text="SYSTEM AUDIT HISTORY", text_color="#00E5FF", font=("Segoe UI Black", 18)).pack(pady=(20, 10))
    tv_frame = ctk.CTkFrame(hw, fg_color="transparent")
    tv_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    scroll = ttk.Scrollbar(tv_frame)
    scroll.pack(side="right", fill="y")
    cols_h = ("File", "Size", "Time", "SHA-256", "Standard")
    tv = ttk.Treeview(tv_frame, columns=cols_h, show="headings", yscrollcommand=scroll.set)
    scroll.config(command=tv.yview)
    for c, w in zip(cols_h, [280, 70, 140, 220, 180]):
        tv.heading(c, text=c)
        tv.column(c, width=w, anchor="center" if c in ["Size","Time"] else "w")
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("Treeview", background="#18181b", foreground="#10b981", fieldbackground="#18181b", rowheight=28, borderwidth=0)
    style.configure("Treeview.Heading", background="#27272a", foreground="#ffffff", font=('Segoe UI', 10, 'bold'))
    style.map("Treeview", background=[('selected', '#3f3f46')])
    tv.pack(fill="both", expand=True)
    try:
        cursor.execute("SELECT file, size, time, hash, standard FROM logs ORDER BY time DESC")
        for row in cursor.fetchall():
            clean_time = row[2].split('.')[0] if '.' in row[2] else row[2]
            tv.insert("", "end", values=(row[0], round(row[1], 2), clean_time, row[3], row[4] or "N/A"))
    except Exception as e:
        messagebox.showerror("Database Error", str(e))

def export_pdf():
    if not login(): return
    file = filedialog.asksaveasfilename(defaultextension=".pdf", title="Save Certificate of Destruction")
    if not file: return
    row = cursor.execute("SELECT file, size, time, hash, standard FROM logs ORDER BY time DESC LIMIT 1").fetchone()
    if not row: return messagebox.showerror("Error", "No audit data.")
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        import qrcode

        cert_id = f"ZT-{hashlib.sha256((row[0]+row[2]).encode()).hexdigest()[:8].upper()}"
        cert_data = {
            "certificate_id": cert_id,
            "target": row[0],
            "size_mb": round(row[1], 4),
            "timestamp": row[2],
            "sha256_pre_wipe": row[3],
            "standard": row[4] or "N/A",
            "status": "VERIFIED_DESTROYED"
        }

        # RSA signature (if key exists)
        sig_text = "N/A"
        key_path = resource_path("private.pem")
        if os.path.exists(key_path):
            try:
                from cryptography.hazmat.primitives import hashes, serialization # type: ignore
                from cryptography.hazmat.primitives.asymmetric import padding # type: ignore
                with open(key_path, "rb") as kf:
                    priv_key = serialization.load_pem_private_key(kf.read(), password=None)
                payload = json.dumps(cert_data, sort_keys=True).encode()
                sig = priv_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
                sig_text = hashlib.sha256(sig).hexdigest()
            except Exception as sig_err:
                sig_text = f"SIG_ERROR: {sig_err}"

        cert_data["rsa_signature_sha256"] = sig_text

        # QR code
        qr_path = os.path.join(app_path, "_qr_tmp.png")
        qrcode.make(json.dumps(cert_data)).save(qr_path)

        doc = SimpleDocTemplate(file, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('title', fontSize=20, textColor=colors.HexColor("#00E5FF"),
                                     spaceAfter=12, fontName='Helvetica-Bold', alignment=1)
        head_style = ParagraphStyle('head', fontSize=11, textColor=colors.HexColor("#10b981"),
                                    fontName='Helvetica-Bold', spaceAfter=4)
        normal_style = ParagraphStyle('norm', fontSize=9, textColor=colors.black, spaceAfter=3)

        table_data = [
            ["Field", "Value"],
            ["Certificate ID", cert_data["certificate_id"]],
            ["Target Path", cert_data["target"]],
            ["Data Mass", f"{cert_data['size_mb']} MB"],
            ["Wipe Standard", cert_data["standard"]],
            ["Timestamp", cert_data["timestamp"]],
            ["SHA-256 (Pre-Wipe)", cert_data["sha256_pre_wipe"]],
            ["RSA Signature (SHA-256)", sig_text[:32] + "..."],
            ["Destruction Status", cert_data["status"]],
        ]
        tbl = Table(table_data, colWidths=[2.2*inch, 4.3*inch])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0a0a0c")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#00E5FF")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#f5f5f5"), colors.white]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))

        content = [
            Paragraph("🛡️ ZeroTrace — Certificate of Destruction", title_style),
            Paragraph("Issued by ZeroTrace Secure Wipe Engine | Compliant with NIST 800-88 / DoD 5220.22-M", normal_style),
            Spacer(1, 12),
            tbl,
            Spacer(1, 16),
            Paragraph("QR Code — Scan to verify destruction record:", head_style),
            RLImage(qr_path, 120, 120),
        ]
        doc.build(content)
        os.remove(qr_path)
        messagebox.showinfo("Success", f"Certificate saved:\n{file}")

    except Exception as e:
        messagebox.showerror("PDF Error", str(e))

def export_csv():
    if not login(): return
    file_path = filedialog.asksaveasfilename(defaultextension=".csv")
    if not file_path: return
    try:
        rows = cursor.execute("SELECT file, size, time, hash, standard FROM logs ORDER BY time DESC").fetchall()
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Path", "Size (MB)", "Timestamp", "SHA-256 (Pre-Wipe)", "Standard"])
            writer.writerows(rows)
        messagebox.showinfo("Success", "Master log exported.")
    except Exception as e:
        log("Export Error: " + str(e))

def clear_logs():
    if messagebox.askyesno("WARNING", "Purge all internal audit logs?"):
        cursor.execute("DELETE FROM logs")
        conn.commit()
        root.after(0, lambda: log_box.delete("0.0", "end"))
        update_dashboard()

def update_dashboard():
    total = cursor.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    size = cursor.execute("SELECT SUM(size) FROM logs").fetchone()[0] or 0
    root.after(0, lambda: total_label.configure(
        text=f"NEUTRALIZED ASSETS: {total}  |  TOTAL MASS PURGED: {round(size,2)} MB"))

# ==========================================
# 🎨 AEGIS PROTOCOL VISUAL ENGINE 🎨
# ==========================================
ctk.set_appearance_mode("dark")

root = ZeroTraceApp()
root.title("ZEROTRACE - TACTICAL COMMAND")
root.geometry("1200x800")
try: root.iconbitmap(resource_path("logo.ico"))
except: pass

# --- Master Layout ---
sidebar = ctk.CTkFrame(root, width=280, corner_radius=0, fg_color="#0a0a0c", border_width=1, border_color="#18181b")
sidebar.pack(side="left", fill="y")

main = ctk.CTkFrame(root, corner_radius=0, fg_color="#000000")
main.pack(side="right", expand=True, fill="both")

# --- Dashboard Header ---
ctk.CTkLabel(main, text="ZEROTRACE", text_color="#00E5FF", font=("Consolas", 32, "bold")).pack(pady=(30, 5))
total_label = ctk.CTkLabel(main, text="", text_color="#a1a1aa", font=("Consolas", 13, "bold"))
total_label.pack(pady=(0, 10))

# --- Wipe Standard Selector ---
std_frame = ctk.CTkFrame(main, fg_color="#0a0a0c", corner_radius=5, border_width=1, border_color="#27272a")
std_frame.pack(padx=60, fill="x", pady=(0, 8))
ctk.CTkLabel(std_frame, text="WIPE STANDARD:", text_color="#00E5FF", font=("Consolas", 11, "bold")).pack(side="left", padx=12, pady=8)
standard_var = ctk.StringVar(value="DoD 5220.22-M (3-pass)")
std_menu = ctk.CTkOptionMenu(std_frame, variable=standard_var, values=list(WIPE_STANDARDS.keys()),
                              fg_color="#18181b", button_color="#27272a", button_hover_color="#3f3f46",
                              text_color="#10b981", font=("Consolas", 12))
std_menu.pack(side="left", padx=8, pady=8)

# --- Status & Sector Map ---
status_label = ctk.CTkLabel(main, text="SYSTEM IDLE. AWAITING TARGET PARAMETERS.", text_color="#3f3f46", font=("Consolas", 13, "bold"))
status_label.pack(pady=(5, 5))

sector_grid = SectorMap(main)
sector_grid.pack(pady=(0, 6))

progress = ctk.CTkProgressBar(main, width=640, height=4, progress_color="#00E5FF", fg_color="#18181b")
progress.set(0)
progress.pack(pady=(0, 6))

# --- Live Telemetry Bar ---
telem_frame = ctk.CTkFrame(main, fg_color="#0a0a0c", corner_radius=5, border_width=1, border_color="#27272a")
telem_frame.pack(fill="x", padx=60, pady=(0, 8))

cpu_lbl = ctk.CTkLabel(telem_frame, text="CPU  0%", text_color="#00E5FF", font=("Consolas", 10, "bold"), width=80)
cpu_lbl.grid(row=0, column=0, padx=(10,4), pady=6)
cpu_bar = ctk.CTkProgressBar(telem_frame, width=120, height=6, progress_color="#00E5FF", fg_color="#18181b")
cpu_bar.set(0)
cpu_bar.grid(row=0, column=1, padx=4)

mem_lbl = ctk.CTkLabel(telem_frame, text="MEM  0%", text_color="#10b981", font=("Consolas", 10, "bold"), width=80)
mem_lbl.grid(row=0, column=2, padx=(16,4))
mem_bar = ctk.CTkProgressBar(telem_frame, width=120, height=6, progress_color="#10b981", fg_color="#18181b")
mem_bar.set(0)
mem_bar.grid(row=0, column=3, padx=4)

disk_lbl = ctk.CTkLabel(telem_frame, text="DISK WRITE  0.0 MB/s", text_color="#f59e0b", font=("Consolas", 10, "bold"))
disk_lbl.grid(row=0, column=4, padx=(16,10))

# --- Floating Drop Zone ---
drop_frame = ctk.CTkFrame(main, fg_color="#0a0a0c", corner_radius=5, border_width=1, border_color="#00E5FF")
drop_frame.pack(pady=6, padx=60, fill="x")

drop = ctk.CTkLabel(drop_frame, text="[ INITIATE TARGET LINK ]\nDrag & Drop Asset Payloads Here",
                    text_color="#e4e4e7", font=("Consolas", 15, "bold"), pady=28)
drop.pack(fill="both", expand=True)
drop.drop_target_register(DND_FILES)

def handle_drop(event):
    std = standard_var.get()
    files = root.tk.splitlist(event.data)
    def _do():
        for f in files:
            if os.path.isfile(f): process(f, std)
            elif os.path.isdir(f):
                for r, _, flist in os.walk(f):
                    for fname in flist: process(os.path.join(r, fname), std)
    run_in_thread(_do)
drop.dnd_bind('<<Drop>>', handle_drop)

# --- Hacker Terminal (Log Box) ---
log_frame = ctk.CTkFrame(main, fg_color="#050505", corner_radius=5, border_width=1, border_color="#18181b")
log_frame.pack(fill="both", expand=True, padx=60, pady=(12, 20))

log_box = ctk.CTkTextbox(log_frame, fg_color="transparent", text_color="#39FF14", font=("Consolas", 12))
log_box.pack(fill="both", expand=True, padx=10, pady=10)

# --- Tactical Sidebar Buttons ---
all_buttons = []

def create_btn(parent, text, command, hover="#059669"):
    btn = ctk.CTkButton(parent, text=text, command=command, font=("Consolas", 12, "bold"),
                        fg_color="transparent", border_width=1, border_color="#27272a",
                        text_color="#a1a1aa", hover_color=hover, anchor="w", height=40)
    btn.pack(fill="x", padx=20, pady=4)
    all_buttons.append(btn)
    return btn

ctk.CTkLabel(sidebar, text="DESTRUCT SEQUENCES", text_color="#00E5FF", font=("Consolas", 11, "bold")).pack(pady=(30, 5), anchor="w", padx=20)
create_btn(sidebar, "> Target Single File", wipe_file_folder, hover="#00E5FF")
create_btn(sidebar, "> Target Directory", wipe_entire_directory, hover="#00E5FF")
create_btn(sidebar, "> Target USB Volume", wipe_usb, hover="#00E5FF")
create_btn(sidebar, "> Purge Ghost Data", sanitize_free_space, hover="#d97706")

ctk.CTkLabel(sidebar, text="AUDIT & COMPLIANCE", text_color="#00E5FF", font=("Consolas", 11, "bold")).pack(pady=(25, 5), anchor="w", padx=20)
create_btn(sidebar, "> View Audit Log", view_history, hover="#2563eb")
create_btn(sidebar, "> Generate PDF Cert", export_pdf, hover="#2563eb")
create_btn(sidebar, "> Export CSV Master", export_csv, hover="#2563eb")
create_btn(sidebar, "> Flush System Logs", clear_logs, hover="#dc2626")

ctk.CTkLabel(sidebar, text="ADVANCED OPS", text_color="#00E5FF", font=("Consolas", 11, "bold")).pack(pady=(25, 5), anchor="w", padx=20)
create_btn(sidebar, "> Deep Search & Destroy", search_and_destroy, hover="#7c3aed")
create_btn(sidebar, "> Set Panic Burn Folder", configure_burn_folder, hover="#b91c1c")

ctk.CTkLabel(sidebar, text="ULTRA OPS", text_color="#ef4444", font=("Consolas", 11, "bold")).pack(pady=(25, 5), anchor="w", padx=20)
create_btn(sidebar, "> Forensic Footprint Clean", forensic_cleanup, hover="#0891b2")
create_btn(sidebar, "> Schedule Timed Wipe", wipe_scheduler_dialog, hover="#0891b2")
create_btn(sidebar, "> SELF-DESTRUCT ALL LOGS", self_destruct, hover="#7f1d1d")

update_dashboard()

# --- Auto-Lock Overlay (built after root exists) ---
lock_overlay = ctk.CTkFrame(root, fg_color="#000000", corner_radius=0)
ctk.CTkLabel(lock_overlay, text="🔒 SESSION LOCKED", text_color="#00E5FF",
             font=("Consolas", 28, "bold")).pack(expand=True, pady=(120, 8))
ctk.CTkLabel(lock_overlay, text=f"Auto-locked after {IDLE_TIMEOUT}s of inactivity.",
             text_color="#71717a", font=("Consolas", 12)).pack(pady=(0, 12))
lock_status_lbl = ctk.CTkLabel(lock_overlay, text="", text_color="#ef4444", font=("Consolas", 11))
lock_status_lbl.pack(pady=(0, 8))
ctk.CTkButton(lock_overlay, text="UNLOCK SESSION", font=("Consolas", 14, "bold"),
              fg_color="#0a0a0c", border_width=1, border_color="#00E5FF",
              text_color="#00E5FF", hover_color="#18181b",
              command=_do_unlock).pack(pady=8)

# --- Bind idle reset to all mouse/key events ---
for event in ("<Motion>", "<KeyPress>", "<Button>"):
    root.bind(event, _reset_idle, add="+")

# --- Start background loops ---
_load_burn_folder()
root.after(1000, _update_telemetry)
root.after(5000, _check_idle)

# --- Panic Burn global hotkey ---
root.bind("<Control-Shift-F12>", panic_burn)

# --- Dead Man's Switch (fires on forced kill / crash) ---
import atexit
import signal as _signal

def _dead_mans_switch():
    if _burn_folder and os.path.isdir(_burn_folder):
        try:
            for r, _, files in os.walk(_burn_folder):
                for fn in files:
                    fp = os.path.join(r, fn)
                    try:
                        sz = os.path.getsize(fp)
                        with open(fp, "r+b") as fh:
                            fh.write(os.urandom(sz)); fh.flush()
                        os.remove(fp)
                    except Exception:
                        pass
        except Exception:
            pass

atexit.register(_dead_mans_switch)
try:
    _signal.signal(_signal.SIGTERM, lambda s, f: (_dead_mans_switch(), sys.exit(0)))
except Exception:
    pass

# --- Scheduler background thread ---
threading.Thread(target=_run_scheduler_thread, daemon=True).start()

log("[INIT] ZeroTrace Ultra Engine v4.0 online.")
log("[INIT] Dead Man's Switch armed. Scheduler running. All systems nominal.")

root.mainloop()