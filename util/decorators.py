from functools import wraps
import discord
from discord.ext import commands
from util.database import db

class DpyDecorator():
    def member_check(func):
        @wraps(func)
        async def _inner(self,*args,**kwargs):
            member:discord.Member=None
            match type(args[0]):
                case discord.Message:
                    member=args[0].author
                case discord.RawReactionActionEvent:
                    member=self.bot.get_guild(args[0].guild_id).get_member(args[0].user_id)
                case discord.Member:
                    member=args[0]
            if member==None:
                await func(self,*args,**kwargs)
            elif member.bot:
                pass
            elif db.read_member(member.guild.id,"id",member.id) != None:
                await func(self,*args,**kwargs)
        return _inner
    
    def admin(func):
        @wraps(func)
        async def _inner(self,*args,**kwargs):
            if isinstance(args[0],commands.Context):
                if args[0].author.id==638677227860394005:
                    await func(self,*args,**kwargs)
                else:
                    pass
        return _inner