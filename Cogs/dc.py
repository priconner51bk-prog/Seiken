import asyncio
import json
import sqlite3
from typing import Literal, Optional
import discord
from discord import app_commands
from discord.ext import commands,tasks
import datetime as date
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

import re
import math

import discord.http

from util.database import db
from util.decorators import DpyDecorator
from util.content_generator import Generator
from util.spreadsheetdc import SpreadSheetDC
from util.mochi_helper import MochiTableHelper

time=date.time(hour=5,tzinfo=ZoneInfo("Asia/Tokyo"))

table_reaction={}
dc_reprint={}
class PrevName:
    def __init__(self):
        self.name_list={}
    def add(self,guild_id,member_id,prev,boss):
        if not guild_id in self.name_list:
            self.name_list[guild_id]={}
        self.name_list[guild_id][member_id]=(prev,boss)
    def get(self,guild_id,member_id):
        if guild_id in self.name_list and member_id in self.name_list[guild_id]:
            res = self.name_list[guild_id][member_id][0]
            del self.name_list[guild_id][member_id]
            return res
        return None
    def delete(self,guild_id,boss):
        res=[]
        if guild_id in self.name_list:
            for member_id in self.name_list[guild_id].copy():
                if self.name_list[guild_id][member_id][1] == boss:
                    res.append((member_id,self.name_list[guild_id][member_id]))
                    del self.name_list[guild_id][member_id]
        return res
    def return_button(self,guild_id,values):
        if not guild_id in self.name_list:
            self.name_list[guild_id]={}
        for value in values:
            self.name_list[guild_id][value[0]]=value[1]
prev_name=PrevName()
prev_mochi={}
class  PrevMessage:
    def __init__(self):
        self.message_list={}
    def add(self,guild_id,message_id,boss,No,isfinish):
        if not guild_id in self.message_list:
            self.message_list[guild_id]={}
        self.message_list[guild_id][message_id]=(boss,No,isfinish)
    def find(self,guild_id,message_id):
        if guild_id in self.message_list and message_id in self.message_list[guild_id]:
            return True
        return False
    def delete(self,guild_id,message_id):
        if guild_id in self.message_list and message_id in self.message_list[guild_id]:
            del self.message_list[guild_id][message_id]
    def delete_boss(self,guild_id,boss):
        res=[]
        if guild_id in self.message_list:
            for v in self.message_list[guild_id].copy():
                if self.message_list[guild_id][v][0]==boss:
                    res.append((v,self.message_list[guild_id][v]))
                    del self.message_list[guild_id][v]
        return res
    def return_button(self,guild_id,boss,values):
        if not guild_id in self.message_list:
            self.message_list[guild_id]={}
        for value in values:
            self.message_list[guild_id][value[0]]=value[1]
    def delete_No(self,guild_id,No):
        if guild_id in self.message_list:
            for v in self.message_list[guild_id]:
                if No in self.message_list[guild_id][v][1]:
                    self.message_list[guild_id][v][1].remove(No)
                    if len(self.message_list[guild_id][v][1])==0:
                        del self.message_list[guild_id][v]
                    return v
    def content(self,guild_id,message_id):
        if guild_id in self.message_list and message_id in self.message_list[guild_id]:
            res = "〆　" if self.message_list[guild_id][message_id][2] else "通し\n"
            for No in self.message_list[guild_id][message_id][1]:
                member_id=db.execute(f"SELECT id FROM dc_{guild_id} WHERE No = {No}")[0][0]
                res+=f"<@{member_id}>\n"
            return res
        return None
prev_message=PrevMessage()

finish_members={}








class DCCompleteView(discord.ui.View):
    """討伐を押した際に出すボタン"""
    def __init__(self,members,log:discord.Message,content:str,boss:int,prev_stat:dict):
        super().__init__(timeout=120)
        self.members=members
        self.log=log
        self.content=content
        self.boss=boss
        self.prev_stat=prev_stat
        self.isreturn=False
    async def interaction_check(self, interaction):
        if self.isreturn:
            return False
        self.isreturn=True
        return True
    @discord.ui.button(label="戻す",style=discord.ButtonStyle.primary)
    async def return_button(self,interaction:discord.Interaction,button):
        try:
            for member in self.members:
                values=",".join([f"'{v}'" if v != None else "NULL" for v in member])
                db.execute(f"INSERT INTO dc_{interaction.guild_id} \
                    (No,id,boss,status,damage,text,done) \
                    VALUES ({values})")
            content=self.content
            await interaction.channel.get_partial_message(interaction.message.reference.message_id).edit(content=content)
            if self.log!=None:
                await self.log.delete()
            global dc_reprint
            dc_reprint[interaction.guild_id][self.boss-1]=self.prev_stat["dc_reprint"]
            global table_reaction
            table_reaction[interaction.guild_id][self.boss-1]=self.prev_stat["table_reaction"]
            global prev_mochi
            prev_mochi[interaction.guild_id][self.boss-1]=self.prev_stat["prev_mochi"]
            global prev_message
            prev_message.return_button(interaction.guild_id,self.boss,self.prev_stat["prev_message"])
            global prev_name
            prev_name.return_button(interaction.guild_id,self.prev_stat["prev_name"])
        except:
            pass
        await interaction.response.send_message("戻しました",ephemeral=True,delete_after=15)
        await interaction.message.delete()

class SuspendView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="有効化",style=discord.ButtonStyle.primary,custom_id="resume_sengen_button")
    async def resume_sengen_button(self,interaction:discord.Interaction,button):
        db.delete_guild(interaction.guild_id,"suspend_sengen")
        await interaction.message.delete()

class DCBossRenameModal(discord.ui.Modal,title="ボス名変更"):
    b1=discord.ui.TextInput(label="1ボス")
    b2=discord.ui.TextInput(label="2ボス")
    b3=discord.ui.TextInput(label="3ボス")
    b4=discord.ui.TextInput(label="4ボス")
    b5=discord.ui.TextInput(label="5ボス")
    def __init__(self,names):
        self.names=names
        self.b1.default=names[0]
        self.b2.default=names[1]
        self.b3.default=names[2]
        self.b4.default=names[3]
        self.b5.default=names[4]
        super().__init__(timeout=240,custom_id="dc_modal")
    async def on_submit(self, interaction: discord.Interaction):
        res=""
        changed=self.names
        boss=[self.b1,self.b2,self.b3,self.b4,self.b5]
        changenum=[]
        for i in range(5):
            if boss[i].value != self.names[i]:
                res+=f"{self.names[i]}　→　{boss[i].value}\n"
                changed[i]=boss[i].value
                changenum.append(i)
        if res=="":
            await interaction.response.send_message(content="名前の変更はありません",view=None,ephemeral=True)
        else:
            db.write_guild(interaction.guild_id,"dc_name","\n".join(changed))
            for i in changenum:
                content=Generator.dc_content(interaction.guild,i+1)
                message=interaction.guild.get_channel(db.read_guild("dc_ch",interaction.guild_id)).get_partial_message(int(db.read_guild("dc_msg",interaction.guild_id).split("\n")[i]))
                await message.edit(content=content)
            await interaction.response.send_message(content=res,view=None,ephemeral=True)

class DCManageView(discord.ui.View):
    def __init__(self,guild,boss_num):
        super().__init__(timeout=240)
        self.add_item(DCManageSelect(guild,boss_num))

class DCManageSelect(discord.ui.Select):
    def __init__(self,guild:discord.Guild,boss_num):
        self.boss_num=boss_num
        guild_id=guild.id
        self.members=db.execute(f"SELECT dc_{guild_id}.*,member_{guild_id}.taskkill FROM dc_{guild_id} \
                INNER JOIN member_{guild_id} ON dc_{guild_id}.id = member_{guild_id}.id \
                WHERE dc_{guild_id}.boss = {boss_num} ")
        self.members.sort(key=lambda x:x[4] if x[4] != None else -1,reverse=True)
        options=[]
        if len(self.members)>=1:
            for i,m in enumerate(self.members):
                stat=f"{guild.get_member(m[1]).display_name}{m[3]} {m[5]}"
                if m[3] == None:
                    stat=f"{guild.get_member(m[1]).display_name} 凸宣言"
                emj="⬜" if m[6]==0 or m[6]==-1 else "✅"
                options.append(discord.SelectOption(label=stat,value=str(i),emoji=emj))
        super().__init__(options=options[:20],max_values=1)

    async def callback(self, interaction: discord.Interaction):
        stat=f"{interaction.guild.get_member(self.members[int(self.values[0])][1]).display_name}{self.members[int(self.values[0])][3]} {self.members[int(self.values[0])][5]}"
        if self.members[int(self.values[0])][3] == None:
            stat=f"{interaction.guild.get_member(self.members[int(self.values[0])][1]).display_name} 凸宣言"
        emj="⬜" if self.members[int(self.values[0])][6]==0 or self.members[int(self.values[0])][6]==-1 else "✅"
        await interaction.response.edit_message(content=f"{emj} {stat}",view=DCMemberView(self.boss_num,self.members[int(self.values[0])]))



