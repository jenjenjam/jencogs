from redbot.core import commands, checks, Config
from redbot.core.utils import AsyncIter, menus
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.data_manager import cog_data_path
import discord
from discord.ext import tasks
from typing import Optional, Union
import time
import datetime
import pytz
import apsw
import asyncio
import concurrent.futures
import functools
import random

AUTOUPDATE_CHECK_INTERVAL = 60
TIME_BUCKET = 5*60
EXPIRY_TIME = 7*24*60*60

class UserStonks(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.ignore_cache = {}
        self.config = Config.get_conf(self, identifier=328598315917591)
        self.config.register_guild(
            enableGuild = True,
            disabledChannels = [],
            disabledPrefixes = [],
            autoLeaderboards=[]
        )
        self._connection = apsw.Connection(str(cog_data_path(self) / 'userstats.db'))
        self.cursor = self._connection.cursor()
        self.cursor.execute('PRAGMA journal_mode = wal;')
        self.cursor.execute('PRAGMA read_uncommitted = 1;')
        self.cursor.execute(
            'CREATE TABLE IF NOT EXISTS member_stats ('
            'guild_id INTEGER NOT NULL,'
            'user_id INTEGER NOT NULL,'
            'time INTEGER NOT NULL,'
            'quantity INTEGER DEFAULT 1,'
            'PRIMARY KEY (guild_id, user_id, time)'
            ');'
        )
        self._executor = concurrent.futures.ThreadPoolExecutor(1)
        self.printer.start()

    @tasks.loop(seconds=AUTOUPDATE_CHECK_INTERVAL)
    async def printer(self):
        for guild in self.bot.guilds:
            leaderboards = await self.config.guild(guild).autoLeaderboards()
            now = datetime.datetime.timestamp(datetime.datetime.now())
            leaderboards = list(filter(lambda b: now - b["next_update"] < EXPIRY_TIME, leaderboards))
            for i, b in enumerate(leaderboards):
                try:
                    now = datetime.datetime.timestamp(datetime.datetime.now())
                    if now >= b["next_update"]:
                        channel = guild.get_channel(b["channelId"])
                        if channel is None:
                            continue
                        msg = await channel.fetch_message(b["messageId"])
                        if msg is None:
                            continue

                        new_embed = await self.get_leaderboard(guild, b["length"], b["time_period"], b["has_comparison"])
                        if new_embed is None:
                            continue
                        await msg.edit(embed=new_embed)
                        b["next_update"] = now + b["update_period"]
                        leaderboards[i] = b
                except:
                    # print(sys.exc_info()[0])
                    pass
            await self.config.guild(guild).autoLeaderboards.set(leaderboards)

    @printer.before_loop
    async def before_printer(self):
        await self.bot.wait_until_ready()


    async def get_comp_leaderboard(
        self,
        guild,
        amount,
        time_period
    ):
       

        time_end =  int(datetime.datetime.now(datetime.timezone.utc).timestamp() / TIME_BUCKET)
        time_start =  int((datetime.datetime.now(datetime.timezone.utc).timestamp() - time_period) / TIME_BUCKET)
        time_prev_start =  int((datetime.datetime.now(datetime.timezone.utc).timestamp() - 2*time_period) / TIME_BUCKET)

        result = self.cursor.execute(
            'WITH now AS ('
            'SELECT user_id, sum(quantity) AS total FROM member_stats '
            'WHERE guild_id = ? AND time >= ? AND time <= ? '
            'GROUP BY user_id '
            'ORDER BY total DESC '
            'LIMIT ?), '
            'prev AS ('
            'SELECT *, RANK () OVER ( ORDER BY total DESC ) rank_no FROM ('
            'SELECT user_id, sum(quantity) AS total FROM member_stats '
            'WHERE guild_id = ? AND time >= ? AND time <= ? '
            'GROUP BY user_id '
            'ORDER BY total DESC )) '
            'SELECT now.*, prev.total, prev.rank_no FROM now '
            'LEFT JOIN prev ON now.user_id = prev.user_id',
            (guild.id, time_start, time_end, amount, 
            guild.id, time_prev_start, time_start)
        ).fetchall()
        if len(result) == 0 or not result[0]:
            return discord.Embed.from_dict( {"title": "STONKS", "description": f"Found nothing in the db :("} )

        time = f"{int(time_period // (24*60*60))}d{int((time_period % (24*60*60)) // (3600))}h"
        embed = discord.Embed.from_dict( {"title": "STONKS", "description": f"Showing the stonks for top {amount} users for the past {time}, compared with previous stonks"} )
        embed.colour = random.randint(0, 0xffffff)
        msg = ""
        for (i, value) in enumerate(result):  
            mem = guild.get_member(value[0])
            if mem is None:
                name = f'<removed member {value[0]}>'
            else:
                name = mem.display_name
            count = value[1]
            prev_count = value[2]
            prev_i = value[3]
            def diff(old, new):
                if old is None or new is None:
                    return "/"
                n = new - old
                if n == 0:
                    return "="
                return f"▲{n}" if n >= 0 else f"▼{abs(n)}"   
            msg += f"#**{i+1}** ({diff(i+1, prev_i)})   `{name}`: **{count}** ({diff(prev_count, count)})\n"
        embed.add_field(name="Leaderboard", value=msg, inline=True)
        return embed

    async def get_simple_leaderboard(
        self,
        guild,
        amount,
        time_period
    ):
       
        time_end =  int(datetime.datetime.now(datetime.timezone.utc).timestamp() / TIME_BUCKET)
        time_start =  int((datetime.datetime.now(datetime.timezone.utc).timestamp() - time_period) / TIME_BUCKET)
        time_prev_start =  int((datetime.datetime.now(datetime.timezone.utc).timestamp() - 2*time_period) / TIME_BUCKET)

        result = self.cursor.execute(
            'SELECT user_id, sum(quantity) AS total FROM member_stats '
            'WHERE guild_id = ? AND time >= ? AND time <= ? '
            'GROUP BY user_id '
            'ORDER BY total DESC '
            'LIMIT ?',
            (guild.id, time_start, time_end, amount)
        ).fetchall()
        if len(result) == 0 or not result[0]:
            return discord.Embed.from_dict( {"title": "STONKS", "description": f"Found nothing in the db :("} )

        time = f"{int(time_period // (24*60*60))}d{int((time_period % (24*60*60)) // (3600))}h"
        embed = discord.Embed.from_dict( {"title": "STONKS", "description": f"Showing the stonks for top {amount} users for the past {time}"} )
        embed.colour = random.randint(0, 0xffffff)
        msg = ""
        for (i, value) in enumerate(result):  
            mem = guild.get_member(value[0])
            if mem is None:
                name = f'<removed member {value[0]}>'
            else:
                name = mem.display_name
            count = value[1]

            msg += f"#**{i+1}** `{name}`: **{count}**\n"
        embed.add_field(name="Leaderboard", value=msg, inline=True)
        return embed
    
    async def get_leaderboard(
        self,
        guild,
        length,
        time_period,
        has_comparison
    ):
        if has_comparison:
            return await self.get_comp_leaderboard(guild, length, time_period)
        else:
            return await self.get_simple_leaderboard(guild, length, time_period)

    @commands.guild_only()
    @checks.admin()
    @commands.group()
    async def userstonks(self, ctx):
        """Config options for wordstats."""
        pass

    @userstonks.command()
    async def staticleaderboard(self, ctx, length: int=10, time_period: int=24*60*60, has_comparison: bool=True):
        """
        Generates a leaderboard
        
        Use the optional parameter "time_period" to set the time period to measure back to in seconds.
        Use the optional parameter "length" to change the number of members that are displayed.
        Use the optional parameter "has_comparison" to display leaderboards with a comparison to the previous period.
        """

        guild = ctx.guild
        if time_period < TIME_BUCKET:
            return await ctx.send(f'Time period must be more than {TIME_BUCKET}')
        if length <= 0:
            return await ctx.send('At least one member needs to be displayed.')
        if length > 100:
            return await ctx.send('You cannot request more than 100 members.')


        with ctx.typing():
            e = await self.get_leaderboard(guild, length, time_period, has_comparison)

        try:
            await ctx.send(embed=e)
        except discord.errors.HTTPException:
            await ctx.send('The result is too long to send.')


    @userstonks.command()
    async def autoleaderboard(self, ctx, update_period: int=15*60, length: int=10, time_period: int=24*60*60, has_comparison: bool=True):
        """
        Generates an autoupdating leaderboard
        
        Use the optional parameter "update_period" to set the update period for the leaderboard.
        Use the optional parameter "time_period" to set the time period to measure back to in seconds.
        Use the optional parameter "length" to change the number of members that are displayed.
        Use the optional parameter "has_comparison" to display leaderboards with a comparison to the previous period.
        """
        
        guild = ctx.guild
        if update_period < AUTOUPDATE_CHECK_INTERVAL / 2:
            return await ctx.send(f'Update period must be more than {AUTOUPDATE_CHECK_INTERVAL / 2}')
        if time_period < TIME_BUCKET:
            return await ctx.send(f'Time period must be more than {TIME_BUCKET}')
        if length <= 0:
            return await ctx.send('At least one member needs to be displayed.')
        if length > 100:
            return await ctx.send('You cannot request more than 100 members.')

        with ctx.typing():
            e = await self.get_leaderboard(guild, length, time_period, has_comparison)

        try:
            embed_sent = await ctx.send(embed=e)
        except discord.errors.HTTPException:
            await ctx.send('The leaderboard is too long to send.')
            return
        msg = await ctx.fetch_message(embed_sent.id)

        leaderboards = await self.config.guild(guild).autoLeaderboards()
        leaderboards.append({
            "messageId": msg.id,
            "channelId": msg.channel.id,
            "update_period": update_period,
            "next_update": datetime.datetime.timestamp(datetime.datetime.now()) + update_period,
            "length": length,
            "time_period": time_period,
            "has_comparison": has_comparison
        })
        await self.config.guild(guild).autoLeaderboards.set(leaderboards)

    @userstonks.command()
    async def deleteauto(self, ctx, id: int=None):
        leaderboards = await self.config.guild(ctx.guild).autoLeaderboards()
        if id is None:
            msg = "Leaderboards: (use `deleteauto id` to remove from the auto update list)\n"
            for i, b in enumerate(leaderboards):
                try:
                    channel = ctx.guild.get_channel(b["channelId"])
                    if channel is None:
                        msg += f"id: {i} = couldn't find channel\n"
                        continue
                    embed = await channel.fetch_message(b["messageId"])
                    if embed is None:
                        msg += f"id: {i} = couldn't find message\n"
                        continue
                    msg += f"id: {i} = {embed.jump_url}\n"
                except:
                    msg += f"id: {i} = failed to load leaderboard\n"
            await ctx.send(msg)
        else:
            if id < 0 or id >= len(leaderboards):
                await ctx.send("Invalid id")
                return
            del leaderboards[id]
            await self.config.guild(ctx.guild).autoLeaderboards.set(leaderboards)
            await ctx.send("Leaderboard removed from update list")

    @checks.is_owner()
    @userstonks.command()
    async def deleteall(self, ctx, confirm: bool=False):
        """
        Delete all user stats data.
        
        This removes all existing data, creating a blank state.
        This cannot be undone.
        """
        if not confirm:
            await ctx.send(
                'Running this command will delete all user stats data. '
                'This cannot be undone. '
                f'Run `{ctx.prefix}userstonks deleteall yes` to confirm.'
            )
            return
        self.cursor.execute('DROP TABLE member_stats;')
        self.cursor.execute(
            'CREATE TABLE IF NOT EXISTS member_stats ('
            'guild_id INTEGER NOT NULL,'
            'user_id INTEGER NOT NULL,'
            'time INTEGER NOT NULL,'
            'quantity INTEGER DEFAULT 1,'
            'PRIMARY KEY (guild_id, user_id, time)'
            ');'
        )
        await ctx.send('User stats data has been reset.')
    
    @userstonks.command()
    async def server(self, ctx, value: bool=None):
        """
        Set if user stats should record stats for this server.
        
        Defaults to True.
        This value is server specific.
        """
        if value is None:
            v = await self.config.guild(ctx.guild).enableGuild()
            if v:
                await ctx.send('Stats are being recorded in this server.')
            else:
                await ctx.send('Stats are not being recorded in this server.')
        else:
            await self.config.guild(ctx.guild).enableGuild.set(value)
            if value:
                await ctx.send('Stats will now be recorded in this server.')
            else:
                await ctx.send('Stats will no longer be recorded in this server.')
            if ctx.guild.id in self.ignore_cache:
                del self.ignore_cache[ctx.guild.id]
    
    @userstonks.command()
    async def channel(self, ctx, channel: Optional[discord.TextChannel]=None, value: bool=None):
        """
        Set if users stats should record stats for this channel.
        
        Defaults to True.
        This value is channel specific.
        """
        if channel is None:
            channel = ctx.channel
        v = await self.config.guild(ctx.guild).disabledChannels()
        if value is None:
            if channel.id not in v:
                await ctx.send(f'Stats are being recorded in {channel.mention}.')
            else:
                await ctx.send(f'Stats are not being recorded in {channel.mention}.')
        else:
            if value:
                if channel.id not in v:
                    await ctx.send(f'Stats are already being recorded in {channel.mention}.')
                else:
                    v.remove(channel.id)
                    await self.config.guild(ctx.guild).disabledChannels.set(v)
                    await ctx.send(f'Stats will now be recorded in {channel.mention}.')
            else:
                if channel.id in v:
                    await ctx.send(f'Stats are already not being recorded in {channel.mention}.')
                else:
                    v.append(channel.id)
                    await self.config.guild(ctx.guild).disabledChannels.set(v)
                    await ctx.send(f'Stats will no longer be recorded in {channel.mention}.')
            if ctx.guild.id in self.ignore_cache:
                del self.ignore_cache[ctx.guild.id]
    
    @userstonks.command()
    async def ignoreprefix(self, ctx, prefix: str=None, value: bool=True):
        """
        Set the message prefixes that should be ignored
        
        Use the optional parameter prefix to add or remove it from the ignore list.
        Use the optional parameter value to set if it should be ignored or not, defaults to true.
        This value is server specific.
        """
        v = await self.config.guild(ctx.guild).disabledPrefixes()
        if prefix is None:
            await ctx.send(f'Messages starting with [{" ".join(v)}] are being ignored.')
        elif value:
            if prefix in v:
                await ctx.send(f'Messages starting with {prefix} are already being ignored.')
            else:
                v.append(prefix)
                await self.config.guild(ctx.guild).disabledPrefixes.set(v)
                await ctx.send(f'Messages starting with {prefix} will now be ignored.')
        else:
            if prefix not in v:
                await ctx.send(f'Messages starting with {prefix} are not being ignored.')
            else:
                v.remove(prefix)
                await self.config.guild(ctx.guild).disabledPrefixes.set(v)
                await ctx.send(f'Messages starting with {prefix} will now be counted.')
            
        if ctx.guild.id in self.ignore_cache:
            del self.ignore_cache[ctx.guild.id]
    
    def cog_unload(self):
        self.printer.cancel()
        self._executor.shutdown()
    
    def safe_write(self, query, data):
        """Func for safely writing in another thread."""
        cursor = self._connection.cursor()
        cursor.execute(query, data)

    @commands.Cog.listener()
    async def on_message_without_command(self, msg):
        if msg.author.bot or not isinstance(msg.channel, discord.TextChannel):
            return
        if await self.bot.cog_disabled_in_guild(self, msg.guild):
            return
        if msg.guild.id not in self.ignore_cache:
            cfg = await self.config.guild(msg.guild).all()
            self.ignore_cache[msg.guild.id] = cfg
        enableGuild = self.ignore_cache[msg.guild.id]['enableGuild']
        disabledChannels = self.ignore_cache[msg.guild.id]['disabledChannels']
        disabledPrefixes = self.ignore_cache[msg.guild.id]['disabledPrefixes']
        if not enableGuild or msg.channel.id in disabledChannels:
            return
        for p in disabledPrefixes:
            if msg.content.startswith(p):
                return

        amount = 3
        if len(msg.attachments) > 0:
            amount = 4
        query = (
            'INSERT INTO member_stats (guild_id, user_id, time)'
            'VALUES (?, ?, ?)'
            f'ON CONFLICT(guild_id, user_id, time) DO UPDATE SET quantity = quantity + {amount};'
        )
        time = int(msg.created_at.replace(tzinfo=pytz.UTC).timestamp() / TIME_BUCKET)
        data = (msg.guild.id, msg.author.id, time)
        task = functools.partial(self.safe_write, query, data)
        await self.bot.loop.run_in_executor(self._executor, task)