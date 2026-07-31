import asyncio
import math
from datetime import datetime

import discord

from util.database import db
from util.content_generator import Generator
from util.spreadsheetdc import SpreadSheetDC
from util.mochi_helper import MochiTableHelper

from .dc_state import (
    table_reaction,
    dc_reprint,
    prev_name,
    prev_message,
    prev_mochi,
    finish_members,
)


class DCCompleteView(discord.ui.View):
    """討伐を押した際に出すボタン"""

    def __init__(
        self, members, log: discord.Message, content: str, boss: int, prev_stat: dict
    ):
        super().__init__(timeout=120)
        self.members = members
        self.log = log
        self.content = content
        self.boss = boss
        self.prev_stat = prev_stat
        self.isreturn = False

    async def interaction_check(self, interaction):
        if self.isreturn:
            return False
        self.isreturn = True
        return True

    @discord.ui.button(label="戻す", style=discord.ButtonStyle.primary)
    async def return_button(self, interaction: discord.Interaction, button):
        try:
            for member in self.members:
                values = ",".join([f"'{v}'" if v != None else "NULL" for v in member])
                db.execute(f"INSERT INTO dc_{interaction.guild_id} \
                    (No,id,boss,status,damage,text,done) \
                    VALUES ({values})")
            content = self.content
            await interaction.channel.get_partial_message(
                interaction.message.reference.message_id
            ).edit(content=content)
            if self.log != None:
                await self.log.delete()
            global dc_reprint
            dc_reprint[interaction.guild_id][self.boss - 1] = self.prev_stat[
                "dc_reprint"
            ]
            global table_reaction
            table_reaction[interaction.guild_id][self.boss - 1] = self.prev_stat[
                "table_reaction"
            ]
            global prev_mochi
            prev_mochi[interaction.guild_id][self.boss - 1] = self.prev_stat[
                "prev_mochi"
            ]
            global prev_message
            prev_message.return_button(
                interaction.guild_id, self.boss, self.prev_stat["prev_message"]
            )
            global prev_name
            prev_name.return_button(interaction.guild_id, self.prev_stat["prev_name"])
        except:
            pass
        await interaction.response.send_message(
            "戻しました", ephemeral=True, delete_after=15
        )
        await interaction.message.delete()


class SuspendView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="有効化",
        style=discord.ButtonStyle.primary,
        custom_id="resume_sengen_button",
    )
    async def resume_sengen_button(self, interaction: discord.Interaction, button):
        db.delete_guild(interaction.guild_id, "suspend_sengen")
        await interaction.message.delete()


class DCBossRenameModal(discord.ui.Modal, title="ボス名変更"):
    b1 = discord.ui.TextInput(label="1ボス")
    b2 = discord.ui.TextInput(label="2ボス")
    b3 = discord.ui.TextInput(label="3ボス")
    b4 = discord.ui.TextInput(label="4ボス")
    b5 = discord.ui.TextInput(label="5ボス")

    def __init__(self, names):
        self.names = names
        self.b1.default = names[0]
        self.b2.default = names[1]
        self.b3.default = names[2]
        self.b4.default = names[3]
        self.b5.default = names[4]
        super().__init__(timeout=240, custom_id="dc_modal")

    async def on_submit(self, interaction: discord.Interaction):
        res = ""
        changed = self.names
        boss = [self.b1, self.b2, self.b3, self.b4, self.b5]
        changenum = []
        for i in range(5):
            if boss[i].value != self.names[i]:
                res += f"{self.names[i]}　→　{boss[i].value}\n"
                changed[i] = boss[i].value
                changenum.append(i)
        if res == "":
            await interaction.response.send_message(
                content="名前の変更はありません", view=None, ephemeral=True
            )
        else:
            db.write_guild(interaction.guild_id, "dc_name", "\n".join(changed))
            for i in changenum:
                content = Generator.dc_content(interaction.guild, i + 1)
                message = interaction.guild.get_channel(
                    db.read_guild("dc_ch", interaction.guild_id)
                ).get_partial_message(
                    int(db.read_guild("dc_msg", interaction.guild_id).split("\n")[i])
                )
                await message.edit(content=content)
            await interaction.response.send_message(
                content=res, view=None, ephemeral=True
            )


class DCManageView(discord.ui.View):
    def __init__(self, guild, boss_num):
        super().__init__(timeout=240)
        self.add_item(DCManageSelect(guild, boss_num))


