import discord
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Use environment variable for token security
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("ERROR: Set DISCORD_TOKEN environment variable")


intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print("\n=== YOUR SERVER IDs ===")
    for guild in client.guilds:
        print(f"Server: {guild.name}")
        print(f"ID: {guild.id}")
        print("-" * 40)
    print("\nCopy the ID of your server and use it in bot.py")
    await client.close()

if __name__ == "__main__":
    client.run(BOT_TOKEN)
