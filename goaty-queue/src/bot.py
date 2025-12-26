import os
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler


# Load environment variables
load_dotenv()

# Use environment variable for token security
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("ERROR: Set DISCORD_TOKEN environment variable")


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)

# Queue storage: {guild_id: {"queue": [user_ids], "message_id": int, "channel_id": int, "timer_task": Task, "timer_start": datetime, "is_active": bool, "update_task": Task}}
queues = {}

# Timer duration in seconds (6 minutes = 360 seconds)
TIMER_DURATION = 360

async def update_timer_display(guild_id: int):
    """Background task that updates the queue display every 5 seconds to show countdown"""
    try:
        while True:
            await asyncio.sleep(5)  # Update every 5 seconds
            
            # Check if queue still exists and has people
            if guild_id not in queues or not queues[guild_id]["queue"]:
                continue
            
            # Get guild
            guild = bot.get_guild(guild_id)
            if not guild:
                break
            
            # Update the queue message to show current timer
            await update_queue_message(guild)
    except asyncio.CancelledError:
        pass

async def start_timer(guild_id: int):
    """Start the 6-minute timer for the first person in queue"""
    try:
        # Wait 6 minutes
        await asyncio.sleep(TIMER_DURATION)
        
        # Check if queue still has people
        if guild_id not in queues or not queues[guild_id]["queue"]:
            return
        
        # Remove first person
        removed_user_id = queues[guild_id]["queue"].pop(0)
        
        # Get guild and channel
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        
        channel = guild.get_channel(queues[guild_id]["channel_id"])
        if not channel:
            return
        
        # Notify that time expired (with ping)
        removed_user = guild.get_member(removed_user_id)
        if removed_user:
            await channel.send(f"{removed_user.mention} Your time is up! (6 minutes expired)")
        else:
            await channel.send(f"<@{removed_user_id}> Your time is up! (6 minutes expired)")
        
        # Update queue display
        await update_queue_message(guild)
        
        # Ping next person if queue not empty
        if queues[guild_id]["queue"]:
            next_user_id = queues[guild_id]["queue"][0]
            next_user = guild.get_member(next_user_id)
            
            if next_user:
                await channel.send(f"{next_user.mention} **It's your turn now!**")
            else:
                await channel.send(f"<@{next_user_id}> **It's your turn now!**")
            
            # Start timer for next person
            queues[guild_id]["timer_task"] = asyncio.create_task(start_timer(guild_id))
            queues[guild_id]["timer_start"] = datetime.now()
            
            # Start update task if not already running
            if not queues[guild_id].get("update_task") or queues[guild_id]["update_task"].done():
                queues[guild_id]["update_task"] = asyncio.create_task(update_timer_display(guild_id))
        else:
            # No one left in queue
            queues[guild_id]["timer_task"] = None
            queues[guild_id]["timer_start"] = None
            
            # Stop update task
            if queues[guild_id].get("update_task"):
                queues[guild_id]["update_task"].cancel()
                queues[guild_id]["update_task"] = None
    except asyncio.CancelledError:
        # Timer was cancelled (queue cleared or person manually removed)
        pass

class QueueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
    
    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.green, custom_id="queue_join", row=0)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        if guild_id not in queues:
            queues[guild_id] = {"queue": [], "message_id": None, "channel_id": None, "timer_task": None, "timer_start": None, "is_active": False, "update_task": None}
        
        if user_id in queues[guild_id]["queue"]:
            await interaction.response.send_message("You're already in the queue!", ephemeral=True)
            return
        
        queues[guild_id]["queue"].append(user_id)
        position = len(queues[guild_id]["queue"])
        
        await interaction.response.send_message(f"Joined queue at position **{position}**", ephemeral=True)
        await update_queue_message(interaction.guild)
        
        # Only start timer if queue is active and this is the first person
        if position == 1 and queues[guild_id].get("is_active"):
            # Cancel any existing timer first
            if queues[guild_id].get("timer_task"):
                queues[guild_id]["timer_task"].cancel()
            
            await interaction.channel.send(f"{interaction.user.mention} **It's your turn now!**")
            queues[guild_id]["timer_task"] = asyncio.create_task(start_timer(guild_id))
            queues[guild_id]["timer_start"] = datetime.now()
            
            # Start update task if not already running
            if not queues[guild_id].get("update_task") or queues[guild_id]["update_task"].done():
                queues[guild_id]["update_task"] = asyncio.create_task(update_timer_display(guild_id))
    
    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.red, custom_id="queue_leave", row=0)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        if guild_id not in queues or user_id not in queues[guild_id]["queue"]:
            await interaction.response.send_message("You're not in the queue!", ephemeral=True)
            return
        
        # Check if this user was first in queue
        was_first = queues[guild_id]["queue"][0] == user_id if queues[guild_id]["queue"] else False
        
        queues[guild_id]["queue"].remove(user_id)
        await interaction.response.send_message("Left the queue", ephemeral=True)
        await update_queue_message(interaction.guild)
        
        # If the person who left was first, ping the new first person (only if queue is active)
        if was_first and queues[guild_id]["queue"]:
            # Cancel existing timer
            if queues[guild_id].get("timer_task"):
                queues[guild_id]["timer_task"].cancel()
            
            # Only ping and start timer if queue is active
            if queues[guild_id].get("is_active"):
                next_user_id = queues[guild_id]["queue"][0]
                next_user = interaction.guild.get_member(next_user_id)
                
                channel = interaction.channel
                if next_user:
                    await channel.send(f"{next_user.mention} **It's your turn now!**")
                else:
                    await channel.send(f"<@{next_user_id}> **It's your turn now!**")
                
                # Restart timer for next person
                queues[guild_id]["timer_task"] = asyncio.create_task(start_timer(guild_id))
                queues[guild_id]["timer_start"] = datetime.now()
                
                # Start update task if not already running
                if not queues[guild_id].get("update_task") or queues[guild_id]["update_task"].done():
                    queues[guild_id]["update_task"] = asyncio.create_task(update_timer_display(guild_id))
            else:
                queues[guild_id]["timer_task"] = None
                queues[guild_id]["timer_start"] = None
        elif was_first:
            # Queue is now empty, cancel timer
            if queues[guild_id].get("timer_task"):
                queues[guild_id]["timer_task"].cancel()
            queues[guild_id]["timer_task"] = None
            queues[guild_id]["timer_start"] = None
            
            # Stop update task
            if queues[guild_id].get("update_task"):
                queues[guild_id]["update_task"].cancel()
                queues[guild_id]["update_task"] = None
            queues[guild_id]["timer_start"] = None

