from django.db import connection

from .apikeys import SpotifyUserAuth


def _execute(query, values=None):
	with connection.cursor() as cursor:
		cursor.execute(query, values)


def _fetchone(query, values=None):
	with connection.cursor() as cursor:
		cursor.execute(query, values)
		return cursor.fetchone()


def _fetchall(query, values=None):
	with connection.cursor() as cursor:
		cursor.execute(query, values)
		return cursor.fetchall()


# User queries

_insert_user_sql = """
	INSERT INTO synchrify_users (email, password)
	VALUES (%s, %s)
"""

_activate_user_sql = """
	UPDATE synchrify_users SET activated = 1
	WHERE id = %s
"""

_email_exists_sql = """
	SELECT COUNT(*) FROM synchrify_users
	WHERE email = %s
"""

_user_by_email_sql = """
	SELECT id, password, activated FROM synchrify_users
	WHERE email = %s
"""

_email_by_id_sql = """
	SELECT email FROM synchrify_users
	WHERE id = %s
"""


def insert_user(email, password):
	_execute(
		_insert_user_sql,
		(email, password)
	)


def activate_user(user):
	_execute(
		_activate_user_sql,
		(user,)
	)


def check_email_exists(email):
	row = _fetchone(
		_email_exists_sql,
		(email,)
	)
	return None if not row else row[0] == 1


def get_login(email):
	return _fetchone(
		_user_by_email_sql,
		(email,)
	)


def get_email(user):
	row = _fetchone(
		_email_by_id_sql,
		(user,)
	)
	return None if not row else row[0]


# Activation queries

_insert_activation_sql = """
	INSERT INTO synchrify_activations (token, user)
	VALUES (
		%s,
		(SELECT id FROM synchrify_users WHERE email = %s)
	)
"""

_activation_invalidate_sql = """
	UPDATE synchrify_activations SET valid = 0
	WHERE token = %s
"""

_activation_token_sql = """
	SELECT user, valid FROM synchrify_activations
	WHERE token = %s
"""


def insert_activation(email, token):
	_execute(
		_insert_activation_sql,
		(token, email)
	)


def invalidate_activation(token):
	_execute(
		_activation_invalidate_sql,
		(token,)
	)


def get_activation(token):
	row = _fetchone(
		_activation_token_sql,
		(token,)
	)
	if not row:
		return None
	else:
		user, valid = row
		return user, valid == 1


# Friend queries

_insert_friend_sql = """
	INSERT INTO synchrify_friends (friender, friendee)
	VALUES (%s, %s)
	ON DUPLICATE KEY UPDATE
		friender = friender
"""

_delete_friend_sql = """
	DELETE FROM synchrify_friends
	WHERE friender = %s AND friendee = %s
"""

_friends_pending_sql = """
	SELECT friendee FROM synchrify_friends f
	WHERE friender = %s AND (
		SELECT IF(COUNT(*), FALSE, TRUE) FROM synchrify_friends
		WHERE friender = f.friendee AND friendee = f.friender
	)
"""

_friends_list_sql = """
	SELECT friendee FROM synchrify_friends f
	WHERE friender = %s AND (
		SELECT IF(COUNT(*), TRUE, FALSE) FROM synchrify_friends
		WHERE friender = f.friendee AND friendee = f.friender
	)
"""

_friends_of_friends_sql = """
	SELECT DISTINCT friendee FROM synchrify_friends f2
	WHERE friendee <> %(user)s
	AND friender IN (
		SELECT friendee FROM synchrify_friends f1
		WHERE friender = %(user)s AND (
			SELECT IF(COUNT(*), TRUE, FALSE) FROM synchrify_friends
			WHERE friender = f1.friendee AND friendee = f1.friender
		)
	) AND (
		SELECT IF(COUNT(*), TRUE, FALSE) FROM synchrify_friends
		WHERE friender = f2.friendee AND friendee = f2.friender
	)
"""

_friends_check_sql = """
	SELECT IF(COUNT(*), TRUE, FALSE) FROM synchrify_friends f
	WHERE friender = %s AND friendee = %s AND (
		SELECT IF(COUNT(*), TRUE, FALSE) FROM synchrify_friends
		WHERE friender = f.friendee AND friendee = f.friender
	)
"""


def insert_friend(user, friend):
	_execute(
		_insert_friend_sql,
		(user, friend)
	)


def delete_friend(user, friend):
	_execute(
		_delete_friend_sql,
		(user, friend)
	)


def get_friends_pending(user):
	return [row[0] for row in _fetchall(
		_friends_pending_sql,
		(user,)
	)]


