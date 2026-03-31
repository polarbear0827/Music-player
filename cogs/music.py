import asyncio
import re
import random
import logging
import sqlite3
import urllib.request
from datetime import datetime
import discord
from discord.ext import commands
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from dotenv import load_dotenv
import json
from groq import AsyncGroq
load_dotenv()

# Setup logging
log = logging.getLogger(__name__)

# yt-dlp Configuration
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0', 
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
ytdl_search = yt_dlp.YoutubeDL(dict(YTDL_OPTIONS, extract_flat=True, default_search='ytsearch5'))

# Spotify Setup
spotify_client_id = os.getenv('SPOTIPY_CLIENT_ID')
spotify_client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')

sp = None
if spotify_client_id and spotify_client_secret and spotify_client_id != "your_spotify_client_id_here":
    auth_manager = SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
else:
    log.warning("Spotify credentials not configured correctly. Spotify link parsing will fail.")

# Groq Setup
groq_api_key = os.getenv('GROQ_API_KEY')
groq_client = None
if groq_api_key:
    groq_client = AsyncGroq(api_key=groq_api_key)
else:
    log.warning("GROQ_API_KEY not found. DJ and Chat features will be disabled.")


def is_spotify_url(url: str) -> bool:
    return "open.spotify.com/" in url and any(x in url for x in ["/track/", "/album/", "/playlist/"])

def is_apple_music_url(url: str) -> bool:
    return "music.apple.com/" in url

