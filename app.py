import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, url_for, session, redirect
import time

app = Flask(__name__)
app.config.update(
    SESSION_COOKIE_NAME='session',
    SECRET_KEY='tylerdiscoverweekly'
)
TOKEN_INFO = 'token_info'

@app.route('/')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)

@app.route('/redirect')
def redirect_to_page():
    session.clear()
    code = request.args.get('code')
    token_info = create_spotify_oauth().get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('save_discover'))

@app.route('/saveDiscoverWeekly')
def save_discover():
    try:
        token_info = get_token()
    except Exception as e:
        print(f"User is not logged in: {e}")
        return redirect('/')
    
    spotify = spotipy.Spotify(auth=token_info['access_token'])
    user_id = spotify.current_user()['id']
    discover_weekly_id = None
    discover_saved_id = None
    current_playlists = spotify.current_user_playlists()['items']
    
    # Debug print statements
    print("Current playlists:")
    for playlist in current_playlists:
        print(f"Playlist name: {playlist['name']}")

    for playlist in current_playlists:
        if playlist['name'] == "Discover Weekly":
            discover_weekly_id = playlist['id']
        if playlist['name'] == 'My Discover Saved':
            discover_saved_id = playlist['id']
    
    if not discover_weekly_id:
        return "Discover Weekly Not Found"

    if not discover_saved_id:
        new_playlist = spotify.user_playlist_create(user_id, 'My Discover Saved', True)
        discover_saved_id = new_playlist['id']
    
    discover_weekly_playlist = spotify.playlist_items(discover_weekly_id)
    song_uris = [song['track']['uri'] for song in discover_weekly_playlist['items']]
    
    spotify.user_playlist_add_tracks(user_id, discover_saved_id, song_uris)
    
    return "OAUTH SUCCESS"

def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if token_info is None:
        return redirect(url_for('login'))
    
    current_time = int(time.time())
    is_token_expired = token_info['expires_at'] - current_time < 60
    if is_token_expired:
        spotipy_oauth = create_spotify_oauth()
        token_info = spotipy_oauth.refresh_access_token(token_info['refresh_token'])
        session[TOKEN_INFO] = token_info
    
    return token_info

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id="ccce6787bbb14a3dba834b5a5282b97f",
        client_secret="37f8bd0bb3404ddb923846aa36af9c18",
        redirect_uri=url_for('redirect_to_page', _external=True),
        scope='user-library-read playlist-modify-public playlist-modify-private'
    )

if __name__ == '__main__':
    app.run(debug=True)