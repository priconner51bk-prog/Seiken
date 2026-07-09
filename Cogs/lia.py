import atexit
import re
import traceback
import discord
from discord.ext import commands
import asyncio


import os

from datetime import datetime
import collections
import json
import sqlite3


# pip install emoji
import emoji

class Enquete():
    """アンケートメンバーを管理するクラス"""
    def __init__(self,members:list[discord.Member]=[],emojis:list=[],channel_id=None,message_id=None):
        self.members_dict=collections.OrderedDict({'ノーリアクション':[]})
        for member in members:
            self.members_dict['ノーリアクション'].append(member.id)
        for _emoji in emojis:
            self.members_dict[_emoji]=[]
        self.channel_id=channel_id
        self.message_id=message_id
        self.created_at=datetime.now()
        self.send_id=None
        self.bot_id=None


    def __eq__(self, __o: object):
        return self.message_id == __o

    
    def ToContent(self,guild:discord.Guild):
        """アンケートのmessage.content"""
        _content=""
        _no_reaction=""

        for _emoji in self.members_dict:

            _member_ids=[v for v in self.members_dict[_emoji] if v != self.bot_id]

            if _emoji=='ノーリアクション':
                members=[]
                for member_id in _member_ids:
                    if sum([self.members_dict[_emoji].count(member_id) for _emoji in self.members_dict]) == 1:
                        members.append(member_id)
                _no_reaction=f'\nノーリアクション {len(members)}人\n'
                if len(members)>0:
                    _no_reaction+=f'{"　".join(["`"+guild.get_member(v).display_name+"`" for v in members])}'

            else:
                _content+=f'\n{_emoji} {len(_member_ids)}人\n'
                if len(_member_ids)>0:
                    _content+=f'{"　".join(["`"+guild.get_member(v).display_name+"`" for v in _member_ids])}\n'

        return _content+_no_reaction
    

    def ToString(self):
        """ファイルに保存する用の文字列に変換"""
        _members_str=json.dumps(self.members_dict)
        return f"{self.channel_id},{self.message_id},{self.send_id},{self.created_at.timestamp()},{_members_str}"
    

    def FromString(s:str):
        """ToStringで変換した文字列をMembersListへ変換"""
        try:
            _e=Enquete()
            _e.channel_id=int(s.split(",")[0])
            _e.message_id=int(s.split(",")[1])
            _e.send_id=int(s.split(",")[2])
            _e.created_at=datetime.fromtimestamp(float(s.split(",")[3]))
            _members_str=",".join(s.split(",")[4:])
            _e.members_dict=json.loads(_members_str)
            return _e
        except:
            print(traceback.format_exc())
    

    async def check_reaction(self,bot:commands.Bot):
        try:
            _changed=False
            _message=await bot.get_channel(self.channel_id).fetch_message(self.message_id)
            for _reaction in _message.reactions:
                _e=_reaction.emoji
                if type(_e) != str and _reaction.emoji.id != None:
                    _e=f'<:{_reaction.emoji.name}:{_reaction.emoji.id}>'

                if _e not in self.members_dict:
                    async for user in _reaction.users():
                        self.add_reaction(user.id,_e)
                    _changed=True
                else:
                    _reaction_members=[user.id async for user in _reaction.users()]
                    for _member_id in self.members_dict[_e]:
                        if _member_id not in _reaction_members:
                            self.remove_reaction(_member_id,_e)
                            _changed=True
                    for _member_id in _reaction_members:
                        if _member_id not in self.members_dict[_e]:
                            self.add_reaction(_member_id,_e)
                            _changed=True
            
            if _changed:
                _content=self.ToContent(_message.guild)
                _send_message=_message.channel.get_partial_message(self.send_id)
                await _send_message.edit(content=_content,allowed_mentions=discord.AllowedMentions(users=False))
        except discord.NotFound:
            return False
        except:
            pass
        return True
                        
                    


                
    

    def add_reaction(self,member_id,e):
        if e not in self.members_dict:
            self.members_dict[e]=[]
        self.members_dict[e].append(member_id)

        #if member_id in self.members_dict["ノーリアクション"]:
        #    self.members_dict["ノーリアクション"].remove(member_id)
    

    def remove_reaction(self,member_id,e):
        if e in self.members_dict and member_id in self.members_dict[e]:
            self.members_dict[e].remove(member_id)
            if len(self.members_dict[e])==0:
                del self.members_dict[e]

            # どこにもリアクションをしていない場合にノーリアクションにぶち込む
            #if sum([self.members_dict[_emoji].count(member_id) for _emoji in self.members_dict]) == 0:
            #    self.members_dict["ノーリアクション"].append(member_id)
        

