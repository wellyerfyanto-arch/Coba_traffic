import os
import json
from datetime import datetime

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
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error writing to {file_path}: {e}")
        return False

def init_data_files():
    """Initialize data files if they don't exist"""
    data_dir = 'data'
    files = {
        os.path.join(data_dir, 'profiles.json'): {"profiles": []},
        os.path.join(data_dir, 'sessions.json'): {"sessions": [], "session_counter": 0},
        os.path.join(data_dir, 'logs.json'): {"logs": []},
        os.path.join(data_dir, 'config.json'): {
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
    
    for file_path, default_data in files.items():
        if not os.path.exists(file_path):
            write_json(default_data, file_path)

def get_timestamp():
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()

def validate_url(url):
    """Basic URL validation"""
    import re
    pattern = re.compile(
        r'^(https?://)?'  # http:// or https://
        r'([a-zA-Z0-9.-]+)'  # domain
        r'(\.[a-zA-Z]{2,})'  # dot something
        r'(/.*)?$'  # optional path
    )
    return bool(pattern.match(url))
