import os
import json
import time
import random
import threading
import traceback
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

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
except ImportError as e:
    print(f"Selenium import failed: {e}")
    SELENIUM_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# Configuration
DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)

# Simple file operations
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
        print(f"Write error: {e}")
        return False

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

# Traffic Bot dengan enhanced error handling
class TrafficBot:
    def __init__(self, session_id, profile_data, target_url):
        self.session_id = session_id
        self.profile_data = profile_data
        self.target_url = target_url
        self.driver = None
        self.is_running = True
        
    def safe_execute(self, func, description, max_retries=2):
        """Execute function dengan retry mechanism"""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {description}: {e}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2)
    
    def setup_driver(self):
        """Setup driver dengan comprehensive error handling"""
        if not SELENIUM_AVAILABLE:
            return False
            
        try:
            chrome_options = Options()
            
            # Essential options
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage") 
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--remote-debugging-port=9222")
            
            # Performance optimizations
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-javascript")
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")
            
            # Timeout settings
            chrome_options.add_argument("--page-load-timeout=30000")
            
            # User agent
            user_agent = self.profile_data.get('user_agent', UserAgentGenerator.generate_desktop())
            chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # Window size
            if self.profile_data.get('profile_type') == 'mobile':
                chrome_options.add_argument("--window-size=375,812")
            else:
                chrome_options.add_argument("--window-size=1024,768")  # Smaller for performance
                
            print("Attempting to create Chrome driver...")
            
            # Try multiple initialization methods
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
            except SessionNotCreatedException as e:
                print(f"Session creation failed: {e}")
                return False
            except WebDriverException as e:
                print(f"WebDriver exception: {e}")
                return False
                
            # Set timeouts
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)
            
            print("Chrome driver created successfully")
            return True
            
        except Exception as e:
            print(f"Driver setup completely failed: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            return False
    
    def run_session(self):
        """Run session dengan comprehensive error handling"""
        session_data = read_json('data/sessions.json')
        
        try:
            # Update session status
            for session in session_data.get("sessions", []):
                if session.get("session_id") == self.session_id:
                    session["status"] = "running"
                    session["current_step"] = "initializing"
                    break
            write_json(session_data, 'data/sessions.json')
            
            print(f"Starting session {self.session_id}")
            
            if not self.setup_driver():
                print("Driver setup failed")
                return
                
            print("Driver setup successful, proceeding with session...")
            
            # Simple test navigation
            try:
                print("Navigating to target URL...")
                self.driver.get(self.target_url)
                print(f"Successfully loaded: {self.target_url}")
                
                # Simple scroll simulation
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);") 
                time.sleep(1)
                
                print("Session completed successfully")
                
            except Exception as e:
                print(f"Navigation error: {e}")
                
        except Exception as e:
            print(f"Session error: {e}")
            print(f"Traceback: {traceback.format_exc()}")
        finally:
            # Cleanup
            try:
                if self.driver:
                    self.driver.quit()
                    print("Driver quit successfully")
            except Exception as e:
                print(f"Driver quit error: {e}")
            
            # Update session status
            for session in session_data.get("sessions", []):
                if session.get("session_id") == self.session_id:
                    session["status"] = "completed"
                    session["progress"] = 100
                    break
            write_json(session_data, 'data/sessions.json')
            
            print(f"Session {self.session_id} finished")

# Flask Routes
active_sessions = {}

@app.route('/')
def index():
    return "Traffic Bot is running!"

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "selenium_available": SELENIUM_AVAILABLE,
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(active_sessions)
    })

@app.route('/api/create_session', methods=['POST'])
def create_session():
    if not SELENIUM_AVAILABLE:
        return jsonify({"success": False, "message": "Selenium not available"}), 500
        
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
            "message": "Session started"
        })
        
    except Exception as e:
        print(f"Create session error: {e}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    try:
        sessions_data = read_json('data/sessions.json')
        return jsonify(sessions_data.get('sessions', []))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Traffic Bot on port {port}")
    print(f"🔧 Selenium available: {SELENIUM_AVAILABLE}")
    
    # Initialize data directory
    os.makedirs('data', exist_ok=True)
    if not os.path.exists('data/sessions.json'):
        write_json({"sessions": [], "session_counter": 0}, 'data/sessions.json')
    
    app.run(host='0.0.0.0', port=port, debug=False)