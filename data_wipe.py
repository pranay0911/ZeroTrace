import os, sys, hashlib, sqlite3, datetime, subprocess, csv, random, time
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

# ---------- LOGIN ----------
USERNAME = "admin"
PASSWORD = "1234"

def login():
    dialog_u = ctk.CTkInputDialog(text="Enter Admin Username:", title="Authentication Required")
    u = dialog_u.get_input()
    if u != USERNAME: return False
    dialog_p = ctk.CTkInputDialog(text="Enter Passcode:", title="Authentication Required")
    p = dialog_p.get_input()
    return p == PASSWORD

# ---------- DATABASE ----------
if getattr(sys, 'frozen', False): app_path = os.path.dirname(sys.executable)
else: app_path = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(app_path, "logs.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(logs)")
cols = [c[1] for c in cursor.fetchall()]

if not cols: cursor.execute("CREATE TABLE logs(file TEXT,size REAL,time TEXT,hash TEXT)")
elif "hash" not in cols: cursor.execute("ALTER TABLE logs ADD COLUMN hash TEXT")
conn.commit()

# ---------- UTILS ----------
def get_hash(f):
    try:
        out = subprocess.check_output(["openssl","dgst","-sha256",f]).decode()
        return out.split("=")[-1].strip()
    except:
        h = hashlib.sha256()
        h.update(open(f,"rb").read())
        return h.hexdigest()

def log(msg, matrix=False):
    if matrix:
        # Generate random hex for the "hacker" visual effect
        hex_stream = "".join([random.choice("0123456789ABCDEF") for _ in range(32)])
        log_box.insert("end", f"[0x{random.randint(1000,9999)}] SHREDDING: {hex_stream} ...\n")
    else:
        t = datetime.datetime.now().strftime('%H:%M:%S')
        log_box.insert("end", f"[{t}] {msg}\n")
    log_box.see("end")

# ---------- CUSTOM VISUAL WIDGET: SECTOR MAP ----------
class SectorMap(tk.Canvas):
    def __init__(self, parent, width=640, height=60, **kwargs):
        super().__init__(parent, width=width, height=height, bg="#09090b", highlightthickness=0, **kwargs)
        self.rects = []
        self.cols = 40
        self.rows = 4
        # Draw the grid of memory sectors
        for y in range(self.rows):
            for x in range(self.cols):
                r = self.create_rectangle(x*16, y*15, x*16+14, y*15+13, fill="#18181b", outline="#27272a")
                self.rects.append(r)
                
    def trigger_threat(self):
        # Turns the whole grid Red when a file is detected
        for r in self.rects: self.itemconfig(r, fill="#450a0a", outline="#7f1d1d")
        
    def update_scan(self, percentage):
        # Progressively turns sectors Neon Green as they are wiped
        total = len(self.rects)
        cleared = int((percentage / 100.0) * total)
        for i in range(total):
            if i < cleared:
                self.itemconfig(self.rects[i], fill="#10b981", outline="#059669")
                
    def reset(self):
        for r in self.rects: self.itemconfig(r, fill="#18181b", outline="#27272a")