class DCMemberView(discord.ui.View):
    def __init__(self,boss_num,db_member):
        super().__init__(timeout=240)
        self.db_member=list(db_member)
        self.boss_num=boss_num
    
    @discord.ui.button(label="✅⇔⬜",style=discord.ButtonStyle.blurple)
    async def check_button(self,interaction:discord.Interaction,button):
        if self.db_member[6]!=-1:
            if self.db_member[6]==0:
                db.execute(f"UPDATE dc_{interaction.guild_id} SET done = 1 WHERE No = {self.db_member[0]}")
                self.db_member[6]=1
            else:
                db.execute(f"UPDATE dc_{interaction.guild_id} SET done = 0 WHERE No = {self.db_member[0]}")
                self.db_member[6]=0

            stat=f"{interaction.guild.get_member(self.db_member[1]).display_name}{self.db_member[3]} {self.db_member[5]}"
            if self.db_member[3] == None:
                stat=f"{interaction.guild.get_member(self.db_member[1]).display_name} 凸宣言"
            emj="⬜" if self.db_member[6]==0 or self.db_member[6]==-1 else "✅"

            message=interaction.guild.get_channel(db.read_guild("dc_ch",interaction.guild_id)).get_partial_message(db.read_guild("dc_msg",interaction.guild_id).split("\n")[self.boss_num-1])
            await message.edit(content=Generator.dc_content(interaction.guild,self.boss_num))
            await interaction.response.edit_message(content=f"{emj} {stat}")
        else:
            await interaction.response.edit_message(content="凸宣言メッセージは変更できません")
    
    @discord.ui.button(label="取り消し",style=discord.ButtonStyle.red)
    async def delete_button(self,interaction:discord.Interaction,button):
        db.execute(f"DELETE FROM dc_{interaction.guild_id} WHERE No = {self.db_member[0]}")
        message=interaction.guild.get_channel(db.read_guild("dc_ch",interaction.guild_id)).get_partial_message(db.read_guild("dc_msg",interaction.guild_id).split("\n")[self.boss_num-1])
        await message.edit(content=Generator.dc_content(interaction.guild,self.boss_num))
        await interaction.response.edit_message(content="取り消しました",view=None)









class DCReprintDCMessageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    async def interaction_check(self, interaction:discord.Interaction):
        roles=[interaction.guild.get_role(808240600691900417),interaction.guild.get_role(1292855894454964336),interaction.guild.get_role(1335210159735177297)]
        if set(roles) & set(interaction.user.roles):
            return True
        return False
    async def on_error(self, interaction:discord.Interaction, error, item):
        await interaction.response.send_message("転送に失敗しました",ephemeral=True)
    @discord.ui.button(label="メイン転送",style=discord.ButtonStyle.gray,custom_id="main_reprint")
    async def main_button(self,interaction:discord.Interaction,button):
        if interaction.guild_id ==1276184060791750656:
            channel=interaction.guild.get_channel(1293579100056846409)
        else:
            channel=interaction.guild.get_channel(927488075716759562)
        dc_messages=db.read_guild("dc_msg",interaction.guild_id).split("\n")
        boss_num=dc_messages.index(str(interaction.message.id))+1
        await interaction.response.send_message(content=f"{channel.mention}に転送ますか",ephemeral=True,view=DCReprintDCMessageConfirmView(channel,boss_num))
    @discord.ui.button(label="サブ転送",style=discord.ButtonStyle.gray,custom_id="sub_reprint")
    async def sub_button(self,interaction:discord.Interaction,button):
        if interaction.guild_id ==1276184060791750656:
            channel=interaction.guild.get_channel(1335059739410698344)
        else:
            channel=interaction.guild.get_channel(864795442742427648)
        dc_messages=db.read_guild("dc_msg",interaction.guild_id).split("\n")
        boss_num=dc_messages.index(str(interaction.message.id))+1
        await interaction.response.send_message(content=f"{channel.mention}に転送ますか",ephemeral=True,view=DCReprintDCMessageConfirmView(channel,boss_num))
    @discord.ui.button(label="単騎転送",style=discord.ButtonStyle.gray,custom_id="t_reprint")
    async def t_button(self,interaction:discord.Interaction,button):
        if interaction.guild_id ==1276184060791750656:
            channel=interaction.guild.get_channel(1293579743681319023)
        else:
            channel=interaction.guild.get_channel(808238342239813642)
        dc_messages=db.read_guild("dc_msg",interaction.guild_id).split("\n")
        boss_num=dc_messages.index(str(interaction.message.id))+1
        await interaction.response.send_message(content=f"{channel.mention}に転送ますか",ephemeral=True,view=DCReprintDCMessageConfirmView(channel,boss_num))


reprinttimer=[datetime.now(),datetime.now(),datetime.now(),datetime.now(),datetime.now()]
class DCReprintDCMessageConfirmView(discord.ui.View):
    def __init__(self,channel:discord.TextChannel,boss_num):
        super().__init__(timeout=60)
        self.channel=channel
        self.boss_num=boss_num
    @discord.ui.button(label="OK",style=discord.ButtonStyle.green)
    async def OK_button(self,interaction:discord.Interaction,button):
        global reprinttimer
        waittime=(datetime.now()-reprinttimer[self.boss_num-1]).total_seconds()
        if waittime < 10:
            await interaction.response.edit_message(content=f"{int(10-waittime)}秒後に再度試してください")
            return
        await interaction.response.edit_message(content="")
        global dc_reprint
        content=Generator.dc_content(interaction.guild,self.boss_num)
        send_message=await self.channel.send(content=content,view=DCReprintView(self.boss_num),silent=True)
        if not interaction.guild_id in dc_reprint:
            dc_reprint[interaction.guild_id]=[None,None,None,None,None]
        dc_reprint[interaction.guild_id][self.boss_num-1]=send_message
        await interaction.delete_original_response()
        reprinttimer[self.boss_num-1]=datetime.now()
    @discord.ui.button(label="取り消し",style=discord.ButtonStyle.red)
    async def cancel_button(self,interaction:discord.Interaction,button):
        await interaction.response.edit_message(content="")
        await interaction.delete_original_response()


class DCReprintView(discord.ui.View):
    def __init__(self,boss_num):
        super().__init__(timeout=None)
        self.boss_num=boss_num
        
    async def interaction_check(self, interaction:discord.Interaction):
        roles=[interaction.guild.get_role(808240600691900417),interaction.guild.get_role(1292855894454964336),interaction.guild.get_role(1335210159735177297)]
        if set(roles) & set(interaction.user.roles):
            return True
        return False
    
    @discord.ui.button(label="通し指示",style=discord.ButtonStyle.blurple)
    async def through_button(self,interaction:discord.Interaction,button):
        members=db.execute(f"SELECT No,id FROM dc_{interaction.guild.id} WHERE boss = {self.boss_num} AND done = 0")
        if len(members)>0:
            await interaction.response.send_message("通すメンバーを選択",view=DCReprintMembersView(self.boss_num,interaction.guild,False,interaction.message),ephemeral=True)
        else:
            await interaction.response.send_message("メンバーがいません",ephemeral=True)
    @discord.ui.button(label="〆指示",style=discord.ButtonStyle.blurple)
    async def finish_button(self,interaction:discord.Interaction,button):
        members=db.execute(f"SELECT No,id FROM dc_{interaction.guild.id} WHERE boss = {self.boss_num} AND done = 0")
        if len(members)>0:
            await interaction.response.send_message("通すメンバーを選択",view=DCReprintMembersView(self.boss_num,interaction.guild,True,interaction.message),ephemeral=True)
        else:
            await interaction.response.send_message("メンバーがいません",ephemeral=True)
    @discord.ui.button(label="指示キャンセル",style=discord.ButtonStyle.red)
    async def cancel_button(self,interaction:discord.Interaction,button):
        members=db.execute(f"SELECT No,id FROM dc_{interaction.guild.id} WHERE boss = {self.boss_num} AND done = 1")
        if len(members)>0:
            await interaction.response.send_message("キャンセルするメンバーを選択",view=DCReprintCancelMembersView(self.boss_num,interaction.guild,interaction.message),ephemeral=True)
        else:
            await interaction.response.send_message("メンバーがいません",ephemeral=True)
    @discord.ui.button(label="連携終了",style=discord.ButtonStyle.gray)
    async def kaihou_button(self,interaction:discord.Interaction,button):
        await interaction.response.send_message("連携を終了しますか？",view=KaihouConfirmView(self.boss_num),ephemeral=True)
    @discord.ui.button(row=2,label="ダメージリスト",style=discord.ButtonStyle.green)
    async def damagelist_button(self,interaction:discord.Interaction,button):
        await interaction.response.send_message("",view=DamageListView(interaction.guild,self.boss_num),ephemeral=True)
        

class DCReprintMembersView(discord.ui.View):
    def __init__(self,boss_num,guild,last_attack,original_message):
        super().__init__(timeout=240)
        self.add_item(DCReprintMembersSelect(boss_num,guild,last_attack,original_message))
class DCReprintMembersSelect(discord.ui.Select):
    def __init__(self,boss_num,guild:discord.Guild,last_attack,original_message):
        self.boss_num=boss_num
        self.guild=guild
        self.last_attack=last_attack
        self.original_message=original_message
        self.members=db.execute(f"SELECT No,id,status,damage FROM dc_{guild.id} WHERE boss = {self.boss_num} AND done = 0 ORDER BY damage DESC")
        self.names=[guild.get_member(v[1]).display_name for v in self.members]
        options=[]
        if len(self.members)>=1:
            for i,m in enumerate(self.members):
                options.append(discord.SelectOption(label=f"{self.names[i]}　{m[2]}　{m[3]}",value=str(i)))
        max_values=1 if last_attack else 20
        super().__init__(options=options[:20],max_values=min(max_values,len(options)))
    async def callback(self, interaction: discord.Interaction):
        res="〆指示\n" if self.last_attack else "通し指示\n"
        res+="以下のメンバーにメンションを送ります\n"
        for idx in self.values:
            res+=f"<@{self.members[int(idx)][1]}>\n"
        await interaction.response.edit_message(content=res,view=DCReprintConfirmView(self.boss_num,self.last_attack,self.members,self.values,self.original_message))


