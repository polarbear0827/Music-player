import asyncio
import os
from dotenv import load_dotenv

# Load real environment variables
load_dotenv()

from cogs.music import get_track_info_from_spotify, YTDLSource

async def run_full_test():
    url = "https://open.spotify.com/track/7FeEiAWqWScpMFnlLSUvX2?si=cf6099296c9d49db"
    print(f"1. 測試開始，輸入的 Spotify 網址為: {url}")
    
    try:
        # Test 1: Spotify API Parsing
        query = get_track_info_from_spotify(url)
        print(f"✅ [測試 1 通過] Spotify API 驗證與解析成功！轉換結果: {query}")
        
    except Exception as e:
        print(f"❌ [測試 1 失敗] Spotify 解析錯誤: {e}")
        return

    try:
        # Test 2: yt-dlp direct fetch
        print(f"2. 準備將 '{query}' 餵給 yt-dlp 解析串流...")
        player = await YTDLSource.from_query(query, stream=True)
        print(f"✅ [測試 2 通過] YouTube 擷取成功！影片標題: {player.title}")
        print(f"✅ 測試完畢，此組金鑰完全可正常服役！")
    except Exception as e:
        print(f"❌ [測試 2 失敗] yt-dlp 發生錯誤: {e}")

if __name__ == "__main__":
    asyncio.run(run_full_test())
