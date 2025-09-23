# botapp/game_manager.py
from __future__ import annotations

import asyncio
import random
import re
from typing import Optional, Dict

import discord

from botapp import ai_client


# -----------------------------
# Utilities
# -----------------------------

MAX_HUMAN_WAIT_S = 90          # how long we wait for the human contestant's DM
MAX_AI_TOKENS_TEXT = 1200      # rough character cap for AI text (extra safety)
MIN_TYPING_DELAY = 0.4         # s
PER_CHAR_DELAY = 0.008         # s per char (very small)
JITTER_DELAY = (0.15, 0.6)     # extra human-like jitter for fairness


def normalize_answer(text: str) -> str:
    """Keep answers short and conversational; trim excessive whitespace/length."""
    t = re.sub(r"\s+", " ", text.strip())
    if len(t) > MAX_AI_TOKENS_TEXT:
        t = t[:MAX_AI_TOKENS_TEXT].rsplit(" ", 1)[0] + "…"
    return t


async def human_like_send(channel: discord.abc.Messageable, label: str, text: str):
    """Send with a short typing delay so timing doesn't give away the AI."""
    text = normalize_answer(text)
    # pretend to type
    delay = MIN_TYPING_DELAY + PER_CHAR_DELAY * min(len(text), 400)
    delay += random.uniform(*JITTER_DELAY)
    try:
        async with channel.typing():
            await asyncio.sleep(delay)
    except Exception:
        # Some channel types don't support typing()—fallback to a normal delay
        await asyncio.sleep(delay)
    await channel.send(f"**{label}:** {text}")


# -----------------------------
# Game state
# -----------------------------

class GameState:
    def __init__(self, guild: discord.Guild, channel: discord.TextChannel):
        self.guild = guild
        self.channel = channel
        self.humans: list[discord.Member] = []
        self.interrogator: Optional[discord.Member] = None
        self.human_contestant: Optional[discord.Member] = None
        self.ai_is_A: Optional[bool] = None
        self.thread: Optional[discord.Thread] = None
        self.running = False
        self.rounds_done = 0
        self.max_rounds = 6  # tweak

    def reset(self):
        self.__init__(self.guild, self.channel)


