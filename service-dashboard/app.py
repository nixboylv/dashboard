# --- app.py (Correct structure for Gunicorn --preload) ---

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

# Configure basic logging (include thread name)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(threadName)s] %(levelname)s - %(message)s')

# Create Flask app instance FIRST
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
    logging.info(f"--> Entered check_service for [{name}] ({url_to_check})") # Log entry

    response = None # Initialize response variable

    try:
        logging.info(f"    [{name}] Attempting requests.get...")
        response = requests.get(url_to_check, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        logging.info(f"    [{name}] requests.get completed. Status Code: {response.status_code}") # Log status code

        # Consider redirects (3xx) as online for web services
        if 200 <= response.status_code < 400:
            current_status = "online"
            logging.info(f"    [{name}] Status determined: online")
        else:
            current_status = f"error_{response.status_code}"
            logging.warning(f"    [{name}] Status determined: {current_status}") # Log non-2xx/3xx status

    except requests.exceptions.Timeout:
        current_status = "offline_timeout"
        logging.warning(f"    [{name}] EXCEPTION: Timeout after {REQUEST_TIMEOUT_SECONDS}s")
    except requests.exceptions.ConnectionError as e:
         current_status = "offline_conn_error"
         logging.error(f"    [{name}] EXCEPTION: Connection Error - {e}")
    except requests.exceptions.RequestException as e:
        current_status = "offline_error"
        logging.error(f"    [{name}] EXCEPTION: Generic Request Error - {e}")
    except Exception as e:
        current_status = "offline_unknown_error"
        logging.error(f"    [{name}] EXCEPTION: Unexpected Error - {e}", exc_info=True) # Log full traceback for unexpected errors


    # --- Update Status ---
    try:
        # Use a lock if you suspect race conditions, but for simple updates it might be overkill
        # with status_lock: # Example if using threading.Lock()
        logging.info(f"    [{name}] Updating SERVICE_STATUS. Determined Status = '{current_status}'. Previous = '{SERVICE_STATUS.get(service_id, {}).get('status', 'N/A')}'.") # Safer access
        if service_id in SERVICE_STATUS: # Ensure key exists before updating
             SERVICE_STATUS[service_id]["status"] = current_status
             SERVICE_STATUS[service_id]["history"].append((timestamp, current_status))
             logging.info(f"    [{name}] SERVICE_STATUS updated. New Status = '{SERVICE_STATUS[service_id]['status']}'. History length = {len(SERVICE_STATUS[service_id]['history'])}.")
        else:
             logging.error(f"    [{name}] CRITICAL: service_id '{service_id}' not found in SERVICE_STATUS dictionary!")
    except Exception as e:
        logging.error(f"    [{name}] CRITICAL: Failed to update SERVICE_STATUS dictionary! - {e}", exc_info=True)
    # --- End Update Status ---

    logging.info(f"<-- Exiting check_service for [{name}]") # Log exit


# --- Scheduler Setup and Execution ---
def check_all_services():
    """Runs checks for all configured services concurrently."""
    logging.info(">>> Entered check_all_services") # Log entry
    threads = []
    for service in SERVICES:
        # Make sure SERVICE_STATUS has been initialized before starting threads
        if service["id"] in SERVICE_STATUS:
            thread = threading.Thread(
                target=check_service,
                args=(service["id"], service["name"], service["check_url"]),
                daemon=True,
                name=f"Check-{service['id']}" # Name threads for easier log reading
            )
            threads.append(thread)
            logging.info(f"    Starting thread for [{service['name']}]")
            thread.start()
        else:
            logging.error(f"    Skipping thread for unknown service_id [{service['id']}] during check_all_services")
    logging.info("<<< Exiting check_all_services (threads started)")


def run_scheduler():
    """Runs the scheduler loop after performing an initial check."""
    logging.info("--- Entered run_scheduler ---") # Log entry
    logging.info("    Performing initial service checks...")
    check_all_services() # Run checks immediately on start
    time.sleep(2) # Give initial checks a moment

    # Schedule subsequent checks
    logging.info(f"    Scheduling checks every {CHECK_INTERVAL_MINUTES} minutes.")
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_all_services)
    logging.info("--- Scheduler setup complete, entering run_pending loop ---")
    loop_count = 0
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
            loop_count += 1
            if loop_count % 300 == 0: # Log roughly every 5 minutes that the loop is alive
                logging.info("    Scheduler loop is alive...")
        except Exception as e:
            logging.error(f"--- CRITICAL ERROR IN SCHEDULER LOOP: {e} ---", exc_info=True)
            time.sleep(10) # Avoid spamming logs if loop itself errors


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
    # Make a copy to avoid potential issues if checks run during request processing
    # Using a lock would be safer for production, but copy is simpler for now
    current_statuses = SERVICE_STATUS.copy()
    for service_id, data in current_statuses.items():
        response_data[service_id] = {
            "name": data.get("name", "Unknown"), # Use .get for safer access
            "status": data.get("status", "error_unknown"),
            "display_url": data.get("display_url", "#"),
            "history": list(data.get("history", [])) # Ensure history is a list
        }
    return jsonify(response_data)


# --- Application Initialization ---
# This code runs ONCE when the application is loaded by Gunicorn (using --preload)
# It also runs if you execute 'python app.py' directly
# Using a simple flag to prevent double execution in Flask debug reloader mode
app_initialized = False
if not app_initialized:
    logging.info("****** Initializing Dashboard Application ******")
    logging.info("****** Starting background scheduler thread ******")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True, name="SchedulerThread")
    scheduler_thread.start()
    app_initialized = True # Set flag
else:
     logging.info("****** Skipping background scheduler start (already initialized) ******")


# This block is now only relevant for direct execution: `python app.py`
if __name__ == '__main__':
    # This part is NOT run by Gunicorn
    logging.info("****** Running Flask development server directly (scheduler already started) ******")
    # Note: Debug mode will cause the initialization block above to run twice without extra checks.
    # The 'app_initialized' flag handles this.
    app.run(debug=False, host='0.0.0.0', port=5000) # Set debug=True only for active development