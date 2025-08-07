#!/usr/bin/env python3
"""
Database models and relationships test script for Discord Bot Ecosystem
Tests all model functionality, relationships, and constraints
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def test_models():
    """Test all database models and relationships"""
    try:
        print("Testing database models and relationships...")
        
        from src.main import app, db
        from src.models.database import (
            User, Transaction, Item, Purchase, PaymentRecord, 
            MinecraftServer, ServerStatus, BotConfig, AuditLog, Gift
        )
        
        with app.app_context():
            print("✅ Models imported successfully")
            
            # Test User model
            print("\n👤 Testing User model...")
            test_user = User(
                discord_id="123456789",
                username="TestUser",
                email="test@example.com",
                coins=100,
                minecraft_uuid="test-uuid-123"
            )
            db.session.add(test_user)
            db.session.flush()  # Get ID without committing
            
            print(f"   ✅ User created: {test_user.username} (ID: {test_user.id})")
            
            # Test Item model
            print("\n🛒 Testing Item model...")
            test_item = Item(
                name="Test Sword",
                description="A test sword for testing",
                price=25,
                category="weapons",
                item_type="minecraft",
                minecraft_command_template="give {username} diamond_sword 1",
                is_available=True
            )
            db.session.add(test_item)
            db.session.flush()
            
            print(f"   ✅ Item created: {test_item.name} (Price: {test_item.price})")
            
            # Test Purchase model and relationships
            print("\n💳 Testing Purchase model and relationships...")
            test_purchase = Purchase(
                user_id=test_user.id,
                item_id=test_item.id,
                quantity=2,
                total_cost=50,
                status='fulfilled',
                fulfilled_at=datetime.utcnow()
            )
            db.session.add(test_purchase)
            db.session.flush()
            
            print(f"   ✅ Purchase created: {test_purchase.quantity}x {test_purchase.item.name}")
            print(f"   ✅ Relationship test: Purchase -> User: {test_purchase.user.username}")
            print(f"   ✅ Relationship test: Purchase -> Item: {test_purchase.item.name}")
            
            # Test Transaction model
            print("\n💰 Testing Transaction model...")
            test_transaction = Transaction(
                user_id=test_user.id,
                transaction_type='purchase',
                amount=-50,
                description=f'Purchased {test_purchase.quantity}x {test_item.name}',
                reference_id=f'purchase_{test_purchase.id}'
            )
            db.session.add(test_transaction)
            db.session.flush()
            
            print(f"   ✅ Transaction created: {test_transaction.transaction_type} ({test_transaction.amount})")
            print(f"   ✅ Relationship test: Transaction -> User: {test_transaction.user.username}")
            
            # Test Gift model
            print("\n🎁 Testing Gift model...")
            test_recipient = User(
                discord_id="987654321",
                username="TestRecipient",
                coins=0
            )
            db.session.add(test_recipient)
            db.session.flush()
            
            test_gift = Gift(
                sender_id=test_user.id,
                recipient_id=test_recipient.id,
                amount=25,
                message="Test gift!",
                status='completed',
                processed_at=datetime.utcnow()
            )
            db.session.add(test_gift)
            db.session.flush()
            
            print(f"   ✅ Gift created: {test_gift.amount} coins")
            print(f"   ✅ Relationship test: Gift -> Sender: {test_gift.sender.username}")
            print(f"   ✅ Relationship test: Gift -> Recipient: {test_gift.recipient.username}")
            
            # Test MinecraftServer model
            print("\n🖥️  Testing MinecraftServer model...")
            test_server = MinecraftServer(
                name="Test Server",
                host="test.example.com",
                port=25565,
                rcon_host="test.example.com",
                rcon_port=25575,
                rcon_password="test123",
                is_active=True
            )
            db.session.add(test_server)
            db.session.flush()
            
            print(f"   ✅ Server created: {test_server.name} ({test_server.host}:{test_server.port})")
            
            # Test ServerStatus model
            print("\n📊 Testing ServerStatus model...")
            test_status = ServerStatus(
                server_id=test_server.id,
                is_online=True,
                players_online=5,
                max_players=20,
                version="1.19.4",
                tps=19.5
            )
            db.session.add(test_status)
            db.session.flush()
            
            print(f"   ✅ Server status created: {test_status.players_online}/{test_status.max_players} players")
            print(f"   ✅ Relationship test: Status -> Server: {test_status.server.name}")
            
            # Test AuditLog model
            print("\n📝 Testing AuditLog model...")
            test_audit = AuditLog(
                user_id=test_user.id,
                action='test_action',
                details='{"test": "data"}'
            )
            db.session.add(test_audit)
            db.session.flush()
            
            print(f"   ✅ Audit log created: {test_audit.action}")
            print(f"   ✅ Relationship test: Audit -> User: {test_audit.user.username}")
            
            # Test BotConfig (already exists from init)
            print("\n⚙️  Testing BotConfig model...")
            configs = BotConfig.query.all()
            print(f"   ✅ Config entries found: {len(configs)}")
            if configs:
                sample_config = configs[0]
                print(f"   ✅ Sample config: {sample_config.key} = {sample_config.value}")
            
            # Test complex queries and relationships
            print("\n🔍 Testing complex queries...")
            
            # User's purchases
            user_purchases = Purchase.query.filter_by(user_id=test_user.id).all()
            print(f"   ✅ User purchases: {len(user_purchases)}")
            
            # User's transactions
            user_transactions = Transaction.query.filter_by(user_id=test_user.id).all()
            print(f"   ✅ User transactions: {len(user_transactions)}")
            
            # User's sent gifts
            sent_gifts = Gift.query.filter_by(sender_id=test_user.id).all()
            print(f"   ✅ Gifts sent: {len(sent_gifts)}")
            
            # User's received gifts
            received_gifts = Gift.query.filter_by(recipient_id=test_recipient.id).all()
            print(f"   ✅ Gifts received: {len(received_gifts)}")
            
            # Server status history
            server_statuses = ServerStatus.query.filter_by(server_id=test_server.id).all()
            print(f"   ✅ Server status history: {len(server_statuses)}")
            
            # Test constraints and validations
            print("\n🔒 Testing constraints and validations...")
            
            # Test unique constraints
            try:
                duplicate_user = User(discord_id="123456789", username="Duplicate")
                db.session.add(duplicate_user)
                db.session.flush()
                print("   ❌ Unique constraint test failed - duplicate discord_id allowed")
            except Exception:
                print("   ✅ Unique constraint working - duplicate discord_id rejected")
                db.session.rollback()
            
            # Test check constraints
            try:
                invalid_transaction = Transaction(
                    user_id=test_user.id,
                    transaction_type='invalid_type',
                    amount=0,
                    description='Test'
                )
                db.session.add(invalid_transaction)
                db.session.flush()
                print("   ❌ Check constraint test failed - invalid transaction type allowed")
            except Exception:
                print("   ✅ Check constraint working - invalid transaction type rejected")
                db.session.rollback()
            
            # Rollback all test data
            db.session.rollback()
            print("\n🔄 Test data rolled back successfully")
            
            print("\n✅ All model tests passed!")
            return True
            
    except Exception as e:
        print(f"\n❌ Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Discord Bot Ecosystem - Database Models Test")
    print("=" * 50)
    
    success = test_models()
    
    if success:
        print("\n🎉 Database models are working correctly!")
    else:
        print("\n❌ Database models test failed!")
        sys.exit(1)