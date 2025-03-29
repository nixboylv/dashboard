import os
import requests
import schedule
import time
import threading
from flask import Flask, render_template, jsonify
from collections import deque # Efficient for fixed-size history
from datetime import datetime, timezone

app = Flask(__name__)

# --- Configuration ---
# Use environment variables or configure directly
# Ensure URLs start with http:// or https://
SERVICES = [
    {"name": "Beszel (Status)", "url": os.environ.get("URL_BESZEL", "https://status.niksindriksons.com")},
    {"name": "OpenWebUI", "url": os.environ.get("URL_OPENWEBUI", "https://ai.niksindriksons.com")},
    {"name": "LiteLLM", "url": os.environ.get("URL_LITELLM", "https://llm.niksindriksons.com")}, # Assuming it has a web endpoint to ping
    {"name": "n8n", "url": os.environ.get("URL_N8N", "https://n8n.niksindriksons.com")},
    {"name": "Nextcloud", "url": os.environ.get("URL_NEXTCLOUD", "https://cloud.niksindriksons.com")},
    {"name": "Vaultwarden", "url": os.environ.get("URL_VAULTWARDEN", "https://vault.niksindriksons.com")},
    {"name": "AdGuard Home", "url": os.environ.get("URL_ADGUARD", "https://adguard.niksindriksons.com")},
    # Add wg-easy dashboard itself if you want to monitor it too
    # {"name": "WireGuard Easy", "url": os.environ.get("URL_WG", "https://wg.niksindriksons.com")},
]

# Store status and history (limited to HISTORY_LENGTH entries)
# Format: { "service_name": {"status": "checking", "history": deque([(timestamp, status_code), ...]) } }
SERVICE_STATUS = {service["name"]: {"status": "checking", "url": service["url"], "history": deque(maxlen=20)} for service in SERVICES} # Keep last 20 checks
HISTORY_LENGTH = 20 # Match maxlen above
CHECK_INTERVAL_MINUTES = 5 # How often the backend checks
REQUEST_TIMEOUT_SECONDS = 5 # Timeout for status checks

# --- Status Checking Logic ---
def check_service(service_name, url):
    """Checks a single service and updates its status and history."""
    try:
        # Use verify=False if using self-signed certs *within* the private network, but prefer proper certs via NPM
        # Add headers if needed, e.g., User-Agent
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True, verify=True) # Set verify=False ONLY if necessary and understand the risk
        timestamp = datetime.now(timezone.utc).isoformat()

        # Consider any 2xx or 3xx status code as "online"
        if 200 <= response.status_code < 400:
            status = "online"
        else:
            status = f"error_{response.status_code}" # e.g., error_404, error_500

        SERVICE_STATUS[service_name]["status"] = status
        SERVICE_STATUS[service_name]["history"].append((timestamp, status))
        print(f"Checked {service_name}: {status}")

    except requests.exceptions.Timeout:
        timestamp = datetime.now(timezone.utc).isoformat()
        SERVICE_STATUS[service_name]["status"] = "offline_timeout"
        SERVICE_STATUS[service_name]["history"].append((timestamp, "offline_timeout"))
        print(f"Checked {service_name}: Timeout")
    except requests.exceptions.RequestException as e:
        timestamp = datetime.now(timezone.utc).isoformat()
        status = "offline_error"
        SERVICE_STATUS[service_name]["status"] = status
        SERVICE_STATUS[service_name]["history"].append((timestamp, status))
        print(f"Checked {service_name}: Error - {e}")

def check_all_services():
    """Runs checks for all configured services."""
    print(f"Running scheduled checks at {datetime.now()}")
    for service in SERVICES:
        # Run each check in a separate thread to avoid blocking if one service is slow
        thread = threading.Thread(target=check_service, args=(service["name"], service["url"]), daemon=True)
        thread.start()

def run_scheduler():
    """Runs the scheduler in a loop."""
    print("Scheduler started.")
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main HTML dashboard page."""
    return render_template('index.html', services=SERVICES) # Pass services for initial structure

@app.route('/api/status')
def api_status():
    """Returns the current status and history of all services."""
    # Convert deque to list for JSON serialization
    response_data = {}
    for name, data in SERVICE_STATUS.items():
        response_data[name] = {
            "status": data["status"],
            "url": data["url"],
            "history": list(data["history"]) # Convert deque to list
        }
    return jsonify(response_data)

# --- Main Execution ---
if __name__ == '__main__':
    # Perform an initial check on startup
    print("Performing initial service checks...")
    check_all_services()
    time.sleep(2) # Give initial checks a moment to potentially complete

    # Schedule background checks
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_all_services)

    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # Start Flask server (use Gunicorn in production/Docker)
    # For local testing: app.run(debug=True, host='0.0.0.0', port=5000)
    # Gunicorn will run this:
    print("Starting Flask server...")
    # Note: Gunicorn is typically used via command line, not within the script like this for production.
    # The Dockerfile CMD/ENTRYPOINT will handle running Gunicorn.
    # If running directly with `python app.py` for testing, use:
    app.run(host='0.0.0.0', port=5000)