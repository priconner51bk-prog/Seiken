from io import BytesIO

import discord
import emoji
import matplotlib.pyplot as plt
import pandas as pd

from util.database import db


def create_table(bot, guild_id: int, restype=0):
    # 1の位　本凸
    # 10の位　長い持ち越し
    # 100の位　短い持ち越し
    # 1000の位　フル持ち越し

    # 11 12 13 14 25 長い持ち越し
    # 21 22 23 24 25 短い持ち越し
    # 31 32 33 34 35 フル持ち越し
    value = [[], [], [], [], [], [], [], []]
    afkvalue = [[], [], [], [], [], [], [], []]
    totsu = db.execute(
        f"SELECT id,boss1,boss2,boss3,boss4,boss5,AFK,mochi FROM member_{guild_id}"
    )
    totsu_num = [[int(v) if v != None else 0 for v in m] for m in totsu]
    members = []

    plt.ioff()

    # リストのソート

    # 最も希望が多いボス
    boss_counter = [0, 0, 0, 0, 0]
    for _t in totsu_num:
        for i, val in enumerate(_t[1:6]):
            if val % 100 != 0:
                boss_counter[i] += 1

    boss_sort = sorted(
        [(i, v) for i, v in enumerate(boss_counter)],
        key=lambda x: x[1],
        reverse=True,
    )

    # メンバーのソート
    for _t in totsu_num:
        try:
            name = bot.get_guild(guild_id).get_member(_t[0]).display_name
        except:
            continue
        score = 0
        for i, boss in enumerate(boss_sort):
            if _t[1 + boss[0]] % 100 != 0:
                score += pow(10, 5 - i)
        # memberの各ボスに持ち越しを追加
        for i in range(0, len(str(_t[7])), 2):
            addition = (
                0
                if _t[7] == 0
                else (
                    10
                    if str(_t[7])[i] == "1"
                    else (
                        100
                        if str(_t[7])[i] == "2"
                        else 1000 if str(_t[7])[i] == "3" else 0
                    )
                )
            )
            if addition > 0:
                boss = int(str(_t[7])[i + 1])  # 1~5
                _t[boss] += addition
        members.append(list(_t) + [name, score])

    members.sort(key=lambda x: x[9], reverse=True)

    # listの要素を行列から列行へ変更
    for member in members:
        if member[1:6].count(0) == 5:
            continue

        if member[6] != 0:
            for i, v in enumerate(afkvalue):
                if i <= 7:
                    v.append(member[i + 1])
        else:
            for i, v in enumerate(value):
                if i <= 7:
                    v.append(member[i + 1])

    if len(value[0]) + len(afkvalue[0]) == 0:
        return

    # 凸人数カウント
    for v in value[:6]:
        v.insert(0, str(sum(x % 100 != 0 or int(x / 1000) != 0 for x in v)) + "人")
    value[6].insert(0, "")
    value[7].insert(0, "")

    # 離席中のメンバーリストと結合
    for i in range(len(value)):
        value[i].extend(afkvalue[i])

    # 表示用に変換
    values_str = []
    for col, value_col in enumerate(value):
        str_row = []
        for value_row in value_col:
            if type(value_row) == str or col >= 6:
                str_row.append(value_row)
                continue
            s = ""
            if value_row % 10 != 0:
                s = "〇"
            if int(value_row / 1000) % 10 != 0:
                s += "フ"
            if int(value_row / 10) % 10 != 0:
                s += "長"
            for i in range(int(value_row / 100) % 10):
                s += "短"
            str_row.append(s)
        values_str.append(str_row)

    data = {
        "名前": values_str[7],
        "1ボス": values_str[0],
        "2ボス": values_str[1],
        "3ボス": values_str[2],
        "4ボス": values_str[3],
        "5ボス": values_str[4],
    }
    df = pd.DataFrame(data)
    fig, ax = plt.subplots(figsize=(10, len(value[0]) * 0.8))
    ax.axis("off")
    tb = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        bbox=[0, 0, 1, 1],
        colWidths=[5.5, 1, 1, 1, 1, 1],
        cellLoc="center",
    )
    # 色付け
    for r in range(len(value[0]) - 1):
        for c in range(5):
            if value[5][r + 1] != 1:
                # if (value[c][r+1]%10!=0 or int(value[c][r+1]/1000)%10!=0) and int((value[c][r+1]%1000)/10)!=0:
                if value[c][r + 1] % 10 != 0 and int(value[c][r + 1] / 10) != 0:
                    tb[r + 2, c + 1].set_facecolor("#ABE1FA")
                elif value[c][r + 1] % 10 != 0:
                    tb[r + 2, c + 1].set_facecolor("#B2D235")
                elif value[c][r + 1] % 10000 != 0:
                    tb[r + 2, c + 1].set_facecolor("#ffb6c1")
            else:
                # if (value[c][r+1]%10!=0 or int(value[c][r+1]/1000)%10!=0) and int(value[c][r+1]/10)!=0:
                if value[c][r + 1] % 10 != 0 and int(value[c][r + 1] / 10) != 0:
                    tb[r + 2, c + 1].set_facecolor("#89B0D5")
                elif value[c][r + 1] % 10 != 0:
                    tb[r + 2, c + 1].set_facecolor("#6d793e")
                elif value[c][r + 1] % 10000 != 0:
                    tb[r + 2, c + 1].set_facecolor("#4d363a")
                else:
                    tb[r + 2, c + 1].set_facecolor("#555555")
        if value[5][r + 1] == 1:
            tb[r + 2, 0].set_facecolor("#555555")

    tb.set_fontsize(15)
    buffer = BytesIO()
    extent = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    plt.savefig(buffer, format="png", bbox_inches=extent)
    plt.clf()
    plt.close()
    buffer.seek(0)
    if restype == 0:
        return discord.File(filename="table.png", fp=buffer)
    if restype == 1:
        return buffer


