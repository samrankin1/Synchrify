import base64
import time

from django.conf import settings

import requests
import spotipy

from . import db


OAUTH_TOKEN_URL = 'https://accounts.spotify.com/api/token'


class SpotifyUserAuth:
	def __init__(self, access_token, refresh_token, expires_at, user, username=None, requests_timeout=None):
		self.access_token = access_token
		self.refresh_token = refresh_token
		self.expires_at = expires_at
		self.username = username or self._fetch_username(user, requests_timeout)

	def _fetch_username(self, user, requests_timeout=None):
		return self.client(user, requests_timeout).current_user().get('id')

	@classmethod
	def from_response(cls, token_response, user, username=None, requests_timeout=None):
		access_token = token_response['access_token']
		refresh_token = token_response['refresh_token']
		expires_at = int(time.time()) + token_response['expires_in']
		return cls(
			access_token, refresh_token, expires_at, user, username, requests_timeout
		)

	def _is_token_expired(self):
		now = int(time.time())
		return self.expires_at - now < 60

	def _update_auth(self, new_auth):
		self.access_token = new_auth.access_token
		self.refresh_token = new_auth.refresh_token
		self.expires_at = new_auth.expires_at

	def _get_access_token(self, user, requests_timeout=None):
		if self._is_token_expired():
			new_auth = _refresh_auth(self, user, requests_timeout)
			self._update_auth(new_auth)
			db.insert_spotify_auth(user, self)
		return self.access_token

	def client(self, user, requests_timeout=None):
		return spotipy.Spotify(
			auth=self._get_access_token(user, requests_timeout)
		)


def _auth_headers():
	auth = base64.b64encode(
		(settings.SPOTIFY_CLIENT_ID + ':' + settings.SPOTIFY_CLIENT_SECRET).encode('ascii')
	)
	return {'Authorization': 'Basic ' + auth.decode('ascii')}


def _api_error(response):
	try:
		msg = response.json()['error']['message']
	except (ValueError, KeyError, TypeError):
		msg = 'unknown error'

	return spotipy.SpotifyException(
		response.status_code,
		-1,
		response.url + ':\n ' + msg,
		headers=response.headers
	)


def complete_auth(code, user, requests_timeout=None):
	payload = {
		'grant_type': 'authorization_code',
		'code': code,
		'redirect_uri': settings.SPOTIFY_REDIRECT_URI,
	}

	response = requests.post(
		OAUTH_TOKEN_URL,
		data=payload,
		headers=_auth_headers(),
		timeout=requests_timeout,
	)

	if response.status_code != 200:
		raise _api_error(response)

	return SpotifyUserAuth.from_response(
		response.json(),
		user,
		requests_timeout=requests_timeout
	)


def _refresh_auth(auth, user, requests_timeout=None):
	payload = {
		'grant_type': 'refresh_token',
		'refresh_token': auth.refresh_token,
	}

	response = requests.post(
		OAUTH_TOKEN_URL,
		data=payload,
		headers=_auth_headers(),
		timeout=requests_timeout,
	)

	if response.status_code != 200:
		raise _api_error(response)

	token_response = response.json()

	if 'refresh_token' not in token_response:
		token_response['refresh_token'] = auth.refresh_token

	return SpotifyUserAuth.from_response(
		token_response,
		user,
		auth.username,
		requests_timeout
	)
