import random
import asyncio
import discord
from typing import Optional

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
    Minimal game manager.
    TODO (YOU WRITE THIS):
      - Full startup sequence
      - Role randomization
      - Anonymization (Interrogator sees A/B only)
      - Fairness timing + length normalization
      - Q&A loop, Guess, Reveal, Logging
    """
    def __init__(self):
        self.games: dict[int, GameState] = {}  # key: channel.id

    def get_game(self, guild: discord.Guild, channel: discord.TextChannel) -> GameState:
        if channel.id not in self.games:
            self.games[channel.id] = GameState(guild, channel)
        return self.games[channel.id]

    async def create_lobby(self, ctx):
        game = self.get_game(ctx.guild, ctx.channel)
        if game.running:
            await ctx.send("A game is already running here.")
            return
        await ctx.send(
            "**Imitation Game lobby created!**\n"
            "Two humans: run `!join` to join.\n"
            "When two humans have joined, run `!start`."
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

        # TODO (YOU WRITE THIS): Choose interrogator vs human contestant; randomize AI as A or B.
        game.interrogator, game.human_contestant = random.sample(game.humans, 2)
        game.ai_is_A = random.choice([True, False])

        # Create a thread for the interrogation
        game.thread = await ctx.channel.create_thread(name="imitation-game", auto_archive_duration=60)
        game.running = True

        # DM role info (anonymity)
        try:
            await game.interrogator.create_dm()
            await game.human_contestant.create_dm()
            await game.interrogator.dm_channel.send(
                "You are the **Interrogator**. Ask questions in the game thread. "
                "Contestants are **A** and **B**."
            )
            # Human contestant: tell them they're contestant A or B?
            # For anonymity, you can DM them instructions to reply via DM to the bot,
            # using a command like `!answer <A|B> <text>` depending on their assigned label.
            await game.human_contestant.dm_channel.send(
                "You are a **Contestant**. The bot will query you in DM. Answer promptly and naturally."
            )
        except Exception as e:
            await ctx.send(f"Could not DM players: {e}")

        await game.thread.send(
            f"**Game started!** {game.interrogator.mention} is Interrogator.\n"
            "Ask your first question here (one line). The bot will collect answers from Contestants A and B."
        )

    async def relay_question(self, ctx, question: str):
        """
        TODO (YOU WRITE THIS):
          - When interrogator posts a question in the thread,
            the bot should:
              1) DM the human contestant to get an answer.
              2) Query the AI for an answer.
              3) Post both answers into the thread as 'A:' and 'B:' in randomized order.
              4) Apply response delay jitter for fairness.
        """
        pass

    async def end(self, ctx):
        game = self.get_game(ctx.guild, ctx.channel)
        if not game.running:
            await ctx.send("No game in progress.")
            return
        # TODO (YOU WRITE THIS): Handle final guess, reveal, results logging
        game.running = False
        await ctx.send("Game ended. Thanks for playing!")
        if game.thread:
            try:
                await game.thread.edit(archived=True, locked=True)
            except Exception:
                pass
        game.reset()
