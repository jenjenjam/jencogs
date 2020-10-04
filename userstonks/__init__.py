from .userstonks import UserStonks

def setup(bot):
    bot.add_cog(UserStonks(bot))