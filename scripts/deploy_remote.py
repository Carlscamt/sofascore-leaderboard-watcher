import paramiko
import time
import sys

HOST = "192.168.123.2"
USER = "carlscamt"
PASS = "7373"
PROJECT_DIR = "/home/carlscamt/antigravity/sofascore-leaderboard-watcher"

def run_remote_command(ssh, cmd, description):
    print(f"\n🚀 {description}...")
    print(f"   Command: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    
    # Send password for sudo if prompted
    # Paramiko doesn't interactive well with sudo unless we anticipate prompt
    # Simple hack: send password immediately if sudo is in command
    if "sudo" in cmd:
        stdin.write(f"{PASS}\n")
        stdin.flush()
        
    # Handle PPA confirmation
    if "add-apt-repository" in cmd:
        time.sleep(2) # Wait for prompt
        stdin.write("\n")
        stdin.flush()
    
    # Live output
    while True:
        line = stdout.readline()
        if not line: break
        print(f"   {line.strip()}")
        
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        print(f"❌ Failed (Exit Code: {exit_status})")
        # Don't exit script immediately? Or maybe we should?
        # For some commands like 'git pull' it might return non-zero if divergent
        # But generally we want to know.
        return False
    print("✅ Success")
    return True

def main():
    print(f"Connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, username=USER, password=PASS)
        print("✅ Connected via SSH")
        
        # 1. Environment Setup
        cmds = [
            (f"mkdir -p {PROJECT_DIR}", "Ensuring project directory exists"),
            # Clone if not exists, pull if exists
            (f"if [ -d {PROJECT_DIR}/.git ]; then cd {PROJECT_DIR} && git pull; else git clone https://github.com/Carlscamt/sofascore-leaderboard-watcher.git {PROJECT_DIR}; fi", "Syncing Repository"),
            # Ensure Python 3.11 is installed via deadsnakes PPA if not found
            ("sudo apt update && sudo apt install -y software-properties-common && sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt update && sudo apt install -y python3.11 python3.11-venv python3.11-dev", "Installing Python 3.11 & Venv (with PPA)"),
            # Virtual Env
            (f"cd {PROJECT_DIR} && python3.11 -m venv venv", "Creating Virtual Environment"),
            # Dependencies
            (f"cd {PROJECT_DIR} && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt", "Installing Dependencies"),
        ]

        for cmd, desc in cmds:
            if not run_remote_command(client, cmd, desc):
                print("⚠️ Stopping deployment due to error.")
                return

        # 2. Configuration (.env)
        print("\n🚀 Configuring .env...")
        # Read local .env file content
        try:
            with open(".env", "r") as f:
                env_content = f.read()
            print("   Loaded local .env file.")
        except FileNotFoundError:
            print("⚠️ Local .env not found. Using default template.")
            env_content = """DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID
DISCORD_HEALTH_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_HEALTH_WEBHOOK_ID
SCAN_INTERVAL_MINUTES=5
MIN_ROI=5.0
MIN_AVG_ODDS=1.5
MIN_TOTAL_BETS=10
DB_PATH=/home/carlscamt/antigravity/sofascore-leaderboard-watcher/data/sofascore_monitor.db
LOG_LEVEL=INFO
"""
        # Escape newlines for echo
        # Using sftp is safer
        sftp = client.open_sftp()
        with sftp.file(f"{PROJECT_DIR}/.env", "w") as f:
            f.write(env_content)
        print("✅ .env file created via SFTP")

        # 3. Database Init
        db_init_cmd = f"""cd {PROJECT_DIR} && mkdir -p data && mkdir -p logs && source venv/bin/activate && python3 -c "import sys; sys.path.insert(0, './src'); from sofascore_monitor.storage import Storage; Storage('{PROJECT_DIR}/data/sofascore_monitor.db'); print('DB Initialized')" """
        if not run_remote_command(client, db_init_cmd, "Initializing Database"): return

        # 3.5 Verify Python Binary
        verify_python_cmd = f"{PROJECT_DIR}/venv/bin/python --version"
        if not run_remote_command(client, verify_python_cmd, "Verifying Python Binary"):
             print("❌ Python binary check failed! Venv might be broken.")
             return

        # 4. Systemd Service
        # We need to construct the service file content with correct paths
        service_content = f"""[Unit]
Description=Sofascore Leaderboard Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={USER}
Group={USER}
WorkingDirectory={PROJECT_DIR}
Environment="PYTHONUNBUFFERED=1"
Environment="PYTHONPATH={PROJECT_DIR}/src"
Environment="TZ=Europe/London"
EnvironmentFile={PROJECT_DIR}/.env
ExecStart={PROJECT_DIR}/venv/bin/python main.py
Restart=on-failure
RestartSec=60
StartLimitBurst=5
StartLimitIntervalSec=600
MemoryMax=400M
MemoryHigh=350M
CPUQuota=40%
TasksMax=50
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=false
ReadWritePaths={PROJECT_DIR}/data
ReadWritePaths={PROJECT_DIR}/logs
CapabilityBoundingSet=
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sofascore-monitor

[Install]
WantedBy=multi-user.target
"""
        # Upload service file to temp then sudo mv
        with sftp.file(f"/home/{USER}/sofascore-monitor.service", "w") as f:
            f.write(service_content)
        
        if not run_remote_command(client, f"sudo mv /home/{USER}/sofascore-monitor.service /etc/systemd/system/sofascore-monitor.service", "Installing Service File"): return
        
        # 5. Start Service
        start_cmds = [
            ("sudo systemctl daemon-reload", "Reloading Systemd"),
            ("sudo systemctl enable sofascore-monitor.service", "Enabling Service"),
            ("sudo systemctl restart sofascore-monitor.service", "Starting Service"), # Restart handles both start and re-deploy
            ("sudo systemctl status sofascore-monitor.service --no-pager", "Checking Status"),
        ]
        
        for cmd, desc in start_cmds:
            run_remote_command(client, cmd, desc)

        # 6. Power Management
        # Check if logind.conf needs update
        # Grep for HandleLidSwitch=ignore
        # If not present, append it
        # Simple check:
        # run_remote_command(client, "grep 'HandleLidSwitch=ignore' /etc/systemd/logind.conf", "Checking Lid Switch Config")
        # If exit code 1, append
        
        setup_power = """
if ! grep -q "HandleLidSwitch=ignore" /etc/systemd/logind.conf; then
    echo "HandleLidSwitch=ignore" | sudo tee -a /etc/systemd/logind.conf
    echo "HandleLidSwitchExternalPower=ignore" | sudo tee -a /etc/systemd/logind.conf
    echo "HandleLidSwitchDocked=ignore" | sudo tee -a /etc/systemd/logind.conf
    sudo systemctl restart systemd-logind.service
    echo "Updated logind.conf"
else
    echo "logind.conf already configured"
fi
"""
        run_remote_command(client, setup_power, "Configuring Power Management")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
