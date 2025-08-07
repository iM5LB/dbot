from flask import Blueprint, request, jsonify, current_app
from src.models.database import db, User, MinecraftServer, AuditLog
from src.minecraft_integration import MinecraftIntegration
from datetime import datetime
import logging
import os

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)
minecraft = MinecraftIntegration()

def is_admin(user_id):
    """Check if user is admin"""
    admin_ids = os.getenv('ADMIN_USER_IDS', '').split(',')
    return str(user_id) in admin_ids

@admin_bp.route('/servers', methods=['GET'])
def get_servers():
    """Get all Minecraft servers"""
    try:
        servers = MinecraftServer.query.all()
        return jsonify({
            'servers': [server.to_dict() for server in servers]
        })
        
    except Exception as e:
        logger.error(f"Error getting servers: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/servers', methods=['POST'])
def create_server():
    """Create a new Minecraft server"""
    try:
        data = request.get_json()
        
        server = MinecraftServer(
            name=data['name'],
            host=data['host'],
            port=data.get('port', 25565),
            rcon_host=data.get('rcon_host', data['host']),
            rcon_port=data.get('rcon_port', 25575),
            rcon_password=data.get('rcon_password', ''),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(server)
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            action='server_created',
            details=f"Created server: {server.name} ({server.host}:{server.port})",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': 'Server created successfully',
            'server': server.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating server: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/servers/<int:server_id>', methods=['PUT'])
def update_server(server_id):
    """Update a Minecraft server"""
    try:
        data = request.get_json()
        server = MinecraftServer.query.get_or_404(server_id)
        
        server.name = data.get('name', server.name)
        server.host = data.get('host', server.host)
        server.port = data.get('port', server.port)
        server.rcon_host = data.get('rcon_host', server.rcon_host)
        server.rcon_port = data.get('rcon_port', server.rcon_port)
        server.rcon_password = data.get('rcon_password', server.rcon_password)
        server.is_active = data.get('is_active', server.is_active)
        server.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            action='server_updated',
            details=f"Updated server: {server.name}",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': 'Server updated successfully',
            'server': server.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating server: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/servers/<int:server_id>', methods=['DELETE'])
def delete_server(server_id):
    """Delete a Minecraft server"""
    try:
        server = MinecraftServer.query.get_or_404(server_id)
        
        # Log the action before deletion
        audit_log = AuditLog(
            action='server_deleted',
            details=f"Deleted server: {server.name} ({server.host}:{server.port})",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.delete(server)
        db.session.commit()
        
        return jsonify({'message': 'Server deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting server: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/servers/<int:server_id>/test', methods=['POST'])
def test_server_connection(server_id):
    """Test connection to a Minecraft server"""
    try:
        server = MinecraftServer.query.get_or_404(server_id)
        
        # Test server connection
        import asyncio
        results = asyncio.run(minecraft.test_connection(
            host=server.host,
            port=server.port,
            rcon_host=server.rcon_host,
            rcon_port=server.rcon_port,
            rcon_password=server.rcon_password
        ))
        
        return jsonify({
            'server': server.to_dict(),
            'test_results': results
        })
        
    except Exception as e:
        logger.error(f"Error testing server connection: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/users/<int:user_id>/ban', methods=['POST'])
def ban_user(user_id):
    """Ban/unban a user"""
    try:
        data = request.get_json()
        user = User.query.get_or_404(user_id)
        
        user.is_active = not data.get('ban', True)
        db.session.commit()
        
        action = 'banned' if not user.is_active else 'unbanned'
        
        # Log the action
        audit_log = AuditLog(
            action=f'user_{action}',
            details=f"User {user.username} ({user.discord_id}) was {action}",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': f'User {action} successfully',
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/users/<int:user_id>/admin', methods=['POST'])
def toggle_admin(user_id):
    """Toggle admin status for a user"""
    try:
        data = request.get_json()
        user = User.query.get_or_404(user_id)
        
        user.is_admin = data.get('is_admin', not user.is_admin)
        db.session.commit()
        
        action = 'granted' if user.is_admin else 'revoked'
        
        # Log the action
        audit_log = AuditLog(
            action=f'admin_{action}',
            details=f"Admin privileges {action} for user {user.username} ({user.discord_id})",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': f'Admin privileges {action} successfully',
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error toggling admin: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/audit-logs', methods=['GET'])
def get_audit_logs():
    """Get audit logs with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        action = request.args.get('action')
        user_id = request.args.get('user_id', type=int)
        
        query = AuditLog.query
        
        if action:
            query = query.filter_by(action=action)
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        logs = query.order_by(AuditLog.timestamp.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'logs': [log.to_dict() for log in logs.items],
            'total': logs.total,
            'pages': logs.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error getting audit logs: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/system/info', methods=['GET'])
def get_system_info():
    """Get system information"""
    try:
        import psutil
        import platform
        
        # Get system info
        system_info = {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_usage': psutil.disk_usage('/').percent
        }
        
        # Get database info
        db_info = {
            'total_users': User.query.count(),
            'total_servers': MinecraftServer.query.count(),
            'database_size': 'N/A'  # Would need specific implementation for different DB types
        }
        
        return jsonify({
            'system': system_info,
            'database': db_info
        })
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/backup/create', methods=['POST'])
def create_backup():
    """Create a database backup"""
    try:
        import shutil
        from datetime import datetime
        
        # Create backup filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}.db"
        
        # For SQLite, just copy the file
        db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        backup_path = f"/tmp/{backup_filename}"
        
        shutil.copy2(db_path, backup_path)
        
        # Log the action
        audit_log = AuditLog(
            action='backup_created',
            details=f"Database backup created: {backup_filename}",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': 'Backup created successfully',
            'filename': backup_filename,
            'path': backup_path
        })
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/maintenance/mode', methods=['POST'])
def toggle_maintenance_mode():
    """Toggle maintenance mode"""
    try:
        data = request.get_json()
        maintenance_mode = data.get('enabled', False)
        
        # This would typically set a flag in the database or config
        # For now, we'll just log it
        audit_log = AuditLog(
            action='maintenance_mode',
            details=f"Maintenance mode {'enabled' if maintenance_mode else 'disabled'}",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': f"Maintenance mode {'enabled' if maintenance_mode else 'disabled'}",
            'maintenance_mode': maintenance_mode
        })
        
    except Exception as e:
        logger.error(f"Error toggling maintenance mode: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_bp.route('/broadcast', methods=['POST'])
def broadcast_message():
    """Broadcast a message to all Minecraft servers"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        servers = MinecraftServer.query.filter_by(is_active=True).all()
        results = {}
        
        for server in servers:
            import asyncio
            success = asyncio.run(minecraft.broadcast_message(
                message,
                rcon_host=server.rcon_host,
                rcon_port=server.rcon_port,
                rcon_password=server.rcon_password
            ))
            results[server.name] = success
        
        # Log the action
        audit_log = AuditLog(
            action='broadcast_message',
            details=f"Broadcasted message: {message}",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': 'Broadcast sent',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        return jsonify({'error': 'Internal server error'}), 500

