#!/usr/bin/env python3
"""
Simple Discord bot import test
"""

import os
import sys
from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def test_simple_discord():
    """Test basic Discord imports"""
    try:
        print("Testing basic Discord imports...")
        
        # Test py-cord import
        import discord
        print("✅ Discord (py-cord) imported successfully")
        
        # Test Discord components
        from discord.ext import commands
        print("✅ Discord commands imported successfully")
        
        # Test basic bot creation
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        bot = commands.Bot(command_prefix='!', intents=intents)
        print("✅ Discord bot instance created successfully")
        
        # Test Flask app import
        from src.main import app
        print("✅ Flask app imported successfully")
        
        # Test setting Flask app on bot (simulating what our bot does)
        bot.app = app
        print("✅ Flask app context attached to bot")
        
        # Test database access from bot context
        with app.app_context():
            from src.models.database import User, BotConfig
            config_count = BotConfig.query.count()
            print(f"✅ Bot can access database ({config_count} configs)")
        
        print("\n✅ Basic Discord bot setup is working!")
        print("\n📝 NOTE: Full Discord functionality requires:")
        print("   1. Valid Discord bot token")
        print("   2. Discord application setup")
        print("   3. Server to test commands")
        
        return True
        
    except Exception as e:
        print(f"❌ Discord test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Discord Bot Ecosystem - Simple Discord Test")
    print("=" * 50)
    
    success = test_simple_discord()
    
    if success:
        print("\n🎉 Discord bot imports and basic setup working correctly!")
    else:
        print("\n❌ Discord bot test failed!")
        sys.exit(1)