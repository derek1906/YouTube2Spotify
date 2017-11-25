"""Testing OAuth2 module"""
import pytest
import werkzeug

# pylint: skip-file

@pytest.fixture(scope="session")
def client():
    from apis.oauth2 import OAuth2Session
    import flask

    return OAuth2Session(
        flask, "TestingService",
        "client_id", "client_secret",
        "http://authorize.url", "http://authorize.callback.url",
        "http://request.token.url")

@pytest.fixture(scope="session")
def scope():
    return ("scope-a", "scope-b")

def test_authorize(client, scope):
    """Testing returned flask redirection object"""
    value = client.authorize(scope, extra_params={"extra": "params"})

    # Assert correct type
    assert isinstance(value, werkzeug.wrappers.Response)

    # Assert redirection url
    from urlparse import urlparse, parse_qs
    url = urlparse(value.location)
    queries = {k: q[0] for k, q in parse_qs(url.query).iteritems()}

    assert url.scheme == "http"
    assert url.netloc == "authorize.url"
    assert queries == {
        "client_id": "client_id",
        "response_type": "code",
        "redirect_uri": "http://authorize.callback.url",
        "scope": "scope-a scope-b",
        "extra": "params"
    }

    # Assert redirection status code
    assert value.status_code == 302
