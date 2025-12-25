from collections import deque
import discord

class QueueManager:
    def __init__(self):
        self.queue = deque()

    def join_queue(self, user_id):
        if user_id not in self.queue:
            self.queue.append(user_id)
            return True
        return False

    def leave_queue(self, user_id):
        if user_id in self.queue:
            self.queue.remove(user_id)
            return True
        return False

    def get_queue(self):
        return list(self.queue)

    def notify_user(self, user_id):
        # This function should be called to notify the user when it's their turn
        return f"<@{user_id}>, it's your turn!"

    def next_in_queue(self):
        if self.queue:
            return self.queue[0]
        return None

    def remove_next(self):
        if self.queue:
            return self.queue.popleft()
        return None