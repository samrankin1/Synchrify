import json
import uuid

from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseRedirect, HttpResponseNotAllowed, HttpResponseNotFound

import spotipy

from . import db, mail, patterns, apikeys


SPOTIFY_OAUTH = spotipy.SpotifyOAuth(
	settings.SPOTIFY_CLIENT_ID,
	settings.SPOTIFY_CLIENT_SECRET,
	settings.SPOTIFY_REDIRECT_URI,
	scope=settings.SPOTIFY_SCOPE,
	username=settings.SPOTIFY_USERNAME,
)

SPOTIFY_MARKET = 'US'
SPOTIFY_CONTENT_TYPES = ['track', 'artist', 'album', 'playlist']


def _enforce_method(request, method):
	if not request.method == method:
		return HttpResponseNotAllowed([method])


def _get_user(request):
	if 'user' not in request.session:
		return None
	else:
		return request.session['user']


def _ok():
	return JsonResponse({})


def _err(msg):
	return JsonResponse({'error': msg})


def register(request):
	err = _enforce_method(request, 'POST')
	if err:
		return err

	params = json.loads(request.body)
	email, password = params.get('email'), params.get('password')

	if not email or not password:
		return HttpResponseBadRequest("Fields 'email' and 'password' are required")

	if not patterns.match_email(email):
		return _err('Invalid email address!')

	if db.check_email_exists(email):
		return _err('User already exists!')

	db.insert_user(email, password)

	token = str(uuid.uuid4())
	db.insert_activation(email, token)
	mail.send_activation_mail(request, email, token)

	return _ok()


def activate(request, token):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	row = db.get_activation(token)
	if not row:
		return HttpResponseBadRequest('Invalid activation token!')

	user, valid = row

	if not valid:
		return _err('Your account is already activated')

	db.activate_user(user)
	db.invalidate_activation(token)

	return JsonResponse({
		'activated': db.get_email(user)
	})


def login(request):
	err = _enforce_method(request, 'POST')
	if err:
		return err

	params = json.loads(request.body)
	email, password = params.get('email'), params.get('password')

	if not email or not password:
		return HttpResponseBadRequest("Fields 'email' and 'password' are required")

	if not patterns.match_email(email):
		return _err('Invalid email address')

	row = db.get_login(email)

	if not row:
		return _err('User does not exist')

	user, pass_hash, activated = row

	if activated != 1:
		return _err('Account is not activated! Check your email')

	if password != pass_hash:
		return _err('Wrong password')

	request.session['user'] = user
	return _ok()


def user(request):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	spotify_user = db.get_spotify_username(user)
	return JsonResponse({'user_id': user, 'spotify_user': spotify_user})


def logout(request):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	if 'user' in request.session:
		del request.session['user']

	return _ok()


def friends_list(request, friend_id=None):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	friends = db.get_friends_list(user)

	if friend_id:
		# TODO: privacy settings?
		if friend_id not in friends:
			return _err('You must be friends with this user to list their friends')
		friends = db.get_friends_list(friend_id)

	return JsonResponse({'friends': friends})


def friends_list_friends(request):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	return JsonResponse({'friends_of_friends': db.get_friends_of_friends(user)})


def friends_pending(request):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	return JsonResponse({'pending': db.get_friends_pending(user)})


def friends_add(request, friend_id):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	if user == friend_id:
		return _err('You cannot add yourself as a friend')

	if not db.get_email(friend_id):
		return _err('Friend user not found')

	db.insert_friend(user, friend_id)
	return _ok()


def friends_remove(request, friend_id):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	db.delete_friend(user, friend_id)
	return _ok()


def content_get_by_id(request, content_id):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	row = db.get_content_by_id(content_id)
	if not row:
		return _err('Content ID not found')

	content_type, uri, name = row
	return JsonResponse({'type': content_type, 'uri': uri, 'name': name})


def content_get_by_uri(request, content_type, uri):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	auth = db.get_spotify_auth(user)
	if not auth:
		return _err('You must be authenticated with Spotify to access this URL')

	if content_type not in SPOTIFY_CONTENT_TYPES:
		return _err('Content type must be in ' + str(SPOTIFY_CONTENT_TYPES))

	row = db.get_content_by_uri(content_type, uri)
	if row:
		content_id, name = row
		return JsonResponse({'content_id': content_id, 'name': name, 'created': False})

	content_info = None
	try:
		client = auth.client(user)

		if content_type == 'track':
			content_info = client.track(uri)
		elif content_type == 'artist':
			content_info = client.artist(uri)
		elif content_type == 'album':
			content_info = client.album(uri)
		elif content_type == 'playlist':
			content_info = client.playlist(uri, market=SPOTIFY_MARKET)

	except spotipy.SpotifyException as e:
		return _err(str(e))

	if not content_info:
		return _err('Unknown error fetching content_info')

	if 'name' not in content_info:
		return _err('Failed to fetch Spotify content name')

	db.insert_content(content_type, uri, content_info['name'])

	row = db.get_content_by_uri(content_type, uri)
	if not row:
		return _err('Could not retrieve newly created content ID')

	content_id, name = row
	return JsonResponse({'content_id': content_id, 'name': name, 'created': True})


def content_get_rating(request, content_id, friend_id=None):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	if friend_id:
		# TODO: privacy settings?
		if not db.check_friends(user, friend_id):
			return _err('You must be friends with this user to view their ratings')

	rating = db.get_rating(friend_id if friend_id else user, content_id)
	if not rating:
		return _err('Rating not found')

	return JsonResponse({'rating': rating})


