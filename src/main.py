from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import models and routes
from src.models.database import db
from src.routes.api import api_bp
from src.routes.admin import admin_bp
from src.routes.payments import payments_bp
from src.routes.auth import auth_bp
from src.routes.bot_config import bot_config_bp
from src.routes.gifts import gifts_bp
from src.routes.audit import audit_bp
from src.routes.servers import servers_bp

# Create Flask app
app = Flask(__name__, static_folder='static')

# Enable CORS
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database/app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Register blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(payments_bp, url_prefix='/payments')
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(bot_config_bp, url_prefix='/api')
app.register_blueprint(gifts_bp, url_prefix='/api')
app.register_blueprint(audit_bp, url_prefix='/api')
app.register_blueprint(servers_bp, url_prefix='/api')

# Initialize database
db.init_app(app)

# Initialize database
def init_database():
    """Initialize database with default data"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Initialize default configuration if not exists
        from src.models.database import BotConfig, Item, MinecraftServer
        
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
        
        try:
            db.session.commit()
            print("Database initialized successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error initializing database: {e}")

@app.route('/')
def index():
    """Basic index page"""
    return "Discord Bot Ecosystem API is running! Check /api endpoints for API access."

@app.route('/health')
def health():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Discord Bot Ecosystem is running"}

def start_discord_bot():
    """Start Discord bot in a separate thread"""
    try:
        from src.discord_bot_slash import run_bot
        run_bot(app)
    except Exception as e:
        print(f"Error starting Discord bot: {e}")

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Start Discord bot in background thread
    bot_thread = threading.Thread(target=start_discord_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)

