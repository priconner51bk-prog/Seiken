import asyncio
import copy
import itertools
import json
import os
import re
import warnings
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import discord
import emoji
import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
from cv2 import add
from discord import app_commands, reaction
from discord.ext import commands
from proto import Message

from util.content_generator import Generator
from util.database import db
from util.debug_util import debug_write
from util.decorators import DpyDecorator
from util.emoji_util import EmojiUtil

warnings.filterwarnings("ignore", category=UserWarning)

fonts = []
for f in os.listdir("./font"):
    fm.fontManager.addfont(f"font/{f}")
    fonts.append(fm.FontProperties(fname=f"font/{f}").get_name())
plt.rcParams["font.family"] = fonts
matplotlib.use("Agg")


class ForwardMessageUtil:
    messages: dict
    file_path = "forwardmessage.json"

    def __init__(self):
        self.messages = {}

    @staticmethod
    async def MessageFromURL(guild: discord.Guild, url: str):
        parts = url.rstrip("/").split("/")
        if len(parts) < 4:
            return None
        if (int(parts[-3])) != guild.id:
            return None
        channel_id = int(parts[-2])
        message_id = int(parts[-1])
        message = None
        try:
            message = await guild.get_channel(channel_id).fetch_message(message_id)
        except:
            pass
        return message

    def Register(self, message: discord.Message, boss):
        # boss 0~4
        if message.guild.id not in self.messages:
            self.messages[message.guild.id] = [None for _ in range(5)]
        self.messages[message.guild.id][boss] = message

    def Delete(self, guild_id, boss):
        if guild_id in self.messages:
            self.messages[guild_id][boss] = None

    def Save(self):
        values = {}
        for key in self.messages:
            values[key] = [
                x.jump_url if x != None else None for x in self.messages[key]
            ]
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(values, f, ensure_ascii=False, indent=2)

    async def Load(self, bot: commands.Bot):
        if not os.path.exists(self.file_path):
            return
        today = datetime.today()
        if (today + timedelta(days=9)).day == 1:
            os.remove(self.file_path)
            return
        with open(self.file_path, "r", encoding="utf-8") as f:
            values = json.load(f)
        await bot.wait_until_ready()
        for key in values:
            for i in range(5):
                if values[key][i] != None:
                    guild = bot.get_guild(int(key))
                    message = await ForwardMessageUtil.MessageFromURL(
                        guild, values[key][i]
                    )
                    self.Register(message, i)

    def Get(self, guild_id, boss):
        if guild_id not in self.messages:
            return ""
        if self.messages[guild_id][boss] == None:
            return ""
        return self.messages[guild_id][boss].jump_url

    def GetMessage(self, guild_id, boss) -> None | discord.Message:
        if guild_id not in self.messages:
            return None
        if self.messages[guild_id][boss] == None:
            return None
        return self.messages[guild_id][boss]

    def Check(self, guild_id, boss):
        if guild_id not in self.messages:
            return False
        if self.messages[guild_id][boss] == None:
            return False
        return True

    async def Forward(self, channel: discord.TextChannel, boss):
        if (
            channel.guild.id not in self.messages
            or self.messages[channel.guild.id][boss] is None
        ):
            debug_write("Forward: source message not found")
            return

        source_message = self.messages[channel.guild.id][boss]
        forwarded_message = await source_message.forward(channel)

        for reaction in source_message.reactions:
            emoji = reaction.emoji
            try:
                if isinstance(emoji, str):
                    debug_write(f"custom emoji string={emoji}")
                    await forwarded_message.add_reaction(emoji)
                else:
                    resolved = EmojiUtil.get(emoji.id)
                    debug_write(f"custom emoji resolved={resolved!r} id={emoji.id}")
                    await forwarded_message.add_reaction(resolved)
            except Exception as e:
                debug_write(f"failed emoji={emoji!r} error={e!r}")


forward_message = ForwardMessageUtil()


class RaiseHandCounter:
    members = {}
    messages = {}
    edit_timer = {}

    def Start(self, message: discord.Message, memberslist: list):
        if message.guild.id not in self.members:
            self.members[message.guild.id] = {}
            self.messages[message.guild.id] = {}
            self.edit_timer[message.guild.id] = {}
        self.members[message.guild.id][message.channel.id] = {}
        for mentions in memberslist:
            member_id = int(re.search(r"\d+", mentions).group())
            self.members[message.guild.id][message.channel.id][member_id] = False
        self.messages[message.guild.id][message.channel.id] = message
        self.edit_timer[message.guild.id][message.channel.id] = datetime.now()

    def Count(self, message: discord.Message):
        if message == None or message.author.bot:
            return 0
        if (
            (
                len(message.stickers) > 0
                and message.stickers[0].id == 1304441542542360637
            )
            or "<:honsen_start:1343468869137858600>" in message.content
            or "<:seiken:806760893521985546>" in message.content
        ):
            self.members[message.guild.id][message.channel.id] = {}
            del self.messages[message.guild.id][message.channel.id]
            del self.edit_timer[message.guild.id][message.channel.id]
            return 0
        if (
            message.guild.id in self.members
            and message.channel.id in self.members[message.guild.id]
            and message.author.id in self.members[message.guild.id][message.channel.id]
        ):
            if (
                datetime.now() - self.edit_timer[message.guild.id][message.channel.id]
            ).total_seconds() > 3600:
                return 0
            if (
                self.members[message.guild.id][message.channel.id][message.author.id]
                == False
            ):
                self.members[message.guild.id][message.channel.id][
                    message.author.id
                ] = True
                asyncio.create_task(self.Edit(message.channel))
                return sum(
                    1
                    for x in self.members[message.guild.id][message.channel.id]
                    if self.members[message.guild.id][message.channel.id][x]
                )
        return 0

    async def Edit(self, channel: discord.TextChannel):
        if datetime.now() > self.edit_timer[channel.guild.id][channel.id]:
            self.edit_timer[channel.guild.id][channel.id] = datetime.now() + timedelta(
                seconds=7.1
            )
            await asyncio.sleep(7)
            self.edit_timer[channel.guild.id][channel.id] = datetime.now()

            text = discord.ui.TextDisplay(
                self.messages[channel.guild.id][channel.id].components[0].content
            )
            notready = discord.ui.Container(discord.ui.TextDisplay("⠀"))
            ready = discord.ui.Container(
                discord.ui.TextDisplay("⠀"), accent_color=discord.Colour.green()
            )
            members = self.members[channel.guild.id][channel.id]
            ready_members = []
            notready_members = []
            for member in members:
                if members[member]:
                    ready_members.append(f"<@{member}>")
                else:
                    notready_members.append(f"<@{member}>")
            ready.children[0].content = (
                f"{len(ready_members)}人\n" + " ".join(ready_members)
                if len(ready_members) > 0
                else "0人"
            )
            notready.children[0].content = (
                " ".join(notready_members) if len(notready_members) > 0 else "⠀"
            )
            view = discord.ui.LayoutView(timeout=None)
            view.add_item(text)
            view.add_item(notready)
            view.add_item(ready)

            await self.messages[channel.guild.id][channel.id].edit(view=view)


raiserhand_counter = RaiseHandCounter()


class TotsuAtSameTimeReservationUtility:
    def __init__(self):
        self.members = [[], [], [], [], []]
        self.combination = []
        self.divide = []
        self.comp = [False, False, False, False, False]

    def register(self, guild_id, boss1, boss2):
        if len(self.members[boss1 - 1]) == 0 and len(self.members[boss2 - 1]) == 0:
            members1 = TotsuAtSameTimeReservationUtility.get_members(guild_id, boss1)
            members2 = TotsuAtSameTimeReservationUtility.get_members(guild_id, boss2)
            if len(members1) > 0 and len(members2) > 0:
                self.combination.append(sorted([boss1, boss2]))
                common = list(set(members1) & set(members2))
                self.members[boss1 - 1] = [x for x in members1 if x not in common]
                self.members[boss2 - 1] = [x for x in members2 if x not in common]
                self.divide.append([])
                return True
        return False

    def member_check(self, guild_id, boss1, boss2, afk=False):
        members1 = TotsuAtSameTimeReservationUtility.get_members(guild_id, boss1, afk)
        members2 = TotsuAtSameTimeReservationUtility.get_members(guild_id, boss2, afk)
        common = list(set(members1) & set(members2))
        unique1 = [x for x in members1 if x not in common]
        unique2 = [x for x in members2 if x not in common]
        append1 = list(set(unique1) - set(self.members[boss1 - 1]))
        append2 = list(set(unique2) - set(self.members[boss2 - 1]))
        divide = self.divide[self.combination.index(sorted([boss1, boss2]))]
        # 振り分けていない人を削除
        for m in list(set(self.members[boss1 - 1]) & set(common))[:]:
            if m not in divide:
                self.members[boss1 - 1].remove(m)
        for m in list(set(self.members[boss2 - 1]) & set(common))[:]:
            if m not in divide:
                self.members[boss2 - 1].remove(m)
        for a in append1:
            self.members[boss1 - 1].append(a)
        for a in append2:
            self.members[boss2 - 1].append(a)
        common_sub = common[:]
        for c in common_sub[:]:
            if c in self.members[boss1 - 1]:
                common_sub.remove(c)
                unique1.append(c)
            if c in self.members[boss2 - 1]:
                common_sub.remove(c)
                unique2.append(c)
        return unique1, unique2, common_sub, common

    def set_member(self, member_id, selected, boss):
        other, idx = self.find_other(boss)
        if member_id in self.members[boss - 1] and not selected:
            self.members[boss - 1].remove(member_id)
            if member_id in self.divide[idx]:
                self.divide[idx].remove(member_id)
        elif member_id not in self.members[boss - 1] and selected:
            self.members[boss - 1].append(member_id)
            if member_id in self.members[other - 1]:
                self.members[other - 1].remove(member_id)
            if member_id not in self.divide[idx]:
                self.divide[idx].append(member_id)

    @staticmethod
    def get_members(guild_id, boss, afk=False):
        sql = f"SELECT id FROM member_{guild_id} WHERE boss{boss} IS NOT NULL"
        sql2 = f"SELECT id,mochi FROM member_{guild_id} WHERE mochi > 0"
        if afk:
            sql += " AND AFK IS NULL"
            sql2 += " AND AFK IS NULL"
        members = db.execute(sql)
        members = list(itertools.chain.from_iterable(members))
        mochi = db.execute(sql2)
        for m in mochi:
            if str(boss) in [str(m[1])[i + 1] for i in range(0, len(str(m[1])), 2)]:
                members.append(m[0])
        return members

    def find_other(self, boss):
        for i, (a, b) in enumerate(self.combination):
            if boss == a:
                return b, i
            if boss == b:
                return a, i
        return None, None

    def to_dict(self):
        return self.__dict__


