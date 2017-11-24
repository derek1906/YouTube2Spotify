"""OAuth2 Session module"""
from __future__ import print_function
import time

from urllib import urlencode
import requests

import apis.oauth2_exceptions as oauth2_exceptions

#pylint: disable=C0103

class OAuth2Session(object):
    """OAuth2 Session"""

    Exceptions = oauth2_exceptions

    def __init__(self, flask, service_name,
                 client_id, client_secret,
                 authorize_url, auth_callback_url, request_token_url):
        self.flask = flask
        self.service_name = service_name
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.auth_callback_url = auth_callback_url
        self.request_token_url = request_token_url

        self.codes = {}

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "<OAuth2Session {} (authenticated: {}, has_token: {})>".format(
            self.service_name,
            "authorization_code" in self.codes,
            "token" in self.codes)

    def authorize(self, scopes, extra_params=None):
        """Initiate authorization"""
        if extra_params is None:
            extra_params = ()

        parameters = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.auth_callback_url,
            "scope": " ".join(scopes)
        }
        parameters.update(extra_params)

        return self.flask.redirect(
            "{}?{}".format(self.authorize_url, urlencode(parameters)), code=302)

    def hnadle_auth_callback(self):
        """Handle authorization callback from service"""
        try:
            authorization_code = self.flask.request.args.get("code")
            self.codes["authorization_code"] = authorization_code
        except KeyError:
            raise OAuth2Session.Exceptions.AuthorizationFailedException()

    def request_new_token(self):
        """Request a new token from service"""
        if "authorization_code" not in self.codes:
            raise OAuth2Session.Exceptions.NotAuthorizedException()

        print("Requesting new token")

        authorization_code = self.codes["authorization_code"]

        payload = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.auth_callback_url,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        res = requests.post(self.request_token_url, data=payload)

        if res.status_code != 200:
            raise OAuth2Session.Exceptions.AccessTokenRequestFailedException()

        try:
            token = res.json()
            self.codes["token"] = {
                "type": token["token_type"],
                "access": token["access_token"],
                "expires_in": token["expires_in"],
                "time_created": time.time()
            }
            if "refresh_token" in token:
                self.codes["token"]["refresh_token"] = token["refresh_token"]
        except ValueError:
            # Invalid response
            raise OAuth2Session.Exceptions.AccessTokenRequestFailedException()

    def get_token(self):
        """
        Get usable token.
        Will attempt to request a new token if current token is absent or expired.
        """
        try:
            token = self.codes["token"]
            if time.time() - token["time_created"] > token["expires_in"]:
                del self.codes["token"]
                raise KeyError()
        except KeyError:
            self.request_new_token()
            token = self.codes["token"]

        return token

    def get_auth_header(self):
        """"Returns header object with authorization code"""
        token = self.get_token()
        return {
            "Authorization": "{} {}".format(token["type"], token["access"])
        }

    def make_get_request(self, method, params=None):
        """Make raw get request"""
        params = params or {}

        auth_header = self.get_auth_header()
        res = requests.get(method, headers=auth_header, params=params)

        return res

    def get(self, method, params=None):
        """Get request"""
        res = self.make_get_request(method, params)

        if res.status_code != 200:
            raise OAuth2Session.Exceptions.RequestFailedException()

        try:
            data = res.json()
            return data
        except ValueError:
            raise OAuth2Session.Exceptions.RequestFailedException()

    def post(self, method, body=None):
        """Post request"""
        body = body or {}

        auth_header = self.get_auth_header()
        auth_header.update({
            "Content-Type": "application/json"
        })

        res = requests.post(method, headers=auth_header, json=body)
        if res.status_code not in [200, 201]:
            raise OAuth2Session.Exceptions.PostRequestFailedException()

        try:
            data = res.json()
            return data
        except ValueError:
            # POST suceeded but returned data is not valid JSON
            return data
