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

# Check browser installation
def check_browser_installation():
    """Check if Chromium is properly installed"""
    try:
        browser_paths = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome"
        ]
        
        browser_info = {
            "installed": False,
            "path": None,
            "version": "Unknown",
            "chromedriver_available": False,
            "browser_type": "None"
        }
        
        # Find browser binary
        for path in browser_paths:
            if os.path.exists(path):
                browser_info["installed"] = True
                browser_info["path"] = path
                try:
                    version_output = subprocess.check_output([path, '--version'], stderr=subprocess.STDOUT, text=True)
                    browser_info["version"] = version_output.strip()
                    if "chromium" in version_output.lower():
                        browser_info["browser_type"] = "Chromium"
                    else:
                        browser_info["browser_type"] = "Chrome"
                except Exception as e:
                    browser_info["version"] = f"Error: {str(e)}"
                break
        
        # Check chromedriver
        try:
            chromedriver_output = subprocess.check_output(['chromedriver', '--version'], stderr=subprocess.STDOUT, text=True)
            browser_info["chromedriver_available"] = True
        except:
            # Try alternative chromedriver path
            try:
                chromedriver_output = subprocess.check_output(['/usr/bin/chromedriver', '--version'], stderr=subprocess.STDOUT, text=True)
                browser_info["chromedriver_available"] = True
            except:
                browser_info["chromedriver_available"] = False
            
        return browser_info
        
    except Exception as e:
        logger.error(f"Error checking browser installation: {e}")
        return {"installed": False, "path": None, "version": "Error", "chromedriver_available": False, "browser_type": "None"}

# Check browser before importing selenium
browser_status = check_browser_installation()
logger.info(f"Browser Status: {browser_status}")

# Try to import selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    SELENIUM_AVAILABLE = True
    logger.info("✅ Selenium imported successfully")
except ImportError as e:
    logger.error(f"❌ Selenium import failed: {e}")
    SELENIUM_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# Configuration
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

# Traffic Bot dengan Chromium
class TrafficBot:
    def __init__(self, session_id, profile_data, target_url):
        self.session_id = session_id
        self.profile_data = profile_data
        self.target_url = target_url
        self.driver = None
        self.is_running = True
        
    def setup_driver(self):
        """Setup Chromium driver"""
        if not SELENIUM_AVAILABLE:
            self.log_step("setup_driver", "error", "Selenium not available")
            return False
            
        browser_status = check_browser_installation()
        if not browser_status["installed"]:
            self.log_step("setup_driver", "error", f"Browser not installed: {browser_status}")
            return False
            
        try:
            chrome_options = Options()
            
            # Set browser binary location explicitly
            if browser_status["path"]:
                chrome_options.binary_location = browser_status["path"]
                logger.info(f"Using browser: {browser_status['browser_type']} at {browser_status['path']}")
            
            # Essential options
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-gpu")
            
            # Performance optimizations
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-javascript")
            
            # Anti-detection
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # User agent
            user_agent = self.profile_data.get('user_agent', UserAgentGenerator.generate_desktop())
            chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # Window size
            if self.profile_data.get('profile_type') == 'mobile':
                chrome_options.add_argument("--window-size=375,812")
            else:
                chrome_options.add_argument("--window-size=1024,768")
                
            logger.info("Starting browser driver...")
            
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
            except Exception as e:
                logger.error(f"Driver creation failed: {e}")
                return False
            
            # Set timeouts
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)
            
            # Anti-detection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Browser driver started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Driver setup failed: {str(e)}")
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
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            return True
        except Exception as e:
            self.log_step("scrolling", "error", f"Scrolling error: {str(e)}")
            return False
    
    def run_session(self):
        """Main session execution"""
        try:
            self.log_step("initializing", "running", "Session started")
            
            if not self.setup_driver():
                return
                
            # Navigate to target URL
            try:
                self.driver.get(self.target_url)
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
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("✅ Driver quit successfully")
                except Exception as e:
                    logger.error(f"Driver quit error: {e}")
            
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
    return jsonify({"status": "Traffic Bot Server is Running!"})

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    browser_status = check_browser_installation()
    return jsonify({
        "status": "healthy",
        "browser_installation": browser_status,
        "selenium_available": SELENIUM_AVAILABLE,
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(active_sessions)
    })

@app.route('/api/debug', methods=['GET'])
def debug_system():
    """Debug system information"""
    try:
        # Test browser
        browser_test = subprocess.run(['chromium', '--version'], capture_output=True, text=True)
        driver_test = subprocess.run(['chromedriver', '--version'], capture_output=True, text=True)
        
        return jsonify({
            "browser_installation": check_browser_installation(),
            "browser_test": browser_test.stdout if browser_test.returncode == 0 else f"Error: {browser_test.stderr}",
            "driver_test": driver_test.stdout if driver_test.returncode == 0 else f"Error: {driver_test.stderr}",
            "files_in_root": os.listdir('.'),
            "files_in_bin": [f for f in os.listdir('/usr/bin') if 'chrome' in f or 'chromium' in f]
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/test-browser', methods=['GET'])
def test_browser():
    """Test browser functionality"""
    if not SELENIUM_AVAILABLE:
        return jsonify({"success": False, "message": "Selenium not available"}), 500
        
    browser_status = check_browser_installation()
    if not browser_status["installed"]:
        return jsonify({"success": False, "message": "Browser not installed"}), 500
    
    try:
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        
        # Set browser binary
        if browser_status["path"]:
            chrome_options.binary_location = browser_status["path"]
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://httpbin.org/ip")
        
        result = {
            "success": True,
            "page_title": driver.title,
            "browser_type": browser_status["browser_type"],
            "status": "Browser test passed!"
        }
        
        driver.quit()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "browser_status": browser_status
        }), 500

@app.route('/api/create_session', methods=['POST'])
def create_session():
    """Create and start a new session"""
    if not SELENIUM_AVAILABLE:
        return jsonify({"success": False, "message": "Selenium not available"}), 500
        
    browser_status = check_browser_installation()
    if not browser_status["installed"]:
        return jsonify({"success": False, "message": f"Browser not installed: {browser_status}"}), 500
    
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
    print("🚀 TRAFFIC BOT STARTING...")
    print("=" * 60)
    
    browser_status = check_browser_installation()
    print(f"🔧 Browser Installed: {browser_status['installed']}")
    print(f"🔧 Browser Type: {browser_status['browser_type']}")
    print(f"🔧 Browser Path: {browser_status['path']}")
    print(f"🔧 Browser Version: {browser_status['version']}")
    print(f"🔧 ChromeDriver Available: {browser_status['chromedriver_available']}")
    print(f"🔧 Selenium Available: {SELENIUM_AVAILABLE}")
    print("=" * 60)
    
    if not browser_status['installed']:
        print("❌ WARNING: Browser not found! Sessions will fail.")
    else:
        print("✅ Browser is ready!")
    
    app.run(host='0.0.0.0', port=port, debug=False)
