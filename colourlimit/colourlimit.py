from redbot.core import commands, checks, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.predicates import MessagePredicate
import discord

class ColourLimit(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 147189471982418789741)
        self.config.register_guild(
            roles=[]
        )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if len(after.roles) <= len(before.roles):
            return

        diff = [item.id for item in after.roles if item not in before.roles]
        user = after
        limit_roles = await self.config.guild(user.guild).roles()
        remove_roles = False
        for role in diff:
            if role in limit_roles:
                remove_roles = True
        
        if remove_roles:
            to_remove = []
            for role_id in limit_roles:
                role = user.guild.get_role(role_id)
                if role in before.roles:
                    to_remove.append(role)
            if len(to_remove) > 0:
                await user.remove_roles(*to_remove)
            


    @commands.guild_only()
    @commands.group()
    async def colourlimit(self, cxx):
        pass

    @commands.guild_only()
    @checks.admin()
    @colourlimit.command()
    async def set(self, ctx, *roles: discord.Role):
        await self.config.guild(ctx.message.guild).roles.set(
                [r.id for r in roles]
            )
        await self.listroles(ctx)

    @commands.guild_only()
    @checks.admin()
    @colourlimit.command()
    async def listroles(self, ctx):
        roles = await self.config.guild(ctx.message.guild).roles()
        role_list = ', '.join([f"{str(r)} ({ctx.message.guild.get_role(r)})" for r in roles])
        await ctx.send(f"Roles to limit (to newest): {role_list}")

    @commands.guild_only()
    @checks.admin()
    @colourlimit.command()
    async def clear(self, ctx):
        await self.config.guild(ctx.message.guild).roles.set(
                []
            )
        await self.listroles(ctx)