class DCManageSelect(discord.ui.Select):
    def __init__(self, guild: discord.Guild, boss_num):
        self.boss_num = boss_num
        guild_id = guild.id
        self.members = db.execute(
            f"SELECT dc_{guild_id}.*,member_{guild_id}.taskkill FROM dc_{guild_id} \
                INNER JOIN member_{guild_id} ON dc_{guild_id}.id = member_{guild_id}.id \
                WHERE dc_{guild_id}.boss = {boss_num} "
        )
        self.members.sort(key=lambda x: x[4] if x[4] != None else -1, reverse=True)
        options = []
        if len(self.members) >= 1:
            for i, m in enumerate(self.members):
                stat = f"{guild.get_member(m[1]).display_name}{m[3]} {m[5]}"
                if m[3] == None:
                    stat = f"{guild.get_member(m[1]).display_name} 凸宣言"
                emj = "⬜" if m[6] == 0 or m[6] == -1 else "✅"
                options.append(
                    discord.SelectOption(label=stat, value=str(i), emoji=emj)
                )
        super().__init__(options=options[:20], max_values=1)

    async def callback(self, interaction: discord.Interaction):
        stat = f"{interaction.guild.get_member(self.members[int(self.values[0])][1]).display_name}{self.members[int(self.values[0])][3]} {self.members[int(self.values[0])][5]}"
        if self.members[int(self.values[0])][3] == None:
            stat = f"{interaction.guild.get_member(self.members[int(self.values[0])][1]).display_name} 凸宣言"
        emj = (
            "⬜"
            if self.members[int(self.values[0])][6] == 0
            or self.members[int(self.values[0])][6] == -1
            else "✅"
        )
        await interaction.response.edit_message(
            content=f"{emj} {stat}",
            view=DCMemberView(self.boss_num, self.members[int(self.values[0])]),
        )


class DCMemberView(discord.ui.View):
    def __init__(self, boss_num, db_member):
        super().__init__(timeout=240)
        self.db_member = list(db_member)
        self.boss_num = boss_num

    @discord.ui.button(label="✅⇔⬜", style=discord.ButtonStyle.blurple)
    async def check_button(self, interaction: discord.Interaction, button):
        if self.db_member[6] != -1:
            if self.db_member[6] == 0:
                db.execute(
                    f"UPDATE dc_{interaction.guild_id} SET done = 1 WHERE No = {self.db_member[0]}"
                )
                self.db_member[6] = 1
            else:
                db.execute(
                    f"UPDATE dc_{interaction.guild_id} SET done = 0 WHERE No = {self.db_member[0]}"
                )
                self.db_member[6] = 0

            stat = f"{interaction.guild.get_member(self.db_member[1]).display_name}{self.db_member[3]} {self.db_member[5]}"
            if self.db_member[3] == None:
                stat = f"{interaction.guild.get_member(self.db_member[1]).display_name} 凸宣言"
            emj = "⬜" if self.db_member[6] == 0 or self.db_member[6] == -1 else "✅"

            message = interaction.guild.get_channel(
                db.read_guild("dc_ch", interaction.guild_id)
            ).get_partial_message(
                db.read_guild("dc_msg", interaction.guild_id).split("\n")[
                    self.boss_num - 1
                ]
            )
            await message.edit(
                content=Generator.dc_content(interaction.guild, self.boss_num)
            )
            await interaction.response.edit_message(content=f"{emj} {stat}")
        else:
            await interaction.response.edit_message(
                content="凸宣言メッセージは変更できません"
            )

    @discord.ui.button(label="取り消し", style=discord.ButtonStyle.red)
    async def delete_button(self, interaction: discord.Interaction, button):
        db.execute(
            f"DELETE FROM dc_{interaction.guild_id} WHERE No = {self.db_member[0]}"
        )
        message = interaction.guild.get_channel(
            db.read_guild("dc_ch", interaction.guild_id)
        ).get_partial_message(
            db.read_guild("dc_msg", interaction.guild_id).split("\n")[self.boss_num - 1]
        )
        await message.edit(
            content=Generator.dc_content(interaction.guild, self.boss_num)
        )
        await interaction.response.edit_message(content="取り消しました", view=None)


class DCReprintDCMessageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction):
        roles = [
            interaction.guild.get_role(808240600691900417),
            interaction.guild.get_role(1292855894454964336),
            interaction.guild.get_role(1335210159735177297),
        ]
        if set(roles) & set(interaction.user.roles):
            return True
        return False

    async def on_error(self, interaction: discord.Interaction, error, item):
        await interaction.response.send_message("転送に失敗しました", ephemeral=True)

    @discord.ui.button(
        label="メイン転送", style=discord.ButtonStyle.gray, custom_id="main_reprint"
    )
    async def main_button(self, interaction: discord.Interaction, button):
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1293579100056846409)
        else:
            channel = interaction.guild.get_channel(1524979826761535498)
        dc_messages = db.read_guild("dc_msg", interaction.guild_id).split("\n")
        boss_num = dc_messages.index(str(interaction.message.id)) + 1
        await interaction.response.send_message(
            content=f"{channel.mention}に転送しますか",
            ephemeral=True,
            view=DCReprintDCMessageConfirmView(channel, boss_num),
        )

    @discord.ui.button(
        label="サブ転送", style=discord.ButtonStyle.gray, custom_id="sub_reprint"
    )
    async def sub_button(self, interaction: discord.Interaction, button):
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1335059739410698344)
        else:
            channel = interaction.guild.get_channel(864795442742427648)
        dc_messages = db.read_guild("dc_msg", interaction.guild_id).split("\n")
        boss_num = dc_messages.index(str(interaction.message.id)) + 1
        await interaction.response.send_message(
            content=f"{channel.mention}に転送しますか",
            ephemeral=True,
            view=DCReprintDCMessageConfirmView(channel, boss_num),
        )

    @discord.ui.button(
        label="単騎転送", style=discord.ButtonStyle.gray, custom_id="t_reprint"
    )
    async def t_button(self, interaction: discord.Interaction, button):
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1293579743681319023)
        else:
            channel = interaction.guild.get_channel(1524979951928086539)
        dc_messages = db.read_guild("dc_msg", interaction.guild_id).split("\n")
        boss_num = dc_messages.index(str(interaction.message.id)) + 1
        await interaction.response.send_message(
            content=f"{channel.mention}に転送しますか",
            ephemeral=True,
            view=DCReprintDCMessageConfirmView(channel, boss_num),
        )


