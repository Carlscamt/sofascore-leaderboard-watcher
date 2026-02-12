import paramiko
import time

HOST = "192.168.123.2"
USER = "carlscamt"
PASS = "7373"

def run_remote_command(ssh, cmd, description, ignore_errors=False):
    print(f"\n🚀 {description}...")
    print(f"   Command: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    
    # Handle sudo password
    if "sudo" in cmd:
        stdin.write(f"{PASS}\n")
        stdin.flush()
        
    # Live output
    while True:
        line = stdout.readline()
        if not line: break
        print(f"   {line.strip()}")
        
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        if ignore_errors:
            print(f"⚠️ Failed (Exit Code: {exit_status}) - Ignoring")
            return True
        print(f"❌ Failed (Exit Code: {exit_status})")
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
        
        # 1. WiFi Power Management
        # Detect functionality first? Assuming wlan0 or similar.
        # We can try 'iwconfig' to find wireless interface
        
        # Priority 1: Network Reliability
        cmds = [
            # Disable WiFi Power Save (Immediate)
            # Find interface first - usually starts with wl
            # We'll try a generic approach or assume wlan0
            ("sudo iw dev $(iw dev | awk '$1==\"Interface\"{print $2}') set power_save off", "Disabling WiFi Power Save (Immediate)"),
            
            # Persistent WiFi Power Save Disable
            ("""echo "[connection]
wifi.powersave = 2" | sudo tee /etc/NetworkManager/conf.d/wifi-powersave.conf""", "Configuring Persistent WiFi Power Save"),
            ("sudo systemctl restart NetworkManager", "Restarting NetworkManager"),
            
            # 2. Install Tools
            ("sudo apt update && sudo apt install -y tlp tlp-rdw thermald lm-sensors watchdog", "Installing Power/Thermal Tools"),
            
            # 3. Configure TLP (Battery Limit)
            # Check if tlp.conf exists
            # We can use sed to uncomment/set lines
            ("sudo sed -i 's/#START_CHARGE_THRESH_BAT0=75/START_CHARGE_THRESH_BAT0=50/' /etc/tlp.conf", "Setting Start Charge Threshold"),
            ("sudo sed -i 's/#STOP_CHARGE_THRESH_BAT0=80/STOP_CHARGE_THRESH_BAT0=80/' /etc/tlp.conf", "Setting Stop Charge Threshold"),
             # Ensure TLP handles WiFi power too? TLP often enables it by default, we want it OFF.
            ("sudo sed -i 's/#WIFI_PWR_ON_AC=on/WIFI_PWR_ON_AC=off/' /etc/tlp.conf", "Disabling WiFi Power Save in TLP (AC)"),
            ("sudo sed -i 's/#WIFI_PWR_ON_BAT=on/WIFI_PWR_ON_BAT=off/' /etc/tlp.conf", "Disabling WiFi Power Save in TLP (BAT)"),
            ("sudo tlp start", "Starting TLP"),
            
            # 4. Thermal Management
            ("yes | sudo sensors-detect", "Detecting Sensors (Auto-Yes)"),
            ("sudo systemctl enable thermald", "Enabling Thermald"),
            ("sudo systemctl start thermald", "Starting Thermald"),
            
            # 5. Watchdog Configuration
            # Detect network interface for watchdog interactively or assume wlan0/enp* matches
            # We'll try to find the default route interface
            # "watchdog-device = /dev/watchdog"
            ("sudo sed -i 's/#watchdog-device/watchdog-device/' /etc/watchdog.conf", "Configuring Watchdog Device"),
            ("sudo sed -i 's/#watchdog-timeout = 60/watchdog-timeout = 60/' /etc/watchdog.conf", "Configuring Watchdog Timeout"),
            ("sudo sed -i 's/#min-memory = 1/min-memory = 100/' /etc/watchdog.conf", "Configuring Watchdog Min Memory"),
            
            # Explicitly monitor wlan0 (or whatever is active)
            # We use a bit of shell magic to get the active interface
            # Note: We use 'ip -o -4 route show to default' to be more precise
            ("""IFACE=$(ip -o -4 route show to default | awk '{print $5}' | head -n1)
if [ -n "$IFACE" ]; then
    # We use a more flexible regex for sed to catch commented lines with spaces
    sudo sed -i "s/#\s*interface\s*=.*/interface = $IFACE/" /etc/watchdog.conf
    echo "Configured watchdog for interface $IFACE"
fi""", "Configuring Watchdog Interface"),

            # Thermal monitoring
            ("""TEMP_SENSOR=$(find /sys/class/thermal -name "temp" 2>/dev/null | grep "thermal_zone" | head -n1)
if [ -n "$TEMP_SENSOR" ]; then
    # Use | delimiter for sed because path contains /
    sudo sed -i "s|#\s*temperature-sensor\s*=.*|temperature-sensor = $TEMP_SENSOR|" /etc/watchdog.conf
    sudo sed -i "s/#\s*max-temperature\s*=.*/max-temperature = 90/" /etc/watchdog.conf
    echo "Configured watchdog for thermal sensor: $TEMP_SENSOR"
fi""", "Configuring Watchdog Temperature Sensor"),

            ("sudo systemctl restart watchdog", "Restarting Watchdog"),
            ("sudo systemctl enable watchdog", "Enabling Watchdog"),
            
            # 6. Kernel Panic Reboot
            ("""echo "kernel.panic = 10
kernel.panic_on_oops = 1" | sudo tee /etc/sysctl.d/99-panic-reboot.conf""", "Configuring Kernel Panic Reboot"),
            ("sudo sysctl -p /etc/sysctl.d/99-panic-reboot.conf", "Applying Sysctl Changes"),
            
            # 7. Disable Sleep/Suspend (Crucial for 24/7 operation)
            # Mask sleep targets to prevent manual or automatic suspension
            ("sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target", "Masking Sleep/Suspend Targets"),
            
            # Configure logind.conf to ignore lid close and idle
            ("sudo sed -i 's/#HandleLidSwitch=suspend/HandleLidSwitch=ignore/' /etc/systemd/logind.conf", "Ignoring Lid Switch"),
            ("sudo sed -i 's/#HandleLidSwitchDocked=suspend/HandleLidSwitchDocked=ignore/' /etc/systemd/logind.conf", "Ignoring Lid Switch (Docked)"),
            ("sudo sed -i 's/#IdleAction=ignore/IdleAction=ignore/' /etc/systemd/logind.conf", "Ignoring Idle Action"),
            
            # Restart logind to apply changes
            ("sudo systemctl restart systemd-logind", "Restarting Login Service"),

            # 8. Verification Logs
            ("iwconfig 2>&1 | grep 'Power Management'", "Verifying WiFi Power Management"),
            ("sudo tlp-stat -s | grep 'Mode'", "Verifying TLP Status"),
            ("sensors | grep 'Core'", "Verifying Temperature"),
            ("systemctl status sofascore-monitor --no-pager", "Verifying Service Status"),
        ]

        for cmd, desc in cmds:
            # We ignore errors on 'sensors-detect' or similar if they are interactive or quirky, 
            # but generally we want to know.
            # sensors-detect output might be weird via paramiko execution.
            # actually 'yes | sudo sensors-detect' usually works.
            run_remote_command(client, cmd, desc, ignore_errors=False)

    except Exception as e:
        print(f"❌ Connection/Optimization Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