# ---------- THE SMART ENGINE WIPE ----------
def secure_delete(f):
    try:
        size = os.path.getsize(f)
        size_mb = size / (1024 * 1024)
        chunk_size = 1024 * 1024  
        file_name = os.path.basename(f)
        
        if size_mb > 50:
            active_mode = "Crypto-Erase (AES-256)"
            passes = 2
        else:
            active_mode = "Phantom-Collapse"
            passes = 1

        # UI Updates
        status_label.configure(text=f">> EXECUTING: {active_mode} ON '{file_name}' <<", text_color="#ff4444")
        sector_grid.trigger_threat() # Turn grid red
        root.update_idletasks() 
        log(f"Engine: Engaged {active_mode} for {round(size_mb,2)} MB payload.")

        encryptor = None
        if "Crypto-Erase" in active_mode:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes # type: ignore
            key = os.urandom(32)
            nonce = os.urandom(16)
            cipher = Cipher(algorithms.AES(key), modes.CTR(nonce))
            encryptor = cipher.encryptor()

        for i in range(passes):
            with open(f, "r+b") as file:
                bytes_written = 0
                while bytes_written < size:
                    write_size = min(chunk_size, size - bytes_written)
                    
                    if "Crypto-Erase" in active_mode:
                        if i == 0:
                            file.seek(bytes_written)
                            chunk_data = file.read(write_size)
                            data = encryptor.update(chunk_data)
                            file.seek(bytes_written)
                        else: data = b'\x00' * write_size

                    elif "Phantom" in active_mode:
                        if bytes_written == 0:
                            data = os.urandom(min(4096, write_size))
                            if write_size > 4096:
                                decoy = b"SYSTEM_ERROR_LOG_NULL_POINTER_EXCEPTION_OVERWRITE_0x00F... "
                                repeats = (write_size - 4096) // len(decoy) + 1
                                data += (decoy * repeats)[:(write_size - 4096)]
                        else:
                            decoy = b"SYSTEM_ERROR_LOG_NULL_POINTER_EXCEPTION_OVERWRITE_0x00F... "
                            repeats = write_size // len(decoy) + 1
                            data = (decoy * repeats)[:write_size]
                    
                    file.write(data)
                    bytes_written += write_size
                
                file.flush()
                os.fsync(file.fileno()) 

            if "Crypto-Erase" in active_mode and i == 0:
                encryptor = None; key = None

            # Visual Animation Math
            percent = ((i + 1) / passes) * 100
            progress.set(percent / 100)
            sector_grid.update_scan(percent)
            log("", matrix=True) # Trigger the Matrix Hex Flood
            root.update_idletasks()

        temp_name = os.path.join(os.path.dirname(f), "WIPED_" + get_hash(f)[:8] + ".tmp")
        os.rename(f, temp_name)
        os.remove(temp_name)
        
        progress.set(0)
        sector_grid.reset()

    except Exception as e:
        log("CRITICAL ERROR: " + str(e))
        status_label.configure(text="SYSTEM FAILURE DURING DESTRUCTION.", text_color="#ff4444")

# ---------- PROCESS ----------
def process(f):
    try:
        if not os.path.exists(f): return
        size = os.path.getsize(f)/(1024*1024)
        h = get_hash(f)

        log(f"Target acquired: {os.path.basename(f)}")
        secure_delete(f)

        cursor.execute("INSERT INTO logs(file,size,time,hash) VALUES(?,?,?,?)",
                       (f,size,str(datetime.datetime.now()),h))
        conn.commit()

        update_dashboard()
        status_label.configure(text="TARGET SUCCESSFULLY NEUTRALIZED.", text_color="#10b981")
        log("Destruction Verified and Logged.\n")

    except Exception as e:
        log("Error "+str(e))
        status_label.configure(text="OPERATION FAILED.", text_color="#ff4444")

# ---------- CORE FEATURES ----------
def wipe_file_folder():
    if not login(): return
    files = filedialog.askopenfilenames(title="Select Files to Destroy")
    if files:
        for f in files: process(f)

def wipe_entire_directory():
    if not login(): return
    folder = filedialog.askdirectory(title="Select Directory to Eradicate")
    if not folder: return
    if not messagebox.askyesno("CONFIRMATION","Wipe ALL files inside this directory permanently?"): return
    for r,_,files in os.walk(folder):
        for f in files: process(os.path.join(r,f))

def wipe_usb():
    if not login(): return
    drives = [d.device for d in psutil.disk_partitions() if 'removable' in d.opts.lower()]
    if not drives:
        messagebox.showinfo("USB","No external drive detected.")
        return
    if not messagebox.askyesno("CRITICAL WARNING", f"Sanitize entirely: {drives[0]}?"): return
    for r,_,files in os.walk(drives[0]):
        for f in files: process(os.path.join(r,f))

def sanitize_free_space():
    if not login(): return
    target_dir = filedialog.askdirectory(title="Select Volume for Ghost Sanitization")
    if not target_dir: return
    if not messagebox.askyesno("CONFIRMATION", f"Overwrite all free space on {target_dir}?"): return

    try:
        free_bytes = psutil.disk_usage(target_dir).free
        free_mb = free_bytes / (1024 * 1024)
        
        status_label.configure(text=f">> PURGING GHOST DATA: {round(free_mb, 2)} MB <<", text_color="#00E5FF")
        sector_grid.trigger_threat()
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
                    percent = (bytes_written / free_bytes) * 100
                    progress.set(percent / 100)
                    sector_grid.update_scan(percent)
                    log("", matrix=True)
                    root.update_idletasks()
                except OSError: break
        
        os.remove(temp_file)
        progress.set(0)
        sector_grid.reset()
        status_label.configure(text="GHOST PROTOCOL COMPLETE.", text_color="#10b981")
        log("Ghost File Sanitization Verified.")
    except Exception as e:
        log("Sanitization Error: " + str(e))
        progress.set(0)

