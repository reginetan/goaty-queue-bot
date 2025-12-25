from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
QUEUE_LIMIT = 10  # Maximum number of users in the queue
ADMIN_ROLE_NAME = "Admin"  # Role name for admin permissions
NOTIFICATION_MESSAGE = "It's your turn in the queue!"  # Message to notify users when it's their turn