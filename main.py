import spotipy
import os
from flask import Flask, render_template, request, redirect
from urllib.parse import urlparse, parse_qs
import socket
from keep_alive import keep_alive
import psutil
import tempfile
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

clientID = os.environ.get('clientID')
clientSECRET = os.environ.get('clientSECRET')
redirectURI = 'https://similarities.redirect/callback'

cache_directory = tempfile.mkdtemp(prefix='spotipy_cache_')
cache_path = os.path.join(cache_directory, '.spotifycache')

sp_oauth = spotipy.SpotifyOAuth(client_id=clientID,
                                client_secret=clientSECRET,
                                redirect_uri=redirectURI,
                                scope='user-library-read user-read-recently-played playlist-modify-public',
                                cache_path=cache_path)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth')
def authenticate():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    authorization_code = request.args.get('code')
    if authorization_code:
        token_info = sp_oauth.get_access_token(authorization_code, as_dict=False)
        access_token = token_info
        sp = spotipy.Spotify(auth=access_token)

        playlists = sp.current_user_playlists()
        playlist_id = None
        
        for playlist in playlists['items']:
            if playlist['name'] == 'Similarities Playlist':
                playlist_id = playlist['id']
                break
        
        if playlist_id:
            playlist_tracks = sp.playlist_tracks(playlist_id)
            tracks = []
            for track in playlist_tracks['items']:
                track_info = {
                    'name': track['track']['name'],
                    'artist': track['track']['artists'][0]['name'],
                    'image': track['track']['album']['images'][0]['url'],
                    'album_name': track['track']['album']['name']
                }
                tracks.append(track_info)

            return render_template('playlist_result.html', tracks=tracks)
        else:
            return "Playlist not found."
    else:
        return "Authentication failed. No authorization code received."

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    #print("Inside create_playlist route")
    authorization_code = sp_oauth.get_access_token(None, as_dict=False)
    #print("Authorization code:", authorization_code)
    if authorization_code:
        token_info = sp_oauth.get_access_token(authorization_code, as_dict=False)
        access_token = token_info
        sp = spotipy.Spotify(auth=access_token)

        user_info = sp.current_user()
        username = user_info['id']

        recent_tracks = sp.current_user_recently_played()
        most_recent_track = recent_tracks['items'][0]['track']

        num_songs_to_add = int(request.form['num_songs_to_add'])
        #print("Number of songs to add:", num_songs_to_add)
        similar_tracks = sp.recommendations(seed_tracks=[most_recent_track['id']],
                                            seed_genres=None,
                                            seed_artists=None,
                                            limit=num_songs_to_add)

        similar_track_ids = [track['id'] for track in similar_tracks['tracks']]
        playlist_name = 'Similarities Playlist'
        playlists = sp.user_playlists(user=username)
        existing_playlist = next((playlist for playlist in playlists['items'] if playlist['name'] == playlist_name), None)
        if existing_playlist:
            sp.playlist_add_items(playlist_id=existing_playlist['id'], items=similar_track_ids)
            playlist_id = existing_playlist['id']
            message = "Tracks added to the existing playlist!"
        else:
            new_playlist = sp.user_playlist_create(user=username, name=playlist_name, public=True)
            sp.playlist_add_items(playlist_id=new_playlist['id'], items=similar_track_ids)
            playlist_id = new_playlist['id']
            message = "Playlist created and tracks added!"

        playlist_tracks = sp.playlist_tracks(playlist_id=playlist_id)
        tracks = []
        for track in playlist_tracks['items']:
          track_info = {
              'name': track['track']['name'],
              'artist': track['track']['artists'][0]['name'],
              'image': track['track']['album']['images'][0]['url'],
              'album_name': track['track']['album']['name']
          }
          tracks.append(track_info)
  
        return render_template('playlist_result.html', tracks=tracks, message=message, playlist_id=playlist_id)
    
    return "An error occurred."

@app.route('/input_callback', methods=['POST'])
def input_callback():
    redirect_url = request.form.get('redirect_url')

    if redirect_url:
        parsed_url = urlparse(redirect_url)
        query_params = parse_qs(parsed_url.query)
        authorization_code = query_params.get('code', [None])[0]

        if authorization_code:
            token_info = sp_oauth.get_access_token(authorization_code, as_dict=False)
            access_token = token_info
            sp = spotipy.Spotify(auth=access_token)

            playlists = sp.current_user_playlists()
            playlist_id = None

            for playlist in playlists['items']:
                if playlist['name'] == 'Similarities Playlist':
                    playlist_id = playlist['id']
                    break

            if not playlist_id:
                # Create the playlist if it doesn't exist
                user_info = sp.current_user()
                username = user_info['id']
                new_playlist = sp.user_playlist_create(user=username, name='Similarities Playlist', public=True)
                playlist_id = new_playlist['id']

            playlist_tracks = sp.playlist_tracks(playlist_id)
            tracks = []
            for track in playlist_tracks['items']:
                track_info = {
                    'name': track['track']['name'],
                    'artist': track['track']['artists'][0]['name'],
                    'image': track['track']['album']['images'][0]['url'],
                    'album_name': track['track']['album']['name']
                }
                tracks.append(track_info)

            return render_template('playlist_result.html', tracks=tracks)
        else:
            return "Authentication failed. No authorization code received."
    else:
        return "Redirect URL not provided."

def kill_process_by_port(port):
    for process in psutil.process_iter(attrs=['pid', 'name', 'connections']):
        try:
            for conn in process.info['connections']:
                if conn.laddr.port == port:
                    process_pid = process.info['pid']
                    process_name = process.info['name']
                    print(f"Terminating process: {process_name} (PID: {process_pid}) using port {port}")
                    psutil.Process(process_pid).terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

      
def is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

if __name__ == '__main__':
    desired_port = 5000
    if is_port_available(desired_port):
        keep_alive(desired_port)
        app.run(host='0.0.0.0', port=desired_port)
    else:
        print(f"Port {desired_port} is not available.")
        kill_process_by_port(desired_port)
        app.run(host='0.0.0.0', port=desired_port)