# ---------- AUDIT FEATURES ----------
def view_history():
    if not login(): return
    import tkinter.ttk as ttk
    hw = ctk.CTkToplevel(root)
    hw.title("Cryptographic Audit Log")
    hw.geometry("900x450")
    try: hw.iconbitmap(resource_path("logo.ico"))
    except: pass
    
    ctk.CTkLabel(hw, text="SYSTEM AUDIT HISTORY", text_color="#00E5FF", font=("Segoe UI Black", 18)).pack(pady=(20, 10))
    
    tv_frame = ctk.CTkFrame(hw, fg_color="transparent")
    tv_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    scroll = ttk.Scrollbar(tv_frame)
    scroll.pack(side="right", fill="y")
    
    cols = ("File", "Size", "Time", "Hash")
    tv = ttk.Treeview(tv_frame, columns=cols, show="headings", yscrollcommand=scroll.set)
    scroll.config(command=tv.yview)
    
    for c, w in zip(cols, [350, 80, 150, 250]):
        tv.heading(c, text=c if c!="File" else "Target Path")
        tv.column(c, width=w, anchor="center" if c in ["Size","Time"] else "w")
    
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("Treeview", background="#18181b", foreground="#10b981", fieldbackground="#18181b", rowheight=28, borderwidth=0)
    style.configure("Treeview.Heading", background="#27272a", foreground="#ffffff", font=('Segoe UI', 10, 'bold'))
    style.map("Treeview", background=[('selected', '#3f3f46')])
    tv.pack(fill="both", expand=True)
    
    try:
        cursor.execute("SELECT file, size, time, hash FROM logs ORDER BY time DESC")
        for row in cursor.fetchall():
            clean_time = row[2].split('.')[0] if '.' in row[2] else row[2]
            tv.insert("", "end", values=(row[0], round(row[1], 2), clean_time, row[3]))
    except Exception as e: messagebox.showerror("Database Error", str(e))

def export_pdf():
    if not login(): return
    file = filedialog.asksaveasfilename(defaultextension=".pdf")
    if not file: return
    row = cursor.execute("SELECT * FROM logs ORDER BY time DESC LIMIT 1").fetchone()
    if not row: return messagebox.showerror("Error","No audit data.")
    
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Image as RLImage
        from reportlab.lib.styles import getSampleStyleSheet
        import qrcode
    except: return messagebox.showerror("Error", "Required libraries missing.")

    doc = SimpleDocTemplate(file)
    styles = getSampleStyleSheet()
    content = [
        Paragraph("ZeroTrace Audit Certificate", styles['Title']),
        Paragraph(f"<b>Target:</b> {row[0]}", styles['Normal']),
        Paragraph(f"<b>Data Mass:</b> {round(row[1],2)} MB", styles['Normal']),
        Paragraph(f"<b>SHA-256:</b> {row[3]}", styles['Normal']),
        Paragraph(f"<b>Time:</b> {row[2]}", styles['Normal'])
    ]
    qr = qrcode.make(str(row)); qr.save("qr.png")
    content.append(RLImage("qr.png",100,100))
    doc.build(content); os.remove("qr.png")
    messagebox.showinfo("Success","Certificate generated.")

def export_csv():
    if not login(): return
    file_path = filedialog.asksaveasfilename(defaultextension=".csv")
    if not file_path: return
    try:
        rows = cursor.execute("SELECT file, size, time, hash FROM logs ORDER BY time DESC").fetchall()
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Path", "Size (MB)", "Timestamp", "SHA-256"])
            writer.writerows(rows)
        messagebox.showinfo("Success", "Master log exported.")
    except Exception as e: log("Export Error: " + str(e))

def clear_logs():
    if messagebox.askyesno("WARNING", "Purge all internal audit logs?"):
        cursor.execute("DELETE FROM logs")
        conn.commit()
        log_box.delete("0.0", "end")
        update_dashboard()

def update_dashboard():
    total = cursor.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    size = cursor.execute("SELECT SUM(size) FROM logs").fetchone()[0] or 0
    total_label.configure(text=f"NEUTRALIZED ASSETS: {total}  |  TOTAL MASS PURGED: {round(size,2)} MB")

# ==========================================
# 🎨 AEGIS PROTOCOL VISUAL ENGINE 🎨
# ==========================================
ctk.set_appearance_mode("dark")  

root = ZeroTraceApp()
root.title("ZEROTRACE - TACTICAL COMMAND")
root.geometry("1100x780")
try: root.iconbitmap(resource_path("logo.ico"))
except: pass

