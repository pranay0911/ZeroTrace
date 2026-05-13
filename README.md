# 🛡️ ZeroTrace

**Tactical Data Sanitization & IT Asset Disposition (ITAD) Engine**

ZeroTrace is a standalone, enterprise-grade desktop cybersecurity application built for secure data destruction. Standard operating system deletion simply removes file pointers, leaving sensitive corporate and personal data fully recoverable. ZeroTrace solves this by implementing cryptographic, software-based data sanitization, allowing for the safe, eco-friendly recycling and repurposing of IT hardware.

Developed by team **Anti Gravity**.

---

## ⚡ Key Features

* **Military-Grade Cryptographic Wiping:** Replaces standard file deletion with rigorous overwrite algorithms, scrambling both magnetic and digital signatures.
  * *Supported Standards:* NIST 800-88 Clear (1-pass), DoD 5220.22-M (3-pass), DoD 5220.22-M ECE (7-pass), Gutmann (35-pass).
* **Purge Ghost Data:** A specialized protocol that targets and neutralizes unallocated "free space" on a drive to permanently destroy previously "deleted" historical files while leaving the active OS intact.
* **Verifiable Audit Trails:** Automatically logs every destruction event into an encrypted local SQLite database.
* **PDF Certificates of Destruction:** Generates tamper-evident, digitally signed PDF certificates complete with pre-wipe SHA-256 hashes and verification QR codes for legal GDPR/HIPAA compliance.
* **Tactical Command GUI:** A modern, dark-themed interface featuring drag-and-drop asset payload zones, live system telemetry (CPU/Memory/Disk I/O), and real-time visual sector mapping.

---

## 🛠️ Technology Stack

* **Core Language:** Python 3.11+
* **Frontend UI:** `customtkinter`, `tkinterdnd2`
* **Database & Auditing:** `sqlite3`, `hashlib`
* **Compliance Reporting:** `reportlab`, `qrcode`, `cryptography`
* **System Telemetry:** `psutil`
* **Compilation:** `PyInstaller`

---
   ```bash
   git clone [https://github.com/yourusername/zerotrace.git](https://github.com/yourusername/zerotrace.git)
   cd zerotrace
