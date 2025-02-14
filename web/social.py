import re
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache


class NitterClient:
    """Client for fetching Twitter/X data via Nitter."""

    # List of Nitter instances to try in case of failure
    NITTER_INSTANCES = [
        "https://nitter.net",
        "https://nitter.1d4.us",
        "https://nitter.kavin.rocks",
    ]

    def __init__(self, username):
        self.username = username
        self.base_url = self.get_working_instance()

    def get_working_instance(self):
        """Try each Nitter instance and return the first working one."""
        for instance in self.NITTER_INSTANCES:
            try:
                response = requests.get(f"{instance}/twitter", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                if response.status_code == 200:
                    return instance
            except requests.RequestException:
                continue
        return self.NITTER_INSTANCES[0]  # Default to first instance if none work

    def get_profile_stats(self):
        """
        Fetch profile statistics from Nitter.
        Returns dict with followers, following, tweets count, and last tweet info.
        """
        cache_key = f"nitter_stats_{self.username}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        try:
            response = requests.get(
                f"{self.base_url}/{self.username}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10
            )
            response.raise_for_status()
            html_content = response.text

            # Parse profile stats
            stats = {
                "followers": 0,
                "following": 0,
                "tweets": 0,
                "engagement": 0,
                "last_tweet": None,
                "name": None,
                "bio": None,
                "location": None,
                "website": None,
                "joined": None,
            }

            # Extract name
            name_pattern = r'class="profile-card-fullname"[^>]*>([^<]+)'
            name_match = re.search(name_pattern, html_content)
            if name_match:
                stats["name"] = name_match.group(1).strip()

            # Extract bio
            bio_pattern = r'class="profile-bio"[^>]*>([^<]+)'
            bio_match = re.search(bio_pattern, html_content)
            if bio_match:
                stats["bio"] = bio_match.group(1).strip()

            # Extract location
            location_pattern = r'class="profile-location"[^>]*>([^<]+)'
            location_match = re.search(location_pattern, html_content)
            if location_match:
                stats["location"] = location_match.group(1).strip()

            # Extract website
            website_pattern = r'class="profile-website"[^>]*href="([^"]+)"'
            website_match = re.search(website_pattern, html_content)
            if website_match:
                stats["website"] = website_match.group(1)

            # Extract joined date
            joined_pattern = r'class="profile-joindate"[^>]*>Joined ([^<]+)'
            joined_match = re.search(joined_pattern, html_content)
            if joined_match:
                try:
                    stats["joined"] = datetime.strptime(joined_match.group(1).strip(), "%B %Y")
                except ValueError:
                    pass

            # Extract numeric stats using regex
            followers_pattern = r'class="followers"[^>]*>.*?' r'class="profile-stat-num"[^>]*>([^<]+)'
            followers_match = re.search(followers_pattern, html_content, re.DOTALL)
            if followers_match:
                try:
                    stats["followers"] = int(followers_match.group(1).strip().replace(",", ""))
                except ValueError:
                    pass

            following_pattern = r'class="following"[^>]*>.*?' r'class="profile-stat-num"[^>]*>([^<]+)'
            following_match = re.search(following_pattern, html_content, re.DOTALL)
            if following_match:
                try:
                    stats["following"] = int(following_match.group(1).strip().replace(",", ""))
                except ValueError:
                    pass

            tweets_pattern = r'class="tweets"[^>]*>.*?' r'class="profile-stat-num"[^>]*>([^<]+)'
            tweets_match = re.search(tweets_pattern, html_content, re.DOTALL)
            if tweets_match:
                try:
                    stats["tweets"] = int(tweets_match.group(1).strip().replace(",", ""))
                except ValueError:
                    pass

            # Extract latest tweet date
            tweet_date_pattern = r'class="tweet-date"[^>]*>.*?title="([^"]+)"'
            tweet_date_match = re.search(tweet_date_pattern, html_content, re.DOTALL)
            if tweet_date_match:
                try:
                    stats["last_tweet"] = datetime.strptime(tweet_date_match.group(1), "%b %d, %Y · %I:%M %p UTC")
                except ValueError:
                    pass

            # Calculate engagement rate
            if stats["followers"] > 0 and stats["tweets"] > 0:
                stats["engagement"] = round((stats["tweets"] / stats["followers"]) * 100, 2)

            # Cache the results for 1 hour
            cache.set(cache_key, stats, timeout=3600)

            return stats

        except requests.RequestException as e:
            print(f"Error fetching Nitter stats from {self.base_url}: {str(e)}")
            # Try another instance if current one fails
            self.base_url = self.get_working_instance()
            if self.base_url != self.NITTER_INSTANCES[0]:
                return self.get_profile_stats()  # Retry with new instance
            return {
                "followers": 0,
                "following": 0,
                "tweets": 0,
                "engagement": 0,
                "last_tweet": None,
                "name": None,
                "bio": None,
                "location": None,
                "website": None,
                "joined": None,
            }
        except Exception as e:
            print(f"Error parsing Nitter stats: {str(e)}")
            return {
                "followers": 0,
                "following": 0,
                "tweets": 0,
                "engagement": 0,
                "last_tweet": None,
                "name": None,
                "bio": None,
                "location": None,
                "website": None,
                "joined": None,
            }


def get_social_stats():
    """
    Get stats from all configured social media platforms.
    Returns dict with stats for each platform.
    """
    stats = {}

    # Get X/Twitter stats via Nitter
    if hasattr(settings, "TWITTER_USERNAME"):
        nitter = NitterClient(settings.TWITTER_USERNAME)
        x_stats = nitter.get_profile_stats()
        if x_stats:
            stats["x"] = {
                "stats": x_stats,
                "date": x_stats.get("last_tweet"),
                "status": "success" if x_stats.get("last_tweet") else "neutral",
            }

    # Add other social media platforms here as needed

    return stats