async def update_queue_message(guild: discord.Guild):
    """Update the queue embed message"""
    guild_id = guild.id
    
    if guild_id not in queues or not queues[guild_id].get("message_id"):
        return
    
    channel = guild.get_channel(queues[guild_id]["channel_id"])
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(queues[guild_id]["message_id"])
    except:
        return
    
    queue_list = queues[guild_id]["queue"]
    is_active = queues[guild_id].get("is_active", False)
    
    status_text = "ACTIVE" if is_active else "STOPPED"
    
    # Calculate remaining time if timer is active
    timer_text = ""
    if is_active and queue_list and queues[guild_id].get("timer_start"):
        elapsed = (datetime.now() - queues[guild_id]["timer_start"]).total_seconds()
        remaining = max(0, TIMER_DURATION - elapsed)
        
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
    
    embed = discord.Embed(
        title="Queue System",
        description=f"**Status:** {status_text}\n**Total in queue:** {len(queue_list)}{timer_text}",
        timer_text = f"\n**Time per person:** 6 minutes",
        color=discord.Color.green() if is_active else discord.Color.red()
    )
    
    if queue_list:
        queue_text = ""
        for idx, user_id in enumerate(queue_list[:10], 1):  # Show top 10
            user = guild.get_member(user_id)
            
            # Calculate wait time and timer for each person
            wait_info = ""
            if is_active and queues[guild_id].get("timer_start"):
                if idx == 1:
                    # First person - show remaining time
                    elapsed = (datetime.now() - queues[guild_id]["timer_start"]).total_seconds()
                    remaining = max(0, TIMER_DURATION - elapsed)
                    minutes = int(remaining // 60)
                    seconds = int(remaining % 60)
                    wait_info = f" `{minutes}:{seconds:02d} remaining`"
                else:
                    # Other people - show estimated wait time
                    elapsed = (datetime.now() - queues[guild_id]["timer_start"]).total_seconds()
                    current_remaining = max(0, TIMER_DURATION - elapsed)
                    # Each person before them has their full timer duration, except the first person
                    estimated_wait = current_remaining + ((idx - 2) * TIMER_DURATION)
                    wait_minutes = int(estimated_wait // 60)
                    wait_seconds = int(estimated_wait % 60)
                    wait_info = f" `~{wait_minutes}:{wait_seconds:02d} wait`"
            
            if user:
                queue_text += f"**{idx}.** {user.mention}{wait_info}\n"
            else:
                queue_text += f"**{idx}.** <@{user_id}> (left server){wait_info}\n"
        
        embed.add_field(name="Current Queue", value=queue_text, inline=False)
        
        if len(queue_list) > 10:
            embed.add_field(name="", value=f"*...and {len(queue_list) - 10} more*", inline=False)
    else:
        embed.add_field(name="Current Queue", value="*Queue is empty*", inline=False)
    
    await message.edit(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    # Register persistent view
    bot.add_view(QueueView())
    
    # Sync slash commands (globally - takes up to 1 hour)
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s) globally")
        print("NOTE: Global commands can take up to 1 hour to appear in Discord")
        print("For instant testing, use guild-specific sync (see comments in code)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# OPTIONAL: For instant command sync during testing, uncomment this and add your guild ID
# Replace YOUR_GUILD_ID with your server's ID (right-click server icon > Copy Server ID)
# @bot.event
# async def on_ready():
#     print(f"Logged in as {bot.user} (ID: {bot.user.id})")
#     bot.add_view(QueueView())
#     
#     guild = discord.Object(id=YOUR_GUILD_ID)  # Replace with your server ID
#     bot.tree.copy_global_to(guild=guild)
#     synced = await bot.tree.sync(guild=guild)
#     print(f"Synced {len(synced)} command(s) to guild instantly")
#     print("Commands should appear immediately in your server")

@bot.tree.command(name="goaty", description="[ADMIN] Create the queue panel")
@app_commands.checks.has_permissions(administrator=True)
async def setup_queue(interaction: discord.Interaction):
    """Admin command to create the queue panel"""
    guild_id = interaction.guild_id
    
    # If a queue already exists, clean it up first
    if guild_id in queues:
        # Cancel any running timers
        if queues[guild_id].get("timer_task"):
            queues[guild_id]["timer_task"].cancel()
        if queues[guild_id].get("update_task"):
            queues[guild_id]["update_task"].cancel()
        
        # Try to delete the old queue message
        if queues[guild_id].get("message_id") and queues[guild_id].get("channel_id"):
            try:
                channel = interaction.guild.get_channel(queues[guild_id]["channel_id"])
                if channel:
                    old_message = await channel.fetch_message(queues[guild_id]["message_id"])
                    await old_message.delete()
            except:
                pass  # Message might already be deleted
        
        # Clear the old queue data
        queues[guild_id] = {"queue": [], "message_id": None, "channel_id": None, "timer_task": None, "timer_start": None, "is_active": False, "update_task": None}
    
    embed = discord.Embed(
        title="Queue System",
        description="**Total in queue:** 0",
        color=discord.Color.blue()
    )
    embed.add_field(name="Current Queue", value="*Queue is empty*", inline=False)
    
    view = QueueView()
    message = await interaction.channel.send(embed=embed, view=view)
    
    if guild_id not in queues:
        queues[guild_id] = {"queue": [], "message_id": None, "channel_id": None, "timer_task": None, "timer_start": None, "is_active": False, "update_task": None}
    
    queues[guild_id]["message_id"] = message.id
    queues[guild_id]["channel_id"] = interaction.channel_id
    queues[guild_id]["is_active"] = False  # Queue starts inactive
    
    await interaction.response.send_message("Queue panel created! Use `/start_queue` to begin accepting people.", ephemeral=True)

@bot.tree.command(name="start_queue", description="[ADMIN] Start the queue and begin timers")
@app_commands.checks.has_permissions(administrator=True)
async def start_queue_cmd(interaction: discord.Interaction):
    """Admin command to start the queue"""
    guild_id = interaction.guild_id
    
    if guild_id not in queues:
        await interaction.response.send_message("No queue panel exists! Use `/goaty` first.", ephemeral=True)
        return
    
    if queues[guild_id].get("is_active"):
        await interaction.response.send_message("Queue is already active!", ephemeral=True)
        return
    
    queues[guild_id]["is_active"] = True
    
    # If there's someone in queue, ping them and start their timer
    if queues[guild_id]["queue"]:
        first_user_id = queues[guild_id]["queue"][0]
        first_user = interaction.guild.get_member(first_user_id)
        
        if first_user:
            await interaction.channel.send(f"Queue started! {first_user.mention} **It's your turn now!**")
        else:
            await interaction.channel.send(f"Queue started! <@{first_user_id}> **It's your turn now!**")
        
        # Start timer for first person
        queues[guild_id]["timer_task"] = asyncio.create_task(start_timer(guild_id))
        queues[guild_id]["timer_start"] = datetime.now()
        
        # Start update task if not already running
        if not queues[guild_id].get("update_task") or queues[guild_id]["update_task"].done():
            queues[guild_id]["update_task"] = asyncio.create_task(update_timer_display(guild_id))
        
        await interaction.response.send_message("Queue started! Timer begins for first person.", ephemeral=True)
    else:
        await interaction.response.send_message("Queue started! Timer will begin when first person joins.", ephemeral=True)

@bot.tree.command(name="stop_queue", description="[ADMIN] Stop the queue and pause timers")
@app_commands.checks.has_permissions(administrator=True)
async def stop_queue_cmd(interaction: discord.Interaction):
    """Admin command to stop the queue"""
    guild_id = interaction.guild_id
    
    if guild_id not in queues:
        await interaction.response.send_message("No queue panel exists!", ephemeral=True)
        return
    
    if not queues[guild_id].get("is_active"):
        await interaction.response.send_message("Queue is already stopped!", ephemeral=True)
        return
    
    queues[guild_id]["is_active"] = False
    
    # Cancel any running timer
    if queues[guild_id].get("timer_task"):
        queues[guild_id]["timer_task"].cancel()
    queues[guild_id]["timer_task"] = None
    queues[guild_id]["timer_start"] = None
    
    # Stop update task
    if queues[guild_id].get("update_task"):
        queues[guild_id]["update_task"].cancel()
        queues[guild_id]["update_task"] = None
    
    await update_queue_message(interaction.guild)
    await interaction.response.send_message("Queue stopped successfully. No timers will run.", ephemeral=True)

@bot.tree.command(name="clear_queue", description="[ADMIN] Clear the entire queue")
@app_commands.checks.has_permissions(administrator=True)
async def clear_queue(interaction: discord.Interaction):
    """Admin command to clear the queue"""
    guild_id = interaction.guild_id
    
    if guild_id not in queues or not queues[guild_id]["queue"]:
        await interaction.response.send_message("Queue is already empty!", ephemeral=True)
        return
    
    queues[guild_id]["queue"].clear()
    
    # Cancel timer when queue is cleared
    if queues[guild_id].get("timer_task"):
        queues[guild_id]["timer_task"].cancel()
    queues[guild_id]["timer_task"] = None
    queues[guild_id]["timer_start"] = None
    
    # Stop update task
    if queues[guild_id].get("update_task"):
        queues[guild_id]["update_task"].cancel()
        queues[guild_id]["update_task"] = None
    
    await update_queue_message(interaction.guild)
    await interaction.response.send_message("Queue cleared!", ephemeral=True)

@bot.tree.command(name="next", description="[ADMIN] Call the next person in queue")
@app_commands.checks.has_permissions(administrator=True)
async def next_in_queue(interaction: discord.Interaction):
    """Admin command to call next person and ping them"""
    guild_id = interaction.guild_id
    
    if guild_id not in queues or not queues[guild_id]["queue"]:
        await interaction.response.send_message("Queue is empty!", ephemeral=True)
        return
    
    removed_user_id = queues[guild_id]["queue"].pop(0)
    removed_user = interaction.guild.get_member(removed_user_id)
    
    # Notify who was removed (no ping)
    if removed_user:
        await interaction.response.send_message(f"**{removed_user.name}** has been removed from the queue.")
    else:
        await interaction.response.send_message(f"User (ID: {removed_user_id}) has been removed from the queue.")
    
    await update_queue_message(interaction.guild)
    
    # Cancel existing timer
    if queues[guild_id].get("timer_task"):
        queues[guild_id]["timer_task"].cancel()
    
    # Start timer for next person if queue not empty AND queue is active
    if queues[guild_id]["queue"] and queues[guild_id].get("is_active"):
        next_user_id = queues[guild_id]["queue"][0]
        next_user = interaction.guild.get_member(next_user_id)
        
        if next_user:
            await interaction.channel.send(f"{next_user.mention} **It's your turn now!**")
        else:
            await interaction.channel.send(f"<@{next_user_id}> **It's your turn now!**")
        
        queues[guild_id]["timer_task"] = asyncio.create_task(start_timer(guild_id))
        queues[guild_id]["timer_start"] = datetime.now()
        
        # Start update task if not already running
        if not queues[guild_id].get("update_task") or queues[guild_id]["update_task"].done():
            queues[guild_id]["update_task"] = asyncio.create_task(update_timer_display(guild_id))
    else:
        # Queue is empty or inactive, clear timer
        queues[guild_id]["timer_task"] = None
        queues[guild_id]["timer_start"] = None
        
        # Stop update task
        if queues[guild_id].get("update_task"):
            queues[guild_id]["update_task"].cancel()
            queues[guild_id]["update_task"] = None

@bot.tree.command(name="remove", description="[ADMIN] Remove a user from queue")
@app_commands.describe(user="The user to remove from queue")
@app_commands.checks.has_permissions(administrator=True)
async def remove_from_queue(interaction: discord.Interaction, user: discord.Member):
    """Admin command to remove specific user from queue"""
    guild_id = interaction.guild_id
    
    if guild_id not in queues or user.id not in queues[guild_id]["queue"]:
        await interaction.response.send_message(f"{user.mention} is not in the queue!", ephemeral=True)
        return
    
    # Check if this user was first in queue
    was_first = queues[guild_id]["queue"][0] == user.id if queues[guild_id]["queue"] else False
    
    queues[guild_id]["queue"].remove(user.id)
    await update_queue_message(interaction.guild)
    await interaction.response.send_message(f"Removed **{user.name}** from queue", ephemeral=True)
    
    # If the removed person was first, ping the new first person (only if queue is active)
    if was_first:
        # Cancel existing timer
        if queues[guild_id].get("timer_task"):
            queues[guild_id]["timer_task"].cancel()
        
        if queues[guild_id]["queue"] and queues[guild_id].get("is_active"):
            next_user_id = queues[guild_id]["queue"][0]
            next_user = interaction.guild.get_member(next_user_id)
            
            if next_user:
                await interaction.channel.send(f"{next_user.mention} **It's your turn now!**")
            else:
                await interaction.channel.send(f"<@{next_user_id}> **It's your turn now!**")
            
            # Restart timer for next person
            queues[guild_id]["timer_task"] = asyncio.create_task(start_timer(guild_id))
            queues[guild_id]["timer_start"] = datetime.now()
            
            # Start update task if not already running
            if not queues[guild_id].get("update_task") or queues[guild_id]["update_task"].done():
                queues[guild_id]["update_task"] = asyncio.create_task(update_timer_display(guild_id))
        else:
            # Queue is empty or inactive, clear timer
            queues[guild_id]["timer_task"] = None
            queues[guild_id]["timer_start"] = None
            
            # Stop update task
            if queues[guild_id].get("update_task"):
                queues[guild_id]["update_task"].cancel()
                queues[guild_id]["update_task"] = None

@bot.tree.command(name="move", description="[ADMIN] Move a user to a specific position")
@app_commands.describe(user="The user to move", position="New position (1 = front)")
@app_commands.checks.has_permissions(administrator=True)
async def move_in_queue(interaction: discord.Interaction, user: discord.Member, position: int):
    """Admin command to reorder queue"""
    guild_id = interaction.guild_id
    
    if guild_id not in queues or user.id not in queues[guild_id]["queue"]:
        await interaction.response.send_message(f"{user.mention} is not in the queue!", ephemeral=True)
        return
    
    queue = queues[guild_id]["queue"]
    
    if position < 1 or position > len(queue):
        await interaction.response.send_message(f"Position must be between 1 and {len(queue)}", ephemeral=True)
        return
    
    queue.remove(user.id)
    queue.insert(position - 1, user.id)
    
    await update_queue_message(interaction.guild)
    await interaction.response.send_message(f"Moved {user.mention} to position **{position}**", ephemeral=True)
    
    # If the user was moved to position 1 (front), ping them and restart timer (only if queue is active)
    if position == 1 and queues[guild_id].get("is_active"):
        # Cancel existing timer
        if queues[guild_id].get("timer_task"):
            queues[guild_id]["timer_task"].cancel()
        
        await interaction.channel.send(f"{user.mention} **It's your turn now!**")
        queues[guild_id]["timer_task"] = asyncio.create_task(start_timer(guild_id))
        queues[guild_id]["timer_start"] = datetime.now()
        
        # Start update task if not already running
        if not queues[guild_id].get("update_task") or queues[guild_id]["update_task"].done():
            queues[guild_id]["update_task"] = asyncio.create_task(update_timer_display(guild_id))

@bot.tree.command(name="queue_info", description="Check your position in queue")
async def queue_info(interaction: discord.Interaction):
    """Check your position in the queue"""
    guild_id = interaction.guild_id
    user_id = interaction.user.id
    
    if guild_id not in queues or user_id not in queues[guild_id]["queue"]:
        await interaction.response.send_message("You're not in the queue!", ephemeral=True)
        return
    
    position = queues[guild_id]["queue"].index(user_id) + 1
    total = len(queues[guild_id]["queue"])
    
    await interaction.response.send_message(f"You're at position **{position}** out of **{total}**", ephemeral=True)

@bot.tree.command(name="show_queue", description="Show the current queue list")
async def show_queue(interaction: discord.Interaction):
    """Display the current queue with interactive buttons"""
    guild_id = interaction.guild_id
    
    if guild_id not in queues:
        await interaction.response.send_message("No queue exists! Use `/goaty` to create one.", ephemeral=True)
        return
    
    # Get current queue state
    queue_list = queues[guild_id]["queue"]
    is_active = queues[guild_id].get("is_active", False)
    
    status_text = "ACTIVE" if is_active else "STOPPED"
    
    # Calculate remaining time if timer is active
    timer_text = ""
    if is_active and queue_list and queues[guild_id].get("timer_start"):
        elapsed = (datetime.now() - queues[guild_id]["timer_start"]).total_seconds()
        remaining = max(0, TIMER_DURATION - elapsed)
        
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        timer_text = f"\n**Time remaining:** {minutes}:{seconds:02d}"
    
    embed = discord.Embed(
        title="Queue System",
        description=f"**Status:** {status_text}\n**Total in queue:** {len(queue_list)}{timer_text}",
        color=discord.Color.green() if is_active else discord.Color.red()
    )
    
    if queue_list:
        queue_text = ""
        for idx, user_id in enumerate(queue_list[:10], 1):  # Show top 10
            user = interaction.guild.get_member(user_id)
            
            # Calculate wait time and timer for each person
            wait_info = ""
            if is_active and queues[guild_id].get("timer_start"):
                if idx == 1:
                    # First person - show remaining time
                    elapsed = (datetime.now() - queues[guild_id]["timer_start"]).total_seconds()
                    remaining = max(0, TIMER_DURATION - elapsed)
                    minutes = int(remaining // 60)
                    seconds = int(remaining % 60)
                    wait_info = f" - `{minutes}:{seconds:02d} remaining`"
                else:
                    # Other people - show estimated wait time
                    elapsed = (datetime.now() - queues[guild_id]["timer_start"]).total_seconds()
                    current_remaining = max(0, TIMER_DURATION - elapsed)
                    # Each person before them has their full timer duration, except the first person
                    estimated_wait = current_remaining + ((idx - 2) * TIMER_DURATION)
                    wait_minutes = int(estimated_wait // 60)
                    wait_seconds = int(estimated_wait % 60)
                    wait_info = f" - `~{wait_minutes}:{wait_seconds:02d} wait`"
            
            if user:
                queue_text += f"**{idx}.** {user.mention}{wait_info}\n"
            else:
                queue_text += f"**{idx}.** <@{user_id}> (left server){wait_info}\n"
        
        embed.add_field(name="Current Queue", value=queue_text, inline=False)
        
        if len(queue_list) > 10:
            embed.add_field(name="", value=f"*...and {len(queue_list) - 10} more*", inline=False)
    else:
        embed.add_field(name="Current Queue", value="*Queue is empty*", inline=False)
    
    # Create view with interactive buttons
    view = QueueView()
    
    # Send as public message (not ephemeral)
    await interaction.response.send_message(embed=embed, view=view)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')
    
    def log_message(self, format, *args):
        pass  # Suppress logs

def run_health_server():
    port = int(os.getenv('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Health check server running on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    # Start health check server in background thread
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    print(f"Health check server started on port {os.getenv('PORT', 10000)}")
    
    # Give the health server a moment to start
    import time
    time.sleep(2)
    
    # Run the bot
    bot.run(BOT_TOKEN)