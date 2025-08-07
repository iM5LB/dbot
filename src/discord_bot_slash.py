import discord
from discord.ext import commands, tasks
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import json
from src.discord_gift_commands import GiftCommands

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscordBotSlash(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix='!',  # Keep prefix for legacy commands
            intents=intents,
            help_command=None
        )
        
        self.app = None  # Flask app context will be set later
        
    def set_flask_app(self, app):
        """Set Flask app context for database operations"""
        self.app = app
        
    async def setup_hook(self):
        """Called when the bot is starting up"""
        logger.info("Bot is starting up...")
        
        # Load gift commands as a cog
        try:
            await self.add_cog(GiftCommands(self))
            logger.info("Loaded GiftCommands cog")
        except Exception as e:
            logger.error(f"Failed to load GiftCommands cog: {e}")
        
        # Start background tasks
        self.update_server_status.start()
        self.process_pending_purchases.start()
        
        # Slash commands are automatically loaded in py-cord
        logger.info("Slash commands loaded")
    
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="the server economy 💰"
        )
        await self.change_presence(activity=activity)
    
    async def on_message(self, message):
        """Handle message events for coin earning"""
        if message.author.bot:
            return
            
        # Process coin earning
        await self.process_coin_earning(message)
        
        # Process commands
        await self.process_commands(message)
    
    async def process_coin_earning(self, message):
        """Process coin earning from messages"""
        if not self.app:
            return
            
        try:
            with self.app.app_context():
                from src.models.database import db, User, Transaction, BotConfig
                
                # Get user
                user = User.query.filter_by(discord_id=str(message.author.id)).first()
                if not user:
                    # Create new user
                    user = User(
                        discord_id=str(message.author.id),
                        username=message.author.display_name
                    )
                    db.session.add(user)
                    db.session.commit()
                
                # Check cooldown and daily limits
                config = {}
                try:
                    coins_config = BotConfig.query.filter_by(key='coins_per_message').first()
                    config['coins_per_message'] = int(coins_config.value) if coins_config else 1
                    
                    cooldown_config = BotConfig.query.filter_by(key='message_cooldown').first()
                    config['message_cooldown'] = int(cooldown_config.value) if cooldown_config else 60
                    
                    daily_config = BotConfig.query.filter_by(key='max_daily_coins').first()
                    config['max_daily_coins'] = int(daily_config.value) if daily_config else 100
                except Exception as e:
                    logger.error(f"Error loading bot config: {e}")
                    config = {
                        'coins_per_message': 1,
                        'message_cooldown': 60,
                        'max_daily_coins': 100
                    }
                
                # Check last earning time
                last_transaction = Transaction.query.filter_by(
                    user_id=user.id,
                    transaction_type='earn'
                ).order_by(Transaction.created_at.desc()).first()
                
                if last_transaction:
                    time_diff = datetime.utcnow() - last_transaction.created_at
                    if time_diff.total_seconds() < config['message_cooldown']:
                        return
                
                # Check daily limit
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                today_earnings = db.session.query(db.func.sum(Transaction.amount)).filter(
                    Transaction.user_id == user.id,
                    Transaction.transaction_type == 'earn',
                    Transaction.created_at >= today_start
                ).scalar() or 0
                
                if today_earnings >= config['max_daily_coins']:
                    return
                
                # Award coins
                coins_to_award = min(config['coins_per_message'], config['max_daily_coins'] - today_earnings)
                
                user.coins += coins_to_award
                
                transaction = Transaction(
                    user_id=user.id,
                    transaction_type='earn',
                    amount=coins_to_award,
                    description=f'Earned from message in #{message.channel.name}'
                )
                
                db.session.add(transaction)
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error processing coin earning: {e}")
    
    @tasks.loop(minutes=5)
    async def update_server_status(self):
        """Update Minecraft server status"""
        if not self.app:
            return
            
        try:
            with self.app.app_context():
                from src.minecraft_integration import MinecraftIntegration
                
                integration = MinecraftIntegration()
                await integration.update_all_server_status()
                
        except Exception as e:
            logger.error(f"Error updating server status: {e}")
    
    @tasks.loop(seconds=30)
    async def process_pending_purchases(self):
        """Process pending purchases"""
        if not self.app:
            return
            
        try:
            with self.app.app_context():
                from src.models.database import db, Purchase, Item, User
                
                pending_purchases = Purchase.query.filter_by(status='pending').all()
                
                for purchase in pending_purchases:
                    try:
                        purchase.status = 'processing'
                        db.session.commit()
                        
                        item = Item.query.get(purchase.item_id)
                        user = User.query.get(purchase.user_id)
                        
                        if not item or not user:
                            purchase.status = 'failed'
                            db.session.commit()
                            continue
                        
                        success = await self.fulfill_purchase(purchase, item, user)
                        
                        if success:
                            purchase.status = 'fulfilled'
                            purchase.fulfilled_at = datetime.utcnow()
                        else:
                            purchase.status = 'failed'
                        
                        db.session.commit()
                        
                    except Exception as e:
                        logger.error(f"Error processing purchase {purchase.id}: {e}")
                        purchase.status = 'failed'
                        db.session.commit()
                        
        except Exception as e:
            logger.error(f"Error processing pending purchases: {e}")
    
    async def fulfill_purchase(self, purchase, item, user):
        """Fulfill a purchase by executing Discord and/or Minecraft actions"""
        success = True
        
        try:
            # Handle Discord role assignment
            if item.item_type in ['discord', 'both'] and item.discord_role_id:
                discord_success = await self.assign_discord_role(user, item.discord_role_id)
                if discord_success:
                    purchase.discord_role_assigned = True
                else:
                    success = False
            
            # Handle Minecraft command execution
            if item.item_type in ['minecraft', 'both'] and item.minecraft_command_template:
                minecraft_success = await self.execute_minecraft_command(user, item, purchase)
                if not minecraft_success:
                    success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error fulfilling purchase: {e}")
            return False
    
    async def assign_discord_role(self, user, role_id):
        """Assign a Discord role to a user"""
        try:
            # Find the user in all guilds
            for guild in self.guilds:
                member = guild.get_member(int(user.discord_id))
                if member:
                    role = guild.get_role(int(role_id))
                    if role:
                        await member.add_roles(role, reason="Purchase fulfillment")
                        logger.info(f"Assigned role {role.name} to {member.display_name}")
                        return True
            
            logger.warning(f"Could not find user {user.discord_id} or role {role_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error assigning Discord role: {e}")
            return False
    
    async def execute_minecraft_command(self, user, item, purchase):
        """Execute Minecraft command via RCON"""
        try:
            from src.minecraft_integration import MinecraftIntegration
            
            integration = MinecraftIntegration()
            
            # Replace placeholders in command template
            command = item.minecraft_command_template.replace('{username}', user.username)
            command = command.replace('{discord_id}', user.discord_id)
            command = command.replace('{minecraft_uuid}', user.minecraft_uuid or user.username)
            
            success = await integration.execute_command(command)
            
            if success:
                purchase.minecraft_command = command
                logger.info(f"Executed Minecraft command for purchase {purchase.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing Minecraft command: {e}")
            return False

    # Slash Commands
    @discord.slash_command(name="balance", description="Check your coin balance")
    async def balance_command(self, ctx):
        """Check user's coin balance"""
        if not self.app:
            await ctx.respond("❌ Bot is not properly configured.", ephemeral=True)
            return
        
        try:
            with self.app.app_context():
                from src.models.database import User
                
                user = User.query.filter_by(discord_id=str(ctx.author.id)).first()
                
                if not user:
                    await ctx.respond(
                        "💰 You don't have an account yet! Send a message to create one.",
                        ephemeral=True
                    )
                    return
                
                embed = discord.Embed(
                    title="💰 Your Balance",
                    description=f"You have **{user.coins:,}** coins",
                    color=discord.Color.gold()
                )
                embed.set_footer(text=f"User ID: {user.id}")
                
                await ctx.respond(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in balance command: {e}")
            await ctx.respond("❌ An error occurred.", ephemeral=True)

@bot.tree.command(name="shop", description="Browse the interactive item shop")
async def shop_command(interaction: discord.Interaction, category: Optional[str] = None):
    """Browse the interactive item shop"""
    if not bot.app:
        await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
        return
    
    try:
        with bot.app.app_context():
            from src.models.database import Item
            from src.discord_shop_ui import ShopView
            
            query = Item.query.filter_by(is_available=True)
            if category:
                query = query.filter_by(category=category)
            
            items = query.order_by(Item.price).all()
            
            if not items:
                await interaction.response.send_message("🛒 No items available in the shop.", ephemeral=True)
                return
            
            # Create interactive shop view
            view = ShopView(bot, items, interaction.user.id, category)
            embed = view.create_embed()
            
            await interaction.response.send_message(embed=embed, view=view)
            
    except Exception as e:
        logger.error(f"Error in shop command: {e}")
        await interaction.response.send_message("❌ An error occurred.", ephemeral=True)

@bot.tree.command(name="item", description="View detailed information about an item")
async def item_command(interaction: discord.Interaction, item_id: int):
    """View detailed information about an item"""
    if not bot.app:
        await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
        return
    
    try:
        with bot.app.app_context():
            from src.models.database import Item
            from src.discord_shop_ui import ItemDetailView
            
            item = Item.query.filter_by(id=item_id, is_available=True).first()
            
            if not item:
                await interaction.response.send_message("❌ Item not found or not available.", ephemeral=True)
                return
            
            # Create detailed item view
            view = ItemDetailView(bot, item, interaction.user.id)
            embed = view.create_embed()
            
            await interaction.response.send_message(embed=embed, view=view)
            
    except Exception as e:
        logger.error(f"Error in item command: {e}")
        await interaction.response.send_message("❌ An error occurred.", ephemeral=True)

@bot.tree.command(name="buy", description="Purchase an item from the shop")
async def buy_command(interaction: discord.Interaction, item_id: int, quantity: Optional[int] = 1):
    """Purchase an item from the shop"""
    if not bot.app:
        await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
        return
    
    if quantity <= 0:
        await interaction.response.send_message("❌ Quantity must be positive.", ephemeral=True)
        return
    
    try:
        with bot.app.app_context():
            from src.models.database import db, User, Item, Purchase, Transaction
            
            # Get user
            user = User.query.filter_by(discord_id=str(interaction.user.id)).first()
            if not user:
                await interaction.response.send_message(
                    "❌ You don't have an account yet! Send a message to create one.",
                    ephemeral=True
                )
                return
            
            # Get item
            item = Item.query.filter_by(id=item_id, is_available=True).first()
            if not item:
                await interaction.response.send_message("❌ Item not found or not available.", ephemeral=True)
                return
            
            # Calculate total cost
            total_cost = item.price * quantity
            
            # Check if user has enough coins
            if user.coins < total_cost:
                await interaction.response.send_message(
                    f"❌ Insufficient coins! You need **{total_cost:,}** coins but only have **{user.coins:,}**.",
                    ephemeral=True
                )
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
                description=f'Purchased {quantity}x {item.name}',
                reference_id=f'purchase_{purchase.id}'
            )
            
            db.session.add(purchase)
            db.session.add(transaction)
            db.session.commit()
            
            embed = discord.Embed(
                title="✅ Purchase Successful",
                description=f"You purchased **{quantity}x {item.name}** for **{total_cost:,}** coins",
                color=discord.Color.green()
            )
            embed.add_field(name="Remaining Balance", value=f"{user.coins:,} coins", inline=True)
            embed.add_field(name="Status", value="Processing...", inline=True)
            embed.set_footer(text=f"Purchase ID: {purchase.id}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
    except Exception as e:
        logger.error(f"Error in buy command: {e}")
        await interaction.response.send_message("❌ An error occurred during purchase.", ephemeral=True)

@bot.tree.command(name="status", description="Check Minecraft server status")
async def status_command(interaction: discord.Interaction):
    """Check Minecraft server status"""
    if not bot.app:
        await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
        return
    
    try:
        with bot.app.app_context():
            from src.models.database import MinecraftServer, ServerStatus
            
            servers = MinecraftServer.query.filter_by(is_active=True).all()
            
            if not servers:
                await interaction.response.send_message("❌ No servers configured.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🖥️ Server Status",
                color=discord.Color.blue()
            )
            
            for server in servers:
                latest_status = ServerStatus.query.filter_by(server_id=server.id).order_by(
                    ServerStatus.timestamp.desc()
                ).first()
                
                if latest_status:
                    status_emoji = "🟢" if latest_status.is_online else "🔴"
                    players_text = f"{latest_status.players_online}/{latest_status.max_players}" if latest_status.is_online else "N/A"
                    version_text = latest_status.version or "Unknown"
                    
                    embed.add_field(
                        name=f"{status_emoji} {server.name}",
                        value=f"**Players:** {players_text}\n**Version:** {version_text}\n**Address:** {server.host}:{server.port}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name=f"❓ {server.name}",
                        value=f"**Status:** Unknown\n**Address:** {server.host}:{server.port}",
                        inline=True
                    )
            
            await interaction.response.send_message(embed=embed)
            
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await interaction.response.send_message("❌ An error occurred.", ephemeral=True)

@bot.tree.command(name="gift", description="Send coins to another user")
async def gift_command(interaction: discord.Interaction, recipient: discord.Member, amount: int, message: Optional[str] = None):
    """Send coins to another user"""
    if not bot.app:
        await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
        return
    
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return
    
    if recipient.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot send coins to yourself.", ephemeral=True)
        return
    
    if recipient.bot:
        await interaction.response.send_message("❌ You cannot send coins to bots.", ephemeral=True)
        return
    
    try:
        with bot.app.app_context():
            from src.models.database import db, User, Gift, Transaction
            
            # Get sender
            sender = User.query.filter_by(discord_id=str(interaction.user.id)).first()
            if not sender:
                await interaction.response.send_message(
                    "❌ You don't have an account yet! Send a message to create one.",
                    ephemeral=True
                )
                return
            
            # Check if sender has enough coins
            if sender.coins < amount:
                await interaction.response.send_message(
                    f"❌ Insufficient coins! You need **{amount:,}** coins but only have **{sender.coins:,}**.",
                    ephemeral=True
                )
                return
            
            # Get or create recipient
            recipient_user = User.query.filter_by(discord_id=str(recipient.id)).first()
            if not recipient_user:
                recipient_user = User(
                    discord_id=str(recipient.id),
                    username=recipient.display_name
                )
                db.session.add(recipient_user)
                db.session.flush()  # Get the ID
            
            # Create gift record
            gift = Gift(
                sender_id=sender.id,
                recipient_id=recipient_user.id,
                amount=amount,
                message=message,
                status='completed',
                processed_at=datetime.utcnow()
            )
            
            # Transfer coins
            sender.coins -= amount
            recipient_user.coins += amount
            
            # Create transaction records
            sender_transaction = Transaction(
                user_id=sender.id,
                transaction_type='gift_sent',
                amount=-amount,
                description=f'Gift sent to {recipient.display_name}',
                reference_id=f'gift_{gift.id}'
            )
            
            recipient_transaction = Transaction(
                user_id=recipient_user.id,
                transaction_type='gift_received',
                amount=amount,
                description=f'Gift received from {interaction.user.display_name}',
                reference_id=f'gift_{gift.id}'
            )
            
            db.session.add(gift)
            db.session.add(sender_transaction)
            db.session.add(recipient_transaction)
            db.session.commit()
            
            embed = discord.Embed(
                title="🎁 Gift Sent Successfully",
                description=f"You sent **{amount:,}** coins to {recipient.mention}",
                color=discord.Color.green()
            )
            
            if message:
                embed.add_field(name="Message", value=message, inline=False)
            
            embed.add_field(name="Your Remaining Balance", value=f"{sender.coins:,} coins", inline=True)
            embed.set_footer(text=f"Gift ID: {gift.id}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Notify recipient
            try:
                recipient_embed = discord.Embed(
                    title="🎁 You Received a Gift!",
                    description=f"{interaction.user.mention} sent you **{amount:,}** coins",
                    color=discord.Color.gold()
                )
                
                if message:
                    recipient_embed.add_field(name="Message", value=message, inline=False)
                
                recipient_embed.add_field(name="Your New Balance", value=f"{recipient_user.coins:,} coins", inline=True)
                
                await recipient.send(embed=recipient_embed)
            except discord.Forbidden:
                # User has DMs disabled
                pass
            
    except Exception as e:
        logger.error(f"Error in gift command: {e}")
        await interaction.response.send_message("❌ An error occurred while sending the gift.", ephemeral=True)

@bot.tree.command(name="help", description="Show available commands")
async def help_command(interaction: discord.Interaction):
    """Show help information"""
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Here are all available commands:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="💰 Economy Commands",
        value="`/balance` - Check your coin balance\n`/gift <user> <amount>` - Send coins to another user",
        inline=False
    )
    
    embed.add_field(
        name="🛒 Shop Commands",
        value="`/shop [category]` - Browse available items\n`/buy <item_id> [quantity]` - Purchase an item",
        inline=False
    )
    
    embed.add_field(
        name="🖥️ Server Commands",
        value="`/status` - Check Minecraft server status",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Information",
        value="• Earn coins by chatting in the server\n• Use coins to buy items and ranks\n• Items are delivered automatically",
        inline=False
    )
    
    embed.set_footer(text="Discord Bot Ecosystem v2.0")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

def run_bot(app):
    """Run the Discord bot with Flask app context"""
    bot.set_flask_app(app)
    
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables")
        return
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Error running bot: {e}")

