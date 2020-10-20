from .colourlimit import ColourLimit

def setup(bot):
    bot.add_cog(ColourLimit(bot))