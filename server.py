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
app.secret_key = os.urandom(24) # create secret key for cookies


"""
Session data storage
"""
session_data = {}


"""
Handy functions
"""
class SessionNotCreatedException(Exception):
    """Session has not been created"""

class SessionNamespaceNotFoundException(Exception):
    """Session namespace has not been created"""

def get_session_id():
    """Get session id"""
    try:
        return flask.session["session_id"]
    except KeyError:
        raise SessionNotCreatedException()

def get_session_data(*namespaces):
    """Get session data"""
    try:
        data = session_data[get_session_id()]
        for namespace in namespaces:
            data = data[namespace]

        return data
    except KeyError:
        raise SessionNamespaceNotFoundException()

def set_session_data(*namespaces, **props):
    """Set session data"""
    if "data" not in props:
        raise TypeError("Missing \"data\"")

    obj = session_data[get_session_id()]

    for namespace in namespaces[:-1]:
        if namespace not in obj:
            obj[namespace] = {}
        obj = obj[namespace]

    obj[namespaces[-1]] = props["data"]

def remove_session_data(*namespaces):
    """Remove session data"""
    try:
        obj = session_data[get_session_id()]
        for namespace in namespaces[:-1]:
            obj = obj[namespace]

        del obj[namespaces[-1]]

    except KeyError:
        raise SessionNamespaceNotFoundException()

def process_youtube_name(name):
    """Clean up a YouTube video name. Removes (...), [...] and ft. ..."""
    return re.sub(r"( \[.+?\]| \(.+?\)| ft.+?$)", "", name)


"""
Routes
"""
@app.route("/create_session")
def create_session():
    """Start a session"""
    session_id = hashlib.sha1(str(uuid4())).hexdigest()
    flask.session["session_id"] = session_id

    session_data[session_id] = {
        "oauth_sessions": {},
        "ongoing_translation": {}
    }

    return flask.redirect(flask.url_for("home"))

@app.route("/remove_session")
def remove_session():
    """End a session"""
    if "session_id" in flask.session:
        session_id = flask.session["session_id"]

        flask.session.pop("session_id", None)

        if session_id in session_data:
            session_data.pop(session_id)

    return flask.redirect(flask.url_for("home"))

@app.route("/")
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
def auth_spotify():
    """Authenticate Spotify"""
    try:
        oauth_sessions = get_session_data("oauth_sessions")

        # Create new Spotify OAuth session
        oauth_sessions["spotify"] = SpotifyClient(
            flask,
            CLIENT_INFO["spotify"]["client_id"], CLIENT_INFO["spotify"]["client_secret"],
            "http://localhost:5000/spotify-authorization-callback")

        # Authorize
        return oauth_sessions["spotify"].authorize(SCOPES["spotify"])

    except SessionNotCreatedException:
        return flask.redirect(flask.url_for("home"))


@app.route("/spotify-authorization-callback")
def auth_spotify_callback():
    """Callback route for Spotify auth"""
    try:
        # Get Spotify OAuth session
        spotify_session = get_session_data("oauth_sessions", "spotify")

        # Handle response
        spotify_session.hnadle_auth_callback()

        # Return to homepage
        return flask.redirect(flask.url_for("home"))

    except SessionNotCreatedException:
        return flask.redirect(flask.url_for("home"))

    except SessionNamespaceNotFoundException:
        return "Unexpected callback from service", status.HTTP_400_BAD_REQUEST

    except SpotifyClient.Exceptions.AuthorizationFailedException:
        return "Authorization failed", status.HTTP_400_BAD_REQUEST


@app.route("/auth_youtube")
def auth_youtube():
    """Authenticate YouTube"""

    try:
        oauth_sessions = get_session_data("oauth_sessions")

        # Create new Spotify OAuth session
        oauth_sessions["youtube"] = YouTubeClient(
            flask,
            CLIENT_INFO["youtube"]["client_id"], CLIENT_INFO["youtube"]["client_secret"],
            "http://localhost:5000/youtube-authorization-callback")

        # Authorize
        return oauth_sessions["youtube"].authorize(SCOPES["youtube"], {
            "response_type": "code"
        })

    except SessionNotCreatedException:
        return flask.redirect(flask.url_for("home"))

@app.route("/youtube-authorization-callback")
def auth_youtube_callback():
    """Callback route for YouTube auth"""

    try:
        # Get YouTube OAuth session
        youtube_session = get_session_data("oauth_sessions", "youtube")

        # Handle response
        youtube_session.hnadle_auth_callback()

        # Return to homepage
        return flask.redirect(flask.url_for("home"))

    except SessionNotCreatedException:
        return flask.redirect(flask.url_for("home"))

    except SessionNamespaceNotFoundException:
        return "Unexpected callback from service", status.HTTP_400_BAD_REQUEST

    except SpotifyClient.Exceptions.AuthorizationFailedException:
        return "Authorization failed", status.HTTP_400_BAD_REQUEST

@app.route("/request_token")
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

    except SessionNotCreatedException:
        return flask.redirect(flask.url_for("home"))

    except SessionNamespaceNotFoundException:
        return "OAuth session not created", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.NotAuthorizedException:
        return "Not authorized", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.AccessTokenRequestFailedException:
        return "Request access token failed", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.RequestFailedException:
        return "Request failed", status.HTTP_400_BAD_REQUEST

@app.route("/test")
def test():
    try:
        youtube_session = get_session_data("oauth_sessions", "youtube")
        playlist_items = youtube_session.get_playlist_items("RD2Vv-BfVoq4g")

        return "<pre>{}</pre>".format(json.dumps(playlist_items, indent=4))

    except SessionNotCreatedException:
        return flask.redirect(flask.url_for("home"))

    except SessionNamespaceNotFoundException:
        return "OAuth session not created", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.NotAuthorizedException:
        return "Not authorized", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.AccessTokenRequestFailedException:
        return "Request access token failed", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.RequestFailedException:
        return "Request failed", status.HTTP_400_BAD_REQUEST

@app.route(("/read_youtube_playlist"))
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

    except SessionNotCreatedException:
        return flask.redirect(flask.url_for("home"))

    except SessionNamespaceNotFoundException:
        return "OAuth session not created", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.NotAuthorizedException:
        return "Not authorized", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.AccessTokenRequestFailedException:
        return "Request access token failed", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.RequestFailedException:
        return "Request failed", status.HTTP_400_BAD_REQUEST

@app.route("/select_export_playlist", methods=["GET", "POST"])
def select_export_playlist():
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

    except SessionNotCreatedException:
        return flask.redirect(flask.url_for("home"))

    except SessionNamespaceNotFoundException:
        return "OAuth session not created", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.NotAuthorizedException:
        return "Not authorized", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.AccessTokenRequestFailedException:
        return "Request access token failed", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.RequestFailedException:
        return "Request failed", status.HTTP_400_BAD_REQUEST

    except OAuth2Session.Exceptions.PostRequestFailedException:
        return "Failed to add tracks to playlist", status.HTTP_400_BAD_REQUEST

app.run(debug=True, host="0.0.0.0", threaded=True)
