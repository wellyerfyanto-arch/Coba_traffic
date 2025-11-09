import os
import json
import time
import random
import threading
import subprocess
import sys
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# Try to import selenium with fallback
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError as e:
    print(f"Selenium import error: {e}")
    SELENIUM_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# ==============================
# CONFIGURATION & INITIALIZATION
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
                "max_sessions": 5,
                "default_settings": {
                    "scroll_delay_min": 2,
                    "scroll_delay_max": 5,
                    "session_duration": 300,
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
        print(f"Error writing to {file_path}: {e}")
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
            "max_sessions": 5,
            "default_settings": {
                "scroll_delay_min": 2,
                "scroll_delay_max": 5,
                "session_duration": 300,
                "auto_clear_cache": True
            }
        }
    }
    
    for file_path, default_data in default_files.items():
        if not os.path.exists(file_path):
            write_json(default_data, file_path)

# Initialize data files
init_data_files()

# ==============================
# CHROME & DRIVER HEALTH CHECK
# ==============================

def check_system_dependencies():
    """Comprehensive system dependency check"""
    result = {
        "selenium_available": SELENIUM_AVAILABLE,
        "chrome_installed": False,
        "chrome_path": None,
        "chrome_version": "Unknown",
        "chromedriver_available": False,
        "chromedriver_path": None,
        "system_dependencies": {}
    }
    
    # Check Chrome installation
    chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/app/.apt/usr/bin/google-chrome"
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            result["chrome_installed"] = True
            result["chrome_path"] = path
            try:
                version_output = subprocess.check_output([path, '--version'], stderr=subprocess.STDOUT, text=True)
                result["chrome_version"] = version_output.strip()
            except Exception as e:
                result["chrome_version"] = f"Error: {str(e)}"
            break
    
    # Check chromedriver
    chromedriver_paths = [
        "/usr/local/bin/chromedriver",
        "/usr/bin/chromedriver",
        "/app/.apt/usr/bin/chromedriver",
        "/root/.cache/selenium/chromedriver/linux64/142.0.7444.61/chromedriver"
    ]
    
    for path in chromedriver_paths:
        if os.path.exists(path):
            result["chromedriver_available"] = True
            result["chromedriver_path"] = path
            try:
                subprocess.check_output([path, '--version'], stderr=subprocess.STDOUT)
            except Exception as e:
                result["chromedriver_available"] = False
            break
    
    # Check system libraries
    required_libs = [
        "libnss3", "libxss1", "libgconf-2-4", "libatk-bridge2.0-0",
        "libgtk-3-0", "libx11-xcb1", "libdrm2", "libxkbcommon0"
    ]
    
    for lib in required_libs:
        try:
            subprocess.check_output(["dpkg", "-l", lib], stderr=subprocess.STDOUT)
            result["system_dependencies"][lib] = "Installed"
        except:
            result["system_dependencies"][lib] = "Missing"
    
    return result

def install_chromedriver_fallback():
    """Attempt to install chromedriver as fallback"""
    try:
        print("Attempting to install chromedriver as fallback...")
        
        # Download and install chromedriver
        install_script = """
        apt-get update
        apt-get install -y wget unzip
        wget -q -O /tmp/chromedriver.zip https://storage.googleapis.com/chrome-for-testing-public/119.0.6045.105/linux64/chromedriver-linux64.zip
        unzip -q /tmp/chromedriver.zip -d /tmp/
        mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/
        chmod +x /usr/local/bin/chromedriver
        """
        
        subprocess.run(install_script, shell=True, check=True)
        print("Chromedriver installed successfully")
        return True
    except Exception as e:
        print(f"Chromedriver installation failed: {e}")
        return False

# ==============================
# USER AGENT GENERATOR
# ==============================

class UserAgentGenerator:
    @staticmethod
    def generate_mobile():
        mobile_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 12; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36"
        ]
        return random.choice(mobile_agents)
    
    @staticmethod
    def generate_desktop():
        desktop_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        ]
        return random.choice(desktop_agents)

