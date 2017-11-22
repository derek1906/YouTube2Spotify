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

from spotify_api import SpotifyClient


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

def get_session_data(namespace):
    """Get session data"""
    try:
        return session_data[get_session_id()][namespace]
    except KeyError:
        raise SessionNamespaceNotFoundException()

def spotify_request_new_token(authorization_code):
    """Request new token from Spotify with an auth code"""
    SPOTIFY_REQUEST_TOKEN_URL = "https://accounts.spotify.com/api/token"

    payload = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": SPOTIFY_AUTH_REDIRECT_URI,
        "client_id": CLIENT_INFO["spotify"]["client_id"],
        "client_secret": CLIENT_INFO["spotify"]["client_secret"]
    }
    res = requests.post(SPOTIFY_REQUEST_TOKEN_URL, data=payload)

    if res.status_code != 200:
        msg = u"Error getting refresh and access tokens"
        print(msg)
        return None

    try:
        res_dict = json.loads(res.text)
    except Exception as e:
        msg = u"Error parsing response:\n" + cgi.escape(res.text)
        print(msg)
        return None

    return res_dict

def spotify_refresh_token(refresh_token):
    """Refresh Spotify token with a refresh token"""
    SPOTIFY_REFRESH_TOKEN_URL = "https://accounts.spotify.com/api/token"

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_INFO["spotify"]["client_id"],
        "client_secret": CLIENT_INFO["spotify"]["client_secret"]
    }
    res = requests.post(SPOTIFY_REFRESH_TOKEN_URL, data=payload)

    if res.status_code != 200:
        msg = u"Error getting refresh and access tokens\n{}".format(res.text)
        print(msg)
        return None

    try:
        res_dict = json.loads(res.text)
    except Exception:
        msg = u"Error parsing response:\n" + cgi.escape(res.text)
        print(msg)
        return None

    return res_dict

def youtube_request_new_token(authorization_code):
    """Request new token from YouTube with an auth code"""
    YOUTUBE_REQUEST_TOKEN_URL = "https://accounts.google.com/o/oauth2/token"

    payload = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": YOUTUBE_AUTH_REDIRECT_URI,
        "client_id": CLIENT_INFO["youtube"]["client_id"],
        "client_secret": CLIENT_INFO["youtube"]["client_secret"]
    }
    res = requests.post(YOUTUBE_REQUEST_TOKEN_URL, data=payload)

    if res.status_code != 200:
        msg = u"Error getting refresh and access tokens\n{}".format(res.text)
        print(msg)
        return None

    try:
        res_dict = json.loads(res.text)
    except Exception:
        msg = u"Error parsing response:\n" + cgi.escape(res.text)
        print(msg)
        return None

    return res_dict

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
        session_id = get_session_id()
        auths = {k: json.dumps(v, indent=4) for (k, v) in get_session_data("auths").iteritems()}

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
            "http://localhost:5000/auth_spotify_callback")

        # Authorize
        return oauth_sessions["spotify"].authorize(SCOPES["spotify"])

    except SessionNotCreatedException:
        return flask.redirect(flask.url_for("home"))


@app.route(SPOTIFY_AUTH_REDIRECT_ROUTE_NAME)
def auth_spotify_callback():
    """Callback route for Spotify auth"""

    session_id = get_session_id()
    if session_id is None:
        return flask.redirect(flask.url_for("home"))

    try:
        callback_session_id = flask.request.args.get("state")
        authorization_code = flask.request.args.get("code")
    except Exception:
        msg = "Invalid request"
        return msg, status.HTTP_400_BAD_REQUEST

    if callback_session_id != session_id:
        msg = "Unexpected session id"
        return msg, status.HTTP_400_BAD_REQUEST

    # Store authorization code for this user
    session_data[session_id]["auths"]["spotify"].update({
        "authorization_code": authorization_code
    })

    # Return to homepage
    return flask.redirect(flask.url_for("home"))

@app.route("/auth_youtube")
def auth_youtube():
    """Authenticate YouTube"""

    YOUTUBE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth?"

    session_id = get_session_id()
    if session_id is None:
        return flask.redirect(flask.url_for("home"))

    session_data[session_id]["auths"]["youtube"] = {}

    parameters = {
        "client_id": CLIENT_INFO["youtube"]["client_id"],
        "response_type": "code",
        "redirect_uri": YOUTUBE_AUTH_REDIRECT_URI,
        "scope": " ".join(SCOPES["youtube"]),
        "access_type": "online",
        "state": session_id
    }

    # Redirect to YouTube for user authorization
    return flask.redirect(YOUTUBE_AUTH_URL + urlencode(parameters), code=302)

