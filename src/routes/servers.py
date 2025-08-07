from flask import Blueprint, request, jsonify
from src.models.database import db, MinecraftServer, AuditLog
from src.minecraft_integration import MinecraftIntegration
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

servers_bp = Blueprint('servers', __name__)

@servers_bp.route('/servers', methods=['GET'])
def get_servers():
    """Get all Minecraft servers"""
    try:
        servers = MinecraftServer.query.all()
        servers_data = []
        
        for server in servers:
            server_dict = server.to_dict()
            # Add real-time status if available
            try:
                mc_integration = MinecraftIntegration()
                status = mc_integration.get_server_status(server.host, server.port)
                if status:
                    server_dict.update({
                        'status': 'online' if status.get('online') else 'offline',
                        'players_online': status.get('players', {}).get('online', 0),
                        'max_players': status.get('players', {}).get('max', 0),
                        'version': status.get('version', {}).get('name', 'Unknown'),
                        'latency': status.get('latency', 0),
                        'last_checked': datetime.utcnow().isoformat()
                    })
                else:
                    server_dict['status'] = 'offline'
            except Exception as e:
                logger.warning(f"Failed to get real-time status for server {server.id}: {e}")
                server_dict['status'] = 'unknown'
            
            servers_data.append(server_dict)
        
        return jsonify(servers_data)
        
    except Exception as e:
        logger.error(f"Error fetching servers: {e}")
        return jsonify({'error': 'Failed to fetch servers'}), 500

@servers_bp.route('/servers/<int:server_id>', methods=['GET'])
def get_server(server_id):
    """Get a specific server by ID"""
    try:
        server = MinecraftServer.query.get(server_id)
        if not server:
            return jsonify({'error': 'Server not found'}), 404
        
        server_dict = server.to_dict()
        
        # Get real-time status
        try:
            mc_integration = MinecraftIntegration()
            status = mc_integration.get_server_status(server.host, server.port)
            if status:
                server_dict.update({
                    'status': 'online' if status.get('online') else 'offline',
                    'players_online': status.get('players', {}).get('online', 0),
                    'max_players': status.get('players', {}).get('max', 0),
                    'version': status.get('version', {}).get('name', 'Unknown'),
                    'latency': status.get('latency', 0),
                    'last_checked': datetime.utcnow().isoformat()
                })
            else:
                server_dict['status'] = 'offline'
        except Exception as e:
            logger.warning(f"Failed to get real-time status for server {server_id}: {e}")
            server_dict['status'] = 'unknown'
        
        return jsonify(server_dict)
        
    except Exception as e:
        logger.error(f"Error fetching server {server_id}: {e}")
        return jsonify({'error': 'Failed to fetch server'}), 500

@servers_bp.route('/servers', methods=['POST'])
def create_server():
    """Create a new Minecraft server"""
    try:
        data = request.get_json()
        
        required_fields = ['name', 'host', 'port']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if server with same host:port already exists
        existing_server = MinecraftServer.query.filter_by(
            host=data['host'],
            port=data['port']
        ).first()
        
        if existing_server:
            return jsonify({'error': 'Server with this host and port already exists'}), 400
        
        server = MinecraftServer(
            name=data['name'],
            host=data['host'],
            port=data['port'],
            rcon_host=data.get('rcon_host', data['host']),
            rcon_port=data.get('rcon_port', 25575),
            rcon_password=data.get('rcon_password', ''),
            description=data.get('description', '')
        )
        
        db.session.add(server)
        db.session.commit()
        
        # Create audit log
        audit = AuditLog(
            user_id=data.get('admin_user_id'),
            action='server_created',
            details=f'{{"server_name": "{server.name}", "host": "{server.host}", "port": {server.port}}}',
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr)
        )
        db.session.add(audit)
        db.session.commit()
        
        return jsonify(server.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error creating server: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create server'}), 500

@servers_bp.route('/servers/<int:server_id>', methods=['PUT'])
def update_server(server_id):
    """Update a Minecraft server"""
    try:
        server = MinecraftServer.query.get(server_id)
        if not server:
            return jsonify({'error': 'Server not found'}), 404
        
        data = request.get_json()
        
        # Update fields
        if 'name' in data:
            server.name = data['name']
        if 'host' in data:
            server.host = data['host']
        if 'port' in data:
            server.port = data['port']
        if 'rcon_host' in data:
            server.rcon_host = data['rcon_host']
        if 'rcon_port' in data:
            server.rcon_port = data['rcon_port']
        if 'rcon_password' in data:
            server.rcon_password = data['rcon_password']
        if 'description' in data:
            server.description = data['description']
        
        server.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Create audit log
        audit = AuditLog(
            user_id=data.get('admin_user_id'),
            action='server_updated',
            details=f'{{"server_name": "{server.name}", "server_id": {server.id}}}',
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr)
        )
        db.session.add(audit)
        db.session.commit()
        
        return jsonify(server.to_dict())
        
    except Exception as e:
        logger.error(f"Error updating server {server_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update server'}), 500

@servers_bp.route('/servers/<int:server_id>', methods=['DELETE'])
def delete_server(server_id):
    """Delete a Minecraft server"""
    try:
        server = MinecraftServer.query.get(server_id)
        if not server:
            return jsonify({'error': 'Server not found'}), 404
        
        server_name = server.name
        
        db.session.delete(server)
        db.session.commit()
        
        # Create audit log
        audit = AuditLog(
            action='server_deleted',
            details=f'{{"server_name": "{server_name}", "server_id": {server_id}}}',
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr)
        )
        db.session.add(audit)
        db.session.commit()
        
        return jsonify({'message': 'Server deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting server {server_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete server'}), 500

