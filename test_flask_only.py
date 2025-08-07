#!/usr/bin/env python3
"""
Test script to verify Flask app startup without Discord bot
"""

import os
import sys
from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def test_flask_app():
    """Test Flask application startup"""
    try:
        print("Testing Flask application startup...")
        
        # Import Flask app components
        from src.main import app, db
        
        with app.app_context():
            print("✅ Flask app created successfully")
            
            # Test database connection
            try:
                from src.models.database import User, Item, BotConfig
                
                # Test basic queries
                config_count = BotConfig.query.count()
                item_count = Item.query.count()
                user_count = User.query.count()
                
                print(f"✅ Database connection successful")
                print(f"   - BotConfig entries: {config_count}")
                print(f"   - Items in shop: {item_count}")
                print(f"   - Users registered: {user_count}")
                
            except Exception as e:
                print(f"❌ Database connection failed: {e}")
                return False
            
            # Test routes registration
            print("✅ Testing route registration...")
            rules = list(app.url_map.iter_rules())
            api_routes = [rule for rule in rules if '/api' in rule.rule]
            print(f"   - Total routes: {len(rules)}")
            print(f"   - API routes: {len(api_routes)}")
            
            # Test a simple route
            with app.test_client() as client:
                response = client.get('/')
                if response.status_code == 200:
                    print("✅ Basic route test successful")
                else:
                    print(f"❌ Basic route test failed: {response.status_code}")
                    return False
                
                # Test health endpoint
                response = client.get('/health')
                if response.status_code == 200:
                    data = response.get_json()
                    print(f"✅ Health endpoint successful: {data.get('status', 'unknown')}")
                else:
                    print(f"❌ Health endpoint failed: {response.status_code}")
                    return False
            
            print("✅ All Flask tests passed!")
            return True
            
    except Exception as e:
        print(f"❌ Flask app test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Discord Bot Ecosystem - Flask App Test")
    print("=" * 50)
    
    success = test_flask_app()
    
    if success:
        print("\n🎉 Flask application is working correctly!")
    else:
        print("\n❌ Flask application test failed!")
        sys.exit(1)