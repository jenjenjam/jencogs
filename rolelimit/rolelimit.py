from redbot.core import commands, checks, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.predicates import MessagePredicate
import discord

class RoleLimit(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1471894719841)
        self.config.register_guild(
            roles=[]
        )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if len(after.roles) <= len(before.roles):
            return
        
        await self.clean_roles(after)

    async def clean_roles(self, user):
        limit_roles = await self.config.guild(user.guild).roles()
        highest_limit_role = None
        to_remove = []
        for role_id in limit_roles:
            role = user.guild.get_role(role_id)
            if role in user.roles:
                if highest_limit_role is None:
                    highest_limit_role = role
                else:
                    to_remove.append(highest_limit_role)
                    highest_limit_role = role
        if len(to_remove) > 0:
            await user.remove_roles(*to_remove)


    @commands.guild_only()
    @commands.group()
    async def rolelimit(self, cxx):
        pass

    @commands.guild_only()
    @checks.admin()
    @rolelimit.command()
    async def set(self, ctx, *roles: discord.Role):
        await self.config.guild(ctx.message.guild).roles.set(
                [r.id for r in roles]
            )
        await self.listroles(ctx)

    @commands.guild_only()
    @checks.admin()
    @rolelimit.command()
    async def listroles(self, ctx):
        roles = await self.config.guild(ctx.message.guild).roles()
        role_list = ', '.join([f"{str(r)} ({ctx.message.guild.get_role(r)})" for r in roles])
        await ctx.send(f"Roles to limit (lowest to highest): {role_list}")

    @commands.guild_only()
    @checks.admin()
    @rolelimit.command()
    async def clear(self, ctx):
        await self.config.guild(ctx.message.guild).roles.set(
                []
            )
        await self.listroles(ctx)

    @commands.guild_only()
    @checks.admin()
    @rolelimit.command()
    async def scan(self, ctx):
        await ctx.send(f"Are you sure you want to scan all members and apply the rolelimit? Answer yes/no, timeout in 30 seconds")
        pred = MessagePredicate.yes_or_no(ctx)
        await self.bot.wait_for("message", check=pred, timeout=30.0)
        if pred.result is True:
            await ctx.send(f"Now scanning members")
            async for user in AsyncIter(ctx.message.guild.members, steps=50):
                await self.clean_roles(user)

            await ctx.send(f"Scanned {len(ctx.message.guild.members)} members")
        else:
            await ctx.send(f"Scan cancelled")