reprinttimer = [
    datetime.now(),
    datetime.now(),
    datetime.now(),
    datetime.now(),
    datetime.now(),
]


class DCReprintDCMessageConfirmView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel, boss_num):
        super().__init__(timeout=60)
        self.channel = channel
        self.boss_num = boss_num

    @discord.ui.button(label="OK", style=discord.ButtonStyle.green)
    async def OK_button(self, interaction: discord.Interaction, button):
        global reprinttimer
        waittime = (datetime.now() - reprinttimer[self.boss_num - 1]).total_seconds()
        if waittime < 10:
            await interaction.response.edit_message(
                content=f"{int(10-waittime)}秒後に再度試してください"
            )
            return
        await interaction.response.edit_message(content="")
        global dc_reprint
        content = Generator.dc_content(interaction.guild, self.boss_num)
        send_message = await self.channel.send(
            content=content, view=DCReprintView(self.boss_num), silent=True
        )
        if not interaction.guild_id in dc_reprint:
            dc_reprint[interaction.guild_id] = [None, None, None, None, None]
        dc_reprint[interaction.guild_id][self.boss_num - 1] = send_message
        await interaction.delete_original_response()
        reprinttimer[self.boss_num - 1] = datetime.now()

    @discord.ui.button(label="取り消し", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="")
        await interaction.delete_original_response()


