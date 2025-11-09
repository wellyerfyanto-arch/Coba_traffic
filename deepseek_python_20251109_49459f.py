import os
import json
import time
import random
import threading
import logging
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set Playwright browsers path
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/app/ms-playwright'

# Check Playwright installation
def check_playwright_installation():
    """Check if Playwright and browsers are properly installed"""
    try:
        # Check if playwright is available
        playwright_version = subprocess.run(['playwright', '--version'], capture_output=True, text=True)
        
        # Check if chromium is installed
        chromium_path = "/app/ms-playwright/chromium-*/chrome-linux/chrome"
        chromium_exists = subprocess.run(f"ls {chromium_path}", shell=True, capture_output=True, text=True)
        
        return {
            "playwright_available": playwright_version.returncode == 0,
            "playwright_version": playwright_version.stdout.strip() if playwright_version.returncode == 0 else "Not found",
            "chromium_installed": chromium_exists.returncode == 0,
            "chromium_path": chromium_exists.stdout.strip() if chromium_exists.returncode == 0 else "Not found",
            "browsers_path": os.environ.get('PLAYWRIGHT_BROWSERS_PATH', 'Not set')
        }
    except Exception as e:
        return {
            "playwright_available": False,
            "playwright_version": f"Error: {str(e)}",
            "chromium_installed": False,
            "chromium_path": f"Error: {str(e)}",
            "browsers_path": os.environ.get('PLAYWRIGHT_BROWSERS_PATH', 'Not set')
        }

# Try to import Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
    logger.info("✅ Playwright imported successfully")
except ImportError as e:
    logger.error(f"❌ Playwright import failed: {e}")
    PLAYWRIGHT_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# ==============================
# CONFIGURATION
# ==============================

DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)

def read_json(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except:
        return {"sessions": [], "session_counter": 0}

def write_json(data, file_path):
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Write error: {e}")
        return False

# Initialize data files
if not os.path.exists('data/sessions.json'):
    write_json({"sessions": [], "session_counter": 0}, 'data/sessions.json')
if not os.path.exists('data/logs.json'):
    write_json({"logs": []}, 'data/logs.json')

# User Agent Generator
class UserAgentGenerator:
    @staticmethod
    def generate_mobile():
        agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 12; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36"
        ]
        return random.choice(agents)
    
    @staticmethod 
    def generate_desktop():
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        ]
        return random.choice(agents)

