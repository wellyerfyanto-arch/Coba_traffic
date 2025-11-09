import os
import time
import random
import threading
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .user_agent import UserAgentGenerator
from .helpers import read_json, write_json

class TrafficBot:
    def __init__(self, session_id, profile_data, target_url, proxy_config=None, 
                 sessions_file='data/sessions.json', logs_file='data/logs.json'):
        self.session_id = session_id
        self.profile_data = profile_data
        self.target_url = target_url
        self.proxy_config = proxy_config
        self.sessions_file = sessions_file
        self.logs_file = logs_file
        self.driver = None
        self.is_running = True
        self.current_step = "initializing"
        
    def setup_driver(self):
        """Setup Chrome driver with configuration"""
        try:
            chrome_options = Options()
            
            # Basic options for stability
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
        logs_data = read_json(self.logs_file)
        logs_data.setdefault("logs", []).append(log_entry)
        write_json(logs_data, self.logs_file)
        
        # Update session progress
        self.update_session_progress(step, status)
    
    def update_session_progress(self, step, status):
        """Update session progress in sessions.json"""
        sessions_data = read_json(self.sessions_file)
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
        
        write_json(sessions_data, self.sessions_file)
    
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
                target_position = scroll_height
                
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
            # Test IP address
            self.driver.get("https://httpbin.org/ip")
            time.sleep(2)
            
            # Get IP from response
            ip_text = self.driver.find_element(By.TAG_NAME, "body").text
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
                "[class*='dismiss' i]"
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
                            button.click()
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
                "a:not([href*='#']):not([href*='facebook']):not([href*='twitter']):not([href*='instagram'])"
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
            
            if all_elements:
                # Avoid clicking the first few elements (usually navigation)
                if len(all_elements) > 3:
                    element_to_click = random.choice(all_elements[2:min(8, len(all_elements))])
                    
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
                
                # Clear indexedDB (if supported)
                self.driver.execute_script("""
                    try {
                        indexedDB.databases().then(function(databases) {
                            databases.forEach(function(db) {
                                indexedDB.deleteDatabase(db.name);
                            });
                        });
                    } catch(e) {}
                """)
                
                self.log_step("clearing_cache", "success", "Cache, cookies and storage cleared")
            return True
        except Exception as e:
            self.log_step("clearing_cache", "error", f"Cache clearing failed: {str(e)}")
            return False
    
    def run_session(self):
        """Main session execution"""
        try:
            self.log_step("initializing", "running", "Session started", {
                "profile": self.profile_data,
                "target_url": self.target_url,
                "proxy": self.proxy_config
            })
            
            # Step 1: Setup driver
            if not self.setup_driver():
                self.log_step("setup_driver", "failed", "Driver setup failed")
                return
            
            self.log_step("setup_driver", "success", "WebDriver setup completed")
            
            # Step 2: Check data leaks
            if self.is_running:
                self.check_data_leak()
            
            # Step 3: Open target URL
            if self.is_running:
                self.driver.get(self.target_url)
                self.log_step("opening_url", "success", f"Opened URL: {self.target_url}")
                time.sleep(random.uniform(3, 5))  # Wait for page load
            
            # Step 4: Initial scrolling
            if self.is_running:
                self.human_like_scroll(2)
                self.log_step("scrolling", "success", "Initial scrolling completed")
            
            # Step 5: Skip ads
            if self.is_running:
                self.skip_google_ads()
            
            # Step 6: Click random post
            if self.is_running:
                post_clicked = self.click_random_post()
                
                # If post was clicked, interact with the new page
                if post_clicked and self.is_running:
                    # Scroll on the new page
                    self.human_like_scroll(2)
                    time.sleep(random.uniform(2, 4))
                    
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
            # Cleanup
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            
            # Update final session status
            sessions_data = read_json(self.sessions_file)
            for session in sessions_data.get("sessions", []):
                if session.get("session_id") == self.session_id:
                    if self.is_running:
                        session["status"] = "completed"
                        session["progress"] = 100
                    else:
                        session["status"] = "stopped"
                    break
            write_json(sessions_data, self.sessions_file)
    
    def stop(self):
        """Stop the session"""
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
