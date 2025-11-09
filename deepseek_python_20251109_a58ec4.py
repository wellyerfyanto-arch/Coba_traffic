import os
import json
import time
import random
import threading
import logging
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check Chrome installation
def check_chrome_installation():
    """Check if Chrome is properly installed"""
    try:
        # Check multiple possible Chrome locations
        chrome_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable", 
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser"
        ]
        
        chrome_info = {
            "installed": False,
            "path": None,
            "version": "Unknown",
            "chromedriver_available": False
        }
        
        # Find Chrome binary
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_info["installed"] = True
                chrome_info["path"] = path
                try:
                    version_output = subprocess.check_output([path, '--version'], stderr=subprocess.STDOUT, text=True)
                    chrome_info["version"] = version_output.strip()
                except Exception as e:
                    chrome_info["version"] = f"Error: {str(e)}"
                break
        
        # Check chromedriver
        try:
            chromedriver_output = subprocess.check_output(['chromedriver', '--version'], stderr=subprocess.STDOUT, text=True)
            chrome_info["chromedriver_available"] = True
        except:
            chrome_info["chromedriver_available"] = False
            
        return chrome_info
        
    except Exception as e:
        logger.error(f"Error checking Chrome installation: {e}")
        return {"installed": False, "path": None, "version": "Error", "chromedriver_available": False}

# Check Chrome before importing selenium
chrome_status = check_chrome_installation()
logger.info(f"Chrome Status: {chrome_status}")

# Try to import selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (TimeoutException, NoSuchElementException, 
                                          WebDriverException, SessionNotCreatedException)
    SELENIUM_AVAILABLE = True
    logger.info("✅ Selenium imported successfully")
except ImportError as e:
    logger.error(f"❌ Selenium import failed: {e}")
    SELENIUM_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# ==============================
# CONFIGURATION
# ==============================

DATA_DIR = 'data'
PROFILES_FILE = os.path.join(DATA_DIR, 'profiles.json')
SESSIONS_FILE = os.path.join(DATA_DIR, 'sessions.json')
LOGS_FILE = os.path.join(DATA_DIR, 'logs.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# ==============================
# UTILITY FUNCTIONS
# ==============================

def read_json(file_path):
    """Read JSON file with error handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if 'profiles' in file_path:
            return {"profiles": []}
        elif 'sessions' in file_path:
            return {"sessions": [], "session_counter": 0}
        elif 'logs' in file_path:
            return {"logs": []}
        elif 'config' in file_path:
            return {
                "app_name": "Traffic Bot",
                "version": "1.0.0",
                "max_sessions": 3,
                "default_settings": {
                    "scroll_delay_min": 2,
                    "scroll_delay_max": 5,
                    "session_duration": 180,
                    "auto_clear_cache": True
                }
            }
        else:
            return {}

def write_json(data, file_path):
    """Write JSON file with error handling"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error writing to {file_path}: {e}")
        return False

def init_data_files():
    """Initialize data files if they don't exist"""
    default_files = {
        PROFILES_FILE: {"profiles": []},
        SESSIONS_FILE: {"sessions": [], "session_counter": 0},
        LOGS_FILE: {"logs": []},
        CONFIG_FILE: {
            "app_name": "Traffic Bot",
            "version": "1.0.0",
            "max_sessions": 3,
            "default_settings": {
                "scroll_delay_min": 2,
                "scroll_delay_max": 5,
                "session_duration": 180,
                "auto_clear_cache": True
            }
        }
    }
    
    for file_path, default_data in default_files.items():
        if not os.path.exists(file_path):
            write_json(default_data, file_path)
            logger.info(f"Created {file_path}")

init_data_files()

# ==============================
# USER AGENT GENERATOR
# ==============================

class UserAgentGenerator:
    @staticmethod
    def generate_mobile():
        mobile_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 12; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36"
        ]
        return random.choice(mobile_agents)
    
    @staticmethod
    def generate_desktop():
        desktop_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        ]
        return random.choice(desktop_agents)

# ==============================
# TRAFFIC BOT ENGINE - FIXED
# ==============================