class DCReprintView(discord.ui.View):
    def __init__(self, boss_num):
        super().__init__(timeout=None)
        self.boss_num = boss_num

    async def interaction_check(self, interaction: discord.Interaction):
        roles = [
            interaction.guild.get_role(808240600691900417),
            interaction.guild.get_role(1292855894454964336),
            interaction.guild.get_role(1335210159735177297),
        ]
        if set(roles) & set(interaction.user.roles):
            return True
        return False

    @discord.ui.button(label="通し指示", style=discord.ButtonStyle.blurple)
    async def through_button(self, interaction: discord.Interaction, button):
        members = db.execute(
            f"SELECT No,id FROM dc_{interaction.guild.id} WHERE boss = {self.boss_num} AND done = 0"
        )
        if len(members) > 0:
            await interaction.response.send_message(
                "通すメンバーを選択",
                view=DCReprintMembersView(
                    self.boss_num, interaction.guild, False, interaction.message
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "メンバーがいません", ephemeral=True
            )

    @discord.ui.button(label="〆指示", style=discord.ButtonStyle.blurple)
    async def finish_button(self, interaction: discord.Interaction, button):
        members = db.execute(
            f"SELECT No,id FROM dc_{interaction.guild.id} WHERE boss = {self.boss_num} AND done = 0"
        )
        if len(members) > 0:
            await interaction.response.send_message(
                "通すメンバーを選択",
                view=DCReprintMembersView(
                    self.boss_num, interaction.guild, True, interaction.message
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "メンバーがいません", ephemeral=True
            )

    @discord.ui.button(label="指示キャンセル", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button):
        members = db.execute(
            f"SELECT No,id FROM dc_{interaction.guild.id} WHERE boss = {self.boss_num} AND done = 1"
        )
        if len(members) > 0:
            await interaction.response.send_message(
                "キャンセルするメンバーを選択",
                view=DCReprintCancelMembersView(
                    self.boss_num, interaction.guild, interaction.message
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "メンバーがいません", ephemeral=True
            )

    @discord.ui.button(label="連携終了", style=discord.ButtonStyle.gray)
    async def kaihou_button(self, interaction: discord.Interaction, button):
        await interaction.response.send_message(
            "連携を終了しますか？",
            view=KaihouConfirmView(self.boss_num),
            ephemeral=True,
        )

    @discord.ui.button(row=2, label="ダメージリスト", style=discord.ButtonStyle.green)
    async def damagelist_button(self, interaction: discord.Interaction, button):
        await interaction.response.send_message(
            "", view=DamageListView(interaction.guild, self.boss_num), ephemeral=True
        )


class DCReprintMembersView(discord.ui.View):
    def __init__(self, boss_num, guild, last_attack, original_message):
        super().__init__(timeout=240)
        self.add_item(
            DCReprintMembersSelect(boss_num, guild, last_attack, original_message)
        )


class DCReprintMembersSelect(discord.ui.Select):
    def __init__(self, boss_num, guild: discord.Guild, last_attack, original_message):
        self.boss_num = boss_num
        self.guild = guild
        self.last_attack = last_attack
        self.original_message = original_message
        self.members = db.execute(
            f"SELECT No,id,status,damage FROM dc_{guild.id} WHERE boss = {self.boss_num} AND done = 0 ORDER BY damage DESC"
        )
        self.names = [guild.get_member(v[1]).display_name for v in self.members]
        options = []
        if len(self.members) >= 1:
            for i, m in enumerate(self.members):
                options.append(
                    discord.SelectOption(
                        label=f"{self.names[i]}　{m[2]}　{m[3]}", value=str(i)
                    )
                )
        max_values = 1 if last_attack else 20
        super().__init__(options=options[:20], max_values=min(max_values, len(options)))

    async def callback(self, interaction: discord.Interaction):
        res = "〆指示\n" if self.last_attack else "通し指示\n"
        res += "以下のメンバーにメンションを送ります\n"
        for idx in self.values:
            res += f"<@{self.members[int(idx)][1]}>\n"
        await interaction.response.edit_message(
            content=res,
            view=DCReprintConfirmView(
                self.boss_num,
                self.last_attack,
                self.members,
                self.values,
                self.original_message,
            ),
        )


class DCReprintConfirmView(discord.ui.View):
    def __init__(
        self,
        boss_num,
        last_attack,
        members,
        selected,
        original_message: discord.Message,
    ):
        super().__init__(timeout=240)
        self.boss_num = boss_num
        self.last_attack = last_attack
        self.members = members
        self.selected = selected
        self.original_message = original_message
        self.check = False

    async def interaction_check(self, interaction):
        if self.check:
            return False
        self.check = True
        return True

    @discord.ui.button(label="OK", style=discord.ButtonStyle.green)
    async def ok_button(self, interaction: discord.Interaction, button):
        async def del_mochi_reaction(member_id, boss):
            msg_id = db.read_guild("reaction_mochi_msg", interaction.guild_id)
            if msg_id != None:
                try:
                    ch_id = db.read_guild("reaction_ch", interaction.guild_id)
                    m_message = interaction.guild.get_channel(
                        ch_id
                    ).get_partial_message(msg_id)
                    member = interaction.guild.get_member(member_id)
                    await m_message.remove_reaction(
                        bytes.fromhex(f"3{str(boss)}e283a3").decode("utf-8"), member
                    )
                except:
                    return

        res = "〆　" if self.last_attack else "通し\n"
        # 新しいメッセージ送信
        if self.last_attack:
            await interaction.response.defer(ephemeral=True)
        else:
            send = await interaction.channel.send(
                self.original_message.content,
                view=DCReprintView(self.boss_num),
                silent=True,
            )
            await interaction.response.defer(ephemeral=True)
            global dc_reprint
            await dc_reprint[interaction.guild_id][self.boss_num - 1].delete()
            dc_reprint[interaction.guild_id][self.boss_num - 1] = send
            self.original_message = send

        # 先にメンションを送る
        for idx in self.selected:
            res += (
                interaction.guild.get_member(self.members[int(idx)][1]).mention + "\n"
            )
        send = await interaction.channel.send(content=res)
        members_list = []
        name_update = []

        for idx in self.selected:
            db.execute(
                f"UPDATE dc_{interaction.guild_id} SET done = 1 WHERE No = {self.members[int(idx)][0]}"
            )

            is_mochi = db.execute(
                f"SELECT status FROM dc_{interaction.guild_id} WHERE No = {self.members[int(idx)][0]}"
            )
            mochi = db.read_member(
                interaction.guild_id, "mochi", self.members[int(idx)][1]
            )
            if is_mochi != None and is_mochi[0][0][1] == "🔄":
                if mochi != None:
                    maxdamage = db.execute(
                        f"SELECT MAX(damage) FROM dc_{interaction.guild_id} WHERE boss = {self.boss_num}"
                    )[0][0]
                    damage = db.execute(
                        f"SELECT damage FROM dc_{interaction.guild_id} WHERE No = {self.members[int(idx)][0]}"
                    )[0][0]
                    mochi_slice = [
                        str(mochi)[i : i + 2] for i in range(0, len(str(mochi)), 2)
                    ]
                    rep = 0
                    # 短い持ち越し削除
                    if damage < maxdamage / 2:
                        if f"2{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(
                                interaction.guild,
                                self.members[int(idx)][1],
                                int(f"2{self.boss_num}"),
                            )
                            mochi_slice.remove(f"2{self.boss_num}")
                            rep = (
                                int("".join(mochi_slice)) if len(mochi_slice) > 0 else 0
                            )
                        # フル持ち越し削除
                        elif f"3{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(
                                interaction.guild,
                                self.members[int(idx)][1],
                                int(f"3{self.boss_num}"),
                            )
                            mochi_slice.remove(f"3{self.boss_num}")
                            rep = (
                                int("".join(mochi_slice)) if len(mochi_slice) > 0 else 0
                            )
                            await del_mochi_reaction(
                                self.members[int(idx)][1], self.boss_num
                            )
                        # 長い持ち越し削除
                        elif f"1{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(
                                interaction.guild,
                                self.members[int(idx)][1],
                                int(f"1{self.boss_num}"),
                            )
                            mochi_slice.remove(f"1{self.boss_num}")
                            rep = (
                                int("".join(mochi_slice)) if len(mochi_slice) > 0 else 0
                            )
                            await del_mochi_reaction(
                                self.members[int(idx)][1], self.boss_num
                            )
                    else:
                        if f"3{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(
                                interaction.guild,
                                self.members[int(idx)][1],
                                int(f"3{self.boss_num}"),
                            )
                            mochi_slice.remove(f"3{self.boss_num}")
                            rep = (
                                int("".join(mochi_slice)) if len(mochi_slice) > 0 else 0
                            )
                            await del_mochi_reaction(
                                self.members[int(idx)][1], self.boss_num
                            )
                        elif f"1{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(
                                interaction.guild,
                                self.members[int(idx)][1],
                                int(f"1{self.boss_num}"),
                            )
                            mochi_slice.remove(f"1{self.boss_num}")
                            rep = (
                                int("".join(mochi_slice)) if len(mochi_slice) > 0 else 0
                            )
                            await del_mochi_reaction(
                                self.members[int(idx)][1], self.boss_num
                            )
                        # 短い持ち越し削除
                        elif f"2{self.boss_num}" in mochi_slice:
                            MochiTableHelper.add(
                                interaction.guild,
                                self.members[int(idx)][1],
                                int(f"2{self.boss_num}"),
                            )
                            mochi_slice.remove(f"2{self.boss_num}")
                            rep = (
                                int("".join(mochi_slice)) if len(mochi_slice) > 0 else 0
                            )
                    db.write_member(
                        interaction.guild_id, self.members[int(idx)][1], "mochi", rep
                    )
                name_update.append((self.members[int(idx)][1], 0, -1))
            else:
                members_list.append(self.members[int(idx)])
                if self.last_attack:
                    name_update.append((self.members[int(idx)][1], -1, 1))
                else:
                    name_update.append((self.members[int(idx)][1], -1, 0))
            global prev_mochi
            if not interaction.guild_id in prev_mochi:
                prev_mochi[interaction.guild_id] = [[], [], [], [], []]
            prev_mochi[interaction.guild_id][self.boss_num - 1].append(
                (self.members[int(idx)][0], mochi)
            )

        content = Generator.dc_content(interaction.guild, self.boss_num)
        dc_message = interaction.guild.get_channel(
            db.read_guild("dc_ch", interaction.guild_id)
        ).get_partial_message(
            db.read_guild("dc_msg", interaction.guild_id).split("\n")[self.boss_num - 1]
        )
        await dc_message.edit(content=content)
        await dc_reprint[interaction.guild_id][self.boss_num - 1].edit(content=content)
        await DC.table_change(interaction.guild, self.boss_num, members_list, True)
        prev_message.add(
            interaction.guild_id,
            send.id,
            self.boss_num,
            [self.members[int(idx)][0] for idx in self.selected],
            self.last_attack,
        )
        if self.last_attack:
            if len(members_list) > 0:
                await interaction.edit_original_response(
                    content="持ち越しを選択",
                    view=DCMochiSelectView(interaction.guild_id, members_list[0]),
                )
            else:
                await interaction.delete_original_response()
        else:
            await interaction.delete_original_response()
        # 名前を更新
        for m in name_update:
            global prev_name
            prev = interaction.guild.get_member(m[0]).display_name
            is_finish = await DC.zan_update(m[0], interaction.guild, m[1], m[2])
            global finish_members
            if not interaction.guild_id in finish_members:
                finish_members[interaction.guild_id] = [[], [], [], [], []]
            if is_finish:
                finish_members[interaction.guild_id][self.boss_num - 1].append(m[0])
            prev_name.add(interaction.guild_id, m[0], prev, self.boss_num)

        SpreadSheetDC.write(interaction.guild, self.boss_num)

    @discord.ui.button(label="取り消し", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="取り消しました", view=None)


