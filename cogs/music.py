import asyncio
import re
import random
import logging
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime
import discord
from discord.ext import commands
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from dotenv import load_dotenv
import json
import aiohttp

load_dotenv()

# Loop mode constants
LOOP_OFF = 0
LOOP_SINGLE = 1
LOOP_QUEUE = 2
LOOP_LABELS = {LOOP_OFF: "關閉", LOOP_SINGLE: "單曲循環 🔂", LOOP_QUEUE: "列隊循環 🔁"}

# Setup logging
log = logging.getLogger(__name__)

# OpenRouter / Database Setup
GLOBAL_OR_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

def get_user_api_key(user_id: int) -> str:
    """Retrieve API key from SQLite database initialized in sticker.py"""
    try:
        conn = sqlite3.connect('data/sticker_keys.db', check_same_thread=False)
        row = conn.execute('SELECT api_key FROM user_keys WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        if row: return row[0]
    except Exception:
        pass
    return GLOBAL_OR_API_KEY

async def call_openrouter(messages: list, api_key: str, max_tokens: int, temperature: float = 0.7) -> str:
    """Make HTTP request to OpenRouter API."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/polarbear0827/Music-player",
        "X-Title": "Discord DJ Bot",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "minimax/minimax-m2.5:free",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=20) as resp:
                if resp.status != 200:
                    err_data = await resp.text()
                    raise Exception(f"OpenRouter HTTP {resp.status}: {err_data}")
                
                data = await resp.json()
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0].get("message", {}).get("content")
                    if content is not None:
                        return str(content).strip()
                    return "..." # Fallback for empty content
                raise Exception(f"OpenRouter Unexpected Response: {data}")
    except Exception as e:
        log.error(f"call_openrouter error: {e}")
        raise e


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
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 10M -analyzeduration 10M',
    'options': '-vn -filter:a "volume=1.0"',
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


# 24/7 Radio Dictionary
IDLE_RADIOS = {
    'lofi': 'https://www.youtube.com/watch?v=jfKfPfyJRdk', # Lofi Girl
    'jazz': 'https://www.youtube.com/watch?v=Dx5qFachd3A', # Relaxing Jazz
    'synth': 'https://www.youtube.com/watch?v=4xDzrJKXOOY', # Synthwave Radio
}

def is_spotify_url(url: str) -> bool:
    return "open.spotify.com/" in url and any(x in url for x in ["/track/", "/album/", "/playlist/"])

def is_apple_music_url(url: str) -> bool:
    return "music.apple.com/" in url

def get_apple_music_title(url: str) -> str:
    """Uses urllib and regex to scrape the title of an Apple Music page."""
    try:
        # Handle non-ASCII characters in URL
        parsed_url = urllib.parse.urlparse(url)
        url = urllib.parse.urlunparse(parsed_url._replace(path=urllib.parse.quote(parsed_url.path)))
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')
            match = re.search(r'<title>(.*?)</title>', html, flags=re.IGNORECASE)
            if match:
                title = match.group(1).replace(" on Apple Music", "")
                title = title.replace(" - Single", "").replace(" - EP", "")
                title = title.replace("\u200e", "") # Remove zero-width spaces
                return f"{title} (Official Audio)"
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
                queries.append(f"{track['artists'][0]['name']} - {track['name']} (Official Audio)")
                
        elif "/album/" in url:
            match = re.search(r"album/([a-zA-Z0-9]+)", url)
            if match:
                results = sp.album_tracks(match.group(1))
                for item in results['items']:
                    queries.append(f"{item['artists'][0]['name']} - {item['name']} (Official Audio)")
                    
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
                        queries.append(f"{track['artists'][0]['name']} - {track['name']} (Official Audio)")
                        
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
    async def from_query(cls, query, stream=True):
        # Prepend ytsearch: if it's not a direct URL
        if not query.startswith('http'):
            query = f"ytsearch:{query} (Official Audio)"

        try:
            data = await asyncio.to_thread(ytdl.extract_info, query, **{'download': not stream})
        except Exception as e:
            log.error(f"Error fetching data from yt_dlp: {e}")
            raise e

        # If it's a playlist or search result, get the first item
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

class DashboardView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="⏯", style=discord.ButtonStyle.primary, custom_id="dash_playpause")
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("不播放時無法操作。", ephemeral=True)
        if interaction.guild.id in self.cog.is_playing_radio:
            return await interaction.response.send_message("📻 背景電台無法暫停。", ephemeral=True)
        if vc.is_playing(): vc.pause()
        elif vc.is_paused(): vc.resume()
        await interaction.response.defer()
        await self.cog.update_dashboard(interaction.guild, interaction.channel)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary, custom_id="dash_skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("不播放時無法操作。", ephemeral=True)
        if interaction.guild.id in self.cog.is_playing_radio:
            return await interaction.response.send_message("📻 電台撥放中無法切歌。", ephemeral=True)
        vc.stop()
        await interaction.response.defer()

    @discord.ui.button(label="⏹", style=discord.ButtonStyle.danger, custom_id="dash_stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            self.cog.queues[interaction.guild.id] = []
            self.cog.current_song[interaction.guild.id] = None
            self.cog.active_radios.pop(interaction.guild.id, None)
            self.cog.is_playing_radio.discard(interaction.guild.id)
            vc.stop()
            await vc.disconnect()
        await interaction.response.defer()
        await self.cog.update_dashboard(interaction.guild, interaction.channel)

    @discord.ui.button(label="🔁", style=discord.ButtonStyle.secondary, custom_id="dash_loop")
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild.id
        current = self.cog.loop_mode.get(gid, LOOP_OFF)
        next_mode = (current + 1) % 3  # cycle: 0→1→2→0
        self.cog.loop_mode[gid] = next_mode
        await interaction.response.send_message(
            f"🔁 Loop 模式已切換為：**{LOOP_LABELS[next_mode]}**", ephemeral=True
        )
        await self.cog.update_dashboard(interaction.guild, interaction.channel)

    @discord.ui.button(label="🔀", style=discord.ButtonStyle.secondary, custom_id="dash_shuffle")
    async def shuffle_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild.id
        queue = self.cog.get_queue(gid)
        if len(queue) < 2:
            return await interaction.response.send_message("列隊太短，無法打亂！", ephemeral=True)
        random.shuffle(queue)
        await interaction.response.send_message(f"🔀 已隨機打亂 {len(queue)} 首歌的順序！", ephemeral=True)
        await self.cog.update_dashboard(interaction.guild, interaction.channel)

    @discord.ui.button(label="📻", style=discord.ButtonStyle.success, custom_id="dash_radio")
    async def toggle_radio(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild.id
        await interaction.response.defer(ephemeral=True)  # Always defer first to avoid double-response
        if guild_id in self.cog.active_radios:
            self.cog.active_radios.pop(guild_id, None)
            self.cog.is_playing_radio.discard(guild_id)
            if interaction.guild.voice_client:
                interaction.guild.voice_client.stop()
            await interaction.followup.send("🚫 已關閉背景電台模式。", ephemeral=True)
        else:
            vc = interaction.guild.voice_client
            if not vc:
                if not interaction.user.voice:
                    return await interaction.followup.send("請先進入語音頻道！", ephemeral=True)
                vc = await interaction.user.voice.channel.connect()
            self.cog.active_radios[guild_id] = "lofi"
            await interaction.followup.send("✅ 為您自動駐紮 Lofi 電台！", ephemeral=True)

            class FakeCtx:
                def __init__(self, bot, guild, channel, vc):
                    self.bot = bot
                    self.guild = guild
                    self.channel = channel
                    self.voice_client = vc

                async def send(self, *args, **kwargs):
                    # Mock send: logs instead of sending message to avoid API calls for radio
                    log.info(f"[Radio-FakeCtx] Suppression: {args} {kwargs}")
                    return None

                async def defer(self, *args, **kwargs):
                    return None

            ctx = FakeCtx(self.cog.bot, interaction.guild, interaction.channel, vc)
            if not vc.is_playing() and not vc.is_paused() and not self.cog.get_queue(guild_id):
                self.cog.bot.loop.create_task(self.cog.play_next(ctx))
        await self.cog.update_dashboard(interaction.guild, interaction.channel)


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
        self.active_radios = {}
        self.is_playing_radio = set()
        self.dashboards = {} # {guild_id: {'channel': TextChannel, 'message': Message}}
        self.last_dj_msg = {} # {guild_id: str}
        # Loop mode: 0=off, 1=single, 2=queue
        self.loop_mode = {} # {guild_id: int}
        # Volume: 0.0-1.0 per guild
        self.volumes = {} # {guild_id: float}
        # Song start time for progress bar
        self.song_start_time = {} # {guild_id: float}
        self.dash_cooldown = {} # {guild_id: float}
        
        # SQLite Database Integration for Ranking System
        self._init_db()

    def _init_db(self):
        os.makedirs('data', exist_ok=True)
        import shutil
        if os.path.exists('music_rank.db') and not os.path.exists('data/music_rank.db'):
            try:
                shutil.move('music_rank.db', 'data/music_rank.db')
                log.info("Migrated music_rank.db to data folder")
            except Exception as e:
                log.error(f"Failed to migrate db: {e}")

        try:
            self.conn = sqlite3.connect('data/music_rank.db', check_same_thread=False)
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

    def _build_progress_bar(self, guild_id: int, duration) -> str:
        """Build a ██████░░░░ style progress bar."""
        if not duration:
            return ""
        try:
            elapsed = asyncio.get_event_loop().time() - self.song_start_time.get(guild_id, 0)
            elapsed = min(elapsed, duration)
            ratio = elapsed / duration
            filled = int(ratio * 12)
            bar = '█' * filled + '░' * (12 - filled)
            def fmt(s):
                s = int(s)
                return f"{s//60}:{s%60:02d}"
            return f"`{bar}` {fmt(elapsed)} / {fmt(duration)}"
        except Exception:
            return ""

    async def update_dashboard(self, guild, channel=None, force_resend=False):
        dash_info = self.dashboards.get(guild.id)
        target_channel = channel if channel else (dash_info['channel'] if dash_info else None)
        if not target_channel: return
        
        queue = self.get_queue(guild.id)
        current = self.current_song.get(guild.id)
        is_radio = guild.id in self.is_playing_radio
        vc = guild.voice_client
        loop_mode = self.loop_mode.get(guild.id, LOOP_OFF)
        volume = int(self.volumes.get(guild.id, 0.5) * 100)
        
        embed = discord.Embed(title="🎧 DJ 蝦 派對儀表板 (Live)", color=0xFF69B4)
        
        if current:
            title_text = current.get('title', current['query'])
            if str(title_text).startswith('http'): title_text = "🔗 外部網址"
            dj_txt = self.last_dj_msg.get(guild.id, "")
            if dj_txt: embed.description = dj_txt
            progress = self._build_progress_bar(guild.id, current.get('duration'))
            now_val = f"**{title_text}**\n*(點播者: {current['requester_name']})*"
            if progress:
                now_val += f"\n{progress}"
            embed.add_field(name="🎵 正在播放", value=now_val, inline=False)
        elif is_radio:
            embed.description = ""
            embed.add_field(name="📻 24H 沉浸電台模式", value=f"**{self.active_radios.get(guild.id, 'Radio').upper()} Radio** 聯播中...", inline=False)
        else:
            embed.description = ""
            embed.add_field(name="💤 已結束播放", value="目前列隊空空如也，趕快點歌吧！", inline=False)
            
        up_next = ""
        for i, item in enumerate(queue[:3]):
            q_label = str(item['query']) if not str(item['query']).startswith('http') else "🔗 URL"
            up_next += f"`{i+1}.` {q_label[:40]}...\n"
        if len(queue) > 3: up_next += f"*(還有 {len(queue)-3} 首歌)*"
        
        if up_next: embed.add_field(name="⏳ 待播清單 (Up Next)", value=up_next, inline=False)
        
        status = "⏹️ 停止"
        if vc and vc.is_playing(): status = "▶️ 播放中"
        elif vc and vc.is_paused(): status = "⏸️ 暫停"
        if is_radio: status += " (📻電台)"
        
        embed.set_footer(text=f"狀態: {status} | 🔁 {LOOP_LABELS[loop_mode]} | 🔊 {volume}% | 這個面板會自動更新")
        view = DashboardView(self)
        
        try:
            if not force_resend and dash_info and dash_info.get('message'):
                await dash_info['message'].edit(embed=embed, view=view)
            else:
                if dash_info and dash_info.get('message'):
                    try: await dash_info['message'].delete()
                    except: pass
                msg = await target_channel.send(embed=embed, view=view)
                self.dashboards[guild.id] = {'channel': target_channel, 'message': msg}
        except Exception:
            msg = await target_channel.send(embed=embed, view=view)
            self.dashboards[guild.id] = {'channel': target_channel, 'message': msg}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        gid = message.guild.id
        if gid in self.dashboards:
            dash = self.dashboards[gid]
            if message.channel == dash['channel']:
                now = asyncio.get_event_loop().time()
                if now - self.dash_cooldown.get(gid, 0) > 5: # 5 second cooldown
                    self.dash_cooldown[gid] = now
                    await self.update_dashboard(message.guild, force_resend=True)

    async def get_dj_intro(self, song_title: str, requester: str, requester_id: int = None) -> str:
        api_key = get_user_api_key(requester_id) if requester_id else GLOBAL_OR_API_KEY
        
        prompt = (f"你現在是在 Discord 上的溫馨音樂廣播 DJ。即將播放的歌是『{song_title}』，點播者是『{requester}』。"
                  "請用10~30個繁體中文字說一句鼓勵或溫馨的話介紹這首歌，結尾加一個表情符號。不要加上任何其他的解釋或標題。")
        try:
            dj_msg = await call_openrouter([{"role": "user", "content": prompt}], api_key, max_tokens=60)
            return f"🎙️ **DJ:** 「*{dj_msg}*」\n🎵 **Now playing:** {song_title}"
        except Exception as e:
            log.error(f"OpenRouter error: {e}")
            return f"🎵 **Now playing:** {song_title}\n*(Requested by {requester})*"

    async def play_next(self, ctx, *, _retry: int = 0):
        queue = self.get_queue(ctx.guild.id)
        loop_mode = self.loop_mode.get(ctx.guild.id, LOOP_OFF)

        if len(queue) > 0 or (loop_mode == LOOP_SINGLE and self.current_song.get(ctx.guild.id)):
            # Single loop: re-add the current song to front without popping
            if loop_mode == LOOP_SINGLE and self.current_song.get(ctx.guild.id):
                item = self.current_song[ctx.guild.id].copy()
            else:
                item = queue.pop(0)
                # Queue loop: push to back
                if loop_mode == LOOP_QUEUE:
                    queue.append(item)

                if self.current_song.get(ctx.guild.id) is not None:
                    self.get_history(ctx.guild.id).append(self.current_song[ctx.guild.id])

            self.current_song[ctx.guild.id] = item

            try:
                player = await YTDLSource.from_query(item['query'], stream=True)
                asyncio.create_task(
                    asyncio.to_thread(self.record_play, ctx.guild.id, item['requester_id'], item['requester_name'], item['query'], player.title)
                )

                # Set volume
                player.volume = self.volumes.get(ctx.guild.id, 0.5)

                # Update current song cache with resolved title
                self.current_song[ctx.guild.id]['title'] = player.title
                self.current_song[ctx.guild.id]['duration'] = player.data.get('duration')
                self.song_start_time[ctx.guild.id] = asyncio.get_event_loop().time()

                ctx.voice_client.play(
                    player,
                    after=lambda e: self.bot.loop.create_task(
                        self.play_next(ctx)
                    ) if e is None else log.error(f'Player error: {e}')
                )

                intro_msg = await self.get_dj_intro(player.title, item['requester_name'], item['requester_id'])
                self.last_dj_msg[ctx.guild.id] = intro_msg
                await self.update_dashboard(ctx.guild, ctx.channel, force_resend=True)
            except Exception as e:
                log.error(f"play_next error (retry {_retry}): {e}")
                if _retry < 3:
                    try: 
                        await ctx.send(f"⚠️ 無法播放 `{item['query']}`: {e}，嘗試下一首...", delete_after=5)
                    except Exception: pass
                    await asyncio.sleep(2)
                    await self.play_next(ctx, _retry=_retry + 1)
                else:
                    try:
                        await ctx.send("❌ 連續 3 首無法播放，已停止。", delete_after=5)
                    except Exception: pass
        else:
            self.current_song[ctx.guild.id] = None
            if ctx.guild.id in self.active_radios:
                radio_genre = self.active_radios[ctx.guild.id]
                radio_url = IDLE_RADIOS[radio_genre]
                self.is_playing_radio.add(ctx.guild.id)
                try:
                    player = await YTDLSource.from_query(radio_url, stream=True)
                    ctx.voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.play_next(ctx)) if e is None else log.error(f'Radio error: {e}'))
                    self.last_dj_msg[ctx.guild.id] = ""
                    await self.update_dashboard(ctx.guild, ctx.channel, force_resend=True)
                except Exception as e:
                    await ctx.send(f"❌ 無法連線至直播源。", delete_after=5)
                    self.active_radios.pop(ctx.guild.id, None)
                    self.is_playing_radio.discard(ctx.guild.id)
            else:
                self.last_dj_msg[ctx.guild.id] = ""
                await self.update_dashboard(ctx.guild, ctx.channel, force_resend=True)

    @commands.command(name='radio', help='Toggle 24/7 background radio. Options: lofi, jazz, synth, off')
    async def radio(self, ctx, genre: str = None):
        valid = list(IDLE_RADIOS.keys())
        if not genre or genre.lower() not in valid and genre.lower() != 'off':
            return await ctx.send(f"設定錯誤。\n使用方式：`F!radio [類型]`\n目前支援頻道：`{', '.join(valid)}` 或輸入 `off` 關閉。")
            
        genre = genre.lower()
        if genre == 'off':
            if ctx.guild.id in self.active_radios:
                del self.active_radios[ctx.guild.id]
                if ctx.guild.id in self.is_playing_radio:
                    self.is_playing_radio.discard(ctx.guild.id)
                    if ctx.voice_client: ctx.voice_client.stop()
                await ctx.send("🚫 已關閉 24H 沉浸模式。")
            else:
                await ctx.send("目前沒有開啟背景音樂。")
        else:
            self.active_radios[ctx.guild.id] = genre
            await ctx.send(f"✅ 已設定背景廣播頻道為：**{genre.upper()}**\n*(派對結束空檔時將會為您徹夜聯播！)*")
            if ctx.voice_client:
                if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused() and len(self.get_queue(ctx.guild.id)) == 0:
                    await self.play_next(ctx)
                elif ctx.guild.id in self.is_playing_radio:
                    self.is_playing_radio.discard(ctx.guild.id)
                    ctx.voice_client.stop()
            else:
                if ctx.message.author.voice:
                    await ctx.message.author.voice.channel.connect()
                    if len(self.get_queue(ctx.guild.id)) == 0:
                        await self.play_next(ctx)

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
                data = await asyncio.to_thread(ytdl_search.extract_info, search_query, **{'download': False})
                entries = data.get('entries', [])
                if not entries:
                    return await msg.edit(content="❌ No results found on YouTube.")
                    
                options_text = "**選擇一首歌（30秒內回覆數字 1-5）：**\n"
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
        elif ctx.guild.id in self.is_playing_radio:
            self.is_playing_radio.discard(ctx.guild.id)
            ctx.voice_client.stop() # Seamless Radio Interrupt
            await self.update_dashboard(ctx.guild, ctx.channel)
        elif len(queries) == 1:
            title_text = queries[0]
            if str(title_text).startswith('http'):
                title_text = "Requested Link" 
            await ctx.send(f"✅ 已加入列隊: **{title_text}**", delete_after=3)
            await self.update_dashboard(ctx.guild, ctx.channel)
        else:
            await ctx.send(f"✅ 成功加入 {len(queries)} 首歌曲！", delete_after=3)
            await self.update_dashboard(ctx.guild, ctx.channel)


    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name='dj', help='Ask the AI DJ for a 1-song contextual recommendation')
    async def dj(self, ctx, *, prompt: str):
        prompt = prompt[:150] # Prevent giant malicious prompts
        if not ctx.message.author.voice: return await ctx.send("你必須先進入語音頻道！")
        
        msg = await ctx.send("🧠 DJ 正在為您精挑細選專屬音樂...")
        sys_prompt = ("你是一位溫馨可愛的音樂 DJ。根據使用者的情境，推薦 1 首最適合的歌。"
                      "嚴格只能回傳純 JSON 陣列，不要有任何 Markdown 或其他文字。"
                      "格式範例: [\"Artist - Song Name\"]")
        try:
            api_key = get_user_api_key(ctx.author.id)
            messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}]
            raw_text = await call_openrouter(messages, api_key, max_tokens=100)
            
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
            elif ctx.guild.id in self.is_playing_radio:
                self.is_playing_radio.discard(ctx.guild.id)
                ctx.voice_client.stop()
            
        except json.JSONDecodeError:
            await msg.edit(content="❌ AI DJ 不小心語無倫次了，請再試一次！")
        except Exception as e:
            await msg.edit(content=f"❌ 發生錯誤: {e}")

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name='chat', help='Chat with the AI DJ natively')
    async def chat(self, ctx, *, message: str):
        message = message[:150]
        async with ctx.typing():
            try:
                sys_prompt = "你是一個生動可愛、熱情充滿正能量的 Discord 音樂電台 DJ。負責用短短的幾句話，以繁體中文跟群組裡的朋友聊天。結尾加顏文字或 Emoji。"
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": message}
                ]
                api_key = get_user_api_key(ctx.author.id)
                reply = await call_openrouter(messages, api_key, max_tokens=200, temperature=0.8)
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
            choice_msg = await self.bot.wait_for('message', timeout=30.0, check=check)
            choice = int(choice_msg.content)
            if 1 <= choice <= len(queue[:display_limit]):
                removed_item = queue.pop(choice - 1)
                await ctx.send(f"🗑️ Removed item from queue: `{str(removed_item['query'])[:50]}`")
            else:
                await ctx.send("❌ Invalid number selection.")
        except asyncio.TimeoutError:
            await msg.edit(content="❌ 刪歌操作已超時 (30秒限制)。")
        finally:
            self.remove_locks.discard(ctx.guild.id)


    @commands.command(name='pause', help='Pauses the current song')
    async def pause(self, ctx):
        if ctx.guild.id in self.is_playing_radio:
            return await ctx.send("📻 背景廣播不支援暫停！請使用 `F!radio off` 關閉，或直接點歌。")
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
        if ctx.guild.id in self.is_playing_radio:
            return await ctx.send("📻 背景廣播無法被跳過！請使用 `F!radio off` 關閉，或直接點播歌曲讓系統自動中斷。")
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
        
        if ctx.guild.id in self.is_playing_radio:
            self.is_playing_radio.discard(ctx.guild.id)
            ctx.voice_client.stop()
        elif ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop() 
        else:
            await self.play_next(ctx)
            
        await ctx.send('⏮️ Going back to previous track.')

    @commands.command(name='volume', aliases=['vol'], help='設定音量 (1-100)，例如 F!volume 80')
    async def volume(self, ctx, vol: int):
        if not 1 <= vol <= 100:
            return await ctx.send("❌ 音量必須介於 1 到 100 之間！")
        self.volumes[ctx.guild.id] = vol / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = vol / 100
        await ctx.send(f"🔊 音量已設定為 **{vol}%**")
        await self.update_dashboard(ctx.guild, ctx.channel)

    @commands.command(name='loop', help='切換 Loop 模式：off → single → queue → off')
    async def loop(self, ctx):
        gid = ctx.guild.id
        current = self.loop_mode.get(gid, LOOP_OFF)
        next_mode = (current + 1) % 3
        self.loop_mode[gid] = next_mode
        await ctx.send(f"🔁 Loop 模式已切換為：**{LOOP_LABELS[next_mode]}**")
        await self.update_dashboard(ctx.guild, ctx.channel)

    @commands.command(name='shuffle', help='隨機打亂目前的播放列隊')
    async def shuffle(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if len(queue) < 2:
            return await ctx.send("❌ 列隊至少需要 2 首歌才能打亂！")
        random.shuffle(queue)
        await ctx.send(f"🔀 已隨機打亂 **{len(queue)}** 首歌的順序！")
        await self.update_dashboard(ctx.guild, ctx.channel)

    @commands.command(name='np', aliases=['nowplaying'], help='顯示目前正在播放的歌曲資訊')
    async def nowplaying(self, ctx):
        current = self.current_song.get(ctx.guild.id)
        is_radio = ctx.guild.id in self.is_playing_radio
        vc = ctx.voice_client

        if is_radio:
            genre = self.active_radios.get(ctx.guild.id, 'lofi').upper()
            return await ctx.send(f"📻 目前正在播放 **{genre} Radio** 24H 沉浸電台。")

        if not current:
            return await ctx.send("❌ 目前沒有正在播放的歌曲。")

        title = current.get('title', current['query'])
        if str(title).startswith('http'):
            title = "🔗 外部網址"

        loop_mode = self.loop_mode.get(ctx.guild.id, LOOP_OFF)
        volume = int(self.volumes.get(ctx.guild.id, 0.5) * 100)

        embed = discord.Embed(title="🎵 Now Playing", color=0xFF69B4)
        embed.add_field(name="歌曲", value=f"**{title}**", inline=False)
        embed.add_field(name="點播者", value=current['requester_name'], inline=True)
        embed.add_field(name="🔁 Loop", value=LOOP_LABELS[loop_mode], inline=True)
        embed.add_field(name="🔊 音量", value=f"{volume}%", inline=True)

        progress = self._build_progress_bar(ctx.guild.id, current.get('duration'))
        if progress:
            embed.add_field(name="進度", value=progress, inline=False)

        status = "▶️ 播放中" if vc and vc.is_playing() else "⏸️ 暫停中"
        embed.set_footer(text=f"狀態: {status}")
        await ctx.send(embed=embed)

    @commands.command(name='stop', help='Stops music and clears queue')
    async def stop(self, ctx):
        if ctx.voice_client:
            self.active_radios.pop(ctx.guild.id, None)
            self.is_playing_radio.discard(ctx.guild.id)
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
            elif ctx.voice_client and ctx.guild.id in self.is_playing_radio:
                self.is_playing_radio.discard(ctx.guild.id)
                ctx.voice_client.stop()
                
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
            if ctx.guild.id in self.is_playing_radio:
                self.is_playing_radio.discard(ctx.guild.id)
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