def content_set_rating(request, content_id, rating):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	if not db.check_content_exists(content_id):
		return _err('Content ID not found')

	if rating < 0 or rating > 10:
		return _err('Rating value must be in range 0 <= r <= 10')

	db.insert_rating(user, content_id, rating)
	return _ok()


def content_reset_rating(request, content_id):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	if not db.check_content_exists(content_id):
		return _err('Content ID not found')

	db.delete_rating(user, content_id)
	return _ok()


def ratings_list(request, friend_id=None):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	if friend_id:
		# TODO: privacy settings?
		if not db.check_friends(user, friend_id):
			return _err('You must be friends with this user to list their ratings')

	ratings = db.get_ratings(friend_id if friend_id else user)
	return JsonResponse({'ratings': ratings})


def ratings_list_friends(request):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	ratings = db.get_friends_ratings(user)
	return JsonResponse({'ratings': ratings})


def spotify_auth(request):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	auth_state = uuid.uuid4().hex
	request.session['auth_state'] = auth_state

	return HttpResponseRedirect(
		SPOTIFY_OAUTH.get_authorize_url(auth_state)
	)


def spotify_auth_callback(request):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	params = request.GET
	error, code, state = params.get('error'), params.get('code'), params.get('state')

	if not state:
		return HttpResponseBadRequest("Field 'state' is required")

	if not error and not code:
		return HttpResponseBadRequest("Field 'error' or 'code' is required")

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	if 'auth_state' not in request.session:
		return _err('Session auth_state not found')

	auth_state = request.session['auth_state']

	if auth_state != state:
		return _err('Session auth_state mismatch')

	del request.session['auth_state']

	if error:
		return _err('auth_callback error: ' + error)

	try:
		auth = apikeys.complete_auth(code, user)
		db.insert_spotify_auth(user, auth)
		return _ok()

	except spotipy.SpotifyException as e:
		return _err(str(e))


def spotify_wrapper(request, endpoint):
	err = _enforce_method(request, 'GET')
	if err:
		return err

	user = _get_user(request)
	if not user:
		return _err('You must be logged in to access this URL')

	auth = db.get_spotify_auth(user)
	if not auth:
		return _err('You must be authenticated with Spotify to access this URL')

	params = request.GET

	limit = params.get('limit')
	before = params.get('before')
	after = params.get('after')
	offset = params.get('offset')
	timespan = params.get('timespan')

	tracks = params.get('tracks')
	tracks = tracks.split(',') if tracks else None

	albums = params.get('albums')
	albums = albums.split(',') if albums else None

	artists = params.get('artists')
	artists = artists.split(',') if artists else None

	users = params.get('users')
	users = users.split(',') if users else None

	name = params.get('name')
	description = params.get('description')
	playlist = params.get('playlist')
	position = params.get('position')
	image_b64 = params.get('image')

	query = params.get('q')
	query_type = params.get('type')
	query_user = params.get('user')

	try:
		client = auth.client(user)
		username = auth.username

		if endpoint == 'profile':
			return JsonResponse(client.current_user())
		elif endpoint == 'playing_track':
			return JsonResponse(client.currently_playing(SPOTIFY_MARKET))
		elif endpoint == 'recent_tracks':
			return JsonResponse(client.current_user_recently_played(limit, before, after))
		elif endpoint == 'top_tracks':
			return JsonResponse(client.current_user_top_tracks(limit, offset, timespan))
		elif endpoint == 'followed_artists':
			return JsonResponse(client.current_user_followed_artists(limit, after))
		elif endpoint == 'playlists':
			return JsonResponse(client.current_user_playlists(limit, offset))
		elif endpoint == 'saved_albums':
			return JsonResponse(client.current_user_saved_albums(limit, offset))
		elif endpoint == 'saved_tracks':
			return JsonResponse(client.current_user_saved_tracks(limit, offset))

		elif endpoint == 'search':
			return JsonResponse(client.search(query, limit, offset, query_type, SPOTIFY_MARKET))
		elif endpoint == 'user_playlists':
			return JsonResponse(client.user_playlists(query_user, limit, offset))
		elif endpoint == 'fetch_tracks':
			return JsonResponse(client.tracks(tracks, SPOTIFY_MARKET))
		elif endpoint == 'fetch_albums':
			return JsonResponse(client.albums(albums))
		elif endpoint == 'fetch_artists':
			return JsonResponse(client.artists(artists))

		elif endpoint == 'add_playlist_custom_image':
			return JsonResponse(client.playlist_upload_cover_image(playlist, image_b64))
		elif not username:
			return _err('Failed to fetch Spotify User ID')
		elif endpoint == 'create_playlist':
			return JsonResponse(client.user_playlist_create(username, name, description=description))
		elif endpoint == 'follow_playlist':
			return JsonResponse(client.user_playlist_follow_playlist(username, playlist))
		elif endpoint == 'is_following_playlist':
			return JsonResponse(client.user_playlist_is_following(username, playlist, users))
		elif endpoint == 'add_playlist_tracks':
			return JsonResponse(client.user_playlist_add_tracks(username, playlist, tracks, position))
		elif endpoint == 'edit_playlist_details':
			return JsonResponse(client.user_playlist_change_details(username, playlist, name, description=description))
		else:
			return HttpResponseNotFound('Unknown endpoint')

	except spotipy.SpotifyException as e:
		return _err(str(e))
