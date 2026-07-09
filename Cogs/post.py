import asyncio
from datetime import datetime, timedelta
import sqlite3
from typing import Literal
import discord
from discord import app_commands
from discord.ext import commands

from util.database import db
from util.decorators import DpyDecorator


class PostView(discord.ui.View):
    def __init__(self,message:discord.Message):
        super().__init__(timeout=60)
        self.add_item(PostSelectChannel(message))
class PostSelectChannel(discord.ui.ChannelSelect):
    def __init__(self,message:discord.Message):
        self.message=message
        super().__init__(channel_types=[discord.ChannelType.text],max_values=1,min_values=1,placeholder="チャンネルを選択")
    async def callback(self,interaction:discord.Interaction):
        try:
            channel=await self.values[0].fetch()
            if channel.permissions_for(interaction.guild.get_member(interaction.client.user.id)).send_messages:
                await interaction.response.send_modal(PostModal(self.message,self.values[0]))
                await interaction.delete_original_response()
            else:
                await interaction.response.send_message("指定したチャンネルにはメッセージを送信できません",ephemeral=True)
        except:
            await interaction.response.send_message("指定したチャンネルにはメッセージを送信できません",ephemeral=True)
class PostModal(discord.ui.Modal,title="予約投稿"):
    year=discord.ui.TextInput(label="年")
    month=discord.ui.TextInput(label="月")
    day=discord.ui.TextInput(label="日")
    hour=discord.ui.TextInput(label="時")
    minute=discord.ui.TextInput(label="分")
    def __init__(self,message:discord.Message,channel:discord.TextChannel):
        self.channel=channel
        self.message=message
        now=datetime.now()
        self.year.default=now.year
        self.month.default=now.month
        self.day.default=now.day
        self.hour.default=str(now.hour)
        self.minute.default=str(now.minute)
        super().__init__(timeout=180)
    async def on_submit(self, interaction: discord.Interaction):
        now=datetime.now()
        pid=int(now.timestamp()*100)
        date=[self.year,self.month,self.day,self.hour,self.minute]
        time="".join([v.value.zfill(2) for v in date])+"00"
        try:
            posttime=datetime.strptime(time,'%Y%m%d%H%M%S')
            size=0
            for a in self.message.attachments:
                size+=a.size
            if now > posttime:
                await interaction.response.send_message("指定した時間は現在時刻よりも前です "+posttime.strftime('%Y年%m月%d日%H時%M分'),ephemeral=True)
                return
            elif size>=25000000:
                await interaction.response.send_message("ファイルのサイズが25MBを超えています "+posttime.strftime('%Y年%m月%d日%H時%M分'),ephemeral=True)
                return
            
            embed=discord.Embed(description=self.message.clean_content[:50])
            if len(self.message.attachments)>0:
                embed.description+="\n＊ファイル＊"
            timestamp=int(posttime.timestamp())
            db.write_post(pid,timestamp,interaction.guild_id,self.message.id,self.message.channel.id,self.channel.id)

            if not bool(self.message.mentions) and not bool(self.message.role_mentions):
                send=await interaction.channel.send(f"<t:{timestamp}:f> {self.channel.mention}に投稿予定\n{self.message.jump_url}",embed=embed)
                asyncio.create_task(Post.PostLoop(pid,interaction.guild,posttime))
                await interaction.response.send_message("元のメッセージにはメンションがありません\nメンションを追加しますか",ephemeral=True,view=AddMentionView(self.message,pid,send))
            else:
                asyncio.create_task(Post.PostLoop(pid,interaction.guild,posttime))
                await interaction.response.send_message(f"<t:{timestamp}:f> {self.channel.mention}に投稿予定\n{self.message.jump_url}",embed=embed)
        except:
            timestr=f"{date[0]}年{date[1]}月{date[2]}日{date[3]}時{date[4]}分"
            await interaction.response.send_message("日付の取得に失敗しました\n"+timestr,ephemeral=True)
            return