class TotsuAtSameTimeReservationData:
    data: dict[int, TotsuAtSameTimeReservationUtility] = {}
    file_path = "douji.json"

    def register(self, guild_id, boss1, boss2):
        if guild_id not in self.data:
            self.data[guild_id] = TotsuAtSameTimeReservationUtility()
        result = self.data[guild_id].register(guild_id, boss1, boss2)
        self.save()
        return result

    def button_disabled(self, guild_id):
        if guild_id not in self.data:
            return [False, False, False, False, False]
        result = [False, False, False, False, False]
        for boss in list(
            itertools.chain.from_iterable(self.data[guild_id].combination)
        ):
            result[boss - 1] = True
        return result

    def get_conbination(self, guild_id):
        if guild_id not in self.data:
            return [], 0
        return self.data[guild_id].combination, len(self.data[guild_id].combination)

    def get_members(self, guild_id, boss1, boss2, afk=False):
        if guild_id not in self.data:
            return [], [], [], []
        return self.data[guild_id].member_check(guild_id, boss1, boss2, afk)

    def set_members(self, guild_id, members, selected, boss):
        if guild_id not in self.data:
            return
        for i in range(len(members)):
            self.data[guild_id].set_member(members[i], selected[i], boss)
        self.save()

    def delete(self, guild_id, idx=None, boss=None):
        if guild_id not in self.data:
            return
        if idx == None and boss == None:
            return
        if boss != None:
            _, idx = self.data[guild_id].find_other(boss)
        boss1 = self.data[guild_id].combination[idx][0]
        boss2 = self.data[guild_id].combination[idx][1]
        self.data[guild_id].members[boss1 - 1] = []
        self.data[guild_id].members[boss2 - 1] = []
        self.data[guild_id].comp[boss1 - 1] = False
        self.data[guild_id].comp[boss2 - 1] = False
        del self.data[guild_id].divide[idx]
        del self.data[guild_id].combination[idx]
        self.save()

    def contain(self, guild_id, boss):
        if guild_id not in self.data:
            return False
        if boss in list(itertools.chain.from_iterable(self.data[guild_id].combination)):
            return True
        return False

    def find_other(self, guild_id, boss):
        if guild_id not in self.data:
            return
        boss2 = self.data[guild_id].find_other(boss)
        return boss2[0]

    def check_comp(self, guild_id, boss):
        if guild_id not in self.data:
            return False
        return self.data[guild_id].comp[boss - 1]

    def set_comp(self, guild_id, boss):
        if guild_id not in self.data:
            return
        other, idx = self.data[guild_id].find_other(boss)
        if other == None:
            return
        self.data[guild_id].comp[boss - 1] = True
        if self.data[guild_id].comp[boss - 1] and self.data[guild_id].comp[other - 1]:
            self.delete(guild_id, idx)
        else:
            self.save()

    def save(self):
        dict_data = {v: self.data[v].to_dict() for v in self.data}
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(dict_data, f, ensure_ascii=False, indent=2)

    def load(self):
        if not os.path.exists(self.file_path):
            return
        with open(self.file_path, "r", encoding="utf-8") as f:
            values = json.load(f)
        for key in values:
            guild_id = int(key)
            self.data[guild_id] = TotsuAtSameTimeReservationUtility()
            self.data[guild_id].members = values[key]["members"]
            self.data[guild_id].combination = values[key]["combination"]
            self.data[guild_id].comp = values[key]["comp"]
            self.data[guild_id].divide = values[key]["divide"]

    def file_delete(self):
        if not os.path.exists(self.file_path):
            return
        os.remove(self.file_path)
        self.data = {}


reservation = TotsuAtSameTimeReservationData()


class TotsuChangeView(discord.ui.View):
    def __init__(self, member_id, totsu: list):
        super().__init__(timeout=240)
        mochi = (
            [int(str(totsu[5])[i : i + 2]) for i in range(0, len(str(totsu[5])), 2)]
            if totsu[5] != None
            else [0]
        )
        for row in range(5):
            for column in range(5):
                text = ""
                style = discord.ButtonStyle.gray
                match row:
                    case 0:
                        text = str(column + 1)
                        if totsu[column] == 1:
                            style = discord.ButtonStyle.green
                    case 1:
                        text = f"フ"
                        if 30 + column + 1 in mochi:
                            style = discord.ButtonStyle.red
                    case 2:
                        text = f"長"
                        if 10 + column + 1 in mochi:
                            style = discord.ButtonStyle.red
                    case 3 | 4:
                        text = f"短{row-2}"
                        if 20 + column + 1 in mochi:
                            style = discord.ButtonStyle.red
                            mochi.remove(20 + column + 1)
                self.add_item(
                    TotsuChageButton(text, member_id, style, row, column, totsu)
                )


class TotsuChageButton(discord.ui.Button):
    def __init__(self, text, member_id, style, row, col, totsu: list):
        self.col = col
        self.member_id = member_id
        self.totsu = totsu
        super().__init__(label=text, style=style, row=row)

    async def callback(self, interaction: discord.Interaction):
        mochi = (
            [
                int(str(self.totsu[5])[i : i + 2])
                for i in range(0, len(str(self.totsu[5])), 2)
            ]
            if self.totsu[5] != None
            else [0]
        )
        prev = mochi.copy()
        match self.row:
            case 0:
                if self.totsu[self.col] == None:
                    db.write_member(
                        interaction.guild_id, self.member_id, f"boss{self.col+1}", 1
                    )
                else:
                    db.delete_member(
                        interaction.guild_id, self.member_id, f"boss{self.col+1}"
                    )
            case 1:
                if 30 + self.col + 1 in mochi:
                    mochi.remove(30 + self.col + 1)
                else:
                    mochi.append(30 + self.col + 1)
            case 2:
                if 10 + self.col + 1 in mochi:
                    mochi.remove(10 + self.col + 1)
                else:
                    mochi.append(10 + self.col + 1)
            case 3 | 4:
                if 20 + self.col + 1 in mochi and self.style == discord.ButtonStyle.red:
                    mochi.remove(20 + self.col + 1)
                else:
                    mochi.append(20 + self.col + 1)
        if mochi != prev:
            if 0 in mochi:
                mochi.remove(0)
            if len(mochi) == 0:
                db.delete_member(interaction.guild_id, self.member_id, "mochi")
            else:
                db.write_member(
                    interaction.guild_id,
                    self.member_id,
                    "mochi",
                    sum([mochi[i] * (100**i) for i in range(len(mochi))]),
                )
        totsu = db.execute(
            f"SELECT boss1,boss2,boss3,boss4,boss5,mochi FROM member_{interaction.guild_id} WHERE id = {self.member_id}"
        )[0]
        content = "１列目　本凸\n２列目　フル持ち越し\n３列目　長い持ち越し\n４列目以降　短い持ち越し"
        await interaction.response.edit_message(
            content=content, view=TotsuChangeView(self.member_id, totsu)
        )
        message = interaction.guild.get_channel(
            db.read_guild("reaction_ch", interaction.guild_id)
        ).get_partial_message(db.read_guild("reaction_msg", interaction.guild_id))
        await message.add_reaction("〰")


class RecruitMemberView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i in range(5):
            self.add_item(RecruitMemberButton(i + 1))
        self.add_item(RecruitMemberSelectButton())
        self.add_item(ForwardMessageButton())
        self.add_item(TotsuAtTheSameTimeStartButton())

    async def interaction_check(self, interaction: discord.Interaction):
        roles = [
            interaction.guild.get_role(808240600691900417),
            interaction.guild.get_role(1292855894454964336),
            interaction.guild.get_role(1335210159735177297),
        ]
        if set(roles) & set(interaction.user.roles):
            return True
        return False


class RecruitMemberButton(discord.ui.Button):
    def __init__(self, boss_num):
        super().__init__(
            label=f"{boss_num}募集",
            style=discord.ButtonStyle.gray,
            custom_id=f"Recruitmember{boss_num}",
        )
        self.boss_num = boss_num

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        members = db.execute(
            f"SELECT id FROM member_{interaction.guild_id} "
            f"WHERE boss{self.boss_num} IS NOT NULL AND AFK IS NULL"
        )
        members = list(itertools.chain.from_iterable(members))

        mochi = db.execute(
            f"SELECT id,mochi FROM member_{interaction.guild_id} "
            f"WHERE mochi > 0 AND AFK IS NULL"
        )
        for m in mochi:
            if str(self.boss_num) in [
                str(m[1])[i + 1] for i in range(0, len(str(m[1])), 2)
            ]:
                members.append(m[0])

        if len(members) == 0:
            await interaction.followup.send(
                f"{self.boss_num}ボスのメンバーはいません", ephemeral=True
            )
        elif reservation.contain(interaction.guild_id, self.boss_num):
            await interaction.followup.send(
                view=RecruitAtSameTimeView(interaction.guild, self.boss_num),
                ephemeral=True,
            )
        else:
            members_name = [
                interaction.guild.get_member(m).mention for m in set(members)
            ]
            await interaction.followup.send(
                ephemeral=True,
                view=RecruitConfirmView(self.boss_num, members_name),
            )


class RecruitConfirmView(discord.ui.LayoutView):
    def __init__(self, boss_num, members: list):
        super().__init__(timeout=60)
        self.members = members
        self.boss_num = boss_num
        content = f"# {boss_num}ボス募集\n以下のメンバーにメンションを送ります（{len(members)}人）\n" + "\n".join(
            members
        )
        self.text.content = content

    text = discord.ui.TextDisplay("募集")
    action = discord.ui.ActionRow()

    @action.button(label="メイン募集", style=discord.ButtonStyle.green)
    async def main_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="")
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1293579100056846409)
        else:
            channel = interaction.guild.get_channel(927488075716759562)
        send = await channel.send(
            view=RecruitMessageLayoutView(self.boss_num, self.members)
        )
        await interaction.delete_original_response()
        await forward_message.Forward(channel, self.boss_num - 1)
        raiserhand_counter.Start(send, self.members)
        reservation.set_comp(interaction.guild_id, self.boss_num)

    @action.button(label="サブ募集", style=discord.ButtonStyle.green)
    async def sub_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="")
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1335059739410698344)
        else:
            channel = interaction.guild.get_channel(864795442742427648)
        send = await channel.send(
            view=RecruitMessageLayoutView(self.boss_num, self.members)
        )
        await interaction.delete_original_response()
        await forward_message.Forward(channel, self.boss_num - 1)
        raiserhand_counter.Start(send, self.members)
        reservation.set_comp(interaction.guild_id, self.boss_num)

    @action.button(label="単騎募集", style=discord.ButtonStyle.green)
    async def one_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="")
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1293579743681319023)
        else:
            channel = interaction.guild.get_channel(864795442742427648)
        await channel.send(f"# {self.boss_num}ボス募集\n" + " ".join(self.members))
        await interaction.delete_original_response()

    @action.button(label="取り消し", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(view=self)
        await interaction.delete_original_response()


class RecruitMemberSelectButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="単騎",
            style=discord.ButtonStyle.gray,
            custom_id="Recruitmemberselectbutton",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "単騎募集するメンバーを選択",
            view=RecruitMemberSelectView(interaction.guild),
            ephemeral=True,
        )


