import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("MTQxNTQ0NzYzODQ3OTk5OTAzNg.GI1N55.8VFnJhhaukD8TkVTDjkVo-G6styBZvw1JGDo04")
OPENAI_API_KEY = os.getenv("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")
DISCORD_GUILD_ID = os.getenv("1415445649587179603")  # optional

if not DISCORD_BOT_TOKEN:
    raise RuntimeError("Missing DISCORD_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")
