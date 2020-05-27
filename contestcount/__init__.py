from .contestcount import ContestCount

def setup(bot):
    bot.add_cog(ContestCount(bot))