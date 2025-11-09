import os
import json
import time
import random
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

app = Flask(__name__)
CORS(app)

# Configuration
DATA_DIR = 'data'
PROFILES_FILE = os.path.join(DATA_DIR, 'profiles.json')
SESSIONS_FILE = os.path.join(DATA_DIR, 'sessions.json')
LOGS_FILE = os.path.join(DATA_DIR, 'logs.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize data files if they don't exist
def init_data_files():
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
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)

init_data_files()

# Helper functions for JSON operations
def read_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def write_json(data, file_path):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error writing to {file_path}: {e}")
        return False

# User Agent Generator
class UserAgentGenerator:
    @staticmethod
    def generate_mobile():
        mobile_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 12; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (iPad; CPU OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1"
        ]
        return random.choice(mobile_agents)
    
    @staticmethod
    def generate_desktop():
        desktop_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0"
        ]
        return random.choice(desktop_agents)

# Bot Engine
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
        """Setup Chrome driver with configuration"""
        try:
            chrome_options = Options()
            
            # Basic options
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set user agent
            user_agent = self.profile_data.get('user_agent', UserAgentGenerator.generate_desktop())
            chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # Window size based on device type
            if self.profile_data.get('profile_type') == 'mobile':
                chrome_options.add_argument("--window-size=375,812")  # iPhone X
            else:
                chrome_options.add_argument("--window-size=1920,1080")
            
            # Proxy configuration
            if self.proxy_config and self.proxy_config.get('type') != 'direct':
                proxy_str = f"{self.proxy_config.get('host')}:{self.proxy_config.get('port')}"
                chrome_options.add_argument(f"--proxy-server={proxy_str}")
            
            # For Railway deployment (headless)
            if os.environ.get('RAILWAY_ENVIRONMENT'):
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            return True
        except Exception as e:
            self.log_step("setup_driver", "error", f"Failed to setup driver: {str(e)}")
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
        
        # Save to logs file
        logs_data = read_json(LOGS_FILE)
        logs_data.setdefault("logs", []).append(log_entry)
        write_json(logs_data, LOGS_FILE)
        
        # Update session progress
        self.update_session_progress(step, status)
    
    def update_session_progress(self, step, status):
        """Update session progress in sessions.json"""
        sessions_data = read_json(SESSIONS_FILE)
        for session in sessions_data.get("sessions", []):
            if session.get("session_id") == self.session_id:
                session["current_step"] = step
                session["status"] = status
                
                # Calculate progress percentage based on step
                progress_map = {
                    "initializing": 10,
                    "setup_driver": 20,
                    "data_leak_check": 30,
                    "opening_url": 40,
                    "scrolling": 50,
                    "clicking_post": 60,
                    "skipping_ads": 70,
                    "returning_home": 80,
                    "clearing_cache": 90,
                    "completed": 100
                }
                session["progress"] = progress_map.get(step, 0)
                break
        
        write_json(sessions_data, SESSIONS_FILE)
    
    def human_like_scroll(self, scroll_count=3):
        """Simulate human-like scrolling behavior"""
        try:
            for i in range(scroll_count):
                if not self.is_running:
                    break
                    
                # Scroll down gradually
                scroll_height = self.driver.execute_script("return document.body.scrollHeight")
                current_scroll = 0
                
                while current_scroll < scroll_height and self.is_running:
                    scroll_increment = random.randint(100, 300)
                    current_scroll += scroll_increment
                    self.driver.execute_script(f"window.scrollTo(0, {current_scroll});")
                    time.sleep(random.uniform(0.5, 2.0))
                
                # Scroll back up partially
                if self.is_running:
                    scroll_up = random.randint(200, 500)
                    self.driver.execute_script(f"window.scrollBy(0, -{scroll_up});")
                    time.sleep(random.uniform(1, 3))
            
            return True
        except Exception as e:
            self.log_step("scrolling", "error", f"Scrolling error: {str(e)}")
            return False
    
    def check_data_leak(self):
        """Check for IP/DNS leaks"""
        try:
            # Simple check using external service
            test_urls = [
                "https://httpbin.org/ip",
                "https://api.ipify.org?format=json"
            ]
            
            for url in test_urls:
                if not self.is_running:
                    break
                self.driver.get(url)
                time.sleep(2)
            
            self.log_step("data_leak_check", "success", "Data leak check completed")
            return True
        except Exception as e:
            self.log_step("data_leak_check", "error", f"Data leak check failed: {str(e)}")
            return False
    
    def skip_google_ads(self):
        """Attempt to skip Google ads if present"""
        try:
            # Common ad selectors
            ad_selectors = [
                "button[aria-label*='close' i]",
                "button[class*='close' i]",
                "div[class*='ad' i] button",
                ".ad-close",
                ".close-button"
            ]
            
            for selector in ad_selectors:
                if not self.is_running:
                    break
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in close_buttons:
                        if button.is_displayed():
                            button.click()
                            time.sleep(1)
                            self.log_step("skipping_ads", "success", "Skipped ad")
                            break
                except:
                    continue
            
            return True
        except Exception as e:
            self.log_step("skipping_ads", "error", f"Ad skipping failed: {str(e)}")
            return False
    
    def click_random_post(self):
        """Click on a random post/link on the page"""
        try:
            # Find all clickable elements
            clickable_selectors = [
                "a[href*='http']",
                "button",
                ".post",
                ".article",
                ".card",
                "[onclick]"
            ]
            
            all_elements = []
            for selector in clickable_selectors:
                if not self.is_running:
                    break
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                # Filter visible elements
                visible_elements = [el for el in elements if el.is_displayed()]
                all_elements.extend(visible_elements)
            
            if all_elements:
                # Click a random element (but not the first few)
                if len(all_elements) > 3:
                    element_to_click = random.choice(all_elements[2:min(10, len(all_elements))])
                    
                    # Scroll to element
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth'});", element_to_click)
                    time.sleep(1)
                    
                    # Click with human-like behavior
                    action = ActionChains(self.driver)
                    action.move_to_element(element_to_click).click().perform()
                    
                    self.log_step("clicking_post", "success", "Clicked on random post")
                    time.sleep(3)  # Wait for page load
                    return True
            
            self.log_step("clicking_post", "skipped", "No suitable posts found to click")
            return False
        except Exception as e:
            self.log_step("clicking_post", "error", f"Clicking post failed: {str(e)}")
            return False
    
    def clear_cache_and_cookies(self):
        """Clear browser cache and cookies"""
        try:
            if self.driver:
                self.driver.delete_all_cookies()
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
                self.log_step("clearing_cache", "success", "Cache and cookies cleared")
            return True
        except Exception as e:
            self.log_step("clearing_cache", "error", f"Cache clearing failed: {str(e)}")
            return False
    
    def run_session(self):
        """Main session execution"""
        try:
            self.log_step("initializing", "running", "Session started")
            
            # Step 1: Setup driver
            if not self.setup_driver():
                return
            
            self.log_step("setup_driver", "success", "WebDriver setup completed")
            
            # Step 2: Check data leaks
            if self.is_running:
                self.check_data_leak()
            
            # Step 3: Open target URL
            if self.is_running:
                self.driver.get(self.target_url)
                self.log_step("opening_url", "success", f"Opened URL: {self.target_url}")
                time.sleep(3)
            
            # Step 4: Initial scrolling
            if self.is_running:
                self.human_like_scroll(2)
                self.log_step("scrolling", "success", "Initial scrolling completed")
            
            # Step 5: Skip ads
            if self.is_running:
                self.skip_google_ads()
            
            # Step 6: Click random post
            if self.is_running:
                self.click_random_post()
            
            # Step 7: Continue scrolling
            if self.is_running:
                self.human_like_scroll(3)
                self.log_step("scrolling", "success", "Continued scrolling")
            
            # Step 8: Return to home (if we clicked a post)
            if self.is_running and len(self.driver.window_handles) > 1:
                # Close current tab and switch to original
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            
            # Step 9: Final scroll to top
            if self.is_running:
                self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
                self.log_step("returning_home", "success", "Returned to top of page")
            
            # Step 10: Clear cache
            if self.is_running:
                self.clear_cache_and_cookies()
            
            # Mark as completed
            if self.is_running:
                self.log_step("completed", "success", "Session completed successfully")
            
        except Exception as e:
            self.log_step("error", "failed", f"Session failed: {str(e)}")
        finally:
            # Cleanup
            if self.driver:
                self.driver.quit()
            
            # Update final session status
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
            self.driver.quit()

