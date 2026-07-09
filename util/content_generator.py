import discord
from util.database import db
import re
import sqlite3

class Generator:
    
    
    @staticmethod
    def padding_block(names:dict):
        if len(names) == 0:
            return {}
        counter=[]
        res={}
        for _id in names:
            name:str=names[_id]
            _han=0
            _zen=0
            for c in name:
                if len(c.encode()) == 1:
                    _han+=1
                else:
                    _zen+=1
            counter.append({"id":_id,"han":_han,"zen":_zen})
        
        maxlength=max(counter,key=lambda x:x["han"]*3+x["zen"]*5)
        score=maxlength["han"]*3+maxlength["zen"]*5
        
        for d in counter:
            d_score=d["han"]*3+d["zen"]*5
            _zen_plus=min(maxlength["zen"]-d["zen"],int((score-d_score)/5))
            if _zen_plus < 0:
                _zen_plus = 0
            _han_plus=int((score-d_score-_zen_plus*5)/3)
            res[d["id"]]="`"+names[d["id"]]+"　"*_zen_plus+" "*_han_plus+"`"+"　"
        return res
    
    
    @staticmethod
    def dc_content(guild:discord.Guild,boss):
        """ダメコンメッセージの内容を生成"""
        name=db.read_guild("dc_name",guild.id).split("\n")[int(boss)-1]
        content=f">>> # {name}\n＿＿＿＿＿＿＿＿＿\n"
        sengen=""
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute(f"SELECT dc_{guild.id}.*,member_{guild.id}.taskkill FROM dc_{guild.id} \
                INNER JOIN member_{guild.id} ON dc_{guild.id}.id = member_{guild.id}.id \
                WHERE dc_{guild.id}.boss = {boss} ")
            members=sorted(cur.fetchall(),key=lambda x:x[4] if x[4] != None else 0,reverse=True)
            member_names={m[1]:guild.get_member(m[1]).display_name for m in members if m[6] != -1}
            padding_names=Generator.padding_block(member_names)
            for member in members:
                if member[6]>1000:
                    sengen+="- "+guild.get_member(member[1]).display_name+"\n"
                else:
                    name=padding_names[member[1]]
                    kill=":warning:" if member[7]!=None else "▪"
                    status=str(member[3])#.replace("⚔","⚔")
                    content+=f"- {name}{status}{kill}{member[5]}\n" if member[6]==0 \
                        else f"- {name}||{status}{kill}{member[5]}||\n"
            
            content+=f"\n凸宣言者\n{sengen}" if sengen!="" else ""

        except sqlite3.Error as e:
            print(e)
        conn.close()
        return content+"ㅤ"


    @staticmethod
    def totsu_content(guild:discord.Guild):
        members=db.execute(f"SELECT id,finish,taskkill,renamed FROM member_{guild.id}")
        c_list=[]
        counter=[0,0,0]
        for member in members:
            try:
                user=guild.get_member(member[0])
            except:
                continue
            stat=[3,0]
            if member[1]!=None:
                stat[0]=0
            elif member[3]==None:
                pass
            else:
                s1=re.search("残り?[0-3０-３]",user.display_name)
                s2=re.search("(持ち|持|餅)[0-3０-３]",user.display_name)
                if s1:
                    stat[0]=int(s1.group()[-1])
                if s2:
                    stat[1]=int(s2.group()[-1])
            tk="⚫" if member[2] == None else "🔴" 
            if member[1] != None:
                tk="🟢"
            counter[0]+=stat[0]
            counter[1]+=3-stat[0]
            counter[2]+=stat[1]
            c_list.append((f'{"✅"*(3-stat[0])}{"🔲"*stat[0]}|{"〇"*stat[1]}{"　"*(3-stat[1])}|{tk} {user.display_name}\n',stat[0]*10+stat[1]))
        c_list.sort(key=lambda x:x[1])
        content="".join([v[0] for v in c_list])
        content+=f'```\n残り{counter[0]}凸（消化済み{counter[1]}凸）:持ち越し{counter[2]}\n```'
        return content