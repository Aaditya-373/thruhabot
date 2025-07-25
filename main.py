import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import asyncio
import random
import traceback
import webserver

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

BOT_TOKEN = os.getenv("BOT_TOKEN")

AUDIO_SOURCE_DIR = "./audio"
AUDIO_LIST = os.listdir(AUDIO_SOURCE_DIR)

IMAGES_DIR = "./pictures"
IMAGE_LIST = os.listdir(IMAGES_DIR)


@tasks.loop(minutes=30)
async def join_play_disconnect():
    print("Scheduled task triggered...")

    tasks_list = []
    for guild in bot.guilds:
        tasks_list.append(process_guild(guild))

    results = await asyncio.gather(*tasks_list, return_exceptions=True)

    for guild, result in zip(bot.guilds, results):
        if isinstance(result, Exception):
            print(f"Failed to process {guild.name}: {result}")
            traceback.print_exception(
                type(result), result, result.__traceback__)
        else:
            print(f"Finished processing {guild.name}")


async def safe_connect(channel: discord.VoiceChannel, retries=3, timeout=15):
    for attempt in range(1, retries + 1):
        try:
            if channel.guild.voice_client:
                await channel.guild.voice_client.disconnect(force=True)
            return await channel.connect(timeout=timeout)
        except discord.errors.ConnectionClosed as e:
            if e.code == 4006:
                wait_time = attempt * 5
                print(
                    f"[Attempt {attempt}] WS closed (4006). Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
            else:
                raise
        except Exception as e:
            print(f"[Attempt {attempt}] Unexpected error: {e}")
            await asyncio.sleep(attempt * 5)
    print("Voice connection failed after retries.")
    return None


async def process_guild(guild):
    voice_channels = [c for c in guild.voice_channels if isinstance(
        c, discord.VoiceChannel)]
    active_channel = next(
        (vc for vc in voice_channels if any(not m.bot for m in vc.members)), None)

    if not active_channel:
        print(f"No active VC with users in {guild.name}")
        return

    print(f"Found users in '{active_channel.name}' - Server: {guild.name}")

    user_ids = [
        m.id for m in active_channel.members if not m.bot and m.id != 424901740383567874]
    if not user_ids:
        print(f"No valid users in {active_channel.name}")
        return

    voice = await safe_connect(active_channel)
    if not voice:
        print(f"Skipping {guild.name} due to voice failure.")
        return

    audio_file = random.choice(AUDIO_LIST)
    audio_path = os.path.join(AUDIO_SOURCE_DIR, audio_file)
    if not os.path.isfile(audio_path):
        print(f"Audio file missing: {audio_path}")
        await voice.disconnect()
        return

    print(f"Playing {audio_file} in {active_channel.name}")
    voice.play(discord.FFmpegPCMAudio(audio_path))

    while voice.is_playing():
        await asyncio.sleep(1)

    # member = guild.get_member(random.choice(user_ids))
    # if member and member.voice:
    #     print(f"Kicking {member.display_name} from {active_channel.name}")
    #     await member.move_to(None)
    #     await asyncio.sleep(1)

    await voice.disconnect()
    print(f"Completed action in {guild.name}")


@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    await asyncio.sleep(10)
    # join_play_disconnect.start()


@bot.event
async def on_message(message):
    if bot.user.mentioned_in(message):
        random.shuffle(IMAGE_LIST)
        response = random.choice(IMAGE_LIST)
        image_path = os.path.join(IMAGES_DIR, response)
        if os.path.isfile(image_path):
            await message.channel.send(file=discord.File(image_path))
        else:
            await message.channel.send("Image not found.")

webserver.keep_alive()

bot.run(BOT_TOKEN)