class AddMentionView(discord.ui.View):
    def __init__(self,message:discord.Message,pid,send:discord.Message):
        super().__init__(timeout=60)
        self.message=message
        self.pid=pid
        self.send=send
    @discord.ui.select(cls=discord.ui.MentionableSelect,placeholder="メンションを選択",max_values=25)
    async def mention_select(self,interaction:discord.Interaction,select:discord.ui.MentionableSelect):
        mentions_str=" ".join([v.mention for v in select.values])
        db.execute(f"UPDATE post SET mentions='{mentions_str}' WHERE pid={self.pid}")
        embed=discord.Embed(description=mentions_str+"\n"+self.message.clean_content[:50])
        channel=interaction.guild.get_channel(db.read_post(self.pid,"send_ch"))
        timestamp=db.read_post(self.pid,"timestamp")
        if len(self.message.attachments)>0:
            embed.description+="\n＊ファイル＊"
        await self.send.delete()
        await interaction.response.send_message(f"<t:{timestamp}:f> {channel.mention}に投稿予定\n{self.message.jump_url}",embed=embed)



class DelPostView(discord.ui.View):
    def __init__(self,post_list:list):
        super().__init__(timeout=180)
        self.add_item(DelPostSelect(post_list))
class DelPostSelect(discord.ui.Select):
    def __init__(self,post_list:list):
        self.post_list=post_list
        options=[]
        for count,p in enumerate(post_list):
            options.append(discord.SelectOption(label=str(count+1)))
        super().__init__(options=options,max_values=1,placeholder="取り消す予約を選択")
    async def callback(self, interaction: discord.Interaction):
        pid=self.post_list[int(self.values[0])-1][1][0]
        db.execute(f"DELETE FROM post WHERE pid={pid}")
        await interaction.response.send_message(self.values[0]+"の予約を取り消しました",ephemeral=True)

class PostLog():
    def add_log(guild_id:int,is_complete:bool,result:str,date:datetime,message:discord.PartialMessage):
        url=message.jump_url if message != None else ""
        conn=sqlite3.connect("postlog.db")
        cur=conn.cursor()
        try:
            cur.execute(f'''CREATE TABLE IF NOT EXISTS log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild INTEGER,
                        is_complete INTEGER,
                        date INTEGER,
                        message TEXT,
                        result TEXT
                        )''')
            
            cur.execute(f"INSERT INTO log (guild,is_complete,date,message,result) VALUES ({guild_id},{int(is_complete)},{int(date.timestamp())},'{url}','{result}')")
            conn.commit()
        except sqlite3.Error as e:
            pass
        conn.close()
    def print_log(guild_id:int):
        content="ログ\n"
        conn=sqlite3.connect("postlog.db")
        cur=conn.cursor()
        try:
            cur.execute(f"SELECT * FROM log WHERE guild = {guild_id}")
            res=cur.fetchall()
            for _row in reversed(res):
                lump="🟩"
                if not bool(_row[2]):
                    lump="🟥"
                date=discord.utils.format_dt(datetime.fromtimestamp(_row[3]))
                _str=f"{lump} {date} {_row[5]} {_row[4]}\n"
                if len(content+_str)>=2000:
                    break
                content+=_str
            conn.commit()
        except sqlite3.Error as e:
            pass
        conn.close()
        return content

