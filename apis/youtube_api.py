"""Accessing YouTube APIs"""
import re
from apis.oauth2 import OAuth2Session

#pylint: disable=C0103

class YouTubeClient(OAuth2Session):
    """YouTube API with OAuth2 support"""
    def __init__(self, flask, client_id, client_secret, auth_callback_url):
        super(YouTubeClient, self).__init__(
            flask, "YouTube",
            client_id, client_secret,
            "https://accounts.google.com/o/oauth2/v2/auth",
            auth_callback_url,
            "https://accounts.google.com/o/oauth2/token"
        )

    def get_playlist_items(self, playlist_id):
        """
        Get playlist items by id

        Sample playlist id: RD2Vv-BfVoq4g
        """
        return self.get("https://www.googleapis.com/youtube/v3/playlistItems", {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50
        })

    @staticmethod
    def process_youtube_name(name):
        """Clean up a YouTube video name. Removes (...), [...] and ft. ..."""
        return re.sub(r"( \[.+?\]| \(.+?\)| ft.+?$)", "", name)
