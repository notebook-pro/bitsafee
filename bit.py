import discord
from discord import app_commands
import sqlite3
import hashlib

# Bot setup
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# --- Database Setup ---
def setup_database():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            discord_id INTEGER UNIQUE,
            username TEXT UNIQUE,
            password_hash TEXT
        )
    ''')
    # Create data table
    c.execute('''
        CREATE TABLE IF NOT EXISTS data (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            data_key TEXT,
            data_value TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# --- Hashing Utility ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- Bot Events ---
@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    setup_database()
    await tree.sync() # Sync slash commands to Discord
    print("Database is set up and commands are synced.")

# A simple in-memory store for logged-in users
logged_in_users = set()

# --- User Authentication Slash Commands ---
@tree.command(name="register", description="Register a new account.")
async def register(interaction: discord.Interaction, username: str, password: str):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()

    # Check if username or discord id is already registered
    c.execute("SELECT * FROM users WHERE username = ? OR discord_id = ?", (username, interaction.user.id))
    if c.fetchone():
        await interaction.response.send_message("Username or Discord account already registered.", ephemeral=True)
        conn.close()
        return

    password_hash = hash_password(password)
    try:
        c.execute("INSERT INTO users (discord_id, username, password_hash) VALUES (?, ?, ?)",
                  (interaction.user.id, username, password_hash))
        conn.commit()
        await interaction.response.send_message(f"User '{username}' registered successfully!", ephemeral=True)
    except sqlite3.IntegrityError:
        await interaction.response.send_message("An error occurred during registration.", ephemeral=True)
    finally:
        conn.close()

@tree.command(name="login", description="Log in to your account.")
async def login(interaction: discord.Interaction, username: str, password: str):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()

    password_hash = hash_password(password)
    c.execute("SELECT * FROM users WHERE username = ? AND password_hash = ? AND discord_id = ?", (username, password_hash, interaction.user.id))
    user = c.fetchone()
    conn.close()

    if user:
        logged_in_users.add(interaction.user.id)
        await interaction.response.send_message(f"Welcome back, {username}! You are now logged in.", ephemeral=True)
    else:
        await interaction.response.send_message("Invalid username or password.", ephemeral=True)

@tree.command(name="logout", description="Log out of your account.")
async def logout(interaction: discord.Interaction):
    if interaction.user.id in logged_in_users:
        logged_in_users.remove(interaction.user.id)
        await interaction.response.send_message("You have been logged out.", ephemeral=True)
    else:
        await interaction.response.send_message("You are not logged in.", ephemeral=True)

# --- Data Management Slash Commands ---
@tree.command(name="store", description="Store or update a piece of text data.")
async def store(interaction: discord.Interaction, key: str, value: str):
    if interaction.user.id not in logged_in_users:
        await interaction.response.send_message("You must be logged in to store data.", ephemeral=True)
        return

    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE discord_id = ?", (interaction.user.id,))
    user_id = c.fetchone()
    if not user_id:
        await interaction.response.send_message("An error occurred. User not found.", ephemeral=True)
        conn.close()
        return
    user_id = user_id[0]

    c.execute("SELECT * FROM data WHERE user_id = ? AND data_key = ?", (user_id, key))
    if c.fetchone():
        c.execute("UPDATE data SET data_value = ? WHERE user_id = ? AND data_key = ?",
                  (value, user_id, key))
        await interaction.response.send_message(f"Data for key '{key}' updated.", ephemeral=True)
    else:
        c.execute("INSERT INTO data (user_id, data_key, data_value) VALUES (?, ?, ?)",
                  (user_id, key, value))
        await interaction.response.send_message(f"Data stored with key '{key}'.", ephemeral=True)

    conn.commit()
    conn.close()

@tree.command(name="get", description="Retrieve your stored data via Direct Message.")
async def get_data(interaction: discord.Interaction, key: str):
    if interaction.user.id not in logged_in_users:
        await interaction.response.send_message("You must be logged in to retrieve data.", ephemeral=True)
        return

    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE discord_id = ?", (interaction.user.id,))
    user_id = c.fetchone()
    if not user_id:
        await interaction.response.send_message("An error occurred. User not found.", ephemeral=True)
        conn.close()
        return
    user_id = user_id[0]

    c.execute("SELECT data_value FROM data WHERE user_id = ? AND data_key = ?", (user_id, key))
    data = c.fetchone()
    conn.close()

    if data:
        try:
            await interaction.user.send(f"Data for key '{key}': {data[0]}")
            await interaction.response.send_message("Your data has been sent to your DMs.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I couldn't send you a DM. Please check your privacy settings.", ephemeral=True)
    else:
        await interaction.response.send_message(f"No data found for key '{key}'.", ephemeral=True)

# --- Help Command ---
@tree.command(name="storage_help", description="Shows the list of commands for the bot.")
async def storage_help(interaction: discord.Interaction):
    help_text = """
**Data Storage Bot Commands**
`/register <username> <password>` - Register a new account.
`/login <username> <password>` - Log in to your account.
`/logout` - Log out of your account.
`/store <key> <value>` - Store or update a piece of text data.
`/get <key>` - Retrieve your stored data. The bot will send it to your DMs.
    """
    await interaction.response.send_message(help_text, ephemeral=True)


client.run("MTM5MjAzMDY0MTA3OTQ1MTc0OQ.G6nqXm.uiTL6h5dpdYcURPyOO-T5_O8wDrzQe3Uz6IIx8")
