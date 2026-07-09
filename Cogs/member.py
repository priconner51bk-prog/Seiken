import asyncio
from datetime import datetime, timedelta
import math
import re
from typing import Literal
import discord
from discord import app_commands
from discord.ext import commands

from util.database import db
from util.decorators import DpyDecorator
from util.content_generator import Generator

class MemberAddView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    @discord.ui.select(cls=discord.ui.MentionableSelect,placeholder="選択",max_values=25)
    async def member_selected(self,interaction:discord.Interaction,select:discord.ui.MentionableSelect):
        res=""
        for value in select.values:
            if type(value)==discord.Member:
                db.write_member(interaction.guild_id,value.id,"display_name",value.display_name)
                res+=f"{value.display_name}\n"
            elif type(value)==discord.Role:
                for member in value.members:
                    db.write_member(interaction.guild_id,member.id,"display_name",member.display_name)
                    res+=f"{member.display_name}\n"
        await interaction.response.edit_message(content="追加しました\n"+res,view=None)

class MemberDeleteView(discord.ui.View):
    def __init__(self,members):
        super().__init__(timeout=120)
        members_slide=[members[i:i+25] for i in range(0,min(len(members),100),25)]
        for _members in members_slide:
            self.add_item(MemberDeleteSelect(_members))
    @discord.ui.button(label="@everyone")
    async def memberdelete_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        db.execute(f"DELETE FROM member_{interaction.guild_id}")
        await interaction.response.edit_message(content="全てのメンバーを削除しました",view=None)
class MemberDeleteSelect(discord.ui.Select):
    def __init__(self,members):
        options=[discord.SelectOption(label=member[1],value=member[0]) for member in members]
        super().__init__(options=options,max_values=len(options))
    async def callback(self,interaction:discord.Interaction):
        res=""
        for id in self.values:
            db.delete_member(interaction.guild_id,id)
            res+=interaction.guild.get_member(int(id)).display_name+"\n"
        await interaction.response.edit_message(content=f"{res}を削除しました",view=None)

class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    @discord.ui.select(cls=discord.ui.RoleSelect,max_values=1,placeholder="ロールを選択")
    async def roleselect(self,interaction:discord.Interaction,select:discord.ui.RoleSelect):
        db.write_guild(interaction.guild_id,"role",select.values[0].id)
        res=""
        for member in select.values[0].members:
                db.write_member(interaction.guild_id,member.id,"display_name",member.display_name)
                res+=f"{member.display_name}\n"
        await interaction.response.edit_message(content=f"{select.values[0].mention}に設定しました\n{res}をメンバーに追加",view=None)


