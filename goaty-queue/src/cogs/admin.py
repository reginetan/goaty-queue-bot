from discord.ext import commands
from discord.utils import get
from utils.queue_manager import QueueManager
from utils.permissions import is_admin

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue_manager = QueueManager()

    @commands.command()
    @is_admin()
    async def move(self, ctx, user: str, position: int):
        """Move a user to a specific position in the queue."""
        success = self.queue_manager.move_user(user, position)
        if success:
            await ctx.send(f"Moved {user} to position {position}.")
        else:
            await ctx.send(f"Failed to move {user}. Please check if they are in the queue.")

    @commands.command()
    @is_admin()
    async def view_queue(self, ctx):
        """View the current queue status."""
        queue = self.queue_manager.get_queue()
        if queue:
            await ctx.send("Current queue: " + ", ".join(queue))
        else:
            await ctx.send("The queue is currently empty.")

def setup(bot):
    bot.add_cog(AdminCog(bot))