from .impersonate import Impersonate

def setup(bot):
    bot.add_cog(Impersonate(bot))