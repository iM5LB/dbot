#!/usr/bin/env python3
"""
Database initialization script for Discord Bot Ecosystem (Windows Compatible)
Run this script to set up the database with default values

Usage: python init_db_fixed.py
"""

import os
import sys
from dotenv import load_dotenv

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

# Load environment variables
load_dotenv()

from flask import Flask
from models.database import db, BotConfig, Item, MinecraftServer

def create_app():
    """Create Flask app for database initialization"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database/app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Create database directory if it doesn't exist
    db_dir = os.path.join(current_dir, 'database')
    os.makedirs(db_dir, exist_ok=True)
    
    # Initialize database
    db.init_app(app)
    
    return app

def init_database():
    """Initialize database with default data"""
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        
        # Create all tables
        db.create_all()
        
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
        
        configs_added = 0
        for key, value, description in default_configs:
            if not BotConfig.query.filter_by(key=key).first():
                config = BotConfig(key=key, value=value, description=description)
                db.session.add(config)
                print(f"  ✅ Added config: {key}")
                configs_added += 1
        
        if configs_added == 0:
            print("  ℹ️  All default configurations already exist")
        
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
        
        items_added = 0
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
                print(f"  ✅ Added item: {name}")
                items_added += 1
        
        if items_added == 0:
            print("  ℹ️  All default items already exist")
        
        print("Adding default Minecraft server...")
        
        # Default Minecraft server
        servers_added = 0
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
            print(f"  ✅ Added server: {server.name}")
            servers_added += 1
        else:
            print("  ℹ️  Default server already exists")
        
        try:
            db.session.commit()
            print(f"\n🎉 Database initialized successfully!")
            print(f"📊 Added: {configs_added} configs, {items_added} items, {servers_added} servers")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error initializing database: {e}")
            return False

def check_environment():
    """Check if environment is properly configured"""
    print("🔍 Checking environment...")
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("📝 Creating example .env file...")
        return False
    else:
        print("✅ .env file found")
    
    # Check database path
    db_url = os.getenv('DATABASE_URL', 'sqlite:///database/app.db')
    print(f"📁 Database URL: {db_url}")
    
    # Check if database directory can be created
    try:
        db_dir = os.path.join(current_dir, 'database')
        os.makedirs(db_dir, exist_ok=True)
        print(f"✅ Database directory ready: {db_dir}")
        return True
    except Exception as e:
        print(f"❌ Cannot create database directory: {e}")
        return False

if __name__ == '__main__':
    print("🚀 Discord Bot Ecosystem - Database Initialization")
    print("=" * 55)
    print(f"📁 Working from: {current_dir}")
    
    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed!")
        sys.exit(1)
    
    # Initialize database
    print(f"\n📊 Initializing database...")
    success = init_database()
    
    if success:
        print("\n🎉 Database setup complete!")
        print("🚀 You can now start the Discord bot with:")
        print("   python main_fixed.py")
        print("\n📝 Don't forget to:")
        print("   1. Set your DISCORD_BOT_TOKEN in .env file")
        print("   2. Set your DISCORD_CLIENT_ID in .env file")
        print("   3. Invite your bot to your Discord server")
    else:
        print("\n❌ Database setup failed!")
        sys.exit(1)