class Post(commands.Cog):
    def __init__(self,bot:commands.Bot):
        self.bot=bot

        self.bot.tree.add_command(app_commands.ContextMenu(name="予約投稿",callback=self.scheduledmessage))
    
    async def PostLoop(pid,guild:discord.Guild,posttime:datetime):
        now=datetime.now()
        
        nexttime=now.replace(hour=5,minute=0,second=0)+timedelta(days=1)
        if now.hour<5:
            nexttime=now.replace(hour=5,minute=0,second=0)
        
        if now <posttime and posttime <= nexttime:
            await asyncio.sleep((posttime-now).seconds+2)
        elif now >= posttime:
            if (now-posttime).seconds>120:
                message=guild.get_channel(db.read_post(pid,"message_ch")).get_partial_message(db.read_post(pid,"message_id"))
                PostLog.add_log(guild.id,False,f"指定した時刻に投稿できませんでした 投稿予定時刻:{discord.utils.format_dt(posttime)}",now,message)
                db.execute(f"DELETE FROM post WHERE pid={pid}")
                return
        else:
            return
        if db.read_post(pid,"timestamp")!=None:
            try:
                mention=""
                message=await guild.get_channel(db.read_post(pid,"message_ch")).fetch_message(db.read_post(pid,"message_id"))
                files=[]
                for a in message.attachments:
                    f=await a.to_file()
                    files.append(f)
                if db.read_post(pid,"mentions")!=None:
                    mentions=[v for v in db.read_post(pid,"mentions").split(" ") if v not in message.content]
                    if bool(mentions):
                        mention=" ".join(mentions)+"\n"
                send=await guild.get_channel(db.read_post(pid,"send_ch")).send(content=mention+message.content,files=files)
                PostLog.add_log(guild.id,True,f"投稿完了 {send.jump_url}",datetime.now(),message)
                db.execute(f"DELETE FROM post WHERE pid={pid}")
            except discord.NotFound:
                PostLog.add_log(guild.id,False,f"指定されたメッセージは見つかりませんでした",datetime.now(),None)
                db.execute(f"DELETE FROM post WHERE pid={pid}")
                return
            except discord.Forbidden:
                PostLog.add_log(guild.id,False,f"権限がありません",datetime.now(),None)
                db.execute(f"DELETE FROM post WHERE pid={pid}")
                return
            except:
                PostLog.add_log(guild.id,False,f"エラー 投稿予定時刻:{discord.utils.format_dt(posttime)}",datetime.now(),message)
                db.execute(f"DELETE FROM post WHERE pid={pid}")
                return
    
    async def PostReset(self):
        _posts=db.execute("SELECT * FROM post")
        if _posts != None:
            for _post in _posts[:]:
                posttime=datetime.fromtimestamp(_post[1])
                asyncio.create_task(Post.PostLoop(_post[0],self.bot.get_guild(_post[2]),posttime))

    async def cog_load(self):
        asyncio.create_task(self.daily_post())

    async def daily_post(self):
        while True:
            await self.PostReset()
            today=datetime.today()
            nexttime=today.replace(hour=5,minute=0,second=0)+timedelta(days=1)
            if today.hour<5:
                nexttime=today.replace(hour=5,minute=0,second=0)
            await asyncio.sleep((nexttime-today).seconds+10)
            print(datetime.today())
    
    #コンテキストメニュー
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_nicknames=True)
    async def scheduledmessage(self,interaction:discord.Interaction,message:discord.Message):
        if interaction.channel.permissions_for(interaction.guild.get_member(self.bot.user.id)).read_messages:
            await interaction.response.send_message("投稿するチャンネルを選択",view=PostView(message),ephemeral=True)
        else:
            await interaction.response.send_message("指定したメッセージはBOTが見ることができない設定になっています",ephemeral=True)
    

    @app_commands.command(description="予約投稿に関するコマンド",name="post")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_nicknames=True)
    async def post_command(self,interaction:discord.Interaction,log:Literal["log"]=None):
        if log==None:
            content=""
            _post_all=db.execute("SELECT * FROM post")
            if len(_post_all)>0:
                post_list=[(v[1],v) for v in _post_all if v[2]==interaction.guild_id]
                post_list.sort(key=lambda x:x[0])
                await interaction.response.defer(ephemeral=True)
                count=0
                for i,p in enumerate(post_list[:]):
                    try:
                        date=datetime.fromtimestamp(p[0])
                        message=await interaction.guild.get_channel(p[1][4]).fetch_message(p[1][3])
                        channel=interaction.guild.get_channel(p[1][5])
                        mention=""
                        if p[1][6]!=None:
                            mention="\n追加のメンション "+p[1][6]
                        content+=str(count+1)+"・"+date.strftime('%Y年%m月%d日%H:%M')+channel.mention+mention+"\n"+message.jump_url+"\n\n"
                        count+=1
                    except:
                        del post_list[i]
                        db.execute(f"DELETE FROM post WHERE pid={p[1][0]}")
                if content!="":
                    await interaction.edit_original_response(content=content,view=DelPostView(post_list))
                else:
                    await interaction.edit_original_response(content="予約はありません")
            else:
                await interaction.response.send_message("予約はありません",ephemeral=True)
        else:
            await interaction.response.defer(ephemeral=True)
            await interaction.edit_original_response(content=PostLog.print_log(interaction.guild_id))


async def setup(bot:commands.Bot):
    await bot.add_cog(Post(bot))