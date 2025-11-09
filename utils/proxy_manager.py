import requests
import random

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.valid_proxies = []
    
    def add_proxy(self, proxy_config):
        """Add proxy configuration"""
        self.proxies.append(proxy_config)
    
    def validate_proxy(self, proxy_config, timeout=10):
        """Validate proxy connection"""
        try:
            proxies = {
                'http': f"http://{proxy_config['username']}:{proxy_config['password']}@{proxy_config['host']}:{proxy_config['port']}",
                'https': f"http://{proxy_config['username']}:{proxy_config['password']}@{proxy_config['host']}:{proxy_config['port']}"
            }
            response = requests.get('https://httpbin.org/ip', proxies=proxies, timeout=timeout)
            if response.status_code == 200:
                return True
        except:
            pass
        return False
    
    def get_random_proxy(self):
        """Get random validated proxy"""
        if self.valid_proxies:
            return random.choice(self.valid_proxies)
        return None
    
    def validate_all_proxies(self):
        """Validate all proxies in the list"""
        self.valid_proxies = []
        for proxy in self.proxies:
            if self.validate_proxy(proxy):
                self.valid_proxies.append(proxy)
        
        return len(self.valid_proxies)
    
    def load_proxies_from_file(self, file_path):
        """Load proxies from JSON file"""
        import json
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                self.proxies = data.get('proxies', [])
            return True
        except:
            return False
    
    def save_proxies_to_file(self, file_path):
        """Save proxies to JSON file"""
        import json
        try:
            with open(file_path, 'w') as f:
                json.dump({'proxies': self.proxies}, f, indent=2)
            return True
        except:
            return False
