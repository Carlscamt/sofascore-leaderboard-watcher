import paramiko

HOST = "192.168.123.2"
USER = "carlscamt"
PASS = "7373"
REMOTE_DIR = "/home/carlscamt/antigravity/sofascore-leaderboard-watcher"

def main():
    print(f"Connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, username=USER, password=PASS)
        print("✅ Connected\n")
        
        cmd = f"cd {REMOTE_DIR} && source venv/bin/activate && pip install tls-client"
        print(f"🚀 Running: {cmd}")
        
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
        # Handle sudo just in case, though pip usually doesn't need it in venv
        # But if it tries to build wheels and needs system dependencies?
        
        while True:
            line = stdout.readline()
            if not line: break
            print(line.strip())
            
        exit_code = stdout.channel.recv_exit_status()
        if exit_code == 0:
            print("✅ Installation Successful")
        else:
            print(f"❌ Failed (Exit Code: {exit_code})")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
