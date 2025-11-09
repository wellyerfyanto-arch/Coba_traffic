import os
import json
import time
import random
import threading
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

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
        # Return empty structure based on filename
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
# CHROME DRIVER SETUP & HEALTH CHECK
# ==============================

def check_chrome_installation():
    """Check if Chrome is properly installed"""
    try:
        # Check if chrome binary exists
        chrome_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable", 
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser"
        ]
        
        chrome_found = False
        actual_chrome_path = None
        
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_found = True
                actual_chrome_path = path
                break
                
        if not chrome_found:
            # Try to find chrome using which command
            try:
                result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
                if result.returncode == 0:
                    chrome_found = True
                    actual_chrome_path = result.stdout.strip()
            except:
                pass
        
        # Check chrome version
        chrome_version = "Unknown"
        if actual_chrome_path:
            try:
                result = subprocess.run([actual_chrome_path, '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    chrome_version = result.stdout.strip()
            except:
                pass
        
        return {
            "chrome_installed": chrome_found,
            "chrome_path": actual_chrome_path,
            "chrome_version": chrome_version
        }
        
    except Exception as e:
        return {
            "chrome_installed": False,
            "chrome_path": None,
            "chrome_version": f"Error: {str(e)}"
        }

def check_chromedriver():
    """Check chromedriver availability"""
    try:
        from selenium.webdriver.chrome.service import Service
        service = Service()
        driver = webdriver.Chrome(service=service)
        driver.quit()
        return {"status": "healthy", "message": "Chromedriver working properly"}
    except Exception as e:
        return {"status": "error", "message": f"Chromedriver error: {str(e)}"}

# ==============================
# USER AGENT GENERATOR
# ==============================

class UserAgentGenerator:
    @staticmethod
    def generate_mobile():
        mobile_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 12; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (iPad; CPU OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.210 Mobile Safari/537.36"
        ]
        return random.choice(mobile_agents)
    
    @staticmethod
    def generate_desktop():
        desktop_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/110.0.1587.41"
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
        """Setup Chrome driver dengan konfigurasi yang robust"""
        try:
            chrome_options = Options()
            
            # Dapatkan info instalasi Chrome
            chrome_info = check_chrome_installation()
            
            # Set Chrome binary location jika ditemukan
            if chrome_info["chrome_path"]:
                chrome_options.binary_location = chrome_info["chrome_path"]
                self.log_step("setup_driver", "info", f"Using Chrome at: {chrome_info['chrome_path']}")
            
            # **FIX UNTUK ERROR 127**: Opsi penting untuk environment server
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")
            
            # Opsi untuk menghindari detection
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set user agent
            user_agent = self.profile_data.get('user_agent', UserAgentGenerator.generate_desktop())
            chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # Window size based on device type
            if self.profile_data.get('profile_type') == 'mobile':
                chrome_options.add_argument("--window-size=375,812")
            else:
                chrome_options.add_argument("--window-size=1920,1080")
            
            # Proxy configuration
            if self.proxy_config and self.proxy_config.get('type') != 'direct':
                proxy_str = f"{self.proxy_config.get('host')}:{self.proxy_config.get('port')}"
                chrome_options.add_argument(f"--proxy-server={proxy_str}")
            
            # Headless mode untuk server
            chrome_options.add_argument("--headless=new")
            
            # Additional preferences
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 2,
                "download_restrictions": 3
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Setup service dengan error handling
            try:
                # Coba dengan Service() default terlebih dahulu
                service = Service()
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except WebDriverException as e:
                self.log_step("setup_driver", "warning", f"Default service failed, trying without service: {str(e)}")
                # Fallback: coba tanpa Service()
                self.driver = webdriver.Chrome(options=chrome_options)
            
            # Execute script untuk avoid detection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": user_agent,
                "platform": "Linux" if self.profile_data.get('profile_type') == 'desktop' else "Android"
            })
            
            self.log_step("setup_driver", "success", "WebDriver setup completed")
            return True
            
        except Exception as e:
            error_msg = f"Failed to setup driver: {str(e)}"
            self.log_step("setup_driver", "error", error_msg, {
                "chrome_info": check_chrome_installation(),
                "chromedriver_info": check_chromedriver()
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
                    
                # Scroll down gradually with random pauses
                scroll_height = self.driver.execute_script("return document.body.scrollHeight")
                scroll_pauses = [0.5, 0.8, 1.2, 1.5, 2.0]
                scroll_increments = [100, 150, 200, 250, 300]
                
                current_position = 0
                target_position = scroll_height * 0.8  # Scroll 80% of page
                
                while current_position < target_position and self.is_running:
                    increment = random.choice(scroll_increments)
                    current_position += increment
                    
                    # Smooth scroll
                    self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                    
                    # Random pause
                    time.sleep(random.choice(scroll_pauses))
                    
                    # Occasionally scroll back a bit (human behavior)
                    if random.random() < 0.2:  # 20% chance
                        back_scroll = random.randint(50, 150)
                        current_position -= back_scroll
                        self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                        time.sleep(random.uniform(0.5, 1.5))
                
                # Scroll back to top occasionally
                if random.random() < 0.3 and self.is_running:  # 30% chance
                    self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
                    time.sleep(random.uniform(1, 3))
            
            return True
        except Exception as e:
            self.log_step("scrolling", "error", f"Scrolling error: {str(e)}")
            return False
    
    def check_data_leak(self):
        """Check for IP/DNS leaks"""
        try:
            # Test IP address dengan timeout
            self.driver.set_page_load_timeout(30)
            self.driver.get("https://httpbin.org/ip")
            time.sleep(2)
            
            # Get IP from response
            ip_text = self.driver.find_element(By.TAG_NAME, "pre").text
            self.log_step("data_leak_check", "success", f"IP Check completed: {ip_text[:100]}...")
            
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
                ".close-button",
                "[aria-label*='tutup' i]",
                "[class*='dismiss' i]",
                "#dismiss-button",
                ".ytp-ad-skip-button",
                ".ytp-ad-overlay-close-button"
            ]
            
            ads_skipped = 0
            for selector in ad_selectors:
                if not self.is_running:
                    break
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in close_buttons:
                        if button.is_displayed() and self.is_running:
                            # Human-like delay before clicking
                            time.sleep(random.uniform(0.5, 1.5))
                            try:
                                button.click()
                                ads_skipped += 1
                                self.log_step("skipping_ads", "success", f"Skipped ad #{ads_skipped}")
                                time.sleep(1)
                            except:
                                # Try JavaScript click as fallback
                                self.driver.execute_script("arguments[0].click();", button)
                                ads_skipped += 1
                                self.log_step("skipping_ads", "success", f"Skipped ad #{ads_skipped} (JS)")
                                time.sleep(1)
                except Exception as e:
                    continue
            
            if ads_skipped > 0:
                self.log_step("skipping_ads", "success", f"Total ads skipped: {ads_skipped}")
            else:
                self.log_step("skipping_ads", "skipped", "No ads found to skip")
            
            return True
        except Exception as e:
            self.log_step("skipping_ads", "error", f"Ad skipping failed: {str(e)}")
            return False
    
    def click_random_post(self):
        """Click on a random post/link on the page"""
        try:
            # Find all clickable elements (excluding navigation and footer)
            clickable_selectors = [
                "a[href*='/p/']",  # Instagram-like posts
                "a[href*='/post/']",
                "a[href*='/article/']",
                ".post a",
                ".article a",
                ".card a",
                ".content a",
                "a:not([href*='#']):not([href*='facebook']):not([href*='twitter']):not([href*='instagram'])",
                "button:not([type='submit'])",
                "[role='button']"
            ]
            
            all_elements = []
            for selector in clickable_selectors:
                if not self.is_running:
                    break
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    # Filter visible, clickable elements
                    visible_elements = [el for el in elements if el.is_displayed() and el.is_enabled()]
                    all_elements.extend(visible_elements)
                except:
                    continue
            
            # Remove duplicates by element reference
            unique_elements = []
            seen_elements = set()
            for el in all_elements:
                el_id = id(el)
                if el_id not in seen_elements:
                    seen_elements.add(el_id)
                    unique_elements.append(el)
            
            if unique_elements:
                # Avoid clicking the first few elements (usually navigation)
                if len(unique_elements) > 3:
                    element_to_click = random.choice(unique_elements[2:min(8, len(unique_elements))])
                    
                    # Scroll to element smoothly
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                        element_to_click
                    )
                    time.sleep(random.uniform(1, 2))
                    
                    # Human-like click with mouse movement simulation
                    action = ActionChains(self.driver)
                    action.move_to_element(element_to_click).pause(random.uniform(0.2, 0.5)).click().perform()
                    
                    self.log_step("clicking_post", "success", "Clicked on random post")
                    time.sleep(random.uniform(3, 5))  # Wait for page load
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
                # Clear cookies
                self.driver.delete_all_cookies()
                
                # Clear local storage
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
                
                self.log_step("clearing_cache", "success", "Cache, cookies and storage cleared")
            return True
        except Exception as e:
            self.log_step("clearing_cache", "error", f"Cache clearing failed: {str(e)}")
            return False
    
    def run_session(self):
        """Main session execution dengan error handling yang lebih baik"""
        try:
            self.log_step("initializing", "running", "Session started", {
                "profile": self.profile_data.get('profile_name'),
                "target_url": self.target_url,
                "proxy": "Yes" if self.proxy_config else "No"
            })
            
            # Step 1: Setup driver
            if not self.setup_driver():
                self.log_step("setup_driver", "failed", "Driver setup failed")
                return
            
            # Step 2: Check data leaks
            if self.is_running:
                self.check_data_leak()
            
            # Step 3: Open target URL dengan timeout
            if self.is_running:
                try:
                    self.driver.set_page_load_timeout(30)
                    self.driver.get(self.target_url)
                    self.log_step("opening_url", "success", f"Opened URL: {self.target_url}")
                    time.sleep(random.uniform(3, 5))
                except TimeoutException:
                    self.log_step("opening_url", "warning", "Page load timeout, but continuing...")
                except Exception as e:
                    self.log_step("opening_url", "error", f"Failed to open URL: {str(e)}")
                    return
            
            # Step 4: Initial scrolling
            if self.is_running:
                self.human_like_scroll(2)
                self.log_step("scrolling", "success", "Initial scrolling completed")
            
            # Step 5: Skip ads
            if self.is_running:
                self.skip_google_ads()
            
            # Step 6: Click random post
            post_clicked = False
            if self.is_running:
                post_clicked = self.click_random_post()
                
                # If post was clicked, interact with the new page
                if post_clicked and self.is_running:
                    # Scroll on the new page
                    self.human_like_scroll(1)
                    time.sleep(random.uniform(2, 4))
                    
                    # Skip ads on new page
                    self.skip_google_ads()
                    
                    # Go back to original page
                    self.driver.back()
                    self.log_step("navigation", "success", "Returned to original page")
                    time.sleep(random.uniform(2, 3))
            
            # Step 7: Continue scrolling on main page
            if self.is_running:
                self.human_like_scroll(1)
                self.log_step("scrolling", "success", "Final scrolling completed")
            
            # Step 8: Final scroll to top
            if self.is_running:
                self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
                time.sleep(1)
                self.log_step("returning_home", "success", "Returned to top of page")
            
            # Step 9: Clear cache
            if self.is_running:
                self.clear_cache_and_cookies()
            
            # Mark as completed
            if self.is_running:
                self.log_step("completed", "success", "Session completed successfully")
            
        except Exception as e:
            self.log_step("error", "failed", f"Session failed: {str(e)}")
        finally:
            # Cleanup dengan error handling
            if self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    self.log_step("cleanup", "warning", f"Driver cleanup warning: {str(e)}")
            
            # Update final session status
            sessions_data = read_json(SESSIONS_FILE)
            for session in sessions_data.get("sessions", []):
                if session.get("session_id") == self.session_id:
                    if self.is_running:
                        session["status"] = "completed"
                        session["progress"] = 100
                    else:
                        session["status"] = "stopped"
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