class ManageMember(commands.Cog):
    def __init__(self,bot:commands.Bot):
        self.bot=bot

    @app_commands.command(description="メンバーの操作")
    @app_commands.guild_only()
    async def member(self,interaction:discord.Interaction,mode:Literal["一覧","追加","削除","ロール設定","ロール削除","更新"]):
        res=""
        if mode=="一覧":
            members=db.read_member(interaction.guild_id,"display_name")
            role_id=db.read_guild("role",interaction.guild_id)
            if role_id != None:
                res+=f"<@&{role_id}>\n"
            if members != None:
                for i,member in enumerate(members):
                    res+=f"{str(i+1)} {member[1]}\n"
            if res=="":
                res="登録されているメンバーはいません"
            await interaction.response.send_message(res,ephemeral=True)
        elif mode=="追加":
            await interaction.response.send_message("追加するメンバー、ロールを選択",view=MemberAddView(),ephemeral=True)
        elif mode=="削除":
            members=db.read_member(interaction.guild_id,"display_name")
            await interaction.response.send_message("削除するメンバーを選択",view=MemberDeleteView(members),ephemeral=True)
        elif mode=="ロール設定":
            await interaction.response.send_message("メンバーのロールを選択",view=RoleSelectView(),ephemeral=True)
        elif mode=="ロール削除":
            db.delete_guild(interaction.guild_id,"role")
            await interaction.response.send_message("ロールの設定を削除しました",ephemeral=True)
        elif mode=="更新":
            role_id=db.read_guild("role",interaction.guild_id)
            if  role_id != None:
                role=interaction.guild.get_role(role_id)
                role_members_id=[m.id for m in role.members]
                _m=db.read_member(interaction.guild_id,"id")
                members=[m[0] for m in _m] if _m != None else []
                for member_id in members:
                    if member_id not in role_members_id:
                        db.delete_member(interaction.guild_id,member_id)
                        members.remove(member_id)
                for member_id in role_members_id:
                    if member_id not in members:
                        member=interaction.guild.get_member(member_id)
                        db.write_member(interaction.guild_id,member_id,"display_name",member.display_name)
            else:
                pass
            await interaction.response.send_message("更新しました",ephemeral=True)
        

    @commands.Cog.listener()
    async def on_member_update(self,before:discord.Member,after:discord.Member):
        # ロールの変更 ################################################################
        diff=list(set(before.roles)^set(after.roles))
        if len(diff)>=100:
            for _diff in diff:
                if _diff.id==db.read_guild("role",before.guild.id):
                    if _diff in after.roles:
                        db.write_member(before.guild.id,before.id,"display_name",before.display_name)
                    elif _diff in before.roles:
                        db.delete_member(before.guild.id,before.id)
        elif db.read_member(before.guild.id,"id",before.id) == None:
            return
        elif before.display_name!=after.display_name:
            db.write_member(before.guild.id,before.id,"renamed",after.display_name)
            db.write_member(before.guild.id,before.id,"display_name",after.display_name)
            try:
                message=self.bot.get_guild(before.guild.id).get_channel(db.read_guild("totsukanri_ch",before.guild.id)).get_partial_message(db.read_guild("totsukanri_msg",before.guild.id))
                await message.edit(embed=discord.Embed(color=discord.colour.parse_hex_number("ffffff"),title="凸管理",description=Generator.totsu_content(before.guild)),allowed_mentions=discord.AllowedMentions(users=False))
            except:
                pass
    
    @commands.Cog.listener()
    @DpyDecorator.member_check
    async def on_user_update(self,before:discord.User,after:discord.User):
        if before.display_name!=after.display_name:
            guilds=before.mutual_guilds
            for guild in guilds:
                if db.read_member(guild.id,"id",before.id) != None:
                    db.write_member(guild.id,before.id,"renamed",after.display_name)
                    db.write_member(guild.id,before.id,"display_name",after.display_name)
                    try:
                        message=self.bot.get_guild(guild.id).get_channel(db.read_guild("totsukanri_ch",guild.id)).get_partial_message(db.read_guild("totsukanri_msg",guild.id))
                        await message.edit(embed=discord.Embed(color=discord.colour.parse_hex_number("ffffff"),title="凸管理",description=Generator.totsu_content(guild)),allowed_mentions=discord.AllowedMentions(users=False))
                    except:
                        pass

                

    @app_commands.command(description="完凸報告をしていないメンバーのチェック")
    @app_commands.guild_only()
    async def check_complete(self,interaction:discord.Interaction,mode:Literal["完凸表示","未報告表示","凸状況一覧"]=None):
        members=db.execute(f"SELECT id,finish,renamed FROM member_{interaction.guild_id}")
        if mode == None or mode == "完凸表示":
            result_list=[interaction.guild.get_member(int(v[0])).mention for v in members if v[1] != None]
            await interaction.response.send_message("完凸報告者一覧\n"+"\n".join(result_list),ephemeral=True)
        if mode =="未報告表示":
            result_list=[]
            for member in members:
                name=interaction.guild.get_member(int(member[0])).display_name
                mention=interaction.guild.get_member(int(member[0])).mention
                s1=re.search("残り?[0-3０-３]",name)
                s2=re.search("(持ち|持|餅)[0-3０-３]",name)
                stat=[0,0]
                if s1:
                    stat[0]=int(s1.group()[-1])
                if s2:
                    stat[1]=int(s2.group()[-1])
                if member[2] != None and member[1] == None and stat[0]+stat[1]==0:
                    result_list.append(mention)
            if len(result_list)==0:
                await interaction.response.send_message("完凸報告をしていないメンバーはいません",ephemeral=True)
            else:
                await interaction.response.send_message("\n".join(result_list),ephemeral=True)
        if mode == "凸状況一覧":
            await interaction.response.send_message(embed=discord.Embed(color=discord.colour.parse_hex_number("ffffff"),title="凸管理",description=Generator.totsu_content(interaction.guild)),ephemeral=True)



        
    @commands.command("totsu")
    async def totsu(self,ctx:commands.Context):
        if ctx.message.author.bot:
            return
        embed=discord.Embed(color=discord.colour.parse_hex_number("ffffff"),title="凸管理",description=Generator.totsu_content(ctx.guild),allowed_mentions=discord.AllowedMentions(users=False))
        send=await ctx.channel.send(embed=embed)
        db.write_guild(ctx.guild.id,"totsukanri_ch",send.channel.id)
        db.write_guild(ctx.guild.id,"totsukanri_msg",send.id)


    async def cog_load(self):
        asyncio.create_task(self.daily_totsu())

    async def daily_totsu(self):
        while True:
            today=datetime.today()
            nexttime=today.replace(hour=5,minute=0,second=0)+timedelta(days=1)
            if today.hour<5:
                nexttime=today.replace(hour=5,minute=0,second=0)
            await asyncio.sleep((nexttime-today).seconds+10)
            guilds=db.read_guild("id")
            for guild in guilds:
                try:
                    members=db.read_member(guild[0],"id")
                    for member in members:
                        db.delete_member(guild[0],member[0],"renamed")
                        db.delete_member(guild[0],member[0],"finish")
                        db.delete_member(guild[0],member[0],"taskkill")
                    message=self.bot.get_guild(guild[0]).get_channel(db.read_guild("totsukanri_ch",guild[0])).get_partial_message(db.read_guild("totsukanri_msg",guild[0]))
                    await message.edit(embed=discord.Embed(color=discord.colour.parse_hex_number("ffffff"),title="凸管理",description=Generator.totsu_content(self.bot.get_guild(guild[0]))),allowed_mentions=discord.AllowedMentions(users=False))
                except:
                    pass


async def setup(bot:commands.Bot):
    await bot.add_cog(ManageMember(bot))