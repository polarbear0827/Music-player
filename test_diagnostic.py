import asyncio
import re
import yt_dlp

def test_spotify_regex():
    url = "https://open.spotify.com/track/7FeEiAWqWScpMFnlLSUvX2?si=cf6099296c9d49db"
    match = re.search(r"track/([a-zA-Z0-9]+)", url)
    if match:
        print(f"✅ Spotify Regex Match Success! Track ID: {match.group(1)}")
    else:
        print("❌ Spotify Regex Match Failed!")

def test_ytdl_search():
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0'
    }
    ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
    
    # 假設我們從 Spotify API 獲得了歌手與歌名
    mock_spotify_result = "ytsearch:YOASOBI - IDOL"
    print(f"正在測試 yt-dlp 的 YouTube 模擬搜尋功能: {mock_spotify_result}")
    
    try:
        data = ytdl.extract_info(mock_spotify_result, download=False)
        if 'entries' in data:
            entry = data['entries'][0]
            print(f"✅ yt-dlp 搜尋成功！找到影片標題: {entry.get('title')}")
            print(f"✅ 串流播放直連網址取得成功！(網址長度: {len(entry.get('url'))})")
        else:
            print("❌ 未找到影片")
    except Exception as e:
        print(f"❌ yt-dlp 執行時發生錯誤: {e}")

if __name__ == "__main__":
    test_spotify_regex()
    test_ytdl_search()
