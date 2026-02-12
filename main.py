import sys
import logging
from pathlib import Path

# Add src to path
current_dir = Path(__file__).parent.resolve()
src_path = current_dir / "src"
sys.path.append(str(src_path))

# Configure logging
# Force UTF-8 for Windows console
if sys.platform == "win32":
    # Reconfigure stdout/stderr to use utf-8
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout), # Explicitly use reconfigured stdout
        logging.FileHandler("monitor.log", encoding='utf-8') # Force UTF-8 for file
    ]
)

from sofascore_monitor.monitor import Monitor
import asyncio

def main():
    try:
        monitor = Monitor()
        asyncio.run(monitor.run())  # Run the async loop
    except KeyboardInterrupt:
        print("\nStopping monitor...")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
