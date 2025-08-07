import discord
from discord.ext import commands, tasks
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import json
from dotenv import load_dotenv

# Import database models
from src.models.database import db, User, Transaction, Item, Purchase, BotConfig, MinecraftServer, ServerStatus
from src.minecraft_integration import MinecraftIntegration

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.minecraft = MinecraftIntegration()
        self.user_message_timestamps = {}  # Track message timestamps for cooldown
        
    async def setup_hook(self):
        """Called when the bot is starting up"""
        logger.info("Bot is starting up...")
        
        # Start background tasks
        self.update_server_status.start()
        self.process_pending_purchases.start()
        
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        
        # Update bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the Minecraft server | !help"
            )
        )
        
    async def on_message(self, message):
        """Handle incoming messages"""
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Process coin earning
        await self.process_coin_earning(message)
        
        # Process commands
        await self.process_commands(message)
        
    async def process_coin_earning(self, message):
        """Process coin earning from chat messages"""
        try:
            user_id = str(message.author.id)
            current_time = datetime.utcnow()
            
            # Check cooldown
            if user_id in self.user_message_timestamps:
                last_message_time = self.user_message_timestamps[user_id]
                cooldown = await self.get_config_value('message_cooldown', 60)
                
                if (current_time - last_message_time).total_seconds() < int(cooldown):
                    return
                    
            # Update timestamp
            self.user_message_timestamps[user_id] = current_time
            
            # Get or create user
            user = await self.get_or_create_user(message.author)
            
            # Check daily limit
            daily_limit = await self.get_config_value('max_daily_coins', 100)
            coins_today = await self.get_daily_coins_earned(user.id)
            
            if coins_today >= int(daily_limit):
                return
                
            # Award coins
            coins_per_message = await self.get_config_value('coins_per_message', 1)
            coins_to_award = int(coins_per_message)
            
            await self.award_coins(user, coins_to_award, 'Message activity')
            
        except Exception as e:
            logger.error(f"Error processing coin earning: {e}")
            
    async def get_or_create_user(self, discord_user) -> User:
        """Get or create a user in the database"""
        from flask import current_app
        
        with current_app.app_context():
            user = User.query.filter_by(discord_id=str(discord_user.id)).first()
            
            if not user:
                user = User(
                    discord_id=str(discord_user.id),
                    username=discord_user.display_name
                )
                db.session.add(user)
                db.session.commit()
                
            return user
            
    async def award_coins(self, user: User, amount: int, description: str):
        """Award coins to a user"""
        from flask import current_app
        
        with current_app.app_context():
            # Update user coins
            user.coins += amount
            
            # Create transaction record
            transaction = Transaction(
                user_id=user.id,
                transaction_type='earn',
                amount=amount,
                description=description
            )
            
            db.session.add(transaction)
            db.session.commit()
            
    async def get_daily_coins_earned(self, user_id: int) -> int:
        """Get total coins earned today by a user"""
        from flask import current_app
        
        with current_app.app_context():
            today = datetime.utcnow().date()
            
            total = db.session.query(db.func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_type == 'earn',
                db.func.date(Transaction.created_at) == today
            ).scalar()
            
            return int(total) if total else 0
            
    async def get_config_value(self, key: str, default_value):
        """Get a configuration value from the database"""
        from flask import current_app
        
        with current_app.app_context():
            config = BotConfig.query.filter_by(key=key).first()
            return config.value if config else default_value
            
    @tasks.loop(minutes=5)
    async def update_server_status(self):
        """Update Minecraft server status periodically"""
        try:
            from flask import current_app
            
            with current_app.app_context():
                servers = MinecraftServer.query.filter_by(is_active=True).all()
                
                for server in servers:
                    status = await self.minecraft.get_server_status(server.host, server.port)
                    
                    # Save status to database
                    server_status = ServerStatus(
                        server_id=server.id,
                        is_online=status['online'],
                        players_online=status.get('players_online', 0),
                        max_players=status.get('max_players', 0),
                        version=status.get('version', ''),
                        timestamp=datetime.utcnow()
                    )
                    
                    db.session.add(server_status)
                    
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error updating server status: {e}")
            
    @tasks.loop(minutes=1)
    async def process_pending_purchases(self):
        """Process pending purchases"""
        try:
            from flask import current_app
            
            with current_app.app_context():
                pending_purchases = Purchase.query.filter_by(status='pending').all()
                
                for purchase in pending_purchases:
                    try:
                        # Get user and item details
                        user = User.query.get(purchase.user_id)
                        item = Item.query.get(purchase.item_id)
                        
                        if not user or not item:
                            continue
                            
                        # Generate Minecraft command
                        minecraft_command = item.minecraft_command_template.format(
                            username=user.minecraft_uuid or user.username
                        )
                        
                        # Execute command on Minecraft server
                        success = await self.minecraft.execute_command(minecraft_command)
                        
                        if success:
                            purchase.status = 'fulfilled'
                            purchase.fulfilled_at = datetime.utcnow()
                            purchase.minecraft_command = minecraft_command
                            
                            # Notify user
                            discord_user = self.get_user(int(user.discord_id))
                            if discord_user:
                                embed = discord.Embed(
                                    title="Purchase Fulfilled!",
                                    description=f"Your purchase of **{item.name}** has been delivered!",
                                    color=discord.Color.green()
                                )
                                await discord_user.send(embed=embed)
                        else:
                            purchase.status = 'failed'
                            
                    except Exception as e:
                        logger.error(f"Error processing purchase {purchase.id}: {e}")
                        purchase.status = 'failed'
                        
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error processing pending purchases: {e}")