def get_friends_list(user):
	return [row[0] for row in _fetchall(
		_friends_list_sql,
		(user,)
	)]


def get_friends_of_friends(user):
	return [row[0] for row in _fetchall(
		_friends_of_friends_sql,
		{'user': user}
	)]


def check_friends(user, friend):
	row = _fetchone(
		_friends_check_sql,
		(user, friend)
	)
	return None if not row else row[0] == 1


# Spotify Auth queries

_insert_spotify_auth_sql = """
	INSERT INTO synchrify_spotify_auth (user, username, access_token, refresh_token, expires_at)
	VALUES (%(user)s, %(username)s, %(access)s, %(refresh)s, %(expires)s)
	ON DUPLICATE KEY UPDATE
		username = %(username)s,
		access_token = %(access)s,
		refresh_token = %(refresh)s,
		expires_at = %(expires)s
"""

_spotify_auth_by_id_sql = """
	SELECT username, access_token, refresh_token, expires_at FROM synchrify_spotify_auth
	WHERE user = %s
"""


def insert_spotify_auth(user, auth):
	_execute(
		_insert_spotify_auth_sql,
		{
			'user': user,
			'username': auth.username,
			'access': auth.access_token,
			'refresh': auth.refresh_token,
			'expires': auth.expires_at,
		}
	)


def get_spotify_auth(user, requests_timeout=None):
	row = _fetchone(
		_spotify_auth_by_id_sql,
		(user,)
	)
	if not row:
		return None
	else:
		username, access_token, refresh_token, expires_at = row
		return SpotifyUserAuth(
			access_token, refresh_token, expires_at, user, username, requests_timeout
		)


# Content queries

_insert_content_sql = """
	INSERT INTO synchrify_spotify_content (type, uri, name)
	VALUES (%(type)s, %(uri)s, %(name)s)
	ON DUPLICATE KEY UPDATE
		name = %(name)s
"""

_content_exists_sql = """
	SELECT COUNT(*) FROM synchrify_spotify_content
	WHERE id = %s
"""

_content_by_id = """
	SELECT type, uri, name FROM synchrify_spotify_content
	WHERE id = %s
"""

_content_by_uri = """
	SELECT id, name FROM synchrify_spotify_content
	WHERE type = %s AND uri = %s
"""


def insert_content(content_type, uri, name):
	_execute(
		_insert_content_sql,
		{
			'type': content_type,
			'uri': uri,
			'name': name,
		}
	)


def check_content_exists(content):
	row = _fetchone(
		_content_exists_sql,
		(content,)
	)
	return None if not row else row[0] == 1


def get_content_by_id(content):
	return _fetchone(
		_content_by_id,
		(content,)
	)


def get_content_by_uri(content_type, uri):
	return _fetchone(
		_content_by_uri,
		(content_type, uri)
	)


# Rating queries

_insert_rating_sql = """
	INSERT INTO synchrify_ratings (user, content, rating)
	VALUES (%(user)s, %(content)s, %(rating)s)
	ON DUPLICATE KEY UPDATE
		rating = %(rating)s
"""

_delete_rating_sql = """
	DELETE FROM synchrify_ratings
	WHERE user = %s AND content = %s
"""

_content_rating_sql = """
	SELECT rating FROM synchrify_ratings
	WHERE user = %s AND content = %s
"""

_ratings_list_sql = """
	SELECT content, rating FROM synchrify_ratings
	WHERE user = %s
"""

_ratings_list_friends_sql = """
	SELECT content, rating FROM synchrify_ratings
	WHERE user IN (
		SELECT friendee FROM synchrify_friends f
		WHERE friender = %s AND (
			SELECT IF(COUNT(*), TRUE, FALSE) FROM synchrify_friends
			WHERE friender = f.friendee AND friendee = f.friender
		)
	)
"""


def insert_rating(user, content, rating):
	_execute(
		_insert_rating_sql,
		{
			'user': user,
			'content': content,
			'rating': rating,
		}
	)


def delete_rating(user, content):
	_execute(
		_delete_rating_sql,
		(user, content)
	)


def get_rating(user, content):
	row = _fetchone(
		_content_rating_sql,
		(user, content)
	)
	return None if not row else row[0]


def get_ratings(user):
	return [{'content': content_id, 'rating': rating}
		for content_id, rating in _fetchall(
			_ratings_list_sql,
			(user,)
		)
	]


def get_friends_ratings(user):
	return [{'content': content_id, 'rating': rating}
		for content_id, rating in _fetchall(
			_ratings_list_friends_sql,
			(user,)
		)
	]
