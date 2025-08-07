from flask import Blueprint, request, jsonify
from src.models.database import db, BotConfig
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

bot_config_bp = Blueprint('bot_config', __name__)

@bot_config_bp.route('/bot-config', methods=['GET'])
def get_bot_config():
    """Get all bot configuration settings"""
    try:
        configs = BotConfig.query.all()
        return jsonify([config.to_dict() for config in configs])
    except Exception as e:
        logger.error(f"Error fetching bot config: {e}")
        return jsonify({'error': 'Failed to fetch configuration'}), 500

@bot_config_bp.route('/bot-config/<key>', methods=['GET'])
def get_config_by_key(key):
    """Get a specific configuration by key"""
    try:
        config = BotConfig.query.filter_by(key=key).first()
        if not config:
            return jsonify({'error': 'Configuration not found'}), 404
        
        return jsonify(config.to_dict())
    except Exception as e:
        logger.error(f"Error fetching config {key}: {e}")
        return jsonify({'error': 'Failed to fetch configuration'}), 500

@bot_config_bp.route('/bot-config/<key>', methods=['PUT'])
def update_config(key):
    """Update a specific configuration"""
    try:
        data = request.get_json()
        
        if 'value' not in data:
            return jsonify({'error': 'Value is required'}), 400
        
        config = BotConfig.query.filter_by(key=key).first()
        
        if not config:
            # Create new config if it doesn't exist
            config = BotConfig(
                key=key,
                value=str(data['value']),
                description=data.get('description', '')
            )
            db.session.add(config)
        else:
            # Update existing config
            config.value = str(data['value'])
            if 'description' in data:
                config.description = data['description']
            config.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify(config.to_dict())
        
    except Exception as e:
        logger.error(f"Error updating config {key}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update configuration'}), 500

@bot_config_bp.route('/bot-config/bulk-update', methods=['POST'])
def bulk_update_config():
    """Update multiple configurations at once"""
    try:
        data = request.get_json()
        
        if 'configs' not in data or not isinstance(data['configs'], list):
            return jsonify({'error': 'configs array is required'}), 400
        
        updated_configs = []
        
        for config_data in data['configs']:
            if 'key' not in config_data or 'value' not in config_data:
                continue
            
            key = config_data['key']
            value = str(config_data['value'])
            description = config_data.get('description', '')
            
            config = BotConfig.query.filter_by(key=key).first()
            
            if not config:
                # Create new config
                config = BotConfig(
                    key=key,
                    value=value,
                    description=description
                )
                db.session.add(config)
            else:
                # Update existing config
                config.value = value
                if description:
                    config.description = description
                config.updated_at = datetime.utcnow()
            
            updated_configs.append(config)
        
        db.session.commit()
        return jsonify([config.to_dict() for config in updated_configs])
        
    except Exception as e:
        logger.error(f"Error bulk updating configs: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update configurations'}), 500

@bot_config_bp.route('/bot-config/<key>', methods=['DELETE'])
def delete_config(key):
    """Delete a configuration"""
    try:
        config = BotConfig.query.filter_by(key=key).first()
        
        if not config:
            return jsonify({'error': 'Configuration not found'}), 404
        
        db.session.delete(config)
        db.session.commit()
        
        return jsonify({'message': 'Configuration deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting config {key}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete configuration'}), 500

@bot_config_bp.route('/bot-config/reset-defaults', methods=['POST'])
def reset_to_defaults():
    """Reset all configurations to default values"""
    try:
        # Default bot configuration
        default_configs = [
            ('currency_name', 'Coins', 'Name of the currency'),
            ('currency_symbol', '💰', 'Symbol representing the currency'),
            ('currency_emoji', '🪙', 'Emoji for the currency'),
            ('coins_per_message', '1', 'Coins earned per message'),
            ('message_cooldown', '60', 'Cooldown between coin earnings (seconds)'),
            ('max_daily_coins', '100', 'Maximum coins per day from messages'),
            ('welcome_message', 'Welcome to the server! You can earn coins by chatting and use them to buy items!', 'Bot welcome message'),
            ('purchase_channel', '', 'Channel ID for purchase notifications'),
            ('status_update_interval', '300', 'Server status update interval (seconds)'),
            ('enable_daily_bonus', 'false', 'Enable daily login bonus'),
            ('daily_bonus_amount', '50', 'Amount of daily bonus coins'),
            ('enable_level_multiplier', 'false', 'Enable level-based earning multiplier'),
            ('level_multiplier_rate', '0.1', 'Multiplier rate per level'),
        ]
        
        # Delete all existing configs
        BotConfig.query.delete()
        
        # Add default configs
        for key, value, description in default_configs:
            config = BotConfig(key=key, value=value, description=description)
            db.session.add(config)
        
        db.session.commit()
        
        # Return all configs
        configs = BotConfig.query.all()
        return jsonify([config.to_dict() for config in configs])
        
    except Exception as e:
        logger.error(f"Error resetting configs: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to reset configurations'}), 500

@bot_config_bp.route('/bot-config/categories', methods=['GET'])
def get_config_categories():
    """Get configuration categories for organization"""
    categories = {
        'currency': {
            'name': 'Currency Settings',
            'description': 'Configure currency appearance and behavior',
            'keys': ['currency_name', 'currency_symbol', 'currency_emoji']
        },
        'earning': {
            'name': 'Earning Settings',
            'description': 'Configure how users earn currency',
            'keys': ['coins_per_message', 'message_cooldown', 'max_daily_coins']
        },
        'bonuses': {
            'name': 'Bonus Features',
            'description': 'Additional earning mechanics',
            'keys': ['enable_daily_bonus', 'daily_bonus_amount', 'enable_level_multiplier', 'level_multiplier_rate']
        },
        'bot': {
            'name': 'Bot Configuration',
            'description': 'General bot settings',
            'keys': ['welcome_message', 'purchase_channel', 'status_update_interval']
        }
    }
    
    return jsonify(categories)

@bot_config_bp.route('/bot-config/validate', methods=['POST'])
def validate_config():
    """Validate configuration values"""
    try:
        data = request.get_json()
        
        if 'key' not in data or 'value' not in data:
            return jsonify({'error': 'Key and value are required'}), 400
        
        key = data['key']
        value = data['value']
        
        # Validation rules
        validation_rules = {
            'coins_per_message': {'type': 'int', 'min': 0, 'max': 100},
            'message_cooldown': {'type': 'int', 'min': 0, 'max': 3600},
            'max_daily_coins': {'type': 'int', 'min': 0, 'max': 10000},
            'status_update_interval': {'type': 'int', 'min': 60, 'max': 3600},
            'daily_bonus_amount': {'type': 'int', 'min': 0, 'max': 1000},
            'level_multiplier_rate': {'type': 'float', 'min': 0, 'max': 1},
            'currency_name': {'type': 'str', 'max_length': 50},
            'currency_symbol': {'type': 'str', 'max_length': 10},
            'currency_emoji': {'type': 'str', 'max_length': 10},
            'welcome_message': {'type': 'str', 'max_length': 500},
            'purchase_channel': {'type': 'str', 'max_length': 20}
        }
        
        if key not in validation_rules:
            return jsonify({'valid': True, 'message': 'No validation rules for this key'})
        
        rule = validation_rules[key]
        
        # Type validation
        if rule['type'] == 'int':
            try:
                int_value = int(value)
                if 'min' in rule and int_value < rule['min']:
                    return jsonify({'valid': False, 'message': f'Value must be at least {rule["min"]}'})
                if 'max' in rule and int_value > rule['max']:
                    return jsonify({'valid': False, 'message': f'Value must be at most {rule["max"]}'})
            except ValueError:
                return jsonify({'valid': False, 'message': 'Value must be a valid integer'})
        
        elif rule['type'] == 'float':
            try:
                float_value = float(value)
                if 'min' in rule and float_value < rule['min']:
                    return jsonify({'valid': False, 'message': f'Value must be at least {rule["min"]}'})
                if 'max' in rule and float_value > rule['max']:
                    return jsonify({'valid': False, 'message': f'Value must be at most {rule["max"]}'})
            except ValueError:
                return jsonify({'valid': False, 'message': 'Value must be a valid number'})
        
        elif rule['type'] == 'str':
            if 'max_length' in rule and len(str(value)) > rule['max_length']:
                return jsonify({'valid': False, 'message': f'Value must be at most {rule["max_length"]} characters'})
        
        return jsonify({'valid': True, 'message': 'Value is valid'})
        
    except Exception as e:
        logger.error(f"Error validating config: {e}")
        return jsonify({'error': 'Failed to validate configuration'}), 500

