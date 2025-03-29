import os
import requests
import schedule
import time
import threading
from flask import Flask, render_template, jsonify
from collections import deque
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv # Optional: for .env file

# Load environment variables from .env file if it exists (optional)
load_dotenv()

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- Configuration ---
# IMPORTANT: Verify the internal ports for each service! Use environment variables or update directly.
SERVICES = [
    {
        "id": "beszel",
        "name": "Beszel (Status)",
        "display_url": os.environ.get("URL_BESZEL", "https://status.niksindriksons.com"),
        "check_url": os.environ.get("CHECK_URL_BESZEL", "http://10.42.42.5:80"), # ASSUMED PORT 80
    },
    {
        "id": "openwebui",
        "name": "OpenWebUI",
        "display_url": os.environ.get("URL_OPENWEBUI", "https://ai.niksindriksons.com"),
        "check_url": os.environ.get("CHECK_URL_OPENWEBUI", "http://10.42.42.10:8080"), # ASSUMED PORT 8080
    },
    {
        "id": "litellm",
        "name": "LiteLLM",
        "display_url": os.environ.get("URL_LITELLM", "https://llm.niksindriksons.com"),
        "check_url": os.environ.get("CHECK_URL_LITELLM", "http://10.42.42.9:8000"), # ASSUMED PORT 8000
    },
    {
        "id": "n8n",
        "name": "n8n",
        "display_url": os.environ.get("URL_N8N", "https://n8n.niksindriksons.com"),
        "check_url": os.environ.get("CHECK_URL_N8N", "http://10.42.42.8:5678"), # DEFAULT N8N PORT 5678
    },
    {
        "id": "nextcloud",
        "name": "Nextcloud",
        "display_url": os.environ.get("URL_NEXTCLOUD", "https://cloud.niksindriksons.com"),
        "check_url": os.environ.get("CHECK_URL_NEXTCLOUD", "http://10.42.42.4:80"), # ASSUMED PORT 80
    },
    {
        "id": "vaultwarden",
        "name": "Vaultwarden",
        "display_url": os.environ.get("URL_VAULTWARDEN", "https://vault.niksindriksons.com"),
        "check_url": os.environ.get("CHECK_URL_VAULTWARDEN", "http://10.42.42.7:80"), # ASSUMED PORT 80
    },
    {
        "id": "adguard",
        "name": "AdGuard Home",
        "display_url": os.environ.get("URL_ADGUARD", "https://adguard.niksindriksons.com"),
        "check_url": os.environ.get("CHECK_URL_ADGUARD", "http://10.42.42.3:80"), # ASSUMED PORT 80
    },
]

# Initialize status dictionary
SERVICE_STATUS = {
    service["id"]: {
        "name": service["name"],
        "status": "checking",
        "display_url": service["display_url"],
        "check_url": service["check_url"],
        "history": deque(maxlen=30) # Keep last 30 checks
    } for service in SERVICES
}
HISTORY_LENGTH = 30
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", 5))
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", 10))

# --- Status Checking Logic ---
def check_service(service_id, name, url_to_check):
    """Checks a single service using its internal URL and updates its status and history."""
    timestamp = datetime.now(timezone.utc).isoformat()
    current_status = "checking" # Default intermediate status for logic

    try:
        # Check the internal URL (likely HTTP)
        # Add headers if needed, e.g., {'Host': 'internal-service-name'} if required by the service
        response = requests.get(url_to_check, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        # logging.info(f"Checking {name} ({url_to_check})... Status Code: {response.status_code}")

        # Consider redirects (3xx) as online for web services
        if 200 <= response.status_code < 400:
            current_status = "online"
        else:
            current_status = f"error_{response.status_code}"

    except requests.exceptions.Timeout:
        current_status = "offline_timeout"
        logging.warning(f"Check failed for {name} ({url_to_check}): Timeout after {REQUEST_TIMEOUT_SECONDS}s")
    except requests.exceptions.ConnectionError as e:
         current_status = "offline_conn_error"
         logging.error(f"Check failed for {name} ({url_to_check}): Connection Error - {e}")
    except requests.exceptions.RequestException as e:
        current_status = "offline_error"
        logging.error(f"Check failed for {name} ({url_to_check}): Generic Request Error - {e}")
    except Exception as e:
        current_status = "offline_unknown_error"
        logging.error(f"Check failed for {name} ({url_to_check}): Unexpected Error - {e}", exc_info=True)


    # Update status and history using the determined status
    SERVICE_STATUS[service_id]["status"] = current_status
    SERVICE_STATUS[service_id]["history"].append((timestamp, current_status))
    # logging.info(f"Finished check for {name}: {current_status}")


def check_all_services():
    """Runs checks for all configured services concurrently."""
    logging.info(f"Running {len(SERVICES)} scheduled checks...")
    threads = []
    for service in SERVICES:
        thread = threading.Thread(target=check_service, args=(service["id"], service["name"], service["check_url"]), daemon=True)
        threads.append(thread)
        thread.start()

    # Optional: Join threads if you need to wait for all checks in one cycle
    # for t in threads:
    #     t.join(timeout=REQUEST_TIMEOUT_SECONDS + 2)
    # logging.info("Scheduled check cycle complete.")


def run_scheduler():
    """Runs the scheduler in a loop after an initial check."""
    logging.info("Scheduler thread started.")
    logging.info("Performing initial service checks...")
    check_all_services() # Run checks immediately on start
    time.sleep(2) # Give initial checks a moment to complete potentially

    # Schedule subsequent checks
    logging.info(f"Scheduling checks every {CHECK_INTERVAL_MINUTES} minutes.")
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_all_services)

    while True:
        schedule.run_pending()
        time.sleep(1)

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main HTML dashboard page."""
    # Pass only needed info for initial HTML rendering
    initial_services = [{"id": s["id"], "name": s["name"]} for s in SERVICES]
    return render_template('index.html', services=initial_services)

@app.route('/api/status')
def api_status():
    """Returns the current status and history of all services."""
    response_data = {}
    # Make a copy to avoid issues if checks run during request processing
    current_statuses = SERVICE_STATUS.copy()
    for service_id, data in current_statuses.items():
        response_data[service_id] = {
            "name": data["name"],
            "status": data["status"],
            "display_url": data["display_url"], # Use the public URL for links
            "history": list(data["history"]) # Convert deque to list for JSON
        }
    return jsonify(response_data)

# --- Main Execution ---
if __name__ == '__main__':
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # Gunicorn will run the app based on the Dockerfile CMD
    # If running locally directly (python app.py):
    # logging.info("Starting Flask development server...")
    # app.run(debug=False, host='0.0.0.0', port=5000) # Use debug=True only for active development
    # Note: Gunicorn is specified in the Dockerfile CMD for production runs
    pass # Necessary if not running app.run here