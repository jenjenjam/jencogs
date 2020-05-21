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
        self.config = Config.get_conf(self, 573147218420573)
        self.bot_prefixes = ['&', '-', '.', '#', '\'']
        self.config.register_user(
            markov=None,
            markov_date=None,
            markov_size=None
        )

        self.config.register_guild(
            tries=200, 
            max_overlap_ratio=0.7, 
            max_overlap_total=20,
            history={}
        )

        self.config.register_channel(
            channel_download_date=None
        )

    async def save_model(self, model, user, text_size):
        await self.config.user(user).markov.set(
                model.to_json()
            )
        await self.config.user(user).markov_size.set(
                text_size
            )
        await self.config.user(user).markov_date.set(
                datetime.timestamp(datetime.now())
            )

    async def generate_new_model(self, ctx, user, m):
        channels = ctx.guild.text_channels
        cfg = self.config.guild(ctx.message.guild)
        history = await cfg.history()
        print(user.id)
        print(list(history.keys()))
        if str(user.id) not in list(history.keys()):
            await m.edit(content=f"No data for this user")
            return None, 0

        history = history[ str(user.id)]
        if len(history) == 0:
            await m.edit(content=f"No messages...")
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
    @checks.admin()
    @impersonate.command()
    async def getdata(self, ctx, channel: discord.TextChannel = None, limit: int = 5000):
        cfg = self.config.guild(ctx.message.guild)
        history = await cfg.history()

        if channel is None:
            channel = ctx.message.channel

        from_date = await self.config.channel(channel).channel_download_date()
        if not from_date is None:
            m = await ctx.send(f"Attempting to load up to {limit} messages from after date {from_date} in channel {channel}")
            from_date = datetime.fromtimestamp(from_date)
        else:
            m = await ctx.send(f"Attempting to load up to {limit} messages in channel {channel}")

        msg_counter = 0
        async for msg in channel.history(limit=limit, after=from_date):
            if not msg.author.bot and len(msg.clean_content) > 0 and msg.clean_content[0] not in self.bot_prefixes:
                if str(msg.author.id) not in list(history.keys()):
                    history[str(msg.author.id)] = []
                history[str(msg.author.id)].append(msg.clean_content)
                msg_counter += 1
        
        print(history)
        await cfg.history.set(
                history
            )
        await  self.config.channel(channel).channel_download_date.set(
                datetime.timestamp(datetime.now())
            )
        await ctx.send(f"Saved {msg_counter} messages")

    @commands.guild_only()
    @checks.admin()
    @impersonate.command()
    async def cleardata(self, ctx):
        await self.config.guild(ctx.message.guild).history.set(
                {}
            )
        await self.config.clear_all_channels()
        await ctx.send(f"Cleared all data")

    @commands.guild_only()
    @impersonate.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def generate(self, ctx, user: discord.User = None, force_redo: bool = False, sentences: int = 1):
        if user is None:
            user = ctx.message.author
        if sentences <= 0 or sentences >= 10:
            await ctx.send(f"Invalid num of sentences")
            return
        
        cfg = self.config.guild(ctx.message.guild)
        
        date = await self.config.user(user).markov_date()
        if force_redo or date is None:
            m = await ctx.send(f"Generating model for {user}...")
            # Make new model
            model, size = await self.generate_new_model(ctx, user, m)
            if size == 0:
                return
            await self.save_model(model, user, size)

        # elif datetime.now() - datetime.fromtimestamp(date) > timedelta(hours=24):
        #     # Update model
        #     m = await ctx.send(f"Updating model for {user}...")
        #     new_model, new_size = await self.generate_new_model(ctx, user, m, datetime.fromtimestamp(date), limit=limit)
        #     old_model = markovify.Text.from_json(await self.config.user(user).markov())
        #     old_size = await self.config.user(user).markov_size()
        #     if new_size == 0:
        #         model = old_model
        #     else:
        #         model = markovify.combine([ old_model, new_model ], [ int(old_size), int(new_size) ])
        #         await self.save_model(model, user, old_size + new_size)
        #         await m.edit(content=f"Model updated and saved for {user}")

        else:
            # Reuse old model
            m = await ctx.send(f"Reusing model for {user}")
            model = markovify.Text.from_json(await self.config.user(user).markov())


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
       