class DCReprintConfirmView(discord.ui.View):
    def __init__(self,boss_num,last_attack,members,selected,original_message:discord.Message):
        super().__init__(timeout=240)
        self.boss_num=boss_num
        self.last_attack=last_attack
        self.members=members
        self.selected=selected
        self.original_message=original_message
        self.check=False
    async def interaction_check(self, interaction):
        if self.check:
            return False
        self.check=True
        return True
    @discord.ui.button(label="OK",style=discord.ButtonStyle.green)
    async def ok_button(self,interaction:discord.Interaction,button):
        async def del_mochi_reaction(member_id,boss):
            msg_id=db.read_guild("reaction_mochi_msg",interaction.guild_id)
            if msg_id != None:
                try:
                    ch_id=db.read_guild("reaction_ch",interaction.guild_id)
                    m_message=interaction.guild.get_channel(ch_id).get_partial_message(msg_id)
                    member=interaction.guild.get_member(member_id)
                    await m_message.remove_reaction(bytes.fromhex(f"3{str(boss)}e283a3").decode("utf-8"),member)
                except:
                    return
        res="〆　" if self.last_attack else "通し\n"
        # 新しいメッセージ送信
        if self.last_attack:
            await interaction.response.defer(ephemeral=True)
        else:
            send=await interaction.channel.send(self.original_message.content,view=DCReprintView(self.boss_num),silent=True)
            await interaction.response.defer(ephemeral=True)
            global dc_reprint
            await dc_reprint[interaction.guild_id][self.boss_num-1].delete()
            dc_reprint[interaction.guild_id][self.boss_num-1]=send
            self.original_message=send
        
        # 先にメンションを送る
        for idx in self.selected:
            res+=interaction.guild.get_member(self.members[int(idx)][1]).mention+"\n"
        send=await interaction.channel.send(content=res)
        members_list=[]
        name_update=[]

        

        for idx in self.selected:
            db.execute(f"UPDATE dc_{interaction.guild_id} SET done = 1 WHERE No = {self.members[int(idx)][0]}")
            
            is_mochi=db.execute(f"SELECT status FROM dc_{interaction.guild_id} WHERE No = {self.members[int(idx)][0]}")
            mochi=db.read_member(interaction.guild_id,"mochi",self.members[int(idx)][1])
            if is_mochi != None and is_mochi[0][0][1] == "🔄":
                if mochi != None:
                    maxdamage=db.execute(f"SELECT MAX(damage) FROM dc_{interaction.guild_id} WHERE boss = {self.boss_num}")[0][0]
                    damage=db.execute(f"SELECT damage FROM dc_{interaction.guild_id} WHERE No = {self.members[int(idx)][0]}")[0][0]
                    mochi_slice=[str(mochi)[i:i+2] for i in range(0,len(str(mochi)),2)]
                    rep=0
                    # 短い持ち越し削除
                    if damage < maxdamage/2:
                        if f"2{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(interaction.guild,self.members[int(idx)][1],int(f"2{self.boss_num}"))
                            mochi_slice.remove(f"2{self.boss_num}")
                            rep=int("".join(mochi_slice)) if len(mochi_slice)>0 else 0
                        # フル持ち越し削除
                        elif f"3{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(interaction.guild,self.members[int(idx)][1],int(f"3{self.boss_num}"))
                            mochi_slice.remove(f"3{self.boss_num}")
                            rep=int("".join(mochi_slice)) if len(mochi_slice)>0 else 0
                            await del_mochi_reaction(self.members[int(idx)][1],self.boss_num)
                        # 長い持ち越し削除
                        elif f"1{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(interaction.guild,self.members[int(idx)][1],int(f"1{self.boss_num}"))
                            mochi_slice.remove(f"1{self.boss_num}")
                            rep=int("".join(mochi_slice)) if len(mochi_slice)>0 else 0
                            await del_mochi_reaction(self.members[int(idx)][1],self.boss_num)
                    else:
                        if f"3{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(interaction.guild,self.members[int(idx)][1],int(f"3{self.boss_num}"))
                            mochi_slice.remove(f"3{self.boss_num}")
                            rep=int("".join(mochi_slice)) if len(mochi_slice)>0 else 0
                            await del_mochi_reaction(self.members[int(idx)][1],self.boss_num)
                        elif f"1{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(interaction.guild,self.members[int(idx)][1],int(f"1{self.boss_num}"))
                            mochi_slice.remove(f"1{self.boss_num}")
                            rep=int("".join(mochi_slice)) if len(mochi_slice)>0 else 0
                            await del_mochi_reaction(self.members[int(idx)][1],self.boss_num)
                        # 短い持ち越し削除
                        elif f"2{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(interaction.guild,self.members[int(idx)][1],int(f"2{self.boss_num}"))
                            mochi_slice.remove(f"2{self.boss_num}")
                            rep=int("".join(mochi_slice)) if len(mochi_slice)>0 else 0
                    db.write_member(interaction.guild_id,self.members[int(idx)][1],"mochi",rep)
                name_update.append((self.members[int(idx)][1],0,-1))
            else:
                members_list.append(self.members[int(idx)])
                if self.last_attack:
                    name_update.append((self.members[int(idx)][1],-1,1))
                else:
                    name_update.append((self.members[int(idx)][1],-1,0))
            global prev_mochi
            if not interaction.guild_id in prev_mochi:
                prev_mochi[interaction.guild_id]=[[],[],[],[],[]]
            prev_mochi[interaction.guild_id][self.boss_num-1].append((self.members[int(idx)][0],mochi))
            
        content=Generator.dc_content(interaction.guild,self.boss_num)
        dc_message=interaction.guild.get_channel(db.read_guild("dc_ch",interaction.guild_id)).get_partial_message(db.read_guild("dc_msg",interaction.guild_id).split("\n")[self.boss_num-1])
        await dc_message.edit(content=content)
        await dc_reprint[interaction.guild_id][self.boss_num-1].edit(content=content) 
        await DC.table_change(interaction.guild,self.boss_num,members_list,True)
        prev_message.add(interaction.guild_id,send.id,self.boss_num,[self.members[int(idx)][0] for idx in self.selected],self.last_attack)
        if self.last_attack:
            if len(members_list) > 0:
                await interaction.edit_original_response(content="持ち越しを選択",view=DCMochiSelectView(interaction.guild_id,members_list[0]))
            else:
                await interaction.delete_original_response()
        else:
            await interaction.delete_original_response()
        # 名前を更新
        for m in name_update:
            global prev_name
            prev=interaction.guild.get_member(m[0]).display_name
            is_finish=await DC.zan_update(m[0],interaction.guild,m[1],m[2])
            global finish_members
            if not interaction.guild_id in finish_members:
                finish_members[interaction.guild_id]=[[],[],[],[],[]]
            if is_finish:
                finish_members[interaction.guild_id][self.boss_num-1].append(m[0])
            prev_name.add(interaction.guild_id,m[0],prev,self.boss_num)
        
        SpreadSheetDC.write(interaction.guild,self.boss_num)
    @discord.ui.button(label="取り消し",style=discord.ButtonStyle.red)
    async def cancel_button(self,interaction:discord.Interaction,button):
        await interaction.response.edit_message(content="取り消しました",view=None)


class DCReprintCancelMembersView(discord.ui.View):
    def __init__(self,boss_num,guild,original_message):
        super().__init__(timeout=240)
        self.add_item(DCReprintCancelMembersSelect(boss_num,guild,original_message))
class DCReprintCancelMembersSelect(discord.ui.Select):
    def __init__(self,boss_num,guild:discord.Guild,original_message):
        self.boss_num=boss_num
        self.guild=guild
        self.original_message=original_message
        self.members=db.execute(f"SELECT No,id FROM dc_{guild.id} WHERE boss = {self.boss_num} AND done = 1 ORDER BY No DESC")
        self.names=[guild.get_member(v[1]).display_name for v in self.members]
        options=[]
        ids=[]
        if len(self.members)>=1:
            for i,m in enumerate(self.members):
                if m[1] in ids:
                    continue
                ids.append(m[1])
                options.append(discord.SelectOption(label=self.names[i],value=str(i)))
        max_values=20
        super().__init__(options=options[:20],max_values=min(max_values,len(options)))
    async def callback(self, interaction: discord.Interaction):
        res="指示キャンセル\n以下のメンバーにメンションを送ります\n"
        for idx in self.values:
            res+=f"<@{self.members[int(idx)][1]}>\n"
        await interaction.response.edit_message(content=res,view=DCReprintCancelConfirmView(self.boss_num,self.members,self.values,self.original_message))


class DCReprintCancelConfirmView(discord.ui.View):
    def __init__(self,boss_num,members,selected,original_message:discord.Message):
        super().__init__(timeout=240)
        self.boss_num=boss_num
        self.members=members
        self.selected=selected
        self.original_message=original_message
    @discord.ui.button(label="OK",style=discord.ButtonStyle.green)
    async def ok_button(self,interaction:discord.Interaction,button):
        def find(No):
            global prev_mochi
            if not interaction.guild_id in prev_mochi:
                return -1
            for i,m in enumerate(prev_mochi[interaction.guild_id][self.boss_num-1]):
                if m[0] == No:
                    return prev_mochi[interaction.guild_id][self.boss_num-1].pop(i)[1]
            return -1
        await interaction.response.edit_message(view=None)
        await interaction.delete_original_response()
        res="キャンセル\n"
        # 新しいメッセージ送信
        
        send=await interaction.channel.send(self.original_message.content,view=DCReprintView(self.boss_num),silent=True)
        global dc_reprint
        await dc_reprint[interaction.guild_id][self.boss_num-1].delete()
        dc_reprint[interaction.guild_id][self.boss_num-1]=send
        self.original_message=send
        
        # 先にメンションを送る
        for idx in self.selected:
            res+=interaction.guild.get_member(self.members[int(idx)][1]).mention+"\n"
        await interaction.channel.send(content=res)


        members_list=[]
        message_ids=[]
        for idx in self.selected:
            db.execute(f"UPDATE dc_{interaction.guild_id} SET done = 0 WHERE No = {self.members[int(idx)][0]}")
            prev=find(self.members[int(idx)][0])
            if prev != -1:
                if prev != None and prev > 0:
                    db.write_member(interaction.guild_id,self.members[int(idx)][1],"mochi",prev)
                else:
                    db.delete_member(interaction.guild_id,self.members[int(idx)][1],"mochi")
                MochiTableHelper.undo(interaction.guild,self.members[int(idx)][1])
            members_list.append(self.members[int(idx)])
            message_ids.append(prev_message.delete_No(interaction.guild_id,self.members[int(idx)][0]))
            # 3凸完了リスト削除
            global finish_members
            if interaction.guild_id in finish_members and self.members[int(idx)][1] in finish_members[interaction.guild_id][self.boss_num-1]:
                finish_members[interaction.guild_id][self.boss_num-1].remove(self.members[int(idx)][1])
        ###############
        # メンション削除
        for message_id in set(message_ids):
            try:
                pm=interaction.channel.get_partial_message(message_id)
                c=prev_message.content(interaction.guild_id,message_id)
                if c != None:
                    await pm.edit(content=c)
                else:
                    await pm.delete()
            except:
                continue
        ###############
        content=Generator.dc_content(interaction.guild,self.boss_num)
        dc_message=interaction.guild.get_channel(db.read_guild("dc_ch",interaction.guild_id)).get_partial_message(db.read_guild("dc_msg",interaction.guild_id).split("\n")[self.boss_num-1])
        await dc_message.edit(content=content)
        await self.original_message.edit(content=content) 
        await DC.table_change(interaction.guild,self.boss_num,members_list,False)
        global prev_name
        for idx in self.selected:
            prev=prev_name.get(interaction.guild_id,self.members[int(idx)][1])
            if prev != None:
                try:
                    m = interaction.guild.get_member(self.members[int(idx)][1])
                    await m.edit(nick=prev)
                except:
                    pass
        SpreadSheetDC.write(interaction.guild,self.boss_num)
    @discord.ui.button(label="取り消し",style=discord.ButtonStyle.red)
    async def cancel_button(self,interaction:discord.Interaction,button):
        await interaction.response.edit_message(content="取り消しました",view=None)
    