# ==============================
# TRAFFIC BOT ENGINE (DIPERBAIKI)
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
        """Setup Chrome driver dengan multiple fallback methods"""
        if not SELENIUM_AVAILABLE:
            self.log_step("setup_driver", "error", "Selenium not available")
            return False
            
        try:
            # Check system dependencies first
            deps = check_system_dependencies()
            
            if not deps["chrome_installed"]:
                self.log_step("setup_driver", "error", "Chrome not installed in system")
                return False
            
            chrome_options = Options()
            
            # Set Chrome binary location
            if deps["chrome_path"]:
                chrome_options.binary_location = deps["chrome_path"]
            
            # Essential options for server environment
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument("--headless=new")
            
            # Anti-detection options
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set user agent
            user_agent = self.profile_data.get('user_agent', UserAgentGenerator.generate_desktop())
            chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # Window size
            if self.profile_data.get('profile_type') == 'mobile':
                chrome_options.add_argument("--window-size=375,812")
            else:
                chrome_options.add_argument("--window-size=1920,1080")
            
            # Proxy configuration
            if self.proxy_config and self.proxy_config.get('type') != 'direct':
                proxy_str = f"{self.proxy_config.get('host')}:{self.proxy_config.get('port')}"
                chrome_options.add_argument(f"--proxy-server={proxy_str}")
            
            # Try multiple methods to initialize driver
            driver = None
            
            # Method 1: Try with automatic chromedriver
            try:
                from selenium.webdriver.chrome.service import Service
                service = Service()
                driver = webdriver.Chrome(service=service, options=chrome_options)
                self.log_step("setup_driver", "success", "WebDriver initialized with automatic service")
            except Exception as e1:
                self.log_step("setup_driver", "warning", f"Automatic service failed: {str(e1)}")
                
                # Method 2: Try with explicit chromedriver path
                try:
                    if deps["chromedriver_path"] and os.path.exists(deps["chromedriver_path"]):
                        from selenium.webdriver.chrome.service import Service
                        service = Service(executable_path=deps["chromedriver_path"])
                        driver = webdriver.Chrome(service=service, options=chrome_options)
                        self.log_step("setup_driver", "success", "WebDriver initialized with explicit path")
                    else:
                        # Method 3: Try without service (legacy method)
                        driver = webdriver.Chrome(options=chrome_options)
                        self.log_step("setup_driver", "success", "WebDriver initialized without service")
                except Exception as e2:
                    self.log_step("setup_driver", "error", f"All driver initialization methods failed: {str(e2)}")
                    return False
            
            if driver:
                self.driver = driver
                # Anti-detection scripts
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                return True
            else:
                return False
                
        except Exception as e:
            self.log_step("setup_driver", "error", f"Driver setup completely failed: {str(e)}", {
                "dependencies": check_system_dependencies()
            })
            return False
    
    def log_step(self, step, status, message, details=None):
        """Log each step of the session"""
        log_entry = {
            "log_id": f"log_{int(time.time() * 1000)}",
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "status": status,
            "message": message,
            "details": details or {}
        }
        
        logs_data = read_json(LOGS_FILE)
        logs_data.setdefault("logs", []).append(log_entry)
        write_json(logs_data, LOGS_FILE)
        self.update_session_progress(step, status)
    
    def update_session_progress(self, step, status):
        """Update session progress"""
        sessions_data = read_json(SESSIONS_FILE)
        for session in sessions_data.get("sessions", []):
            if session.get("session_id") == self.session_id:
                session["current_step"] = step
                session["status"] = status
                progress_map = {
                    "initializing": 10, "setup_driver": 20, "data_leak_check": 30,
                    "opening_url": 40, "scrolling": 50, "clicking_post": 60,
                    "skipping_ads": 70, "returning_home": 80, "clearing_cache": 90,
                    "completed": 100
                }
                session["progress"] = progress_map.get(step, 0)
                break
        write_json(sessions_data, SESSIONS_FILE)
    
    def human_like_scroll(self, scroll_count=3):
        """Simulate human-like scrolling"""
        try:
            for i in range(scroll_count):
                if not self.is_running:
                    break
                    
                scroll_height = self.driver.execute_script("return document.body.scrollHeight")
                current_position = 0
                target_position = scroll_height * 0.8
                
                while current_position < target_position and self.is_running:
                    increment = random.randint(100, 300)
                    current_position += increment
                    self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                    time.sleep(random.uniform(0.5, 2.0))
                    
                    if random.random() < 0.2:
                        back_scroll = random.randint(50, 150)
                        current_position -= back_scroll
                        self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                        time.sleep(random.uniform(0.5, 1.5))
                
                if random.random() < 0.3 and self.is_running:
                    self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
                    time.sleep(random.uniform(1, 3))
            
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
            
            # Continue with other steps...
            if self.is_running:
                self.driver.get("https://httpbin.org/ip")
                time.sleep(2)
                self.log_step("data_leak_check", "success", "Basic connectivity check passed")
            
            if self.is_running:
                self.driver.get(self.target_url)
                self.log_step("opening_url", "success", f"Opened URL: {self.target_url}")
                time.sleep(3)
            
            # Simulate browsing behavior
            if self.is_running:
                self.human_like_scroll(2)
                self.log_step("scrolling", "success", "Scrolling completed")
            
            if self.is_running:
                self.log_step("completed", "success", "Session completed successfully")
            
        except Exception as e:
            self.log_step("error", "failed", f"Session failed: {str(e)}")
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            
            sessions_data = read_json(SESSIONS_FILE)
            for session in sessions_data.get("sessions", []):
                if session.get("session_id") == self.session_id:
                    session["status"] = "completed" if self.is_running else "stopped"
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
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Comprehensive health check"""
    deps = check_system_dependencies()
    
    health_status = "healthy" if (deps["selenium_available"] and deps["chrome_installed"]) else "unhealthy"
    
    return jsonify({
        "status": health_status,
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(active_sessions),
        "dependencies": deps,
        "version": "1.0.0"
    })

@app.route('/api/install-dependencies', methods=['POST'])
def install_dependencies():
    """Manual dependency installation endpoint"""
    try:
        success = install_chromedriver_fallback()
        return jsonify({
            "success": success,
            "message": "Dependency installation attempted" if success else "Dependency installation failed"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/create_session', methods=['POST'])
def create_session():
    """Create new session dengan dependency check"""
    if not SELENIUM_AVAILABLE:
        return jsonify({"success": False, "message": "Selenium not available"}), 500
    
    deps = check_system_dependencies()
    if not deps["chrome_installed"]:
        return jsonify({"success": False, "message": "Chrome not installed in system"}), 500
    
    try:
        data = request.get_json()
        required_fields = ['profile_type', 'profile_count', 'target_url']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"Missing field: {field}"}), 400
        
        sessions_data = read_json(SESSIONS_FILE)
        session_id = f"sess_{sessions_data['session_counter'] + 1:03d}"
        
        profile_type = data['profile_type']
        user_agent = UserAgentGenerator.generate_mobile() if profile_type == 'mobile' else UserAgentGenerator.generate_desktop()
        
        profile_data = {
            "profile_name": f"{profile_type}_profile_{sessions_data['session_counter'] + 1}",
            "profile_type": profile_type,
            "user_agent": user_agent
        }
        
        session_entry = {
            "session_id": session_id,
            "profile_name": profile_data['profile_name'],
            "user_agent": profile_type,
            "target_url": data['target_url'],
            "status": "running",
            "current_step": "initializing",
            "start_time": datetime.now().isoformat(),
            "progress": 0
        }
        
        sessions_data['sessions'].append(session_entry)
        sessions_data['session_counter'] += 1
        write_json(sessions_data, SESSIONS_FILE)
        
        bot = TrafficBot(session_id, profile_data, data['target_url'])
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
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

# ... (other routes remain similar but with better error handling)

@app.route('/api/system-info', methods=['GET'])
def system_info():
    """Get detailed system information"""
    return jsonify({
        "python_version": sys.version,
        "working_directory": os.getcwd(),
        "environment_variables": dict(os.environ),
        "system_dependencies": check_system_dependencies()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🚀 TRAFFIC BOT STARTING...")
    print("=" * 60)
    
    deps = check_system_dependencies()
    
    print("🔍 DEPENDENCY CHECK:")
    print(f"   Selenium: {'✅' if deps['selenium_available'] else '❌'}")
    print(f"   Chrome: {'✅' if deps['chrome_installed'] else '❌'}")
    print(f"   Chrome Path: {deps['chrome_path'] or 'Not found'}")
    print(f"   Chrome Version: {deps['chrome_version']}")
    print(f"   Chromedriver: {'✅' if deps['chromedriver_available'] else '❌'}")
    
    if not deps['chrome_installed']:
        print("⚠️  CRITICAL: Chrome not found! Attempting fallback installation...")
        install_chromedriver_fallback()
        deps = check_system_dependencies()
        print(f"   After fallback - Chrome: {'✅' if deps['chrome_installed'] else '❌'}")
    
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)