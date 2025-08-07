import discord
from discord.ext import commands
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GiftCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def cog_check(self, ctx):
        """Check if bot has Flask app context"""
        return hasattr(self.bot, 'app') and self.bot.app is not None

    @discord.slash_command(name="gift", description="Send coins to another user")
    async def gift_coins(self, ctx, user: discord.Member, amount: int, message: str = ""):
        """Send coins to another user"""
        try:
            await interaction.response.defer()
            
            # Validation
            if amount <= 0:
                await ctx.followup.send("❌ Amount must be positive!", ephemeral=True)
                return
            
            if user.id == interaction.user.id:
                await ctx.followup.send("❌ You cannot send coins to yourself!", ephemeral=True)
                return
            
            if user.bot:
                await ctx.followup.send("❌ You cannot send coins to bots!", ephemeral=True)
                return
            
            with self.bot.app.app_context():
                from src.models.database import db, User, Gift, Transaction, AuditLog
                
                # Get or create users
                sender = User.query.filter_by(discord_id=str(ctx.author.id)).first()
            if not sender:
                await ctx.followup.send("❌ You need to use the bot first to send gifts!", ephemeral=True)
                return
            
            recipient = User.query.filter_by(discord_id=str(user.id)).first()
            if not recipient:
                # Create recipient user
                recipient = User(
                    discord_id=str(user.id),
                    username=user.display_name,
                    coins=0
                )
                db.session.add(recipient)
                db.session.flush()  # Get the ID
            
            # Check if sender has enough coins
            if sender.coins < amount:
                await ctx.followup.send(
                    f"❌ Insufficient coins! You have {sender.coins:,} coins but need {amount:,}.",
                    ephemeral=True
                )
                return
            
            # Create gift record
            gift = Gift(
                sender_id=sender.id,
                recipient_id=recipient.id,
                amount=amount,
                message=message,
                status='completed',
                processed_at=datetime.utcnow()
            )
            
            # Transfer coins
            sender.coins -= amount
            recipient.coins += amount
            
            # Create transaction records
            sender_transaction = Transaction(
                user_id=sender.id,
                transaction_type='gift_sent',
                amount=-amount,
                description=f'Gift sent to {recipient.username}',
                reference_id=f'gift_{gift.id}'
            )
            
            recipient_transaction = Transaction(
                user_id=recipient.id,
                transaction_type='gift_received',
                amount=amount,
                description=f'Gift received from {sender.username}',
                reference_id=f'gift_{gift.id}'
            )
            
            # Create audit log entries
            sender_audit = AuditLog(
                user_id=sender.id,
                action='gift_sent',
                details=f'{{"amount": {amount}, "recipient": "{recipient.username}", "message": "{message}"}}'
            )
            
            recipient_audit = AuditLog(
                user_id=recipient.id,
                action='gift_received',
                details=f'{{"amount": {amount}, "sender": "{sender.username}", "message": "{message}"}}'
            )
            
            db.session.add(gift)
            db.session.add(sender_transaction)
            db.session.add(recipient_transaction)
            db.session.add(sender_audit)
            db.session.add(recipient_audit)
            db.session.commit()
            
            # Create success embed
            embed = discord.Embed(
                title="🎁 Gift Sent Successfully!",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="From",
                value=f"{ctx.author.mention}\n💰 {sender.coins:,} coins remaining",
                inline=True
            )
            
            embed.add_field(
                name="To",
                value=f"{user.mention}\n💰 {recipient.coins:,} coins total",
                inline=True
            )
            
            embed.add_field(
                name="Amount",
                value=f"🪙 {amount:,} coins",
                inline=True
            )
            
            if message:
                embed.add_field(
                    name="Message",
                    value=f"💬 {message}",
                    inline=False
                )
            
            embed.set_footer(text=f"Gift ID: {gift.id}")
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to recipient if possible
            try:
                dm_embed = discord.Embed(
                    title="🎁 You received a gift!",
                    description=f"**{ctx.author.display_name}** sent you **{amount:,} coins**!",
                    color=0x00ff00,
                    timestamp=datetime.utcnow()
                )
                
                if message:
                    dm_embed.add_field(name="Message", value=message, inline=False)
                
                dm_embed.add_field(
                    name="Your Balance",
                    value=f"💰 {recipient.coins:,} coins",
                    inline=True
                )
                
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                pass  # User has DMs disabled
            
        except Exception as e:
            logger.error(f"Error in gift command: {e}")
            await ctx.followup.send("❌ An error occurred while sending the gift.", ephemeral=True)
            db.session.rollback()

    @app_commands.command(name="gifts", description="View your gift history")
    async def gift_history(self, interaction: discord.Interaction):
        """View gift history for the user"""
        if not self.bot.app:
            await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
            return
            
        try:
            await interaction.response.defer()
            
            with self.bot.app.app_context():
                from src.models.database import User, Gift
                
                # Get user
                user = User.query.filter_by(discord_id=str(interaction.user.id)).first()
                if not user:
                    await interaction.followup.send("❌ You haven't used the bot yet!", ephemeral=True)
                    return
                
                # Get sent and received gifts
                sent_gifts = Gift.query.filter_by(sender_id=user.id).order_by(Gift.created_at.desc()).limit(10).all()
                received_gifts = Gift.query.filter_by(recipient_id=user.id).order_by(Gift.created_at.desc()).limit(10).all()
            
            embed = discord.Embed(
                title="🎁 Your Gift History",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            # Sent gifts
            if sent_gifts:
                sent_text = ""
                for gift in sent_gifts[:5]:  # Show last 5
                    recipient_name = gift.recipient.username if gift.recipient else "Unknown"
                    sent_text += f"• **{gift.amount:,}** coins to **{recipient_name}**\n"
                    if gift.message:
                        sent_text += f"  💬 _{gift.message}_\n"
                    sent_text += f"  📅 {gift.created_at.strftime('%m/%d/%Y')}\n\n"
                
                embed.add_field(
                    name="📤 Recently Sent",
                    value=sent_text or "No gifts sent yet",
                    inline=False
                )
            
            # Received gifts
            if received_gifts:
                received_text = ""
                for gift in received_gifts[:5]:  # Show last 5
                    sender_name = gift.sender.username if gift.sender else "Admin"
                    received_text += f"• **{gift.amount:,}** coins from **{sender_name}**\n"
                    if gift.message:
                        received_text += f"  💬 _{gift.message}_\n"
                    received_text += f"  📅 {gift.created_at.strftime('%m/%d/%Y')}\n\n"
                
                embed.add_field(
                    name="📥 Recently Received",
                    value=received_text or "No gifts received yet",
                    inline=False
                )
            
            # Statistics
            total_sent = sum(gift.amount for gift in sent_gifts)
            total_received = sum(gift.amount for gift in received_gifts)
            
            embed.add_field(
                name="📊 Statistics",
                value=f"**Sent:** {len(sent_gifts)} gifts ({total_sent:,} coins)\n**Received:** {len(received_gifts)} gifts ({total_received:,} coins)",
                inline=False
            )
            
            embed.set_footer(text=f"Current Balance: {user.coins:,} coins")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in gift history command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching gift history.", ephemeral=True)

    @app_commands.command(name="leaderboard", description="View the top coin holders and gift givers")
    async def leaderboard(self, interaction: discord.Interaction):
        """Show leaderboards for coins and gifts"""
        if not self.bot.app:
            await interaction.response.send_message("❌ Bot is not properly configured.", ephemeral=True)
            return
            
        try:
            await interaction.response.defer()
            
            with self.bot.app.app_context():
                from src.models.database import db, User, Gift
                
                # Top coin holders
                top_holders = User.query.order_by(User.coins.desc()).limit(10).all()
                
                # Top gift givers (by amount sent)
                top_givers = db.session.query(
                    User.username,
                    db.func.sum(Gift.amount).label('total_sent')
                ).join(Gift, User.id == Gift.sender_id).filter(
                    Gift.status == 'completed'
                ).group_by(User.id).order_by(
                    db.func.sum(Gift.amount).desc()
                ).limit(10).all()
            
            embed = discord.Embed(
                title="🏆 Leaderboards",
                color=0xffd700,
                timestamp=datetime.utcnow()
            )
            
            # Coin holders leaderboard
            if top_holders:
                holders_text = ""
                for i, user in enumerate(top_holders, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    holders_text += f"{medal} **{user.username}** - {user.coins:,} coins\n"
                
                embed.add_field(
                    name="💰 Top Coin Holders",
                    value=holders_text,
                    inline=True
                )
            
            # Gift givers leaderboard
            if top_givers:
                givers_text = ""
                for i, giver in enumerate(top_givers, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    givers_text += f"{medal} **{giver.username}** - {giver.total_sent:,} coins given\n"
                
                embed.add_field(
                    name="🎁 Top Gift Givers",
                    value=givers_text,
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching leaderboards.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(GiftCommands(bot))

