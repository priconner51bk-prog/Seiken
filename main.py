import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()

import os

from util.database import db

from util.path import dir_path

token=os.getenv("DISCORD_TOKEN")
intents=discord.Intents.default()
intents.members=True
intents.message_content=True

isLoaded=False


bot=commands.Bot(command_prefix="/",intents=intents)

@bot.event
async def on_ready():
    global isLoaded
    if not isLoaded:
        for f in os.listdir(dir_path+"/Cogs"):
            if f.endswith(".py"):
                await bot.load_extension("Cogs."+f[:-3])
        #await bot.tree.sync(guild=discord.Object(id=1276184060791750656))
        await bot.tree.sync()
        isLoaded=True
    print("ready")

@bot.event
async def on_command_error(ctx,error):
    pass
bot.run(token)