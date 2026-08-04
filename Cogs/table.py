import asyncio
import copy
import os
import re
import warnings
from datetime import datetime, timedelta

import discord
import emoji
import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from discord import app_commands
from discord.ext import commands

from util.content_generator import Generator
from util.database import db
from util.decorators import DpyDecorator

from .table_state import forward_message, raiserhand_counter, reservation
from .table_utils import create_table, create_table2
from .table_views import RecruitMemberView, TotsuChangeView

warnings.filterwarnings("ignore", category=UserWarning)

fonts = []
for f in os.listdir("./font"):
    fm.fontManager.addfont(f"font/{f}")
    fonts.append(fm.FontProperties(fname=f"font/{f}").get_name())
plt.rcParams["font.family"] = fonts
matplotlib.use("Agg")


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
        return create_table(self.bot, guild_id, restype)

    def CreateTable2(self, guild_id: int, restype=0):
        return create_table2(self.bot, guild_id, restype)

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
        await interaction.response.defer(ephemeral=True)
        roles = [
            interaction.guild.get_role(808240600691900417),
            interaction.guild.get_role(1292855894454964336),
            interaction.guild.get_role(1335210159735177297),
        ]
        is_member = await asyncio.to_thread(
            db.read_member, member.guild.id, "id", member.id
        )
        if is_member == None:
            await interaction.edit_original_response(content="メンバーではありません")
        elif not (
            set(roles) & set(interaction.user.roles) or interaction.user.id == member.id
        ):
            await interaction.edit_original_response(
                content="自分以外の凸希望は変更できません"
            )
        else:
            totsu = (
                await asyncio.to_thread(
                    db.execute,
                    f"SELECT boss1,boss2,boss3,boss4,boss5,mochi FROM member_{member.guild.id} WHERE id = {member.id}",
                )
            )[0]
            content = "１列目　本凸\n２列目　フル持ち越し\n３列目　長い持ち越し\n４列目以降　短い持ち越し"
            await interaction.edit_original_response(
                content=content, view=TotsuChangeView(member.id, totsu)
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
        result = await asyncio.to_thread(self.CreateTable, interaction.guild_id)
        await interaction.delete_original_response()
        if result != None:
            send = await interaction.channel.send(file=result, view=RecruitMemberView())
            await self.img_auto_set(interaction.guild_id, send)
        else:
            await interaction.channel.send("🤔")

    @app_commands.command(name="simg", description="シークレットな凸希望表の表示")
    @app_commands.guild_only()
    async def simg_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        result = await asyncio.to_thread(self.CreateTable, interaction.guild_id)
        if result != None:
            await interaction.edit_original_response(
                attachments=[result], view=RecruitMemberView()
            )
        else:
            await interaction.edit_original_response(content="🤔")

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
        is_member = await asyncio.to_thread(
            db.read_member, member.guild.id, "id", member.id
        )
        if is_member != None:
            is_finished = await asyncio.to_thread(
                db.read_member, interaction.guild_id, "finish", member.id
            )
            if is_finished == None:
                await self.member_reset(member)
                await self.delete_mochikoshi(member.guild.id, member.id)
                await asyncio.to_thread(
                    db.write_member, interaction.guild_id, member.id, "finish", 0
                )
                await interaction.edit_original_response(
                    content=f"{member.display_name}を完了にしました"
                )
            else:
                await asyncio.to_thread(
                    db.delete_member, interaction.guild_id, member.id, "finish"
                )
                await interaction.edit_original_response(
                    content=f"{member.display_name}を未完了にしました"
                )
            try:
                totsu_kanri_ch = await asyncio.to_thread(
                    db.read_guild, "totsukanri_ch", interaction.guild_id
                )
                totsu_kanri_msg = await asyncio.to_thread(
                    db.read_guild, "totsukanri_msg", interaction.guild_id
                )
                totsu_message = interaction.guild.get_channel(
                    totsu_kanri_ch
                ).get_partial_message(totsu_kanri_msg)
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
        is_member = await asyncio.to_thread(
            db.read_member, member.guild.id, "id", member.id
        )
        if is_member != None:
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Table(bot))
