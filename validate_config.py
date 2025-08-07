#!/usr/bin/env python3
"""
Configuration validation script for Discord Bot Ecosystem
Validates all environment variables and configuration settings
"""

import os
import sys
from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def validate_config():
    """Validate all configuration settings"""
    print("Validating configuration settings...")
    
    errors = []
    warnings = []
    
    # Required Flask settings
    required_flask = {
        'FLASK_SECRET_KEY': os.getenv('FLASK_SECRET_KEY'),
        'FLASK_ENV': os.getenv('FLASK_ENV'),
        'DATABASE_URL': os.getenv('DATABASE_URL')
    }
    
    print("\n📋 Flask Configuration:")
    for key, value in required_flask.items():
        if value is None:
            errors.append(f"Missing required setting: {key}")
            print(f"   ❌ {key}: Not set")
        elif key == 'FLASK_SECRET_KEY' and value == 'your-super-secure-secret-key-change-this-in-production':
            warnings.append(f"Using default secret key - change this in production!")
            print(f"   ⚠️  {key}: Using default (change in production)")
        else:
            print(f"   ✅ {key}: Set")
    
    # Discord settings (required for bot to work)
    discord_settings = {
        'DISCORD_CLIENT_ID': os.getenv('DISCORD_CLIENT_ID'),
        'DISCORD_CLIENT_SECRET': os.getenv('DISCORD_CLIENT_SECRET'),
        'DISCORD_BOT_TOKEN': os.getenv('DISCORD_BOT_TOKEN'),
        'DISCORD_REDIRECT_URI': os.getenv('DISCORD_REDIRECT_URI')
    }
    
    print("\n🤖 Discord Configuration:")
    for key, value in discord_settings.items():
        if value is None:
            errors.append(f"Missing Discord setting: {key}")
            print(f"   ❌ {key}: Not set")
        elif value.startswith('your-'):
            warnings.append(f"Using placeholder Discord setting: {key}")
            print(f"   ⚠️  {key}: Using placeholder")
        else:
            print(f"   ✅ {key}: Set")
    
    # Optional but recommended settings
    optional_settings = {
        'REDIS_URL': os.getenv('REDIS_URL'),
        'STRIPE_SECRET_KEY': os.getenv('STRIPE_SECRET_KEY'),
        'STRIPE_PUBLISHABLE_KEY': os.getenv('STRIPE_PUBLISHABLE_KEY'),
        'MINECRAFT_SERVER_HOST': os.getenv('MINECRAFT_SERVER_HOST'),
        'MINECRAFT_RCON_PASSWORD': os.getenv('MINECRAFT_RCON_PASSWORD')
    }
    
    print("\n🔧 Optional Configuration:")
    for key, value in optional_settings.items():
        if value is None:
            print(f"   ⚪ {key}: Not set")
        elif value.startswith('your-') or value.startswith('sk_test_') or value.startswith('pk_test_'):
            print(f"   ⚠️  {key}: Using placeholder")
        else:
            print(f"   ✅ {key}: Set")
    
    # Bot behavior settings
    bot_settings = {
        'COINS_PER_MESSAGE': os.getenv('COINS_PER_MESSAGE', '1'),
        'MESSAGE_COOLDOWN': os.getenv('MESSAGE_COOLDOWN', '60'),
        'MAX_DAILY_COINS': os.getenv('MAX_DAILY_COINS', '100'),
        'ADMIN_USER_IDS': os.getenv('ADMIN_USER_IDS')
    }
    
    print("\n⚙️  Bot Behavior Configuration:")
    for key, value in bot_settings.items():
        if value is None:
            print(f"   ⚪ {key}: Not set (will use defaults)")
        else:
            print(f"   ✅ {key}: {value}")
    
    # Test database connection
    print("\n💾 Database Connection:")
    try:
        from src.main import app, db
        with app.app_context():
            from src.models.database import BotConfig
            config_count = BotConfig.query.count()
            print(f"   ✅ Database connection successful ({config_count} configs)")
    except Exception as e:
        errors.append(f"Database connection failed: {e}")
        print(f"   ❌ Database connection failed: {e}")
    
    # Check file permissions and directories
    print("\n📁 File System:")
    database_dir = os.path.dirname(os.getenv('DATABASE_URL', '').replace('sqlite:///', ''))
    if database_dir and os.path.exists(database_dir):
        print(f"   ✅ Database directory exists: {database_dir}")
    else:
        warnings.append("Database directory may not exist")
        print(f"   ⚠️  Database directory: {database_dir}")
    
    # Summary
    print("\n" + "="*50)
    print("🏁 Validation Summary:")
    
    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for error in errors:
            print(f"   • {error}")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"   • {warning}")
    
    if not errors and not warnings:
        print("\n✅ All configuration settings are valid!")
        return True
    elif not errors:
        print(f"\n⚠️  Configuration is functional but has {len(warnings)} warnings")
        return True
    else:
        print(f"\n❌ Configuration has {len(errors)} errors that must be fixed")
        return False

if __name__ == '__main__':
    print("Discord Bot Ecosystem - Configuration Validation")
    print("=" * 50)
    
    success = validate_config()
    
    if success:
        print("\n🎉 Configuration validation passed!")
    else:
        print("\n❌ Configuration validation failed!")
        sys.exit(1)