# Discord Queue Bot

This project is a Discord bot designed for managing queues within a Discord server. It allows users to join and leave a queue, enables admins to manage the queue order, and notifies users when it's their turn.

## Features

- Users can join and leave the queue via interactive buttons
- 6-minute timer system for queue management
- Admins can start/stop the queue and manage queue order
- Users receive notifications when it's their turn
- Persistent queue panel with real-time updates

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/reginetan/goaty-queue-bot.git
   cd discord-queue-bot
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on the `.env.example` template and add your bot token:
   ```
   DISCORD_TOKEN=your_bot_token_here
   ```

## Commands

### Admin Commands (Requires Administrator Permission)

- `/goaty` - Create the queue panel with interactive buttons
- `/start_queue` - Start the queue and begin timers for users
- `/stop_queue` - Stop the queue and pause all timers
- `/clear_queue` - Clear the entire queue
- `/next` - Manually call the next person in queue
- `/remove <user>` - Remove a specific user from the queue
- `/move <user> <position>` - Move a user to a specific position in the queue (1 = front)

### User Commands

- `/queue_info` - Check your current position in the queue
- `/show_queue` - Display the current queue list

### Interactive Buttons

The queue panel includes the following buttons:

- **Join Queue** (Green) - Join the queue at the end
- **Leave Queue** (Red) - Leave the queue
- **Start Queue** (Blue) - [Admin Only] Activate the queue and start timers
- **Stop Queue** (Gray) - [Admin Only] Deactivate the queue and pause timers

## How It Works

1. An admin uses `/goaty` to create the queue panel
2. Users click "Join Queue" to enter the queue
3. Admin uses `/start_queue` to activate the queue
4. The first person is pinged and has 6 minutes
5. After 6 minutes, they're automatically removed and the next person is pinged
6. Users can leave manually using the "Leave Queue" button
7. Admins can manage the queue using admin commands

## Contributing

Feel free to submit issues or pull requests if you have suggestions or improvements for the bot.
