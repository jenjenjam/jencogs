from .impersonate import Impersonate

try:
    import markovify
    markovifyAvailable = True
except ImportError:
    markovifyAvailable = False

def setup(bot):
    if markovifyAvailable:
        bot.add_cog(Impersonate(bot))
    else:
        raise RuntimeError(f"You need to install markovify via 'pip3 install markovify'")