import paramiko
import time
import sys

HOST = "192.168.123.2"
USER = "carlscamt"
PASS = "7373"
PROJECT_DIR = "/home/carlscamt/antigravity/sofascore-leaderboard-watcher"

def run_cmd(client, cmd, desc, critical=False):
    print(f"\n🔍 {desc}...")
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    stdin.write(f"{PASS}\n")
    stdin.flush()
    
    # Read output incrementally with flush
    output = ""
    while True:
        line = stdout.readline()
        if not line: break
        print(line, end="") 
        sys.stdout.flush() # Force flush
        output += line
        
    exit_status = stdout.channel.recv_exit_status()
    
    if exit_status != 0:
        print(f"\n❌ Failed (Exit Code: {exit_status})")
        if critical:
            print("⚠️ Critical check failed. Aborting.")
            return None
    else:
        # print("✅ Passed") # Don't duplicate if printing live
        pass
    return output.strip()

def main():
    print(f"🏥 Starting Comprehensive Remote Health Check on {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, username=USER, password=PASS)
        print("✅ SSH Connection Established\n")
        
        # 1. Service Status & Resources
        status = run_cmd(client, "systemctl is-active sofascore-monitor", "Checking Service Status", critical=True)
        if status != "active": return

        run_cmd(client, "systemctl status sofascore-monitor --no-pager | grep -E 'Memory|CPU'", "Checking Resource Usage")
        
        # 2. Database Integrity & Freshness
        # Check if DB file exists and size
        run_cmd(client, f"ls -lh {PROJECT_DIR}/data/sofascore_monitor.db", "Checking Database File")
        
        # Check for recent writes (last 1 hour)
        sql_check = f"""sqlite3 {PROJECT_DIR}/data/sofascore_monitor.db "SELECT count(*) FROM seen_bets WHERE created_at > datetime('now', '-1 hour');" """
        bts = run_cmd(client, sql_check, "Checking Recent Bets (Last 1h)")
        
        # 3. Log Analysis
        # Check for recent errors
        errs = run_cmd(client, "sudo journalctl -u sofascore-monitor --since '1 hour ago' -p err --no-pager | wc -l", "Checking for Recent Errors")
        if errs and int(errs) > 0:
            print(f"⚠️ Found {errs} errors in the last hour!")
            run_cmd(client, "sudo journalctl -u sofascore-monitor --since '1 hour ago' -p err --no-pager | tail -n 5", "Showing Last 5 Errors")
        
        # Check for successful polling (Adaptive Sleep logs)
        run_cmd(client, "sudo journalctl -u sofascore-monitor --since '1 hour ago' --no-pager | grep 'Sleeping for' | tail -n 3", "Verifying Polling Cycles")
        
        # 4. Environment & Hardware
        run_cmd(client, "sensors | grep 'Core'", "Checking CPU Temperature")
        run_cmd(client, "cat /etc/NetworkManager/conf.d/wifi-powersave.conf", "Verifying WiFi Power Config")
        run_cmd(client, "systemctl is-active watchdog", "Verifying Watchdog Service")
        
        # 5. Connectivity
        run_cmd(client, "ping -c 3 8.8.8.8", "Testing Internet Connectivity")

        print("\n✅ Health Check Complete!")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