class RecruitMemberSelectView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=240)
        self.add_item(RecruitMemberSelect(guild))


class RecruitMemberSelect(discord.ui.Select):
    def __init__(self, guild: discord.Guild):
        # 凸希望にあるメンバー一覧の取得
        members = db.execute(
            f"SELECT id FROM member_{guild.id} WHERE boss1 IS NOT NULL OR boss2 IS NOT NULL OR boss3 IS NOT NULL OR boss4 IS NOT NULL OR boss5 IS NOT NULL"
        )
        mochi = db.execute(
            f"SELECT id,mochi FROM member_{guild.id} WHERE mochi > 0 AND AFK IS NULL"
        )
        for m in mochi:
            members.append(m[0])
        members = set([v[0] if isinstance(v, tuple) else v for v in members])
        options = []
        if len(members) >= 1:
            for i, m in enumerate(members):
                options.append(
                    discord.SelectOption(
                        label=f"{guild.get_member(int(m)).display_name}", value=m
                    )
                )
        max_values = 20
        super().__init__(options=options[:20], max_values=min(max_values, len(options)))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=None)
        await interaction.delete_original_response()
        res = "単騎募集\n"
        for member_id in self.values:
            res += f"<@{member_id}> "
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1293579743681319023)
        else:
            channel = interaction.guild.get_channel(864795442742427648)
        await channel.send(res)


class RecruitAtSameTimeView(discord.ui.LayoutView):
    def __init__(self, guild: discord.Guild, boss):
        self.boss = boss
        self.other = reservation.find_other(guild.id, boss)
        self.member1, self.member2, self.common_sub, common = reservation.get_members(
            guild.id, boss, self.other, True
        )
        super().__init__(timeout=240)
        self.text.content = (
            f"# {boss}ボス募集({len(self.member1)}人)\n{self.other}ボスと同時凸予定"
        )
        self.container_boss1.add_item(
            discord.ui.TextDisplay(
                f"## {boss}ボス（{len(self.member1)}人）\n"
                + " ".join([f"<@{m}>" for m in self.member1])
            )
        )
        self.container_boss2.add_item(
            discord.ui.TextDisplay(
                f"-# {self.other}ボス（{len(self.member2)}人）\n"
                + " ".join([f"<@{m}>" for m in self.member2])
            )
        )
        self.action.children[0].label = f"{boss}ボスのみ募集"
        if reservation.check_comp(guild.id, self.other):
            self.action.remove_item(self.action.children[1])
        if len(self.common_sub) > 0:
            container_common = discord.ui.Container()
            container_common.add_item(
                discord.ui.TextDisplay(
                    f"## 未振り分け\n" + " ".join([f"<@{m}>" for m in self.common_sub])
                )
            )
            self.add_item(discord.ui.Separator())
            self.add_item(container_common)
            boss_list = sorted([boss, self.other])
            self.add_item(
                discord.ui.ActionRow(
                    RecruitAtTheSameTimeDivideButton(
                        boss, boss_list[0], boss_list[1], self.common_sub
                    )
                )
            )

    text = discord.ui.TextDisplay("募集")
    container_boss1 = discord.ui.Container(accent_color=discord.Color.og_blurple())
    container_boss2 = discord.ui.Container(accent_color=discord.Color.brand_green())
    action = discord.ui.ActionRow()

    @action.button(label="募集", style=discord.ButtonStyle.gray, id=1)
    async def bosyu(self, interaction: discord.Interaction, button):
        members_name = [
            interaction.guild.get_member(m).mention
            for m in set(self.member1 + self.common_sub)
        ]
        await interaction.response.edit_message(
            view=RecruitConfirmView(self.boss, members_name)
        )

    @action.button(label="同時凸募集", style=discord.ButtonStyle.green)
    async def doutotsu(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(
            view=RecruitAtSameTimeConfirmView(
                self.boss,
                self.other,
                self.member1 + self.common_sub,
                self.member2 + self.common_sub,
            )
        )


class RecruitAtSameTimeConfirmView(discord.ui.LayoutView):
    def __init__(self, boss1, boss2, members1, members2):
        super().__init__(timeout=180)
        self.boss1 = boss1
        self.boss2 = boss2
        self.members_name1 = [f"<@{m}>" for m in members1]
        self.members_name2 = [f"<@{m}>" for m in members2]
        text1 = discord.ui.TextDisplay(
            f"## {boss1}ボス（{len(self.members_name1)}人）\n"
            + " ".join(self.members_name1)
        )
        text2 = discord.ui.TextDisplay(
            f"## {boss2}ボス（{len(self.members_name2)}人）\n"
            + " ".join(self.members_name2)
        )
        self.container1.add_item(text1)
        self.container2.add_item(text2)
        self.action.children[0].label = f"{boss1}ボスメイン {boss2}ボスサブ"
        self.action.children[1].label = f"{boss1}ボスサブ　 {boss2}ボスメイン"

    container1 = discord.ui.Container(accent_color=discord.Color.og_blurple())
    container2 = discord.ui.Container(accent_color=discord.Color.brand_green())
    action = discord.ui.ActionRow()

    @action.button(label="", style=discord.ButtonStyle.green)
    async def main_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(view=self)
        # メイン送信
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1293579100056846409)
        else:
            channel = interaction.guild.get_channel(1524979826761535498)
        send = await channel.send(
            view=RecruitMessageLayoutView(self.boss1, self.members_name1)
        )
        await interaction.delete_original_response()
        await forward_message.Forward(channel, self.boss1 - 1)
        raiserhand_counter.Start(send, self.members_name1)
        # サブ送信
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1335059739410698344)
        else:
            channel = interaction.guild.get_channel(1524979843194818702)
        send = await channel.send(
            view=RecruitMessageLayoutView(self.boss2, self.members_name2)
        )
        await forward_message.Forward(channel, self.boss2 - 1)
        raiserhand_counter.Start(send, self.members_name2)
        reservation.delete(interaction.guild_id, boss=self.boss1)

    @action.button(label="", style=discord.ButtonStyle.green)
    async def sub_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(view=self)
        # メイン送信
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1293579100056846409)
        else:
            channel = interaction.guild.get_channel(1524979826761535498)
        send = await channel.send(
            view=RecruitMessageLayoutView(self.boss2, self.members_name2)
        )
        await interaction.delete_original_response()
        await forward_message.Forward(channel, self.boss2 - 1)
        raiserhand_counter.Start(send, self.members_name2)
        # サブ送信
        if interaction.guild_id == 1276184060791750656:
            channel = interaction.guild.get_channel(1335059739410698344)
        else:
            channel = interaction.guild.get_channel(1524979843194818702)
        send = await channel.send(
            view=RecruitMessageLayoutView(self.boss1, self.members_name1)
        )
        await forward_message.Forward(channel, self.boss1 - 1)
        raiserhand_counter.Start(send, self.members_name1)
        reservation.delete(interaction.guild_id, boss=self.boss1)


class RecruitAtTheSameTimeDivideButton(discord.ui.Button):
    def __init__(self, select_boss, boss1, boss2, members):
        self.select_boss = select_boss
        self.boss1 = boss1
        self.boss2 = boss2
        self.members = members
        super().__init__(label="振り分け")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=RecruitAtTheSameTimeDivideView(
                interaction.guild,
                self.select_boss,
                self.boss1,
                self.boss2,
                self.members,
            )
        )


class RecruitAtTheSameTimeDivideView(discord.ui.LayoutView):
    def __init__(self, guild: discord.Guild, select_boss, boss1, boss2, members):
        super().__init__(timeout=240)
        self.members = members
        self.boss1 = boss1
        self.boss2 = boss2
        self.select_boss = select_boss
        self.text.content = guild.get_member(members[0]).display_name
        for button in self.action.walk_children():
            if button.id == 1:
                button.label = f"{self.boss1}ボス"
            else:
                button.label = f"{self.boss2}ボス"

    text = discord.ui.TextDisplay("振り分け")
    action = discord.ui.ActionRow()

    @action.button(style=discord.ButtonStyle.blurple, id=1)
    async def boss1_button(self, interaction: discord.Interaction, button):
        reservation.set_members(
            interaction.guild_id, [self.members[0]], [True], self.boss1
        )
        if len(self.members) > 1:
            await interaction.response.edit_message(
                view=RecruitAtTheSameTimeDivideView(
                    interaction.guild,
                    self.select_boss,
                    self.boss1,
                    self.boss2,
                    self.members[1:],
                )
            )
        else:
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.TextDisplay("振り分けが完了しました"))
            await interaction.response.edit_message(view=view)
            await asyncio.sleep(0.5)
            await interaction.edit_original_response(
                view=RecruitAtSameTimeView(interaction.guild, self.select_boss)
            )

    @action.button(style=discord.ButtonStyle.green, id=2)
    async def boss2_button(self, interaction: discord.Interaction, button):
        reservation.set_members(
            interaction.guild_id, [self.members[0]], [True], self.boss2
        )
        if len(self.members) > 1:
            await interaction.response.edit_message(
                view=RecruitAtTheSameTimeDivideView(
                    interaction.guild,
                    self.select_boss,
                    self.boss1,
                    self.boss2,
                    self.members[1:],
                )
            )
        else:
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.TextDisplay("振り分けが完了しました"))
            await interaction.response.edit_message(view=view)
            await asyncio.sleep(0.5)
            await interaction.edit_original_response(
                view=RecruitAtSameTimeView(interaction.guild, self.select_boss)
            )


