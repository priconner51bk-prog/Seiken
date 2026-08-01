from discord.ext import commands


class EmojiUtil:
    _bot: commands.Bot | None = None

    @classmethod
    def setup(cls, bot: commands.Bot):
        cls._bot = bot

    @classmethod
    def get(cls, emoji_id: int):
        if cls._bot is None:
            raise RuntimeError("EmojiUtil is not initialized")
        return cls._bot.get_emoji(emoji_id)
