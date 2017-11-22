"""Accessing Spotify APIs"""

from oauth2 import OAuth2Session

#pylint: disable=C0103

class SpotifyClient(OAuth2Session):
    """Spotify API with OAuth2 support"""
    def __init__(self, flask, client_id, client_secret, auth_callback_url):
        super(SpotifyClient, self).__init__(
            flask,
            client_id, client_secret,
            "https://accounts.spotify.com/authorize",
            auth_callback_url,
            "https://accounts.spotify.com/api/token"
        )

    def get_user_profile(self):
        """Get user profile"""
        return self.get("https://api.spotify.com/v1/me")

    def get_user_playlists(self):
        """Get user playlists"""
        return self.get("https://api.spotify.com/v1/me/playlists")