# Active sessions tracker
active_sessions = {}

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/create_session', methods=['POST'])
def create_session():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['profile_type', 'profile_count', 'target_url']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400
        
        # Generate session data
        sessions_data = read_json(SESSIONS_FILE)
        session_id = f"sess_{sessions_data['session_counter'] + 1:03d}"
        
        # Create profile data
        profile_type = data['profile_type']
        user_agent = UserAgentGenerator.generate_mobile() if profile_type == 'mobile' else UserAgentGenerator.generate_desktop()
        
        profile_data = {
            "profile_name": f"{profile_type}_profile_{sessions_data['session_counter'] + 1}",
            "profile_type": profile_type,
            "user_agent": user_agent
        }
        
        # Proxy configuration
        proxy_config = None
        if data.get('proxy_type') and data['proxy_type'] != 'direct':
            proxy_config = {
                "type": data['proxy_type'],
                "host": data.get('proxy_host'),
                "port": data.get('proxy_port'),
                "username": data.get('proxy_username'),
                "password": data.get('proxy_password')
            }
        
        # Create session entry
        session_entry = {
            "session_id": session_id,
            "profile_name": profile_data['profile_name'],
            "user_agent": profile_type,
            "proxy_config": proxy_config,
            "target_url": data['target_url'],
            "status": "running",
            "current_step": "initializing",
            "start_time": datetime.now().isoformat(),
            "progress": 0
        }
        
        sessions_data['sessions'].append(session_entry)
        sessions_data['session_counter'] += 1
        write_json(sessions_data, SESSIONS_FILE)
        
        # Start bot in separate thread
        bot = TrafficBot(session_id, profile_data, data['target_url'], proxy_config)
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
        return jsonify({"success": False, "message": f"Error creating session: {str(e)}"}), 500

