from django.db import connection, migrations


create_users_sql = """
	CREATE TABLE synchrify_users (
		id INTEGER PRIMARY KEY AUTO_INCREMENT,
		email VARCHAR(100) UNIQUE NOT NULL,
		password CHAR(32) NOT NULL,
		activated INTEGER NOT NULL DEFAULT 0,
		CHECK (activated in (0, 1))
	)
"""

create_activations_sql = """
	CREATE TABLE synchrify_activations (
		token CHAR(36) PRIMARY KEY,
		user INTEGER UNIQUE NOT NULL,
		valid INTEGER NOT NULL DEFAULT 1,
		FOREIGN KEY (user)
			REFERENCES synchrify_users(id)
				ON DELETE CASCADE,
		CHECK (valid in (0, 1))
	)
"""

create_friends_sql = """
	CREATE TABLE synchrify_friends (
		friender INTEGER NOT NULL,
		friendee INTEGER NOT NULL,
		PRIMARY KEY (friender, friendee),
		FOREIGN KEY (friender)
			REFERENCES synchrify_users(id)
				ON DELETE CASCADE,
		FOREIGN KEY (friendee)
			REFERENCES synchrify_users(id)
				ON DELETE CASCADE,
		CHECK (friender <> friendee)
	)
"""

create_spotify_auth_sql = """
	CREATE TABLE synchrify_spotify_auth (
		user INTEGER PRIMARY KEY,
		username VARCHAR(50),
		access_token TEXT NOT NULL,
		refresh_token CHAR(150) NOT NULL,
		expires_at INTEGER NOT NULL,
		FOREIGN KEY (user)
			REFERENCES synchrify_users(id)
				ON DELETE CASCADE
	)
"""

create_content_sql = """
	CREATE TABLE synchrify_spotify_content (
		id INTEGER PRIMARY KEY AUTO_INCREMENT,
		type CHAR(8) NOT NULL,
		uri CHAR(22) NOT NULL,
		name VARCHAR(100),
		UNIQUE KEY (type, uri),
		CHECK (type in ('track', 'artist', 'album', 'playlist'))
	)
"""

create_ratings_sql = """
	CREATE TABLE synchrify_ratings (
		user INTEGER NOT NULL,
		content INTEGER NOT NULL,
		rating TINYINT UNSIGNED NOT NULL,
		PRIMARY KEY (user, content),
		FOREIGN KEY (user)
			REFERENCES synchrify_users(id)
				ON DELETE CASCADE,
		FOREIGN KEY (content)
			REFERENCES synchrify_spotify_content(id)
				ON DELETE CASCADE,
		CHECK (rating <= 10)
	)
"""


def _execute(query):
	with connection.cursor() as cursor:
		cursor.execute(query)


def create_users(apps, schema_editor):
	_execute(create_users_sql)


def create_activations(apps, schema_editor):
	_execute(create_activations_sql)


def create_friends(apps, schema_editor):
	_execute(create_friends_sql)


def create_spotify_auth(apps, schema_editor):
	_execute(create_spotify_auth_sql)


def create_content(apps, schema_editor):
	_execute(create_content_sql)


def create_ratings(apps, schema_editor):
	_execute(create_ratings_sql)


class Migration(migrations.Migration):
	dependencies = [
	]

	operations = [
		migrations.RunPython(create_users),
		migrations.RunPython(create_activations),
		migrations.RunPython(create_friends),
		migrations.RunPython(create_spotify_auth),
		migrations.RunPython(create_content),
		migrations.RunPython(create_ratings),
	]
