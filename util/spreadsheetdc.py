import os
import sqlite3
import discord
import gspread
from google.oauth2.service_account import Credentials

from util.database import db
from dotenv import load_dotenv
load_dotenv()

spreadsheet_key=os.getenv("SPREADSHEET_KEY")
clientsecret_google=os.getenv("CLIENT_SECRET_GOOGLE")


class SpreadSheetDC:
    @staticmethod
    def damage_data(guild:discord.Guild,boss_no):
        damage_list=[]
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute(f"SELECT dc_{guild.id}.*,member_{guild.id}.taskkill FROM dc_{guild.id} \
                INNER JOIN member_{guild.id} ON dc_{guild.id}.id = member_{guild.id}.id \
                WHERE dc_{guild.id}.boss = {boss_no} ")
            members=sorted(cur.fetchall(),key=lambda x:x[4] if x[4] != None else 0,reverse=True)
            damage_list=[
                {
                    "no":i,
                    "member_id":m[1],
                    "name":guild.get_member(m[1]).display_name,
                    "damage":m[4],
                    "mochi":True if isinstance(m[3], str) and len(m[3]) > 1 and m[3][1]=="🔄" else False,
                    "status":m[3][-2] if isinstance(m[3], str) and len(m[3]) > 1 else "",
                    "syudou":False if "<" not in m[3] else True,
                    "taskkill":False if m[7]==None else True,
                    "comment":m[5],
                    "done":False if m[6]==0 else True
                } 
                for i,m in enumerate([m for m in members if m[6] < 1000])]
            
        except sqlite3.Error as e:
            print(e)
        conn.close()
        return damage_list
    @staticmethod
    def get_key():
        #スプシのキー
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_file(
            clientsecret_google,
            scopes=scopes
        )
        return credentials
    
    @staticmethod
    def write(guild,boss):
        if guild.id != 1276184060791750656:
            return
        if not os.path.exists(clientsecret_google):
            return
        credentials=SpreadSheetDC.get_key()

        gc = gspread.authorize(credentials)
        workbook = gc.open_by_key('1IsWbXkb8R9gZKcfoGXEIdeP_jgmFWY-duQ1lMyIB-sE')
        worksheet = workbook.worksheet(f'boss{boss}')

        worksheet.batch_clear(["A2:J30"])

        damage_list=SpreadSheetDC.damage_data(guild,boss)
        cell_list=worksheet.range(f'A2:J{len(damage_list)+1}')
        for row,damage_row in enumerate(damage_list):
            for col,value in enumerate(damage_row):
                update_number=row*len(damage_row)+col
                cell_list[update_number].value=damage_row[value]
        worksheet.update_cells(cell_list)
    

    @staticmethod
    def get_pw():
        credentials=SpreadSheetDC.get_key()

        gc = gspread.authorize(credentials)
        workbook = gc.open_by_key(spreadsheet_key)
        worksheet = workbook.worksheet(f's')
        return worksheet.acell("B4").value


