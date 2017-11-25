"""Translate YouTube playlist into Spotify playlist"""

from __future__ import print_function
from uuid import uuid4
import hashlib
import json
import os
import sys
import traceback
import re

import flask
from flask_api import status

from apis.session_data import SessionDataContainer

from apis.oauth2 import OAuth2Session
from apis.spotify_api import SpotifyClient
from apis.youtube_api import YouTubeClient


# pylint: disable=C0103


"""
Client info (ids and secrets) file name
"""
CLIENT_INFO_FILE = "client_info.json"

# Read client ids and secrets
if not os.path.isfile(CLIENT_INFO_FILE):
    print("Cannot find {}, aborting.".format(CLIENT_INFO_FILE))
    sys.exit(1)

with open(CLIENT_INFO_FILE) as info:
    try:
        CLIENT_INFO = json.load(info)
    except ValueError:
        traceback.print_exc()
        print("Cannot parse {}, aborting.".format(CLIENT_INFO_FILE))
        sys.exit(1)


"""
Scopes to be used for OAuth
"""
SCOPES = {
    "spotify": (
        # Request playlists access
        "playlist-read-private",
        "playlist-read-collaborative",
        "playlist-modify-public",
        "playlist-modify-private"
    ),
    "youtube": (
        "https://www.googleapis.com/auth/youtube.readonly",
    )
}


"""
App configurations
"""
app = flask.Flask(__name__)
app.secret_key = os.urandom(24) # create secret key for signing cookies


"""
Session data storage
"""
session_data = SessionDataContainer()


"""
Handy functions
"""
class SessionNotCreatedException(Exception):
    """Session has not been created"""

def get_session_id():
    """Get session id"""
    print(session_data.session_data)
    try:
        return flask.session["session_id"]
    except KeyError:
        raise SessionNotCreatedException()

def get_session_data(*namespaces):
    """Get session data wrapper"""
    return session_data.get(get_session_id(), *namespaces)

def set_session_data(*namespaces, **props):
    """Set session data wrapper"""
    return session_data.set(get_session_id(), *namespaces, **props)

def remove_session_data(*namespaces):
    """Remove session data wrapper"""
    return session_data.remove(get_session_id(), *namespaces)

def process_youtube_name(name):
    """Clean up a YouTube video name. Removes (...), [...] and ft. ..."""
    return re.sub(r"( \[.+?\]| \(.+?\)| ft.+?$)", "", name)


"""
Decorators
"""
def handle_general_exceptions(f):
    """
    Handles these exceptions:

    - SessionNotCreatedException
    - SessionNamespaceNotFoundException
    - OAuth2Session.Exceptions.NotAuthorizedException
    - OAuth2Session.Exceptions.AccessTokenRequestFailedException
    """
    def wrapper(*args, **kargs):
        """Wrapper"""
        try:
            return f(*args, **kargs)

        except SessionNotCreatedException:
            return flask.redirect(flask.url_for("home"))

        except SessionDataContainer.Exceptions.NamespaceNotFoundException:
            return "OAuth session not created", status.HTTP_400_BAD_REQUEST

        except OAuth2Session.Exceptions.NotAuthorizedException:
            return "Not authorized", status.HTTP_400_BAD_REQUEST

        except OAuth2Session.Exceptions.AccessTokenRequestFailedException:
            return "Request access token failed", status.HTTP_400_BAD_REQUEST

    wrapper.__name__ = f.__name__
    return wrapper


"""
Routes
"""
@app.route("/create_session")
def create_session():
    """Start a session"""

    # Generate a new session id
    session_id = hashlib.sha1(str(uuid4())).hexdigest()

    # Assign session id
    flask.session["session_id"] = session_id

    # Create session data
    set_session_data(data={
        "oauth_sessions": {}
    })

    # Return to homepage
    return flask.redirect(flask.url_for("home"))


