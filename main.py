import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN', '').strip()

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix=commands.when_mentioned_or('F!'),
            intents=intents,
            help_command=commands.DefaultHelpCommand(),
            case_insensitive=True
        )

    async def setup_hook(self):
        # Load cogs
        initial_extensions = ['cogs.music', 'cogs.sticker']
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f'Loaded extension: {ext}')
            except Exception as e:
                logger.error(f'Failed to load extension {ext}: {e}')

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('------')

async def main():
    if not TOKEN or TOKEN == "your_discord_bot_token_here":
        logger.error("Please configure your .env file with a valid DISCORD_TOKEN.")
        return

    bot = MusicBot()
    async with bot:
        await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")