class DCReprintCancelMembersView(discord.ui.View):
    def __init__(self, boss_num, guild, original_message):
        super().__init__(timeout=240)
        self.add_item(DCReprintCancelMembersSelect(boss_num, guild, original_message))


class DCReprintCancelMembersSelect(discord.ui.Select):
    def __init__(self, boss_num, guild: discord.Guild, original_message):
        self.boss_num = boss_num
        self.guild = guild
        self.original_message = original_message
        self.members = db.execute(
            f"SELECT No,id FROM dc_{guild.id} WHERE boss = {self.boss_num} AND done = 1 ORDER BY No DESC"
        )
        self.names = [guild.get_member(v[1]).display_name for v in self.members]
        options = []
        ids = []
        if len(self.members) >= 1:
            for i, m in enumerate(self.members):
                if m[1] in ids:
                    continue
                ids.append(m[1])
                options.append(discord.SelectOption(label=self.names[i], value=str(i)))
        max_values = 20
        super().__init__(options=options[:20], max_values=min(max_values, len(options)))

    async def callback(self, interaction: discord.Interaction):
        res = "指示キャンセル\n以下のメンバーにメンションを送ります\n"
        for idx in self.values:
            res += f"<@{self.members[int(idx)][1]}>\n"
        await interaction.response.edit_message(
            content=res,
            view=DCReprintCancelConfirmView(
                self.boss_num, self.members, self.values, self.original_message
            ),
        )


