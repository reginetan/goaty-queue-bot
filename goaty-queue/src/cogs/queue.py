from discord.ext import commands
from utils.queue_manager import QueueManager

class QueueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue_manager = QueueManager()

    @commands.command()
    async def join_queue(self, ctx):
        user = ctx.author
        if self.queue_manager.add_to_queue(user):
            await ctx.send(f"{user.mention} has joined the queue!")
        else:
            await ctx.send(f"{user.mention}, you are already in the queue!")

    @commands.command()
    async def leave_queue(self, ctx):
        user = ctx.author
        if self.queue_manager.remove_from_queue(user):
            await ctx.send(f"{user.mention} has left the queue.")
        else:
            await ctx.send(f"{user.mention}, you are not in the queue!")

    @commands.command()
    async def current_queue(self, ctx):
        queue = self.queue_manager.get_queue()
        if queue:
            queue_list = "\n".join([user.mention for user in queue])
            await ctx.send(f"Current queue:\n{queue_list}")
        else:
            await ctx.send("The queue is currently empty.")

    async def notify_user(self, user):
        await user.send("It's your turn in the queue!")

def setup(bot):
    bot.add_cog(QueueCog(bot))