def get_apple_music_title(url: str) -> str:
    """Uses urllib and regex to scrape the title of an Apple Music page."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')
            match = re.search(r'<title>(.*?)</title>', html, flags=re.IGNORECASE)
            if match:
                title = match.group(1).replace(" on Apple Music", "")
                title = title.replace(" - Single", "").replace(" - EP", "")
                title = title.replace("\u200e", "") # Remove zero-width spaces
                return title
    except Exception as e:
        log.error(f"Apple Music scraping error: {e}")
    return url # Fallback to URL


def get_track_info_from_spotify(url: str) -> list[str]:
    """Parses Spotify URL and returns a list of query strings: ['Artist - Track Name']"""
    if not sp:
        raise ValueError("Spotify credentials not configured.")
        
    queries = []
    try:
        if "/track/" in url:
            match = re.search(r"track/([a-zA-Z0-9]+)", url)
            if match:
                track = sp.track(match.group(1))
                queries.append(f"{track['artists'][0]['name']} - {track['name']}")
                
        elif "/album/" in url:
            match = re.search(r"album/([a-zA-Z0-9]+)", url)
            if match:
                results = sp.album_tracks(match.group(1))
                for item in results['items']:
                    queries.append(f"{item['artists'][0]['name']} - {item['name']}")
                    
        elif "/playlist/" in url:
            match = re.search(r"playlist/([a-zA-Z0-9]+)", url)
            if match:
                results = sp.playlist_tracks(match.group(1))
                tracks = results['items']
                while results['next']:
                    results = sp.next(results)
                    tracks.extend(results['items'])
                
                for item in tracks:
                    if len(queries) >= 200:
                        break
                    track = item.get('track')
                    if track and track.get('artists') and track.get('name'):
                        queries.append(f"{track['artists'][0]['name']} - {track['name']}")
                        
    except Exception as e:
        log.error(f"Spotify URL parsing error: {e}")
        
    if not queries:
        return [url] # Fallback to original url
    return queries


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_query(cls, query, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        
        # Prepend ytsearch: if it's not a direct URL to explicitly tell yt-dlp to search
        if not query.startswith('http'):
            query = f"ytsearch:{query}"

        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=not stream))
        except Exception as e:
            log.error(f"Error fetching data from yt_dlp: {e}")
            raise e

        # If it's a playlist or search result, get the first item
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Maps guild_id to a list of dicts: {'query': str, 'requester_id': int, 'requester_name': str}
        self.queues = {}
        # Maps guild_id to a list of previously played items
        self.histories = {}
        # Maps guild_id to currently playing item dict to allow going back
        self.current_song = {}
        self.remove_locks = set()
        
        # SQLite Database Integration for Ranking System
        self._init_db()

    def _init_db(self):
        try:
            self.conn = sqlite3.connect('music_rank.db', check_same_thread=False)
            self.cursor = self.conn.cursor()
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS play_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    user_name TEXT,
                    query TEXT,
                    title TEXT,
                    play_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Attempt to alter existing table safely if upgrading old DB
            try:
                self.cursor.execute("ALTER TABLE play_history ADD COLUMN query TEXT")
                self.cursor.execute("ALTER TABLE play_history ADD COLUMN title TEXT")
            except Exception:
                pass
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    creator_id INTEGER,
                    name TEXT,
                    UNIQUE(guild_id, name)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlist_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER,
                    query TEXT,
                    FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS guess_scores (
                    guild_id INTEGER,
                    user_id INTEGER,
                    user_name TEXT,
                    score INTEGER DEFAULT 0,
                    PRIMARY KEY(guild_id, user_id)
                )
            ''')
            self.conn.commit()
        except Exception as e:
            log.error(f"DB Error: Failed to initialize SQLite: {e}")

    def record_play(self, guild_id, user_id, user_name, query, title):
        try:
            self.cursor.execute('''
                INSERT INTO play_history (guild_id, user_id, user_name, query, title) 
                VALUES (?, ?, ?, ?, ?)
            ''', (guild_id, user_id, user_name, query, title))
            self.conn.commit()
        except Exception as e:
            log.error(f"DB Insert Error: {e}")

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]
        
    def get_history(self, guild_id):
        if guild_id not in self.histories:
            self.histories[guild_id] = []
        return self.histories[guild_id]

    async def get_dj_intro(self, song_title: str, requester: str) -> str:
        if not groq_client: return f"🎵 **Now playing:** {song_title}\n*(Requested by {requester})*"
        
        prompt = (f"你現在是在 Discord 上的溫馨音樂廣播 DJ。即將播放的歌是『{song_title}』，點播者是『{requester}』。"
                  "請用10~30個繁體中文字說一句鼓勵或溫馨的話介紹這首歌，結尾加一個表情符號。不要加上任何其他的解釋或標題。")
        try:
            comp = await groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-70b-8192",
                temperature=0.7,
                max_tokens=60
            )
            dj_msg = comp.choices[0].message.content.strip()
            return f"🎙️ **DJ:** 「*{dj_msg}*」\n🎵 **Now playing:** {song_title}"
        except Exception as e:
            log.error(f"Groq error: {e}")
            return f"🎵 **Now playing:** {song_title}\n*(Requested by {requester})*"

    async def play_next(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if len(queue) > 0:
            item = queue.pop(0)
            
            if ctx.guild.id in self.current_song and self.current_song[ctx.guild.id] is not None:
                self.get_history(ctx.guild.id).append(self.current_song[ctx.guild.id])
                
            self.current_song[ctx.guild.id] = item
            
            # Write to database (STRICT MODE: Only count score when song actually starts playing)
            try:
                player = await YTDLSource.from_query(item['query'], loop=self.bot.loop, stream=True)
                self.bot.loop.run_in_executor(None, self.record_play, ctx.guild.id, item['requester_id'], item['requester_name'], item['query'], player.title)
                
                ctx.voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.play_next(ctx)) if e is None else print(f'Player error: {e}'))
                
                intro_msg = await self.get_dj_intro(player.title, item['requester_name'])
                await ctx.send(intro_msg)
            except Exception as e:
                await ctx.send(f"An error occurred while trying to play `{item['query']}`: {e}")
                await asyncio.sleep(2) # Prevent recursion limit infinite loops
                await self.play_next(ctx)
        else:
            self.current_song[ctx.guild.id] = None
            await ctx.send("Queue empty. Waiting for more tracks.")

    @commands.command(name='play', help='Plays a song, album, or playlist from YouTube/Spotify/Apple Music/SoundCloud')
    async def play(self, ctx, *, query: str):
        if not ctx.message.author.voice:
            return await ctx.send("You are not connected to a voice channel.")
        
        channel = ctx.message.author.voice.channel

        if not ctx.voice_client:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)

        queue = self.get_queue(ctx.guild.id)
        queries = []
        
        # 1. Spotify Handling
        if is_spotify_url(query):
            try:
                msg = await ctx.send(f"⏳ Fetching Spotify tracks... Please wait.")
                parsed_queries = await self.bot.loop.run_in_executor(None, get_track_info_from_spotify, query)
                
                track_count = len(parsed_queries)
                if track_count == 0:
                    return await msg.edit(content="❌ Could not parse any tracks from that Spotify link.")
                elif track_count > 1:
                    await msg.edit(content=f"✅ Found {track_count} tracks from Spotify! Adding to queue...")
                else:
                    await msg.delete() 
                queries.extend(parsed_queries)
            except Exception as e:
                return await ctx.send(f"❌ Failed to parse Spotify link. Error: {e}")
                
        # 2. Apple Music Handling
        elif is_apple_music_url(query):
            msg = await ctx.send(f"⏳ Fetching Apple Music track info...")
            title = await self.bot.loop.run_in_executor(None, get_apple_music_title, query)
            await msg.delete()
            queries.append(title)
            
        # 3. Interactive Keyword Search Selection
        elif not query.startswith('http'):
            msg = await ctx.send(f"🔍 Searching YouTube for: `{query}`...")
            try:
                search_query = f"ytsearch5:{query}"
                data = await self.bot.loop.run_in_executor(None, lambda: ytdl_search.extract_info(search_query, download=False))
                entries = data.get('entries', [])
                if not entries:
                    return await msg.edit(content="❌ No results found on YouTube.")
                    
                options_text = "**Select a track by replying with its number (1-5) within 30 seconds:**\n"
                for i, entry in enumerate(entries, 1):
                    options_text += f"**{i}.** {entry.get('title')}\n"
                    
                await msg.edit(content=options_text)
                
                def check(m):
                    return m.author == ctx.message.author and m.channel == ctx.message.channel and m.content.isdigit()
                    
                try:
                    choice_msg = await self.bot.wait_for('message', timeout=30.0, check=check)
                    choice = int(choice_msg.content)
                    if 1 <= choice <= len(entries):
                        selected_entry = entries[choice - 1]
                        video_url = selected_entry.get('url') or selected_entry.get('webpage_url')
                        if not video_url:
                            video_url = f"https://www.youtube.com/watch?v={selected_entry.get('id')}"
                            
                        queries.append(video_url)
                        await ctx.send(f"✅ Selected: **{selected_entry.get('title')}**")
                    else:
                        return await ctx.send("❌ Invalid selection. Cancelling play command.")
                except asyncio.TimeoutError:
                    return await msg.edit(content="❌ Search timed out. Please try again.")
            except Exception as e:
                return await msg.edit(content=f"❌ Error searching YouTube: {e}")
        
        # 4. Normal URLs (YouTube, SoundCloud, etc)
        else:
             queries.append(query)
        
        # Enqueue the structured items
        for q in queries:
            item = {'query': q, 'requester_id': ctx.author.id, 'requester_name': ctx.author.display_name}
            queue.append(item)
            
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await self.play_next(ctx)
        elif len(queries) == 1:
            title_text = queries[0]
            if str(title_text).startswith('http'):
                title_text = "Requested Link" 
            await ctx.send(f"Added to queue: **{title_text}**")


    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name='dj', help='Ask the AI DJ for a 1-song contextual recommendation')
    async def dj(self, ctx, *, prompt: str):
        prompt = prompt[:150] # Prevent giant malicious prompts
        if not groq_client: return await ctx.send("Groq API 尚未解鎖，無法呼叫 AI DJ！")
        if not ctx.message.author.voice: return await ctx.send("你必須先進入語音頻道！")
        
        msg = await ctx.send("🧠 DJ 正在為您精挑細選專屬音樂...")
        sys_prompt = ("你是一位溫馨可愛的音樂 DJ。根據使用者的情境，推薦 1 首最適合的歌。"
                      "嚴格只能回傳純 JSON 陣列，不要有任何 Markdown 或其他文字。"
                      "格式範例: [\"Artist - Song Name\"]")
        try:
            comp = await groq_client.chat.completions.create(
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                model="llama3-70b-8192",
                temperature=0.7,
                max_tokens=100
            )
            raw_text = comp.choices[0].message.content.strip()
            if raw_text.startswith("```json"): raw_text = raw_text[7:]
            if raw_text.startswith("```"): raw_text = raw_text[3:]
            if raw_text.endswith("```"): raw_text = raw_text[:-3]
            
            song_list = json.loads(raw_text.strip())
            if not song_list:
                return await msg.edit(content="❌ 抱歉，DJ 想不到適合的歌，請換個情境說法！")
            
            song = song_list[0]
            await msg.edit(content=f"✅ DJ 靈光一閃！推薦了這首：**{song}**\n正在為您加入列隊中...")
            
            queue = self.get_queue(ctx.guild.id)
            item = {'query': song, 'requester_id': ctx.author.id, 'requester_name': ctx.author.display_name}
            queue.append(item)

            channel = ctx.message.author.voice.channel
            if not ctx.voice_client:
                await channel.connect()
            elif ctx.voice_client.channel != channel:
                await ctx.voice_client.move_to(channel)

            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await self.play_next(ctx)
            
        except json.JSONDecodeError:
            await msg.edit(content="❌ AI DJ 不小心語無倫次了，請再試一次！")
        except Exception as e:
            await msg.edit(content=f"❌ 發生錯誤: {e}")

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name='chat', help='Chat with the AI DJ natively')
    async def chat(self, ctx, *, message: str):
        message = message[:150]
        if not groq_client: return await ctx.send("Groq API 尚未解鎖，無法對話唷！")
            
        async with ctx.typing():
            try:
                sys_prompt = "你是一個生動可愛、熱情充滿正能量的 Discord 音樂電台 DJ。負責用短短的幾句話，以繁體中文跟群組裡的朋友聊天。結尾加顏文字或 Emoji。"
                comp = await groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": message}
                    ],
                    model="llama3-70b-8192",
                    temperature=0.8,
                    max_tokens=200
                )
                reply = comp.choices[0].message.content.strip()
                await ctx.send(f"🎙️ **DJ:** 「{reply}」")
            except Exception as e:
                await ctx.send(f"❌ DJ 的麥克風壞掉了: {e}")


    @commands.command(name='remove', help='Remove a specific track from the queue interactively')
    async def remove(self, ctx):
        if ctx.guild.id in self.remove_locks:
            return await ctx.send("⏳ 另一個使用者正在刪歌中，請小等 5 秒鐘！")
            
        self.remove_locks.add(ctx.guild.id)
        queue = self.get_queue(ctx.guild.id)
        if not queue:
            return await ctx.send("The queue is currently empty.")
            
        display_limit = 10
        q_list = "**Select a song to remove by replying with its number within 30s:**\n"
        for i, item in enumerate(queue[:display_limit]):
            query_label = item['query']
            if 'http' in query_label:
                query_label = f"[URL Link] requested by {item['requester_name']}"
            else:
                query_label += f" requested by {item['requester_name']}"
            q_list += f"**{i+1}.** {query_label[:50]}\n"
            
        msg = await ctx.send(q_list)
        
        def check(m):
            return m.author == ctx.message.author and m.channel == ctx.message.channel and m.content.isdigit()
            
        try:
            choice_msg = await self.bot.wait_for('message', timeout=5.0, check=check)
            choice = int(choice_msg.content)
            if 1 <= choice <= len(queue[:display_limit]):
                removed_item = queue.pop(choice - 1)
                await ctx.send(f"🗑️ Removed item from queue: `{str(removed_item['query'])[:50]}`")
            else:
                await ctx.send("❌ Invalid number selection.")
        except asyncio.TimeoutError:
            await msg.edit(content="❌ 刪歌操作已超時 (5秒限制)。")
        finally:
            self.remove_locks.discard(ctx.guild.id)


    @commands.command(name='pause', help='Pauses the current song')
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send('⏸️ Paused the music.')
        else:
            await ctx.send("Not currently playing any music.")

    @commands.command(name='resume', help='Resumes the paused song')
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send('▶️ Resumed the music.')
        else:
            await ctx.send("The music is not paused.")

    @commands.command(name='skip', help='Skips the current song')
    async def skip(self, ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send('⏭️ Skipped.')
        else:
            await ctx.send("Not playing any music right now.")

    @commands.command(name='back', help='Plays the previous song')
    async def back(self, ctx):
        history = self.get_history(ctx.guild.id)
        if not history:
            return await ctx.send("No previous songs recorded in history.")
            
        previous_item = history.pop() 
        queue = self.get_queue(ctx.guild.id)
        
        current = self.current_song.get(ctx.guild.id)
        if current:
            queue.insert(0, current)
            
        queue.insert(0, previous_item)
        self.current_song[ctx.guild.id] = None 
        
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop() 
        else:
            await self.play_next(ctx)
            
        await ctx.send('⏮️ Going back to previous track.')

    @commands.command(name='stop', help='Stops music and clears queue')
    async def stop(self, ctx):
        if ctx.voice_client:
            self.queues[ctx.guild.id] = []
            self.histories[ctx.guild.id] = []
            self.current_song[ctx.guild.id] = None
            ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            await ctx.send('⏹️ Disconnected and cleared queue.')
        else:
            await ctx.send("I'm not in a voice channel.")

    @commands.command(name='queue', help='Shows current queue')
    async def queue(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if not queue:
            return await ctx.send('Queue is empty.')
            
        display_limit = 15
        q_list = ''
        for i, item in enumerate(queue[:display_limit]):
            q_label = str(item['query']) if not str(item['query']).startswith('http') else "[Play URL]"
            q_list += f"{i+1}. {q_label} (by {item['requester_name']})\n"
        
        extra = f"\n...and {len(queue) - display_limit} more" if len(queue) > display_limit else ""
        await ctx.send(f'**Current Queue:**\n{q_list}{extra}')

    @commands.command(name='rank', help='Show top users who requested songs. Args: day, month, year, all')
    async def rank(self, ctx, period: str = 'all'):
        query_modifier = ""
        if period == 'day':
            query_modifier = "AND date(play_time) = date('now', 'localtime')"
        elif period == 'month':
            query_modifier = "AND strftime('%Y-%m', play_time) = strftime('%Y-%m', 'now', 'localtime')"
        elif period == 'year':
            query_modifier = "AND strftime('%Y', play_time) = strftime('%Y', 'now', 'localtime')"
        else:
            period = 'all time'
            
        try:
            self.cursor.execute(f'''
                SELECT user_name, COUNT(id) as score 
                FROM play_history 
                WHERE guild_id = ? {query_modifier}
                GROUP BY user_id 
                ORDER BY score DESC 
                LIMIT 10
            ''', (ctx.guild.id,))
            
            results = self.cursor.fetchall()
            
            if not results:
                return await ctx.send(f"🏅 No ranking data available for {period}.")
                
            board = f"🏆 **DJ Ranking ({period.capitalize()})** 🏆\n\n"
            for i, (name, score) in enumerate(results, 1):
                board += f"**{i}.** {name} - `{score} plays`\n"
                
            await ctx.send(board)
        except Exception as e:
            await ctx.send(f"❌ Error fetching rank: {e}")

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ 冷靜一下！這招被封印了，請 {round(error.retry_after, 1)} 秒後再試。")

    @commands.group(name='playlist', invoke_without_command=True, help='Group command for saving/loading server playlists.')
    async def playlist(self, ctx):
        await ctx.send("使用方式：\n`F!playlist save <名稱>` - 儲存當前列隊\n`F!playlist load <名稱>` - 讀取清單\n`F!playlist list` - 檢視所有清單")

    @playlist.command(name='save', help='Save the current queue to a named playlist')
    async def playlist_save(self, ctx, *, name: str):
        queue = self.get_queue(ctx.guild.id)
        if not queue:
            return await ctx.send("❌ 目前列隊是空的，沒有東西可儲存！")
            
        try:
            self.cursor.execute('INSERT OR IGNORE INTO playlists (guild_id, creator_id, name) VALUES (?, ?, ?)', (ctx.guild.id, ctx.author.id, name))
            self.conn.commit()
            
            self.cursor.execute('SELECT id FROM playlists WHERE guild_id = ? AND name = ?', (ctx.guild.id, name))
            row = self.cursor.fetchone()
            if not row:
                return await ctx.send("❌ 儲存失敗。")
            pl_id = row[0]
            
            self.cursor.execute('DELETE FROM playlist_items WHERE playlist_id = ?', (pl_id,))
            for item in queue:
                self.cursor.execute('INSERT INTO playlist_items (playlist_id, query) VALUES (?, ?)', (pl_id, item['query']))
                
            self.conn.commit()
            await ctx.send(f"✅ 成功將 {len(queue)} 首歌儲存至專屬清單：**{name}**")
        except Exception as e:
            await ctx.send(f"❌ 儲存發生錯誤：{e}")

    @playlist.command(name='load', help='Load a named playlist into the queue')
    async def playlist_load(self, ctx, *, name: str):
        try:
            self.cursor.execute('SELECT id FROM playlists WHERE guild_id = ? AND name = ?', (ctx.guild.id, name))
            row = self.cursor.fetchone()
            if not row:
                return await ctx.send(f"❌ 找不到名為 **{name}** 的清單！請確認名稱是否正確。")
                
            pl_id = row[0]
            self.cursor.execute('SELECT query FROM playlist_items WHERE playlist_id = ?', (pl_id,))
            items = self.cursor.fetchall()
            
            if not items:
                return await ctx.send(f"⚠️ 清單 **{name}** 裡面沒有任何歌曲。")
                
            queue = self.get_queue(ctx.guild.id)
            for (query,) in items:
                queue.append({'query': query, 'requester_id': ctx.author.id, 'requester_name': ctx.author.display_name})
                
            await ctx.send(f"✅ 將 **{name}** 中的 {len(items)} 首歌加入列隊！")
            
            viewing_channel = ctx.message.author.voice.channel if ctx.message.author.voice else None
            if viewing_channel:
                if not ctx.voice_client:
                    await viewing_channel.connect()
                elif ctx.voice_client.channel != viewing_channel:
                    await ctx.voice_client.move_to(viewing_channel)
                    
            if ctx.voice_client and not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await self.play_next(ctx)
                
        except Exception as e:
            await ctx.send(f"❌ 讀取發生錯誤：{e}")

    @playlist.command(name='list', help='List all saved playlists for this server')
    async def playlist_list(self, ctx):
        self.cursor.execute('SELECT name FROM playlists WHERE guild_id = ?', (ctx.guild.id,))
        rows = self.cursor.fetchall()
        if not rows:
            return await ctx.send("📦 目前這個伺服器還沒有任何私房清單，用 `F!playlist save <名稱>` 建立一個專屬回憶吧！")
            
        names = "\n".join([f"• **{r[0]}**" for r in rows])
        await ctx.send(f"🎵 **本伺服器私房專屬歌單：**\n{names}")

    @commands.cooldown(1, 30, commands.BucketType.guild)
    @commands.command(name='guess', help='Start a music guessing mini-game based on server history')
    async def guess(self, ctx):
        if not ctx.message.author.voice:
            return await ctx.send("你必須先進入語音頻道！")
            
        # Get random historic song that actually has a query and title
        self.cursor.execute('SELECT query, title FROM play_history WHERE guild_id = ? AND query IS NOT NULL AND title IS NOT NULL ORDER BY RANDOM() LIMIT 1', (ctx.guild.id,))
        row = self.cursor.fetchone()
        if not row:
            return await ctx.send("❌ 你們的點播歷史太少了，無法啟動猜歌遊戲！趕快多點幾首 YouTube 的歌進來吧！")
            
        query, title = row
        clean_title = re.sub(r'[\(\[].*?[\)\]]', '', title).strip().lower() # Remove stuff in brackets for cleaner matching
        
        channel = ctx.message.author.voice.channel
        if not ctx.voice_client:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
            
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop() 
            await asyncio.sleep(0.5) # Give it half a sec to flush stream

        start_time = random.randint(15, 60)
        game_ffmpeg_options = {
            'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_time}',
            'options': '-vn',
        }
        
        try:
            msg = await ctx.send("🎲 **猜歌挑戰開始！**\n正在載入神秘片段...\n*(你有 20 秒鐘的時間，第一個在聊天室給出『正確歌名關鍵字』的人就能得分！)*")
            
            loop = self.bot.loop
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
            if 'entries' in data: data = data['entries'][0]
            filename = data['url']
            player_audio = discord.FFmpegPCMAudio(filename, **game_ffmpeg_options)
            
            ctx.voice_client.play(discord.PCMVolumeTransformer(player_audio, 0.5))
            
            def check(m):
                # Loose matching: >2 chars and substring matching
                return m.channel == ctx.message.channel and len(m.content) >= 2 and m.content.lower() in clean_title

            try:
                winner_msg = await self.bot.wait_for('message', timeout=20.0, check=check)
                ctx.voice_client.stop()
                
                # Add score
                self.cursor.execute('INSERT OR IGNORE INTO guess_scores (guild_id, user_id, user_name, score) VALUES (?, ?, ?, 0)', (ctx.guild.id, winner_msg.author.id, winner_msg.author.display_name))
                self.cursor.execute('UPDATE guess_scores SET score = score + 1 WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, winner_msg.author.id))
                self.conn.commit()
                
                self.cursor.execute('SELECT score FROM guess_scores WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, winner_msg.author.id))
                points = self.cursor.fetchone()[0]
                
                await ctx.send(f"🎉 恭喜 {winner_msg.author.mention} 猜對了！\n這首歌是：**{title}**\n目前總分：`{points} 分`")
            except asyncio.TimeoutError:
                ctx.voice_client.stop()
                await ctx.send(f"⏰ 時間到！沒有人猜中。\n正確解答是：**{title}**")
                
        except Exception as e:
            log.error(f"Guess game error: {e}")
            await ctx.send("❌ 遊戲發生錯誤，可能是這首歌被下架了。請再玩一次！")

async def setup(bot):
    await bot.add_cog(Music(bot))
