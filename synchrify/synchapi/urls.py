from django.urls import path, re_path

from . import views


app_name = 'synchapi'

urlpatterns = [

	path('register/', views.register, name='register'),
	re_path(r'activate/(?P<token>[a-z\d]{8}-[a-z\d]{4}-[a-z\d]{4}-[a-z\d]{4}-[a-z\d]{12})',
			views.activate, name='activate'),  # Takes activation token (UUIDv4)
	path('login/', views.login, name='login'),
	path('logout/', views.logout, name='logout'),

	path('friends/list', views.friends_list, name='friends-list'),
	path('friends/list/<int:friend_id>', views.friends_list, name='friends-list-other'),
	path('friends/list/friends', views.friends_list_friends, name='friends-list-all'),
	path('friends/pending', views.friends_pending, name='friends-pending'),
	path('friends/add/<int:friend_id>', views.friends_add, name='friends-add'),
	path('friends/remove/<int:friend_id>', views.friends_remove, name='friends-remove'),

	path('content/<int:content_id>', views.content_get_by_id, name='content-get-by-id'),
	path('content/<int:content_id>/rating', views.content_get_rating, name='content-get-rating'),
	path('content/<int:content_id>/rating/<int:friend_id>', views.content_get_rating, name='content-get-rating-other'),
	path('content/<int:content_id>/rating/set/<int:rating>', views.content_set_rating, name='content-set-rating'),
	path('content/<int:content_id>/rating/reset', views.content_reset_rating, name='content-reset-rating'),
	path('content/<content_type>/<uri>', views.content_get_by_uri, name='content-get-by-uri'),

	path('ratings/list', views.ratings_list, name='ratings-list'),
	path('ratings/list/<int:friend_id>', views.ratings_list, name='ratings-list-other'),
	path('ratings/list/friends', views.ratings_list_friends, name='ratings-list-all'),

	path('spotify/auth', views.spotify_auth, name='spotify-auth'),
	path('spotify/auth/callback', views.spotify_auth_callback, name='spotify-auth-callback'),

	path('spotify/user/<endpoint>', views.spotify_wrapper, name='spotify-wrapper'),
]
