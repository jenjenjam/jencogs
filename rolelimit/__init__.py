from .rolelimit import RoleLimit

def setup(bot):
    bot.add_cog(RoleLimit(bot))