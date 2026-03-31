import asyncio
import re
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
                    play_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
        except Exception as e:
            log.error(f"DB Error: Failed to initialize SQLite: {e}")

    def record_play(self, guild_id, user_id, user_name):
        try:
            self.cursor.execute('''
                INSERT INTO play_history (guild_id, user_id, user_name) 
                VALUES (?, ?, ?)
            ''', (guild_id, user_id, user_name))
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

    async def play_next(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if len(queue) > 0:
            item = queue.pop(0)
            
            if ctx.guild.id in self.current_song and self.current_song[ctx.guild.id] is not None:
                self.get_history(ctx.guild.id).append(self.current_song[ctx.guild.id])
                
            self.current_song[ctx.guild.id] = item
            
            # Write to database (STRICT MODE: Only count score when song actually starts playing)
            self.bot.loop.run_in_executor(None, self.record_play, ctx.guild.id, item['requester_id'], item['requester_name'])
            
            try:
                player = await YTDLSource.from_query(item['query'], loop=self.bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.play_next(ctx)) if e is None else print(f'Player error: {e}'))
                await ctx.send(f"🎵 **Now playing:** {player.title}\n*(Requested by {item['requester_name']})*")
            except Exception as e:
                await ctx.send(f"An error occurred while trying to play `{item['query']}`: {e}")
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


    @commands.command(name='remove', help='Remove a specific track from the queue interactively')
    async def remove(self, ctx):
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
            await msg.edit(content="❌ Remove command timed out.")


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

async def setup(bot):
    await bot.add_cog(Music(bot))
