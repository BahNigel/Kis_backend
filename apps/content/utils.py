# content/utils.py
import hashlib
from django.utils import timezone

def hash_ip(ip_str: str) -> str:
    """
    Hash an IP address to protect PII. Use salted hashing in production.
    """
    if not ip_str:
        return ""
    return hashlib.sha256(ip_str.encode("utf-8")).hexdigest()

def human_trending_description(score: float) -> str:
    if score > 10:
        return "Very Hot"
    if score > 3:
        return "Trending"
    if score > 0.5:
        return "Gaining"
    return "Low"