class TrafficBot:
    def __init__(self, session_id, profile_data, target_url, proxy_config=None):
        self.session_id = session_id
        self.profile_data = profile_data
        self.target_url = target_url
        self.proxy_config = proxy_config
        self.driver = None
        self.is_running = True
        self.current_step = "initializing"
        
    def setup_driver(self):
        """Setup Chrome driver dengan fix untuk error 127"""
        if not SELENIUM_AVAILABLE:
            self.log_step("setup_driver", "error", "Selenium not available")
            return False
            
        # Check Chrome status again
        chrome_status = check_chrome_installation()
        if not chrome_status["installed"]:
            self.log_step("setup_driver", "error", f"Chrome not installed. Status: {chrome_status}")
            return False
            
        try:
            chrome_options = Options()
            
            # SET CHROME BINARY LOCATION EXPLICITLY
            if chrome_status["path"]:
                chrome_options.binary_location = chrome_status["path"]
                logger.info(f"Using Chrome binary at: {chrome_status['path']}")
            
            # Essential options untuk server environment - FIX FOR ERROR 127
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--remote-debugging-port=9222")
            
            # Performance optimizations
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-javascript")
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")
            
            # Anti-detection
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set user agent
            user_agent = self.profile_data.get('user_agent', UserAgentGenerator.generate_desktop())
            chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # Window size berdasarkan device type
            if self.profile_data.get('profile_type') == 'mobile':
                chrome_options.add_argument("--window-size=375,812")
            else:
                chrome_options.add_argument("--window-size=1024,768")
            
            # Proxy configuration
            if self.proxy_config and self.proxy_config.get('type') != 'direct':
                proxy_str = f"{self.proxy_config.get('host')}:{self.proxy_config.get('port')}"
                chrome_options.add_argument(f"--proxy-server={proxy_str}")
            
            # Headless mode untuk server
            chrome_options.add_argument("--headless=new")
            
            logger.info(f"🔄 Starting Chrome driver for session {self.session_id}")
            
            # Try multiple methods to create driver
            driver = None
            
            # Method 1: Try with Service
            try:
                from selenium.webdriver.chrome.service import Service
                service = Service()
                driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info("✅ Chrome driver created with Service")
            except Exception as e:
                logger.warning(f"Method 1 failed: {e}")
                
                # Method 2: Try without service
                try:
                    driver = webdriver.Chrome(options=chrome_options)
                    logger.info("✅ Chrome driver created without Service")
                except Exception as e:
                    logger.error(f"Method 2 failed: {e}")
                    self.log_step("setup_driver", "error", f"All driver creation methods failed: {str(e)}")
                    return False
            
            if driver:
                self.driver = driver
                # Set timeouts
                self.driver.set_page_load_timeout(30)
                self.driver.set_script_timeout(30)
                
                # Anti-detection scripts
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                logger.info("✅ Chrome driver started successfully")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Driver setup failed: {str(e)}")
            self.log_step("setup_driver", "error", f"Driver setup failed: {str(e)}")
            return False
    
    def log_step(self, step, status, message, details=None):
        """Log setiap step session"""
        log_entry = {
            "log_id": f"log_{int(time.time() * 1000)}",
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "status": status,
            "message": message,
            "details": details or {}
        }
        
        # Save ke logs file
        logs_data = read_json(LOGS_FILE)
        logs_data.setdefault("logs", []).append(log_entry)
        write_json(logs_data, LOGS_FILE)
        
        logger.info(f"📝 {step} - {status}: {message}")
    
    def human_like_scroll(self, scroll_count=2):
        """Simulate human-like scrolling behavior"""
        try:
            for i in range(scroll_count):
                if not self.is_running:
                    break
                    
                # Simple scroll simulation
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
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
            
            # Step 1: Setup driver
            if not self.setup_driver():
                return
            
            # Step 2: Open target URL
            if self.is_running:
                try:
                    self.driver.get(self.target_url)
                    self.log_step("opening_url", "success", f"Opened URL: {self.target_url}")
                    time.sleep(3)
                except Exception as e:
                    self.log_step("opening_url", "error", f"Failed to open URL: {str(e)}")
                    return
            
            # Step 3: Scroll around
            if self.is_running:
                self.human_like_scroll(2)
                self.log_step("scrolling", "success", "Scrolling completed")
            
            # Step 4: Mark completed
            if self.is_running:
                self.log_step("completed", "success", "Session completed successfully")
            
        except Exception as e:
            self.log_step("error", "failed", f"Session failed: {str(e)}")
        finally:
            # Cleanup
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info(f"✅ Driver quit for session {self.session_id}")
                except Exception as e:
                    logger.error(f"❌ Driver quit error: {e}")
            
            # Update session status
            sessions_data = read_json(SESSIONS_FILE)
            for session in sessions_data.get("sessions", []):
                if session.get("session_id") == self.session_id:
                    session["status"] = "completed"
                    session["progress"] = 100
                    break
            write_json(sessions_data, SESSIONS_FILE)
    
    def stop(self):
        """Stop the session"""
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