class Lia(commands.Cog):
    def __init__(self,bot:commands.Bot):
        self.bot=bot
        self.enquete_list:list[Enquete]=[]
    
    @commands.Cog.listener('on_message')
    async def on_enquete(self,message:discord.Message):
        if isinstance(message.channel,discord.TextChannel) and f'<@{self.bot.user.id}>' in message.content and message.channel.permissions_for(message.guild.get_member(self.bot.user.id)).send_messages:
            _emojis=emoji.distinct_emoji_list(message.content)
            _emojis.extend([v for v in re.findall(r'<:[^:]+:\d+>',message.content)])

            _emoji_list=[]
            for _emoji in _emojis:
                _emoji_list.append((_emoji,message.content.find(_emoji)))
            _emoji_list.sort(key=lambda x:x[1])
            for _emoji in _emoji_list:
                try:
                    await message.add_reaction(_emoji[0])
                except:
                    continue
            
            #_mentions=message.mentions
            _mentions=[]

            #for role in message.role_mentions:
            if len(message.role_mentions) >= 1:
                _mentions.extend(message.role_mentions[0].members)
            
            _members=Enquete(_mentions,[_e[0] for _e in _emoji_list],message.channel.id,message.id)
            _members.bot_id=self.bot.user.id
            self.enquete_list.append(_members)

            for _e in _emoji_list:
                self.enquete_list[-1].add_reaction(self.bot.user.id,_e[0])

            _enquete_content=_members.ToContent(message.guild)
            _send=await message.channel.send(_enquete_content,allowed_mentions=discord.AllowedMentions(users=False))
            _members.send_id=_send.id

            #新規登録時にファイル保存
            self.fwrite()
    
    @commands.Cog.listener('on_raw_reaction_add')
    async def enquete_reaction_add(self,payload:discord.RawReactionActionEvent):
        if payload.message_id in self.enquete_list:
            _members=self.enquete_list[self.enquete_list.index(payload.message_id)]
            if payload.emoji.id == None:
                _members.add_reaction(payload.user_id,payload.emoji.name)
            else:
                _members.add_reaction(payload.user_id,f'<:{payload.emoji.name}:{payload.emoji.id}>')
            _content=_members.ToContent(self.bot.get_guild(payload.guild_id))
            await self.bot.get_channel(payload.channel_id).get_partial_message(_members.send_id).edit(content=_content,allowed_mentions=discord.AllowedMentions(users=False))


    @commands.Cog.listener('on_raw_reaction_remove')
    async def enquete_reaction_remove(self,payload:discord.RawReactionActionEvent):
        if payload.message_id in self.enquete_list:
            _members=self.enquete_list[self.enquete_list.index(payload.message_id)]
            if payload.emoji.id == None:
                _members.remove_reaction(payload.user_id,payload.emoji.name)
            else:
                _members.remove_reaction(payload.user_id,f'<:{payload.emoji.name}:{payload.emoji.id}>')
            _content=_members.ToContent(self.bot.get_guild(payload.guild_id))
            await self.bot.get_channel(payload.channel_id).get_partial_message(_members.send_id).edit(content=_content,allowed_mentions=discord.AllowedMentions(users=False))

    @commands.command()
    async def add_enquete(self,ctx:commands.Context):
        args=ctx.message.content.split()
        if len(args)==3:
            try:
                channel_id=int(str(args[1]).split("/")[-2])
                Qmsg_id=int(str(args[1]).split("/")[-1])
                Amsg_id=int(str(args[2]).split("/")[-1])

                Amsg=await ctx.guild.get_channel(channel_id).fetch_message(Amsg_id)
                if Amsg.author.id != self.bot.application_id:
                    return
                message=await ctx.guild.get_channel(channel_id).fetch_message(Qmsg_id)
                
                _emojis=emoji.distinct_emoji_list(message.content)
                _emojis.extend([v for v in re.findall(r'<:[^:]+:\d+>',message.content)])

                _emoji_list=[]
                for _emoji in _emojis:
                    _emoji_list.append((_emoji,message.content.find(_emoji)))
                _emoji_list.sort(key=lambda x:x[1])
                
                #_mentions=message.mentions
                _mentions=[]

                #for role in message.role_mentions:
                if len(message.role_mentions) >= 1:
                    _mentions.extend(message.role_mentions[0].members)
                
                _members=Enquete(_mentions,[_e[0] for _e in _emoji_list],message.channel.id,message.id)
                _members.bot_id=self.bot.user.id
                self.enquete_list.append(_members)

                for _e in _emoji_list:
                    self.enquete_list[-1].add_reaction(self.bot.user.id,_e[0])

                _members.send_id=Amsg_id

                #新規登録時にファイル保存
                self.fwrite()
            except:
                pass

    async def cog_load(self):
        
        asyncio.create_task(self.enquete_reactions())
        
        # プログラム終了時に実行する関数
        atexit.register(self.fwrite)
    
    async def enquete_reactions(self):
        await asyncio.sleep(10)
        now=datetime.now()
        try:
            with open('list.txt','r') as f:
                for _s in f:
                    _enquete=Enquete.FromString(_s)
                    if (now-_enquete.created_at).days <= 30:
                        _enquete.bot_id=self.bot.user.id
                        if await _enquete.check_reaction(self.bot):
                            self.enquete_list.append(_enquete)
        except:
            pass
        
    

    def fwrite(self):
        
        with open('list.txt','w') as f:
            _s="\n".join([v.ToString() for v in self.enquete_list])
            f.write(_s)



async def setup(bot:commands.Bot):
    await bot.add_cog(Lia(bot))
