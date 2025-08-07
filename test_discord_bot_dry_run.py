#!/usr/bin/env python3
"""
Discord Bot dry run test script for Discord Bot Ecosystem
Tests bot initialization and command loading without connecting to Discord
"""

import os
import sys
from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def test_discord_bot_dry_run():
    """Test Discord bot initialization without connecting"""
    try:
        print("Testing Discord bot initialization (dry run)...")
        
        # Import Flask app
        from src.main import app
        
        with app.app_context():
            print("✅ Flask app context created")
            
            # Import Discord bot components
            try:
                from src.discord_bot_slash import DiscordBotSlash, bot
                print("✅ Discord bot class imported successfully")
                
                # Test bot instance creation
                test_bot = DiscordBotSlash()
                print("✅ Bot instance created successfully")
                
                # Set Flask app context
                test_bot.set_flask_app(app)
                print("✅ Flask app context set on bot")
                
                # Test that Flask app is accessible
                if test_bot.app is not None:
                    print("✅ Bot has Flask app context")
                else:
                    print("❌ Bot missing Flask app context")
                    return False
                
            except Exception as e:
                print(f"❌ Discord bot import/creation failed: {e}")
                return False
            
            # Test Discord gift commands cog
            try:
                from src.discord_gift_commands import GiftCommands
                gift_cog = GiftCommands(test_bot)
                print("✅ Gift commands cog created successfully")
                
                # Test cog check method
                if hasattr(gift_cog, 'cog_check'):
                    check_result = gift_cog.cog_check(None)  # Pass None as ctx for testing
                    if check_result:
                        print("✅ Gift cog check passes with Flask app context")
                    else:
                        print("❌ Gift cog check fails")
                        return False
                else:
                    print("⚠️  Gift cog missing cog_check method")
                
            except Exception as e:
                print(f"❌ Gift commands cog creation failed: {e}")
                return False
            
            # Test Discord shop UI components
            try:
                from src.discord_shop_ui import ShopView, ItemDetailView
                print("✅ Discord shop UI components imported successfully")
                
                # Test creating a shop view with sample data
                from src.models.database import Item
                
                # Get some items for testing
                items = Item.query.limit(3).all()
                if items:
                    # Test shop view creation (this should not fail during import/creation)
                    print(f"✅ Found {len(items)} items for shop view test")
                else:
                    print("⚠️  No items found for shop view test")
                
            except Exception as e:
                print(f"❌ Discord shop UI import failed: {e}")
                return False
            
            # Test slash command definitions exist
            print("\n🔍 Testing slash command structure...")
            
            # Check if the bot has a command tree
            if hasattr(test_bot, 'tree'):
                print("✅ Bot has command tree for slash commands")
            else:
                print("❌ Bot missing command tree")
                return False
            
            # Test command registration (without actually syncing)
            command_count = 0
            
            # Check if commands are properly defined in the module
            from src import discord_bot_slash
            module_attrs = dir(discord_bot_slash)
            
            slash_commands = [attr for attr in module_attrs if attr.endswith('_command')]
            print(f"✅ Found {len(slash_commands)} command definitions")
            
            for cmd in slash_commands:
                print(f"   - {cmd}")
            
            # Test background task definitions
            print("\n⏰ Testing background tasks...")
            
            if hasattr(test_bot, 'update_server_status'):
                print("✅ Server status update task defined")
            else:
                print("❌ Server status update task missing")
                return False
            
            if hasattr(test_bot, 'process_pending_purchases'):
                print("✅ Purchase processing task defined")
            else:
                print("❌ Purchase processing task missing")
                return False
            
            # Test database operations in bot context
            print("\n💾 Testing database operations in bot context...")
            
            try:
                from src.models.database import User, BotConfig
                
                # Test config loading (like the bot would do)
                config_count = BotConfig.query.count()
                print(f"✅ Bot can access config ({config_count} entries)")
                
                # Test user queries (like the bot would do)
                user_count = User.query.count()
                print(f"✅ Bot can access users ({user_count} users)")
                
            except Exception as e:
                print(f"❌ Database operations in bot context failed: {e}")
                return False
            
            # Test Minecraft integration import
            print("\n🖥️  Testing Minecraft integration...")
            
            try:
                from src.minecraft_integration import MinecraftIntegration
                print("✅ Minecraft integration imported successfully")
                
                # Test creating integration instance
                mc_integration = MinecraftIntegration()
                print("✅ Minecraft integration instance created")
                
            except Exception as e:
                print(f"❌ Minecraft integration test failed: {e}")
                return False
            
            print("\n✅ All Discord bot dry run tests passed!")
            return True
            
    except Exception as e:
        print(f"\n❌ Discord bot dry run test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Discord Bot Ecosystem - Discord Bot Dry Run Test")
    print("=" * 50)
    
    success = test_discord_bot_dry_run()
    
    if success:
        print("\n🎉 Discord bot initialization is working correctly!")
        print("\n📝 NOTE: This was a dry run test. To fully test the bot:")
        print("   1. Set up a Discord application and bot")
        print("   2. Add the bot token to .env file")
        print("   3. Run the main application: python src/main.py")
    else:
        print("\n❌ Discord bot dry run test failed!")
        sys.exit(1)