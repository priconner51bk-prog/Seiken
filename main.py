import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from util.path import dir_path

load_dotenv()

token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

isLoaded = False

bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    global isLoaded

    print("[BOOT] on_ready called")
    print(f"[BOOT] bot user: {bot.user}")
    print(f"[BOOT] cog dir: {dir_path}/Cogs")

    if not isLoaded:
        print("[LOAD] start loading cogs")

        for f in os.listdir(dir_path + "/Cogs"):
            if not f.endswith(".py"):
                continue
            if f == "__init__.py" or f.endswith("_views.py") or f.endswith("_state.py"):
                continue

            ext_name = "Cogs." + f[:-3]
            try:
                await bot.load_extension(ext_name)
                print(f"[OK] loaded: {ext_name}")
            except Exception as e:
                print(f"[NG] failed: {ext_name}")
                print(f"     reason: {type(e).__name__}: {e}")


        print("[LOAD] loaded cogs:", list(bot.cogs.keys()))
        print("[TREE] local commands before sync:", [cmd.name for cmd in bot.tree.get_commands()])

        try:
            # synced = await bot.tree.sync(guild=discord.Object(id=1360448049272328333))
            synced = await bot.tree.sync()
            print(f"[SYNC] synced command count: {len(synced)}")
            print("[SYNC] synced commands:", [cmd.name for cmd in synced])
        except Exception as e:
            print(f"[SYNC ERROR] {type(e).__name__}: {e}")

        isLoaded = True

    print("[READY] ready")


@bot.event
async def on_command_error(ctx, error):
    print(f"[COMMAND ERROR] {type(error).__name__}: {error}")


bot.run(token)
