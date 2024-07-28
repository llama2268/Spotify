import json
import boto3
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import uuid

# Constants
TOKEN_TABLE = 'SpotifyTokens'
client_id = "ccce6787bbb14a3dba834b5a5282b97f"
client_secret = "37f8bd0bb3404ddb923846aa36af9c18"
redirect_uri = "https://5rhq9t2d0l.execute-api.us-west-1.amazonaws.com/prod/redirect"

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TOKEN_TABLE)

def login(event):
    auth_url = create_spotify_oauth().get_authorize_url()
    return {
        'statusCode': 302,
        'headers': {
            'Location': auth_url
        }
    }

def redirect_to_page(event):
    try:
        if 'queryStringParameters' not in event or 'code' not in event['queryStringParameters']:
            raise KeyError("Missing queryStringParameters or code")
        code = event['queryStringParameters']['code']
        token_info = create_spotify_oauth().get_access_token(code)
        print(f"Token Info: {token_info}")
        
        # Generate a unique identifier for the primary key
        token_info['id'] = str(uuid.uuid4())
        
        table.put_item(Item=token_info)
        return {
            'statusCode': 302,
            'headers': {
                'Location': '/saveDiscoverWeekly'
            }
        }
    except Exception as e:
        print(f"Error in redirect_to_page: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Internal Server Error: {e}")
        }


def save_discover(event):
    token_info = get_token()
    if not token_info:
        return {
            'statusCode': 302,
            'headers': {
                'Location': '/login'
            }
        }
    
    spotify = spotipy.Spotify(auth=token_info['access_token'])
    user_id = spotify.current_user()['id']
    discover_weekly_id = None
    discover_saved_id = None
    current_playlists = spotify.current_user_playlists()['items']
    
    for playlist in current_playlists:
        if playlist['name'] == "Discover Weekly":
            discover_weekly_id = playlist['id']
        if playlist['name'] == 'My Discover Saved':
            discover_saved_id = playlist['id']
    
    if not discover_weekly_id:
        return {
            'statusCode': 200,
            'body': json.dumps("Discover Weekly Not Found")
        }

    if not discover_saved_id:
        new_playlist = spotify.user_playlist_create(user_id, 'My Discover Saved', True)
        discover_saved_id = new_playlist['id']
    
    discover_weekly_playlist = spotify.playlist_items(discover_weekly_id)
    song_uris = [song['track']['uri'] for song in discover_weekly_playlist['items']]
    
    spotify.user_playlist_add_tracks(user_id, discover_saved_id, song_uris)
    
    return {
        'statusCode': 200,
        'body': json.dumps("OAUTH SUCCESS")
    }

def get_token():
    response = table.scan()
    if not response['Items']:
        return None

    token_info = response['Items'][0]
    current_time = int(time.time())
    is_token_expired = token_info['expires_at'] - current_time < 60
    if is_token_expired:
        spotipy_oauth = create_spotify_oauth()
        token_info = spotipy_oauth.refresh_access_token(token_info['refresh_token'])
        
        # Ensure the id is retained during refresh
        token_info['id'] = response['Items'][0]['id']
        
        table.put_item(Item=token_info)
    
    return token_info

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope='user-library-read playlist-modify-public playlist-modify-private'
    )

def trigger_weekly(event):
    return save_discover(event)
    
def lambda_handler(event, context):
    path = event.get('rawPath', None)
    if not path:
        return {
            'statusCode': 400,
            'body': json.dumps('Bad Request: Missing required keys')
        }

    if path == '/prod/login':
        return login(event)
    elif path == '/prod/redirect':
        return redirect_to_page(event)
    elif path == '/prod/saveDiscoverWeekly':
        return save_discover(event)
    elif event.get('source') == 'aws.events':
        return trigger_weekly(event)
    else:
        return {
            'statusCode': 404,
            'body': json.dumps('Not Found')
        }
