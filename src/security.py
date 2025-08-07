import hashlib
import secrets
import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from src.models.database import User, AuditLog, db
import logging
import re
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

class SecurityManager:
    """Comprehensive security manager for the Discord bot ecosystem"""
    
    def __init__(self):
        self.rate_limit_storage = defaultdict(list)
        self.failed_attempts = defaultdict(int)
        self.blocked_ips = set()
        
    def generate_secure_token(self, length=32):
        """Generate a cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    def hash_password(self, password):
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt)
    
    def verify_password(self, password, hashed):
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    
    def generate_jwt_token(self, user_id, expires_in_hours=24):
        """Generate a JWT token for user authentication"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=expires_in_hours),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    
    def verify_jwt_token(self, token):
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def validate_discord_id(self, discord_id):
        """Validate Discord ID format"""
        if not isinstance(discord_id, str):
            return False
        if not re.match(r'^\d{17,19}$', discord_id):
            return False
        return True
    
    def validate_minecraft_uuid(self, uuid):
        """Validate Minecraft UUID format"""
        if not isinstance(uuid, str):
            return False
        # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', uuid.lower()):
            return False
        return True
    
    def sanitize_input(self, input_string, max_length=255):
        """Sanitize user input to prevent injection attacks"""
        if not isinstance(input_string, str):
            return ""
        
        # Remove potential SQL injection characters
        sanitized = re.sub(r'[;\'"\\]', '', input_string)
        
        # Remove potential XSS characters
        sanitized = re.sub(r'[<>]', '', sanitized)
        
        # Limit length
        sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    def rate_limit(self, key, max_requests=100, window_minutes=15):
        """Implement rate limiting"""
        current_time = time.time()
        window_start = current_time - (window_minutes * 60)
        
        # Clean old requests
        self.rate_limit_storage[key] = [
            timestamp for timestamp in self.rate_limit_storage[key]
            if timestamp > window_start
        ]
        
        # Check if limit exceeded
        if len(self.rate_limit_storage[key]) >= max_requests:
            return False
        
        # Add current request
        self.rate_limit_storage[key].append(current_time)
        return True
    
    def check_ip_blocked(self, ip_address):
        """Check if IP address is blocked"""
        return ip_address in self.blocked_ips
    
    def block_ip(self, ip_address, reason="Security violation"):
        """Block an IP address"""
        self.blocked_ips.add(ip_address)
        logger.warning(f"IP {ip_address} blocked: {reason}")
    
    def record_failed_attempt(self, identifier, ip_address):
        """Record a failed authentication attempt"""
        self.failed_attempts[identifier] += 1
        
        # Block after 5 failed attempts
        if self.failed_attempts[identifier] >= 5:
            self.block_ip(ip_address, f"Too many failed attempts for {identifier}")
            
        # Log the attempt
        audit_log = AuditLog(
            action='failed_auth_attempt',
            details=f"Failed attempt for {identifier}",
            ip_address=ip_address
        )
        db.session.add(audit_log)
        db.session.commit()
    
    def validate_coin_amount(self, amount):
        """Validate coin amount for transactions"""
        if not isinstance(amount, int):
            return False
        if amount < -1000000 or amount > 1000000:  # Reasonable limits
            return False
        return True
    
    def validate_purchase_data(self, data):
        """Validate purchase data"""
        required_fields = ['user_id', 'item_id', 'quantity']
        
        for field in required_fields:
            if field not in data:
                return False, f"Missing field: {field}"
        
        if not isinstance(data['user_id'], int) or data['user_id'] <= 0:
            return False, "Invalid user_id"
        
        if not isinstance(data['item_id'], int) or data['item_id'] <= 0:
            return False, "Invalid item_id"
        
        if not isinstance(data['quantity'], int) or data['quantity'] <= 0 or data['quantity'] > 100:
            return False, "Invalid quantity (1-100)"
        
        return True, "Valid"
    
    def encrypt_sensitive_data(self, data):
        """Encrypt sensitive data (placeholder - implement proper encryption)"""
        # In production, use proper encryption like Fernet
        return hashlib.sha256(data.encode()).hexdigest()
    
    def audit_log(self, user_id, action, details, ip_address=None):
        """Create an audit log entry"""
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address
        )
        db.session.add(log_entry)
        db.session.commit()

# Global security manager instance
security_manager = SecurityManager()

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = security_manager.verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Add user info to request context
        request.user_id = payload['user_id']
        return f(*args, **kwargs)
    
    return decorated_function

def require_admin(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check authentication
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = security_manager.verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Check if user is admin
        user = User.query.get(payload['user_id'])
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin privileges required'}), 403
        
        request.user_id = payload['user_id']
        return f(*args, **kwargs)
    
    return decorated_function

def rate_limit_decorator(max_requests=100, window_minutes=15):
    """Decorator for rate limiting"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use IP address as key
            key = request.remote_addr
            
            if not security_manager.rate_limit(key, max_requests, window_minutes):
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def security_check(f):
    """General security check decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip_address = request.remote_addr
        
        # Check if IP is blocked
        if security_manager.check_ip_blocked(ip_address):
            return jsonify({'error': 'Access denied'}), 403
        
        # Basic rate limiting
        if not security_manager.rate_limit(ip_address):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        return f(*args, **kwargs)
    
    return decorated_function

def validate_request_data(schema):
    """Decorator to validate request data against a schema"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if not data:
                return jsonify({'error': 'JSON data required'}), 400
            
            # Validate against schema
            for field, validator in schema.items():
                if field not in data:
                    if validator.get('required', False):
                        return jsonify({'error': f'Missing required field: {field}'}), 400
                    continue
                
                value = data[field]
                field_type = validator.get('type')
                
                if field_type and not isinstance(value, field_type):
                    return jsonify({'error': f'Invalid type for {field}'}), 400
                
                if 'min_length' in validator and len(str(value)) < validator['min_length']:
                    return jsonify({'error': f'{field} too short'}), 400
                
                if 'max_length' in validator and len(str(value)) > validator['max_length']:
                    return jsonify({'error': f'{field} too long'}), 400
                
                if 'min_value' in validator and value < validator['min_value']:
                    return jsonify({'error': f'{field} too small'}), 400
                
                if 'max_value' in validator and value > validator['max_value']:
                    return jsonify({'error': f'{field} too large'}), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Common validation schemas
USER_SCHEMA = {
    'username': {'type': str, 'required': True, 'min_length': 1, 'max_length': 100},
    'discord_id': {'type': str, 'required': True, 'min_length': 17, 'max_length': 19},
    'email': {'type': str, 'required': False, 'max_length': 255}
}

COIN_ADJUSTMENT_SCHEMA = {
    'amount': {'type': int, 'required': True, 'min_value': -1000000, 'max_value': 1000000},
    'description': {'type': str, 'required': False, 'max_length': 500}
}

ITEM_SCHEMA = {
    'name': {'type': str, 'required': True, 'min_length': 1, 'max_length': 100},
    'description': {'type': str, 'required': False, 'max_length': 1000},
    'price': {'type': int, 'required': True, 'min_value': 1, 'max_value': 1000000},
    'category': {'type': str, 'required': False, 'max_length': 50},
    'minecraft_command_template': {'type': str, 'required': True, 'min_length': 1, 'max_length': 500}
}

PURCHASE_SCHEMA = {
    'item_id': {'type': int, 'required': True, 'min_value': 1},
    'quantity': {'type': int, 'required': False, 'min_value': 1, 'max_value': 100}
}