class DCReprintCancelConfirmView(discord.ui.View):
    def __init__(self, boss_num, members, selected, original_message: discord.Message):
        super().__init__(timeout=240)
        self.boss_num = boss_num
        self.members = members
        self.selected = selected
        self.original_message = original_message

    @discord.ui.button(label="OK", style=discord.ButtonStyle.green)
    async def ok_button(self, interaction: discord.Interaction, button):
        def find(No):
            global prev_mochi
            if not interaction.guild_id in prev_mochi:
                return -1
            for i, m in enumerate(prev_mochi[interaction.guild_id][self.boss_num - 1]):
                if m[0] == No:
                    return prev_mochi[interaction.guild_id][self.boss_num - 1].pop(i)[1]
            return -1

        await interaction.response.edit_message(view=None)
        await interaction.delete_original_response()
        res = "キャンセル\n"
        # 新しいメッセージ送信

        send = await interaction.channel.send(
            self.original_message.content,
            view=DCReprintView(self.boss_num),
            silent=True,
        )
        global dc_reprint
        await dc_reprint[interaction.guild_id][self.boss_num - 1].delete()
        dc_reprint[interaction.guild_id][self.boss_num - 1] = send
        self.original_message = send

        # 先にメンションを送る
        for idx in self.selected:
            res += (
                interaction.guild.get_member(self.members[int(idx)][1]).mention + "\n"
            )
        await interaction.channel.send(content=res)

        members_list = []
        message_ids = []
        for idx in self.selected:
            db.execute(
                f"UPDATE dc_{interaction.guild_id} SET done = 0 WHERE No = {self.members[int(idx)][0]}"
            )
            prev = find(self.members[int(idx)][0])
            if prev != -1:
                if prev != None and prev > 0:
                    db.write_member(
                        interaction.guild_id, self.members[int(idx)][1], "mochi", prev
                    )
                else:
                    db.delete_member(
                        interaction.guild_id, self.members[int(idx)][1], "mochi"
                    )
                MochiTableHelper.undo(interaction.guild, self.members[int(idx)][1])
            members_list.append(self.members[int(idx)])
            message_ids.append(
                prev_message.delete_No(interaction.guild_id, self.members[int(idx)][0])
            )
            # 3凸完了リスト削除
            global finish_members
            if (
                interaction.guild_id in finish_members
                and self.members[int(idx)][1]
                in finish_members[interaction.guild_id][self.boss_num - 1]
            ):
                finish_members[interaction.guild_id][self.boss_num - 1].remove(
                    self.members[int(idx)][1]
                )
        ###############
        # メンション削除
        for message_id in set(message_ids):
            try:
                pm = interaction.channel.get_partial_message(message_id)
                c = prev_message.content(interaction.guild_id, message_id)
                if c != None:
                    await pm.edit(content=c)
                else:
                    await pm.delete()
            except:
                continue
        ###############
        content = Generator.dc_content(interaction.guild, self.boss_num)
        dc_message = interaction.guild.get_channel(
            db.read_guild("dc_ch", interaction.guild_id)
        ).get_partial_message(
            db.read_guild("dc_msg", interaction.guild_id).split("\n")[self.boss_num - 1]
        )
        await dc_message.edit(content=content)
        await self.original_message.edit(content=content)
        await DC.table_change(interaction.guild, self.boss_num, members_list, False)
        global prev_name
        for idx in self.selected:
            prev = prev_name.get(interaction.guild_id, self.members[int(idx)][1])
            if prev != None:
                try:
                    m = interaction.guild.get_member(self.members[int(idx)][1])
                    await m.edit(nick=prev)
                except:
                    pass
        SpreadSheetDC.write(interaction.guild, self.boss_num)

    @discord.ui.button(label="取り消し", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="取り消しました", view=None)


class DCMochiSelectView(discord.ui.View):
    def __init__(self, guild_id, member_id, prev=None):
        if isinstance(member_id, int):
            self.member_id = member_id
        else:
            self.member_id = member_id[1]
        if prev != None:
            self.prev = prev
        else:
            self.prev = db.read_member(guild_id, "mochi", self.member_id)
            if self.prev == None:
                self.prev = 0
        super().__init__(timeout=240)

    async def update(self, guild: discord.Guild):
        message = guild.get_channel(
            db.read_guild("reaction_ch", guild.id)
        ).get_partial_message(db.read_guild("reaction_msg", guild.id))
        await message.add_reaction("〰")

    @discord.ui.button(label="1フル", style=discord.ButtonStyle.blurple, row=0)
    async def boss1full_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 31
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="１ボスフル持ち越し",
            view=DCMochiEditView(self.member_id, self.prev),
        )

    @discord.ui.button(label="1長餅", style=discord.ButtonStyle.blurple, row=0)
    async def boss1long_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 11
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="１ボス長い持ち越し",
            view=DCMochiEditView(self.member_id, self.prev),
        )

    @discord.ui.button(label="1小餅", style=discord.ButtonStyle.gray, row=0)
    async def boss1short_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 21
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="１ボス短い持ち越し",
            view=DCMochiEditView(self.member_id, self.prev),
        )

    @discord.ui.button(label="2フル", style=discord.ButtonStyle.blurple, row=1)
    async def boss2full_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 32
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="2ボスフル持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="2長餅", style=discord.ButtonStyle.blurple, row=1)
    async def boss2long_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 12
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="2ボス長い持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="2小餅", style=discord.ButtonStyle.gray, row=1)
    async def boss2short_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 22
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="2ボス短い持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="3フル", style=discord.ButtonStyle.blurple, row=2)
    async def boss3full_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 33
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="3ボスフル持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="3長餅", style=discord.ButtonStyle.blurple, row=2)
    async def boss3long_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 13
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="3ボス長い持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="3小餅", style=discord.ButtonStyle.gray, row=2)
    async def boss3short_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 23
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="3ボス短い持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="4フル", style=discord.ButtonStyle.blurple, row=3)
    async def boss4full_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 34
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="4ボスフル持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="4長餅", style=discord.ButtonStyle.blurple, row=3)
    async def boss4long_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 14
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="4ボス長い持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="4小餅", style=discord.ButtonStyle.gray, row=3)
    async def boss4short_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 24
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="4ボス短い持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="5フル", style=discord.ButtonStyle.blurple, row=4)
    async def boss5full_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 35
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="5ボスフル持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="5長餅", style=discord.ButtonStyle.blurple, row=4)
    async def boss5long_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 15
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="5ボス長い持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )

    @discord.ui.button(label="5小餅", style=discord.ButtonStyle.gray, row=4)
    async def boss5short_button(self, interaction: discord.Interaction, button):
        db.write_member(
            interaction.guild_id, self.member_id, "mochi", self.prev * 100 + 25
        )
        await self.update(interaction.guild)
        await interaction.response.edit_message(
            content="5ボス短い持ち越し", view=DCMochiEditView(self.member_id, self.prev)
        )


