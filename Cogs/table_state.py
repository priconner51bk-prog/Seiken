import asyncio
import itertools
import json
import os
import re
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from util.database import db
from util.debug_util import debug_write
from util.emoji_util import EmojiUtil


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
            or self.messages[channel.guild.id][boss] == None
        ):
            return

        source_message = self.messages[channel.guild.id][boss]
        forwarded_message = await source_message.forward(channel)

        for reaction in source_message.reactions:
            emoji = reaction.emoji
            try:
                if isinstance(emoji, str):
                    print(f"custom emoji string={emoji}")
                    await forwarded_message.add_reaction(emoji)
                else:
                    resolved = EmojiUtil.get(emoji.id)
                    print(f"custom emoji resolved={resolved!r} id={emoji.id}")
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
