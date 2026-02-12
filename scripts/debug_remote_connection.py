import paramiko
import time

HOST = "192.168.123.2"
USER = "carlscamt"
PASS = "7373"
REMOTE_DIR = "/home/carlscamt/antigravity/sofascore-leaderboard-watcher"

DEBUG_SCRIPT_CONTENT = """
import sys
import os
import time

# Add src to path just in case, though we might not use src modules directly
sys.path.insert(0, os.path.abspath('src'))

try:
    from tls_client import Session
    print("✅ tls_client imported successfully.")
except ImportError:
    print("❌ tls_client NOT found. Ensure venv is active and installed.")
    sys.exit(1)

URL = "https://www.sofascore.com/api/v1/user-account/vote-ranking"

def test_fingerprint(fp):
    print(f"\\n🔍 Testing fingerprint: {fp}")
    try:
        session = Session(client_identifier=fp)
        # Sofascore sometimes needs these headers
        headers = {
            "Accept": "application/json",
            "Referer": "https://www.sofascore.com/",
            # "User-Agent": "..." # Let tls_client handle UA? Or override?
            # Usually better to let tls_client handle it or match exactly.
        }
        
        resp = session.get(URL, headers=headers, timeout_seconds=10)
        print(f"   Status: {resp.status_code}")
        
        if resp.status_code == 200:
            print("   ✅ Success!")
            print(f"   Data keys: {list(resp.json().keys()) if resp.json() else 'None'}")
            return True
        elif resp.status_code == 403:
            print("   ❌ 403 Forbidden (Blocked)")
        else:
            print(f"   ⚠️ {resp.status_code} (Other Error)")
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    return False

fingerprints = [
    "chrome_124",         # Latest Chrome
    "chrome_120",         # Slightly older
    "firefox_126",        # Latest Firefox 
    "firefox_120",        # Current setting (failed?)
    "safari_16_0",        # Safari MacOS
    "okhttp4_android_13", # Android API
]

print("🚀 Starting Fingerprint Tests on 192.168.123.2...")
for fp in fingerprints:
    if test_fingerprint(fp):
        print(f"\\n🏆 WINNER: {fp}")
        break
else:
    print("\\n❌ ALL FAILED.")
"""

def main():
    print(f"Connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, username=USER, password=PASS)
        print("✅ Connected\n")
        
        # 1. Upload Script
        sftp = client.open_sftp()
        with sftp.file(f"{REMOTE_DIR}/debug_fingerprints.py", "w") as f:
            f.write(DEBUG_SCRIPT_CONTENT)
        print("✅ Uploaded debug_fingerprints.py")
        
        # 2. Run Script in Venv
        cmd = f"cd {REMOTE_DIR} && venv/bin/python debug_fingerprints.py"
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
        
        while True:
            line = stdout.readline()
            if not line: break
            print(line.strip())
            
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
