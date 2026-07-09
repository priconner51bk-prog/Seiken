
import datetime
import json
import os
import re
import subprocess
import sqlite3
import brotli

import requests


class CheckMaster:
    @staticmethod
    def check_update():
        version=10010800
        hash=""
        clan_battle_id=1001
        try:
            with open("unit_data/version.json") as f:
                d=json.load(f)
                version=d["version"]
                hash=d["hash"]
                clan_battle_id=d["clan_battle_id"]
        except:
            pass

        # トレモ入ったら更新確認する
        # 月初から8日前
        today = datetime.datetime.today()
        next_day= today + datetime.timedelta(days=8)
        if next_day.day == 1 and today.hour == 6:
            version = version-10
            clan_battle_id = 0


        new_version=version
        for i in range(1,30):

            # 10刻みで応答を確認
            guess = version+i*10
            response=requests.get(f"http://prd-priconne-redive.akamaized.net/dl/Resources/{guess}/Jpn/AssetBundles/iOS/manifest/masterdata_assetmanifest")
            
            # 応答があった場合バージョンを更新
            if response.status_code == 200:
                new_version=guess
                hash=response.text.split(",")[1]
                print(f"{guess}  ok")
            else:
                continue
        
        # バージョンが更新されていたならjson出力とデータベースの更新をする
        if new_version != version:
            CheckMaster.download_from_web(new_version,hash)
            with open("unit_data/version.json","wt") as f:
                json.dump({"version":new_version,"hash":hash,"clan_battle_id":clan_battle_id},f)
        
        return new_version != version
    
    @staticmethod
    def download(version,hash):

        response=requests.get(f"http://prd-priconne-redive.akamaized.net/dl/pool/AssetBundles/{hash[:2]}/{hash}")
        if response.status_code == 200:
            with open("unit_data/master.cdb","wb") as cdb:
                cdb.write(response.content)
            match os.name:
                case "nt":
                    subprocess.call(f'unit_data\\Coneshell_call.exe -cdb unit_data\\master.cdb unit_data\\master.db'.split())
                case "posix":
                    # Linuxの場合はwineを使用してConeshell_call.exeを起動
                    subprocess.call(f'wine unit_data/Coneshell_call.exe -cdb unit_data/master.cdb unit_data/master.db'.split())
            return True
        else:
            return CheckMaster.download_from_web(version,hash)
        
    
    @staticmethod
    def download_from_web2(version,hash):
        response=requests.get(f"https://redive.estertion.win/db/redive_jp.db.br")
        if response.ok:
            data=response.content
            decomp=brotli.decompress(data)
            with open("unit_data/master.db",mode="wb") as f:
                f.write(decomp)
            return True
        else:
            return False
    

    @staticmethod
    def download_from_web(version,hash):
        response=requests.get(f"https://wthee.xyz/db/")
        if response.ok:
            search=re.search(r'<a href="redive_jp_hash.db.br">redive_jp_hash.db.br</a>\s+\d+',response.text)
            now=datetime.datetime.now()
            if search and int(search.group()[-2:]) == now.day:
                response2=requests.get(f"https://wthee.xyz/db/redive_jp_hash.db.br")
                data=response2.content
                decomp=brotli.decompress(data)
                with open("unit_data/master.db",mode="wb") as f:
                    f.write(decomp)
                return True
        else:
            return CheckMaster.download_from_web2(version,hash)
        return False

