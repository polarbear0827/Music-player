import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import re

load_dotenv()

spotify_client_id = os.getenv('SPOTIPY_CLIENT_ID')
spotify_client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')

try:
    print("正在測試 Spotify API 驗證...")
    auth_manager = SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)

    url = "https://open.spotify.com/track/7FeEiAWqWScpMFnlLSUvX2?si=cf6099296c9d49db"
    match = re.search(r"track/([a-zA-Z0-9]+)", url)
    if not match:
        raise ValueError("Regex 解析失敗！")
    track_id = match.group(1)

    print(f"提取 Track ID: {track_id}")
    track = sp.track(track_id)
    
    print("✅ Spotify API 連線與資料擷取完美成功！")
    print(f"🎵 歌曲名稱: {track['name']}")
    print(f"🎤 演出者: {track['artists'][0]['name']}")
    print(f"💿 專輯: {track['album']['name']}")
except spotipy.exceptions.SpotifyException as e:
    print(f"❌ Spotify API 錯誤: 授權失敗或憑證無法使用. 錯誤細節: {e}")
except Exception as e:
    print(f"❌ 發生其他意外錯誤: {e}")
