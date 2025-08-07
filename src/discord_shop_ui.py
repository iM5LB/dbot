import discord
from discord.ext import commands
from typing import List, Optional
import math
from datetime import datetime

class ShopView(discord.ui.View):
    """Interactive shop view with pagination and category filtering"""
    
    def __init__(self, bot, items: List, user_id: int, category: Optional[str] = None, page: int = 0):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.bot = bot
        self.items = items
        self.user_id = user_id
        self.category = category
        self.page = page
        self.items_per_page = 5
        self.max_pages = math.ceil(len(items) / self.items_per_page) if items else 1
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page"""
        # Previous button
        self.previous_page.disabled = self.page <= 0
        
        # Next button
        self.next_page.disabled = self.page >= self.max_pages - 1
        
        # Category buttons
        if self.category:
            self.show_all.disabled = False
        else:
            self.show_all.disabled = True
    
    def get_current_items(self):
        """Get items for current page"""
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        return self.items[start:end]
    
    def create_embed(self):
        """Create embed for current page"""
        embed = discord.Embed(
            title="🛒 Item Shop",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        if self.category:
            embed.description = f"**Category:** {self.category.title()}"
        else:
            embed.description = "Browse all available items"
        
        current_items = self.get_current_items()
        
        if not current_items:
            embed.add_field(
                name="No Items Found",
                value="No items available in this category.",
                inline=False
            )
        else:
            for item in current_items:
                type_emoji = {
                    'discord': '🎭',
                    'minecraft': '⛏️',
                    'both': '🎮'
                }.get(item.item_type, '📦')
                
                availability = "✅ Available" if item.is_available else "❌ Unavailable"
                
                embed.add_field(
                    name=f"{type_emoji} {item.name} (ID: {item.id})",
                    value=f"{item.description}\n💰 **{item.price:,}** coins\n{availability}",
                    inline=True
                )
        
        # Add page info
        embed.set_footer(
            text=f"Page {self.page + 1}/{self.max_pages} • Total items: {len(self.items)} • Use /buy <item_id> to purchase"
        )
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user can interact with this view"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You cannot interact with this shop. Use `/shop` to open your own.",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary, row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        if self.page < self.max_pages - 1:
            self.page += 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary, row=0)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the shop"""
        if not self.bot.app:
            await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
            return
        
        try:
            with self.bot.app.app_context():
                from src.models.database import Item
                
                query = Item.query.filter_by(is_available=True)
                if self.category:
                    query = query.filter_by(category=self.category)
                
                self.items = query.order_by(Item.price).all()
                self.max_pages = math.ceil(len(self.items) / self.items_per_page) if self.items else 1
                
                # Reset to first page if current page is out of bounds
                if self.page >= self.max_pages:
                    self.page = 0
                
                self.update_buttons()
                embed = self.create_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                
        except Exception as e:
            await interaction.response.send_message("❌ Error refreshing shop.", ephemeral=True)
    
    @discord.ui.select(
        placeholder="Filter by category...",
        options=[
            discord.SelectOption(label="All Categories", value="all", emoji="📦"),
            discord.SelectOption(label="Weapons", value="weapons", emoji="⚔️"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️"),
            discord.SelectOption(label="Ranks", value="ranks", emoji="👑"),
            discord.SelectOption(label="Resources", value="resources", emoji="💎"),
            discord.SelectOption(label="Enchantments", value="enchantments", emoji="✨"),
            discord.SelectOption(label="Tools", value="tools", emoji="🔧"),
            discord.SelectOption(label="Other", value="other", emoji="📋"),
        ],
        row=1
    )
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Filter items by category"""
        if not self.bot.app:
            await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
            return
        
        try:
            with self.bot.app.app_context():
                from src.models.database import Item
                
                selected_category = select.values[0]
                
                if selected_category == "all":
                    self.category = None
                    query = Item.query.filter_by(is_available=True)
                else:
                    self.category = selected_category
                    query = Item.query.filter_by(is_available=True, category=selected_category)
                
                self.items = query.order_by(Item.price).all()
                self.max_pages = math.ceil(len(self.items) / self.items_per_page) if self.items else 1
                self.page = 0  # Reset to first page
                
                self.update_buttons()
                embed = self.create_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                
        except Exception as e:
            await interaction.response.send_message("❌ Error filtering items.", ephemeral=True)
    
    @discord.ui.button(label="🛒 Quick Buy", style=discord.ButtonStyle.primary, row=2)
    async def quick_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open quick buy modal"""
        modal = QuickBuyModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="💰 Balance", style=discord.ButtonStyle.success, row=2)
    async def check_balance(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Check user balance"""
        if not self.bot.app:
            await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
            return
        
        try:
            with self.bot.app.app_context():
                from src.models.database import User
                
                user = User.query.filter_by(discord_id=str(interaction.user.id)).first()
                
                if not user:
                    await interaction.response.send_message(
                        "💰 You don't have an account yet! Send a message to create one.",
                        ephemeral=True
                    )
                    return
                
                embed = discord.Embed(
                    title="💰 Your Balance",
                    description=f"You have **{user.coins:,}** coins",
                    color=discord.Color.gold()
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message("❌ Error checking balance.", ephemeral=True)
    
    @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger, row=2)
    async def close_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the shop"""
        embed = discord.Embed(
            title="🛒 Shop Closed",
            description="Thank you for browsing! Use `/shop` to open the shop again.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

class QuickBuyModal(discord.ui.Modal):
    """Modal for quick item purchase"""
    
    def __init__(self, bot):
        super().__init__(title="🛒 Quick Buy")
        self.bot = bot
    
    item_id = discord.ui.TextInput(
        label="Item ID",
        placeholder="Enter the item ID you want to buy...",
        required=True,
        max_length=10
    )
    
    quantity = discord.ui.TextInput(
        label="Quantity",
        placeholder="Enter quantity (default: 1)...",
        required=False,
        default="1",
        max_length=5
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle quick buy submission"""
        if not self.bot.app:
            await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
            return
        
        try:
            item_id = int(self.item_id.value)
            quantity = int(self.quantity.value) if self.quantity.value else 1
            
            if quantity <= 0:
                await interaction.response.send_message("❌ Quantity must be positive.", ephemeral=True)
                return
            
            with self.bot.app.app_context():
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
                
        except ValueError:
            await interaction.response.send_message("❌ Invalid item ID or quantity.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ An error occurred during purchase.", ephemeral=True)

class ItemDetailView(discord.ui.View):
    """Detailed view for a specific item"""
    
    def __init__(self, bot, item, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.item = item
        self.user_id = user_id
    
    def create_embed(self):
        """Create detailed embed for the item"""
        type_emoji = {
            'discord': '🎭',
            'minecraft': '⛏️',
            'both': '🎮'
        }.get(self.item.item_type, '📦')
        
        embed = discord.Embed(
            title=f"{type_emoji} {self.item.name}",
            description=self.item.description,
            color=discord.Color.blue()
        )
        
        embed.add_field(name="💰 Price", value=f"{self.item.price:,} coins", inline=True)
        embed.add_field(name="📂 Category", value=self.item.category.title(), inline=True)
        embed.add_field(name="🏷️ Type", value=self.item.item_type.title(), inline=True)
        
        if self.item.item_type in ['discord', 'both'] and self.item.discord_role_id:
            embed.add_field(name="🎭 Discord Role", value=f"<@&{self.item.discord_role_id}>", inline=True)
        
        if self.item.item_type in ['minecraft', 'both'] and self.item.minecraft_command_template:
            embed.add_field(name="⛏️ Minecraft Command", value=f"```\n{self.item.minecraft_command_template}\n```", inline=False)
        
        availability = "✅ Available" if self.item.is_available else "❌ Unavailable"
        embed.add_field(name="📊 Status", value=availability, inline=True)
        
        if self.item.image_url:
            embed.set_thumbnail(url=self.item.image_url)
        
        embed.set_footer(text=f"Item ID: {self.item.id}")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user can interact with this view"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You cannot interact with this item view.",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="🛒 Buy Now", style=discord.ButtonStyle.primary, row=4)
    async def buy_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Buy the item directly"""
        modal = QuickBuyModal(self.bot)
        modal.item_id.default = str(self.item.id)
        await interaction.response.send_modal(modal)

async def setup(bot):
    # This function is required for cogs/extensions
    pass