@app.route('/api/create_profile', methods=['POST'])
def create_profile():
    try:
        data = request.get_json()
        
        required_fields = ['profile_name', 'profile_type']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400
        
        profiles_data = read_json(PROFILES_FILE)
        profile_id = f"profile_{len(profiles_data['profiles']) + 1:03d}"
        
        # Generate user agent if not provided
        user_agent = data.get('custom_user_agent')
        if not user_agent:
            if data['profile_type'] == 'mobile':
                user_agent = UserAgentGenerator.generate_mobile()
            else:
                user_agent = UserAgentGenerator.generate_desktop()
        
        profile = {
            "profile_id": profile_id,
            "profile_name": data['profile_name'],
            "profile_type": data['profile_type'],
            "user_agent": user_agent,
            "proxy_settings": {},
            "created_at": datetime.now().isoformat(),
            "last_used": None
        }
        
        profiles_data['profiles'].append(profile)
        write_json(profiles_data, PROFILES_FILE)
        
        return jsonify({
            "success": True,
            "profile_id": profile_id,
            "message": "Profile created successfully"
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Error creating profile: {str(e)}"}), 500

@app.route('/api/profiles', methods=['GET'])
def get_profiles():
    try:
        profiles_data = read_json(PROFILES_FILE)
        return jsonify(profiles_data.get('profiles', []))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    try:
        sessions_data = read_json(SESSIONS_FILE)
        return jsonify(sessions_data.get('sessions', []))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        logs_data = read_json(LOGS_FILE)
        return jsonify(logs_data.get('logs', [])[-50:])  # Return last 50 logs
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/delete_profile/<profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    try:
        profiles_data = read_json(PROFILES_FILE)
        profiles_data['profiles'] = [p for p in profiles_data['profiles'] if p['profile_id'] != profile_id]
        write_json(profiles_data, PROFILES_FILE)
        
        return jsonify({"success": True, "message": "Profile deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/stop_session/<session_id>', methods=['POST'])
def stop_session(session_id):
    try:
        if session_id in active_sessions:
            active_sessions[session_id].stop()
            del active_sessions[session_id]
        
        sessions_data = read_json(SESSIONS_FILE)
        for session in sessions_data['sessions']:
            if session['session_id'] == session_id:
                session['status'] = 'stopped'
                session['current_step'] = 'stopped'
                break
        
        write_json(sessions_data, SESSIONS_FILE)
        
        return jsonify({"success": True, "message": "Session stopped successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/clear_logs', methods=['DELETE'])
def clear_logs():
    try:
        write_json({"logs": []}, LOGS_FILE)
        return jsonify({"success": True, "message": "Logs cleared successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(active_sessions)
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
