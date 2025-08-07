import asyncio
import logging
from typing import Dict, Optional, Any
from mcstatus import JavaServer
from mcrcon import MCRcon
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
logger = logging.getLogger(__name__)

class MinecraftIntegration:
    """Handle Minecraft server integration including status checking and RCON commands"""
    
    def __init__(self):
        self.default_host = os.getenv('MINECRAFT_SERVER_HOST', 'localhost')
        self.default_port = int(os.getenv('MINECRAFT_SERVER_PORT', 25565))
        self.default_rcon_host = os.getenv('MINECRAFT_RCON_HOST', 'localhost')
        self.default_rcon_port = int(os.getenv('MINECRAFT_RCON_PORT', 25575))
        self.default_rcon_password = os.getenv('MINECRAFT_RCON_PASSWORD', '')
        
    async def get_server_status(self, host: str = None, port: int = None) -> Dict[str, Any]:
        """
        Get the status of a Minecraft server
        
        Args:
            host: Server hostname (defaults to configured host)
            port: Server port (defaults to configured port)
            
        Returns:
            Dictionary containing server status information
        """
        host = host or self.default_host
        port = port or self.default_port
        
        try:
            # Create server instance
            server = JavaServer.lookup(f"{host}:{port}")
            
            # Get server status with timeout
            status = await asyncio.wait_for(
                asyncio.to_thread(server.status),
                timeout=10.0
            )
            
            return {
                'online': True,
                'players_online': status.players.online,
                'max_players': status.players.max,
                'version': status.version.name,
                'description': status.description,
                'latency': status.latency,
                'host': host,
                'port': port
            }
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout while checking server status for {host}:{port}")
            return {
                'online': False,
                'error': 'Timeout',
                'host': host,
                'port': port
            }
        except Exception as e:
            logger.error(f"Error checking server status for {host}:{port}: {e}")
            return {
                'online': False,
                'error': str(e),
                'host': host,
                'port': port
            }
            
    async def get_server_players(self, host: str = None, port: int = None) -> Dict[str, Any]:
        """
        Get detailed player information from a Minecraft server
        
        Args:
            host: Server hostname (defaults to configured host)
            port: Server port (defaults to configured port)
            
        Returns:
            Dictionary containing player information
        """
        host = host or self.default_host
        port = port or self.default_port
        
        try:
            server = JavaServer.lookup(f"{host}:{port}")
            
            # Get server query (more detailed info)
            query = await asyncio.wait_for(
                asyncio.to_thread(server.query),
                timeout=10.0
            )
            
            return {
                'online': True,
                'players_online': query.players.online,
                'max_players': query.players.max,
                'player_names': query.players.names,
                'version': query.software.version,
                'software': query.software.brand,
                'map_name': query.map,
                'host': host,
                'port': port
            }
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout while querying server {host}:{port}")
            return {
                'online': False,
                'error': 'Timeout',
                'host': host,
                'port': port
            }
        except Exception as e:
            logger.error(f"Error querying server {host}:{port}: {e}")
            return {
                'online': False,
                'error': str(e),
                'host': host,
                'port': port
            }
            
    async def execute_command(self, command: str, rcon_host: str = None, rcon_port: int = None, rcon_password: str = None) -> bool:
        """
        Execute a command on the Minecraft server via RCON
        
        Args:
            command: The command to execute
            rcon_host: RCON hostname (defaults to configured host)
            rcon_port: RCON port (defaults to configured port)
            rcon_password: RCON password (defaults to configured password)
            
        Returns:
            True if command was executed successfully, False otherwise
        """
        rcon_host = rcon_host or self.default_rcon_host
        rcon_port = rcon_port or self.default_rcon_port
        rcon_password = rcon_password or self.default_rcon_password
        
        if not rcon_password:
            logger.error("RCON password not configured")
            return False
            
        try:
            # Execute RCON command in a separate thread
            result = await asyncio.wait_for(
                asyncio.to_thread(self._execute_rcon_command, command, rcon_host, rcon_port, rcon_password),
                timeout=30.0
            )
            
            logger.info(f"RCON command executed successfully: {command}")
            logger.debug(f"RCON response: {result}")
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout while executing RCON command: {command}")
            return False
        except Exception as e:
            logger.error(f"Error executing RCON command '{command}': {e}")
            return False
            
    def _execute_rcon_command(self, command: str, host: str, port: int, password: str) -> str:
        """
        Execute RCON command synchronously (to be run in thread)
        
        Args:
            command: The command to execute
            host: RCON hostname
            port: RCON port
            password: RCON password
            
        Returns:
            Command response string
        """
        with MCRcon(host, password, port) as mcr:
            response = mcr.command(command)
            return response
            
    async def execute_multiple_commands(self, commands: list, rcon_host: str = None, rcon_port: int = None, rcon_password: str = None) -> Dict[str, bool]:
        """
        Execute multiple commands on the Minecraft server
        
        Args:
            commands: List of commands to execute
            rcon_host: RCON hostname (defaults to configured host)
            rcon_port: RCON port (defaults to configured port)
            rcon_password: RCON password (defaults to configured password)
            
        Returns:
            Dictionary mapping commands to their success status
        """
        results = {}
        
        for command in commands:
            success = await self.execute_command(command, rcon_host, rcon_port, rcon_password)
            results[command] = success
            
            # Small delay between commands to avoid overwhelming the server
            await asyncio.sleep(0.1)
            
        return results
        
    async def give_item_to_player(self, player: str, item: str, amount: int = 1, rcon_host: str = None, rcon_port: int = None, rcon_password: str = None) -> bool:
        """
        Give an item to a player
        
        Args:
            player: Player username or UUID
            item: Item ID (e.g., 'diamond', 'iron_sword')
            amount: Amount to give (default: 1)
            rcon_host: RCON hostname (defaults to configured host)
            rcon_port: RCON port (defaults to configured port)
            rcon_password: RCON password (defaults to configured password)
            
        Returns:
            True if successful, False otherwise
        """
        command = f"give {player} {item} {amount}"
        return await self.execute_command(command, rcon_host, rcon_port, rcon_password)
        
    async def set_player_rank(self, player: str, rank: str, rcon_host: str = None, rcon_port: int = None, rcon_password: str = None) -> bool:
        """
        Set a player's rank (requires LuckPerms or similar plugin)
        
        Args:
            player: Player username or UUID
            rank: Rank name
            rcon_host: RCON hostname (defaults to configured host)
            rcon_port: RCON port (defaults to configured port)
            rcon_password: RCON password (defaults to configured password)
            
        Returns:
            True if successful, False otherwise
        """
        command = f"lp user {player} parent set {rank}"
        return await self.execute_command(command, rcon_host, rcon_port, rcon_password)
        
    async def broadcast_message(self, message: str, rcon_host: str = None, rcon_port: int = None, rcon_password: str = None) -> bool:
        """
        Broadcast a message to all players on the server
        
        Args:
            message: Message to broadcast
            rcon_host: RCON hostname (defaults to configured host)
            rcon_port: RCON port (defaults to configured port)
            rcon_password: RCON password (defaults to configured password)
            
        Returns:
            True if successful, False otherwise
        """
        command = f'say {message}'
        return await self.execute_command(command, rcon_host, rcon_port, rcon_password)
        
    async def get_server_performance(self, rcon_host: str = None, rcon_port: int = None, rcon_password: str = None) -> Dict[str, Any]:
        """
        Get server performance metrics (TPS, memory usage, etc.)
        
        Args:
            rcon_host: RCON hostname (defaults to configured host)
            rcon_port: RCON port (defaults to configured port)
            rcon_password: RCON password (defaults to configured password)
            
        Returns:
            Dictionary containing performance metrics
        """
        try:
            # Execute TPS command (works with most server software)
            tps_result = await self.execute_command("tps", rcon_host, rcon_port, rcon_password)
            
            # Parse TPS from response (this may vary depending on server software)
            # This is a simplified example - real implementation would need proper parsing
            performance_data = {
                'tps': None,
                'memory_usage': None,
                'uptime': None,
                'raw_response': tps_result
            }
            
            return performance_data
            
        except Exception as e:
            logger.error(f"Error getting server performance: {e}")
            return {
                'error': str(e)
            }
            
    async def update_all_server_status(self):
        """Update status for all configured servers"""
        try:
            from src.models.database import db, MinecraftServer
            
            servers = MinecraftServer.query.all()
            
            for server in servers:
                try:
                    status = await self.get_server_status(server.host, server.port)
                    
                    # Update server status in database
                    server.is_online = status['online']
                    server.players_online = status.get('players_online', 0)
                    server.max_players = status.get('max_players', 0)
                    server.version = status.get('version', '')
                    server.latency = status.get('latency', 0)
                    server.last_checked = datetime.utcnow()
                    
                    if not status['online']:
                        server.error_message = status.get('error', 'Unknown error')
                    else:
                        server.error_message = None
                    
                except Exception as e:
                    logger.error(f"Error updating status for server {server.name}: {e}")
                    server.is_online = False
                    server.error_message = str(e)
                    server.last_checked = datetime.utcnow()
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error in update_all_server_status: {e}")

    async def test_connection(self, host: str = None, port: int = None, rcon_host: str = None, rcon_port: int = None, rcon_password: str = None) -> Dict[str, Any]:
        """
        Test both server status and RCON connections
        
        Returns:
            Dictionary containing connection test results
        """
        results = {
            'server_status': False,
            'rcon_connection': False,
            'errors': []
        }
        
        # Test server status
        try:
            status = await self.get_server_status(host, port)
            results['server_status'] = status['online']
            if not status['online']:
                results['errors'].append(f"Server status error: {status.get('error', 'Unknown')}")
        except Exception as e:
            results['errors'].append(f"Server status test failed: {e}")
            
        # Test RCON connection
        try:
            rcon_success = await self.execute_command("list", rcon_host, rcon_port, rcon_password)
            results['rcon_connection'] = rcon_success
            if not rcon_success:
                results['errors'].append("RCON command execution failed")
        except Exception as e:
            results['errors'].append(f"RCON test failed: {e}")
            
        return results