class RecruitMessageLayoutView(discord.ui.LayoutView):
    def __init__(self, boss, members_list: list):
        super().__init__(timeout=None)
        self.text.content = f"# {boss}ボス募集（{len(members_list)}人）"
        self.notready.children[0].content = " ".join(members_list) + "⠀"

    text = discord.ui.TextDisplay("募集")
    notready = discord.ui.Container(discord.ui.TextDisplay("0人"))
    ready = discord.ui.Container(
        discord.ui.TextDisplay("0人"), accent_color=discord.Color.green()
    )


class ForwardMessageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="転送設定",
            style=discord.ButtonStyle.gray,
            custom_id="forward_message",
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=ForwardMessageSettingView(interaction.guild_id), ephemeral=True
        )


class ForwardMessageSettingView(discord.ui.LayoutView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        for i in range(1, 6):
            self.add_item(ForwardMessageSettingContainer(guild_id, i))
        self.add_item(ForwardMessageSettingAllContainer())


class ForwardMessageSettingContainer(discord.ui.Container):
    text = discord.ui.TextDisplay("ボス")
    messagetext = discord.ui.TextDisplay("転送するメッセージは設定されていません")
    media = discord.ui.MediaGallery()

    def __init__(self, guild_id, boss):
        super().__init__(accent_color=discord.Color.brand_green())
        self.text.content = f"## {boss}ボス\n{forward_message.Get(guild_id,boss-1)}"
        message = forward_message.GetMessage(guild_id, boss - 1)
        if message != None:
            self.messagetext.content = (
                message.content if message.content != "" else " ⠀"
            )
            kw = (".png", ".jpg", ".jpeg", ".gif", ".webp")
            for a in message.attachments:
                if any(k in a.url for k in kw):
                    mg = discord.MediaGalleryItem(a.url)
                    self.media.append_item(mg)
        else:
            self.messagetext.content = "転送するメッセージは設定されていません"
        if len(self.media.items) == 0:
            self.remove_item(self.media)
        self.boss = boss

    actionrow = discord.ui.ActionRow()

    @actionrow.button(label="変更", style=discord.ButtonStyle.green)
    async def change(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(
            ForwardMessageSettingModal(self.boss, interaction.guild_id)
        )
        await interaction.delete_original_response()

    @actionrow.button(label="削除", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(
            view=ForwardMessageDeleteView(self.boss)
        )


class ForwardMessageSettingModal(discord.ui.Modal):
    def __init__(self, boss, guild_id):
        super().__init__(title=f"{boss}ボス", timeout=300)
        self.boss = boss
        self.url.default = forward_message.Get(guild_id, boss - 1)

    url = discord.ui.TextInput(
        label="メッセージURL", placeholder="転送するメッセージのURL", required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        prev = forward_message.Get(interaction.guild_id, self.boss - 1)
        if prev == self.url.value:
            await interaction.response.send_message(
                f"設定は変更されませんでした\n{prev} → {self.url.value}",
                ephemeral=True,
                delete_after=10,
            )
            return
        if self.url.value == "":
            forward_message.Delete(interaction.guild_id, self.boss - 1)
            forward_message.Save()
            await interaction.response.send_message(
                "メッセージの転送設定を取り消しました", ephemeral=True, delete_after=10
            )
            return
        message = await ForwardMessageUtil.MessageFromURL(
            interaction.guild, self.url.value
        )
        if message != None:
            forward_message.Register(message, self.boss - 1)
            forward_message.Save()
            await interaction.response.send_message(
                f"転送するメッセージを変更しました\n{prev} → {self.url.value}",
                ephemeral=True,
                delete_after=10,
            )
        else:
            await interaction.response.send_message(
                f"指定したメッセージの取得に失敗しました\n{self.url.value}",
                ephemeral=True,
                delete_after=10,
            )


class ForwardMessageDeleteView(discord.ui.LayoutView):
    def __init__(self, boss):
        super().__init__(timeout=240)
        self.boss = boss
        self.text.content = f"{boss}ボスの転送設定を削除します"

    text = discord.ui.TextDisplay("ボスの転送設定を削除します")
    row = discord.ui.ActionRow()

    @row.button(label="OK", style=discord.ButtonStyle.red)
    async def ok(self, interaction: discord.Interaction, button):
        forward_message.Delete(interaction.guild_id, self.boss - 1)
        forward_message.Save()
        view = discord.ui.LayoutView()
        view.add_item(
            discord.ui.TextDisplay(f"{self.boss}ボスの転送設定を削除しました")
        )
        await interaction.response.edit_message(view=view, delete_after=10)

    @row.button(label="キャンセル", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button):
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.TextDisplay("キャンセルしました"))
        await interaction.response.edit_message(view=view, delete_after=10)


class ForwardMessageSettingAllContainer(discord.ui.Container):
    def __init__(self):
        super().__init__(accent_color=discord.Color.dark_green())

    action = discord.ui.ActionRow()

    @action.button(label="一括変更", style=discord.ButtonStyle.green)
    async def change(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(
            ForwardMessageSettingAllModal(interaction.guild_id)
        )
        await interaction.delete_original_response()

    @action.button(label="一括削除", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(view=ForwardMessageDeleteAllView())


class ForwardMessageSettingAllModal(discord.ui.Modal):
    def __init__(self, guild_id):
        super().__init__(title="一括変更", timeout=300)

    url = discord.ui.TextInput(
        label="URL", placeholder="転送するメッセージのURL", required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        message = await ForwardMessageUtil.MessageFromURL(
            interaction.guild, self.url.value
        )
        if message != None:
            for i in range(5):
                forward_message.Register(message, i)

        forward_message.Save()
        await interaction.response.send_message(
            f"転送するメッセージを変更しました\n{self.url.value}",
            ephemeral=True,
            delete_after=10,
        )


class ForwardMessageDeleteAllView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=240)

    text = discord.ui.TextDisplay("転送設定を全て削除します")
    row = discord.ui.ActionRow()

    @row.button(label="OK", style=discord.ButtonStyle.red)
    async def ok(self, interaction: discord.Interaction, button):
        for i in range(5):
            forward_message.Delete(interaction.guild_id, i)
        forward_message.Save()
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.TextDisplay(f"転送設定を削除しました"))
        await interaction.response.edit_message(view=view, delete_after=10)

    @row.button(label="キャンセル", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button):
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.TextDisplay("キャンセルしました"))
        await interaction.response.edit_message(view=view, delete_after=10)


class TotsuAtTheSameTimeStartButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="同時凸設定", row=2, custom_id="at_the_same_time")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=TotsuAtTheSameTimeView(interaction.guild), ephemeral=True
        )


class TotsuAtTheSameTimeView(discord.ui.LayoutView):
    def __init__(self, guild):
        combinations, num = reservation.get_conbination(guild.id)
        super().__init__(timeout=240)
        for i in range(num):
            self.add_item(TotsuAtTheSameTimePreviewContainer(guild, combinations[i], i))
        self.add_item(TotsuAtTheSameTimeRegister())


class TotsuAtTheSameTimePreviewContainer(discord.ui.Container):

    text1 = discord.ui.TextDisplay("ボス")
    sep1 = discord.ui.Separator(spacing=discord.SeparatorSpacing.large)
    text2 = discord.ui.TextDisplay("ボス")
    sep2 = discord.ui.Separator(spacing=discord.SeparatorSpacing.large)
    text3 = discord.ui.TextDisplay("未振り分け")
    action = discord.ui.ActionRow()

    def __init__(self, guild: discord.Guild, combination, idx):
        self.idx = idx
        self.boss1 = combination[0]
        self.boss2 = combination[1]
        member1, member2, common_sub, common = reservation.get_members(
            guild.id, self.boss1, self.boss2
        )
        super().__init__(
            accent_color=discord.Color.from_rgb(255, 255, int(255 / self.boss1))
        )
        self.text1.content = f"## {self.boss1}ボス（{len(member1)}人）\n" + " ".join(
            [f"<@{m}>" for m in member1]
        )
        self.text2.content = f"## {self.boss2}ボス（{len(member2)}人）\n" + " ".join(
            [f"<@{m}>" for m in member2]
        )
        self.text3.content = f"未振り分け\n" + " ".join([f"<@{m}>" for m in common_sub])

    @action.button(label="募集", style=discord.ButtonStyle.green)
    async def bosyu_button(self, interaction: discord.Interaction, button):
        members1, members2, common_sub, _ = reservation.get_members(
            interaction.guild_id, self.boss1, self.boss2, True
        )
        await interaction.response.edit_message(
            view=RecruitAtSameTimeConfirmView(
                self.boss1, self.boss2, members1 + common_sub, members2 + common_sub
            )
        )

    @action.button(label="編集", style=discord.ButtonStyle.green)
    async def edit_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(
            view=TotsuAtTheSameTimeSettingView(
                interaction.guild, self.boss1, self.boss2
            )
        )

    @action.button(label="削除", style=discord.ButtonStyle.red)
    async def delete_button(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(
            view=TotsuAtTheSameTimeDeleteView(self.idx)
        )


class TotsuAtTheSameTimeRegister(discord.ui.Container):
    def __init__(self):
        super().__init__()

    action = discord.ui.ActionRow()

    @action.button(label="登録")
    async def register(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(
            view=TotsuAtTheSameTimeSelectBossView(interaction.guild_id)
        )


class TotsuAtTheSameTimeSelectBossView(discord.ui.LayoutView):
    text = discord.ui.TextDisplay("同時凸するボスを選択")
    action = discord.ui.ActionRow()

    def __init__(self, guild_id):
        super().__init__(timeout=240)
        self.selected = []
        for i in range(5):
            self.action.add_item(TotsuAtTheSameTimeSelectBossButton(i + 1))
        self.set_view(guild_id)

    def set_view(self, guild_id):
        button_disable = reservation.button_disabled(guild_id)
        for button in self.action.walk_children():
            button.disabled = button_disable[button.id - 1]
            if button.id in self.selected:
                button.style = discord.ButtonStyle.green
            else:
                button.style = discord.ButtonStyle.gray
        return self

    def button_click(self, button_id):
        if button_id in self.selected:
            self.selected.remove(button_id)
        else:
            self.selected.append(button_id)
            self.selected.sort()
        if len(self.selected) == 2:
            return True
        return False


class TotsuAtTheSameTimeSelectBossButton(discord.ui.Button):
    def __init__(self, boss):
        super().__init__(label=f"{boss}ボス", id=boss)

    async def callback(self, interaction: discord.Interaction):
        if self.view.button_click(self.id):
            boss1 = self.view.selected[0]
            boss2 = self.view.selected[1]
            if reservation.register(interaction.guild_id, boss1, boss2):
                await interaction.response.edit_message(
                    view=TotsuAtTheSameTimeSettingView(interaction.guild, boss1, boss2)
                )
            else:
                self.view.selected = []
                await interaction.response.send_message(
                    f"{boss1}ボス、または{boss2}ボスは既に登録されているか凸するメンバーがいません",
                    ephemeral=True,
                )
        else:
            view = self.view.set_view(interaction.guild_id)
            await interaction.response.edit_message(view=view)


class TotsuAtTheSameTimeSettingView(discord.ui.LayoutView):
    def __init__(self, guild: discord.Guild, boss1, boss2):
        self.boss1 = boss1
        self.boss2 = boss2
        self.guild = guild
        super().__init__(timeout=300)
        member1, member2, common_sub, common = reservation.get_members(
            guild.id, boss1, boss2
        )
        text1 = discord.ui.TextDisplay(
            f"## {boss1}ボス\n" + " ".join([f"<@{m}>" for m in member1])
        )
        text2 = discord.ui.TextDisplay(
            f"## {boss2}ボス\n" + " ".join([f"<@{m}>" for m in member2])
        )
        text3 = discord.ui.TextDisplay(
            f"## 未振り分け\n" + " ".join([f"<@{m}>" for m in common_sub])
        )
        self.container_boss1.add_item(text1)
        self.container_boss2.add_item(text2)
        self.container_common.add_item(text3)
        selected1 = []
        for c in common:
            if c in member1:
                selected1.append(True)
            else:
                selected1.append(False)
        selected2 = []
        for c in common:
            if c in member2:
                selected2.append(True)
            else:
                selected2.append(False)
        common_members = [guild.get_member(c) for c in common]
        select1 = TotsuAtTheSameTimeSettingSelect(common_members, selected1, boss1)
        select2 = TotsuAtTheSameTimeSettingSelect(common_members, selected2, boss2)
        self.container_boss1.add_item(discord.ui.ActionRow(select1))
        self.container_boss2.add_item(discord.ui.ActionRow(select2))
        self.container_common.add_item(
            discord.ui.ActionRow(
                TotsuAtTheSameTimeDivideStartButton(boss1, boss2, common_sub)
            )
        )

    def update(self):
        member1, member2, common_sub, common = reservation.get_members(
            self.guild.id, self.boss1, self.boss2
        )
        self.container_boss1.children[0].content = f"## {self.boss1}ボス\n" + " ".join(
            [f"<@{m}>" for m in member1]
        )
        self.container_boss2.children[0].content = f"## {self.boss2}ボス\n" + " ".join(
            [f"<@{m}>" for m in member2]
        )
        self.container_common.children[0].content = f"## 未振り分け\n" + " ".join(
            [f"<@{m}>" for m in common_sub]
        )
        selected1 = []
        for c in common:
            if c in member1:
                selected1.append(True)
            else:
                selected1.append(False)
        selected2 = []
        for c in common:
            if c in member2:
                selected2.append(True)
            else:
                selected2.append(False)
        common_members = [self.guild.get_member(c) for c in common]
        select1 = TotsuAtTheSameTimeSettingSelect(common_members, selected1, self.boss1)
        select2 = TotsuAtTheSameTimeSettingSelect(common_members, selected2, self.boss2)
        self.container_boss1.remove_item(self.container_boss1.children[1])
        self.container_boss2.remove_item(self.container_boss2.children[1])
        self.container_common.remove_item(self.container_common.children[1])
        self.container_boss1.add_item(discord.ui.ActionRow(select1))
        self.container_boss2.add_item(discord.ui.ActionRow(select2))
        self.container_common.add_item(
            discord.ui.ActionRow(
                TotsuAtTheSameTimeDivideStartButton(self.boss1, self.boss2, common_sub)
            )
        )
        return self

    container_boss1 = discord.ui.Container(accent_color=discord.Color.og_blurple())
    container_boss2 = discord.ui.Container(accent_color=discord.Color.brand_green())
    container_common = discord.ui.Container()


class TotsuAtTheSameTimeSettingSelect(discord.ui.Select):
    def __init__(self, members: list, selected: list, boss):
        options = []
        self.members = members
        self.boss = boss
        for i in range(len(members)):
            so = discord.SelectOption(
                label=f"{members[i].display_name}", default=selected[i], value=str(i)
            )
            options.append(so)
        super().__init__(
            options=options,
            min_values=0,
            max_values=len(options),
            placeholder="凸するメンバーを選択",
        )

    async def callback(self, interaction: discord.Interaction):
        selected = [
            True if str(i) in self.values else False for i in range(len(self.members))
        ]
        reservation.set_members(
            interaction.guild_id, [m.id for m in self.members], selected, self.boss
        )
        view = self.view.update()
        await interaction.response.edit_message(view=view)


class TotsuAtTheSameTimeDivideStartButton(discord.ui.Button):
    def __init__(self, boss1, boss2, members):
        self.boss1 = boss1
        self.boss2 = boss2
        self.members = members
        super().__init__(label="振り分け")

    async def callback(self, interaction: discord.Interaction):
        if len(self.members) == 0:
            await interaction.response.send_message(
                "振り分けるメンバーがいません", ephemeral=True, delete_after=10
            )
        else:
            await interaction.response.edit_message(
                view=TotsuAtTheSameTimeDivideView(
                    interaction.guild, self.boss1, self.boss2, self.members
                )
            )


class TotsuAtTheSameTimeDivideView(discord.ui.LayoutView):
    def __init__(self, guild: discord.Guild, boss1, boss2, members):
        super().__init__(timeout=240)
        self.members = members
        self.boss1 = boss1
        self.boss2 = boss2
        self.text.content = guild.get_member(members[0]).display_name
        for button in self.action.walk_children():
            if button.id == 1:
                button.label = f"{self.boss1}ボス"
            else:
                button.label = f"{self.boss2}ボス"

    text = discord.ui.TextDisplay("振り分け")
    action = discord.ui.ActionRow()

    @action.button(style=discord.ButtonStyle.blurple, id=1)
    async def boss1_button(self, interaction: discord.Interaction, button):
        reservation.set_members(
            interaction.guild_id, [self.members[0]], [True], self.boss1
        )
        if len(self.members) > 1:
            await interaction.response.edit_message(
                view=TotsuAtTheSameTimeDivideView(
                    interaction.guild, self.boss1, self.boss2, self.members[1:]
                )
            )
        else:
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.TextDisplay("振り分けが完了しました"))
            await interaction.response.edit_message(view=view)
            await asyncio.sleep(1)
            await interaction.edit_original_response(
                view=TotsuAtTheSameTimeSettingView(
                    interaction.guild, self.boss1, self.boss2
                )
            )

    @action.button(style=discord.ButtonStyle.green, id=2)
    async def boss2_button(self, interaction: discord.Interaction, button):
        reservation.set_members(
            interaction.guild_id, [self.members[0]], [True], self.boss2
        )
        if len(self.members) > 1:
            await interaction.response.edit_message(
                view=TotsuAtTheSameTimeDivideView(
                    interaction.guild, self.boss1, self.boss2, self.members[1:]
                )
            )
        else:
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.TextDisplay("振り分けが完了しました"))
            await interaction.response.edit_message(view=view)
            await asyncio.sleep(1)
            await interaction.edit_original_response(
                view=TotsuAtTheSameTimeSettingView(
                    interaction.guild, self.boss1, self.boss2
                )
            )


class TotsuAtTheSameTimeDeleteView(discord.ui.LayoutView):
    def __init__(self, idx):
        super().__init__(timeout=180)
        self.idx = idx

    text = discord.ui.TextDisplay("削除しますか?")
    action = discord.ui.ActionRow()

    @action.button(label="削除する", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button):
        reservation.delete(interaction.guild_id, self.idx)
        view = discord.ui.LayoutView(timeout=10)
        view.add_item(discord.ui.TextDisplay("削除しました"))
        await interaction.response.edit_message(view=view, delete_after=10)

    @action.button(label="キャンセル")
    async def cancel(self, interaction: discord.Interaction, button):
        view = discord.ui.LayoutView(timeout=10)
        view.add_item(discord.ui.TextDisplay("キャンセルしました"))
        await interaction.response.edit_message(view=view, delete_after=10)


class Table(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="リアクションリセット", callback=self.member_reset_context
            )
        )
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="3凸完了", callback=self.member_complete_context
            )
        )
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="凸希望編集", callback=self.totsu_change_context
            )
        )

        self.bot.add_view(RecruitMemberView())

        self.guild_img = {}
        self.guild_img2 = {}
        self.afk_members = {}

        self.emj = {}
        self.emj2 = {}

    def CreateTable(self, guild_id: int, restype=0):
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
                name = self.bot.get_guild(guild_id).get_member(_t[0]).display_name
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

    def CreateTable2(self, guild_id: int, restype=0):
        value = [[], [], [], [], [], [], [], [], []]
        routes = db.execute(
            f"SELECT id,boss1,boss2,boss3,boss4,boss5,AFK,mochi,route FROM member_{guild_id} WHERE finish IS NULL"
        )
        routes_num = [
            [v if v != None else 0 for v in m]
            for m in routes
            if (m[1:6] == (None, None, None, None, None) and m[7] == None)
            or m[6] != None
        ]
        members = []

        plt.ioff()

        # メンバーのソート
        for _r in routes_num:
            try:
                name = self.bot.get_guild(guild_id).get_member(_r[0]).display_name
                rep_name = emoji.replace_emoji(name, replace="")
            except:
                continue
            # memberの各ボスに持ち越しを追加
            for i in range(0, len(str(_r[7])), 2):
                addition = (
                    0
                    if _r[7] == 0
                    else (
                        10
                        if str(_r[7])[i] == "1"
                        else 100 if str(_r[7])[i] == "2" else 0
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

    @commands.command()
    async def reactions(self, ctx: commands.Context, arg1=None):
        message = (
            ctx.message
            if ctx.message.reference == None
            else ctx.channel.get_partial_message(ctx.message.reference.message_id)
        )
        if arg1 != None:
            try:
                message = await commands.MessageConverter().convert(ctx, arg1)
            except:
                await ctx.send("メッセージの取得に失敗しました")
                return
        await message.add_reaction("1⃣")
        await message.add_reaction("2⃣")
        await message.add_reaction("3⃣")
        await message.add_reaction("4⃣")
        await message.add_reaction("5⃣")
        await message.add_reaction("🪑")
        db.write_guild(message.guild.id, "reaction_ch", message.channel.id)
        db.write_guild(message.guild.id, "reaction_msg", message.id)

    @commands.Cog.listener("on_raw_reaction_add")
    @DpyDecorator.member_check
    async def reaction_add_table(self, payload: discord.RawReactionActionEvent):
        today = datetime.today()
        next_day = today + timedelta(days=6)
        is_dayfirst = next_day.day == 1
        if (
            payload.emoji.name in ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣"]
            and payload.message_id == db.read_guild("reaction_msg", payload.guild_id)
            and not is_dayfirst
        ):
            db.write_member(
                payload.guild_id,
                payload.user_id,
                "boss" + str(payload.emoji.name.encode("utf-8"))[2],
                1,
            )
            asyncio.create_task(self.img_auto_reaction(payload.guild_id))
            asyncio.create_task(self.img2_auto_reaction(payload.guild_id))
        elif payload.emoji.name == "🪑" and payload.message_id == db.read_guild(
            "reaction_msg", payload.guild_id
        ):
            db.write_member(payload.guild_id, payload.user_id, "AFK", 1)
            asyncio.create_task(self.img_auto_reaction(payload.guild_id))
            asyncio.create_task(self.img2_auto_reaction(payload.guild_id))
            if payload.guild_id not in self.afk_members:
                self.afk_members[payload.guild_id] = {}
            self.afk_members[payload.guild_id][payload.user_id] = int(
                datetime.now().timestamp()
            )
        # 持ち越しよう
        elif payload.emoji.name in ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣"] and (
            payload.message_id == db.read_guild("reaction_mochi_msg", payload.guild_id)
            or (
                payload.message_id == db.read_guild("reaction_msg", payload.guild_id)
                and is_dayfirst
            )
        ):
            mochi = db.read_member(payload.guild_id, "mochi", payload.user_id)
            if mochi == None:
                mochi = 0
            addition = 10 + int(str(payload.emoji.name.encode("utf-8"))[2])
            mochi_list = [
                int(str(mochi)[s : s + 2]) for s in range(0, len(str(mochi)), 2)
            ]
            if addition in mochi_list:
                return
            db.write_member(
                payload.guild_id, payload.user_id, "mochi", mochi * 100 + addition
            )
            asyncio.create_task(self.img_auto_reaction(payload.guild_id))
            asyncio.create_task(self.img2_auto_reaction(payload.guild_id))

    @commands.Cog.listener("on_raw_reaction_add")
    async def reaction_update_table(self, payload: discord.RawReactionActionEvent):
        if payload.emoji.name == "〰" and payload.message_id == db.read_guild(
            "reaction_msg", payload.guild_id
        ):
            message = self.bot.get_channel(payload.channel_id).get_partial_message(
                payload.message_id
            )
            await message.remove_reaction("〰", payload.member)
            asyncio.create_task(self.img_auto_reaction(payload.guild_id))
        if payload.emoji.name == "➖" and payload.message_id == db.read_guild(
            "reaction_msg", payload.guild_id
        ):
            message = self.bot.get_channel(payload.channel_id).get_partial_message(
                payload.message_id
            )
            await message.remove_reaction("➖", payload.member)
            asyncio.create_task(self.img2_auto_reaction(payload.guild_id))

    @commands.Cog.listener("on_raw_reaction_remove")
    @DpyDecorator.member_check
    async def reaction_remove_table(self, payload: discord.RawReactionActionEvent):
        today = datetime.today()
        next_day = today + timedelta(days=6)
        is_dayfirst = next_day.day == 1
        if (
            payload.emoji.name in ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣"]
            and payload.message_id == db.read_guild("reaction_msg", payload.guild_id)
            and not is_dayfirst
        ):
            db.delete_member(
                payload.guild_id,
                payload.user_id,
                "boss" + str(payload.emoji.name.encode("utf-8"))[2],
            )
            asyncio.create_task(self.img_auto_reaction(payload.guild_id))
        elif payload.emoji.name == "🪑" and payload.message_id == db.read_guild(
            "reaction_msg", payload.guild_id
        ):
            db.delete_member(payload.guild_id, payload.user_id, "AFK")
            asyncio.create_task(self.img_auto_reaction(payload.guild_id))
            asyncio.create_task(self.img2_auto_reaction(payload.guild_id))
            if payload.user_id in self.afk_members[payload.guild_id]:
                del self.afk_members[payload.guild_id][payload.user_id]
        # 持ち越しよう
        elif payload.emoji.name in ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣"] and (
            payload.message_id == db.read_guild("reaction_mochi_msg", payload.guild_id)
            or (
                payload.message_id == db.read_guild("reaction_msg", payload.guild_id)
                and is_dayfirst
            )
        ):
            mochi = db.read_member(payload.guild_id, "mochi", payload.user_id)
            if mochi == None:
                return
            addition = 10 + int(str(payload.emoji.name.encode("utf-8"))[2])
            mochi_list = [
                int(str(mochi)[s : s + 2]) for s in range(0, len(str(mochi)), 2)
            ]
            if addition in mochi_list:
                mochi_list.remove(addition)
            db.write_member(
                payload.guild_id,
                payload.user_id,
                "mochi",
                sum(m * (100**i) for i, m in enumerate(reversed(mochi_list))),
            )
            asyncio.create_task(self.img_auto_reaction(payload.guild_id))

    @app_commands.guild_only()
    async def totsu_change_context(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        roles = [
            interaction.guild.get_role(808240600691900417),
            interaction.guild.get_role(1292855894454964336),
            interaction.guild.get_role(1335210159735177297),
        ]
        if db.read_member(member.guild.id, "id", member.id) == None:
            await interaction.response.send_message(
                "メンバーではありません", ephemeral=True
            )
        elif not (
            set(roles) & set(interaction.user.roles) or interaction.user.id == member.id
        ):
            await interaction.response.send_message(
                "自分以外の凸希望は変更できません", ephemeral=True
            )
        else:
            totsu = db.execute(
                f"SELECT boss1,boss2,boss3,boss4,boss5,mochi FROM member_{member.guild.id} WHERE id = {member.id}"
            )[0]
            content = "１列目　本凸\n２列目　フル持ち越し\n３列目　長い持ち越し\n４列目以降　短い持ち越し"
            await interaction.response.send_message(
                content, ephemeral=True, view=TotsuChangeView(member.id, totsu)
            )

    @commands.Cog.listener("on_message")
    async def afk_check(self, message: discord.Message):
        if message.channel.id in [
            1293578758741295207,
            1293579100056846409,
            1335059739410698344,
            1293579743681319023,
            1157527508615430163,
        ]:
            if (
                message.guild != None
                and message.guild.id in self.afk_members
                and message.author.id in self.afk_members[message.guild.id]
            ):
                date = datetime.fromtimestamp(
                    self.afk_members[message.guild.id][message.author.id]
                )
                if (datetime.now() - date).total_seconds() > 60:
                    pmessage = message.guild.get_channel(
                        db.read_guild("reaction_ch", message.guild.id)
                    ).get_partial_message(
                        db.read_guild("reaction_msg", message.guild.id)
                    )
                    await pmessage.remove_reaction("🪑", message.author)

    @commands.Cog.listener("on_message")
    async def raiser_count(self, message: discord.Message):
        counter = raiserhand_counter.Count(message)
        if counter > 0:
            if counter >= 10:
                await message.add_reaction(
                    bytes.fromhex(f"3{int(counter/10)}efb88fe283a3").decode("utf-8")
                )
            await message.add_reaction(
                bytes.fromhex(f"3{counter%10}e283a3").decode("utf-8")
            )

    @commands.command()
    async def img(self, ctx: commands.Context):
        result = self.CreateTable(ctx.guild.id)
        if result != None:
            send = await ctx.send(file=result, view=RecruitMemberView())
            await self.img_auto_set(send.guild.id, send)
        else:
            await ctx.message.add_reaction("🤔")

    @app_commands.command(name="img", description="凸希望表の表示")
    @app_commands.guild_only()
    async def img_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        result = self.CreateTable(interaction.guild_id)
        await interaction.delete_original_response()
        if result != None:
            send = await interaction.channel.send(file=result, view=RecruitMemberView())
            await self.img_auto_set(interaction.guild_id, send)
        else:
            await interaction.channel.send("🤔")

    @app_commands.command(name="simg", description="シークレットな凸希望表の表示")
    @app_commands.guild_only()
    async def simg_slash(self, interaction: discord.Interaction):
        result = self.CreateTable(interaction.guild_id)
        if result != None:
            await interaction.response.send_message(
                file=result, ephemeral=True, view=RecruitMemberView()
            )
        else:
            await interaction.response.send_message("🤔", ephemeral=True)

    async def img_fixed_load(self):
        imgfixed_ids = db.execute(
            "SELECT id,imgfixed_ch,imgfixed_msg FROM guild WHERE imgfixed_ch IS NOT NULL"
        )
        for imgfixed_id in imgfixed_ids:
            try:
                message = await self.bot.get_channel(imgfixed_id[1]).fetch_message(
                    imgfixed_id[2]
                )
                self.guild_img[str(imgfixed_id[0])] = {}
                self.guild_img[str(imgfixed_id[0])]["fixed_message"] = message
                self.guild_img[str(imgfixed_id[0])][
                    "next"
                ] = datetime.now() + timedelta(seconds=5)
                self.guild_img[str(imgfixed_id[0])]["updated"] = True
                ############################################################
                # 通常のほうにも登録
                # await self.img_auto_set(message.guild.id,message)
                ############################################################
                await self.img_auto_reaction(imgfixed_id[0])
            except discord.NotFound:
                db.delete_guild(imgfixed_id[0], "imgfixed_ch")
                db.delete_guild(imgfixed_id[0], "imgfixed_msg")
            except:
                pass
        imgfixed2_ids = db.execute(
            "SELECT id,imgfixed2_ch,imgfixed2_msg FROM guild WHERE imgfixed2_ch IS NOT NULL"
        )
        for imgfixed2_id in imgfixed2_ids:
            try:
                message2 = await self.bot.get_channel(imgfixed2_id[1]).fetch_message(
                    imgfixed2_id[2]
                )
                self.guild_img2[str(imgfixed2_id[0])] = {}
                self.guild_img2[str(imgfixed2_id[0])]["message"] = message2
                self.guild_img2[str(imgfixed2_id[0])][
                    "next"
                ] = datetime.now() + timedelta(seconds=5)
                self.guild_img2[str(imgfixed2_id[0])]["updated"] = True
                await self.img2_auto_reaction(imgfixed2_id[0])
            except discord.NotFound:
                db.delete_guild(imgfixed2_id[0], "imgfixed2_ch")
                db.delete_guild(imgfixed2_id[0], "imgfixed2_msg")
            except:
                pass

    @app_commands.command(description="凸希望表のリセット")
    @app_commands.guild_only()
    async def reaction_reset(
        self, interaction: discord.Interaction, member: discord.Member = None
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            if member == None:
                await self.guild_reset(interaction.guild_id)
                await interaction.edit_original_response(
                    content="リアクションをリセットしました"
                )
            else:
                await self.member_reset(member)
                await interaction.edit_original_response(
                    content=f"{member.display_name}のリアクションをリセットしました"
                )
        except:
            await interaction.delete_original_response()

    @commands.Cog.listener("on_message")
    @DpyDecorator.member_check
    async def on_message_complete(self, message: discord.Message):
        """3凸完了報告"""
        if message.channel.id == db.read_guild("kanryou_ch", message.guild.id):
            if re.search("(凸完|凸終|完凸)", message.content):
                await self.delete_mochikoshi(message.guild.id, message.author.id)
                await self.member_reset(message.author)
                await message.add_reaction("👍")

                # まだ凸完了をしていない場合に何人目の官僚化をカウントする
                if (
                    db.read_member(message.guild.id, "finish", message.author.id)
                    == None
                ):
                    finished = db.read_member(message.guild.id, "finish")
                    db.write_member(
                        message.guild.id, message.author.id, "finish", message.id
                    )
                    if re.search(r"\d+人目", message.content):
                        finish_num = int(
                            re.sub(
                                r"\D",
                                "",
                                re.search(r"\d+人目", message.content).group(),
                            )
                        )
                    else:
                        finish_num = 0
                    if finish_num != len(finished) + 1:
                        await message.add_reaction(
                            bytes.fromhex(f"3{str(len(finished)+1)[0]}e283a3").decode(
                                "utf-8"
                            )
                        )
                        if len(str(len(finished) + 1)) == 2:
                            await message.add_reaction(
                                bytes.fromhex(
                                    f"3{str(len(finished)+1)[1]}efb88fe283a3"
                                ).decode("utf-8")
                            )
                else:
                    db.write_member(
                        message.guild.id, message.author.id, "finish", message.id
                    )
                # asyncio.create_task(self.delete_mochikoshi(message.guild.id,message.author.id))

            elif message.guild.id not in [
                739872778395844650,
                731720074754523148,
                1276184060791750656,
            ] and re.search(r"\d", message.content):
                await self.member_reset(message.author)
                # await message.add_reaction("👍")

                if db.read_member(message.guild.id, "finish", message.author.id) == "":
                    finished = db.read_member(message.guild.id, "finish")
                    db.write_member(
                        message.guild.id, message.author.id, "finish", message.id
                    )
            try:
                totsu_message = message.guild.get_channel(
                    db.read_guild("totsukanri_ch", message.guild.id)
                ).get_partial_message(db.read_guild("totsukanri_msg", message.guild.id))
                await totsu_message.edit(
                    embed=discord.Embed(
                        color=discord.colour.parse_hex_number("ffffff"),
                        title="凸管理",
                        description=Generator.totsu_content(message.guild),
                    ),
                    allowed_mentions=discord.AllowedMentions(users=False),
                )
            except:
                pass

    async def delete_mochikoshi(self, guild_id, member_id):
        def is_member(m: discord.Message):
            nonlocal member_id
            return m.author.id == member_id

        try:
            channel_id = db.read_guild("mochikoshi_ch", guild_id)
            if channel_id != None:
                channel = self.bot.get_guild(guild_id).get_channel(channel_id)
                await channel.purge(limit=100, check=is_member)
            db.delete_member(guild_id, member_id, "mochi")
        except Exception as e:
            print(e)

    @commands.Cog.listener("on_raw_message_delete")
    @DpyDecorator.member_check
    async def on_message_complete_delete(self, payload: discord.RawMessageDeleteEvent):
        """完了報告の削除"""
        if payload.channel_id == db.read_guild("kanryou_ch", payload.guild_id):
            members = db.read_member(payload.guild_id, "finish")
            if members != None:
                try:
                    message_ids = [m[1] for m in members]
                    idx = message_ids.index(payload.message_id)
                    db.delete_member(payload.guild_id, members[idx][0], "finish")
                except ValueError:
                    return

    @app_commands.guild_only()
    async def member_complete_context(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)
        if db.read_member(member.guild.id, "id", member.id) != None:
            if db.read_member(interaction.guild_id, "finish", member.id) == None:
                await self.member_reset(member)
                await self.delete_mochikoshi(member.guild.id, member.id)
                db.write_member(interaction.guild_id, member.id, "finish", 0)
                await interaction.edit_original_response(
                    content=f"{member.display_name}を完了にしました"
                )
            else:
                db.delete_member(interaction.guild_id, member.id, "finish")
                await interaction.edit_original_response(
                    content=f"{member.display_name}を未完了にしました"
                )
            try:
                totsu_message = interaction.guild.get_channel(
                    db.read_guild("totsukanri_ch", interaction.guild_id)
                ).get_partial_message(
                    db.read_guild("totsukanri_msg", interaction.guild_id)
                )
                await totsu_message.edit(
                    embed=discord.Embed(
                        color=discord.colour.parse_hex_number("ffffff"),
                        title="凸管理",
                        description=Generator.totsu_content(interaction.guild_id),
                    ),
                    allowed_mentions=discord.AllowedMentions(users=False),
                )
            except:
                pass
        else:
            await interaction.edit_original_response(
                content=f"{member.display_name}はメンバーではありません"
            )

    @app_commands.guild_only()
    async def member_reset_context(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)
        if db.read_member(member.guild.id, "id", member.id) != None:
            await self.member_reset(member)
            await interaction.edit_original_response(
                content=f"{member.display_name}のリアクションをリセットしました"
            )
        else:
            await interaction.edit_original_response(
                content=f"{member.display_name}はメンバーではありません"
            )

    async def cog_load(self):
        asyncio.create_task(self.reactions_load())
        asyncio.create_task(self.daily())
        asyncio.create_task(forward_message.Load(self.bot))
        self.emj_load()
        reservation.load()

    async def daily(self):
        while True:
            today = datetime.today()
            nexttime = today.replace(hour=5, minute=0, second=0) + timedelta(days=1)
            if today.hour < 5:
                nexttime = today.replace(hour=5, minute=0, second=0)
            await asyncio.sleep((nexttime - today).seconds + 10)
            await self.daily_reaction()
            await self.daily_mochikoshi()
            reservation.file_delete()
            # await self.daily_cb_start_check()

    async def daily_reaction(self):
        guild_ids = db.read_guild("reaction_msg")
        for guild_id in guild_ids:
            await self.guild_reset(guild_id[0])

    async def daily_mochikoshi(self):
        guild_ids = db.read_guild("mochikoshi_ch")
        for guild_id in guild_ids:
            try:
                channel = self.bot.get_guild(guild_id[0]).get_channel(guild_id[1])
                # await channel.purge(limit=100)

                # purgeは監査ログに引っかかるのでhistoryを使用
                async for message in channel.history(limit=100):
                    await message.delete()
            except:
                continue

    async def guild_reset(self, guild_id):
        for member_id in db.read_member(guild_id, "id"):
            db.delete_member(guild_id, member_id[0], "boss1")
            db.delete_member(guild_id, member_id[0], "boss2")
            db.delete_member(guild_id, member_id[0], "boss3")
            db.delete_member(guild_id, member_id[0], "boss4")
            db.delete_member(guild_id, member_id[0], "boss5")
            db.delete_member(guild_id, member_id[0], "AFK")
            db.delete_member(guild_id, member_id[0], "mochi")
            db.delete_member(guild_id, member_id[0], "route")
        try:
            message = (
                self.bot.get_guild(guild_id)
                .get_channel(db.read_guild("reaction_ch", guild_id))
                .get_partial_message(db.read_guild("reaction_msg", guild_id))
            )
            await message.clear_reactions()
            await message.add_reaction("1⃣")
            await message.add_reaction("2⃣")
            await message.add_reaction("3⃣")
            await message.add_reaction("4⃣")
            await message.add_reaction("5⃣")
            await message.add_reaction("🪑")
        except:
            pass

    async def member_reset(self, member: discord.Member):
        db.delete_member(member.guild.id, member.id, "boss1")
        db.delete_member(member.guild.id, member.id, "boss2")
        db.delete_member(member.guild.id, member.id, "boss3")
        db.delete_member(member.guild.id, member.id, "boss4")
        db.delete_member(member.guild.id, member.id, "boss5")
        db.delete_member(member.guild.id, member.id, "AFK")
        reaction_ch = db.read_guild("reaction_ch", member.guild.id)
        reaction_msg = db.read_guild("reaction_msg", member.guild.id)
        try:
            reaction_partial_message = member.guild.get_channel(
                reaction_ch
            ).get_partial_message(reaction_msg)
            await reaction_partial_message.remove_reaction("1⃣", member)
            await reaction_partial_message.remove_reaction("2⃣", member)
            await reaction_partial_message.remove_reaction("3⃣", member)
            await reaction_partial_message.remove_reaction("4⃣", member)
            await reaction_partial_message.remove_reaction("5⃣", member)
            await reaction_partial_message.remove_reaction("🪑", member)
        except:
            pass

    async def daily_cb_start_check(self):
        today = datetime.today()
        next_day = today + timedelta(days=6)
        if next_day.day == 1:
            guild_ids = db.read_guild("reaction_ch")
            for guild_id in guild_ids:
                await self.set_mochi_reaction(guild_id[0])
        else:
            # メッセージの削除
            guild_ids = db.read_guild("reaction_ch,reaction_mochi_msg")
            for guild_id in guild_ids:
                try:
                    if guild_id[2] != None:
                        db.delete_guild(guild_id[0], "reaction_mochi_msg")
                        mochi_message = (
                            self.bot.get_guild(guild_id[0])
                            .get_channel(guild_id[1])
                            .get_partial_message(guild_id[2])
                        )
                        await mochi_message.delete()
                except:
                    pass

    async def set_mochi_reaction(self, guild_id):
        ch_id = db.read_guild("reaction_ch", guild_id)
        msg_id = db.read_guild("reaction_mochi_msg", guild_id)
        guild = self.bot.get_guild(guild_id)
        if ch_id != None:
            if msg_id != None:
                prev = guild.get_channel(ch_id).get_partial_message(msg_id)
                await prev.delete()
            try:
                new_message = await guild.get_channel(ch_id).send("持ち越し")
                db.write_guild(guild_id, "reaction_mochi_msg", new_message.id)
                await new_message.add_reaction("1⃣")
                await new_message.add_reaction("2⃣")
                await new_message.add_reaction("3⃣")
                await new_message.add_reaction("4⃣")
                await new_message.add_reaction("5⃣")
            except:
                pass

    @commands.command(name="emoji")
    async def img_emoji(self, ctx: commands.Context):
        args = ctx.message.content.split()
        if len(args) == 2:
            if emoji.is_emoji(args[1]):
                db.write_guild(ctx.guild.id, "emoji", args[1] + "$")
                self.emj[ctx.guild.id] = args[1] + "$"
                await ctx.channel.send(f"{args[1]}で登録しました")
            if re.match(r"<:.+:\d+>$", args[1]):
                rep = re.sub(r":.+:", ":.+:", args[1])
                db.write_guild(ctx.guild.id, "emoji", rep + "$")
                self.emj[ctx.guild.id] = rep + "$"
                await ctx.channel.send(f"{args[1]}で登録しました")

    @commands.Cog.listener("on_message")
    async def img_emoji_show(self, message: discord.Message):
        if message.author.bot:
            return
        if (
            message.guild.id in self.emj
            and self.emj[message.guild.id] != None
            and re.match(self.emj[message.guild.id], message.content)
        ):
            result = self.CreateTable(message.guild.id)
            if result != None:
                send = await message.channel.send(file=result, view=RecruitMemberView())
                await self.img_auto_set(send.guild.id, send)
            else:
                await message.add_reaction("🤔")
        # emj2
        if (
            message.guild.id in self.emj2
            and self.emj2[message.guild.id] != None
            and re.match(self.emj2[message.guild.id], message.content)
        ):
            result = self.CreateTable2(message.guild.id)
            if result != None:
                send = await message.channel.send(file=result)
                await self.img2_auto_set(send.guild.id, send)
            else:
                await message.add_reaction("🤔")

    async def img_auto_set(self, guild_id, message: discord.Message):
        if str(guild_id) not in self.guild_img:
            self.guild_img[str(guild_id)] = {}
        try:
            old_message: discord.Message = self.guild_img[str(guild_id)]["message"]
            await old_message.edit(content=message.jump_url)
        except:
            pass
        self.guild_img[str(guild_id)]["message"] = message
        self.guild_img[str(guild_id)]["next"] = datetime.now() + timedelta(seconds=5)
        self.guild_img[str(guild_id)]["updated"] = True

        ###################################################################
        # 再起動用に保存
        ###################################################################
        db.write_guild(guild_id, "imgfixed_ch", message.channel.id)
        db.write_guild(guild_id, "imgfixed_msg", message.id)

    async def img_auto_reaction(self, guild_id):
        if str(guild_id) in self.guild_img:
            self.guild_img[str(guild_id)]["updated"] = False
            nexttime: datetime = self.guild_img[str(guild_id)]["next"]
            now = datetime.now()
            if nexttime > now:
                await asyncio.sleep(
                    (nexttime - now).seconds + (nexttime - now).microseconds / 1000000
                )
            if self.guild_img[str(guild_id)]["updated"] == False:
                self.guild_img[str(guild_id)]["next"] = datetime.now() + timedelta(
                    seconds=5
                )
                self.guild_img[str(guild_id)]["updated"] = True
                result = self.CreateTable(guild_id, 1)
                if result != None:
                    if "message" in self.guild_img[str(guild_id)]:
                        try:
                            message: discord.Message = self.guild_img[str(guild_id)][
                                "message"
                            ]
                            buffs = copy.copy(result)
                            attachment = discord.File(filename="table.png", fp=buffs)
                            await message.edit(attachments=[attachment])
                        except:
                            if "fixed_message" in self.guild_img[str(guild_id)]:
                                del self.guild_img[str(guild_id)]["message"]
                            else:
                                del self.guild_img[str(guild_id)]
                    if "fixed_message" in self.guild_img[str(guild_id)]:
                        try:
                            message: discord.Message = self.guild_img[str(guild_id)][
                                "fixed_message"
                            ]
                            attachment = discord.File(filename="table.png", fp=result)
                            await message.edit(attachments=[attachment])
                        except:
                            if "message" in self.guild_img[str(guild_id)]:
                                del self.guild_img[str(guild_id)]["fixed_message"]
                            else:
                                del self.guild_img[str(guild_id)]

    async def reactions_load(self):
        today = datetime.today()
        next_day = today + timedelta(days=6)
        is_dayfirst = next_day.day == 1

        def member_update(member_id, stat, key, mochi, reaction_member_ids):
            if key != "AFK" and is_dayfirst:
                pass
            else:
                if member_id in reaction_member_ids and stat == None:
                    db.write_member(guild_id, member_id, key, 1)
                    return True
                elif member_id not in reaction_member_ids and stat != None:
                    db.delete_member(guild_id, member_id, key)
                    return False
                return None

        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY NAME"
        )
        for table in tables:
            if table[0].startswith("member_"):
                guild_id = int(re.search(r"\d+", table[0]).group())
                message_ids = db.execute(
                    f"SELECT reaction_ch,reaction_msg FROM guild WHERE id = {guild_id}"
                )
                members = db.execute(
                    f"SELECT id,boss1,boss2,boss3,boss4,boss5,AFK,mochi FROM {table[0]}"
                )
                self.afk_members[guild_id] = {
                    v[0]: v[6] for v in filter(lambda x: x[6] != None, members)
                }
                try:
                    message = (
                        await self.bot.get_guild(guild_id)
                        .get_channel(message_ids[0][0])
                        .fetch_message(message_ids[0][1])
                    )
                    for reaction in message.reactions:
                        if reaction.emoji not in ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "🪑"]:
                            continue
                        reaction_member_ids = [
                            user.id async for user in reaction.users()
                        ]
                        for member in members:
                            if reaction.emoji == "1⃣":
                                member_update(
                                    member[0],
                                    member[1],
                                    "boss1",
                                    member[7],
                                    reaction_member_ids,
                                )
                            if reaction.emoji == "2⃣":
                                member_update(
                                    member[0],
                                    member[2],
                                    "boss2",
                                    member[7],
                                    reaction_member_ids,
                                )
                            if reaction.emoji == "3⃣":
                                member_update(
                                    member[0],
                                    member[3],
                                    "boss3",
                                    member[7],
                                    reaction_member_ids,
                                )
                            if reaction.emoji == "4⃣":
                                member_update(
                                    member[0],
                                    member[4],
                                    "boss4",
                                    member[7],
                                    reaction_member_ids,
                                )
                            if reaction.emoji == "5⃣":
                                member_update(
                                    member[0],
                                    member[5],
                                    "boss5",
                                    member[7],
                                    reaction_member_ids,
                                )
                            if reaction.emoji == "🪑":
                                a = member_update(
                                    member[0],
                                    member[6],
                                    "AFK",
                                    member[7],
                                    reaction_member_ids,
                                )
                                if a != None:
                                    if a:
                                        self.afk_members[guild_id][member[0]] = 1
                                    else:
                                        del self.afk_members[guild_id][member[0]]
                except Exception as e:
                    print(e)
                    continue
        await self.img_fixed_load()

    def emj_load(self):
        val = db.execute("SELECT id,emoji,emoji2 FROM guild")
        for v in val:
            if v[1] != None:
                self.emj[v[0]] = v[1]
            if v[2] != None:
                self.emj2[v[0]] = v[2]

    ##############################################################################
    # 未参加リスト
    ##############################################################################
    @commands.command(name="emoji2")
    async def img_emoji(self, ctx: commands.Context):
        args = ctx.message.content.split()
        if len(args) == 2:
            if emoji.is_emoji(args[1]):
                db.write_guild(ctx.guild.id, "emoji2", args[1] + "$")
                self.emj2[ctx.guild.id] = args[1] + "$"
                await ctx.channel.send(f"{args[1]}で登録しました")
            if re.match(r"<:.+:\d+>$", args[1]):
                rep = re.sub(r":.+:", ":.+:", args[1])
                db.write_guild(ctx.guild.id, "emoji2", rep + "$")
                self.emj2[ctx.guild.id] = rep + "$"
                await ctx.channel.send(f"{args[1]}で登録しました")

    async def img2_auto_set(self, guild_id, message: discord.Message):
        if str(guild_id) not in self.guild_img2:
            self.guild_img2[str(guild_id)] = {}
        try:
            old_message: discord.Message = self.guild_img2[str(guild_id)]["message"]
            await old_message.edit(content=message.jump_url)
        except:
            pass
        self.guild_img2[str(guild_id)]["message"] = message
        self.guild_img2[str(guild_id)]["next"] = datetime.now() + timedelta(seconds=5)
        self.guild_img2[str(guild_id)]["updated"] = True

        ###################################################################
        # 再起動用に保存
        ###################################################################
        db.write_guild(guild_id, "imgfixed2_ch", message.channel.id)
        db.write_guild(guild_id, "imgfixed2_msg", message.id)

    async def img2_auto_reaction(self, guild_id):
        if str(guild_id) in self.guild_img2:
            self.guild_img2[str(guild_id)]["updated"] = False
            nexttime: datetime = self.guild_img2[str(guild_id)]["next"]
            now = datetime.now()
            if nexttime > now:
                await asyncio.sleep(
                    (nexttime - now).seconds + (nexttime - now).microseconds / 1000000
                )
            if self.guild_img2[str(guild_id)]["updated"] == False:
                self.guild_img2[str(guild_id)]["next"] = datetime.now() + timedelta(
                    seconds=10
                )
                self.guild_img2[str(guild_id)]["updated"] = True
                result = self.CreateTable2(guild_id, 1)
                if result != None:
                    if "message" in self.guild_img2[str(guild_id)]:
                        try:
                            message: discord.Message = self.guild_img2[str(guild_id)][
                                "message"
                            ]
                            buffs = copy.copy(result)
                            attachment = discord.File(filename="table.png", fp=buffs)
                            await message.edit(attachments=[attachment])
                        except:
                            del self.guild_img2[str(guild_id)]


async def setup(bot: commands.Bot):
    await bot.add_cog(Table(bot))
