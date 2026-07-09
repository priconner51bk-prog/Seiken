import asyncio
from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands

from util.database import db

from unit_data.check_master import CheckMaster
from unit_data.un_hash import Unhash
from unit_data.clanbattle_boss_data import ClanBossData



class Unit(commands.Cog):
    def __init__(self,bot:commands.Bot):
        self.bot=bot

    def cog_load(self):
        asyncio.create_task(self.daily_check_db())

    async def daily_check_db(self):
        while True:
            if CheckMaster.check_update():
                Unhash.run()
            if ClanBossData.check_update():
                enemy_parameters = ClanBossData.get_enemy_id()
                await self.set_dc_name([p[0] for  p in enemy_parameters])
            today=datetime.today()
            delta_hour=3-today.hour%3

            nexttime=today.replace(minute=0,second=0)+timedelta(hours=delta_hour)

            await asyncio.sleep((nexttime-today).seconds+10)
    

    async def set_dc_name(self,enemy_parameters:list):
        dc_data=db.read_guild('dc_ch,dc_msg,dc_name')
        a=enemy_parameters[0][2]/10000
        b=int(enemy_parameters[0][2]/10000)
        for i in range(len(dc_data)):
            try:
                if dc_data[i][1] != None:
                    message_ids=dc_data[i][2].split("\n")
                    names=dc_data[i][3].split("\n")
                    for boss in range(5):
                        name="{0} {1}".format(enemy_parameters[boss][1],int(enemy_parameters[boss][2]/10000))
                        if names[boss] != name:
                            message=await self.bot.get_channel(dc_data[i][1]).fetch_message(message_ids[boss])
                            content=message.content.replace(names[boss],name,1)
                            await message.edit(content=content)
                            await asyncio.sleep(3)
                    db.write_guild(dc_data[i][0],"dc_name","\n".join(["{0} {1}".format(v[1],int(v[2]/10000)) for v in enemy_parameters]))
            except:
                continue

    @app_commands.command(description="データベース取得")
    async def database(self,interaction:discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        filepath="unit_data/unit.db"
        await interaction.edit_original_response(attachments=[discord.File(filepath)])

async def setup(bot:commands.Bot):
    await bot.add_cog(Unit(bot))
