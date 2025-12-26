"""
AI Call Caching - Cache expensive AI API calls to reduce costs
Uses SQLite with TTL (time-to-live) expiration
"""
import sqlite3
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AICache:
    """
    Cache AI API responses with TTL expiration

    Cost savings example:
    - Without cache: $0.80 per municipality
    - With cache (40% hit rate): $0.48 per municipality
    - Savings: 40%
    """

    def __init__(
        self,
        db_path: str = "cache/ai_cache.db",
        default_ttl_hours: int = 24
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.default_ttl_hours = default_ttl_hours

        self._init_database()

        # Statistics
        self.hits = 0
        self.misses = 0

    def _init_database(self):
        """Initialize SQLite cache database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                response TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                expires_at DATETIME NOT NULL,
                hit_count INTEGER DEFAULT 0,
                last_hit_at DATETIME
            )
        """)

        # Index for expiration cleanup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at
            ON cache(expires_at)
        """)

        conn.commit()
        conn.close()

        logger.info(f"✅ AI cache initialized: {self.db_path}")

    def _generate_cache_key(
        self,
        prompt: str,
        model: str,
        image_data: Optional[str] = None
    ) -> str:
        """
        Generate cache key from prompt and image

        Args:
            prompt: Text prompt
            model: Model name
            image_data: Optional base64 image data

        Returns:
            Cache key (SHA256 hash)
        """
        # Combine prompt, model, and image
        cache_input = f"{model}:{prompt}"
        if image_data:
            # For images, hash first 1000 chars to avoid huge keys
            cache_input += f":{image_data[:1000]}"

        # Generate hash
        cache_key = hashlib.sha256(cache_input.encode()).hexdigest()
        return cache_key

    def get(
        self,
        prompt: str,
        model: str,
        image_data: Optional[str] = None
    ) -> Optional[str]:
        """
        Get cached response if available and not expired

        Args:
            prompt: Text prompt
            model: Model name
            image_data: Optional base64 image data

        Returns:
            Cached response or None if cache miss
        """
        cache_key = self._generate_cache_key(prompt, model, image_data)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get from cache
        cursor.execute("""
            SELECT response, expires_at
            FROM cache
            WHERE cache_key = ?
        """, (cache_key,))

        row = cursor.fetchone()

        if not row:
            self.misses += 1
            conn.close()
            return None

        response, expires_at = row
        expires_at = datetime.fromisoformat(expires_at)

        # Check if expired
        if datetime.now() > expires_at:
            # Expired, delete and return None
            cursor.execute("DELETE FROM cache WHERE cache_key = ?", (cache_key,))
            conn.commit()
            conn.close()
            self.misses += 1
            logger.debug(f"⏰ Cache expired: {cache_key[:8]}...")
            return None

        # Cache hit! Update statistics
        cursor.execute("""
            UPDATE cache
            SET hit_count = hit_count + 1,
                last_hit_at = ?
            WHERE cache_key = ?
        """, (datetime.now(), cache_key))

        conn.commit()
        conn.close()

        self.hits += 1
        logger.info(f"✅ Cache HIT: {cache_key[:8]}... (model: {model})")

        return response

    def set(
        self,
        prompt: str,
        model: str,
        response: str,
        ttl_hours: Optional[int] = None,
        image_data: Optional[str] = None
    ):
        """
        Store response in cache

        Args:
            prompt: Text prompt
            model: Model name
            response: AI response to cache
            ttl_hours: Time-to-live in hours (default: 24)
            image_data: Optional base64 image data
        """
        cache_key = self._generate_cache_key(prompt, model, image_data)
        ttl_hours = ttl_hours or self.default_ttl_hours

        created_at = datetime.now()
        expires_at = created_at + timedelta(hours=ttl_hours)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Insert or replace
        cursor.execute("""
            INSERT OR REPLACE INTO cache
            (cache_key, response, model, created_at, expires_at, hit_count, last_hit_at)
            VALUES (?, ?, ?, ?, ?, 0, NULL)
        """, (cache_key, response, model, created_at, expires_at))

        conn.commit()
        conn.close()

        logger.debug(f"💾 Cache SET: {cache_key[:8]}... (expires: {ttl_hours}h)")

    def clear_expired(self):
        """Remove expired entries from cache"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM cache
            WHERE expires_at < ?
        """, (datetime.now(),))

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted_count > 0:
            logger.info(f"🗑️  Cleared {deleted_count} expired cache entries")

        return deleted_count

    def clear_all(self):
        """Clear entire cache"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("DELETE FROM cache")
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"🗑️  Cleared all cache ({deleted_count} entries)")

        return deleted_count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Total entries
        cursor.execute("SELECT COUNT(*) FROM cache")
        total_entries = cursor.fetchone()[0]

        # Expired entries
        cursor.execute("SELECT COUNT(*) FROM cache WHERE expires_at < ?", (datetime.now(),))
        expired_entries = cursor.fetchone()[0]

        # Most hit entries
        cursor.execute("""
            SELECT model, hit_count, created_at
            FROM cache
            ORDER BY hit_count DESC
            LIMIT 5
        """)
        most_hit = cursor.fetchall()

        conn.close()

        # Calculate hit rate
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "valid_entries": total_entries - expired_entries,
            "session_hits": self.hits,
            "session_misses": self.misses,
            "hit_rate": hit_rate,
            "most_hit": [
                {
                    "model": row[0],
                    "hit_count": row[1],
                    "created_at": row[2]
                }
                for row in most_hit
            ]
        }

    def estimate_cost_savings(
        self,
        avg_cost_per_call: float = 0.05
    ) -> Dict[str, Any]:
        """
        Estimate cost savings from cache

        Args:
            avg_cost_per_call: Average cost per AI API call

        Returns:
            Cost savings breakdown
        """
        total_requests = self.hits + self.misses
        if total_requests == 0:
            return {
                "total_requests": 0,
                "cache_hits": 0,
                "cost_without_cache": 0.0,
                "cost_with_cache": 0.0,
                "savings": 0.0,
                "savings_percentage": 0.0
            }

        cost_without_cache = total_requests * avg_cost_per_call
        cost_with_cache = self.misses * avg_cost_per_call
        savings = cost_without_cache - cost_with_cache
        savings_percentage = (savings / cost_without_cache) * 100 if cost_without_cache > 0 else 0

        return {
            "total_requests": total_requests,
            "cache_hits": self.hits,
            "cache_misses": self.misses,
            "hit_rate": self.hits / total_requests,
            "cost_without_cache": cost_without_cache,
            "cost_with_cache": cost_with_cache,
            "savings": savings,
            "savings_percentage": savings_percentage
        }


