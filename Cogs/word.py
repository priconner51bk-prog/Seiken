import re
from typing import Any, List, Literal, Optional
import discord
from discord import app_commands
from discord.components import SelectOption
from discord.ext import commands
from discord.interactions import Interaction
from discord.utils import MISSING

from util.database import db
from util.decorators import DpyDecorator



class Word(commands.Cog):
    def __init__(self,bot:commands.Bot):
        self.bot=bot
        self.word_list={}
        self.load_word()
    

    class WordDeleteView(discord.ui.View):
        def __init__(self, word_list:dict, timeout=180):
            super().__init__(timeout=timeout)
            self.add_item(Word.WordDeleteView.WordDeleteSelect(word_list))
        
        class WordDeleteSelect(discord.ui.Select):
            def __init__(self,word_list:dict):
                self.word_list=word_list
                options=[discord.SelectOption(value=key,label=key,description=f"{key} : {word_list[key]}") for key in word_list]
                super().__init__(options=options)
            
            async def callback(self, interaction: discord.Interaction):
                for value in self.values:
                    del self.word_list[value]
                    db.delete_word(interaction.guild_id,value)
                await interaction.response.send_message("\n".join(self.values)+"を削除しました",ephemeral=True)



    @app_commands.command(name="word",description="単語登録")
    @app_commands.guild_only()
    async def word_slash(self,interaction:discord.Interaction,keyword:str=None,response:str=None):
        if keyword==None != response==None:
            await interaction.response.send_message("単語を登録することができませんでした\nkeywordとresponseを入力してください",ephemeral=True)
            return
        
        if keyword != None and response != None:
            if interaction.guild_id not in self.word_list:
                self.word_list[interaction.guild_id]={}
            if len(self.word_list[interaction.guild_id]) <= 20:
                self.word_list[interaction.guild_id][keyword.strip()]=response
                db.write_word(interaction.guild_id,keyword.strip(),response)
                await interaction.response.send_message(f"単語を登録しました\n{keyword}\n――――――\n{response}",ephemeral=True)
            else:
                await interaction.response.send_message(f"登録できる単語は20個までです",ephemeral=True)
            return
        
        if interaction.guild_id in self.word_list and len(self.word_list[interaction.guild_id])>0:
            _res="登録されている単語一覧\n"
            for _w in self.word_list[interaction.guild_id]:
                _res+=f"{_w}　:　{self.word_list[interaction.guild_id][_w]}\n"
            await interaction.response.send_message(_res,ephemeral=True,view=self.WordDeleteView(self.word_list[interaction.guild_id]))
        else:
            await interaction.response.send_message("単語は登録されていません",ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message(self,message:discord.Message):
        try:
            content=message.content
            if len(message.stickers) > 0:
                match message.stickers[0].id:
                    # 1～5ボス
                    case 1343949879013281802:
                        content="<:1_kaitou:1343951486253535337>"
                    case 1354476245290586223:
                        content="<:2_kaitou:1354476018953617589>"
                    case 1343950149029859339:
                        content="<:3_kaitou:1343952398028374096>"
                    case 1343950198967111843:
                        content="<:4_kaitou:1343952414625239050>"
                    case 1343950249546350673:
                        content="<:5_kaitou:1343952437295190067>"
                    # 募集
                    case 1304441542542360637:
                        content="<:honsen_start:1343468869137858600>"
            elif message.author.bot:
                return
            if message.guild.id in self.word_list:
                for _key in self.word_list[message.guild.id]:
                    if _key in content:
                        text=self.word_list[message.guild.id][_key]
                        search=re.search(r"@[1-5１-５]ボス",text)
                        if search:
                            boss=int(search.group()[1])
                            mentions_id=db.execute(f"SELECT id FROM dc_{message.guild.id} WHERE boss = {boss} AND done <> 1")
                            mentions=[]
                            for mention_id in mentions_id:
                                mentions.append(mention_id[0])
                            mentions_text=" ".join([f"<@{v}>" for v in set(mentions)])
                            text=re.sub(r"@[1-5１-５]ボス",mentions_text,text)
                        await message.channel.send(text)
                        return
        except:
            return
    
    def load_word(self):
        names=db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY NAME")
        for name in names:
            if name[0].startswith("word_"):
                guild_id=int(re.search(r"\d+",name[0]).group())
                words=db.execute(f"SELECT * FROM {name[0]}")
                self.word_list[guild_id]={}
                for _word in words:
                    self.word_list[guild_id][_word[0]]=_word[1]


async def setup(bot:commands.Bot):
    await bot.add_cog(Word(bot))