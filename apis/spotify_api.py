"""Accessing Spotify APIs"""
import time
import math

from apis.oauth2 import OAuth2Session

#pylint: disable=C0103

class SpotifyClient(OAuth2Session):
    """Spotify API with OAuth2 support"""
    def __init__(self, flask, client_id, client_secret, auth_callback_url):
        super(SpotifyClient, self).__init__(
            flask, "Spotify",
            client_id, client_secret,
            "https://accounts.spotify.com/authorize",
            auth_callback_url,
            "https://accounts.spotify.com/api/token"
        )

    def get(self, method, params=None):
        """Override default oauth2 .get to handle HTTP 429 Too Many Requests"""
        res = self.make_get_request(method, params)

        if res.status_code == 200:
            # Success
            try:
                # Parse content as JSON
                return res.json()

            except ValueError:
                # Failed to parse content as JSON
                raise OAuth2Session.Exceptions.RequestFailedException()

        elif res.status_code == 427:
            # HTTP 427 Too Many Requests
            try:
                # Wait for specified amount of seconds
                wait_duration = int(res.headers["Retry-After"])
                time.sleep(wait_duration)

                # Try again
                return self.get(method, params)

            except KeyError:
                # Missing amount of seconds to wait
                raise OAuth2Session.Exceptions.RequestFailedException()

        else:
            # All other status codes
            raise OAuth2Session.Exceptions.RequestFailedException()

    def get_user_profile(self):
        """Get user profile"""
        return self.get("https://api.spotify.com/v1/me")

    def get_user_playlists(self):
        """Get user playlists"""
        return self.get("https://api.spotify.com/v1/me/playlists")

    def search_track(self, query):
        """Search for a single track by query"""
        print(u"Querying Spotify: {}".format(query))

        # Perform search
        search_result = self.get("https://api.spotify.com/v1/search", {
            "q": unicode(query).encode("utf-8"),
            "type": "track",
            "limit": 1
        })

        try: 
            items = search_result["tracks"]["items"]
            if len(items) < 1:
                return {
                    "name": None,
                    "uri": None
                }
            else:
                return {
                    "name": items[0]["name"],
                    "uri": items[0]["uri"]
                }
        except KeyError:
            # Invalid response
            raise OAuth2Session.Exceptions.RequestFailedException()

    def add_tracks_to_playlist(self, user_id, playlist_id, track_uris):
        """Add tracks to playlist"""
        method = "https://api.spotify.com/v1/users/{user_id}/playlists/{playlist_id}/tracks".format(
            user_id=user_id, playlist_id=playlist_id)

        if len(track_uris) <= 100:
            # Post to API
            self.post(method, body={"uris": track_uris})
        else:
            # Split and add them in separated requests
            for i in range(0, int(math.ceil(len(track_uris) / 100.))):
                self.add_tracks_to_playlist(user_id, playlist_id, track_uris[100*i : 100*(i+1)])
