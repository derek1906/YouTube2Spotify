# YouTube2Spotify
A server that allows clients to translate private/public YouTube playlists into
Spotify equivalents.

## Before You Do Anything
Add a file `client_info.json` into the root directory of this project:

	{
		"spotify": {
			"client_id": [Your Spotify app client id],
			"client_secret": [Your Spotify app client secret]
		},
		"youtube": {
			"client_id": [Your YouTube app client id],
			"client_secret": [Your YouTube app client secret]
		}
	}

which will be used by the server to make calls to YouTube and Spotify APIs.

## How to Use
Before you start, make sure you have

1. Created an application on both [Spotify](https://developer.spotify.com/my-applications/) and [Google](https://console.developers.google.com/apis/)
2. Acquired client ids and secrets for your application
3. Enabled access to the [YouTube Data API](https://console.developers.google.com/apis/api/youtube/overview)

To start:

1. Start up the server on `localhost:5000` by doing:

        python server.py

2. Open up `localhost:5000` on your favorite browser
3. Create a session
4. Authenticate with the two services

## What's Inside

- A Flask-based server
- Concurrent cookie-based session support
- A lightweight custom OAuth2 package (used for authenticating with Spotify and Google)
- Implementation of translation between YouTube video names and Spotify track names

## Dependencies

- Python 2/3
- [Flask](https://pypi.python.org/pypi/Flask)
- [Requests](https://pypi.python.org/pypi/requests)