class GameManager:
    """
    Full Imitation Game manager:
      - Lobby (create_lobby, join)
      - Start (role randomization, DM role info, create thread)
      - Q&A loop (relay_question): judge asks; bot collects human DM + AI answer
      - Guess (final_guess): judge declares X/Y; bot reveals, logs, ends
      - End (graceful cleanup)
    """
    def __init__(self):
        self.games: Dict[int, GameState] = {}  # key: channel.id (the parent text channel)

    # --------------- lifecycle helpers

    def get_game(self, guild: discord.Guild, channel: discord.TextChannel) -> GameState:
        if channel.id not in self.games:
            self.games[channel.id] = GameState(guild, channel)
        return self.games[channel.id]

    async def _dm(self, member: discord.Member, content: str):
        try:
            dm = await member.create_dm()
            await dm.send(content)
        except discord.Forbidden:
            # Surface this to the game thread instead of failing
            return False
        return True

    # --------------- commands called from your bot cog/command handlers

    async def create_lobby(self, ctx):
        game = self.get_game(ctx.guild, ctx.channel)
        if game.running:
            await ctx.send("A game is already running here.")
            return
        game.reset()
        await ctx.send(
            "**Imitation Game lobby created!**\n"
            "Two humans: run `!join` to join.\n"
            "When two humans have joined, run `!start` to assign roles and create the thread."
        )

    async def join(self, ctx, member: discord.Member):
        game = self.get_game(ctx.guild, ctx.channel)
        if game.running:
            await ctx.send("Game already started; can't join.")
            return
        if member in game.humans:
            await ctx.send("You already joined.")
            return
        if len(game.humans) >= 2:
            await ctx.send("Lobby full. (Need exactly two humans.)")
            return
        game.humans.append(member)
        await ctx.send(f"{member.mention} joined. ({len(game.humans)}/2)")

    async def start(self, ctx):
        game = self.get_game(ctx.guild, ctx.channel)
        if game.running:
            await ctx.send("Game already running.")
            return
        if len(game.humans) != 2:
            await ctx.send("Need exactly two humans to start.")
            return

        # Randomize interrogator vs human contestant
        game.interrogator, game.human_contestant = random.sample(game.humans, 2)
        # Randomize whether A or B is AI
        game.ai_is_A = random.choice([True, False])

        # Create a thread for the interrogation
        game.thread = await ctx.channel.create_thread(
            name=f"imitation-game-{game.interrogator.display_name}",
            auto_archive_duration=60
        )
        game.running = True
        game.rounds_done = 0

        # DM role info with anonymity instructions
        judge_ok = await self._dm(
            game.interrogator,
            "You are the **Interrogator**. Ask questions *in the game thread*.\n"
            "Contestants appear only as **A** and **B**.\n"
            "End the game with `!who A` or `!who B` when you’re ready to guess."
        )
        human_label = "B" if game.ai_is_A else "A"
        human_ok = await self._dm(
            game.human_contestant,
            "You are the **Human Contestant**.\n"
            f"Your label is **{human_label}**.\n"
            "I’ll DM you each question—reply to me with your answer (plain text). "
            "Keep it short and natural; I’ll forward it anonymously into the thread."
        )

        if not (judge_ok and human_ok):
            await ctx.send("⚠️ I couldn't DM one or both players. Make sure DMs from server members are enabled.")

        await game.thread.send(
            f"**Game started!** {game.interrogator.mention} is Interrogator.\n\n"
            "Ask your first question here with `!ask <question>`.\n"
            "I will collect answers from **A** and **B** and post them with fair timing."
        )

    async def relay_question(self, ctx, question: str):
        """
        When the interrogator posts a question in the thread, collect:
          1) Human contestant's DM.
          2) AI answer from OpenAI.
        Then post both as 'A:' and 'B:' (A/B mapping fixed for the whole game).
        """
        game = self.get_game(ctx.guild, ctx.channel)
        # must be running, in its thread, and asked by the interrogator
        if not (game.running and game.thread and isinstance(ctx.channel, discord.Thread)):
            return await ctx.send("No active game in this thread.")
        if ctx.channel.id != game.thread.id:
            return await ctx.send("Please ask inside the game thread.")
        if ctx.author.id != game.interrogator.id:
            return await ctx.send("Only the interrogator can ask questions.")

        game.rounds_done += 1
        if game.rounds_done > game.max_rounds:
            return await ctx.send("Max rounds reached. Make your guess with `!who A` or `!who B`.")

        await game.thread.send(f"**Q{game.rounds_done} (Judge):** {question}")

        # --- 1) kick off AI answer
        async def get_ai() -> str:
            try:
                return await ai_client.ai_reply(question)
            except Exception:
                return "…(no answer)"

        # --- 2) prompt human in DM and wait for their DM
        async def get_human() -> str:
            try:
                dm = await game.human_contestant.create_dm()
                await dm.send(f"**Q{game.rounds_done}:** {question}")
            except discord.Forbidden:
                return "(Human DM unavailable)"

            def check(m: discord.Message):
                return (
                    m.author.id == game.human_contestant.id
                    and m.channel == dm
                    and m.content
                )

            try:
                msg: discord.Message = await ctx.bot.wait_for(
                    "message", check=check, timeout=MAX_HUMAN_WAIT_S
                )
                return msg.content.strip()
            except asyncio.TimeoutError:
                return "(no human answer)"

        ai_task = asyncio.create_task(get_ai())
        human_task = asyncio.create_task(get_human())
        human_text, ai_text = await asyncio.gather(human_task, ai_task)

        # Map to A/B (fixed mapping across the game)
        text_A = ai_text if game.ai_is_A else human_text
        text_B = human_text if game.ai_is_A else ai_text

        # Post with short typing delays for fairness
        await human_like_send(game.thread, "A", text_A)
        await human_like_send(game.thread, "B", text_B)

        if game.rounds_done >= game.max_rounds:
            await game.thread.send(
                f"Reached the round limit (**{game.max_rounds}**). "
                "Judge, make your final guess with `!who A` or `!who B`."
            )

    async def final_guess(self, ctx, guess_label: str):
        """
        Judge declares 'A' or 'B' as the human: !who A  or  !who B
        """
        game = self.get_game(ctx.guild, ctx.channel)
        if not (game.running and game.thread and isinstance(ctx.channel, discord.Thread)):
            return await ctx.send("No active game in this thread.")
        if ctx.channel.id != game.thread.id:
            return await ctx.send("Use this inside the game thread.")
        if ctx.author.id != game.interrogator.id:
            return await ctx.send("Only the interrogator can make the final guess.")

        g = guess_label.strip().upper()
        if g not in {"A", "B"}:
            return await ctx.send("Guess must be `A` or `B`.")

        human_label = "B" if game.ai_is_A else "A"
        ai_label = "A" if game.ai_is_A else "B"
        correct = (g == human_label)

        await game.thread.send(
            f"**Reveal:** Human was **{human_label}**, AI was **{ai_label}**.\n"
            f"Result: {'✅ Correct' if correct else '❌ Incorrect'}."
        )

        await self.end(ctx, announce=False)

    async def end(self, ctx, announce: bool = True):
        game = self.get_game(ctx.guild, ctx.channel)
        if not game.running:
            if announce:
                await ctx.send("No game in progress.")
            return

        game.running = False
        if announce:
            await ctx.send("Game ended. Thanks for playing!")

        if game.thread:
            try:
                await game.thread.edit(archived=True, locked=True)
            except Exception:
                pass

        # Reset state for this parent channel
        game.reset()
