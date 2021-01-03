from redbot.core import commands, checks, Config
from redbot.core.utils import AsyncIter, menus
from redbot.core.utils.predicates import MessagePredicate
import discord
from datetime import datetime
import typing

class ContestCount(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        

    @commands.guild_only()
    @checks.admin()
    @commands.command()
    async def contestcount(self, ctx, channel: discord.TextChannel,
                            emote: str,
                            show_invalid: bool=True, 
                            voter_server_age: commands.TimedeltaConverter()=None,
                            entries_per_page: int=9,
                            *other_emotes):
        timenow = datetime.now()
        def valid_user_vote(u):
            if (not hasattr(u, 'joined_at')) or u.joined_at is None:
                return False
            elif (not voter_server_age is None) and (u.joined_at >= timenow - voter_server_age):
                return False
            return True 
        
        entries = []
        async for message in channel.history():
            entry = {
                "name": str(message.author),
                "valid_votes": 0,
                "invalid_votes": 0
            }
            for r in message.reactions:
                if str(r.emoji) == emote or str(r.emoji) in other_emotes:
                    all_votes = await r.users().flatten()
                    entry["valid_votes"] = len(list(filter(valid_user_vote, all_votes)))
                    entry["invalid_votes"] = len(all_votes) - entry["valid_votes"]
            entries.append(entry)
        
        if len(entries) == 0:
            await ctx.send(f"No entris found for channel {channel}")
        else:
            entries = sorted(entries, key=lambda e: e["valid_votes"], reverse=True)

            pages = []
            embed = None
            for (i, entry) in enumerate(entries):
                if i % entries_per_page == 0:
                    if not embed is None:
                        pages.append(embed)
                    embed = discord.Embed.from_dict( {"description": f"Contest leaderboard!"} )
                if show_invalid:
                    embed.add_field(name=f"#{i+1} {entry['name']}", value=f"{entry['valid_votes']} valid votes ({entry['invalid_votes']} invalid)",inline=False)
                else:
                    embed.add_field(name=f"#{i+1} {entry['name']}", value=f"{entry['valid_votes']} votes",inline=False)
                
            pages.append(embed)
                
            await menus.menu(ctx, pages, menus.DEFAULT_CONTROLS)