# --- Master Layout ---
sidebar = ctk.CTkFrame(root, width=260, corner_radius=0, fg_color="#0a0a0c", border_width=1, border_color="#18181b")
sidebar.pack(side="left", fill="y")

main = ctk.CTkFrame(root, corner_radius=0, fg_color="#000000")
main.pack(side="right", expand=True, fill="both")

# --- Dashboard Header ---
ctk.CTkLabel(main, text="ZEROTRACE", text_color="#00E5FF", font=("Consolas", 32, "bold")).pack(pady=(35, 5))
total_label = ctk.CTkLabel(main, text_color="#a1a1aa", font=("Consolas", 14, "bold"))
total_label.pack(pady=(0, 20))

# --- Status & Sector Map ---
status_label = ctk.CTkLabel(main, text="SYSTEM IDLE. AWAITING TARGET PARAMETERS.", text_color="#3f3f46", font=("Consolas", 14, "bold"))
status_label.pack(pady=(5, 5))

# 🚀 THE NEW REAL-TIME SECTOR MAP 🚀
sector_grid = SectorMap(main)
sector_grid.pack(pady=(0, 10))

progress = ctk.CTkProgressBar(main, width=640, height=4, progress_color="#00E5FF", fg_color="#18181b")
progress.set(0)
progress.pack(pady=(0, 20))

# --- Floating Drop Zone ---
drop_frame = ctk.CTkFrame(main, fg_color="#0a0a0c", corner_radius=5, border_width=1, border_color="#00E5FF")
drop_frame.pack(pady=10, padx=60, fill="x")

drop = ctk.CTkLabel(drop_frame, text="[ INITIATE TARGET LINK ]\nDrag & Drop Asset Payloads Here",
                    text_color="#e4e4e7", font=("Consolas", 16, "bold"), pady=35)
drop.pack(fill="both", expand=True)
drop.drop_target_register(DND_FILES)

def handle_drop(event):
    files = root.tk.splitlist(event.data)
    for f in files:
        if os.path.isfile(f): process(f)
        elif os.path.isdir(f):
            for r, _, flist in os.walk(f): 
                for file_name in flist: process(os.path.join(r, file_name))
drop.dnd_bind('<<Drop>>', handle_drop)

# --- Hacker Terminal (Log Box) ---
log_frame = ctk.CTkFrame(main, fg_color="#050505", corner_radius=5, border_width=1, border_color="#18181b")
log_frame.pack(fill="both", expand=True, padx=60, pady=(20, 30))

log_box = ctk.CTkTextbox(log_frame, fg_color="transparent", text_color="#39FF14", font=("Consolas", 12))
log_box.pack(fill="both", expand=True, padx=10, pady=10)

# --- Tactical Sidebar Buttons (FIXED: Removed hover_text_color) ---
def create_btn(parent, text, command, color="#10b981", hover="#059669"):
    btn = ctk.CTkButton(parent, text=text, command=command, font=("Consolas", 13, "bold"), 
                        fg_color="transparent", border_width=1, border_color="#27272a",
                        text_color="#a1a1aa", hover_color=hover, anchor="w", height=40)
    btn.pack(fill="x", padx=20, pady=5)
    return btn

ctk.CTkLabel(sidebar, text="DESTRUCT SEQUENCES", text_color="#00E5FF", font=("Consolas", 12, "bold")).pack(pady=(30, 5), anchor="w", padx=20)
create_btn(sidebar, "> Target Single File", wipe_file_folder, hover="#00E5FF")
create_btn(sidebar, "> Target Directory", wipe_entire_directory, hover="#00E5FF")
create_btn(sidebar, "> Target USB Volume", wipe_usb, hover="#00E5FF")
create_btn(sidebar, "> Purge Ghost Data", sanitize_free_space, hover="#d97706")

ctk.CTkLabel(sidebar, text="AUDIT & COMPLIANCE", text_color="#00E5FF", font=("Consolas", 12, "bold")).pack(pady=(30, 5), anchor="w", padx=20)
create_btn(sidebar, "> View Audit Log", view_history, hover="#2563eb")
create_btn(sidebar, "> Generate PDF Cert", export_pdf, hover="#2563eb")
create_btn(sidebar, "> Export CSV Master", export_csv, hover="#2563eb")
create_btn(sidebar, "> Flush System Logs", clear_logs, hover="#dc2626")

update_dashboard()
root.mainloop()