import asyncio
import os
from dotenv import load_dotenv

# Ensure we load env before importing cogs.music
load_dotenv()

from cogs.music import get_track_info_from_spotify, YTDLSource

def test_spotify_auth_and_fetch():
    url = "https://open.spotify.com/track/7FeEiAWqWScpMFnlLSUvX2?si=cf6099296c9d49db"
    print(f"Testing URL: {url}")
    try:
        query_string = get_track_info_from_spotify(url)
        print(f"✅ Spotify API 授權成功！成功獲取歌曲資訊: {query_string}")
        return query_string
    except Exception as e:
        print(f"❌ Spotify API 獲取失敗: {e}")
        return None

async def test_ytdl_full_pipeline(query_string):
    print(f"\n正在將字串交給 yt-dlp 解析: {query_string}")
    try:
        # stream=True will print URL, stream=False will download. We use stream=True.
        # However, testing YTDLSource requires a mocked discord voice client/event loop.
        # We can just call YTDLSource.from_query without starting bot.
        # Since from_query uses discord.FFmpegPCMAudio, we need to ensure FFMPEG is not crashing or we just handle the exception.
        
        # Actually, if ffmpeg is not properly installed, FFmpegPCMAudio will raise ClientException. 
        # But wait, youtube-dl part:
        player = await YTDLSource.from_query(query_string, stream=True)
        print(f"✅ yt-dlp 直連獲取成功！影片標題為: {player.title}")
        print(f"✅ FFMPEG Source Object created (Ready to stream).")
    except Exception as e:
        print(f"❌ yt-dlp/ffmpeg 發生錯誤: {e}")

if __name__ == "__main__":
    qs = test_spotify_auth_and_fetch()
    if qs and "YOASOBI" in qs:
        # Run async test
        asyncio.run(test_ytdl_full_pipeline(qs))
