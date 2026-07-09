import json
import sqlite3

import util.database

class ClanBossData:
    @staticmethod
    def check_update() -> bool:
        isupdate=False
        try:
            with open("unit_data/version.json") as f:
                d=json.load(f)
                clan_battle_id=d["clan_battle_id"]
        except:
            clan_battle_id=0

        dbname="unit_data/unit.db"
        conn=sqlite3.connect(dbname)
        cur=conn.cursor()

        cur.execute("SELECT clan_battle_id FROM clan_battle_2_map_data ORDER BY id DESC LIMIT 1")
        latest_clan_battle_id=cur.fetchone()[0]
        if latest_clan_battle_id > clan_battle_id:
            d["clan_battle_id"]=latest_clan_battle_id
            isupdate=True
        

        conn.close()
        with open("unit_data/version.json","wt") as f:
                json.dump(d,f)

        return isupdate

    
    @staticmethod
    def get_enemy_id() -> list:
        dbname="unit_data/unit.db"
        conn=sqlite3.connect(dbname)
        cur=conn.cursor()

        cur.execute("SELECT wave_group_id_1,wave_group_id_2,wave_group_id_3,wave_group_id_4,wave_group_id_5 FROM clan_battle_2_map_data ORDER BY id DESC LIMIT 1")
        
        wave_group_ids=cur.fetchone()

        enemy_parameters=[[],[],[],[],[]]

        for boss in range(5):
            cur.execute("SELECT enemy_id_1 FROM wave_group_data WHERE wave_group_id = {0}".format(wave_group_ids[boss]))

            enemy_id=cur.fetchone()[0]
            cur.execute("SELECT unit_id,name,hp FROM enemy_parameter WHERE enemy_id = {0}".format(enemy_id))

            target_parameter=cur.fetchone()
            enemy_parameters[boss].append(target_parameter)

            print(target_parameter)
            

        conn.close()

        return enemy_parameters
    

    
