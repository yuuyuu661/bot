import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import io
from PIL import Image, ImageDraw, ImageFont
import random
from discord import ui
from keep_alive import keep_alive

keep_alive()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = 1398607685158440991  # 即時反映するサーバーID

user_data_file = "data.json"

def load_data():
    try:
        with open(user_data_file, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(user_data_file, "w") as f:
        json.dump(data, f, indent=2)

user_data = load_data()
chat_cooldown = {}

def xp_for_next_level(level):
    return 100 + 50 * level

def calculate_level(xp):
    level = 0
    while xp >= xp_for_next_level(level):
        xp -= xp_for_next_level(level)
        level += 1
    return level

def get_total_xp_required(level):
    return sum(xp_for_next_level(i) for i in range(level))

def get_xp_progress(xp):
    level = calculate_level(xp)
    current_level_xp = xp - get_total_xp_required(level)
    next_level_xp = xp_for_next_level(level)
    return level, current_level_xp, next_level_xp

level_roles = {
    5: "C",
    10: "C-",
    15: "CC",
    25: "B-",
    35: "B",
    45: "B+",
    55: "BB",
    70: "A-",
    85: "A",
    90: "A+",
    100: "AA",
    125: "S-",
    130: "S",
    140: "S+",
    150: "SS",
    200: "国家権力級"
}

