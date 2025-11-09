import os
import json
import time
import random
import threading
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
# TRAFFIC BOT ENGINE WITH PLAYWRIGHT
# ==============================

class TrafficBot:
    def __init__(self, session_id, profile_data, target_url, proxy_config=None):
        self.session_id = session_id
        self.profile_data = profile_data
        self.target_url = target_url
        self.proxy_config = proxy_config
        self.playwright = None
        self.browser = None
        self.page = None
        self.is_running = True
        self.current_step = "initializing"
        
    def setup_browser(self):
        """Setup browser dengan Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            self.log_step("setup_browser", "error", "Playwright not available")
            return False
            
        try:
            logger.info(f"🔄 Starting Playwright browser for session {self.session_id}")
            
            # Start Playwright
            self.playwright = sync_playwright().start()
            
            # Launch browser
            browser_launch_options = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding"
                ]
            }
            
            self.browser = self.playwright.chromium.launch(**browser_launch_options)
            
            # Create context dengan user agent
            context_options = {
                "user_agent": self.profile_data.get('user_agent', UserAgentGenerator.generate_desktop()),
                "viewport": {"width": 1920, "height": 1080} if self.profile_data.get('profile_type') == 'desktop' else {"width": 375, "height": 812}
            }
            
            # Proxy configuration jika ada
            if self.proxy_config and self.proxy_config.get('type') != 'direct':
                context_options["proxy"] = {
                    "server": f"{self.proxy_config.get('type')}://{self.proxy_config.get('host')}:{self.proxy_config.get('port')}",
                    "username": self.proxy_config.get('username'),
                    "password": self.proxy_config.get('password')
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
        
        # Update session progress
        self.update_session_progress(step, status)
        
        logger.info(f"📝 {step} - {status}: {message}")
    
    def update_session_progress(self, step, status):
        """Update session progress di sessions.json"""
        sessions_data = read_json(SESSIONS_FILE)
        for session in sessions_data.get("sessions", []):
            if session.get("session_id") == self.session_id:
                session["current_step"] = step
                session["status"] = status
                
                # Calculate progress percentage berdasarkan step
                progress_map = {
                    "initializing": 10,
                    "setup_browser": 20,
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
                scroll_height = self.page.evaluate("document.body.scrollHeight")
                current_position = 0
                target_position = scroll_height * 0.8
                
                while current_position < target_position and self.is_running:
                    increment = random.randint(100, 300)
                    current_position += increment
                    
                    # Smooth scroll
                    self.page.evaluate(f"window.scrollTo(0, {current_position})")
                    
                    # Random pause
                    time.sleep(random.uniform(0.5, 2.0))
                    
                    # Occasionally scroll back a bit (human behavior)
                    if random.random() < 0.2:
                        back_scroll = random.randint(50, 150)
                        current_position -= back_scroll
                        self.page.evaluate(f"window.scrollTo(0, {current_position})")
                        time.sleep(random.uniform(0.5, 1.5))
                
                # Scroll back to top occasionally
                if random.random() < 0.3 and self.is_running:
                    self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
                    time.sleep(random.uniform(1, 3))
            
            return True
        except Exception as e:
            self.log_step("scrolling", "error", f"Scrolling error: {str(e)}")
            return False
    
    def check_data_leak(self):
        """Check untuk IP/DNS leaks"""
        try:
            # Test IP address
            self.page.goto("https://httpbin.org/ip", wait_until="networkidle")
            time.sleep(2)
            
            # Get IP dari response
            ip_text = self.page.content()
            self.log_step("data_leak_check", "success", f"IP Check completed: {ip_text[:100]}...")
            
            return True
        except Exception as e:
            self.log_step("data_leak_check", "error", f"Data leak check failed: {str(e)}")
            return False
    
    def skip_google_ads(self):
        """Attempt to skip Google ads jika ada"""
        try:
            # Common ad selectors
            ad_selectors = [
                "button[aria-label*='close' i]",
                "button[class*='close' i]",
                "div[class*='ad' i] button",
                ".ad-close",
                ".close-button",
                "[aria-label*='tutup' i]",
                "[class*='dismiss' i]"
            ]
            
            ads_skipped = 0
            for selector in ad_selectors:
                if not self.is_running:
                    break
                
                try:
                    elements = self.page.query_selector_all(selector)
                    for element in elements:
                        if element.is_visible() and self.is_running:
                            # Human-like delay before clicking
                            time.sleep(random.uniform(0.5, 1.5))
                            element.click()
                            ads_skipped += 1
                            self.log_step("skipping_ads", "success", f"Skipped ad #{ads_skipped}")
                            time.sleep(1)
                except:
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
        """Click pada random post/link di page"""
        try:
            # Find semua clickable elements
            clickable_selectors = [
                "a[href*='/p/']",
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
                    elements = self.page.query_selector_all(selector)
                    # Filter visible elements
                    visible_elements = [el for el in elements if el.is_visible()]
                    all_elements.extend(visible_elements)
                except:
                    continue
            
            if all_elements:
                # Avoid clicking the first few elements
                if len(all_elements) > 3:
                    element_to_click = random.choice(all_elements[2:min(8, len(all_elements))])
                    
                    # Scroll to element
                    element_to_click.scroll_into_view_if_needed()
                    time.sleep(random.uniform(1, 2))
                    
                    # Click element
                    element_to_click.click()
                    
                    self.log_step("clicking_post", "success", "Clicked on random post")
                    time.sleep(random.uniform(3, 5))
                    return True
            
            self.log_step("clicking_post", "skipped", "No suitable posts found to click")
            return False
        except Exception as e:
            self.log_step("clicking_post", "error", f"Clicking post failed: {str(e)}")
            return False
    
    def clear_cache(self):
        """Clear browser cache"""
        try:
            if self.browser:
                # Clear cookies dan storage
                self.page.context.clear_cookies()
                self.log_step("clearing_cache", "success", "Cache and cookies cleared")
            return True
        except Exception as e:
            self.log_step("clearing_cache", "error", f"Cache clearing failed: {str(e)}")
            return False
    
    def run_session(self):
        """Main session execution"""
        try:
            self.log_step("initializing", "running", "Session started", {
                "profile": self.profile_data.get('profile_name'),
                "target_url": self.target_url,
                "proxy": "Yes" if self.proxy_config else "No"
            })
            
            # Step 1: Setup browser
            if not self.setup_browser():
                return
            
            # Step 2: Check data leaks
            if self.is_running:
                self.check_data_leak()
            
            # Step 3: Open target URL
            if self.is_running:
                try:
                    self.page.goto(self.target_url, wait_until="networkidle")
                    self.log_step("opening_url", "success", f"Opened URL: {self.target_url}")
                    time.sleep(random.uniform(3, 5))
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
                    self.page.go_back(wait_until="networkidle")
                    self.log_step("navigation", "success", "Returned to original page")
                    time.sleep(random.uniform(2, 3))
            
            # Step 7: Continue scrolling on main page
            if self.is_running:
                self.human_like_scroll(1)
                self.log_step("scrolling", "success", "Final scrolling completed")
            
            # Step 8: Final scroll to top
            if self.is_running:
                self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
                time.sleep(1)
                self.log_step("returning_home", "success", "Returned to top of page")
            
            # Step 9: Clear cache
            if self.is_running:
                self.clear_cache()
            
            # Mark as completed
            if self.is_running:
                self.log_step("completed", "success", "Session completed successfully")
            
        except Exception as e:
            self.log_step("error", "failed", f"Session failed: {str(e)}")
        finally:
            # Cleanup
            try:
                if self.browser:
                    self.browser.close()
                if self.playwright:
                    self.playwright.stop()
                logger.info(f"✅ Browser closed for session {self.session_id}")
            except Exception as e:
                logger.error(f"❌ Cleanup error: {e}")
            
            # Update final session status
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
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass

# ==============================
# FLASK ROUTES
# ==============================

active_sessions = {}

@app.route('/')
def index():
    return "🚀 Traffic Bot with Playwright is Running!"

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "playwright_available": PLAYWRIGHT_AVAILABLE,
        "active_sessions": len(active_sessions),
        "message": "Using Playwright for browser automation"
    })

@app.route('/api/test-playwright', methods=['GET'])
def test_playwright():
    """Test Playwright functionality"""
    if not PLAYWRIGHT_AVAILABLE:
        return jsonify({"success": False, "message": "Playwright not available"}), 500
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://httpbin.org/ip")
            
            result = {
                "success": True,
                "page_title": page.title(),
                "status": "Playwright test passed!",
                "message": "Browser automation is working correctly"
            }
            
            browser.close()
            return jsonify(result)
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }), 500

@app.route('/api/create_session', methods=['POST'])
def create_session():
    """Create and start a new bot session"""
    if not PLAYWRIGHT_AVAILABLE:
        return jsonify({"success": False, "message": "Playwright not available"}), 500
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['profile_type', 'target_url']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400
        
        # Check max sessions limit
        config = read_json(CONFIG_FILE)
        max_sessions = config.get('max_sessions', 3)
        
        sessions_data = read_json(SESSIONS_FILE)
        active_count = len([s for s in sessions_data.get('sessions', []) if s.get('status') in ['running', 'starting']])
        
        if active_count >= max_sessions:
            return jsonify({"success": False, "message": f"Maximum {max_sessions} concurrent sessions allowed"}), 400
        
        # Generate session data
        session_id = f"sess_{sessions_data['session_counter'] + 1:03d}"
        
        # Create profile data
        profile_type = data.get('profile_type', 'desktop')
        user_agent = UserAgentGenerator.generate_mobile() if profile_type == 'mobile' else UserAgentGenerator.generate_desktop()
        
        profile_data = {
            "profile_name": f"{profile_type}_profile_{sessions_data['session_counter'] + 1}",
            "profile_type": profile_type,
            "user_agent": user_agent
        }
        
        # Create session entry
        session_entry = {
            "session_id": session_id,
            "profile_name": profile_data['profile_name'],
            "user_agent": profile_type,
            "target_url": data['target_url'],
            "status": "starting",
            "current_step": "initializing",
            "start_time": datetime.now().isoformat(),
            "progress": 0
        }
        
        sessions_data['sessions'].append(session_entry)
        sessions_data['session_counter'] += 1
        write_json(sessions_data, SESSIONS_FILE)
        
        # Start bot in separate thread
        bot = TrafficBot(session_id, profile_data, data['target_url'])
        active_sessions[session_id] = bot
        
        thread = threading.Thread(target=bot.run_session)
        thread.daemon = True
        thread.start()
        
        logger.info(f"🚀 Started new session: {session_id}")
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "message": "Session started successfully"
        })
        
    except Exception as e:
        logger.error(f"❌ Error creating session: {str(e)}")
        return jsonify({"success": False, "message": f"Error creating session: {str(e)}"}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all sessions"""
    try:
        sessions_data = read_json(SESSIONS_FILE)
        return jsonify(sessions_data.get('sessions', []))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get session logs"""
    try:
        logs_data = read_json(LOGS_FILE)
        return jsonify(logs_data.get('logs', []))
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
        for session in sessions_data['sessions']:
            if session['session_id'] == session_id:
                session['status'] = 'stopped'
                break
        
        write_json(sessions_data, SESSIONS_FILE)
        return jsonify({"success": True, "message": "Session stopped successfully"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🚀 TRAFFIC BOT WITH PLAYWRIGHT STARTING...")
    print("=" * 60)
    print(f"🔧 Playwright Available: {PLAYWRIGHT_AVAILABLE}")
    print(f"🌐 Server port: {port}")
    print("=" * 60)
    
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ WARNING: Playwright not available!")
    else:
        print("✅ Playwright is ready for browser automation!")
    
    app.run(host='0.0.0.0', port=port, debug=False)
