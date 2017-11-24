"""Translate YouTube playlist into Spotify playlist"""

from __future__ import print_function
from urllib import urlencode
from uuid import uuid4
import hashlib
import json
import cgi
import os
import sys
import traceback
import time
import re

import requests
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
    except Exception:
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
Callback URIs
"""
DOMAIN = "http://localhost:5000"
SPOTIFY_AUTH_REDIRECT_ROUTE_NAME = "/spotify-authorization-callback"
SPOTIFY_AUTH_REDIRECT_URI = DOMAIN + SPOTIFY_AUTH_REDIRECT_ROUTE_NAME
YOUTUBE_AUTH_REDIRECT_ROUTE_NAME = "/youtube-authorization-callback"
YOUTUBE_AUTH_REDIRECT_URI = DOMAIN + YOUTUBE_AUTH_REDIRECT_ROUTE_NAME

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

def spotify_search_track(query, access_token, attempt=0):
    """Search for a track on Spotify"""
    SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search?"

    failed_res = {
        "name": None,
        "uri": None
    }

    if attempt > 2:
        # Assume failed
        return failed_res

    parameters = {
        "q": unicode(query).encode("utf-8"),
        "type": "track",
        "limit": 1,
        "access_token": access_token
    }
    print(u"Querying Spotify #{}: {}".format(attempt, query))
    res = requests.get(SPOTIFY_SEARCH_URL + urlencode(parameters))
    if res.status_code != 200:
        if res.status_code == 429:
            # Wait a while
            wait_duration = int(res.headers["Retry-After"])
            if wait_duration > 10:
                # Assume failed
                return failed_res
            else:
                time.sleep(wait_duration)
                return spotify_search_track(query, access_token, attempt + 1)
        else:
            msg = u"Error getting Spotify search results\n{}".format(res.text)
            print(msg)
            return failed_res

    try:
        res_dict = json.loads(res.text)
        items = res_dict["tracks"]["items"]
    except Exception as e:
        msg = u"Error parsing response:\n" + res.text
        traceback.print_exc()
        return failed_res

    # Check if there is at least one result
    if len(items) < 1:
        return failed_res

    item = items[0]

    return {
        "name": item["name"],
        "uri": item["uri"]
    }

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
        "auths": {},
        "translation_result": [],
        "oauth_sessions": {}
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


@app.route(SPOTIFY_AUTH_REDIRECT_ROUTE_NAME)
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

@app.route(YOUTUBE_AUTH_REDIRECT_ROUTE_NAME)
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

@app.route(("/read_youtube_playlist"))
def read_youtube_playlist():
    """Route for translating videos in YouTube playlist into tracks in Spotify"""

    YOUTUBE_GET_PLAYLIST_URL = "https://www.googleapis.com/youtube/v3/playlistItems?"

    session_id = get_session_id()
    if session_id is None:
        return flask.redirect(flask.url_for("home"))
    auths = session_data[session_id]["auths"]

    # Get YouTube playlist id
    try:
        youtube_playlist_id = flask.request.args.get("youtube_playlist_id")
    except Exception:
        msg = "Invalid request"
        return msg, status.HTTP_400_BAD_REQUEST

    # Get service session data
    if "youtube" not in auths:
        msg = "Service not authorized yet."
        return msg, status.HTTP_400_BAD_REQUEST
    youtube_service_data = auths["youtube"]

    # Get service session access token
    if "access_token" not in youtube_service_data:
        msg = "Service not authorized yet."
        return msg, status.HTTP_400_BAD_REQUEST
    youtube_access_token = youtube_service_data["access_token"]

    # Get service session data
    if "spotify" not in auths:
        msg = "Service not authorized yet."
        return msg, status.HTTP_400_BAD_REQUEST
    spotify_service_data = auths["spotify"]

    # Get service session access token
    if "access_token" not in spotify_service_data:
        msg = "Service not authorized yet."
        return msg, status.HTTP_400_BAD_REQUEST
    spotify_access_token = spotify_service_data["access_token"]

    # Get playlist details
    parameters = {
        "part": "snippet",
        "playlistId": youtube_playlist_id,
        "maxResults": 50,
        "access_token": youtube_access_token
    }

    # Get playlist details
    res = requests.get(YOUTUBE_GET_PLAYLIST_URL + urlencode(parameters))
    if res.status_code != 200:
        msg = u"Error getting playlist details\n{}".format(res.text)
        return msg, status.HTTP_400_BAD_REQUEST

    try:
        res_dict = json.loads(res.text)
    except Exception:
        msg = u"Error parsing response:\n" + cgi.escape(res.text)
        return msg, status.HTTP_400_BAD_REQUEST

    youtube_video_names = [item["snippet"]["title"] for item in res_dict["items"]]

    spotify_mappings = [
        spotify_search_track(process_youtube_name(youtube_name), spotify_access_token)
        for youtube_name in youtube_video_names
    ]


    # Organize results
    items = [{"youtube": youtube_names, "spotify": spotify_mapping} for
             (youtube_names, spotify_mapping) in zip(youtube_video_names, spotify_mappings)]

    session_data[session_id]["translation_result"] = items

    return flask.render_template("youtube_playlist_display.html",
                           youtube_playlist_id=youtube_playlist_id, items=items)

@app.route("/apply_translation", methods=["POST"])
def apply_translation():
    SPOTIFY_GET_PLAYLISTS_URL = "https://api.spotify.com/v1/me/playlists"
    SPOTIFY_ADD_TRACKS_TO_PLAYLIST_URL = "https://api.spotify.com/v1/users/{user_id}/playlists/{playlist_id}/tracks"

    raise NotImplementedError()

    session_id = get_session_id()
    if session_id is None:
        msg = "Session missing."
        return msg, status.HTTP_400_BAD_REQUEST

    auths = session_data[session_id]["auths"]

    # Get service session data
    if "spotify" not in auths:
        msg = "Service not authorized yet."
        return msg, status.HTTP_400_BAD_REQUEST
    spotify_service_data = auths["spotify"]

    # Get service session access token
    if "access_token" not in spotify_service_data:
        msg = "Service not authorized yet."
        return msg, status.HTTP_400_BAD_REQUEST
    spotify_access_token = spotify_service_data["access_token"]

    translation_result = session_data[session_id]["translation_result"]
    # Get translation result
    if not translation_result:
        msg = "Empty translation result."
        return msg, status.HTTP_400_BAD_REQUEST

    # Get Sptofiy playlist id to add to
    playlist_id = flask.request.form["playlist_id"]

    # Add tracks to Spotify playlist
    

app.run(debug=True, host="0.0.0.0", threaded=True)
