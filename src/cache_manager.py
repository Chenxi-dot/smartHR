import os
import json
import sqlite3
import time
import pickle
import hashlib
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class CacheManager:
    def __init__(self, db_path="parsed_data.db", redis_host='localhost', redis_port=6379):
        self.db_path = db_path
        self.redis_client = None
        self.redis_available = False
        
        # Initialize SQLite
        self._init_sqlite()
        
        # Initialize Redis
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=False)
                self.redis_client.ping()
                self.redis_available = True
                print("Redis connected successfully.")
            except Exception as e:
                print(f"Redis connection failed: {e}. Using SQLite/File cache only.")
        
    def _init_sqlite(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Create table for structured resume data
        c.execute('''CREATE TABLE IF NOT EXISTS parsed_resumes
                     (id TEXT PRIMARY KEY, 
                      hash TEXT, 
                      parsed_data BLOB, 
                      timestamp REAL)''')
        conn.commit()
        conn.close()

    def get_cached_resume(self, resume_id, content_hash):
        # 1. Try Redis (7 days expiry)
        if self.redis_available:
            try:
                cache_key = f"resume:{resume_id}"
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    data = pickle.loads(cached_data)
                    # Verify hash
                    if data.get('hash') == content_hash:
                        return data.get('content', data)
            except Exception as e:
                print(f"Redis get error: {e}")

        # 2. Try SQLite
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT hash, parsed_data FROM parsed_resumes WHERE id=?", (resume_id,))
            row = c.fetchone()
            conn.close()
            
            if row:
                stored_hash, blob_data = row
                if stored_hash == content_hash:
                    data = pickle.loads(blob_data)
                    content = data.get('content', data) if isinstance(data, dict) else data
                    # Refresh Redis if available
                    if self.redis_available:
                        self.set_cached_resume(resume_id, content_hash, content)
                    return content
        except Exception as e:
            print(f"SQLite get error: {e}")
            
        return None

    def set_cached_resume(self, resume_id, content_hash, parsed_content):
        serialized_content = pickle.dumps({"hash": content_hash, "content": parsed_content})
        
        # 1. Save to Redis
        if self.redis_available:
            try:
                cache_key = f"resume:{resume_id}"
                self.redis_client.setex(cache_key, 7 * 24 * 3600, serialized_content)
            except Exception as e:
                print(f"Redis set error: {e}")
        
        # 2. Save to SQLite
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO parsed_resumes (id, hash, parsed_data, timestamp) VALUES (?, ?, ?, ?)",
                      (resume_id, content_hash, serialized_content, time.time()))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"SQLite set error: {e}")

    @staticmethod
    def compute_hash(text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()
