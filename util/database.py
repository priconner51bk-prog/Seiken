import sqlite3

class db:
    dbname="pric.db"
    def execute(sql:str):
        res=None
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute(sql)
            if sql.lower().startswith("update") or sql.lower().startswith("insert") or sql.lower().startswith("delete") or sql.lower().startswith("create"):
                conn.commit()
            elif sql.lower().startswith("select"):
                res=cur.fetchall()
        except sqlite3.Error as e:
            print(e)
        conn.close()
        return res

    def read_member(guild_id:int,key:str,id=None):
        res=None
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            if id==None:
                key0=key.split(",")[0]
                cur.execute(f"SELECT id,{key} FROM member_{guild_id} WHERE {key0} IS NOT NULL")
                res=cur.fetchall()
            else:
                cur.execute(f"SELECT {key} FROM member_{guild_id} WHERE id = {str(id)}")
                val=cur.fetchone()[0]
                res=val
        except:
            pass

        conn.close()
        return res

    def read_guild(key:str,id=None):
        res=None
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            if id==None:
                key0=key.split(",")[0]
                cur.execute(f"SELECT id,{key} FROM guild WHERE {key0} IS NOT NULL")
                res=cur.fetchall()
            else:
                cur.execute(f"SELECT {key} FROM guild WHERE id = {str(id)}")
                val=cur.fetchone()[0]
                res=val
        except Exception as e:
            print(e)

        conn.close()
        return res
    def read_post(pid,key):
        res=None
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute(f"SELECT {key} FROM post WHERE pid={pid}")
            res=cur.fetchone()[0]
        except:
            pass

        conn.close()
        return res

    def read_word(guild_id:int):
        res=None
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute(f"SELECT * FROM word_{guild_id}")
            res=cur.fetchall()
        except:
            pass

        conn.close()
        return res

    def write_member(guild_id:int,id,key:str,value):
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute(f'''CREATE TABLE IF NOT EXISTS member_{str(guild_id)} (
                        id INTEGER PRIMARY KEY,
                        display_name TEXT,
                        finish INTEGER,
                        renamed INTEGER,
                        totsu INTEGER,
                        boss1 INTEGER,
                        boss2 INTEGER,
                        boss3 INTEGER,
                        boss4 INTEGER,
                        boss5 INTEGER,
                        AFK INTEGER,
                        mochi INTEGER,
                        taskkill INTEGER,
                        route TEXT
                        )''')
            
            cur.execute(f"INSERT INTO member_{str(guild_id)} (id,{key}) VALUES ({str(id)},'{str(value)}') \
                            ON CONFLICT(id) DO UPDATE SET {key}='{str(value)}'")
            conn.commit()
        except sqlite3.Error as e:
            print(e)
        conn.close()

    
    def write_guild(id,key:str,value):
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute('''CREATE TABLE IF NOT EXISTS guild (
                        id INTEGER PRIMARY KEY,
                        prefix TEXT,
                        role INTEGER,
                        reaction_ch INTEGER,
                        reaction_msg INTEGER,
                        reaction_mochi_msg INTEGER,
                        dc_ch INTEGER,
                        dc_msg TEXT,
                        dc_name TEXT,
                        unknown_msg INTEGER,
                        kanryou_ch INTEGER,
                        log_ch INTEGER,
                        taskkill_ch INTEGER,
                        sengen_ch INTEGER,
                        mochikoshi_ch INTEGER,
                        totsukanri_ch INTEGER,
                        totsukanri_msg INTEGER,
                        imgfixed_ch INTEGER,
                        imgfixed_msg INTEGER,
                        imgfixed2_ch INTEGER,
                        imgfixed2_msg INTEGER,
                        suspend_sengen INTEGER,
                        emoji TEXT,
                        emoji2 TEXT
                        )''')
            
            cur.execute(f"INSERT INTO guild (id,{key}) VALUES ({str(id)},'{str(value)}') \
                            ON CONFLICT(id) DO UPDATE SET {key}='{str(value)}'")
            conn.commit()
        except sqlite3.Error as e:
            print(e)
        conn.close()

    def write_post(pid,timestamp,guild_id,message_id,message_ch,send_ch):
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute('''CREATE TABLE IF NOT EXISTS post (
                        pid  INTEGER PRIMARY KEY,
                        timestamp INTEGER,
                        guild_id INTEGER,
                        message_id INTEGER,
                        message_ch INTEGER,
                        send_ch INTEGER,
                        mentions TEXT
                        )''')
            
            cur.execute(f"INSERT INTO post (pid,timestamp,guild_id,message_id,message_ch,send_ch)\
                 VALUES ({pid},{timestamp},{guild_id},{message_id},{message_ch},{send_ch})")
            conn.commit()
        except sqlite3.Error as e:
            print(e)
        conn.close()    
    
    def write_word(guild_id:int,word:str,response:str):
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute(f'''CREATE TABLE IF NOT EXISTS word_{guild_id} (
                        word TEXT PRIMARY KEY,
                        response TEXT
                        )''')
            
            cur.execute(f"INSERT INTO word_{guild_id} (word,response) VALUES ('{word}','{response}') \
                            ON CONFLICT(word) DO UPDATE SET response='{response}'")
            conn.commit()
        except sqlite3.Error as e:
            print(e)
        conn.close()
    
    def delete_member(guild_id:int,id,key:str=None):
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            if key==None:
                cur.execute(f"DELETE FROM member_{guild_id} WHERE id = {id}")
            else:
                cur.execute(f"UPDATE member_{guild_id} SET {key} = NULL WHERE id = {id}")
            conn.commit()
        except:
            pass
        conn.close()
    
    def delete_guild(guild_id:int,key:str=None):
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            if key==None:
                cur.execute(f"DELETE FROM guild WHERE id = {guild_id}")
            else:
                cur.execute(f"UPDATE guild SET {key} = NULL WHERE id = {guild_id}")
            conn.commit()
        except:
            pass
        conn.close()
    
    def delete_word(guild_id:int,key:str):
        conn=sqlite3.connect(db.dbname)
        cur=conn.cursor()
        try:
            cur.execute(f"DELETE FROM word_{guild_id} WHERE word = '{key}'")
            conn.commit()
        except Exception as e:
            print(e)
        conn.close()