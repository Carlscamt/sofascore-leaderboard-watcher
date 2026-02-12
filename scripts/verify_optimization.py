import paramiko

HOST = "192.168.123.2"
USER = "carlscamt"
PASS = "7373"

def run_cmd(client, cmd, desc):
    print(f"\n🔍 {desc}")
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
        
        run_cmd(client, "iwconfig 2>&1", "WiFi Configuration")
        run_cmd(client, "sudo tlp-stat -s", "TLP Status")
        run_cmd(client, "sudo systemctl status watchdog --no-pager", "Watchdog Service")
        run_cmd(client, "sensors", "Thermal Sensors")
        run_cmd(client, "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "CPU Governor")
        run_cmd(client, "cat /etc/NetworkManager/conf.d/wifi-powersave.conf", "WiFi Power Save Config")
        run_cmd(client, "grep -E 'HandleLidSwitch|IdleAction' /etc/systemd/logind.conf", "Logind Power Settings")
        run_cmd(client, "systemctl status sleep.target suspend.target", "Sleep Targets Status")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
