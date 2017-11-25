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

1. Created an application on both [Spotify](https://developer.spotify.com/my-applications/) and [Google](https://console.developers.google.com/apis/),
2. Acquired client ids and secrets for your application,
3. Enabled access to the [YouTube Data API](https://console.developers.google.com/apis/api/youtube/overview).

To start:

1. Start up the server on `localhost:5000` by doing:

        python server.py

2. Open up `localhost:5000` on your favorite browser.
3. Create a session.
4. Authenticate with the two services.
5. Enter the YouTube playlist id in the homepage and click "Submit".
6. The server will now translate all the videos into equivalent Spotify names.
7. Review and click next.
8. Select the target Spotify playlist that you want to add them into (click "Select").
9. ???
10. Profit! (If everything goes well, the tracks should be added to your selected playlist.)

## What's Inside

- A Flask-based server
- Concurrent cookie-based session support
- A lightweight custom OAuth2 package (used for authenticating with Spotify and Google)
- Session data container
- Implementation of translation between YouTube video names and Spotify track names

## Dependencies

- Python 2/3
- [Flask](https://pypi.python.org/pypi/Flask)
- [Requests](https://pypi.python.org/pypi/requests)

## License

	MIT License

	Copyright (c) 2017 Derek Leung

	Permission is hereby granted, free of charge, to any person obtaining a copy
	of this software and associated documentation files (the "Software"), to deal
	in the Software without restriction, including without limitation the rights
	to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
	copies of the Software, and to permit persons to whom the Software is
	furnished to do so, subject to the following conditions:

	The above copyright notice and this permission notice shall be included in all
	copies or substantial portions of the Software.

	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
	OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
	SOFTWARE.