import paramiko

HOST = "192.168.123.2"
USER = "carlscamt"
PASS = "7373"

def run_cmd(client, cmd, desc):
    print(f"\n🖥️ {desc}")
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
        
        # Method 1: Console Blanking (setterm) - For TTY
        # This sets the console to blank after 1 minute of inactivity
        run_cmd(client, "sudo sh -c 'setterm --blank 1 --powerdown 1 > /dev/tty1'", "Enabling Console Blanking (TTY1)")

        # Method 2: Backlight Brightness -> 0
        # Find backlight device
        # usually /sys/class/backlight/intel_backlight or acpi_video0
        cmd = """
        for bl in /sys/class/backlight/*; do
            [ -d "$bl" ] || continue
            echo "Setting brightness to 0 for $bl"
            echo 0 | sudo tee "$bl/brightness"
        done
        """
        run_cmd(client, cmd, "Setting Backlight to 0")
        
        # Method 3: vbetool (Hardware DPMS) - Requires install
        # This is the most effective "Screen Off" command
        run_cmd(client, "sudo apt update && sudo apt install -y vbetool", "Installing vbetool")
        run_cmd(client, "sudo vbetool dpms off", "Turning Screen OFF (vbetool)")
        
        print("\n✅ Screen commands sent. If the screen is still on, it might require a reboot or physical lid close (which is now safe).")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
