
import requests
import re
import datetime
import brotli
import sqlite3
import subprocess
import os



class Unhash():
    @staticmethod
    def run():
        Unhash.initialize()
        Unhash.search()

    @staticmethod
    def initialize():
        if os.path.isfile("unit_data/unit.db"):
            os.remove("unit_data/unit.db")

        conn=sqlite3.connect("unit_data/unit.db")
        conn.row_factory=sqlite3.Row
        cur=conn.cursor()

        cur.execute(f'''CREATE TABLE unit_data (
                        unit_id INTEGER PRIMARY KEY,
                        unit_name STRING,
                        kana STRING,
                        comment STRING,
                        original_unit_id INTEGER
                        )''')
        cur.execute(f'''CREATE TABLE unit_profile (
                        unit_id INTEGER PRIMARY KEY,
                        unit_name STRING,
                        age STRING,
                        guild STRING,
                        race STRING,
                        height STRING,
                        weight STRING,
                        birth_month STRING,
                        birth_day STRING,
                        blood_type STRING
                        )''')
        cur.execute(f'''CREATE TABLE unit_attack_pattern (
                        pattern_id INTEGER PRIMARY KEY,
                        unit_id INTEGER,
                        loop_start INTEGER,
                        loop_end INTEGER,
                        atk_pattern_1 INTEGER,
                        atk_pattern_2 INTEGER,
                        atk_pattern_3 INTEGER,
                        atk_pattern_4 INTEGER,
                        atk_pattern_5 INTEGER,
                        atk_pattern_6 INTEGER,
                        atk_pattern_7 INTEGER,
                        atk_pattern_8 INTEGER,
                        atk_pattern_9 INTEGER,
                        atk_pattern_10 INTEGER,
                        atk_pattern_11 INTEGER,
                        atk_pattern_12 INTEGER,
                        atk_pattern_13 INTEGER,
                        atk_pattern_14 INTEGER,
                        atk_pattern_15 INTEGER,
                        atk_pattern_16 INTEGER,
                        atk_pattern_17 INTEGER,
                        atk_pattern_18 INTEGER,
                        atk_pattern_19 INTEGER,
                        atk_pattern_20 INTEGER
                        )''')
        cur.execute(f'''CREATE TABLE unit_skill_data (
                        unit_id INTEGER PRIMARY KEY,
                        union_burst INTEGER,
                        main_skill_1 INTEGER,
                        main_skill_2 INTEGER,
                        main_skill_3 INTEGER,
                        main_skill_4 INTEGER,
                        main_skill_5 INTEGER,
                        main_skill_6 INTEGER,
                        main_skill_7 INTEGER,
                        main_skill_8 INTEGER,
                        main_skill_9 INTEGER,
                        main_skill_10 INTEGER,
                        ex_skill_1 INTEGER,
                        ex_skill_evolution_1 INTEGER,
                        ex_skill_2 INTEGER DEFAULT 0,
                        ex_skill_evolution_2 INTEGER DEFAULT 0,
                        ex_skill_3 INTEGER DEFAULT 0,
                        ex_skill_evolution_3 INTEGER DEFAULT 0,
                        ex_skill_4 INTEGER DEFAULT 0,
                        ex_skill_evolution_4 INTEGER DEFAULT 0,
                        ex_skill_5 INTEGER DEFAULT 0,
                        ex_skill_evolution_5 INTEGER DEFAULT 0,
                        sp_union_burst INTEGER,
                        sp_skill_1 INTEGER,
                        sp_skill_2 INTEGER,
                        sp_skill_3 INTEGER,
                        sp_skill_4 INTEGER DEFAULT 0,
                        sp_skill_5 INTEGER DEFAULT 0,
                        union_burst_evolution INTEGER,
                        main_skill_evolution_1 INTEGER,
                        main_skill_evolution_2 INTEGER,
                        sp_skill_evolution_1 INTEGER,
                        sp_skill_evolution_2 INTEGER DEFAULT 0
                        )''')
        cur.execute(f'''CREATE TABLE skill_action (
                        action_id INTEGER PRIMARY KEY,
                        class_id INTEGER,
                        action_type INTEGER,
                        action_detail_1 INTEGER,
                        action_detail_2 INTEGER,
                        action_detail_3 INTEGER,
                        action_value_1 INTEGER,
                        action_value_2 INTEGER,
                        action_value_3 INTEGER,
                        action_value_4 INTEGER,
                        action_value_5 INTEGER,
                        action_value_6 INTEGER,
                        action_value_7 INTEGER,
                        target_assignment INTEGER,
                        target_area INTEGER,
                        target_range INTEGER,
                        target_type INTEGER,
                        target_number INTEGER,
                        target_count INTEGER,
                        description STRING,
                        level_up_disp STRING
                        )''')
        cur.execute(f'''CREATE TABLE skill_data (
                        skill_id INTEGER PRIMARY KEY,
                        name STRING,
                        skill_type INTEGER,
                        skill_area_width INTEGER,
                        skill_cast_time INTEGER,
                        action_1 INTEGER,
                        action_2 INTEGER,
                        action_3 INTEGER,
                        action_4 INTEGER,
                        action_5 INTEGER,
                        action_6 INTEGER,
                        action_7 INTEGER,
                        action_8 INTEGER,
                        action_9 INTEGER,
                        action_10 INTEGER,
                        depend_action_1 INTEGER,
                        depend_action_2 INTEGER,
                        depend_action_3 INTEGER,
                        depend_action_4 INTEGER,
                        depend_action_5 INTEGER,
                        depend_action_6 INTEGER,
                        depend_action_7 INTEGER,
                        depend_action_8 INTEGER,
                        depend_action_9 INTEGER,
                        depend_action_10 INTEGER,
                        description STRING,
                        icon_type INTEGER
                        )''')
        cur.execute(f'''CREATE TABLE clan_battle_2_map_data (
                        id INTEGER PRIMARY KEY,
                        clan_battle_id INTEGER,
                        wave_group_id_1 INTEGER,
                        wave_group_id_2 INTEGER,
                        wave_group_id_3 INTEGER,
                        wave_group_id_4 INTEGER,
                        wave_group_id_5 INTEGER
                        )''')
        cur.execute(f'''CREATE TABLE wave_group_data (
                        id INTEGER PRIMARY KEY,
                        wave_group_id INTEGRE,
                        enemy_id_1 INTEGER
                        )''')
        cur.execute(f'''CREATE TABLE enemy_parameter (
                        enemy_id INTEGER PRIMARY KEY,
                        unit_id INTEGRE,
                        name STRING,
                        hp INTEGER
                        )''')

        conn.commit()
        conn.close()
    
    @staticmethod
    def insert(table_name:str,table:list,column:dict):
        conn=sqlite3.connect("unit_data/unit.db")
        conn.row_factory=sqlite3.Row
        cur=conn.cursor()

        column_list=[(column[x],x) for x in column]
        execute_list=[]

        for row in range(1,len(table)):
            row_val=[]
            for i,col_name in column_list:
                row_val.append(table[row][i])
            execute_list.append(row_val)
        
        col_names=",".join([x[1] for x in column_list])
        values=("?,"*len(column_list))[:-1]
        cur.executemany(f"INSERT INTO {table_name} ({col_names}) VALUES ({values})",execute_list)

        conn.commit()
        conn.close()

    @staticmethod
    def search():
        done={}
        conn=sqlite3.connect("unit_data/master.db")
        conn.row_factory=sqlite3.Row
        cur=conn.cursor()

        cur.execute("SELECT * FROM sqlite_master WHERE type='table'")
        hashed_table=cur.fetchall()

                
        hashed_DB={}

        for table in hashed_table:
            name=dict(table)["name"]
            cur.execute(f"SELECT * FROM {name}")
            desc=[v[0] for v in cur.description]
            val=list(map(list,cur.fetchall()))
            val.insert(0,desc)
            if len(val)<=1:
                continue
            # unit_data ヒヨリのテキストで判別
            if "unit_data" not in done and "【物理】前衛で、敵前線を押し返す笑顔の元気娘。\\n前衛に対して大ダメージを与えるユニオンバーストと、\\n自身の攻撃力を強化するスキルを持つ攻撃役。" in val[1]:
                sql=dict(table)["sql"]
                t=re.search(r"PRIMARY.+'.+'",sql)
                pk=re.search("'.+'",t.group()).group()[1:-1]
                Unhash.unit_data(val,pk)
                done["unit_data"]=True

            elif "unit_profile" not in done and "人助けが大好き！\u3000前向き格闘娘" in val[1]:
                Unhash.unit_profile(val)
                done["unit_profile"]=True
            
            elif "unit_attack_pattern" not in done and 10010101 in val[1] and 1002 in val[1]:
                Unhash.unit_attack_pattern(val)
                done["unit_attack_pattern"]=True
                
            elif "unit_skill_data" not in done and 100101 in val[1] and 1001001 in val[1] and 1001501 in val[1]:
                Unhash.unit_skill_data(val)
                done["unit_skill_data"]=True
            
            elif "skill_action" not in done and 100100101 in val[1] and r"敵単体に{0}の物理ダメージ" in val[1]:
                Unhash.skill_action(val)
                done["skill_action"]=True

            elif "skill_data" not in done and "ヒヨリラッシュ" in val[1]:
                Unhash.skill_data(val)
                done["skill_data"]=True
            
            elif "clan_battle_2_map_data" not in done and len(val) >= 338 and 401061411 in val[337] and 401061421 in val[337]:
                Unhash.clan_battle_2_map_data(val)
                done["clan_battle_2_map_data"]=True
            
            elif "wave_group_data" not in done and 100000001 in val[1] and 512000021 in val[1]:
                Unhash.wave_group_data(val)
                done["wave_group_data"]=True
            
            elif "enemy_parameter" not in done and 100000001 in val[1] and "ヒカリタケ" in val[1]:
                Unhash.enemy_parameter(val)
                done["enemy_parameter"]=True

        cur.close()
        conn.close()
    

    @staticmethod
    def unit_data(table:list,pk):
        def hatsune_index(table):
            for i,row in enumerate(table):
                if "ハツネ（ハツネ&シオリ）" in row:
                    return i
            return 1
        column={}
        h_index=hatsune_index(table)
        for i,col_name in enumerate(table[0]):
            match table[1][i]:
                case 100101 if col_name==pk:
                    column["unit_id"]=i
                case "ヒヨリ":
                    column["unit_name"]=i
                case "ひより":
                    column["kana"]=i
                case "【物理】前衛で、敵前線を押し返す笑顔の元気娘。\\n前衛に対して大ダメージを与えるユニオンバーストと、\\n自身の攻撃力を強化するスキルを持つ攻撃役。":
                    column["comment"]=i
                case 0 if table[h_index][i]==180701:
                    column["original_unit_id"]=i
        Unhash.insert("unit_data",table,column)
    
    @staticmethod
    def unit_profile(table:list):
        column={}
        for i,col_name in enumerate(table[0]):
            match table[1][i]:
                case 100101:
                    column["unit_id"]=i
                case "ヒヨリ":
                    column["unit_name"]=i
                case "16":
                    column["age"]=i
                case "トゥインクルウィッシュ":
                    column["guild"]=i
                case "獣人族":
                    column["race"]=i
                case "155":
                    column["height"]=i
                case "44":
                    column["weight"]=i
                case "8":
                    column["birth_month"]=i
                case "27":
                    column["birth_day"]=i
                case "A":
                    column["blood_type"]=i
        Unhash.insert("unit_profile",table,column)
    
    @staticmethod
    def unit_attack_pattern(table:list):

        column={}
        rest=[x for x in range(len(table[0]))]
        pattern_id=[]
        for i,col_name in enumerate(table[0]):
            match table[1][i]:
                case 10010101:
                    column["pattern_id"]=i
                    rest.remove(i)
                    pattern_id=[x[i] for x in table]
                case 100101:
                    column["unit_id"]=i
                    rest.remove(i)
                case 3:
                    column["loop_start"]=i
                    rest.remove(i)
                case 7:
                    column["loop_end"]=i
                    rest.remove(i)
                case 1002 if table[5][i] == 1002:
                    column["atk_pattern_1"]=i
                    rest.remove(i)
                case 1001 if table[3][i] == 1001:
                    column["atk_pattern_2"]=i
                    rest.remove(i)
                case 1 if table[3][i] == 1002:
                    column["atk_pattern_3"]=i
                    rest.remove(i)
                case 1 if table[3][i] == 1:
                    column["atk_pattern_4"]=i
                    rest.remove(i)
                case 1002 if table[5][i] == 1001:
                    column["atk_pattern_5"]=i
                    rest.remove(i)
                case 1 if table[3][i] == 1001:
                    column["atk_pattern_6"]=i
                    rest.remove(i)
                case 1001 if table[3][i] ==1:
                    column["atk_pattern_7"]=i
                    rest.remove(i)
                case 0 if table[3][i] == 1002:
                    column["atk_pattern_8"]=i
                    rest.remove(i)
                case 0 if table[7][i] == 1001:
                    column["atk_pattern_9"]=i
                    rest.remove(i)
                case 0 if table[2][i] == 1001:
                    column["atk_pattern_10"]=i
                    rest.remove(i)
        # 11~13の判定
        pattern_13_index=pattern_id.index(10490101)
        for i in rest[:]:
            match table[pattern_13_index][i]:
                case 1002:
                    column["atk_pattern_11"]=i
                    rest.remove(i)
                case 1:
                    column["atk_pattern_12"]=i
                    rest.remove(i)
                case 1001:
                    column["atk_pattern_13"]=i
                    rest.remove(i)
        # 14~15
        pattern_15_index=pattern_id.index(18010101)
        for i in rest[:]:
            match table[pattern_15_index][i]:
                case 1:
                    column["atk_pattern_14"]=i
                    rest.remove(i)
                case 1001:
                    column["atk_pattern_15"]=i
                    rest.remove(i)
        # 16~17
        pattern_16_index=pattern_id.index(10650101)
        pattern_17_index=pattern_id.index(10820101)
        for i in rest[:]:
            if table[pattern_17_index][i] == 1:
                column["atk_pattern_16"]=i
                rest.remove(i)
            elif table[pattern_17_index][i] == 1001:
                column["atk_pattern_17"]=i
                rest.remove(i)
        # 18~19
        pattern_19_index=pattern_id.index(12450101)
        for i in rest[:]:
            match table[pattern_19_index][i]:
                case 1:
                    column["atk_pattern_18"]=i
                    rest.remove(i)
                case 1001:
                    column["atk_pattern_19"]=i
                    rest.remove(i)
        if len(rest)==1:
            column["atk_pattern_20"]=rest[0]
        Unhash.insert("unit_attack_pattern",table,column)
    
    @staticmethod
    def unit_skill_data(table:list):
        column={}
        rest=[x for x in range(len(table[0]))]
        unit_id=[]
        for i,col_name in enumerate(table[0]):
            match table[1][i]:
                case 100101:
                    column["unit_id"]=i
                    rest.remove(i)
                    unit_id=[x[i] for x in table]
                case 1001001:
                    column["union_burst"]=i
                    rest.remove(i)
                case 1001002:
                    column["main_skill_1"]=i
                    rest.remove(i)
                case 1001003:
                    column["main_skill_2"]=i
                    rest.remove(i)
                case 1001501:
                    column["ex_skill_1"]=i
                    rest.remove(i)
                case 1001511:
                    column["ex_skill_evolution_1"]=i
                    rest.remove(i)
                case 1001011:
                    column["union_burst_evolution"]=i
                    rest.remove(i)
                case 1001012:
                    column["main_skill_evolution_1"]=i
                    rest.remove(i)
        
        # main_skill_3~10
        main_skill_10_index=unit_id.index(315404)
        for i in  rest[:]:
            match table[main_skill_10_index][i]:
                case 3154014:
                    column["main_skill_3"]=i
                    rest.remove(i)
                case 3154005:
                    column["main_skill_4"]=i
                    rest.remove(i)
                case 3154016:
                    column["main_skill_5"]=i
                    rest.remove(i)
                case 3154007:
                    column["main_skill_6"]=i
                    rest.remove(i)
                case 3154018:
                    column["main_skill_7"]=i
                    rest.remove(i)
                case 3154019:
                    column["main_skill_8"]=i
                    rest.remove(i)
                case 3154020:
                    column["main_skill_9"]=i
                    rest.remove(i)
                case 3154021:
                    column["main_skill_10"]=i
                    rest.remove(i)
        # ex2~は無し
        # sp_skill_1~3
        sp_skill_3_index=unit_id.index(115801)
        for i in  rest[:]:
            match table[sp_skill_3_index][i]:
                case 1158100:
                    column["sp_union_burst"]=i
                    rest.remove(i)
                case 1158101:
                    column["sp_skill_1"]=i
                    rest.remove(i)
                case 1158102:
                    column["sp_skill_2"]=i
                    rest.remove(i)
                case 1158103:
                    column["sp_skill_3"]=i
                    rest.remove(i)
        # sp_skill_4~は無し
        # main_skill_evolution_2
        main_skill_evolution_2_index=unit_id.index(108601)
        for i in  rest[:]:
            match table[main_skill_evolution_2_index][i]:
                case 1086013:
                    column["main_skill_evolution_2"]=i
                    rest.remove(i)
        # sp_skill_evolution_1
        sp_skill_evolution_1_index=unit_id.index(122301)
        for i in  rest[:]:
            match table[sp_skill_evolution_1_index][i]:
                case 1223111:
                    column["sp_skill_evolution_1"]=i
                    rest.remove(i)

        Unhash.insert("unit_skill_data",table,column)
    
    @staticmethod
    def skill_action(table:list):
        column={}
        rest=[x for x in range(len(table[0]))]
        action_id=[]
        for i,col_name in enumerate(table[0]):
            if table[1][i]==100100101:
                column["action_id"]=i
                rest.remove(i)
                action_id=[x[i] for x in table]
                break
        comp150101_index=action_id.index(100150101)
        comp300301_index=action_id.index(100300301)
        for i in rest[:]:
            match table[1][i]:
                case 1 if table[comp150101_index][i] == 1:
                    column["class_id"]=i
                    rest.remove(i)
                case 1 if table[comp150101_index][i] == 90:
                    column["action_type"]=i
                    rest.remove(i)
                case 1 if table[comp150101_index][i] == 2:
                    column["action_detail_1"]=i
                    rest.remove(i)
                case 0 if table[comp300301_index][i] == 100300303:
                    column["action_detail_2"]=i
                    rest.remove(i)
                case 0 if table[comp300301_index][i] == 100300302:
                    column["action_detail_3"]=i
                    rest.remove(i)
                case 30 if table[2][i] == 50:
                    column["action_value_1"]=i
                    rest.remove(i)
                case 30 if table[2][i] == 0:
                    column["action_value_2"]=i
                    rest.remove(i)
                case 2.4:
                    column["action_value_3"]=i
                    rest.remove(i)
                case 1 if table[3][i]==2:
                    column["target_area"]=i
                    rest.remove(i)
                case -1:
                    column["target_range"]=i
                    rest.remove(i)
                case 3:
                    column["target_type"]=i
                    rest.remove(i)
                case 1 if table[2][i]==99:
                    column["target_count"]=i
                    rest.remove(i)
                case r"敵単体に{0}の物理ダメージ":
                    column["description"]=i
                    rest.remove(i)
                case r"単体物理ダメージ+{0}":
                    column["level_up_disp"]=i
                    rest.remove(i)

        # action_value_4~7
        val_4_index=action_id.index(100100302)
        val_5_index=action_id.index(100900301)
        val_6_index=action_id.index(101101101)
        val_7_index=action_id.index(100100302)
        for i in  rest[:]:
            if table[val_4_index][i]==12:
                    column["action_value_4"]=i
                    rest.remove(i)
            if table[val_5_index][i]==1:
                    column["action_value_5"]=i
                    rest.remove(i)
            if table[val_6_index][i]==1.75:
                    column["action_value_6"]=i
                    rest.remove(i)
            if table[val_7_index][i]==1:
                    column["action_value_7"]=i
                    rest.remove(i)


        # target_assignment
        assignment_index=action_id.index(100100302)
        for i in rest[:]:
            if table[1][i]==1 and table[assignment_index][i] == 2:
                column["target_assignment"]=i
                rest.remove(i)

        # target_number
        number_index=action_id.index(100400101)
        for i in rest[:]:
            if table[1][i]==0 and table[number_index][i] == 1:
                column["target_number"]=i
                rest.remove(i)

        Unhash.insert("skill_action",table,column)
    
    @staticmethod
    def skill_data(table:list):
        column={}
        rest=[x for x in range(len(table[0]))]
        skill_id=[]
        for i,col_name in enumerate(table[0]):
            match table[1][i]:
                case 1001001:
                    column["skill_id"]=i
                    rest.remove(i)
                    skill_id=[x[i] for x in table]
                case "ヒヨリラッシュ":
                    column["name"]=i
                    rest.remove(i)
                case v if table[2][i]==1.125:
                    column["skill_cast_time"]=i
                    rest.remove(i)
                case "目の前の敵１キャラに物理大ダメージを与え、さらに自分を中心とした範囲内の敵すべてに物理中ダメージを与える。":
                    column["description"]=i
                    rest.remove(i)
                case 1001:
                    column["icon_type"]=i
                    rest.remove(i)


        #skill_type
        skill_type_index=skill_id.index(1002001)
        for i in rest[:]:
            if table[skill_type_index][i]==1:
                column["skill_type"]=i
                rest.remove(i)

        # skill_area
        skill_area_index=skill_id.index(1009003)
        for i in rest[:]:
            if table[skill_area_index][i]==2160:
                column["skill_area_width"]=i
                rest.remove(i)
        
        #action_1~10
        
        action_index=skill_id.index(1065011)
        for i in rest[:]:
            match table[action_index][i]:
                case 106501101:
                    column["action_1"]=i
                    rest.remove(i)
                case 106501102:
                    column["action_2"]=i
                    rest.remove(i)
                case 106501103:
                    column["action_3"]=i
                    rest.remove(i)
                case 106501104:
                    column["action_4"]=i
                    rest.remove(i)
                case 106501105:
                    column["action_5"]=i
                    rest.remove(i)
                case 106501106:
                    column["action_6"]=i
                    rest.remove(i)
                case 106501107:
                    column["action_7"]=i
                    rest.remove(i)
                case 106501108:
                    column["action_8"]=i
                    rest.remove(i)
                case 106501109:
                    column["action_9"]=i
                    rest.remove(i)
                case 106501110:
                    column["action_10"]=i
                    rest.remove(i)
        depend_action_1_index=skill_id.index(1272003)
        depend_action_2_index=skill_id.index(1001001)
        depend_action_3_index=skill_id.index(1005001)
        depend_action_4_index=skill_id.index(1003012)
        depend_action_5_index=skill_id.index(1003012)
        depend_action_6_index=skill_id.index(1033011)
        depend_action_7_index=skill_id.index(1067002)
        depend_action_8_index=skill_id.index(1014011)
        depend_action_9_index=skill_id.index(1229012)
        #depend_action_10_index=skill_id.index(3002053)
        for i in  rest[:]:
            if table[depend_action_2_index][i]==100100102:
                    column["depend_action_2"]=i
                    rest.remove(i)
            elif table[depend_action_3_index][i]==100500102:
                    column["depend_action_3"]=i
                    rest.remove(i)
            elif table[depend_action_4_index][i]==100301202:
                    column["depend_action_4"]=i
                    rest.remove(i)
            elif table[depend_action_5_index][i]==100301203:
                    column["depend_action_5"]=i
                    rest.remove(i)
            elif table[depend_action_6_index][i]==103301105:
                    column["depend_action_6"]=i
                    rest.remove(i)
            elif table[depend_action_7_index][i]==106700203:
                    column["depend_action_7"]=i
                    rest.remove(i)
        
        for i in  rest[:]:
            if table[depend_action_1_index][i]==127200304:
                    column["depend_action_1"]=i
                    rest.remove(i)
            elif table[depend_action_8_index][i]==101401105:
                    column["depend_action_8"]=i
                    rest.remove(i)
            elif table[depend_action_9_index][i]==122901203:
                    column["depend_action_9"]=i
                    rest.remove(i)
            #elif table[depend_action_10_index][i]==300205308:
            #        column["depend_action_10"]=i
            #        rest.remove(i)
        if len(rest)==1:
            column["depend_action_10"]=rest[0]

        Unhash.insert("skill_data",table,column)
    
    @staticmethod
    def clan_battle_2_map_data(table:list):
        column={}
        for i,col_name in enumerate(table[0]):
            match table[1][i]:
                case 1 if table[3][i]==3:
                    column["id"]=i
                case 1001:
                    column["clan_battle_id"]=i
                case 401010011:
                    column["wave_group_id_1"]=i
                case 401010021:
                    column["wave_group_id_2"]=i
                case 401010031:
                    column["wave_group_id_3"]=i
                case 401010041:
                    column["wave_group_id_4"]=i
                case 401010051:
                    column["wave_group_id_5"]=i
                
        Unhash.insert("clan_battle_2_map_data",table,column)
    
    @staticmethod
    def wave_group_data(table:list):
        column={}
        for i,col_name in enumerate(table[0]):
            match table[1][i]:
                case 100000001 if table[2][i] == 100000002:
                    column["id"]=i
                case 512000021:
                    column["wave_group_id"]=i
                case 100000001 if table[2][i] == 100000001:
                    column["enemy_id_1"]=i

        Unhash.insert("wave_group_data",table,column)
                
    @staticmethod
    def enemy_parameter(table:list):
        column={}
        for i,col_name in enumerate(table[0]):
            match table[1][i]:
                case 100000001:
                    column["enemy_id"]=i
                case 202100:
                    column["unit_id"]=i
                case "ヒカリタケ":
                    column["name"]=i
                case 175:
                    column["hp"]=i

        Unhash.insert("enemy_parameter",table,column)
