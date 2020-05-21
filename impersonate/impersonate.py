from redbot.core import commands, checks, Config
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
        self.bot_prefixes = ['&', '-', '.', '#', '\'']
        self.config.register_user(
            markov=None,
            markov_date=None,
            markov_size=None
        )

        self.config.register_guild(
            tries=200, 
            max_overlap_ratio=0.8, 
            max_overlap_total=20,
            message_limit=None,
            ignore_channels=[]
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
        ignore_channels = await self.config.guild(ctx.message.guild).ignore_channels()

        history = []
        for c in channels:
            if c.id not in ignore_channels:
                try:
                    async for msg in c.history(limit=limit, after=date):
                        if msg.author == user and msg.clean_content[0] not in self.bot_prefixes:
                            history.append(msg.clean_content)
                except:
                    pass

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
    @commands.group()
    async def impersonate(self, cxx):
        pass

    @commands.guild_only()
    @impersonate.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def generate(self, ctx, user: discord.User = None, force_redo: bool = False, sentences: int = 1):
        if not ctx.invoked_subcommand is None:
            return
        if user is None:
            user = ctx.message.author
        if sentences <= 0 or sentences >= 10:
            await ctx.send(f"Invalid num of sentences")
            return
        
        cfg = self.config.guild(ctx.message.guild)
        limit = await cfg.message_limit()
        
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


        tries = await cfg.tries() 
        max_overlap_ratio = await cfg.max_overlap_ratio() 
        max_overlap_total = await cfg.max_overlap_total()
        
        preds = []
        for i in range(sentences):
            pred = model.make_sentence(tries=tries, max_overlap_ratio=max_overlap_ratio, max_overlap_total=max_overlap_total)
            if pred is None:
                pred = "Generation failed, go bonk Jen"
            preds.append(pred)
        s = f"{user}: {'. '.join(preds)}." 

        await ctx.send(s)

    @commands.guild_only()
    @checks.admin()
    @impersonate.command()
    async def ignorechannel(self, ctx, channel: discord.TextChannel):
        ignore_channels = await self.config.guild(ctx.message.guild).ignore_channels()
        if channel.id in ignore_channels:
            ignore_channels.remove(channel.id)
            await self.config.guild(ctx.message.guild).ignore_channels.set(
                ignore_channels
            )
            await ctx.send(f"Channel {channel} removed from ignored list")
        else:
            ignore_channels.append(channel.id)
            await self.config.guild(ctx.message.guild).ignore_channels.set(
                ignore_channels
            )
            await ctx.send(f"Channel {channel} added to ignored list")

    @commands.guild_only()
    @checks.admin()
    @impersonate.command()
    async def setmessagelimit(self, ctx, limit: int = None):
        await self.config.guild(ctx.message.guild).message_limit.set(
            limit
        )
        await ctx.send(f"Message limit set to {limit}")
       