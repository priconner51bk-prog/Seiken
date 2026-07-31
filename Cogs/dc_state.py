import datetime as date
from zoneinfo import ZoneInfo

from util.database import db

time = date.time(hour=5, tzinfo=ZoneInfo("Asia/Tokyo"))

table_reaction = {}
dc_reprint = {}
dc_reprint = {}


class PrevName:
    def __init__(self):
        self.name_list = {}

    def add(self, guild_id, member_id, prev, boss):
        if not guild_id in self.name_list:
            self.name_list[guild_id] = {}
        self.name_list[guild_id][member_id] = (prev, boss)

    def get(self, guild_id, member_id):
        if guild_id in self.name_list and member_id in self.name_list[guild_id]:
            res = self.name_list[guild_id][member_id][0]
            del self.name_list[guild_id][member_id]
            return res
        return None

    def delete(self, guild_id, boss):
        res = []
        if guild_id in self.name_list:
            for member_id in self.name_list[guild_id].copy():
                if self.name_list[guild_id][member_id][1] == boss:
                    res.append((member_id, self.name_list[guild_id][member_id]))
                    del self.name_list[guild_id][member_id]
        return res

    def return_button(self, guild_id, values):
        if not guild_id in self.name_list:
            self.name_list[guild_id] = {}
        for value in values:
            self.name_list[guild_id][value[0]] = value[1]


prev_name = PrevName()
prev_mochi = {}


class PrevMessage:
    def __init__(self):
        self.message_list = {}

    def add(self, guild_id, message_id, boss, No, isfinish):
        if not guild_id in self.message_list:
            self.message_list[guild_id] = {}
        self.message_list[guild_id][message_id] = (boss, No, isfinish)

    def find(self, guild_id, message_id):
        if guild_id in self.message_list and message_id in self.message_list[guild_id]:
            return True
        return False

    def delete(self, guild_id, message_id):
        if guild_id in self.message_list and message_id in self.message_list[guild_id]:
            del self.message_list[guild_id][message_id]

    def delete_boss(self, guild_id, boss):
        res = []
        if guild_id in self.message_list:
            for v in self.message_list[guild_id].copy():
                if self.message_list[guild_id][v][0] == boss:
                    res.append((v, self.message_list[guild_id][v]))
                    del self.message_list[guild_id][v]
        return res

    def return_button(self, guild_id, boss, values):
        if not guild_id in self.message_list:
            self.message_list[guild_id] = {}
        for value in values:
            self.message_list[guild_id][value[0]] = value[1]

    def delete_No(self, guild_id, No):
        if guild_id in self.message_list:
            for v in self.message_list[guild_id]:
                if No in self.message_list[guild_id][v][1]:
                    self.message_list[guild_id][v][1].remove(No)
                    if len(self.message_list[guild_id][v][1]) == 0:
                        del self.message_list[guild_id][v]
                    return v

    def content(self, guild_id, message_id):
        if guild_id in self.message_list and message_id in self.message_list[guild_id]:
            res = "〆　" if self.message_list[guild_id][message_id][2] else "通し\n"
            for No in self.message_list[guild_id][message_id][1]:
                member_id = db.execute(f"SELECT id FROM dc_{guild_id} WHERE No = {No}")[
                    0
                ][0]
                res += f"<@{member_id}>\n"
            return res
        return None


prev_message = PrevMessage()

finish_members = {}


prev_mochi = {}
