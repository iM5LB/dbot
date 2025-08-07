#!/usr/bin/env python3
"""
Database initialization script for Discord Bot Ecosystem
Run this script to set up the database with default values
"""

import os
import sys
from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Import Flask app and database
from src.main import app, db

def init_database():
    """Initialize database with default data"""
    with app.app_context():
        print("Creating database tables...")
        
        # Create all tables
        db.create_all()
        
        # Import models after app context is created
        from src.models.database import BotConfig, Item, MinecraftServer
        
        print("Adding default configuration...")
        
        # Default bot configuration
        default_configs = [
            ('coins_per_message', '1', 'Coins earned per message'),
            ('message_cooldown', '60', 'Cooldown between coin earnings (seconds)'),
            ('max_daily_coins', '100', 'Maximum coins per day from messages'),
            ('welcome_message', 'Welcome to the server! You can earn coins by chatting and use them to buy items!', 'Bot welcome message'),
            ('purchase_channel', '', 'Channel ID for purchase notifications'),
            ('status_update_interval', '300', 'Server status update interval (seconds)'),
        ]
        
        for key, value, description in default_configs:
            if not BotConfig.query.filter_by(key=key).first():
                config = BotConfig(key=key, value=value, description=description)
                db.session.add(config)
                print(f"Added config: {key}")
        
        print("Adding default items...")
        
        # Default items
        default_items = [
            ('Diamond Sword', 'A sharp diamond sword', 50, 'weapons', 'minecraft', None, 'give {username} diamond_sword 1'),
            ('Iron Armor Set', 'Full set of iron armor', 100, 'armor', 'minecraft', None, 'give {username} iron_helmet 1; give {username} iron_chestplate 1; give {username} iron_leggings 1; give {username} iron_boots 1'),
            ('VIP Rank', 'VIP rank with special permissions', 500, 'ranks', 'minecraft', None, 'lp user {username} parent set vip'),
            ('Premium Rank', 'Premium rank with exclusive perks', 1000, 'ranks', 'minecraft', None, 'lp user {username} parent set premium'),
            ('Stack of Diamonds', '64 diamonds', 200, 'resources', 'minecraft', None, 'give {username} diamond 64'),
            ('Enchanted Book (Sharpness V)', 'Book with Sharpness V enchantment', 150, 'enchantments', 'minecraft', None, 'give {username} enchanted_book{StoredEnchantments:[{id:sharpness,lvl:5}]} 1'),
        ]
        
        for name, description, price, category, item_type, discord_role_id, command_template in default_items:
            if not Item.query.filter_by(name=name).first():
                item = Item(
                    name=name,
                    description=description,
                    price=price,
                    category=category,
                    item_type=item_type,
                    discord_role_id=discord_role_id,
                    minecraft_command_template=command_template,
                    is_available=True
                )
                db.session.add(item)
                print(f"Added item: {name}")
        
        print("Adding default Minecraft server...")
        
        # Default Minecraft server
        if not MinecraftServer.query.first():
            server = MinecraftServer(
                name='Main Server',
                host=os.getenv('MINECRAFT_SERVER_HOST', 'localhost'),
                port=int(os.getenv('MINECRAFT_SERVER_PORT', 25565)),
                rcon_host=os.getenv('MINECRAFT_RCON_HOST', 'localhost'),
                rcon_port=int(os.getenv('MINECRAFT_RCON_PORT', 25575)),
                rcon_password=os.getenv('MINECRAFT_RCON_PASSWORD', ''),
                is_active=True
            )
            db.session.add(server)
            print(f"Added server: {server.name}")
        
        try:
            db.session.commit()
            print("✅ Database initialized successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error initializing database: {e}")
            return False
            
        return True

if __name__ == '__main__':
    print("Discord Bot Ecosystem - Database Initialization")
    print("=" * 50)
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found! Please create one with the required environment variables.")
        sys.exit(1)
    
    # Initialize database
    success = init_database()
    
    if success:
        print("\n🎉 Database setup complete!")
        print("You can now start the Discord bot with: python src/main.py")
    else:
        print("\n❌ Database setup failed!")
        sys.exit(1)