class DCMochiSelectView(discord.ui.View):
    def __init__(self,guild_id,member_id,prev=None):
        if isinstance(member_id,int):
            self.member_id=member_id
        else:
            self.member_id=member_id[1]
        if prev != None:
            self.prev=prev
        else:
            self.prev=db.read_member(guild_id,"mochi",self.member_id)
            if self.prev==None:
                self.prev=0
        super().__init__(timeout=240)
    async def update(self,guild:discord.Guild):
        message=guild.get_channel(db.read_guild("reaction_ch",guild.id)).get_partial_message(db.read_guild("reaction_msg",guild.id))
        await message.add_reaction("〰")
    @discord.ui.button(label="1フル",style=discord.ButtonStyle.blurple,row=0)
    async def boss1full_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+31)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="１ボスフル持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="1長餅",style=discord.ButtonStyle.blurple,row=0)
    async def boss1long_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+11)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="１ボス長い持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="1小餅",style=discord.ButtonStyle.gray,row=0)
    async def boss1short_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+21)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="１ボス短い持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="2フル",style=discord.ButtonStyle.blurple,row=1)
    async def boss2full_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+32)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="2ボスフル持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="2長餅",style=discord.ButtonStyle.blurple,row=1)
    async def boss2long_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+12)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="2ボス長い持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="2小餅",style=discord.ButtonStyle.gray,row=1)
    async def boss2short_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+22)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="2ボス短い持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="3フル",style=discord.ButtonStyle.blurple,row=2)
    async def boss3full_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+33)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="3ボスフル持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="3長餅",style=discord.ButtonStyle.blurple,row=2)
    async def boss3long_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+13)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="3ボス長い持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="3小餅",style=discord.ButtonStyle.gray,row=2)
    async def boss3short_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+23)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="3ボス短い持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="4フル",style=discord.ButtonStyle.blurple,row=3)
    async def boss4full_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+34)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="4ボスフル持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="4長餅",style=discord.ButtonStyle.blurple,row=3)
    async def boss4long_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+14)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="4ボス長い持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="4小餅",style=discord.ButtonStyle.gray,row=3)
    async def boss4short_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+24)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="4ボス短い持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="5フル",style=discord.ButtonStyle.blurple,row=4)
    async def boss5full_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+35)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="5ボスフル持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="5長餅",style=discord.ButtonStyle.blurple,row=4)
    async def boss5long_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+15)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="5ボス長い持ち越し",view=DCMochiEditView(self.member_id,self.prev))
    @discord.ui.button(label="5小餅",style=discord.ButtonStyle.gray,row=4)
    async def boss5short_button(self,interaction:discord.Interaction,button):
        db.write_member(interaction.guild_id,self.member_id,"mochi",self.prev*100+25)
        await self.update(interaction.guild)
        await interaction.response.edit_message(content="5ボス短い持ち越し",view=DCMochiEditView(self.member_id,self.prev))

class DCMochiEditView(discord.ui.View):
    def __init__(self,member_id,prev):
        self.member_id=member_id
        self.prev=prev
        super().__init__(timeout=240)
    @discord.ui.button(label="持ち越し変更",style=discord.ButtonStyle.gray)
    async def edit_button(self,interaction:discord.Interaction,button):
            await interaction.response.edit_message(content="持ち越しを選択",view=DCMochiSelectView(interaction.guild_id,self.member_id,self.prev))


class KaihouConfirmView(discord.ui.View):
    def __init__(self,boss_num):
        self.boss_num=boss_num
        super().__init__(timeout=240)
    @discord.ui.button(label="OK",style=discord.ButtonStyle.green)
    async def ok_button(self,interaction:discord.Interaction,button):
        await interaction.response.edit_message(view=None)
        await interaction.delete_original_response()
        """
        mentions_id=db.execute(f"SELECT id FROM dc_{interaction.guild_id} WHERE boss = {self.boss_num} AND done <> 1")
        mentions=""
        for mention_id in mentions_id:
            mentions+=f"<@{mention_id[0]}> "
        text="開放"
        if interaction.guild_id == 0:
            text=mentions + f"\n{self.boss_num}ボス開放"

        await interaction.channel.send(text)
        """
        def get_sticker(guild:discord.Guild,id:int):
            for sticker in guild.stickers:
                if sticker.id == id:
                    return [sticker]
            return None
        if interaction.guild_id == 1276184060791750656:
            match self.boss_num:
                case 1:
                    await interaction.channel.send(stickers=get_sticker(interaction.guild,1343949879013281802))
                case 2:
                    await interaction.channel.send(stickers=get_sticker(interaction.guild,1354476245290586223))
                case 3:
                    await interaction.channel.send(stickers=get_sticker(interaction.guild,1343950149029859339))
                case 4:
                    await interaction.channel.send(stickers=get_sticker(interaction.guild,1343950198967111843))
                case 5:
                    await interaction.channel.send(stickers=get_sticker(interaction.guild,1343950249546350673))
            await asyncio.sleep(0.5)

        # ダメコン終了
        members=db.execute(f"SELECT * FROM dc_{interaction.guild_id} WHERE boss = {self.boss_num}")
        db.execute(f"DELETE FROM dc_{interaction.guild_id} WHERE boss = {self.boss_num}")

        message_ch=db.read_guild("dc_ch",interaction.guild_id)
        message_id=db.read_guild("dc_msg",interaction.guild_id).split()[self.boss_num-1]
        message=interaction.guild.get_channel(message_ch).get_partial_message(int(message_id))
        fetch_message=await message.fetch()
        fetch_content=fetch_message.content
        content=Generator.dc_content(interaction.guild,self.boss_num)
        await fetch_message.edit(content=content)

        await message.clear_reactions()
        await message.add_reaction("🔄")
        await message.add_reaction(discord.PartialEmoji.from_str("<:syu:1271379304919465995> "))
        await message.add_reaction("🔼")
        await message.add_reaction("🔻")
        await message.add_reaction("🔥")
        await message.add_reaction("❌")
        await message.add_reaction("✅")
        await message.add_reaction("👉")
        log=None
        if db.read_guild("log_ch",interaction.guild_id)!=None:
            log=await interaction.guild.get_channel(db.read_guild("log_ch",interaction.guild_id)).send(fetch_content)
        prev_stat={"dc_reprint":None,"table_reaction":[],"prev_mochi":[]}
        global dc_reprint
        if message.guild.id in dc_reprint and dc_reprint[message.guild.id][self.boss_num-1] != None:
            global table_reaction
            if message.guild.id in table_reaction:
                prev_stat["table_reaction"]=table_reaction[message.guild.id][self.boss_num-1]
                table_reaction[message.guild.id][self.boss_num-1]=[]
            prev_stat["dc_reprint"]=dc_reprint[message.guild.id][self.boss_num-1]
            dc_reprint[message.guild.id][self.boss_num-1]=None
        global prev_mochi
        if interaction.guild.id in prev_mochi:
            prev_stat["prev_mochi"]=prev_mochi[interaction.guild.id][self.boss_num-1]
            prev_mochi[interaction.guild.id][self.boss_num-1]=[]
        prev_stat["prev_message"]=prev_message.delete_boss(message.guild.id,self.boss_num)
        prev_stat["prev_name"]=prev_name.delete(interaction.guild_id,self.boss_num)

        await interaction.guild.get_channel(message_ch).send("討伐されました",view=DCCompleteView(members,log,fetch_content,self.boss_num,prev_stat),delete_after=60,reference=message)
        SpreadSheetDC.write(interaction.guild,self.boss_num)
    
        # 完凸した人にメンション
        global finish_members
        mention_members=[]
        if interaction.guild_id in finish_members:
            for member_id in finish_members[interaction.guild_id][self.boss_num-1]:
                is_finish=db.read_member(interaction.guild_id,"finish",member_id)
                if is_finish == None:
                    mention_members.append(member_id)
            finish_members[interaction.guild_id][self.boss_num-1]=[]
        if len(mention_members) > 0:
            names=[f"<@{v}>" for v in mention_members]
    @discord.ui.button(label="取り消し",style=discord.ButtonStyle.red)
    async def cancel_button(self,interaction:discord.Interaction,button):
        await interaction.response.edit_message(content="取り消しました",view=None)










