from flask import Blueprint, request, jsonify, redirect, session, url_for
from src.models.database import db, User, AuditLog
from src.security import security_manager, require_auth, require_admin, security_check
import requests
import os
import logging
from datetime import datetime

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# Discord OAuth2 configuration
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI')
DISCORD_API_ENDPOINT = 'https://discord.com/api/v10'

@auth_bp.route('/login', methods=['GET'])
@security_check
def discord_login():
    """Initiate Discord OAuth2 login"""
    try:
        # Generate state for CSRF protection
        state = security_manager.generate_secure_token()
        session['oauth_state'] = state
        
        # Discord OAuth2 URL
        discord_auth_url = (
            f"https://discord.com/api/oauth2/authorize"
            f"?client_id={DISCORD_CLIENT_ID}"
            f"&redirect_uri={DISCORD_REDIRECT_URI}"
            f"&response_type=code"
            f"&scope=identify%20email"
            f"&state={state}"
        )
        
        return jsonify({
            'auth_url': discord_auth_url,
            'state': state
        })
        
    except Exception as e:
        logger.error(f"Error initiating Discord login: {e}")
        return jsonify({'error': 'Authentication error'}), 500

@auth_bp.route('/callback', methods=['GET'])
@security_check
def discord_callback():
    """Handle Discord OAuth2 callback"""
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        
        # Verify state to prevent CSRF
        if not state or state != session.get('oauth_state'):
            return jsonify({'error': 'Invalid state parameter'}), 400
        
        if not code:
            return jsonify({'error': 'Authorization code not provided'}), 400
        
        # Exchange code for access token
        token_data = {
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': DISCORD_REDIRECT_URI
        }
        
        token_response = requests.post(
            f"{DISCORD_API_ENDPOINT}/oauth2/token",
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if not token_response.ok:
            logger.error(f"Discord token exchange failed: {token_response.text}")
            return jsonify({'error': 'Token exchange failed'}), 400
        
        token_json = token_response.json()
        access_token = token_json.get('access_token')
        
        # Get user information from Discord
        user_response = requests.get(
            f"{DISCORD_API_ENDPOINT}/users/@me",
            headers={'Authorization': f"Bearer {access_token}"}
        )
        
        if not user_response.ok:
            logger.error(f"Discord user fetch failed: {user_response.text}")
            return jsonify({'error': 'Failed to fetch user data'}), 400
        
        discord_user = user_response.json()
        discord_id = discord_user.get('id')
        username = discord_user.get('username')
        email = discord_user.get('email')
        
        # Validate Discord ID
        if not security_manager.validate_discord_id(discord_id):
            return jsonify({'error': 'Invalid Discord ID'}), 400
        
        # Get or create user
        user = User.query.filter_by(discord_id=discord_id).first()
        
        if not user:
            # Create new user
            user = User(
                discord_id=discord_id,
                username=security_manager.sanitize_input(username),
                email=security_manager.sanitize_input(email) if email else None
            )
            db.session.add(user)
            db.session.commit()
            
            # Log user creation
            security_manager.audit_log(
                user.id,
                'user_created',
                f"New user registered: {username}",
                request.remote_addr
            )
        else:
            # Update existing user info
            user.username = security_manager.sanitize_input(username)
            if email:
                user.email = security_manager.sanitize_input(email)
            db.session.commit()
            
            # Log login
            security_manager.audit_log(
                user.id,
                'user_login',
                f"User logged in: {username}",
                request.remote_addr
            )
        
        # Generate JWT token
        jwt_token = security_manager.generate_jwt_token(user.id)
        
        # Clear OAuth state
        session.pop('oauth_state', None)
        
        return jsonify({
            'token': jwt_token,
            'user': user.to_dict(),
            'message': 'Login successful'
        })
        
    except Exception as e:
        logger.error(f"Error in Discord callback: {e}")
        return jsonify({'error': 'Authentication failed'}), 500

@auth_bp.route('/verify', methods=['GET'])
@require_auth
def verify_token():
    """Verify JWT token and return user info"""
    try:
        user = User.query.get(request.user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'valid': True,
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return jsonify({'error': 'Token verification failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """Logout user (invalidate token on client side)"""
    try:
        user = User.query.get(request.user_id)
        if user:
            security_manager.audit_log(
                user.id,
                'user_logout',
                f"User logged out: {user.username}",
                request.remote_addr
            )
        
        return jsonify({'message': 'Logout successful'})
        
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return jsonify({'error': 'Logout failed'}), 500

@auth_bp.route('/profile', methods=['GET'])
@require_auth
def get_profile():
    """Get user profile information"""
    try:
        user = User.query.get(request.user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get additional profile data
        from src.models.database import Transaction, Purchase
        
        # Recent transactions
        recent_transactions = Transaction.query.filter_by(
            user_id=user.id
        ).order_by(Transaction.created_at.desc()).limit(5).all()
        
        # Recent purchases
        recent_purchases = Purchase.query.filter_by(
            user_id=user.id
        ).order_by(Purchase.created_at.desc()).limit(5).all()
        
        profile_data = user.to_dict()
        profile_data.update({
            'recent_transactions': [t.to_dict() for t in recent_transactions],
            'recent_purchases': [p.to_dict() for p in recent_purchases],
            'total_transactions': Transaction.query.filter_by(user_id=user.id).count(),
            'total_purchases': Purchase.query.filter_by(user_id=user.id).count()
        })
        
        return jsonify(profile_data)
        
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        return jsonify({'error': 'Failed to get profile'}), 500

@auth_bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile():
    """Update user profile"""
    try:
        data = request.get_json()
        user = User.query.get(request.user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update allowed fields
        if 'minecraft_uuid' in data:
            minecraft_uuid = data['minecraft_uuid'].strip()
            if minecraft_uuid:
                if not security_manager.validate_minecraft_uuid(minecraft_uuid):
                    return jsonify({'error': 'Invalid Minecraft UUID format'}), 400
                user.minecraft_uuid = minecraft_uuid
            else:
                user.minecraft_uuid = None
        
        if 'email' in data:
            email = security_manager.sanitize_input(data['email'])
            if email and '@' in email:  # Basic email validation
                user.email = email
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Log profile update
        security_manager.audit_log(
            user.id,
            'profile_updated',
            "User profile updated",
            request.remote_addr
        )
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return jsonify({'error': 'Failed to update profile'}), 500

@auth_bp.route('/admin/check', methods=['GET'])
@require_admin
def check_admin():
    """Check if user has admin privileges"""
    try:
        user = User.query.get(request.user_id)
        return jsonify({
            'is_admin': True,
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return jsonify({'error': 'Failed to check admin status'}), 500

@auth_bp.route('/sessions', methods=['GET'])
@require_auth
def get_active_sessions():
    """Get active sessions for user (placeholder)"""
    try:
        # In a real implementation, you'd track active sessions
        # For now, just return current session info
        user = User.query.get(request.user_id)
        
        sessions = [{
            'id': 'current',
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'Unknown'),
            'created_at': datetime.utcnow().isoformat(),
            'is_current': True
        }]
        
        return jsonify({'sessions': sessions})
        
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        return jsonify({'error': 'Failed to get sessions'}), 500

@auth_bp.route('/security/audit-logs', methods=['GET'])
@require_auth
def get_user_audit_logs():
    """Get audit logs for the current user"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        logs = AuditLog.query.filter_by(
            user_id=request.user_id
        ).order_by(AuditLog.timestamp.desc()).paginate(
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
        return jsonify({'error': 'Failed to get audit logs'}), 500

@auth_bp.route('/security/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change user password (placeholder - Discord OAuth doesn't use passwords)"""
    # This would be used if we implemented local authentication
    return jsonify({
        'message': 'Password change not available with Discord authentication'
    }), 400

@auth_bp.route('/security/two-factor', methods=['POST'])
@require_auth
def setup_two_factor():
    """Setup two-factor authentication (placeholder)"""
    # This would be implemented for enhanced security
    return jsonify({
        'message': 'Two-factor authentication setup not yet implemented'
    }), 501