@servers_bp.route('/servers/<int:server_id>/status', methods=['POST'])
def refresh_server_status(server_id):
    """Refresh server status manually"""
    try:
        server = MinecraftServer.query.get(server_id)
        if not server:
            return jsonify({'error': 'Server not found'}), 404
        
        mc_integration = MinecraftIntegration()
        status = mc_integration.get_server_status(server.host, server.port)
        
        if status:
            # Update server record with latest status
            server.status = 'online' if status.get('online') else 'offline'
            server.players_online = status.get('players', {}).get('online', 0)
            server.max_players = status.get('players', {}).get('max', 0)
            server.version = status.get('version', {}).get('name', 'Unknown')
            server.latency = status.get('latency', 0)
            server.last_checked = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                'status': server.status,
                'players_online': server.players_online,
                'max_players': server.max_players,
                'version': server.version,
                'latency': server.latency,
                'last_checked': server.last_checked.isoformat()
            })
        else:
            server.status = 'offline'
            server.last_checked = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'status': 'offline',
                'last_checked': server.last_checked.isoformat()
            })
        
    except Exception as e:
        logger.error(f"Error refreshing server status {server_id}: {e}")
        return jsonify({'error': 'Failed to refresh server status'}), 500

@servers_bp.route('/servers/<int:server_id>/execute', methods=['POST'])
def execute_command(server_id):
    """Execute a command on the server via RCON"""
    try:
        server = MinecraftServer.query.get(server_id)
        if not server:
            return jsonify({'error': 'Server not found'}), 404
        
        data = request.get_json()
        if 'command' not in data:
            return jsonify({'error': 'Command is required'}), 400
        
        command = data['command']
        
        mc_integration = MinecraftIntegration()
        result = mc_integration.execute_command(
            server.rcon_host or server.host,
            server.rcon_port,
            server.rcon_password,
            command
        )
        
        if result['success']:
            # Create audit log
            audit = AuditLog(
                user_id=data.get('admin_user_id'),
                action='server_command_executed',
                details=f'{{"server_name": "{server.name}", "command": "{command}", "result": "{result.get("response", "")}"}}',
                ip_address=request.headers.get('X-Forwarded-For', request.remote_addr)
            )
            db.session.add(audit)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'response': result.get('response', ''),
                'command': command
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Command execution failed'),
                'command': command
            }), 400
        
    except Exception as e:
        logger.error(f"Error executing command on server {server_id}: {e}")
        return jsonify({'error': 'Failed to execute command'}), 500

@servers_bp.route('/servers/stats', methods=['GET'])
def get_server_stats():
    """Get server statistics"""
    try:
        total_servers = MinecraftServer.query.count()
        
        # Get online servers (this would need real-time checking in production)
        online_servers = MinecraftServer.query.filter_by(status='online').count()
        
        # Total players across all servers
        total_players = db.session.query(
            db.func.sum(MinecraftServer.players_online)
        ).scalar() or 0
        
        # Total capacity
        total_capacity = db.session.query(
            db.func.sum(MinecraftServer.max_players)
        ).scalar() or 0
        
        # Average latency for online servers
        avg_latency = db.session.query(
            db.func.avg(MinecraftServer.latency)
        ).filter(MinecraftServer.status == 'online').scalar() or 0
        
        return jsonify({
            'total_servers': total_servers,
            'online_servers': online_servers,
            'offline_servers': total_servers - online_servers,
            'total_players': total_players,
            'total_capacity': total_capacity,
            'capacity_usage': (total_players / total_capacity * 100) if total_capacity > 0 else 0,
            'average_latency': round(avg_latency, 2)
        })
        
    except Exception as e:
        logger.error(f"Error fetching server stats: {e}")
        return jsonify({'error': 'Failed to fetch server statistics'}), 500

@servers_bp.route('/servers/bulk-status', methods=['POST'])
def refresh_all_servers():
    """Refresh status for all servers"""
    try:
        servers = MinecraftServer.query.all()
        mc_integration = MinecraftIntegration()
        
        updated_count = 0
        
        for server in servers:
            try:
                status = mc_integration.get_server_status(server.host, server.port)
                
                if status:
                    server.status = 'online' if status.get('online') else 'offline'
                    server.players_online = status.get('players', {}).get('online', 0)
                    server.max_players = status.get('players', {}).get('max', 0)
                    server.version = status.get('version', {}).get('name', 'Unknown')
                    server.latency = status.get('latency', 0)
                else:
                    server.status = 'offline'
                
                server.last_checked = datetime.utcnow()
                updated_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to update status for server {server.id}: {e}")
                server.status = 'unknown'
                server.last_checked = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': f'Updated status for {updated_count} servers',
            'updated_count': updated_count,
            'total_servers': len(servers)
        })
        
    except Exception as e:
        logger.error(f"Error refreshing all servers: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to refresh server statuses'}), 500

