from flask import Blueprint, request, jsonify, current_app
from src.models.database import db, User, Transaction, Item, Purchase, BotConfig, MinecraftServer, ServerStatus, PaymentRecord, AuditLog
from src.minecraft_integration import MinecraftIntegration
from datetime import datetime, timedelta
import logging
import json

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)
minecraft = MinecraftIntegration()

@api_bp.route('/users', methods=['GET'])
def get_users():
    """Get all users with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        
        query = User.query
        
        if search:
            query = query.filter(
                (User.username.contains(search)) | 
                (User.discord_id.contains(search))
            )
        
        users = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return jsonify({
            'users': [user.to_dict() for user in users.items],
            'total': users.total,
            'pages': users.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a specific user"""
    try:
        user = User.query.get_or_404(user_id)
        return jsonify(user.to_dict())
        
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return jsonify({'error': 'User not found'}), 404

@api_bp.route('/users/<int:user_id>/coins', methods=['POST'])
def update_user_coins(user_id):
    """Update user coins (admin only)"""
    try:
        data = request.get_json()
        amount = data.get('amount', 0)
        description = data.get('description', 'Admin adjustment')
        
        user = User.query.get_or_404(user_id)
        
        # Update coins
        user.coins += amount
        
        # Create transaction record
        transaction = Transaction(
            user_id=user.id,
            transaction_type='admin_add' if amount > 0 else 'admin_remove',
            amount=amount,
            description=description
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'message': 'Coins updated successfully',
            'new_balance': user.coins
        })
        
    except Exception as e:
        logger.error(f"Error updating user coins: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/transactions', methods=['GET'])
def get_transactions():
    """Get transactions with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        user_id = request.args.get('user_id', type=int)
        transaction_type = request.args.get('type')
        
        query = Transaction.query
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        if transaction_type:
            query = query.filter_by(transaction_type=transaction_type)
        
        transactions = query.order_by(Transaction.created_at.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'transactions': [t.to_dict() for t in transactions.items],
            'total': transactions.total,
            'pages': transactions.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/items', methods=['GET'])
def get_items():
    """Get all items"""
    try:
        category = request.args.get('category')
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        query = Item.query
        
        if category:
            query = query.filter_by(category=category)
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        items = query.order_by(Item.category, Item.name).all()
        
        return jsonify({
            'items': [item.to_dict() for item in items]
        })
        
    except Exception as e:
        logger.error(f"Error getting items: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/items', methods=['POST'])
def create_item():
    """Create a new item"""
    try:
        data = request.get_json()
        
        item = Item(
            name=data['name'],
            description=data.get('description', ''),
            price=data['price'],
            category=data.get('category', 'general'),
            minecraft_command_template=data['minecraft_command_template'],
            is_active=data.get('is_active', True)
        )
        
        db.session.add(item)
        db.session.commit()
        
        return jsonify({
            'message': 'Item created successfully',
            'item': item.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    """Update an item"""
    try:
        data = request.get_json()
        item = Item.query.get_or_404(item_id)
        
        item.name = data.get('name', item.name)
        item.description = data.get('description', item.description)
        item.price = data.get('price', item.price)
        item.category = data.get('category', item.category)
        item.minecraft_command_template = data.get('minecraft_command_template', item.minecraft_command_template)
        item.is_active = data.get('is_active', item.is_active)
        item.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Item updated successfully',
            'item': item.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating item: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Delete an item"""
    try:
        item = Item.query.get_or_404(item_id)
        
        # Check if item has purchases
        purchase_count = Purchase.query.filter_by(item_id=item_id).count()
        
        if purchase_count > 0:
            # Don't delete, just deactivate
            item.is_active = False
            db.session.commit()
            return jsonify({'message': 'Item deactivated (has purchase history)'})
        else:
            db.session.delete(item)
            db.session.commit()
            return jsonify({'message': 'Item deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting item: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/purchases', methods=['GET'])
def get_purchases():
    """Get purchases with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        user_id = request.args.get('user_id', type=int)
        status = request.args.get('status')
        
        query = Purchase.query
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        purchases = query.order_by(Purchase.created_at.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'purchases': [p.to_dict() for p in purchases.items],
            'total': purchases.total,
            'pages': purchases.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error getting purchases: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/purchases/<int:purchase_id>/fulfill', methods=['POST'])
def fulfill_purchase(purchase_id):
    """Manually fulfill a purchase"""
    try:
        purchase = Purchase.query.get_or_404(purchase_id)
        
        if purchase.status != 'pending':
            return jsonify({'error': 'Purchase is not pending'}), 400
        
        # Get user and item
        user = User.query.get(purchase.user_id)
        item = Item.query.get(purchase.item_id)
        
        if not user or not item:
            return jsonify({'error': 'User or item not found'}), 404
        
        # Generate command
        minecraft_command = item.minecraft_command_template.format(
            username=user.minecraft_uuid or user.username
        )
        
        # Execute command synchronously for now
        import asyncio
        success = asyncio.run(minecraft.execute_command(minecraft_command))
        
        if success:
            purchase.status = 'fulfilled'
            purchase.fulfilled_at = datetime.utcnow()
            purchase.minecraft_command = minecraft_command
            db.session.commit()
            
            return jsonify({'message': 'Purchase fulfilled successfully'})
        else:
            return jsonify({'error': 'Failed to execute Minecraft command'}), 500
        
    except Exception as e:
        logger.error(f"Error fulfilling purchase: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/server/status', methods=['GET'])
def get_server_status():
    """Get current server status"""
    try:
        servers = MinecraftServer.query.filter_by(is_active=True).all()
        server_statuses = []
        
        for server in servers:
            # Get latest status from database
            latest_status = ServerStatus.query.filter_by(server_id=server.id).order_by(ServerStatus.timestamp.desc()).first()
            
            server_data = server.to_dict()
            server_data['status'] = latest_status.to_dict() if latest_status else None
            
            server_statuses.append(server_data)
        
        return jsonify({'servers': server_statuses})
        
    except Exception as e:
        logger.error(f"Error getting server status: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/server/refresh', methods=['POST'])
def refresh_server_status():
    """Manually refresh server status"""
    try:
        servers = MinecraftServer.query.filter_by(is_active=True).all()
        
        for server in servers:
            # Get fresh status synchronously
            import asyncio
            status = asyncio.run(minecraft.get_server_status(server.host, server.port))
            
            # Save to database
            server_status = ServerStatus(
                server_id=server.id,
                is_online=status['online'],
                players_online=status.get('players_online', 0),
                max_players=status.get('max_players', 0),
                version=status.get('version', ''),
                timestamp=datetime.utcnow()
            )
            
            db.session.add(server_status)
        
        db.session.commit()
        
        return jsonify({'message': 'Server status refreshed successfully'})
        
    except Exception as e:
        logger.error(f"Error refreshing server status: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/server/command', methods=['POST'])
def execute_server_command():
    """Execute a command on the Minecraft server"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({'error': 'Command is required'}), 400
        
        # Execute command
        import asyncio
        success = asyncio.run(minecraft.execute_command(command))
        
        if success:
            # Log the action
            audit_log = AuditLog(
                action='server_command',
                details=f"Executed command: {command}",
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
            db.session.commit()
            
            return jsonify({'message': 'Command executed successfully'})
        else:
            return jsonify({'error': 'Failed to execute command'}), 500
        
    except Exception as e:
        logger.error(f"Error executing server command: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/config', methods=['GET'])
def get_bot_config():
    """Get bot configuration"""
    try:
        configs = BotConfig.query.all()
        return jsonify({
            'config': {config.key: config.value for config in configs},
            'details': [config.to_dict() for config in configs]
        })
        
    except Exception as e:
        logger.error(f"Error getting bot config: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/config', methods=['POST'])
def update_bot_config():
    """Update bot configuration"""
    try:
        data = request.get_json()
        
        for key, value in data.items():
            config = BotConfig.query.filter_by(key=key).first()
            
            if config:
                config.value = str(value)
                config.updated_at = datetime.utcnow()
            else:
                config = BotConfig(
                    key=key,
                    value=str(value),
                    description=f"Custom config: {key}"
                )
                db.session.add(config)
        
        db.session.commit()
        
        return jsonify({'message': 'Configuration updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating bot config: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/stats/overview', methods=['GET'])
def get_stats_overview():
    """Get overview statistics"""
    try:
        # Get basic stats
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        total_purchases = Purchase.query.count()
        pending_purchases = Purchase.query.filter_by(status='pending').count()
        
        # Get recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_users = User.query.filter(User.created_at >= week_ago).count()
        recent_purchases = Purchase.query.filter(Purchase.created_at >= week_ago).count()
        
        # Get total coins in circulation
        total_coins = db.session.query(db.func.sum(User.coins)).scalar() or 0
        
        # Get top categories
        category_stats = db.session.query(
            Item.category,
            db.func.count(Purchase.id).label('purchase_count')
        ).join(Purchase).group_by(Item.category).all()
        
        return jsonify({
            'overview': {
                'total_users': total_users,
                'active_users': active_users,
                'total_purchases': total_purchases,
                'pending_purchases': pending_purchases,
                'recent_users': recent_users,
                'recent_purchases': recent_purchases,
                'total_coins': total_coins
            },
            'categories': [
                {'category': cat, 'purchases': count} 
                for cat, count in category_stats
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting stats overview: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/stats/revenue', methods=['GET'])
def get_revenue_stats():
    """Get revenue statistics"""
    try:
        # Get payment statistics
        total_payments = PaymentRecord.query.filter_by(status='succeeded').count()
        total_revenue = db.session.query(
            db.func.sum(PaymentRecord.amount_cents)
        ).filter_by(status='succeeded').scalar() or 0
        
        # Convert cents to dollars
        total_revenue_dollars = total_revenue / 100
        
        # Get monthly revenue (last 12 months)
        monthly_revenue = []
        for i in range(12):
            month_start = datetime.utcnow().replace(day=1) - timedelta(days=30*i)
            month_end = month_start + timedelta(days=30)
            
            revenue = db.session.query(
                db.func.sum(PaymentRecord.amount_cents)
            ).filter(
                PaymentRecord.status == 'succeeded',
                PaymentRecord.created_at >= month_start,
                PaymentRecord.created_at < month_end
            ).scalar() or 0
            
            monthly_revenue.append({
                'month': month_start.strftime('%Y-%m'),
                'revenue': revenue / 100
            })
        
        return jsonify({
            'total_payments': total_payments,
            'total_revenue': total_revenue_dollars,
            'monthly_revenue': list(reversed(monthly_revenue))
        })
        
    except Exception as e:
        logger.error(f"Error getting revenue stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

