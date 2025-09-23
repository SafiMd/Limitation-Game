# botapp/bot.py
import discord
from discord.ext import commands

from botapp import config
from botapp.game_manager import GameManager

# -------- Intents & Bot --------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
gm = GameManager()

# -------- Events --------
@bot.event
async def on_ready():
    guilds = ", ".join(g.name for g in bot.guilds)
    print(f"Logged in as {bot.user} | Guilds: {guilds}")

# -------- Commands --------
@bot.command(help="Create an Imitation Game lobby in this channel.")
async def create_game(ctx):
    await gm.create_lobby(ctx)

@bot.command(help="Join the current lobby.")
async def join(ctx):
    await gm.join(ctx, ctx.author)

@bot.command(help="Start the game (requires exactly two human players joined).")
async def start(ctx):
    await gm.start(ctx)

@bot.command(help="Ask a question in the game thread (judge only).")
async def ask(ctx, *, question: str):
    await gm.relay_question(ctx, question)

@bot.command(help="Judge makes their final guess: !who A or !who B")
async def who(ctx, guess: str):
    await gm.final_guess(ctx, guess)

@bot.command(help="End the current game immediately.")
async def end(ctx):
    await gm.end(ctx)

# Simple health check
@bot.command(help="Check if the bot is alive.")
async def ping(ctx):
    await ctx.send("pong")

# -------- Run --------
bot.run(config.DISCORD_BOT_TOKEN)