class DamageListView(discord.ui.LayoutView):
    def __init__(self,guild:discord.Guild,boss_num):
        super().__init__(timeout=360)
        self.boss_num=boss_num
        self.damage_list=[]
        self.member_select_row.add_item(DamageListMembers(boss_num,guild,self))
        self.multiplier=1
        self.button1_1.disabled=True
        members=db.execute(f"SELECT damage FROM dc_{guild.id} WHERE boss = {self.boss_num} AND done = 0 ORDER BY damage DESC")
        for member in members:
            if int(member[0]) > 0:
                self.damage_list.append(member[0])
        self.gen_content()
    
    def gen_content(self):
        content=""
        if len(self.damage_list) > 0:
            for damage in self.damage_list:
                content+=f" {math.floor(damage*self.multiplier)}"
            self.result_text.content=content
        else:
            self.result_text.content="結果が表示されます"
        
    
    result_text=discord.ui.TextDisplay("結果が表示されます")



        
    
    member_select_row=discord.ui.ActionRow()
    
    acrion_row = discord.ui.ActionRow()

    @acrion_row.button(label="1/1")
    async def button1_1(self,interaction:discord.Interaction,button):
        self.multiplier=1
        self.gen_content()
        self.button1_1.disabled=True
        self.button1_10.disabled=False
        self.button1_100.disabled=False
        self.button1_1000.disabled=False
        await interaction.response.edit_message(view=self)
    @acrion_row.button(label="1/10")
    async def button1_10(self,interaction:discord.Interaction,button):
        self.multiplier=0.1
        self.gen_content()
        self.button1_1.disabled=False
        self.button1_10.disabled=True
        self.button1_100.disabled=False
        self.button1_1000.disabled=False
        await interaction.response.edit_message(view=self)
    @acrion_row.button(label="1/100")
    async def button1_100(self,interaction:discord.Interaction,button):
        self.multiplier=0.01
        self.gen_content()
        self.button1_1.disabled=False
        self.button1_10.disabled=False
        self.button1_100.disabled=True
        self.button1_1000.disabled=False
        await interaction.response.edit_message(view=self)
    @acrion_row.button(label="1/1000")
    async def button1_1000(self,interaction:discord.Interaction,button):
        self.multiplier=0.001
        self.gen_content()
        self.button1_1.disabled=False
        self.button1_10.disabled=False
        self.button1_100.disabled=False
        self.button1_1000.disabled=True
        await interaction.response.edit_message(view=self)
    


class DamageListMembers(discord.ui.Select):
    def __init__(self,boss_num,guild:discord.Guild,view:DamageListView):
        self.boss_num=boss_num
        self.guild=guild
        self.editview=view
        self.members=db.execute(f"SELECT No,id,status,damage FROM dc_{guild.id} WHERE boss = {self.boss_num} AND done = 0 ORDER BY damage DESC")
        self.names=[guild.get_member(v[1]).display_name for v in self.members]
        options=[]
        if len(self.members)>=1:
            for i,m in enumerate(self.members):
                options.append(discord.SelectOption(label=f"{self.names[i]}　{m[2]}　{m[3]}",value=str(i)))
        
        super().__init__(options=options[:20],max_values=min(20,len(options)))
    async def callback(self, interaction: discord.Interaction):
        damage_list=[]
        for idx in sorted(self.values):
            damage_list.append(self.members[int(idx)][3])
        self.editview.damage_list=damage_list
        self.editview.gen_content()
        await interaction.response.edit_message(view=self.editview)





