# Traffic Bot dengan Playwright
class TrafficBot:
    def __init__(self, session_id, profile_data, target_url):
        self.session_id = session_id
        self.profile_data = profile_data
        self.target_url = target_url
        self.playwright = None
        self.browser = None
        self.page = None
        self.is_running = True
        
    def setup_browser(self):
        """Setup browser dengan Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            self.log_step("setup_browser", "error", "Playwright not available")
            return False
            
        try:
            logger.info("🔄 Starting Playwright browser...")
            
            # Start Playwright
            self.playwright = sync_playwright().start()
            
            # Launch browser dengan options yang robust
            browser_launch_options = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",
                    "--no-zygote",
                    "--disable-setuid-sandbox"
                ]
            }
            
            self.browser = self.playwright.chromium.launch(**browser_launch_options)
            
            # Create context dengan user agent
            context_options = {
                "user_agent": self.profile_data.get('user_agent', UserAgentGenerator.generate_desktop()),
                "viewport": {"width": 1920, "height": 1080} if self.profile_data.get('profile_type') == 'desktop' else {"width": 375, "height": 812},
                "ignore_https_errors": True
            }
            
            context = self.browser.new_context(**context_options)
            
            # Create page
            self.page = context.new_page()
            
            # Set timeout
            self.page.set_default_timeout(30000)
            self.page.set_default_navigation_timeout(30000)
            
            logger.info("✅ Playwright browser started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Browser setup failed: {str(e)}")
            self.log_step("setup_browser", "error", f"Browser setup failed: {str(e)}")
            return False
    
    def log_step(self, step, status, message):
        """Log session steps"""
        log_entry = {
            "log_id": f"log_{int(time.time() * 1000)}",
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "status": status,
            "message": message
        }
        
        logs_data = read_json('data/logs.json')
        logs_data.setdefault("logs", []).append(log_entry)
        write_json(logs_data, 'data/logs.json')
        
        logger.info(f"📝 {step} - {status}: {message}")
    
    def human_like_scroll(self):
        """Simple scroll simulation"""
        try:
            # Scroll down
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
            time.sleep(2)
            # Scroll to bottom
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            # Scroll back to top
            self.page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)
            return True
        except Exception as e:
            self.log_step("scrolling", "error", f"Scrolling error: {str(e)}")
            return False
    
    def run_session(self):
        """Main session execution"""
        try:
            self.log_step("initializing", "running", "Session started")
            
            if not self.setup_browser():
                return
                
            # Navigate to target URL
            try:
                self.page.goto(self.target_url, wait_until="domcontentloaded")
                self.log_step("navigation", "success", f"Loaded: {self.target_url}")
                time.sleep(3)
                
                # Perform scrolling
                self.human_like_scroll()
                self.log_step("scrolling", "success", "Scrolling completed")
                
                self.log_step("completed", "success", "Session completed successfully")
                
            except Exception as e:
                self.log_step("navigation", "error", f"Navigation failed: {str(e)}")
                
        except Exception as e:
            self.log_step("error", "failed", f"Session failed: {str(e)}")
        finally:
            # Cleanup
            try:
                if self.browser:
                    self.browser.close()
                if self.playwright:
                    self.playwright.stop()
                logger.info("✅ Browser closed successfully")
            except Exception as e:
                logger.error(f"Browser cleanup error: {e}")
            
            # Update session status
            sessions_data = read_json('data/sessions.json')
            for session in sessions_data.get("sessions", []):
                if session.get("session_id") == self.session_id:
                    session["status"] = "completed"
                    session["progress"] = 100
                    break
            write_json(sessions_data, 'data/sessions.json')

# Flask Routes
active_sessions = {}

@app.route('/')
def home():
    return jsonify({"status": "Traffic Bot with Playwright is Running!"})

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    playwright_status = check_playwright_installation()
    return jsonify({
        "status": "healthy",
        "playwright_available": PLAYWRIGHT_AVAILABLE,
        "playwright_installation": playwright_status,
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(active_sessions)
    })

@app.route('/api/debug-installation', methods=['GET'])
def debug_installation():
    """Debug installation details"""
    try:
        # Check various paths
        results = {}
        
        # Check playwright
        playwright_check = subprocess.run(['playwright', '--version'], capture_output=True, text=True)
        results['playwright'] = playwright_check.stdout if playwright_check.returncode == 0 else f"Error: {playwright_check.stderr}"
        
        # Check browsers directory
        browsers_path = "/app/ms-playwright"
        if os.path.exists(browsers_path):
            results['browsers_directory'] = f"Exists: {os.listdir(browsers_path)}"
        else:
            results['browsers_directory'] = "Directory not found"
            
        # Check chromium executable
        chromium_check = subprocess.run("find /app/ms-playwright -name 'chrome' -type f", shell=True, capture_output=True, text=True)
        results['chromium_executable'] = chromium_check.stdout if chromium_check.returncode == 0 else f"Error: {chromium_check.stderr}"
        
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/test-playwright', methods=['GET'])
def test_playwright():
    """Test Playwright functionality"""
    if not PLAYWRIGHT_AVAILABLE:
        return jsonify({"success": False, "message": "Playwright not available"}), 500
    
    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            
            # Create page
            page = browser.new_page()
            
            # Navigate to test page
            page.goto("https://httpbin.org/ip", wait_until="domcontentloaded")
            
            result = {
                "success": True,
                "page_title": page.title(),
                "status": "Playwright test passed!",
                "message": "Browser automation is working correctly"
            }
            
            browser.close()
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"Playwright test error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "installation_status": check_playwright_installation()
        }), 500

@app.route('/api/create_session', methods=['POST'])
def create_session():
    """Create and start a new session"""
    if not PLAYWRIGHT_AVAILABLE:
        return jsonify({"success": False, "message": "Playwright not available"}), 500
    
    playwright_status = check_playwright_installation()
    if not playwright_status["chromium_installed"]:
        return jsonify({"success": False, "message": f"Chromium not installed: {playwright_status}"}), 500
    
    try:
        data = request.get_json()
        sessions_data = read_json('data/sessions.json')
        
        session_id = f"sess_{sessions_data['session_counter'] + 1:03d}"
        profile_type = data.get('profile_type', 'desktop')
        
        profile_data = {
            "profile_name": f"{profile_type}_profile_{sessions_data['session_counter'] + 1}",
            "profile_type": profile_type,
            "user_agent": UserAgentGenerator.generate_mobile() if profile_type == 'mobile' else UserAgentGenerator.generate_desktop()
        }
        
        session_entry = {
            "session_id": session_id,
            "profile_name": profile_data['profile_name'],
            "target_url": data.get('target_url', 'https://example.com'),
            "status": "starting",
            "start_time": datetime.now().isoformat(),
            "progress": 0
        }
        
        sessions_data['sessions'].append(session_entry)
        sessions_data['session_counter'] += 1
        write_json(sessions_data, 'data/sessions.json')
        
        # Start bot session
        bot = TrafficBot(session_id, profile_data, data.get('target_url', 'https://example.com'))
        active_sessions[session_id] = bot
        
        thread = threading.Thread(target=bot.run_session)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "message": "Session started successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all sessions"""
    try:
        sessions_data = read_json('data/sessions.json')
        return jsonify(sessions_data.get('sessions', []))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get session logs"""
    try:
        logs_data = read_json('data/logs.json')
        return jsonify(logs_data.get('logs', []))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🚀 TRAFFIC BOT WITH PLAYWRIGHT STARTING...")
    print("=" * 60)
    
    playwright_status = check_playwright_installation()
    print(f"🔧 Playwright Available: {PLAYWRIGHT_AVAILABLE}")
    print(f"🔧 Playwright Version: {playwright_status['playwright_version']}")
    print(f"🔧 Chromium Installed: {playwright_status['chromium_installed']}")
    print(f"🔧 Browsers Path: {playwright_status['browsers_path']}")
    print("=" * 60)
    
    if not playwright_status['chromium_installed']:
        print("❌ WARNING: Chromium not found! Sessions will fail.")
        print("💡 TIP: Check build logs for installation errors")
    else:
        print("✅ Playwright and Chromium are ready!")
    
    app.run(host='0.0.0.0', port=port, debug=False)