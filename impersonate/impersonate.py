from redbot.core import commands
from redbot.core import Config
import discord
import os
from io import BytesIO
import time
from datetime import datetime, timedelta
import functools
import asyncio
# import matplotlib
# matplotlib.use("agg")
# import matplotlib.pyplot as plt
# plt.switch_backend("agg")
import markovify

class Impersonate(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 573147218420570)

        self.config.register_user(
            markov=None,
            markov_date=None,
            markov_size=None
        )

    async def save_model(self, model, user, text_size):
        await self.config.user(user).markov_date.set(
                datetime.timestamp(datetime.now())
            )
        await self.config.user(user).markov.set(
                model.to_json()
            )
        await self.config.user(user).markov_size.set(
                text_size
            )

    async def generate_new_model(self, ctx, user, m, limit=None, date=None):
        channels = ctx.guild.text_channels
            
        history = []
        for c in channels:
            async for msg in c.history(limit=limit, after=date):
                if msg.author == user:
                    history.append(msg.content)

        if len(history) == 0:
            await m.edit(content=f"No new messages...")
            return None, 0
        
        await m.edit(content=f"Generating model with {len(history)} messages from {user}...")
        task = functools.partial(markovify.Text, history)
        task = self.bot.loop.run_in_executor(None, task)
        try:
            model = await asyncio.wait_for(task, timeout=600)
        except asyncio.TimeoutError:
            await m.edit(content=f"Model generation timed out")
            return None, 0
        await m.edit(content=f"Model generated with {len(history)} messages from {user}")
        return model, len(history)

        

    @commands.guild_only()
    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def impersonate(self, ctx, user: discord.User = None, limit=None, force_redo: bool = False, sentences=1, tries=200, max_overlap_ratio=0.8, max_overlap_total=20):
        if user is None:
            user = ctx.message.author
        if sentences <= 0 or sentences > 5 or \
        tries <= 0 or tries > 1000 or \
        max_overlap_ratio <= 0 or max_overlap_ratio >= 1 or \
        max_overlap_total <= 0 or max_overlap_total >= 100:
            return
        
        date = await self.config.user(ctx.author).markov_date()
        if force_redo or date is None:
            m = await ctx.send(f"Generating model for {user}...")
            # Make new model
            model, size = await self.generate_new_model(ctx, user, m, limit=limit)
            await self.save_model(model, user, size)

        elif datetime.now() - datetime.fromtimestamp(date) > timedelta(hours=24):
            # Update model
            m = await ctx.send(f"Updating model for {user}...")
            new_model, new_size = await self.generate_new_model(ctx, user, m, datetime.fromtimestamp(date), limit=limit)
            old_model = markovify.Text.from_json(await self.config.user(ctx.author).markov())
            old_size = await self.config.user(ctx.author).markov_size()
            if new_size == 0:
                model = old_model
            else:
                model = markovify.combine([ old_model, new_model ], [ int(old_size), int(new_size) ])
                await self.save_model(model, user, old_size + new_size)
                await m.edit(content=f"Model updated and saved for {user}")

        else:
            # Reuse old model
            m = await ctx.send(f"Reusing model for {user}")
            model = markovify.Text.from_json(await self.config.user(ctx.author).markov())

        s = f"{user}: "
        for i in range(sentences):
            pred = model.make_sentence(tries=tries, max_overlap_ratio=max_overlap_ratio, max_overlap_total=max_overlap_total)
            if pred is None:
                pred = "Generation failed, go bonk Jen"
            s = f"{s}. {pred}"
        await ctx.send(s)

        

      