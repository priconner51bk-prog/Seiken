import re
from typing import List, Literal
import discord
from discord import app_commands
from discord.ext import commands

from util.database import db
from util.decorators import DpyDecorator

import emoji

class Channel(commands.Cog):
    def __init__(self,bot:commands.Bot):
        self.bot=bot
    
    @app_commands.command(name="channel",description="チャンネルに機能を持たせるコマンド 引数無しでチャンネル設定を削除")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_nicknames=True)
    async def channel_slash(self,interaction:discord.Interaction,setting_name:str,channel:discord.TextChannel=None):
        if setting_name!="":
            if channel!=None:
                db.write_guild(interaction.guild_id,setting_name,channel.id)
                await interaction.response.send_message(channel.mention+"に設定しました",ephemeral=True)
            else:
                db.delete_guild(interaction.guild_id,setting_name)
                await interaction.response.send_message("設定を削除しました",ephemeral=True)
        else:
            res=""
            try:
                channels=db.execute(f"SELECT sengen_ch,taskkill_ch,log_ch,mochikoshi_ch,kanryou_ch FROM guild WHERE id = {interaction.guild_id}")[0]
                ch_name=["凸宣言","タスキル報告","ダメコンログ","持ち越し報告","凸完了報告"]
                for i,c in enumerate(channels):
                    if c!=None:
                        res+=f"{ch_name[i]} {interaction.guild.get_channel(c).mention}\n"
            except:
                pass
            if res!="":
                await interaction.response.send_message(res,ephemeral=True)
            else:
                await interaction.response.send_message("登録されているチャンネルはありません",ephemeral=True)
    
    @channel_slash.autocomplete("setting_name")
    async def cgannel_autocomplete(self,interaction:discord.Interaction,current:str,)->List[app_commands.Choice[str]]:
        val=[("凸宣言","sengen_ch"),("タスキル報告","taskkill_ch"),("ダメコンログ","log_ch"),("持ち越し報告","mochikoshi_ch"),("凸完了報告","kanryou_ch"),("一覧表示","")]
        return [app_commands.Choice(name=v[0],value=v[1]) for v in val if current in v[0]]

    @commands.Cog.listener("on_message")
    @DpyDecorator.member_check
    async def on_message_channel(self,message:discord.Message):
        is_emoji=re.search(":.+:",message.content) or emoji.is_emoji(message.content)
        if is_emoji and message.channel.id==db.read_guild("taskkill_ch",message.guild.id):
            db.write_member(message.guild.id,message.author.id,"taskkill",message.id)
        # 凸宣言はdc.py
        #3凸完了はtable.py


    @commands.Cog.listener("on_raw_message_delete")
    @DpyDecorator.member_check
    async def message_delete_channel(self,payload:discord.RawMessageDeleteEvent):
        """タスキルメッセージの削除"""
        if payload.channel_id==db.read_guild("taskkill_ch",payload.guild_id):
            members=db.read_member(payload.guild_id,"taskkill")
            if members != None:
                try:
                    message_ids=[m[1] for m in members]
                    idx=message_ids.index(payload.message_id)
                    db.delete_member(payload.guild_id,members[idx][0],"taskkill")
                except ValueError:
                    return


async def setup(bot:commands.Bot):
    await bot.add_cog(Channel(bot))