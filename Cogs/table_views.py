import asyncio
import itertools

import discord
from discord.ext import commands

from util.database import db

from .table_state import (
    ForwardMessageUtil,
    forward_message,
    raiserhand_counter,
    reservation,
)


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
        # 1) 最初にdeferしてDiscordへの応答期限(3秒)を確保する
        #    この後のDB処理がどれだけ遅くても
        #    タイムアウト(応答なし)にならないようにするための対策
        await interaction.response.defer(ephemeral=True)

        # 2) 同期SQLite処理をスレッドに逃がしてイベントループをブロックしない
        members = await asyncio.to_thread(
            db.execute,
            f"SELECT id FROM member_{interaction.guild_id} WHERE boss{self.boss_num} IS NOT NULL AND AFK IS NULL",
        )
        members = list(itertools.chain.from_iterable(members))
        mochi = await asyncio.to_thread(
            db.execute,
            f"SELECT id,mochi FROM member_{interaction.guild_id} WHERE mochi > 0 AND AFK IS NULL",
        )
        for m in mochi:
            if str(self.boss_num) in [
                str(m[1])[i + 1] for i in range(0, len(str(m[1])), 2)
            ]:
                members.append(m[0])
        if len(members) == 0:
            # 3) defer済みなのでresponseではなくfollowupで最終応答を送る
            await interaction.followup.send(
                f"{self.boss_num}ボスのメンバーはいません", ephemeral=True
            )
        else:
            if reservation.contain(interaction.guild_id, self.boss_num):
                await interaction.followup.send(
                    view=RecruitAtSameTimeView(interaction.guild, self.boss_num),
                    ephemeral=True,
                )
            else:
                members_name = [
                    interaction.guild.get_member(m).mention for m in set(members)
                ]
                await interaction.followup.send(
                    ephemeral=True, view=RecruitConfirmView(self.boss_num, members_name)
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
