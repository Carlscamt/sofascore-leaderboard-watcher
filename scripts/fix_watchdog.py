import paramiko

HOST = "192.168.123.2"
USER = "carlscamt"
PASS = "7373"

def run_cmd(client, cmd, desc):
    print(f"\n🔧 {desc}")
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    stdin.write(f"{PASS}\n")
    stdin.flush()
    print(stdout.read().decode().strip())

def main():
    print(f"Connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, username=USER, password=PASS)
        print("✅ Connected\n")
        
        # Comment out the interface line in watchdog.conf
        # We use sed to find the line starting with 'interface' and prepend #
        run_cmd(client, "sudo sed -i 's/^interface/#interface/' /etc/watchdog.conf", "Disabling Watchdog Interface Check")
        
        # Verify the change
        run_cmd(client, "grep '^#interface' /etc/watchdog.conf", "Verifying Config Change")
        
        # Restart watchdog
        run_cmd(client, "sudo systemctl restart watchdog", "Restarting Watchdog Service")
        
        # Check status
        run_cmd(client, "systemctl status watchdog --no-pager", "Checking Watchdog Status")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