@app.route("/remove_session")
def remove_session():
    """End a session"""
    try:
        # Get current session id
        session_id = flask.session["session_id"]

        # Remove session data
        remove_session_data()

        # Remove session id
        flask.session.pop("session_id", None)

    except (KeyError, SessionDataContainer.Exceptions.NamespaceNotFoundException):
        # Session not exist
        pass

    # Return to homepage
    return flask.redirect(flask.url_for("home"))


@app.route("/")
@handle_general_exceptions
def home():
    """Homepage route"""
    try:
        # Get session id
        session_id = get_session_id()

        # Get authenticated services
        auths = {k: str(v) for (k, v) in get_session_data("oauth_sessions").iteritems()}

        return flask.render_template("status.html", session_id=session_id, auths=auths)

    except SessionNotCreatedException:
        return flask.render_template("guest.html")


@app.route("/auth_spotify")
@handle_general_exceptions
def auth_spotify():
    """Authenticate Spotify"""

    # Create new Spotify OAuth session
    spotify_session = SpotifyClient(
        flask,
        CLIENT_INFO["spotify"]["client_id"], CLIENT_INFO["spotify"]["client_secret"],
        "http://localhost:5000/spotify-authorization-callback")

    set_session_data("oauth_sessions", "spotify", data=spotify_session)

    # Authorize
    return spotify_session.authorize(SCOPES["spotify"])


@app.route("/spotify-authorization-callback")
@handle_general_exceptions
def auth_spotify_callback():
    """Callback route for Spotify auth"""
    try:
        # Get Spotify OAuth session
        spotify_session = get_session_data("oauth_sessions", "spotify")

        # Handle response
        spotify_session.hnadle_auth_callback()

        # Return to homepage
        return flask.redirect(flask.url_for("home"))

    except SessionDataContainer.Exceptions.NamespaceNotFoundException:
        return "Unexpected callback from service", status.HTTP_400_BAD_REQUEST

    except SpotifyClient.Exceptions.AuthorizationFailedException:
        return "Authorization failed", status.HTTP_400_BAD_REQUEST


@app.route("/auth_youtube")
@handle_general_exceptions
def auth_youtube():
    """Authenticate YouTube"""

    # Create new Spotify OAuth session
    youtube_session = YouTubeClient(
        flask,
        CLIENT_INFO["youtube"]["client_id"], CLIENT_INFO["youtube"]["client_secret"],
        "http://localhost:5000/youtube-authorization-callback")

    set_session_data("oauth_sessions", "youtube", data=youtube_session)

    # Authorize
    return youtube_session.authorize(SCOPES["youtube"], {
        "response_type": "code"
    })


@app.route("/youtube-authorization-callback")
@handle_general_exceptions
def auth_youtube_callback():
    """Callback route for YouTube auth"""

    try:
        # Get YouTube OAuth session
        youtube_session = get_session_data("oauth_sessions", "youtube")

        # Handle response
        youtube_session.hnadle_auth_callback()

        # Return to homepage
        return flask.redirect(flask.url_for("home"))

    except SessionDataContainer.Exceptions.NamespaceNotFoundException:
        return "Unexpected callback from service", status.HTTP_400_BAD_REQUEST

    except SpotifyClient.Exceptions.AuthorizationFailedException:
        return "Authorization failed", status.HTTP_400_BAD_REQUEST


@app.route("/request_token")
@handle_general_exceptions
def request_token():
    """General route for requesting token"""
    try:
        service_name = flask.request.args.get("service")
        if service_name is None:
            return flask.redirect(flask.url_for("home"))

        # Get service OAuth session
        session = get_session_data("oauth_sessions", service_name)

        # Manually request new token
        session.request_new_token()

        # Return to homepage
        return flask.redirect(flask.url_for("home"))

    except OAuth2Session.Exceptions.RequestFailedException:
        return "Request failed", status.HTTP_400_BAD_REQUEST