class DC(commands.Cog):
    def __init__(self,bot:commands.Bot):
        self.bot=bot
        self.bot.add_view(SuspendView())
        self.bot.add_view(DCReprintDCMessageView())
        self.DC_timer={}
        self.syudou=discord.PartialEmoji.from_str("<:syu:1271379304919465995> ")
    
    
    async def dc_unknown(self,guild_id):
        """不明な凸宣言者"""

        members=db.execute(f"SELECT dc_{guild_id}.id FROM dc_{guild_id} \
                INNER JOIN member_{guild_id} ON dc_{guild_id}.id = member_{guild_id}.id \
                WHERE dc_{guild_id}.boss IS NULL")
        
        if len(members)>0:
            content="不明な凸宣言者"
            for member in members:
                content+="\n"+self.bot.get_guild(guild_id).get_member(member[0]).display_name
            
            try:

                dc_message=await self.bot.get_channel(db.read_guild("dc_ch",guild_id)).fetch_message(db.read_guild("unknown_msg",guild_id))
                await dc_message.edit(content=content)

            except:

                send=await self.bot.get_channel(db.read_guild("dc_ch",guild_id)).send(content)
                await send.add_reaction("❌")
                db.write_guild(guild_id,"unknown_msg",send.id)
        
        # 不明な凸宣言者がいない場合。メッセージを削除する
        else:
            try:
                dc_message=self.bot.get_channel(db.read_guild("dc_ch",guild_id)).get_partial_message(db.read_guild("unknown_msg",guild_id))
                db.delete_guild(guild_id,"unknown_msg")
                await dc_message.delete()
            except:
                pass


                

    @commands.command()
    async def dc_set(self,ctx:commands.Context,channel:discord.TextChannel=None):

        dc_msg=""
        name=db.read_guild("dc_name",ctx.guild.id)

        # 名前が決まっていない場合にデフォルトで用意する
        if name==None:
            name=["1ボス","2ボス","3ボス","4ボス","5ボス"]
            db.write_guild(ctx.guild.id,"dc_name","\n".join(name))
        else:
            name=name.split("\n")
        
        # メッセージを送信するチャンネル
        _channel=channel if channel != None else ctx.channel

        for i in range(5):
            send=await _channel.send(f">>> # {name[i]}\n＿＿＿＿＿＿＿＿＿\n\nㅤ",view=DCReprintDCMessageView())
            await send.add_reaction("🔄")
            await send.add_reaction(self.syudou)
            await send.add_reaction("🔼")
            await send.add_reaction("🔻")
            await send.add_reaction("🔥")
            await send.add_reaction("❌")
            await send.add_reaction("✅")
            await send.add_reaction("👉")
            dc_msg+=str(send.id)+"\n"
            
        db.write_guild(ctx.guild.id,"dc_ch",_channel.id)
        db.write_guild(ctx.guild.id,"dc_msg",dc_msg[:-1])
        await ctx.message.delete()
        
    
    @app_commands.command(name="dc",description="ダメコンの操作")
    @app_commands.guild_only()
    async def dc_slash(self,interaction:discord.Interaction,mode:Literal["ボス名変更","1ボス操作","2ボス操作","3ボス操作","4ボス操作","5ボス操作"]):
        """ダメコンのスラッシュコマンド"""
        if db.read_guild("dc_ch",interaction.guild_id)==None:
            await interaction.response.send_message("ダメコンのチャンネルが見つかりませんでした",ephemeral=True)
            return
        if mode=="ボス名変更":
            names=db.read_guild("dc_name",interaction.guild_id).split("\n")
            await interaction.response.send_modal(DCBossRenameModal(names))
        else:
            boss_num=int(mode[0])
            if len(db.execute(f"SELECT id FROM dc_{interaction.guild_id} WHERE boss = {boss_num}"))>=1:
                await interaction.response.send_message(mode[0],view=DCManageView(interaction.guild,boss_num),ephemeral=True)
            else:
                await interaction.response.send_message("ダメージは入力されえいません",ephemeral=True)
            



    @commands.Cog.listener("on_message")
    @DpyDecorator.member_check
    async def damage_enter(self,message:discord.Message):
        """ダメージ入力"""
        if message.content != "" and message.content[0].isdigit() and message.channel.id==db.read_guild("dc_ch",message.guild.id):
            sengen=db.execute(f"SELECT boss FROM dc_{message.guild.id}\
                        WHERE id = {message.author.id} AND done > 1000")
            try:
                if len(sengen) >= 1:
                    await message.add_reaction(bytes.fromhex(f"3{sengen[0][0]}e283a3").decode("utf-8"))
                    await asyncio.sleep(0.3)
                await message.add_reaction("\u0031\ufe0f\u20e3")
                await asyncio.sleep(0.3)
                await message.add_reaction("\u0032\ufe0f\u20e3")
                await asyncio.sleep(0.3)
                await message.add_reaction("\u0033\ufe0f\u20e3")
                await asyncio.sleep(0.3)
                await message.add_reaction("\u0034\ufe0f\u20e3")
                await asyncio.sleep(0.3)
                await message.add_reaction("\u0035\ufe0f\u20e3")
            except:
                pass
        # 代行
        elif message.content != "" and len(message.mentions) == 1:
            mentionless_content=message.content.replace(message.mentions[0].mention,"").strip()
            if mentionless_content != "" and mentionless_content[0].isdigit() and message.channel.id==db.read_guild("dc_ch",message.guild.id):
                try:
                    await message.add_reaction("\u0031\ufe0f\u20e3")
                    await message.add_reaction("\u0032\ufe0f\u20e3")
                    await message.add_reaction("\u0033\ufe0f\u20e3")
                    await message.add_reaction("\u0034\ufe0f\u20e3")
                    await message.add_reaction("\u0035\ufe0f\u20e3")
                except:
                    pass


    @commands.Cog.listener("on_message_edit")
    @DpyDecorator.member_check
    async def edit_damage(self,before:discord.Message,after:discord.Message):
        if after.content != "" and after.content[0].isdigit() and after.channel.id==db.read_guild("dc_ch",after.guild.id):
            emojis=[r.emoji for r in after.reactions]
            for emoji in ["\u0031\ufe0f\u20e3","\u0032\ufe0f\u20e3","\u0033\ufe0f\u20e3","\u0034\ufe0f\u20e3","\u0035\ufe0f\u20e3"]:
                if emoji not in emojis:
                    await after.add_reaction(emoji)
    


    @commands.Cog.listener("on_message")
    @DpyDecorator.member_check
    async def reply_dc(self,message:discord.Message):
        try:
            if message.reference != None and str(message.reference.message_id) in db.read_guild("dc_msg",message.guild.id).split("\n"):
                boss=db.read_guild("dc_msg",message.guild.id).split("\n").index(str(message.reference.message_id))+1
                if message.content[0].isdigit():
                    damage=max(map(lambda x:int(re.match(r"\d+",x).group()) if re.match(r"\d+",x) else 0,message.content.split()[:3]))
                    conn=sqlite3.connect(db.dbname)
                    cur=conn.cursor()

                    cur.execute(f'''CREATE TABLE IF NOT EXISTS dc_{message.guild.id} (
                        No INTEGER PRIMARY KEY,
                        id INTEGER,
                        boss INTEGER,
                        status TEXT,
                        damage INTEGER,
                        text TEXT,
                        done INTEGER
                        )''')
                    
                    # 凸宣言メッセージを取得し持ち越しか確認
                    try:
                        cur.execute(f"SELECT done FROM dc_{message.guild.id} WHERE id = {message.author.id} AND (boss = {boss} OR boss IS NULL) AND done > 1000")
                        mochi_id=cur.fetchone()[0]
                        cur.execute(f"SELECT sengen_ch FROM guild WHERE id = {message.guild.id}")
                        mochi_channel=cur.fetchone()[0]
                        mochi_message=await message.guild.get_channel(mochi_channel).fetch_message(mochi_id)
                        is_mochi=bool(re.search(r"[餅持]",mochi_message.content))
                    except:
                        is_mochi=False
                    mochi="🔄" if is_mochi else "🔲"


                    # 凸宣言を削除し、ダメージを登録する
                    cur.execute(f"DELETE FROM dc_{message.guild.id}\
                        WHERE id = {message.author.id} AND (boss = {boss} OR boss IS NULL) AND done > 1000")
                    
                    cur.execute(f"SELECT No FROM dc_{message.guild.id}\
                        WHERE id = {message.author.id} AND boss = {boss} AND done = 0")
                    
                    # 既に登録されているダメージの情報
                    prev=cur.fetchone()

                    if prev != None and bool(len(prev)):
                        # 上書き
                        cur.execute(f"UPDATE dc_{message.guild.id} SET status = '¦{mochi}¦🔲¦🔲¦',damage = {damage},text = '{message.content}'\
                            WHERE No = {prev[0]}")
                    else:
                        # 新規
                        cur.execute(f"INSERT INTO dc_{message.guild.id} (No,id,boss,status,damage,text,done)\
                            VALUES ({int(message.created_at.timestamp()*1000)},{message.author.id},{boss},'¦{mochi}¦🔲¦🔲¦',{damage},'{message.content}',0)")
                    
                    conn.commit()
                    conn.close()

                    self.timer_set(message.guild.id,boss)
                    await message.delete()
                    await DC.dc_unknown(self,message.guild.id)
                else:
                    names=db.read_guild("dc_name",message.guild.id).split("\n")
                    names[boss-1]=message.content
                    db.write_guild(message.guild.id,"dc_name","\n".join(names))

                    self.timer_set(message.guild.id,boss)
                    await message.delete()
        except:
            pass




    @commands.Cog.listener("on_message")
    @DpyDecorator.member_check
    async def sengen(self,message:discord.Message):
        """凸宣言"""
        if message.channel.id == db.read_guild("sengen_ch",message.guild.id) and db.read_guild("suspend_sengen",message.guild.id) == None:
            if message.content[0]==".":
                return
            boss=None
            if re.search("[1-5１-５](ボス|ぼす|ﾎﾞｽ|boss)",message.content):
                boss=int(re.search("[1-5１-５](ボス|ぼす|ﾎﾞｽ|boss)",message.content).group()[0])
            elif re.search(r"([^\d]|^)\d([^凸\d]|$)",message.content):
                tmp=int(re.search(r"([^\d]|^)\d([^凸\d]|$)",message.content).group()[0])
                boss = tmp if 1<= tmp <= 5 else None
            
            db.execute(f'''CREATE TABLE IF NOT EXISTS dc_{message.guild.id} (
                        No INTEGER PRIMARY KEY,
                        id INTEGER,
                        boss INTEGER,
                        status TEXT,
                        damage INTEGER,
                        text TEXT,
                        done INTEGER
                        )''')
            
            
            if boss!=None:
                db.execute(f"DELETE FROM dc_{message.guild.id} WHERE boss = {boss} AND done > 1000 AND id = {message.author.id}")
                db.execute(f"INSERT INTO dc_{message.guild.id} (No,id,boss,done) SELECT {int(message.created_at.timestamp()*1000)},{message.author.id},{boss},{message.id}")
                self.timer_set(message.guild.id,boss)
            
            # 不明な凸宣言者にぶち込む
            else:
                db.execute(f"DELETE FROM dc_{message.guild.id} WHERE boss IS NULL AND done > 1000 AND id = {message.author.id}")
                db.execute(f"INSERT INTO dc_{message.guild.id} (No,id,done) SELECT {int(message.created_at.timestamp()*1000)},{message.author.id},{message.id}")
                await DC.dc_unknown(self,message.guild.id)
    
    @app_commands.command(name="suspend_sengen",description="凸宣言を無効にします")
    @app_commands.guild_only()
    async def suspend_sengen(self,interaction:discord.Interaction):
        try:
            ch=interaction.guild.get_channel(db.read_guild("dc_ch",interaction.guild_id))
            send=await ch.send("凸宣言を無効にしました",view=SuspendView())
            db.write_guild(interaction.guild_id,"suspend_sengen",send.id)
            await interaction.response.send_message("凸宣言を無効にしました",ephemeral=True)
        except:
            await interaction.response.send_message("ダメコンのチャンネルが見つかりません",ephemeral=True)
    
    @commands.Cog.listener("on_raw_message_delete")
    async def suspend_sengen_delete(self,payload:discord.RawMessageDeleteEvent):
        if payload.message_id==db.read_guild("suspend_sengen",payload.guild_id):
            db.delete_guild(payload.guild_id,"suspend_sengen")


    @commands.Cog.listener("on_raw_message_delete")
    async def unknown_delete(self,payload:discord.RawMessageDeleteEvent):
        """不明な凸宣言者のメッセージの削除"""
        if payload.message_id==db.read_guild("unknown_msg",payload.guild_id):
            db.delete_guild(payload.guild_id,"unknown_msg")
            db.execute(f"DELETE FROM dc_{payload.guild_id} WHERE boss IS NULL AND done > 1000")



    @commands.Cog.listener("on_raw_reaction_add")
    @DpyDecorator.member_check
    async def damage_reaction(self,payload:discord.RawReactionActionEvent):
        """ダメコンに関するメッセージにリアクションした際の処理"""
        try:
            if payload.emoji.name in ["\u0031\ufe0f\u20e3","\u0032\ufe0f\u20e3","\u0033\ufe0f\u20e3","\u0034\ufe0f\u20e3","\u0035\ufe0f\u20e3","1⃣","2⃣","3⃣","4⃣","5⃣"] and payload.channel_id==db.read_guild("dc_ch",payload.guild_id):
                message=await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)

                if message.content!="" and (message.content[0].isdigit() or len(message.mentions)==1):
                    content=message.content.replace("＋","+")
                    content=re.sub(r"(\d+[sSｓＳ秒]?)",r"\1 ",content)

                    spl=content.split()[:3]
                    if len(spl) == 2:
                        spl.append("")
                    if len(spl) == 3:
                        damage1=0
                        damage2=0
                        damage_plus=0
                        d_count=0
                        time=""
                        another=""
                        for i in range(3):
                            if spl[i].isdigit():
                                if d_count==0:
                                    damage1=int(spl[i])
                                    d_count+=1
                                else:
                                    damage2=int(spl[i])
                            elif re.match(r"\+\d+$",spl[i]):
                                damage_plus=int(spl[i][1:])
                            elif re.match(r"\d+[sSｓＳ秒]$",spl[i]):
                                time=spl[i]
                            else:
                                another=spl[i]
                        if damage_plus != 0:
                            damage2 = damage1
                            damage1=damage2+damage_plus
                        if damage1 < damage2:
                            temp=damage1
                            damage1=damage2
                            damage2=temp
                        content=f"{damage1} {time} {damage2} {another}"+"".join(content.split()[3:])


                    damage=max(map(lambda x:int(re.match(r"\d+",x).group()) if re.match(r"\d+",x) else 0,content.split()[:3]))
                    boss=str(payload.emoji.name.encode("utf-8"))[2]
                    author_id=message.author.id
                    author=message.author

                    # 代行
                    if len(message.mentions)==1:
                        mentionless_content=message.content.replace(message.mentions[0].mention,"").strip()
                        content=mentionless_content
                        if not mentionless_content[0].isdigit():
                            return
                        if db.read_member(message.guild.id,"id",author_id) == None:
                            return
                        damage=max(map(lambda x:int(re.match(r"\d+",x).group()) if re.match(r"\d+",x) else 0,content.split()[:3]))
                        author_id=message.mentions[0].id
                        author=message.mentions[0]

                    conn=sqlite3.connect(db.dbname)
                    cur=conn.cursor()

                    cur.execute(f'''CREATE TABLE IF NOT EXISTS dc_{payload.guild_id} (
                        No INTEGER PRIMARY KEY,
                        id INTEGER,
                        boss INTEGER,
                        status TEXT,
                        damage INTEGER,
                        text TEXT,
                        done INTEGER
                        )''')
                    

                    # 凸宣言メッセージを取得し持ち越しか確認
                    try:
                        cur.execute(f"SELECT done FROM dc_{message.guild.id} WHERE id = {message.author.id} AND (boss = {boss} OR boss IS NULL) AND done > 1000")
                        mochi_id=cur.fetchone()[0]
                        cur.execute(f"SELECT sengen_ch FROM guild WHERE id = {message.guild.id}")
                        mochi_channel=cur.fetchone()[0]
                        mochi_message=await message.guild.get_channel(mochi_channel).fetch_message(mochi_id)
                        is_mochi=bool(re.search(r"(餅|持|もち)",mochi_message.content))
                    except:
                        is_mochi=False
                    # 持ち越し蚤の場合
                    if not is_mochi:
                        cur.execute(f"SELECT boss{boss},mochi FROM member_{message.guild.id} WHERE id = {message.author.id}")
                        check_mochi=cur.fetchone()
                        mochi_list=[str(check_mochi[1])[i:i+2] for i in range(0,len(str(check_mochi[1])),2)] if check_mochi[1] != None else []
                        if check_mochi[0] == None and (f"1{boss}" in mochi_list or f"2{boss}" in mochi_list or f"3{boss}" in mochi_list):
                            is_mochi=True
                    # 更新時持ち越しリアクションがあった場合
                    if not is_mochi:
                        cur.execute(f"SELECT status FROM dc_{message.guild.id} WHERE id = {author_id} AND boss = {boss} AND done = 0")
                        status=cur.fetchone()
                        if status != None and status[0]!=None and status[0][1] == "🔄":
                            is_mochi = True
                    mochi="🔄" if is_mochi else "🔲"
                        

                    # 凸宣言を削除し、ダメージを登録する
                    cur.execute(f"DELETE FROM dc_{payload.guild_id}\
                        WHERE id = {author_id} AND (boss = {boss} OR boss IS NULL) AND done > 1000")
                    
                    cur.execute(f"SELECT No,status FROM dc_{payload.guild_id}\
                        WHERE id = {author_id} AND boss = {boss} AND done = 0")
                    
                    # 既に登録されているダメージの情報
                    prev=cur.fetchone()

                    if prev != None and bool(len(prev)):
                        # 上書き
                        cur.execute(f"UPDATE dc_{payload.guild_id} SET status = '¦{mochi}¦🔲¦🔲¦',damage = {damage},text = '{content}'\
                            WHERE No = {prev[0]}")
                    else:
                        # 新規
                        cur.execute(f"INSERT INTO dc_{payload.guild_id} (No,id,boss,status,damage,text,done)\
                            VALUES ({int(message.created_at.timestamp()*1000)},{author_id},{boss},'¦{mochi}¦🔲¦🔲¦',{damage},'{content}',0)")
                        
                                    
                        
                    conn.commit()
                    conn.close()


                    #リアクションのリセット
                    dc_message=self.bot.get_channel(payload.channel_id).get_partial_message(db.read_guild("dc_msg",payload.guild_id).split("\n")[int(boss)-1])
                    status=[str(self.syudou),"🔼","🔻","🔥"]
                    if prev == None:
                        
                        No=db.execute(f"SELECT No,status FROM dc_{payload.guild_id}\
                            WHERE id = {author_id} AND boss = {boss} AND done = 1 ORDER BY No DESC")
                        if len(No)>0:
                            for s in status:
                                if s in No[0][1]:
                                    await dc_message.remove_reaction(s,author)
                            if not is_mochi:
                                await dc_message.remove_reaction("🔄",author)
                            await dc_message.remove_reaction("✅",author)
                    else:
                        for s in status:
                            if s in prev[1]:
                                await dc_message.remove_reaction(s,author)
                        if not is_mochi:
                            await dc_message.remove_reaction("🔄",author)


                    self.timer_set(payload.guild_id,boss)
                    await message.delete()
                    await DC.dc_unknown(self,payload.guild_id)

                    

            
            elif str(payload.message_id) in db.read_guild("dc_msg",payload.guild_id):

                updated=False
                boss=db.read_guild("dc_msg",payload.guild_id).split("\n").index(str(payload.message_id))+1

                status=db.execute(f"SELECT No,status FROM dc_{payload.guild_id}\
                    WHERE id = {payload.user_id} AND boss = {boss} AND done = 0")
                    
                if bool(len(status)):
                    status=status[0]
                    match payload.emoji.name:
                        case "🔄":
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '¦🔄{status[1][2:]}' WHERE No = {status[0]}")
                            updated=True
                        case self.syudou.name:
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:3]}{self.syudou}{status[1][-3:]}' WHERE No = {status[0]}")
                            updated=True
                        case "🔼":
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔼¦' WHERE No = {status[0]}")
                            updated=True
                        case "🔻":
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔻¦' WHERE No = {status[0]}")
                            updated=True
                        case "🔥":
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔥¦' WHERE No = {status[0]}")
                            updated=True
                        case "✅":
                            db.execute(f"UPDATE dc_{payload.guild_id} SET done = 1 WHERE No = {status[0]}")
                            updated=True
                    
                if payload.emoji.name=="❌":
                    db.execute(f"DELETE FROM dc_{payload.guild_id}\
                        WHERE id = {payload.user_id} AND boss = {boss} AND done != 1")
                    await self.bot.get_channel(payload.channel_id).get_partial_message(payload.message_id).remove_reaction("❌",payload.member)
                    updated=True
                    
                elif payload.emoji.name=="👉":
                    members=db.execute(f"SELECT * FROM dc_{payload.guild_id} WHERE boss = {boss}")
                    db.execute(f"DELETE FROM dc_{payload.guild_id} WHERE boss = {boss}")

                    message=self.bot.get_channel(payload.channel_id).get_partial_message(payload.message_id)
                    fetch_message=await message.fetch()
                    fetch_content=fetch_message.content
                    guild=self.bot.get_guild(payload.guild_id)
                    content=Generator.dc_content(guild,boss)
                    await fetch_message.edit(content=content)

                    await message.clear_reactions()
                    await message.add_reaction("🔄")
                    await message.add_reaction(self.syudou)
                    await message.add_reaction("🔼")
                    await message.add_reaction("🔻")
                    await message.add_reaction("🔥")
                    await message.add_reaction("❌")
                    await message.add_reaction("✅")
                    await message.add_reaction("👉")
                    log=None
                    if db.read_guild("log_ch",payload.guild_id)!=None:
                        log=await self.bot.get_channel(db.read_guild("log_ch",payload.guild_id)).send(fetch_content)
                    r_message=self.bot.get_channel(payload.channel_id).get_partial_message(payload.message_id)
                    prev_stat={"dc_reprint":None,"table_reaction":[],"prev_mochi":[]}
                    global dc_reprint
                    if message.guild.id in dc_reprint and dc_reprint[message.guild.id][boss-1] != None:
                        global table_reaction
                        if message.guild.id in table_reaction:
                            prev_stat["table_reaction"]=table_reaction[message.guild.id][boss-1]
                            table_reaction[message.guild.id][boss-1]=[]
                        prev_stat["dc_reprint"]=dc_reprint[message.guild.id][boss-1]
                        dc_reprint[message.guild.id][boss-1]=None
                    global prev_mochi
                    if guild.id in prev_mochi:
                        prev_stat["prev_mochi"]=prev_mochi[guild.id][boss-1]
                        prev_mochi[guild.id][boss-1]=[]
                    prev_stat["prev_message"]=prev_message.delete_boss(message.guild.id,boss)
                    prev_stat["prev_name"]=prev_name.delete(guild.id,boss)

                    await self.bot.get_channel(payload.channel_id).send("討伐されました",view=DCCompleteView(members,log,fetch_content,boss,prev_stat),delete_after=60,reference=r_message)
                    SpreadSheetDC.write(guild,boss)
                    
                elif payload.emoji.name=="🚮":
                    members=db.execute(f"SELECT * FROM dc_{payload.guild_id} WHERE boss = {boss}")
                    db.execute(f"DELETE FROM dc_{payload.guild_id} WHERE boss = {boss}")

                    message=self.bot.get_channel(payload.channel_id).get_partial_message(payload.message_id)
                    guild=self.bot.get_guild(payload.guild_id)
                    content=Generator.dc_content(guild,boss)
                    await message.edit(content=content)
                    await message.clear_reactions()
                    await message.add_reaction("🔄")
                    await message.add_reaction(self.syudou)
                    await message.add_reaction("🔼")
                    await message.add_reaction("🔻")
                    await message.add_reaction("🔥")
                    await message.add_reaction("❌")
                    await message.add_reaction("✅")
                    await message.add_reaction("👉")
                # メッセージ内容更新の確認
                if updated:
                    self.timer_set(payload.guild_id,boss)
                
            # 不明な凸宣言者の取り消し
            elif payload.emoji.name=="❌" and payload.message_id == db.read_guild("unknown_msg",payload.guild_id):
                db.execute(f"DELETE FROM dc_{payload.guild_id} WHERE id = {payload.user_id} AND boss IS NULL AND done > 1000")
                await self.bot.get_channel(payload.channel_id).get_partial_message(payload.message_id).remove_reaction("❌",payload.member)
                await DC.dc_unknown(self,payload.guild_id)
        except:
            pass
    



    @commands.Cog.listener("on_raw_reaction_remove")
    @DpyDecorator.member_check
    async def damage_remove_reaction(self,payload:discord.RawReactionActionEvent):
        """ダメコンのリアクション取り消し"""
        try:
            if str(payload.message_id) in db.read_guild("dc_msg",payload.guild_id):
                updated=False
                boss=db.read_guild("dc_msg",payload.guild_id).split("\n").index(str(payload.message_id))+1

                status=db.execute(f"SELECT No,status FROM dc_{payload.guild_id}\
                    WHERE id = {payload.user_id} AND boss = {boss} AND done = 0")
                
                if bool(len(status)) and payload.emoji.name in status[0][1]:
                    status=status[0]
                    match payload.emoji.name:
                        case "🔄":
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '¦🔲{status[1][2:]}' WHERE No = {status[0]}")
                            updated=True
                        case self.syudou.name:
                            status_rep=str(status[1]).replace(str(self.syudou),"🔲")
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '{status_rep}' WHERE No = {status[0]}")
                            updated=True
                        case "🔼":
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔲¦' WHERE No = {status[0]}")
                            updated=True
                        case "🔻" :
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔲¦' WHERE No = {status[0]}")
                            updated=True
                        case "🔥":
                            db.execute(f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔲¦' WHERE No = {status[0]}")
                            updated=True
                
                elif payload.emoji.name == "✅":
                    now=db.execute(f"SELECT No FROM dc_{payload.guild_id} WHERE id = {payload.user_id} AND boss = {boss} AND done = 0")
                    No=db.execute(f"SELECT No FROM dc_{payload.guild_id}\
                        WHERE id = {payload.user_id} AND boss = {boss} AND done = 1 ORDER BY No DESC")
                    if len(No)>0 and len(now) == 0:
                        db.execute(f"UPDATE dc_{payload.guild_id} SET done = 0 WHERE No = {No[0][0]}")
                        updated=True

                if updated:
                    self.timer_set(payload.guild_id,boss)
        except:
            pass
    
    @commands.Cog.listener("on_member_update")
    @DpyDecorator.member_check
    async def change_name(self,before:discord.Member,after:discord.Member):
        if before.display_name!=after.display_name:
            await asyncio.sleep(2) # データベースが更新されるまで待つ
            boss=set([x for row in db.execute(f"SELECT boss FROM dc_{before.guild.id} WHERE id = {before.id}") for x in row])
            for b in boss:
                if b == None:
                    await DC.dc_unknown(self,before.guild.id)
                else:
                    try:
                        self.timer_set(before.guild.id,b,True)
                    except:
                        pass
    
    def timer_set(self,guild_id,boss,rename = False):
        if isinstance(boss,str):
            boss=int(boss)
        if str(guild_id) not in self.DC_timer:
            self.DC_timer[str(guild_id)]=[{},{},{},{},{}]
        if self.DC_timer[str(guild_id)][boss-1]=={}:
            self.DC_timer[str(guild_id)][boss-1]["next"]=datetime.now()
            self.DC_timer[str(guild_id)][boss-1]["updated"]=True
        asyncio.create_task(self.timer_start(guild_id,boss,rename))
    
    async def timer_start(self,guild_id,boss,rename):
        nexttime:datetime=self.DC_timer[str(guild_id)][boss-1]["next"]
        now=datetime.now()
        if not self.DC_timer[str(guild_id)][boss-1]["updated"] and (now-nexttime).total_seconds() >= 10:
            self.DC_timer[str(guild_id)][boss-1]["updated"]=True
        if not self.DC_timer[str(guild_id)][boss-1]["updated"]:
            return
        self.DC_timer[str(guild_id)][boss-1]["updated"]=False
        if nexttime > now:
            await asyncio.sleep((nexttime-now).seconds+(nexttime-now).microseconds/1000000)
        if self.DC_timer[str(guild_id)][boss-1]["updated"] == False:

            try:
                guild=self.bot.get_guild(guild_id)
                content=Generator.dc_content(guild,boss)
                dc_message=self.bot.get_channel(db.read_guild("dc_ch",guild_id)).get_partial_message(db.read_guild("dc_msg",guild_id).split("\n")[boss-1])
                await dc_message.edit(content=content)
                # スプシ処理
                SpreadSheetDC.write(guild,boss)
            except discord.HTTPException as e:
                h=e.response.headers
                print(h)

            self.DC_timer[str(guild_id)][boss-1]["next"]=datetime.now()+timedelta(seconds=5)
            self.DC_timer[str(guild_id)][boss-1]["updated"]=True

            try:
                # 転載の処理
                # 削除送信をする
                global dc_reprint
                if not rename and int(guild_id) in dc_reprint and dc_reprint[int(guild_id)][boss-1]!=None:
                    send_message=await dc_reprint[int(guild_id)][boss-1].channel.send(content=content,silent = True,view=DCReprintView(boss) )
                    await dc_reprint[int(guild_id)][boss-1].delete()
                    dc_reprint[int(guild_id)][boss-1]=send_message
            except:
                pass


    async def cog_load(self):
        asyncio.create_task(self.load_message_reaction())
        self.daily_totsu.start()
        MochiTableHelper.load()
    
    def cog_unload(self):
        self.daily_totsu.cancel()
    
    async def load_message_reaction(self):
        await asyncio.sleep(10)
        channel_ids=db.read_guild("dc_ch")
        for guild_channel_id in channel_ids:
            try:
                channel=self.bot.get_channel(guild_channel_id[1])
                async for message in channel.history(limit=30):
                    if message.author.id != self.bot.user.id and len(message.reactions) == 0 and message.content != "" and message.content[0].isdigit():
                        for emoji in ["\u0031\ufe0f\u20e3","\u0032\ufe0f\u20e3","\u0033\ufe0f\u20e3","\u0034\ufe0f\u20e3","\u0035\ufe0f\u20e3"]:
                            await message.add_reaction(emoji)
            except:
                pass
    
    @tasks.loop(time=time)
    async def daily_totsu(self):
        guilds=db.read_guild("id")
        for guild in guilds:
            try:
                isupdate=[False,False,False,False,False]
                delete_num=[]
                rows=db.execute(f"SELECT * FROM dc_{guild[0]}")
                for values in rows: 
                    if values[2] == None:
                        delete_num.append(values[0])
                    elif values[6] == 0:
                        db.execute(f"UPDATE dc_{guild[0]} SET done = 1 WHERE No = {values[0]}")
                        isupdate[values[2]-1]=True
                    elif values[6] > 1000:
                        delete_num.append(values[0])
                        isupdate[values[2]-1]=True
                if len(delete_num) > 0:
                    _sql=f"DELETE FROM dc_{guild[0]} WHERE "+" OR ".join(map(lambda x:f"No = {x}",delete_num))
                    db.execute(_sql)
                await self.dc_unknown(guild[0])
                for i,_isupdate in enumerate(isupdate):
                    if _isupdate:
                        self.timer_set(guild[0],i+1)
            except:
                pass
        today = datetime.today()
        next_day= today + timedelta(days=6)
        if next_day.day == 1:
            for guild_id in guilds:
                try:
                    guild=self.bot.get_guild(guild_id[0])
                    ch=guild.get_channel(db.read_guild("dc_ch",guild.id))
                    send=await ch.send("凸宣言を無効にしました",view=SuspendView())
                    db.write_guild(guild.id,"suspend_sengen",send.id)
                except:
                    pass
        MochiTableHelper.remove()

    @commands.Cog.listener("on_message_delete")
    async def delete_mention_message(self,message:discord.Message):
        def find(no,boss):
            global prev_mochi
            if not message.guild.id in prev_mochi:
                return -1
            for i,m in enumerate(prev_mochi[message.guild.id][boss-1]):
                if m[0] == no:
                    return prev_mochi[message.guild.id][boss-1].pop(i)[1]
            return -1
        members_list=[]
        if message.guild != None and prev_message.find(message.guild.id,message.id):
            boss=prev_message.message_list[message.guild.id][message.id][0]
            for No in prev_message.message_list[message.guild.id][message.id][1]:
                db.execute(f"UPDATE dc_{message.guild.id} SET done = 0 WHERE No = {No}")
                member_id=db.execute(f"SELECT id FROM dc_{message.guild.id} WHERE No = {No}")[0][0]
                prev=find(No,boss)
                if prev != -1:
                    if prev != None and prev > 0:
                        db.write_member(message.guild.id,member_id,"mochi",prev)
                    else:
                        db.delete_member(message.guild.id,member_id,"mochi")
                    MochiTableHelper.undo(message.guild,member_id)
                members_list.append((No,member_id))
                global finish_members
                if message.guild.id in finish_members and member_id in finish_members[message.guild.id][boss-1]:
                    finish_members[message.guild.id][boss-1].remove(member_id)
            content=Generator.dc_content(message.guild,boss)
            dc_message=message.guild.get_channel(db.read_guild("dc_ch",message.guild.id)).get_partial_message(db.read_guild("dc_msg",message.guild.id).split("\n")[boss-1])
            await dc_message.edit(content=content)
            await dc_reprint[message.guild.id][boss-1].edit(content=content)
            await DC.table_change(message.guild,boss,members_list,False)
            prev_message.delete(message.guild.id,message.id)
            await message.channel.send(f"キャンセル\n{'\n'.join(['<@'+str(m[1])+'>' for m in members_list])}")
            # 名前の変更
            global prev_name
            for member in members_list:
                prev=prev_name.get(message.guild.id,member[1])
                if prev != None:
                    try:
                        m = message.guild.get_member(member[1])
                        await m.edit(nick=prev)
                    except:
                        pass
            
            SpreadSheetDC.write(message.guild,boss)
    
    # テーブルの自動更新
    # リアクションを消すのみで対応
    # ただし、リアクションをつけることはできないので後で考える？
    @staticmethod
    async def table_change(guild:discord.Guild,boss,members:list,finish:bool):
        global table_reaction
        if not guild.id in table_reaction:
            table_reaction[guild.id]=[[],[],[],[],[]]
        message=guild.get_channel(db.read_guild("reaction_ch",guild.id)).get_partial_message(db.read_guild("reaction_msg",guild.id))
        if finish:
            for member in members:
                try:
                    # 通し前の突希望を記録
                    table_reaction_db=db.read_member(guild.id,f"boss{boss}",member[1])
                    table_reaction[guild.id][boss-1].append((member[0],table_reaction_db))
                    
                    db.delete_member(guild.id,member[1],f"boss{boss}")
                    member=guild.get_member(member[1])
                    match boss:
                        case 1:
                            await message.remove_reaction("1⃣",member)
                        case 2:
                            await message.remove_reaction("2⃣",member)
                        case 3:
                            await message.remove_reaction("3⃣",member)
                        case 4:
                            await message.remove_reaction("4⃣",member)
                        case 5:
                            await message.remove_reaction("5⃣",member)
                except:
                    continue
        else:
            for member in members:
                length=len(table_reaction[guild.id][boss-1])
                for i,v in enumerate(reversed(table_reaction[guild.id][boss-1])):
                    if v[0] == member[0]:
                        if v[1] != None:
                            db.write_member(guild.id,member[1],f"boss{boss}",v[1])
                        del table_reaction[guild.id][boss-1][length-(i+1)]
                        break
        await message.add_reaction("〰")
    
    @staticmethod
    async def zan_update(member_id,guild:discord.Guild,zan_u,mochi_u):
        member=guild.get_member(member_id)
        p_name=member.display_name
        zan=zan_u
        mochi=mochi_u
        try:
            search=re.search(r"残\d餅\d",member.display_name)
            if search:
                s=search.group()
                zan=min(3,max(0,int(s[1])+zan_u))
                mochi=min(3,max(0,int(s[3])+mochi_u))
                s_replace=f"残{zan}餅{mochi}"
                if s != s_replace:
                    rep=re.sub(s,s_replace,member.display_name)
                    await member.edit(nick=rep)
                else:
                    p_name=None
            else:
                p_name=None
        except:
            pass
        return zan == 0 and mochi == 0
    

    @commands.command()
    async def mochi(self,ctx:commands.Context):
        await MochiTableHelper.send(ctx.channel)
        await ctx.message.delete()



async def setup(bot:commands.Bot):
    await bot.add_cog(DC(bot))