# ==============================
# FLASK ROUTES
# ==============================

active_sessions = {}

@app.route('/')
def index():
    return "Traffic Bot Server is Running!"

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check dengan detail Chrome status"""
    chrome_status = check_chrome_installation()
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "chrome_installation": chrome_status,
        "selenium_available": SELENIUM_AVAILABLE,
        "active_sessions": len(active_sessions)
    })

@app.route('/api/debug-chrome', methods=['GET'])
def debug_chrome():
    """Debug endpoint untuk cek Chrome"""
    try:
        # Test Chrome installation
        chrome_test = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
        chromedriver_test = subprocess.run(['chromedriver', '--version'], capture_output=True, text=True)
        
        return jsonify({
            "chrome_version": chrome_test.stdout.strip() if chrome_test.returncode == 0 else f"Error: {chrome_test.stderr}",
            "chromedriver_version": chromedriver_test.stdout.strip() if chromedriver_test.returncode == 0 else f"Error: {chromedriver_test.stderr}",
            "chrome_installation": check_chrome_installation()
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/create_session', methods=['POST'])
def create_session():
    """Create and start a new bot session"""
    if not SELENIUM_AVAILABLE:
        return jsonify({"success": False, "message": "Selenium not available"}), 500
        
    # Check Chrome installation
    chrome_status = check_chrome_installation()
    if not chrome_status["installed"]:
        return jsonify({"success": False, "message": f"Chrome not installed: {chrome_status}"}), 500
    
    try:
        data = request.get_json()
        sessions_data = read_json(SESSIONS_FILE)
        
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
        write_json(sessions_data, SESSIONS_FILE)
        
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
        sessions_data = read_json(SESSIONS_FILE)
        return jsonify(sessions_data.get('sessions', []))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/test-selenium', methods=['GET'])
def test_selenium():
    """Test Selenium functionality"""
    if not SELENIUM_AVAILABLE:
        return jsonify({"success": False, "message": "Selenium not available"}), 500
        
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        
        # Set explicit Chrome binary path
        chrome_status = check_chrome_installation()
        if chrome_status["path"]:
            chrome_options.binary_location = chrome_status["path"]
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://httpbin.org/ip")
        
        result = {
            "success": True,
            "page_title": driver.title,
            "status": "Selenium test passed"
        }
        
        driver.quit()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🚀 TRAFFIC BOT STARTING...")
    print("=" * 60)
    
    chrome_status = check_chrome_installation()
    print(f"🔧 Chrome Installed: {chrome_status['installed']}")
    print(f"🔧 Chrome Path: {chrome_status['path']}")
    print(f"🔧 Chrome Version: {chrome_status['version']}")
    print(f"🔧 ChromeDriver Available: {chrome_status['chromedriver_available']}")
    print(f"🔧 Selenium Available: {SELENIUM_AVAILABLE}")
    print("=" * 60)
    
    if not chrome_status['installed']:
        print("❌ WARNING: Chrome not found! Sessions will fail.")
    else:
        print("✅ Chrome is ready!")
    
    app.run(host='0.0.0.0', port=port, debug=False)