# Decorator for caching AI calls
def cached_ai_call(cache: AICache, ttl_hours: int = 24):
    """
    Decorator to cache AI function calls

    Usage:
        @cached_ai_call(cache=ai_cache, ttl_hours=24)
        def my_ai_function(prompt: str, model: str) -> str:
            # ... call AI API
            return response
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract prompt and model from args/kwargs
            prompt = kwargs.get('prompt') or (args[0] if len(args) > 0 else None)
            model = kwargs.get('model') or (args[1] if len(args) > 1 else None)

            if not prompt or not model:
                # Can't cache without prompt and model
                return await func(*args, **kwargs)

            # Check cache
            cached_response = cache.get(prompt, model)
            if cached_response:
                return cached_response

            # Cache miss - call function
            response = await func(*args, **kwargs)

            # Store in cache
            cache.set(prompt, model, response, ttl_hours=ttl_hours)

            return response

        return wrapper
    return decorator


# For testing
if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING AI CACHE")
    print("="*80)

    cache = AICache()

    # Test data
    prompt1 = "Analyze this form and extract fields"
    prompt2 = "Generate Python scraper code for this form"
    model = "claude-sonnet-4"

    # Set some cache entries
    print("\n📝 Setting cache entries...")
    cache.set(prompt1, model, '{"fields": ["name", "email"]}', ttl_hours=24)
    cache.set(prompt2, model, 'class FormScraper:\n    pass', ttl_hours=24)

    # Test cache hits
    print("\n✅ Testing cache hits...")
    response1 = cache.get(prompt1, model)
    print(f"Response 1: {response1[:50]}...")

    response2 = cache.get(prompt2, model)
    print(f"Response 2: {response2[:50]}...")

    # Test cache miss
    print("\n❌ Testing cache miss...")
    response3 = cache.get("This prompt was never cached", model)
    print(f"Response 3: {response3}")

    # Get statistics
    print("\n📊 Cache Statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        if key != "most_hit":
            print(f"   {key}: {value}")

    # Estimate cost savings
    print("\n💰 Cost Savings Estimate:")
    savings = cache.estimate_cost_savings(avg_cost_per_call=0.05)
    for key, value in savings.items():
        if isinstance(value, float):
            if "percentage" in key:
                print(f"   {key}: {value:.1f}%")
            elif "cost" in key or "savings" in key:
                print(f"   {key}: ${value:.4f}")
            else:
                print(f"   {key}: {value:.2f}")
        else:
            print(f"   {key}: {value}")

    # Clear expired
    print("\n🗑️  Clearing expired entries...")
    deleted = cache.clear_expired()
    print(f"   Deleted: {deleted} entries")

    print("\n" + "="*80)