class DCMochiEditView(discord.ui.View):
    def __init__(self, member_id, prev):
        self.member_id = member_id
        self.prev = prev
        super().__init__(timeout=240)

    @discord.ui.button(label="持ち越し変更", style=discord.ButtonStyle.gray)
    async def edit_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(
            content="持ち越しを選択",
            view=DCMochiSelectView(interaction.guild_id, self.member_id, self.prev),
        )


class KaihouConfirmView(discord.ui.View):
    def __init__(self, boss_num):
        self.boss_num = boss_num
        super().__init__(timeout=240)

    @discord.ui.button(label="OK", style=discord.ButtonStyle.green)
    async def ok_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(view=None)
        await interaction.delete_original_response()
        """
        mentions_id=db.execute(f"SELECT id FROM dc_{interaction.guild_id} WHERE boss = {self.boss_num} AND done <> 1")
        mentions=""
        for mention_id in mentions_id:
            mentions+=f"<@{mention_id[0]}> "
        text="開放"
        if interaction.guild_id == 0:
            text=mentions + f"\n{self.boss_num}ボス開放"

        await interaction.channel.send(text)
        """

        def get_sticker(guild: discord.Guild, id: int):
            for sticker in guild.stickers:
                if sticker.id == id:
                    return [sticker]
            return None

        if interaction.guild_id == 1276184060791750656:
            match self.boss_num:
                case 1:
                    await interaction.channel.send(
                        stickers=get_sticker(interaction.guild, 1343949879013281802)
                    )
                case 2:
                    await interaction.channel.send(
                        stickers=get_sticker(interaction.guild, 1354476245290586223)
                    )
                case 3:
                    await interaction.channel.send(
                        stickers=get_sticker(interaction.guild, 1343950149029859339)
                    )
                case 4:
                    await interaction.channel.send(
                        stickers=get_sticker(interaction.guild, 1343950198967111843)
                    )
                case 5:
                    await interaction.channel.send(
                        stickers=get_sticker(interaction.guild, 1343950249546350673)
                    )
            await asyncio.sleep(0.5)

        # ダメコン終了
        members = db.execute(
            f"SELECT * FROM dc_{interaction.guild_id} WHERE boss = {self.boss_num}"
        )
        db.execute(
            f"DELETE FROM dc_{interaction.guild_id} WHERE boss = {self.boss_num}"
        )

        message_ch = db.read_guild("dc_ch", interaction.guild_id)
        message_id = db.read_guild("dc_msg", interaction.guild_id).split()[
            self.boss_num - 1
        ]
        message = interaction.guild.get_channel(message_ch).get_partial_message(
            int(message_id)
        )
        fetch_message = await message.fetch()
        fetch_content = fetch_message.content
        content = Generator.dc_content(interaction.guild, self.boss_num)
        await fetch_message.edit(content=content)

        await message.clear_reactions()
        await message.add_reaction("🔄")
        await message.add_reaction(
            discord.PartialEmoji.from_str("<:syu:1525129140867563571> ")
        )
        await message.add_reaction("🔼")
        await message.add_reaction("🔻")
        await message.add_reaction("🔥")
        await message.add_reaction("❌")
        await message.add_reaction("✅")
        await message.add_reaction("👉")
        log = None
        if db.read_guild("log_ch", interaction.guild_id) != None:
            log = await interaction.guild.get_channel(
                db.read_guild("log_ch", interaction.guild_id)
            ).send(fetch_content)
        prev_stat = {"dc_reprint": None, "table_reaction": [], "prev_mochi": []}
        global dc_reprint
        if (
            message.guild.id in dc_reprint
            and dc_reprint[message.guild.id][self.boss_num - 1] != None
        ):
            global table_reaction
            if message.guild.id in table_reaction:
                prev_stat["table_reaction"] = table_reaction[message.guild.id][
                    self.boss_num - 1
                ]
                table_reaction[message.guild.id][self.boss_num - 1] = []
            prev_stat["dc_reprint"] = dc_reprint[message.guild.id][self.boss_num - 1]
            dc_reprint[message.guild.id][self.boss_num - 1] = None
        global prev_mochi
        if interaction.guild.id in prev_mochi:
            prev_stat["prev_mochi"] = prev_mochi[interaction.guild.id][
                self.boss_num - 1
            ]
            prev_mochi[interaction.guild.id][self.boss_num - 1] = []
        prev_stat["prev_message"] = prev_message.delete_boss(
            message.guild.id, self.boss_num
        )
        prev_stat["prev_name"] = prev_name.delete(interaction.guild_id, self.boss_num)

        await interaction.guild.get_channel(message_ch).send(
            "討伐されました",
            view=DCCompleteView(members, log, fetch_content, self.boss_num, prev_stat),
            delete_after=60,
            reference=message,
        )
        SpreadSheetDC.write(interaction.guild, self.boss_num)

        # 完凸した人にメンション
        global finish_members
        mention_members = []
        if interaction.guild_id in finish_members:
            for member_id in finish_members[interaction.guild_id][self.boss_num - 1]:
                is_finish = db.read_member(interaction.guild_id, "finish", member_id)
                if is_finish == None:
                    mention_members.append(member_id)
            finish_members[interaction.guild_id][self.boss_num - 1] = []
        if len(mention_members) > 0:
            names = [f"<@{v}>" for v in mention_members]

    @discord.ui.button(label="取り消し", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="取り消しました", view=None)


