import asyncio
import sqlite3
from typing import Literal
import discord
from discord import app_commands
from discord.ext import commands, tasks
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

import re

from util.database import db
from util.decorators import DpyDecorator
from util.content_generator import Generator
from util.spreadsheetdc import SpreadSheetDC
from util.mochi_helper import MochiTableHelper

from .dc_state import (
    time,
    table_reaction,
    dc_reprint,
    prev_name,
    prev_message,
    prev_mochi,
    finish_members,
)
from .dc_views import (
    DCCompleteView,
    SuspendView,
    DCBossRenameModal,
    DCManageView,
    DCReprintDCMessageView,
    DCReprintView,
)


class DC(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(SuspendView())
        self.bot.add_view(DCReprintDCMessageView())
        self.DC_timer = {}
        self.syudou = discord.PartialEmoji.from_str("<:syu:1525129140867563571> ")

    async def dc_unknown(self, guild_id):
        """不明な凸宣言者"""

        members = db.execute(f"SELECT dc_{guild_id}.id FROM dc_{guild_id} \
                INNER JOIN member_{guild_id} ON dc_{guild_id}.id = member_{guild_id}.id \
                WHERE dc_{guild_id}.boss IS NULL")

        if len(members) > 0:
            content = "不明な凸宣言者"
            for member in members:
                content += (
                    "\n"
                    + self.bot.get_guild(guild_id).get_member(member[0]).display_name
                )

            try:

                dc_message = await self.bot.get_channel(
                    db.read_guild("dc_ch", guild_id)
                ).fetch_message(db.read_guild("unknown_msg", guild_id))
                await dc_message.edit(content=content)

            except:

                send = await self.bot.get_channel(
                    db.read_guild("dc_ch", guild_id)
                ).send(content)
                await send.add_reaction("❌")
                db.write_guild(guild_id, "unknown_msg", send.id)

        # 不明な凸宣言者がいない場合。メッセージを削除する
        else:
            try:
                dc_message = self.bot.get_channel(
                    db.read_guild("dc_ch", guild_id)
                ).get_partial_message(db.read_guild("unknown_msg", guild_id))
                db.delete_guild(guild_id, "unknown_msg")
                await dc_message.delete()
            except:
                pass

    @commands.command()
    async def dc_set(self, ctx: commands.Context, channel: discord.TextChannel = None):

        dc_msg = ""
        name = db.read_guild("dc_name", ctx.guild.id)

        # 名前が決まっていない場合にデフォルトで用意する
        if name == None:
            name = ["1ボス", "2ボス", "3ボス", "4ボス", "5ボス"]
            db.write_guild(ctx.guild.id, "dc_name", "\n".join(name))
        else:
            name = name.split("\n")

        # メッセージを送信するチャンネル
        _channel = channel if channel != None else ctx.channel

        for i in range(5):
            send = await _channel.send(
                f">>> # {name[i]}\n＿＿＿＿＿＿＿＿＿\n\nㅤ",
                view=DCReprintDCMessageView(),
            )
            await send.add_reaction("🔄")
            await send.add_reaction(self.syudou)
            await send.add_reaction("🔼")
            await send.add_reaction("🔻")
            await send.add_reaction("🔥")
            await send.add_reaction("❌")
            await send.add_reaction("✅")
            await send.add_reaction("👉")
            dc_msg += str(send.id) + "\n"

        db.write_guild(ctx.guild.id, "dc_ch", _channel.id)
        db.write_guild(ctx.guild.id, "dc_msg", dc_msg[:-1])
        await ctx.message.delete()

    @app_commands.command(name="dc", description="ダメコンの操作")
    @app_commands.guild_only()
    async def dc_slash(
        self,
        interaction: discord.Interaction,
        mode: Literal[
            "ボス名変更",
            "1ボス操作",
            "2ボス操作",
            "3ボス操作",
            "4ボス操作",
            "5ボス操作",
        ],
    ):
        """ダメコンのスラッシュコマンド"""
        if db.read_guild("dc_ch", interaction.guild_id) == None:
            await interaction.response.send_message(
                "ダメコンのチャンネルが見つかりませんでした", ephemeral=True
            )
            return
        if mode == "ボス名変更":
            names = db.read_guild("dc_name", interaction.guild_id).split("\n")
            await interaction.response.send_modal(DCBossRenameModal(names))
        else:
            boss_num = int(mode[0])
            if (
                len(
                    db.execute(
                        f"SELECT id FROM dc_{interaction.guild_id} WHERE boss = {boss_num}"
                    )
                )
                >= 1
            ):
                await interaction.response.send_message(
                    mode[0],
                    view=DCManageView(interaction.guild, boss_num),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "ダメージは入力されえいません", ephemeral=True
                )

    @commands.Cog.listener("on_message")
    @DpyDecorator.member_check
    async def damage_enter(self, message: discord.Message):
        """ダメージ入力"""
        if (
            message.content != ""
            and message.content[0].isdigit()
            and message.channel.id == db.read_guild("dc_ch", message.guild.id)
        ):
            sengen = db.execute(f"SELECT boss FROM dc_{message.guild.id}\
                        WHERE id = {message.author.id} AND done > 1000")
            try:
                if len(sengen) >= 1:
                    await message.add_reaction(
                        bytes.fromhex(f"3{sengen[0][0]}e283a3").decode("utf-8")
                    )
                    await asyncio.sleep(0.3)
                await message.add_reaction("\u0031\ufe0f\u20e3")
                await asyncio.sleep(0.3)
                await message.add_reaction("\u0032\ufe0f\u20e3")
                await asyncio.sleep(0.3)
                await message.add_reaction("\u0033\ufe0f\u20e3")
                await asyncio.sleep(0.3)
                await message.add_reaction("\u0034\ufe0f\u20e3")
                await asyncio.sleep(0.3)
                await message.add_reaction("\u0035\ufe0f\u20e3")
            except:
                pass
        # 代行
        elif message.content != "" and len(message.mentions) == 1:
            mentionless_content = message.content.replace(
                message.mentions[0].mention, ""
            ).strip()
            if (
                mentionless_content != ""
                and mentionless_content[0].isdigit()
                and message.channel.id == db.read_guild("dc_ch", message.guild.id)
            ):
                try:
                    await message.add_reaction("\u0031\ufe0f\u20e3")
                    await message.add_reaction("\u0032\ufe0f\u20e3")
                    await message.add_reaction("\u0033\ufe0f\u20e3")
                    await message.add_reaction("\u0034\ufe0f\u20e3")
                    await message.add_reaction("\u0035\ufe0f\u20e3")
                except:
                    pass

    @commands.Cog.listener("on_message_edit")
    @DpyDecorator.member_check
    async def edit_damage(self, before: discord.Message, after: discord.Message):
        if (
            after.content != ""
            and after.content[0].isdigit()
            and after.channel.id == db.read_guild("dc_ch", after.guild.id)
        ):
            emojis = [r.emoji for r in after.reactions]
            for emoji in [
                "\u0031\ufe0f\u20e3",
                "\u0032\ufe0f\u20e3",
                "\u0033\ufe0f\u20e3",
                "\u0034\ufe0f\u20e3",
                "\u0035\ufe0f\u20e3",
            ]:
                if emoji not in emojis:
                    await after.add_reaction(emoji)

    @commands.Cog.listener("on_message")
    @DpyDecorator.member_check
    async def reply_dc(self, message: discord.Message):
        try:
            if message.reference != None and str(
                message.reference.message_id
            ) in db.read_guild("dc_msg", message.guild.id).split("\n"):
                boss = (
                    db.read_guild("dc_msg", message.guild.id)
                    .split("\n")
                    .index(str(message.reference.message_id))
                    + 1
                )
                if message.content[0].isdigit():
                    damage = max(
                        map(
                            lambda x: (
                                int(re.match(r"\d+", x).group())
                                if re.match(r"\d+", x)
                                else 0
                            ),
                            message.content.split()[:3],
                        )
                    )
                    conn = sqlite3.connect(db.dbname)
                    cur = conn.cursor()

                    cur.execute(f"""CREATE TABLE IF NOT EXISTS dc_{message.guild.id} (
                        No INTEGER PRIMARY KEY,
                        id INTEGER,
                        boss INTEGER,
                        status TEXT,
                        damage INTEGER,
                        text TEXT,
                        done INTEGER
                        )""")

                    # 凸宣言メッセージを取得し持ち越しか確認
                    try:
                        cur.execute(
                            f"SELECT done FROM dc_{message.guild.id} WHERE id = {message.author.id} AND (boss = {boss} OR boss IS NULL) AND done > 1000"
                        )
                        mochi_id = cur.fetchone()[0]
                        cur.execute(
                            f"SELECT sengen_ch FROM guild WHERE id = {message.guild.id}"
                        )
                        mochi_channel = cur.fetchone()[0]
                        mochi_message = await message.guild.get_channel(
                            mochi_channel
                        ).fetch_message(mochi_id)
                        is_mochi = bool(re.search(r"[餅持]", mochi_message.content))
                    except:
                        is_mochi = False
                    mochi = "🔄" if is_mochi else "🔲"

                    # 凸宣言を削除し、ダメージを登録する
                    cur.execute(
                        f"DELETE FROM dc_{message.guild.id}\
                        WHERE id = {message.author.id} AND (boss = {boss} OR boss IS NULL) AND done > 1000"
                    )

                    cur.execute(f"SELECT No FROM dc_{message.guild.id}\
                        WHERE id = {message.author.id} AND boss = {boss} AND done = 0")

                    # 既に登録されているダメージの情報
                    prev = cur.fetchone()

                    if prev != None and bool(len(prev)):
                        # 上書き
                        cur.execute(
                            f"UPDATE dc_{message.guild.id} SET status = '¦{mochi}¦🔲¦🔲¦',damage = {damage},text = '{message.content}'\
                            WHERE No = {prev[0]}"
                        )
                    else:
                        # 新規
                        cur.execute(
                            f"INSERT INTO dc_{message.guild.id} (No,id,boss,status,damage,text,done)\
                            VALUES ({int(message.created_at.timestamp()*1000)},{message.author.id},{boss},'¦{mochi}¦🔲¦🔲¦',{damage},'{message.content}',0)"
                        )

                    conn.commit()
                    conn.close()

                    self.timer_set(message.guild.id, boss)
                    await message.delete()
                    await DC.dc_unknown(self, message.guild.id)
                else:
                    names = db.read_guild("dc_name", message.guild.id).split("\n")
                    names[boss - 1] = message.content
                    db.write_guild(message.guild.id, "dc_name", "\n".join(names))

                    self.timer_set(message.guild.id, boss)
                    await message.delete()
        except:
            pass

    @commands.Cog.listener("on_message")
    @DpyDecorator.member_check
    async def sengen(self, message: discord.Message):
        """凸宣言"""
        if (
            message.channel.id == db.read_guild("sengen_ch", message.guild.id)
            and db.read_guild("suspend_sengen", message.guild.id) == None
        ):
            if message.content[0] == ".":
                return
            boss = None
            if re.search("[1-5１-５](ボス|ぼす|ﾎﾞｽ|boss)", message.content):
                boss = int(
                    re.search(
                        "[1-5１-５](ボス|ぼす|ﾎﾞｽ|boss)", message.content
                    ).group()[0]
                )
            elif re.search(r"([^\d]|^)\d([^凸\d]|$)", message.content):
                tmp = int(
                    re.search(r"([^\d]|^)\d([^凸\d]|$)", message.content).group()[0]
                )
                boss = tmp if 1 <= tmp <= 5 else None

            db.execute(f"""CREATE TABLE IF NOT EXISTS dc_{message.guild.id} (
                        No INTEGER PRIMARY KEY,
                        id INTEGER,
                        boss INTEGER,
                        status TEXT,
                        damage INTEGER,
                        text TEXT,
                        done INTEGER
                        )""")

            if boss != None:
                db.execute(
                    f"DELETE FROM dc_{message.guild.id} WHERE boss = {boss} AND done > 1000 AND id = {message.author.id}"
                )
                db.execute(
                    f"INSERT INTO dc_{message.guild.id} (No,id,boss,done) SELECT {int(message.created_at.timestamp()*1000)},{message.author.id},{boss},{message.id}"
                )
                self.timer_set(message.guild.id, boss)

            # 不明な凸宣言者にぶち込む
            else:
                db.execute(
                    f"DELETE FROM dc_{message.guild.id} WHERE boss IS NULL AND done > 1000 AND id = {message.author.id}"
                )
                db.execute(
                    f"INSERT INTO dc_{message.guild.id} (No,id,done) SELECT {int(message.created_at.timestamp()*1000)},{message.author.id},{message.id}"
                )
                await DC.dc_unknown(self, message.guild.id)

    @app_commands.command(name="suspend_sengen", description="凸宣言を無効にします")
    @app_commands.guild_only()
    async def suspend_sengen(self, interaction: discord.Interaction):
        try:
            ch = interaction.guild.get_channel(
                db.read_guild("dc_ch", interaction.guild_id)
            )
            send = await ch.send("凸宣言を無効にしました", view=SuspendView())
            db.write_guild(interaction.guild_id, "suspend_sengen", send.id)
            await interaction.response.send_message(
                "凸宣言を無効にしました", ephemeral=True
            )
        except:
            await interaction.response.send_message(
                "ダメコンのチャンネルが見つかりません", ephemeral=True
            )

    @commands.Cog.listener("on_raw_message_delete")
    async def suspend_sengen_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.message_id == db.read_guild("suspend_sengen", payload.guild_id):
            db.delete_guild(payload.guild_id, "suspend_sengen")

    @commands.Cog.listener("on_raw_message_delete")
    async def unknown_delete(self, payload: discord.RawMessageDeleteEvent):
        """不明な凸宣言者のメッセージの削除"""
        if payload.message_id == db.read_guild("unknown_msg", payload.guild_id):
            db.delete_guild(payload.guild_id, "unknown_msg")
            db.execute(
                f"DELETE FROM dc_{payload.guild_id} WHERE boss IS NULL AND done > 1000"
            )

    @commands.Cog.listener("on_raw_reaction_add")
    @DpyDecorator.member_check
    async def damage_reaction(self, payload: discord.RawReactionActionEvent):
        """ダメコンに関するメッセージにリアクションした際の処理"""
        try:
            if payload.emoji.name in [
                "\u0031\ufe0f\u20e3",
                "\u0032\ufe0f\u20e3",
                "\u0033\ufe0f\u20e3",
                "\u0034\ufe0f\u20e3",
                "\u0035\ufe0f\u20e3",
                "1⃣",
                "2⃣",
                "3⃣",
                "4⃣",
                "5⃣",
            ] and payload.channel_id == db.read_guild("dc_ch", payload.guild_id):
                message = await self.bot.get_channel(payload.channel_id).fetch_message(
                    payload.message_id
                )

                if message.content != "" and (
                    message.content[0].isdigit() or len(message.mentions) == 1
                ):
                    content = message.content.replace("＋", "+")
                    content = re.sub(r"(\d+[sSｓＳ秒]?)", r"\1 ", content)

                    spl = content.split()[:3]
                    if len(spl) == 2:
                        spl.append("")
                    if len(spl) == 3:
                        damage1 = 0
                        damage2 = 0
                        damage_plus = 0
                        d_count = 0
                        time = ""
                        another = ""
                        for i in range(3):
                            if spl[i].isdigit():
                                if d_count == 0:
                                    damage1 = int(spl[i])
                                    d_count += 1
                                else:
                                    damage2 = int(spl[i])
                            elif re.match(r"\+\d+$", spl[i]):
                                damage_plus = int(spl[i][1:])
                            elif re.match(r"\d+[sSｓＳ秒]$", spl[i]):
                                time = spl[i]
                            else:
                                another = spl[i]
                        if damage_plus != 0:
                            damage2 = damage1
                            damage1 = damage2 + damage_plus
                        if damage1 < damage2:
                            temp = damage1
                            damage1 = damage2
                            damage2 = temp
                        content = f"{damage1} {time} {damage2} {another}" + "".join(
                            content.split()[3:]
                        )

                    damage = max(
                        map(
                            lambda x: (
                                int(re.match(r"\d+", x).group())
                                if re.match(r"\d+", x)
                                else 0
                            ),
                            content.split()[:3],
                        )
                    )
                    boss = str(payload.emoji.name.encode("utf-8"))[2]
                    author_id = message.author.id
                    author = message.author

                    # 代行
                    if len(message.mentions) == 1:
                        mentionless_content = message.content.replace(
                            message.mentions[0].mention, ""
                        ).strip()
                        content = mentionless_content
                        if not mentionless_content[0].isdigit():
                            return
                        if db.read_member(message.guild.id, "id", author_id) == None:
                            return
                        damage = max(
                            map(
                                lambda x: (
                                    int(re.match(r"\d+", x).group())
                                    if re.match(r"\d+", x)
                                    else 0
                                ),
                                content.split()[:3],
                            )
                        )
                        author_id = message.mentions[0].id
                        author = message.mentions[0]

                    conn = sqlite3.connect(db.dbname)
                    cur = conn.cursor()

                    cur.execute(f"""CREATE TABLE IF NOT EXISTS dc_{payload.guild_id} (
                        No INTEGER PRIMARY KEY,
                        id INTEGER,
                        boss INTEGER,
                        status TEXT,
                        damage INTEGER,
                        text TEXT,
                        done INTEGER
                        )""")

                    # 凸宣言メッセージを取得し持ち越しか確認
                    try:
                        cur.execute(
                            f"SELECT done FROM dc_{message.guild.id} WHERE id = {message.author.id} AND (boss = {boss} OR boss IS NULL) AND done > 1000"
                        )
                        mochi_id = cur.fetchone()[0]
                        cur.execute(
                            f"SELECT sengen_ch FROM guild WHERE id = {message.guild.id}"
                        )
                        mochi_channel = cur.fetchone()[0]
                        mochi_message = await message.guild.get_channel(
                            mochi_channel
                        ).fetch_message(mochi_id)
                        is_mochi = bool(
                            re.search(r"(餅|持|もち)", mochi_message.content)
                        )
                    except:
                        is_mochi = False
                    # 持ち越し蚤の場合
                    if not is_mochi:
                        cur.execute(
                            f"SELECT boss{boss},mochi FROM member_{message.guild.id} WHERE id = {message.author.id}"
                        )
                        check_mochi = cur.fetchone()
                        mochi_list = (
                            [
                                str(check_mochi[1])[i : i + 2]
                                for i in range(0, len(str(check_mochi[1])), 2)
                            ]
                            if check_mochi[1] != None
                            else []
                        )
                        if check_mochi[0] == None and (
                            f"1{boss}" in mochi_list
                            or f"2{boss}" in mochi_list
                            or f"3{boss}" in mochi_list
                        ):
                            is_mochi = True
                    # 更新時持ち越しリアクションがあった場合
                    if not is_mochi:
                        cur.execute(
                            f"SELECT status FROM dc_{message.guild.id} WHERE id = {author_id} AND boss = {boss} AND done = 0"
                        )
                        status = cur.fetchone()
                        if (
                            status != None
                            and status[0] != None
                            and status[0][1] == "🔄"
                        ):
                            is_mochi = True
                    mochi = "🔄" if is_mochi else "🔲"

                    # 凸宣言を削除し、ダメージを登録する
                    cur.execute(
                        f"DELETE FROM dc_{payload.guild_id}\
                        WHERE id = {author_id} AND (boss = {boss} OR boss IS NULL) AND done > 1000"
                    )

                    cur.execute(f"SELECT No,status FROM dc_{payload.guild_id}\
                        WHERE id = {author_id} AND boss = {boss} AND done = 0")

                    # 既に登録されているダメージの情報
                    prev = cur.fetchone()

                    if prev != None and bool(len(prev)):
                        # 上書き
                        cur.execute(
                            f"UPDATE dc_{payload.guild_id} SET status = '¦{mochi}¦🔲¦🔲¦',damage = {damage},text = '{content}'\
                            WHERE No = {prev[0]}"
                        )
                    else:
                        # 新規
                        cur.execute(
                            f"INSERT INTO dc_{payload.guild_id} (No,id,boss,status,damage,text,done)\
                            VALUES ({int(message.created_at.timestamp()*1000)},{author_id},{boss},'¦{mochi}¦🔲¦🔲¦',{damage},'{content}',0)"
                        )

                    conn.commit()
                    conn.close()

                    # リアクションのリセット
                    dc_message = self.bot.get_channel(
                        payload.channel_id
                    ).get_partial_message(
                        db.read_guild("dc_msg", payload.guild_id).split("\n")[
                            int(boss) - 1
                        ]
                    )
                    status = [str(self.syudou), "🔼", "🔻", "🔥"]
                    if prev == None:

                        No = db.execute(
                            f"SELECT No,status FROM dc_{payload.guild_id}\
                            WHERE id = {author_id} AND boss = {boss} AND done = 1 ORDER BY No DESC"
                        )
                        if len(No) > 0:
                            for s in status:
                                if s in No[0][1]:
                                    await dc_message.remove_reaction(s, author)
                            if not is_mochi:
                                await dc_message.remove_reaction("🔄", author)
                            await dc_message.remove_reaction("✅", author)
                    else:
                        for s in status:
                            if s in prev[1]:
                                await dc_message.remove_reaction(s, author)
                        if not is_mochi:
                            await dc_message.remove_reaction("🔄", author)

                    self.timer_set(payload.guild_id, boss)
                    await message.delete()
                    await DC.dc_unknown(self, payload.guild_id)

            elif str(payload.message_id) in db.read_guild("dc_msg", payload.guild_id):

                updated = False
                boss = (
                    db.read_guild("dc_msg", payload.guild_id)
                    .split("\n")
                    .index(str(payload.message_id))
                    + 1
                )

                status = db.execute(f"SELECT No,status FROM dc_{payload.guild_id}\
                    WHERE id = {payload.user_id} AND boss = {boss} AND done = 0")

                if bool(len(status)):
                    status = status[0]
                    match payload.emoji.name:
                        case "🔄":
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '¦🔄{status[1][2:]}' WHERE No = {status[0]}"
                            )
                            updated = True
                        case self.syudou.name:
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:3]}{self.syudou}{status[1][-3:]}' WHERE No = {status[0]}"
                            )
                            updated = True
                        case "🔼":
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔼¦' WHERE No = {status[0]}"
                            )
                            updated = True
                        case "🔻":
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔻¦' WHERE No = {status[0]}"
                            )
                            updated = True
                        case "🔥":
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔥¦' WHERE No = {status[0]}"
                            )
                            updated = True
                        case "✅":
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET done = 1 WHERE No = {status[0]}"
                            )
                            updated = True

                if payload.emoji.name == "❌":
                    db.execute(f"DELETE FROM dc_{payload.guild_id}\
                        WHERE id = {payload.user_id} AND boss = {boss} AND done != 1")
                    await self.bot.get_channel(payload.channel_id).get_partial_message(
                        payload.message_id
                    ).remove_reaction("❌", payload.member)
                    updated = True

                elif payload.emoji.name == "👉":
                    members = db.execute(
                        f"SELECT * FROM dc_{payload.guild_id} WHERE boss = {boss}"
                    )
                    db.execute(f"DELETE FROM dc_{payload.guild_id} WHERE boss = {boss}")

                    message = self.bot.get_channel(
                        payload.channel_id
                    ).get_partial_message(payload.message_id)
                    fetch_message = await message.fetch()
                    fetch_content = fetch_message.content
                    guild = self.bot.get_guild(payload.guild_id)
                    content = Generator.dc_content(guild, boss)
                    await fetch_message.edit(content=content)

                    await message.clear_reactions()
                    await message.add_reaction("🔄")
                    await message.add_reaction(self.syudou)
                    await message.add_reaction("🔼")
                    await message.add_reaction("🔻")
                    await message.add_reaction("🔥")
                    await message.add_reaction("❌")
                    await message.add_reaction("✅")
                    await message.add_reaction("👉")
                    log = None
                    if db.read_guild("log_ch", payload.guild_id) != None:
                        log = await self.bot.get_channel(
                            db.read_guild("log_ch", payload.guild_id)
                        ).send(fetch_content)
                    r_message = self.bot.get_channel(
                        payload.channel_id
                    ).get_partial_message(payload.message_id)
                    prev_stat = {
                        "dc_reprint": None,
                        "table_reaction": [],
                        "prev_mochi": [],
                    }
                    global dc_reprint
                    if (
                        message.guild.id in dc_reprint
                        and dc_reprint[message.guild.id][boss - 1] != None
                    ):
                        global table_reaction
                        if message.guild.id in table_reaction:
                            prev_stat["table_reaction"] = table_reaction[
                                message.guild.id
                            ][boss - 1]
                            table_reaction[message.guild.id][boss - 1] = []
                        prev_stat["dc_reprint"] = dc_reprint[message.guild.id][boss - 1]
                        dc_reprint[message.guild.id][boss - 1] = None
                    global prev_mochi
                    if guild.id in prev_mochi:
                        prev_stat["prev_mochi"] = prev_mochi[guild.id][boss - 1]
                        prev_mochi[guild.id][boss - 1] = []
                    prev_stat["prev_message"] = prev_message.delete_boss(
                        message.guild.id, boss
                    )
                    prev_stat["prev_name"] = prev_name.delete(guild.id, boss)

                    await self.bot.get_channel(payload.channel_id).send(
                        "討伐されました",
                        view=DCCompleteView(
                            members, log, fetch_content, boss, prev_stat
                        ),
                        delete_after=60,
                        reference=r_message,
                    )
                    SpreadSheetDC.write(guild, boss)

                elif payload.emoji.name == "🚮":
                    members = db.execute(
                        f"SELECT * FROM dc_{payload.guild_id} WHERE boss = {boss}"
                    )
                    db.execute(f"DELETE FROM dc_{payload.guild_id} WHERE boss = {boss}")

                    message = self.bot.get_channel(
                        payload.channel_id
                    ).get_partial_message(payload.message_id)
                    guild = self.bot.get_guild(payload.guild_id)
                    content = Generator.dc_content(guild, boss)
                    await message.edit(content=content)
                    await message.clear_reactions()
                    await message.add_reaction("🔄")
                    await message.add_reaction(self.syudou)
                    await message.add_reaction("🔼")
                    await message.add_reaction("🔻")
                    await message.add_reaction("🔥")
                    await message.add_reaction("❌")
                    await message.add_reaction("✅")
                    await message.add_reaction("👉")
                # メッセージ内容更新の確認
                if updated:
                    self.timer_set(payload.guild_id, boss)

            # 不明な凸宣言者の取り消し
            elif payload.emoji.name == "❌" and payload.message_id == db.read_guild(
                "unknown_msg", payload.guild_id
            ):
                db.execute(
                    f"DELETE FROM dc_{payload.guild_id} WHERE id = {payload.user_id} AND boss IS NULL AND done > 1000"
                )
                await self.bot.get_channel(payload.channel_id).get_partial_message(
                    payload.message_id
                ).remove_reaction("❌", payload.member)
                await DC.dc_unknown(self, payload.guild_id)
        except:
            pass

    @commands.Cog.listener("on_raw_reaction_remove")
    @DpyDecorator.member_check
    async def damage_remove_reaction(self, payload: discord.RawReactionActionEvent):
        """ダメコンのリアクション取り消し"""
        try:
            if str(payload.message_id) in db.read_guild("dc_msg", payload.guild_id):
                updated = False
                boss = (
                    db.read_guild("dc_msg", payload.guild_id)
                    .split("\n")
                    .index(str(payload.message_id))
                    + 1
                )

                status = db.execute(f"SELECT No,status FROM dc_{payload.guild_id}\
                    WHERE id = {payload.user_id} AND boss = {boss} AND done = 0")

                if bool(len(status)) and payload.emoji.name in status[0][1]:
                    status = status[0]
                    match payload.emoji.name:
                        case "🔄":
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '¦🔲{status[1][2:]}' WHERE No = {status[0]}"
                            )
                            updated = True
                        case self.syudou.name:
                            status_rep = str(status[1]).replace(str(self.syudou), "🔲")
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '{status_rep}' WHERE No = {status[0]}"
                            )
                            updated = True
                        case "🔼":
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔲¦' WHERE No = {status[0]}"
                            )
                            updated = True
                        case "🔻":
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔲¦' WHERE No = {status[0]}"
                            )
                            updated = True
                        case "🔥":
                            db.execute(
                                f"UPDATE dc_{payload.guild_id} SET status = '{status[1][:-2]}🔲¦' WHERE No = {status[0]}"
                            )
                            updated = True

                elif payload.emoji.name == "✅":
                    now = db.execute(
                        f"SELECT No FROM dc_{payload.guild_id} WHERE id = {payload.user_id} AND boss = {boss} AND done = 0"
                    )
                    No = db.execute(
                        f"SELECT No FROM dc_{payload.guild_id}\
                        WHERE id = {payload.user_id} AND boss = {boss} AND done = 1 ORDER BY No DESC"
                    )
                    if len(No) > 0 and len(now) == 0:
                        db.execute(
                            f"UPDATE dc_{payload.guild_id} SET done = 0 WHERE No = {No[0][0]}"
                        )
                        updated = True

                if updated:
                    self.timer_set(payload.guild_id, boss)
        except:
            pass

    @commands.Cog.listener("on_member_update")
    @DpyDecorator.member_check
    async def change_name(self, before: discord.Member, after: discord.Member):
        if before.display_name != after.display_name:
            await asyncio.sleep(2)  # データベースが更新されるまで待つ
            boss = set(
                [
                    x
                    for row in db.execute(
                        f"SELECT boss FROM dc_{before.guild.id} WHERE id = {before.id}"
                    )
                    for x in row
                ]
            )
            for b in boss:
                if b == None:
                    await DC.dc_unknown(self, before.guild.id)
                else:
                    try:
                        self.timer_set(before.guild.id, b, True)
                    except:
                        pass

    def timer_set(self, guild_id, boss, rename=False):
        if isinstance(boss, str):
            boss = int(boss)
        if str(guild_id) not in self.DC_timer:
            self.DC_timer[str(guild_id)] = [{}, {}, {}, {}, {}]
        if self.DC_timer[str(guild_id)][boss - 1] == {}:
            self.DC_timer[str(guild_id)][boss - 1]["next"] = datetime.now()
            self.DC_timer[str(guild_id)][boss - 1]["updated"] = True
        asyncio.create_task(self.timer_start(guild_id, boss, rename))

    async def timer_start(self, guild_id, boss, rename):
        nexttime: datetime = self.DC_timer[str(guild_id)][boss - 1]["next"]
        now = datetime.now()
        if (
            not self.DC_timer[str(guild_id)][boss - 1]["updated"]
            and (now - nexttime).total_seconds() >= 10
        ):
            self.DC_timer[str(guild_id)][boss - 1]["updated"] = True
        if not self.DC_timer[str(guild_id)][boss - 1]["updated"]:
            return
        self.DC_timer[str(guild_id)][boss - 1]["updated"] = False
        if nexttime > now:
            await asyncio.sleep(
                (nexttime - now).seconds + (nexttime - now).microseconds / 1000000
            )
        if self.DC_timer[str(guild_id)][boss - 1]["updated"] == False:

            try:
                guild = self.bot.get_guild(guild_id)
                content = Generator.dc_content(guild, boss)
                dc_message = self.bot.get_channel(
                    db.read_guild("dc_ch", guild_id)
                ).get_partial_message(
                    db.read_guild("dc_msg", guild_id).split("\n")[boss - 1]
                )
                await dc_message.edit(content=content)
                # スプシ処理
                SpreadSheetDC.write(guild, boss)
            except discord.HTTPException as e:
                h = e.response.headers
                print(h)

            self.DC_timer[str(guild_id)][boss - 1]["next"] = datetime.now() + timedelta(
                seconds=5
            )
            self.DC_timer[str(guild_id)][boss - 1]["updated"] = True

            try:
                # 転載の処理
                # 削除送信をする
                global dc_reprint
                if (
                    not rename
                    and int(guild_id) in dc_reprint
                    and dc_reprint[int(guild_id)][boss - 1] != None
                ):
                    send_message = await dc_reprint[int(guild_id)][
                        boss - 1
                    ].channel.send(
                        content=content, silent=True, view=DCReprintView(boss)
                    )
                    await dc_reprint[int(guild_id)][boss - 1].delete()
                    dc_reprint[int(guild_id)][boss - 1] = send_message
            except:
                pass

    async def cog_load(self):
        asyncio.create_task(self.load_message_reaction())
        self.daily_totsu.start()
        MochiTableHelper.load()

    def cog_unload(self):
        self.daily_totsu.cancel()

    async def load_message_reaction(self):
        await asyncio.sleep(10)
        channel_ids = db.read_guild("dc_ch")
        for guild_channel_id in channel_ids:
            try:
                channel = self.bot.get_channel(guild_channel_id[1])
                async for message in channel.history(limit=30):
                    if (
                        message.author.id != self.bot.user.id
                        and len(message.reactions) == 0
                        and message.content != ""
                        and message.content[0].isdigit()
                    ):
                        for emoji in [
                            "\u0031\ufe0f\u20e3",
                            "\u0032\ufe0f\u20e3",
                            "\u0033\ufe0f\u20e3",
                            "\u0034\ufe0f\u20e3",
                            "\u0035\ufe0f\u20e3",
                        ]:
                            await message.add_reaction(emoji)
            except:
                pass

    @tasks.loop(time=time)
    async def daily_totsu(self):
        guilds = db.read_guild("id")
        for guild in guilds:
            try:
                isupdate = [False, False, False, False, False]
                delete_num = []
                rows = db.execute(f"SELECT * FROM dc_{guild[0]}")
                for values in rows:
                    if values[2] == None:
                        delete_num.append(values[0])
                    elif values[6] == 0:
                        db.execute(
                            f"UPDATE dc_{guild[0]} SET done = 1 WHERE No = {values[0]}"
                        )
                        isupdate[values[2] - 1] = True
                    elif values[6] > 1000:
                        delete_num.append(values[0])
                        isupdate[values[2] - 1] = True
                if len(delete_num) > 0:
                    _sql = f"DELETE FROM dc_{guild[0]} WHERE " + " OR ".join(
                        map(lambda x: f"No = {x}", delete_num)
                    )
                    db.execute(_sql)
                await self.dc_unknown(guild[0])
                for i, _isupdate in enumerate(isupdate):
                    if _isupdate:
                        self.timer_set(guild[0], i + 1)
            except:
                pass
        today = datetime.today()
        next_day = today + timedelta(days=6)
        if next_day.day == 1:
            for guild_id in guilds:
                try:
                    guild = self.bot.get_guild(guild_id[0])
                    ch = guild.get_channel(db.read_guild("dc_ch", guild.id))
                    send = await ch.send("凸宣言を無効にしました", view=SuspendView())
                    db.write_guild(guild.id, "suspend_sengen", send.id)
                except:
                    pass
        MochiTableHelper.remove()

    @commands.Cog.listener("on_message_delete")
    async def delete_mention_message(self, message: discord.Message):
        def find(no, boss):
            global prev_mochi
            if not message.guild.id in prev_mochi:
                return -1
            for i, m in enumerate(prev_mochi[message.guild.id][boss - 1]):
                if m[0] == no:
                    return prev_mochi[message.guild.id][boss - 1].pop(i)[1]
            return -1

        members_list = []
        if message.guild != None and prev_message.find(message.guild.id, message.id):
            boss = prev_message.message_list[message.guild.id][message.id][0]
            for No in prev_message.message_list[message.guild.id][message.id][1]:
                db.execute(f"UPDATE dc_{message.guild.id} SET done = 0 WHERE No = {No}")
                member_id = db.execute(
                    f"SELECT id FROM dc_{message.guild.id} WHERE No = {No}"
                )[0][0]
                prev = find(No, boss)
                if prev != -1:
                    if prev != None and prev > 0:
                        db.write_member(message.guild.id, member_id, "mochi", prev)
                    else:
                        db.delete_member(message.guild.id, member_id, "mochi")
                    MochiTableHelper.undo(message.guild, member_id)
                members_list.append((No, member_id))
                global finish_members
                if (
                    message.guild.id in finish_members
                    and member_id in finish_members[message.guild.id][boss - 1]
                ):
                    finish_members[message.guild.id][boss - 1].remove(member_id)
            content = Generator.dc_content(message.guild, boss)
            dc_message = message.guild.get_channel(
                db.read_guild("dc_ch", message.guild.id)
            ).get_partial_message(
                db.read_guild("dc_msg", message.guild.id).split("\n")[boss - 1]
            )
            await dc_message.edit(content=content)
            await dc_reprint[message.guild.id][boss - 1].edit(content=content)
            await DC.table_change(message.guild, boss, members_list, False)
            prev_message.delete(message.guild.id, message.id)
            mentions = "\n".join([f"<@{m[1]}>" for m in members_list])
            await message.channel.send(f"キャンセル\n{mentions}")
            # 名前の変更
            global prev_name
            for member in members_list:
                prev = prev_name.get(message.guild.id, member[1])
                if prev != None:
                    try:
                        m = message.guild.get_member(member[1])
                        await m.edit(nick=prev)
                    except:
                        pass

            SpreadSheetDC.write(message.guild, boss)

    # テーブルの自動更新
    # リアクションを消すのみで対応
    # ただし、リアクションをつけることはできないので後で考える？
    @staticmethod
    async def table_change(guild: discord.Guild, boss, members: list, finish: bool):
        global table_reaction
        if not guild.id in table_reaction:
            table_reaction[guild.id] = [[], [], [], [], []]
        message = guild.get_channel(
            db.read_guild("reaction_ch", guild.id)
        ).get_partial_message(db.read_guild("reaction_msg", guild.id))
        if finish:
            for member in members:
                try:
                    # 通し前の突希望を記録
                    table_reaction_db = db.read_member(
                        guild.id, f"boss{boss}", member[1]
                    )
                    table_reaction[guild.id][boss - 1].append(
                        (member[0], table_reaction_db)
                    )

                    db.delete_member(guild.id, member[1], f"boss{boss}")
                    member = guild.get_member(member[1])
                    match boss:
                        case 1:
                            await message.remove_reaction("1⃣", member)
                        case 2:
                            await message.remove_reaction("2⃣", member)
                        case 3:
                            await message.remove_reaction("3⃣", member)
                        case 4:
                            await message.remove_reaction("4⃣", member)
                        case 5:
                            await message.remove_reaction("5⃣", member)
                except:
                    continue
        else:
            for member in members:
                length = len(table_reaction[guild.id][boss - 1])
                for i, v in enumerate(reversed(table_reaction[guild.id][boss - 1])):
                    if v[0] == member[0]:
                        if v[1] != None:
                            db.write_member(guild.id, member[1], f"boss{boss}", v[1])
                        del table_reaction[guild.id][boss - 1][length - (i + 1)]
                        break
        await message.add_reaction("〰")

    @staticmethod
    async def zan_update(member_id, guild: discord.Guild, zan_u, mochi_u):
        member = guild.get_member(member_id)
        p_name = member.display_name
        zan = zan_u
        mochi = mochi_u
        try:
            search = re.search(r"残\d餅\d", member.display_name)
            if search:
                s = search.group()
                zan = min(3, max(0, int(s[1]) + zan_u))
                mochi = min(3, max(0, int(s[3]) + mochi_u))
                s_replace = f"残{zan}餅{mochi}"
                if s != s_replace:
                    rep = re.sub(s, s_replace, member.display_name)
                    await member.edit(nick=rep)
                else:
                    p_name = None
            else:
                p_name = None
        except:
            pass
        return zan == 0 and mochi == 0

    @commands.command()
    async def mochi(self, ctx: commands.Context):
        await MochiTableHelper.send(ctx.channel)
        await ctx.message.delete()


async def setup(bot: commands.Bot):
    await bot.add_cog(DC(bot))
