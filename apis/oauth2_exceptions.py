"""OAuth2Session Exceptions"""

class NotAuthorizedException(Exception):
    """Session not yet authorized"""

class AuthorizationFailedException(Exception):
    """Failed to authorize"""

class AccessTokenRequestFailedException(Exception):
    """Failed to request access token"""

class RequestFailedException(Exception):
    """Failed to complete request"""
