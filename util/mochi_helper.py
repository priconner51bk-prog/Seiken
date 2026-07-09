


from datetime import timedelta,datetime
from io import BytesIO
import json
import asyncio

import discord
from matplotlib import pyplot as plt
import pandas as pd
from util.database import db


class MochiTableHelper:
    _filepath="mochi.json"
    _data={}
    _delta=timedelta(hours=5)

    @staticmethod
    def load():
        """読み込みはdc.pyのcog_load"""

        def cast(d):
            if not isinstance(d,dict):
                return d
            new_d={}
            for key in d:
                if isinstance(key,str) and key.isdigit():
                    new_d[int(key)]=cast(d[key])
                else:
                    new_d[key]=cast(d[key])
            return new_d
        try:
            with open(MochiTableHelper._filepath,"r") as fp:
                load_data=dict(json.load(fp))
                MochiTableHelper._data=cast(load_data)
                
        except:
            return

    @staticmethod
    def save():
        with open(MochiTableHelper._filepath,"w") as fp:
            json.dump(MochiTableHelper._data,fp)
    
    @staticmethod
    def add(guild:discord.Guild,user_id,mochi):
        day=(datetime.now()-MochiTableHelper._delta).day
        if day not in MochiTableHelper._data:
            MochiTableHelper._data[day]={}
        if guild.id not in MochiTableHelper._data[day]:
            MochiTableHelper._data[day][guild.id]={}
        if user_id not in MochiTableHelper._data[day][guild.id]:
            MochiTableHelper._data[day][guild.id][user_id]=[]
        MochiTableHelper._data[day][guild.id][user_id].append(mochi)
        MochiTableHelper.save()
        asyncio.create_task(MochiTableHelper.update(guild))
    
    @staticmethod
    def undo(guild:discord.Guild,user_id):
        day=(datetime.now()-MochiTableHelper._delta).day
        try:
            del MochiTableHelper._data[day][guild.id][user_id][-1]
            if(len(MochiTableHelper._data[day][guild.id][user_id]))==0:
                del MochiTableHelper._data[day][guild.id][user_id]
            MochiTableHelper.save()
            asyncio.create_task(MochiTableHelper.update(guild))
        except:
            return

    
    @staticmethod
    def remove():
        MochiTableHelper._data={}
        MochiTableHelper.save()
    
    @staticmethod
    async def send(channel:discord.TextChannel):
        file=MochiTableHelper.create_table(channel.guild)
        message=await channel.send("",file=file)
        if "message" not in MochiTableHelper._data:
            MochiTableHelper._data["message"]={}
        if channel.guild.id not in MochiTableHelper._data["message"]:
            MochiTableHelper._data["message"][channel.guild.id]=[]
        MochiTableHelper._data["message"][channel.guild.id]=[channel.id,message.id]

    @staticmethod
    async def update(guild:discord.Guild):
        if "message" not in MochiTableHelper._data:
            return
        if guild.id not in MochiTableHelper._data["message"]:
            return
        channel_id=MochiTableHelper._data["message"][guild.id][0]
        message_id=MochiTableHelper._data["message"][guild.id][1]
        message=guild.get_channel(channel_id).get_partial_message(message_id)
        try:
            file=MochiTableHelper.create_table(guild)
            await message.edit(attachments=[file])
        except:
            return

    @staticmethod
    def load_guild(guild_id):
        day=(datetime.now()-MochiTableHelper._delta).day
        result={}
        if day in MochiTableHelper._data and guild_id in MochiTableHelper._data[day]:
            result=MochiTableHelper._data[day][guild_id]
        return result

    @staticmethod
    def create_table(guild:discord.Guild):
        members=MochiTableHelper.load_guild(guild.id)

        values=[[],[],[],[],[],[]]
        for member_id in members:
            try:
                name=guild.get_member(member_id).display_name
                if db.read_member(guild.id,"finish",member_id) != None:
                    continue
            except:
                continue
            values[0].append(name)
            for boss in range(5):
                values[boss+1].append(0)

            for i in range(len(members[member_id])):
                addition=10**int(members[member_id][i]/10)
                boss=members[member_id][i]%10
                values[boss][len(values[boss])-1]+=addition
            
        
        # 1の位　本凸
        # 10の位　長い持ち越し
        # 100の位　短い持ち越し

        # 11 12 13 14 25 長い持ち越し
        # 21 22 23 24 25 短い持ち越し
        
        
        plt.ioff()
        


        
        if len(values[0])==0:
            for i in range(6):
                values[i].append(0)
        
            
        # 表示用に変換
        values_str=[]
        for col,value_col in enumerate(values):
            str_row=[]
            for value_row in value_col:
                if type(value_row)==str:
                    str_row.append(value_row)
                    continue
                s=""
                if value_row%10 != 0:
                    s="〇"
                if int(value_row/10)%10 != 0:
                    s+="〇"
                for i in range(int(value_row/100)):
                    s+="△"
                str_row.append(s)
            values_str.append(str_row)
                
        
        data={'名前':values_str[0],'1ボス':values_str[1],'2ボス':values_str[2],'3ボス':values_str[3],'4ボス':values_str[4],'5ボス':values_str[5]}
        df=pd.DataFrame(data)
        fig, ax=plt.subplots(figsize=(10,len(values[0])*0.8))
        ax.axis('off')
        tb=ax.table(cellText=df.values,
                colLabels=df.columns,
                bbox=[0,0,1,1],
                colWidths=[5.5,1,1,1,1,1],
                cellLoc='center',)
        #色付け
        for r in range(len(values[0])):
            for c in range(5):
                if values[c+1][r]%10!=0:
                    tb[r+1,c+1].set_facecolor("#B2D235")
                elif values[c+1][r]%1000!=0:
                    tb[r+1,c+1].set_facecolor("#ffb6c1")
        
        tb.set_fontsize(15)
        buffer=BytesIO()
        extent=ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
        plt.savefig(buffer,format="png",bbox_inches=extent)
        plt.clf()
        plt.close()
        buffer.seek(0)
        return discord.File(filename="table.png",fp=buffer)
    
    @staticmethod
    def db_add(guild_id,member_id,addition):
        mochi=db.read_member(guild_id,"mochi",member_id)
        if mochi == None:
            mochi = 0
        mochi_list=[int(str(mochi)[s:s+2]) for s in range(0,len(str(mochi)),2)]
        db.write_member(guild_id,member_id,"mochi",mochi*100+addition)

    @staticmethod
    def db_remove(guild_id,member_id):
        pass
