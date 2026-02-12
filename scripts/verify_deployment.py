import paramiko

HOST = "192.168.123.2"
USER = "carlscamt"
PASS = "7373"

def main():
    print(f"Connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, username=USER, password=PASS)
        print("✅ Connected. Checking Service Status...\n")
        
        # Check Status
        stdin, stdout, stderr = client.exec_command("sudo systemctl status sofascore-monitor.service --no-pager", get_pty=True)
        stdin.write(f"{PASS}\n")
        stdin.flush()
        print(stdout.read().decode())
        
        print("\n📊 Recent Logs:")
        stdin, stdout, stderr = client.exec_command("sudo journalctl -u sofascore-monitor.service -n 20 --no-pager", get_pty=True)
        stdin.write(f"{PASS}\n")
        stdin.flush()
        print(stdout.read().decode())

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