class DamageListView(discord.ui.LayoutView):
    def __init__(self, guild: discord.Guild, boss_num):
        super().__init__(timeout=360)
        self.boss_num = boss_num
        self.damage_list = []
        self.member_select_row.add_item(DamageListMembers(boss_num, guild, self))
        self.multiplier = 1
        self.button1_1.disabled = True
        members = db.execute(
            f"SELECT damage FROM dc_{guild.id} WHERE boss = {self.boss_num} AND done = 0 ORDER BY damage DESC"
        )
        for member in members:
            if int(member[0]) > 0:
                self.damage_list.append(member[0])
        self.gen_content()

    def gen_content(self):
        content = ""
        if len(self.damage_list) > 0:
            for damage in self.damage_list:
                content += f" {math.floor(damage*self.multiplier)}"
            self.result_text.content = content
        else:
            self.result_text.content = "結果が表示されます"

    result_text = discord.ui.TextDisplay("結果が表示されます")

    member_select_row = discord.ui.ActionRow()

    acrion_row = discord.ui.ActionRow()

    @acrion_row.button(label="1/1")
    async def button1_1(self, interaction: discord.Interaction, button):
        self.multiplier = 1
        self.gen_content()
        self.button1_1.disabled = True
        self.button1_10.disabled = False
        self.button1_100.disabled = False
        self.button1_1000.disabled = False
        await interaction.response.edit_message(view=self)

    @acrion_row.button(label="1/10")
    async def button1_10(self, interaction: discord.Interaction, button):
        self.multiplier = 0.1
        self.gen_content()
        self.button1_1.disabled = False
        self.button1_10.disabled = True
        self.button1_100.disabled = False
        self.button1_1000.disabled = False
        await interaction.response.edit_message(view=self)

    @acrion_row.button(label="1/100")
    async def button1_100(self, interaction: discord.Interaction, button):
        self.multiplier = 0.01
        self.gen_content()
        self.button1_1.disabled = False
        self.button1_10.disabled = False
        self.button1_100.disabled = True
        self.button1_1000.disabled = False
        await interaction.response.edit_message(view=self)

    @acrion_row.button(label="1/1000")
    async def button1_1000(self, interaction: discord.Interaction, button):
        self.multiplier = 0.001
        self.gen_content()
        self.button1_1.disabled = False
        self.button1_10.disabled = False
        self.button1_100.disabled = False
        self.button1_1000.disabled = True
        await interaction.response.edit_message(view=self)


class DamageListMembers(discord.ui.Select):
    def __init__(self, boss_num, guild: discord.Guild, view: DamageListView):
        self.boss_num = boss_num
        self.guild = guild
        self.editview = view
        self.members = db.execute(
            f"SELECT No,id,status,damage FROM dc_{guild.id} WHERE boss = {self.boss_num} AND done = 0 ORDER BY damage DESC"
        )
        self.names = [guild.get_member(v[1]).display_name for v in self.members]
        options = []
        if len(self.members) >= 1:
            for i, m in enumerate(self.members):
                options.append(
                    discord.SelectOption(
                        label=f"{self.names[i]}　{m[2]}　{m[3]}", value=str(i)
                    )
                )

        super().__init__(options=options[:20], max_values=min(20, len(options)))

    async def callback(self, interaction: discord.Interaction):
        damage_list = []
        for idx in sorted(self.values):
            damage_list.append(self.members[int(idx)][3])
        self.editview.damage_list = damage_list
        self.editview.gen_content()
        await interaction.response.edit_message(view=self.editview)
