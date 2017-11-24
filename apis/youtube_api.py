"""Accessing YouTube APIs"""

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

    def get_user_profile(self):
        """Get user profile"""
        return self.get("https://api.spotify.com/v1/me")

    def get_user_playlists(self):
        """Get user playlists"""
        return self.get("https://api.spotify.com/v1/me/playlists")