# Active sessions tracker
active_sessions = {}

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')

@app.route('/api/create_session', methods=['POST'])
def create_session():
    """Create and start a new bot session"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['profile_type', 'profile_count', 'target_url']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400
        
        # Check max sessions limit
        config = read_json(CONFIG_FILE)
        max_sessions = config.get('max_sessions', 5)
        
        sessions_data = read_json(SESSIONS_FILE)
        active_count = len([s for s in sessions_data.get('sessions', []) if s.get('status') in ['running', 'initializing']])
        
        if active_count >= max_sessions:
            return jsonify({"success": False, "message": f"Maximum {max_sessions} concurrent sessions allowed"}), 400
        
        # Generate session data
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
    """Create a new browser profile"""
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
    """Get all profiles"""
    try:
        profiles_data = read_json(PROFILES_FILE)
        return jsonify(profiles_data.get('profiles', []))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all sessions"""
    try:
        sessions_data = read_json(SESSIONS_FILE)
        # Return only recent sessions (last 20)
        recent_sessions = sessions_data.get('sessions', [])[-20:]
        return jsonify(recent_sessions)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get session logs"""
    try:
        logs_data = read_json(LOGS_FILE)
        # Return last 50 logs
        recent_logs = logs_data.get('logs', [])[-50:]
        return jsonify(recent_logs)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/delete_profile/<profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    """Delete a profile"""
    try:
        profiles_data = read_json(PROFILES_FILE)
        initial_count = len(profiles_data['profiles'])
        profiles_data['profiles'] = [p for p in profiles_data['profiles'] if p['profile_id'] != profile_id]
        
        if len(profiles_data['profiles']) < initial_count:
            write_json(profiles_data, PROFILES_FILE)
            return jsonify({"success": True, "message": "Profile deleted successfully"})
        else:
            return jsonify({"success": False, "message": "Profile not found"}), 404
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/stop_session/<session_id>', methods=['POST'])
def stop_session(session_id):
    """Stop a running session"""
    try:
        if session_id in active_sessions:
            active_sessions[session_id].stop()
            del active_sessions[session_id]
        
        sessions_data = read_json(SESSIONS_FILE)
        session_found = False
        for session in sessions_data['sessions']:
            if session['session_id'] == session_id:
                session['status'] = 'stopped'
                session['current_step'] = 'stopped'
                session_found = True
                break
        
        if session_found:
            write_json(sessions_data, SESSIONS_FILE)
            return jsonify({"success": True, "message": "Session stopped successfully"})
        else:
            return jsonify({"success": False, "message": "Session not found"}), 404
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/clear_logs', methods=['DELETE'])
def clear_logs():
    """Clear all logs"""
    try:
        write_json({"logs": []}, LOGS_FILE)
        return jsonify({"success": True, "message": "Logs cleared successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get application configuration"""
    try:
        config_data = read_json(CONFIG_FILE)
        return jsonify(config_data)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint dengan info Chrome"""
    chrome_info = check_chrome_installation()
    chromedriver_info = check_chromedriver()
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(active_sessions),
        "chrome": chrome_info,
        "chromedriver": chromedriver_info,
        "version": "1.0.0"
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get application statistics"""
    try:
        sessions_data = read_json(SESSIONS_FILE)
        logs_data = read_json(LOGS_FILE)
        profiles_data = read_json(PROFILES_FILE)
        
        total_sessions = len(sessions_data.get('sessions', []))
        completed_sessions = len([s for s in sessions_data.get('sessions', []) if s.get('status') == 'completed'])
        failed_sessions = len([s for s in sessions_data.get('sessions', []) if s.get('status') == 'failed'])
        total_logs = len(logs_data.get('logs', []))
        total_profiles = len(profiles_data.get('profiles', []))
        
        return jsonify({
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "failed_sessions": failed_sessions,
            "success_rate": (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0,
            "total_logs": total_logs,
            "total_profiles": total_profiles,
            "active_sessions": len(active_sessions)
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ==============================
# APPLICATION STARTUP
# ==============================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🚀 TRAFFIC BOT APPLICATION STARTING...")
    print("=" * 60)
    
    # Check system health
    chrome_info = check_chrome_installation()
    chromedriver_info = check_chromedriver()
    
    print(f"📁 Data directory: {os.path.abspath(DATA_DIR)}")
    print(f"🌐 Server port: {port}")
    print(f"🔧 Environment: {'Production' if os.environ.get('RAILWAY_ENVIRONMENT') else 'Development'}")
    print("")
    print("🔍 SYSTEM HEALTH CHECK:")
    print(f"   Chrome Installed: {'✅' if chrome_info['chrome_installed'] else '❌'}")
    print(f"   Chrome Path: {chrome_info['chrome_path'] or 'Not found'}")
    print(f"   Chrome Version: {chrome_info['chrome_version']}")
    print(f"   Chromedriver: {chromedriver_info['status']}")
    print(f"   Chromedriver Message: {chromedriver_info['message']}")
    print("")
    
    if not chrome_info['chrome_installed']:
        print("⚠️  WARNING: Chrome not found! Sessions may fail.")
        print("💡 TIP: Install Chrome with: sudo apt install -y google-chrome-stable")
    
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