@app.route(("/read_youtube_playlist"))
@handle_general_exceptions
def read_youtube_playlist():
    """Route for translating videos in YouTube playlist into tracks in Spotify"""
    try:
        playlist_id = flask.request.args.get("youtube_playlist_id")
        if playlist_id is None:
            return "Invalid request", status.HTTP_400_BAD_REQUEST

        spotify_session = get_session_data("oauth_sessions", "spotify")
        youtube_session = get_session_data("oauth_sessions", "youtube")

        # Fetch playlist item names
        playlist_items = youtube_session.get_playlist_items(playlist_id)
        playlist_item_names = [item["snippet"]["title"] for item in playlist_items["items"]]

        # Look for Spotify mappings
        spotify_mappings = [
            spotify_session.search_track(process_youtube_name(youtube_name))
            for youtube_name in playlist_item_names
        ]

        # Organize result
        items = [{"youtube": youtube_names, "spotify": spotify_mapping} for
                 (youtube_names, spotify_mapping) in zip(playlist_item_names, spotify_mappings)]

        set_session_data("ongoing_translation", "mappings", data=items)

        return flask.render_template("youtube_playlist_display.html",
                                     youtube_playlist_id=playlist_id, items=items)

    except OAuth2Session.Exceptions.RequestFailedException:
        return "Request failed", status.HTTP_400_BAD_REQUEST


@app.route("/select_export_playlist", methods=["GET", "POST"])
@handle_general_exceptions
def select_export_playlist():
    """
    Route for

    GET: Selecting playlist to be exported
    POST: Add tracks to selected playlist
    """
    try:
        if flask.request.method == "POST":
            # Get necessary data
            spotify_session = get_session_data("oauth_sessions", "spotify")

            profile = get_session_data("ongoing_translation", "profile")
            playlists = get_session_data("ongoing_translation", "playlists")
            mappings = get_session_data("ongoing_translation", "mappings")

            track_uris = [
                mapping["spotify"]["uri"] for mapping in mappings
                if mapping["spotify"]["uri"] is not None
            ]

            # Get selected playlist id
            playlist_id = flask.request.form["playlist_id"]

            # Check if playlist id is valid
            if playlist_id not in [playlist["id"] for playlist in playlists]:
                return "Invalid playlist id", status.HTTP_400_BAD_REQUEST

            # Add tracks to playlist
            spotify_session.add_tracks_to_playlist(profile["id"], playlist_id, track_uris)

            # Remove ongoing data
            remove_session_data("ongoing_translation")

            # Success
            return "Added {} tracks to {}.".format(len(track_uris), playlist_id)

        else:
            spotify_session = get_session_data("oauth_sessions", "spotify")

            # Get user profile and playlists
            profile = spotify_session.get_user_profile()
            playlists = spotify_session.get_user_playlists()

            # Clean data
            profile = {
                "id": profile["id"],
                "display_name": profile["display_name"],
                "external_url": profile["external_urls"]["spotify"]
            }
            playlists = [{
                "id": playlist["id"],
                "name": playlist["name"],
                "external_url": playlist["external_urls"]["spotify"]
            } for playlist in playlists["items"]]

            # Store info
            set_session_data("ongoing_translation", "profile", data=profile)
            set_session_data("ongoing_translation", "playlists", data=playlists)

            # Render page
            return flask.render_template("select_spotify_playlist.html",
                                         profile=profile, playlists=playlists)

    except OAuth2Session.Exceptions.RequestFailedException:
        return "Request failed", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.PostRequestFailedException:
        return "Failed to add tracks to playlist", status.HTTP_400_BAD_REQUEST


@app.route("/test")
@handle_general_exceptions
def test():
    """Test route"""
    try:
        youtube_session = get_session_data("oauth_sessions", "youtube")
        playlist_items = youtube_session.get_playlist_items("RD2Vv-BfVoq4g")

        return "<pre>{}</pre>".format(json.dumps(playlist_items, indent=4))

    except OAuth2Session.Exceptions.RequestFailedException:
        return "Request failed", status.HTTP_400_BAD_REQUEST


"""
Start server
"""
app.run(debug=False, host="0.0.0.0", threaded=True)
