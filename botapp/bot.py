import discord
from discord.ext import commands
import discord
from discord.ext import commands
from botapp import config
from botapp.game_manager import GameManager

from botapp.game_manager import GameManager

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
gm = GameManager()

@bot.event
async def on_ready():
    guilds = ", ".join(g.name for g in bot.guilds)
    print(f"Logged in as {bot.user} | Guilds: {guilds}")

@bot.command(help="Create an Imitation Game lobby in this channel.")
async def create_game(ctx):
    await gm.create_lobby(ctx)

@bot.command(help="Join the current lobby.")
async def join(ctx):
    await gm.join(ctx, ctx.author)

@bot.command(help="Start the game (requires exactly two human players joined).")
async def start(ctx):
    await gm.start(ctx)

@bot.command(help="End the current game.")
async def end(ctx):
    await gm.end(ctx)

# Simple health check
@bot.command()
async def ping(ctx):
    await ctx.send("pong")

bot.run(config.DISCORD_BOT_TOKEN)