# Bot Commands
@commands.command(name='balance', aliases=['bal', 'coins'])
async def balance(ctx):
    """Check your coin balance"""
    try:
        user = await ctx.bot.get_or_create_user(ctx.author)
        
        embed = discord.Embed(
            title="💰 Your Balance",
            description=f"You have **{user.coins}** coins!",
            color=discord.Color.gold()
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in balance command: {e}")
        await ctx.send("❌ An error occurred while checking your balance.")

@commands.command(name='shop')
async def shop(ctx):
    """View available items in the shop"""
    try:
        from flask import current_app
        
        with current_app.app_context():
            items = Item.query.filter_by(is_active=True).all()
            
            if not items:
                await ctx.send("🛒 The shop is currently empty!")
                return
                
            embed = discord.Embed(
                title="🛒 Shop",
                description="Available items for purchase:",
                color=discord.Color.blue()
            )
            
            for item in items:
                embed.add_field(
                    name=f"{item.name} - {item.price} coins",
                    value=f"{item.description}\nCategory: {item.category}",
                    inline=False
                )
                
            embed.set_footer(text="Use !buy <item_id> to purchase an item")
            await ctx.send(embed=embed)
            
    except Exception as e:
        logger.error(f"Error in shop command: {e}")
        await ctx.send("❌ An error occurred while loading the shop.")

@commands.command(name='buy')
async def buy(ctx, item_id: int, quantity: int = 1):
    """Buy an item from the shop"""
    try:
        from flask import current_app
        
        with current_app.app_context():
            # Get user and item
            user = await ctx.bot.get_or_create_user(ctx.author)
            item = Item.query.get(item_id)
            
            if not item or not item.is_active:
                await ctx.send("❌ Item not found or not available!")
                return
                
            if quantity <= 0:
                await ctx.send("❌ Quantity must be positive!")
                return
                
            total_cost = item.price * quantity
            
            if user.coins < total_cost:
                await ctx.send(f"❌ Insufficient coins! You need {total_cost} coins but have {user.coins}.")
                return
                
            # Deduct coins
            user.coins -= total_cost
            
            # Create purchase record
            purchase = Purchase(
                user_id=user.id,
                item_id=item.id,
                quantity=quantity,
                total_cost=total_cost,
                status='pending'
            )
            
            # Create transaction record
            transaction = Transaction(
                user_id=user.id,
                transaction_type='purchase',
                amount=-total_cost,
                description=f"Purchased {quantity}x {item.name}",
                reference_id=f"purchase_{purchase.id}"
            )
            
            db.session.add(purchase)
            db.session.add(transaction)
            db.session.commit()
            
            embed = discord.Embed(
                title="✅ Purchase Successful!",
                description=f"You purchased **{quantity}x {item.name}** for **{total_cost}** coins!",
                color=discord.Color.green()
            )
            embed.add_field(name="Remaining Balance", value=f"{user.coins} coins", inline=False)
            embed.add_field(name="Status", value="Your purchase is being processed...", inline=False)
            
            await ctx.send(embed=embed)
            
    except Exception as e:
        logger.error(f"Error in buy command: {e}")
        await ctx.send("❌ An error occurred while processing your purchase.")

@commands.command(name='status', aliases=['server'])
async def server_status(ctx):
    """Check Minecraft server status"""
    try:
        from flask import current_app
        
        with current_app.app_context():
            servers = MinecraftServer.query.filter_by(is_active=True).all()
            
            if not servers:
                await ctx.send("❌ No servers configured!")
                return
                
            embed = discord.Embed(
                title="🖥️ Server Status",
                color=discord.Color.blue()
            )
            
            for server in servers:
                # Get latest status
                latest_status = ServerStatus.query.filter_by(server_id=server.id).order_by(ServerStatus.timestamp.desc()).first()
                
                if latest_status:
                    status_text = "🟢 Online" if latest_status.is_online else "🔴 Offline"
                    players_text = f"{latest_status.players_online}/{latest_status.max_players}" if latest_status.is_online else "N/A"
                    version_text = latest_status.version or "Unknown"
                    
                    embed.add_field(
                        name=f"{server.name}",
                        value=f"Status: {status_text}\nPlayers: {players_text}\nVersion: {version_text}\nAddress: {server.host}:{server.port}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name=f"{server.name}",
                        value=f"Status: ❓ Unknown\nAddress: {server.host}:{server.port}",
                        inline=False
                    )
                    
            await ctx.send(embed=embed)
            
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await ctx.send("❌ An error occurred while checking server status.")

@commands.command(name='help')
async def help_command(ctx):
    """Show help information"""
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Here are all available commands:",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="💰 Economy Commands",
        value="`!balance` - Check your coin balance\n`!shop` - View available items\n`!buy <item_id> [quantity]` - Purchase an item",
        inline=False
    )
    
    embed.add_field(
        name="🖥️ Server Commands",
        value="`!status` - Check Minecraft server status",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Information",
        value="You earn coins by chatting in the server!\nUse your coins to buy items and ranks in Minecraft.",
        inline=False
    )
    
    await ctx.send(embed=embed)

# Add commands to bot
def setup_commands(bot):
    bot.add_command(balance)
    bot.add_command(shop)
    bot.add_command(buy)
    bot.add_command(server_status)
    bot.add_command(help_command)

# Create bot instance
def create_bot():
    bot = DiscordBot()
    setup_commands(bot)
    return bot

# Run bot
def run_bot():
    bot = create_bot()
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables!")
        return
        
    bot.run(token)

