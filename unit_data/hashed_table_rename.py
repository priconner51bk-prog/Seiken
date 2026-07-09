import sqlite3

find_names=["unit_data","unit_profile","unit_attack_pattern","unit_skill_data","skill_action","skill_data","clan_battle_2_map_data","wave_group_data","enemy_parameter"]

class HashedTableRename:
    @staticmethod
    def run():
        
        conn=sqlite3.connect("unit_data/original.db")
        conn.row_factory=sqlite3.Row
        cur=conn.cursor()

        cur.execute("SELECT * FROM sqlite_master WHERE type='table'")
        original_table=cur.fetchall()

        
        original_DB={}

        for table in original_table:
            name=dict(table)["name"]
            cur.execute(f"SELECT * FROM {name}")
            desc=[v[0] for v in cur.description]
            val=list(map(list,cur.fetchall()))
            val.insert(0,desc)
            original_DB[name]=val

        cur.close()
        conn.close()
        #####################################################################################
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
            hashed_DB[name]=val
        
        conn.close()

        HashedTableRename.find_table(original_DB,hashed_DB)

    @staticmethod
    def find_table(original_DB:dict,hashed_DB:dict):
        conn=sqlite3.connect("unit_data/master.db")
        conn.row_factory=sqlite3.Row
        cur=conn.cursor()


        for hashed_table_name in hashed_DB:
            for find_name in find_names:
                if HashedTableRename.deep_equal(original_DB[find_name],hashed_DB[hashed_table_name]):
                    HashedTableRename.rename(cur,original_DB[find_name],find_name,hashed_DB[hashed_table_name],hashed_table_name)

        conn.commit()
        conn.close()
        
    
    @staticmethod
    def deep_equal(original_table,hashed_table):
        ###############################################################
        # 最初の1行で判別
        ###############################################################
        equal=True
        if len(original_table) >= 2 and len(hashed_table) >= 2:
            if len(original_table[0]) == len(hashed_table[0]):
                for col in range(len(original_table[0])):
                    if original_table[1][col] != hashed_table[1][col]:
                        equal=False
            elif len(original_table[0]) < len(hashed_table[0]) and len(original_table[0]) >= 10:
                count=0
                # カラムが追加されたときの処理
                for col in range(len(original_table[0])):
                    if not original_table[0][col] in hashed_table[0]:
                        equal=False
                    else:
                        count+=1
            else:
                equal=False
        else:
            equal=False
        
        return equal
    
    @staticmethod
    def rename(cur:sqlite3.Cursor,original_table,find_name,hashed_table,hashed_table_name):
        if find_name == hashed_table_name:
            return
        if len(original_table[0]) == len(hashed_table[0]):
            for col in range(len(original_table[0])):
                original_col_name=original_table[0][col]
                hashed_col_name=hashed_table[0][col]
                cur.execute(f'ALTER TABLE "{hashed_table_name}" RENAME COLUMN "{hashed_col_name}" TO "{original_col_name}"')
        cur.execute(f'ALTER TABLE "{hashed_table_name}" RENAME TO "{find_name}"')
            