@app.route(YOUTUBE_AUTH_REDIRECT_ROUTE_NAME)
def auth_youtube_callback():
    """Callback route for YouTube auth"""

    session_id = get_session_id()
    if session_id is None:
        return flask.redirect(flask.url_for("home"))

    try:
        authorization_code = flask.request.args.get("code")
    except Exception:
        msg = "Invalid request"
        return msg, status.HTTP_400_BAD_REQUEST

    # Store authorization code for this user
    session_data[session_id]["auths"]["youtube"].update({
        "authorization_code": authorization_code
    })

    # Return to homepage
    return flask.redirect(flask.url_for("home"))

@app.route("/request_token")
def request_token():
    """General route for requesting token"""

    session_id = get_session_id()
    if session_id is None:
        return flask.redirect(flask.url_for("home"))
    auths = session_data[session_id]["auths"]

    # Service look up table
    services = {
        "spotify": spotify_request_new_token,
        "youtube": youtube_request_new_token
    }

    # Get service name
    try:
        service_name = flask.request.args.get("service")
        if service_name not in services.keys():
            raise Exception()
    except Exception:
        msg = "Invalid request"
        return msg, status.HTTP_400_BAD_REQUEST

    # Get service session data
    if service_name not in auths:
        msg = "Service not authorized yet."
        return msg, status.HTTP_400_BAD_REQUEST
    service_data = auths[service_name]

    # Get service session authorization code
    if "authorization_code" not in service_data:
        msg = "Service not authorized yet."
        return msg, status.HTTP_400_BAD_REQUEST
    authorization_code = service_data["authorization_code"]

    # Get new token
    res = services[service_name](authorization_code)
    if res is None:
        msg = "Failed to get token for service \"{}\".".format(service_name)
        return msg, status.HTTP_400_BAD_REQUEST
    service_data.update(res)

    # Return to homepage
    return flask.redirect(flask.url_for("home"))

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
    

@app.route("/test")
def test():
    try:
        oauth_sessions = get_session_data("oauth_sessions")

        data = oauth_sessions["spotify"].get_user_playlists()
        return "<pre>{}</pre>".format(json.dumps(data, indent=4))

    except SessionNotCreatedException:
        """Session not found"""
        return flask.redirect(flask.url_for("home"))

    except SessionNamespaceNotFoundException:
        """Session namespace not found"""
        # Should not happen
        return flask.redirect(flask.url_for("home"))

    except (KeyError, SpotifyClient.Exceptions.NotAuthorizedException):
        """Spotify not authorized"""
        return "Not authorized", status.HTTP_400_BAD_REQUEST

    except SpotifyClient.Exceptions.AccessTokenRequestFailedException:
        """Failed to request access token"""
        return "Failed to request access token", status.HTTP_400_BAD_REQUEST

    except SpotifyClient.Exceptions.RequestFailedException:
        """Request failed"""
        return "Request failed due to unknown reasons", status.HTTP_500_INTERNAL_SERVER_ERROR

@app.route("/test_auth")
def test_auth():
    session_id = get_session_id()
    if session_id is None:
        return flask.redirect(flask.url_for("home"))
    oauth_sessions = session_data[session_id]["oauth_sessions"]

    oauth_sessions["spotify"] = SpotifyClient(
        flask,
        CLIENT_INFO["spotify"]["client_id"], CLIENT_INFO["spotify"]["client_secret"],
        "http://localhost:5000/test_cb")

    # Authorize
    return oauth_sessions["spotify"].authorize(SCOPES["spotify"])

@app.route("/test_cb")
def test_cb():
    session_id = get_session_id()
    if session_id is None:
        return flask.redirect(flask.url_for("home"))
    oauth_sessions = session_data[session_id]["oauth_sessions"]

    try:
        oauth_sessions["spotify"].hnadle_auth_callback()
        return "Success"
    except SpotifyClient.Exceptions.AuthorizationFailedException:
        return "Authorization failed", status.HTTP_500_INTERNAL_SERVER_ERROR
    except KeyError:
        return "Authorization not started", status.HTTP_400_BAD_REQUEST



app.run(debug=True, host="0.0.0.0", threaded=True)