def create_table2(bot, guild_id: int, restype=0):
    value = [[], [], [], [], [], [], [], [], []]
    routes = db.execute(
        f"SELECT id,boss1,boss2,boss3,boss4,boss5,AFK,mochi,route FROM member_{guild_id} WHERE finish IS NULL"
    )
    routes_num = [
        [v if v != None else 0 for v in m]
        for m in routes
        if (m[1:6] == (None, None, None, None, None) and m[7] == None) or m[6] != None
    ]
    members = []

    plt.ioff()

    # メンバーのソート
    for _r in routes_num:
        try:
            name = bot.get_guild(guild_id).get_member(_r[0]).display_name
            rep_name = emoji.replace_emoji(name, replace="")
        except:
            continue
        # memberの各ボスに持ち越しを追加
        for i in range(0, len(str(_r[7])), 2):
            addition = (
                0
                if _r[7] == 0
                else (
                    10 if str(_r[7])[i] == "1" else 100 if str(_r[7])[i] == "2" else 0
                )
            )
            if addition > 0:
                boss = int(str(_r[7])[i + 1])  # 1~5
                _r[boss] += addition
            # 持ち越し含め、凸希望がない場合はrouteに置き換え
            if _r[1:6] == [0, 0, 0, 0, 0]:
                if _r[8] != 0 and isinstance(_r[8], str):
                    route_split = _r[8].split("-")
                    for r_split in route_split:
                        if 1 <= int(r_split) <= 5:
                            _r[int(r_split)] = 1

        members.append(list(_r) + [name, rep_name])

    members.sort(key=lambda x: x[10])

    # listの要素を行列から列行へ変更
    for member in members:
        for i, v in enumerate(value):
            if i <= 8:
                v.append(member[i + 1])

    # 凸人数カウント
    for v in value[:6]:
        v.insert(0, str(sum(x % 100 != 0 for x in v)) + "人")
    value[6].insert(0, "")
    value[7].insert(0, "")
    value[8].insert(0, "")

    # 表示用に変換
    values_str = []
    for col, value_col in enumerate(value):
        str_row = []
        for value_row in value_col:
            if type(value_row) == str or col >= 6:
                str_row.append(value_row)
                continue
            s = ""
            if value_row % 10 != 0:
                s = "〇"
            if int(value_row / 10) % 10 != 0:
                s += "〇"
            for i in range(int(value_row / 100)):
                s += "△"
            str_row.append(s)
        values_str.append(str_row)

    data = {
        "名前": values_str[8],
        "1ボス": values_str[0],
        "2ボス": values_str[1],
        "3ボス": values_str[2],
        "4ボス": values_str[3],
        "5ボス": values_str[4],
    }
    df = pd.DataFrame(data)
    fig, ax = plt.subplots(figsize=(10, len(value[0]) * 0.8))
    ax.axis("off")
    tb = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        bbox=[0, 0, 1, 1],
        colWidths=[5.5, 1, 1, 1, 1, 1],
        cellLoc="center",
    )
    # Tableオブジェクトからセルを取得し、ループで処理
    # ヘッダー行 (インデックス 0) とデータ行 (インデックス 1 から df.shape[0])
    for i in range(df.shape[0] + 1):  # ヘッダー行を含めるため +1
        for j in range(df.shape[1]):  # 列の数だけループ
            cell = tb.get_celld().get((i, j))
            if cell:  # セルが存在すれば背景色を設定
                cell.set_facecolor("#E0FFFF")
                # オプション: ヘッダー行の文字を太字にするなど
                if i == 0:  # ヘッダー行の場合
                    cell.set_text_props(weight="bold", color="black")
                # オプション: 枠線の色や太さを設定したい場合
                # cell.set_edgecolor('gray')
                # cell.set_linewidth(0.5)
    # 色付け
    for r in range(len(value[0]) - 1):
        for c in range(5):
            if value[c][r + 1] % 10 != 0:
                tb[r + 2, c + 1].set_facecolor("#B2D235")
            elif value[c][r + 1] % 1000 != 0:
                tb[r + 2, c + 1].set_facecolor("#ffb6c1")

    tb.set_fontsize(15)
    buffer = BytesIO()
    extent = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    plt.savefig(buffer, format="png", bbox_inches=extent)
    plt.clf()
    plt.close()
    buffer.seek(0)
    if restype == 0:
        return discord.File(filename="table.png", fp=buffer)
    if restype == 1:
        return buffer
