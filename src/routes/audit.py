from flask import Blueprint, request, jsonify, make_response
from src.models.database import db, AuditLog, User
from datetime import datetime, timedelta
import csv
import io
import logging

logger = logging.getLogger(__name__)

audit_bp = Blueprint('audit', __name__)

@audit_bp.route('/audit-logs', methods=['GET'])
def get_audit_logs():
    """Get audit logs with pagination and filtering"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        action_filter = request.args.get('action')
        user_id = request.args.get('user_id')
        date_range = request.args.get('date_range')
        search = request.args.get('search')
        
        query = AuditLog.query
        
        # Apply filters
        if action_filter and action_filter != 'all':
            query = query.filter(AuditLog.action == action_filter)
        
        if user_id and user_id != 'all':
            query = query.filter(AuditLog.user_id == user_id)
        
        if date_range and date_range != 'all':
            now = datetime.utcnow()
            if date_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_range == 'yesterday':
                start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                query = query.filter(AuditLog.timestamp >= start_date, AuditLog.timestamp < end_date)
            elif date_range == 'week':
                start_date = now - timedelta(days=7)
            elif date_range == 'month':
                start_date = now - timedelta(days=30)
            elif date_range == 'year':
                start_date = now - timedelta(days=365)
            
            if date_range != 'yesterday':
                query = query.filter(AuditLog.timestamp >= start_date)
        
        if search:
            query = query.join(User, AuditLog.user_id == User.id, isouter=True).filter(
                db.or_(
                    User.username.ilike(f'%{search}%'),
                    AuditLog.action.ilike(f'%{search}%'),
                    AuditLog.details.ilike(f'%{search}%'),
                    AuditLog.ip_address.ilike(f'%{search}%')
                )
            )
        
        # Order by timestamp (newest first)
        query = query.order_by(AuditLog.timestamp.desc())
        
        # Paginate
        offset = (page - 1) * limit
        logs = query.offset(offset).limit(limit).all()
        total = query.count()
        
        # Convert to dict with user information
        logs_data = []
        for log in logs:
            log_dict = log.to_dict()
            log_dict['user'] = log.user.to_dict() if log.user else None
            logs_data.append(log_dict)
        
        return jsonify({
            'logs': logs_data,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit
        })
        
    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        return jsonify({'error': 'Failed to fetch audit logs'}), 500

@audit_bp.route('/audit-logs/export', methods=['GET'])
def export_audit_logs():
    """Export audit logs as CSV"""
    try:
        action_filter = request.args.get('action')
        user_id = request.args.get('user_id')
        date_range = request.args.get('date_range')
        search = request.args.get('search')
        format_type = request.args.get('format', 'csv')
        
        query = AuditLog.query
        
        # Apply same filters as get_audit_logs
        if action_filter and action_filter != 'all':
            query = query.filter(AuditLog.action == action_filter)
        
        if user_id and user_id != 'all':
            query = query.filter(AuditLog.user_id == user_id)
        
        if date_range and date_range != 'all':
            now = datetime.utcnow()
            if date_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_range == 'yesterday':
                start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                query = query.filter(AuditLog.timestamp >= start_date, AuditLog.timestamp < end_date)
            elif date_range == 'week':
                start_date = now - timedelta(days=7)
            elif date_range == 'month':
                start_date = now - timedelta(days=30)
            elif date_range == 'year':
                start_date = now - timedelta(days=365)
            
            if date_range != 'yesterday':
                query = query.filter(AuditLog.timestamp >= start_date)
        
        if search:
            query = query.join(User, AuditLog.user_id == User.id, isouter=True).filter(
                db.or_(
                    User.username.ilike(f'%{search}%'),
                    AuditLog.action.ilike(f'%{search}%'),
                    AuditLog.details.ilike(f'%{search}%'),
                    AuditLog.ip_address.ilike(f'%{search}%')
                )
            )
        
        # Order by timestamp
        logs = query.order_by(AuditLog.timestamp.desc()).limit(10000).all()  # Limit for performance
        
        if format_type == 'csv':
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'Timestamp', 'User ID', 'Username', 'Action', 'Details', 'IP Address'
            ])
            
            # Write data
            for log in logs:
                writer.writerow([
                    log.timestamp.isoformat(),
                    log.user_id or '',
                    log.user.username if log.user else 'System',
                    log.action,
                    log.details or '',
                    log.ip_address or ''
                ])
            
            # Create response
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=audit-logs-{datetime.now().strftime("%Y%m%d")}.csv'
            
            return response
        
        else:
            return jsonify({'error': 'Unsupported format'}), 400
        
    except Exception as e:
        logger.error(f"Error exporting audit logs: {e}")
        return jsonify({'error': 'Failed to export audit logs'}), 500

@audit_bp.route('/audit-logs/stats', methods=['GET'])
def get_audit_stats():
    """Get audit log statistics"""
    try:
        # Total logs
        total_logs = AuditLog.query.count()
        
        # Logs by action type
        action_stats = db.session.query(
            AuditLog.action,
            db.func.count(AuditLog.id).label('count')
        ).group_by(AuditLog.action).order_by(
            db.func.count(AuditLog.id).desc()
        ).all()
        
        # Recent activity (last 24 hours)
        day_ago = datetime.utcnow() - timedelta(days=1)
        recent_logs = AuditLog.query.filter(AuditLog.timestamp >= day_ago).count()
        
        # User activity (top 10 most active users)
        user_activity = db.session.query(
            User.username,
            db.func.count(AuditLog.id).label('activity_count')
        ).join(AuditLog, User.id == AuditLog.user_id).group_by(
            User.id
        ).order_by(
            db.func.count(AuditLog.id).desc()
        ).limit(10).all()
        
        # System vs user actions
        system_actions = AuditLog.query.filter(AuditLog.user_id.is_(None)).count()
        user_actions = AuditLog.query.filter(AuditLog.user_id.isnot(None)).count()
        
        # Error rate (actions containing 'error' or 'failed')
        error_logs = AuditLog.query.filter(
            db.or_(
                AuditLog.action.like('%error%'),
                AuditLog.action.like('%failed%')
            )
        ).count()
        
        # Activity by hour (last 24 hours)
        hourly_activity = []
        for i in range(24):
            hour_start = (datetime.utcnow() - timedelta(hours=i+1)).replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            count = AuditLog.query.filter(
                AuditLog.timestamp >= hour_start,
                AuditLog.timestamp < hour_end
            ).count()
            hourly_activity.append({
                'hour': hour_start.strftime('%H:00'),
                'count': count
            })
        
        return jsonify({
            'total_logs': total_logs,
            'recent_logs': recent_logs,
            'system_actions': system_actions,
            'user_actions': user_actions,
            'error_logs': error_logs,
            'error_rate': (error_logs / total_logs * 100) if total_logs > 0 else 0,
            'action_stats': [
                {
                    'action': stat.action,
                    'count': stat.count
                }
                for stat in action_stats
            ],
            'user_activity': [
                {
                    'username': activity.username,
                    'activity_count': activity.activity_count
                }
                for activity in user_activity
            ],
            'hourly_activity': list(reversed(hourly_activity))  # Most recent first
        })
        
    except Exception as e:
        logger.error(f"Error fetching audit stats: {e}")
        return jsonify({'error': 'Failed to fetch audit statistics'}), 500

@audit_bp.route('/audit-logs', methods=['POST'])
def create_audit_log():
    """Create a new audit log entry"""
    try:
        data = request.get_json()
        
        required_fields = ['action']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Get IP address from request
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        audit_log = AuditLog(
            user_id=data.get('user_id'),
            action=data['action'],
            details=data.get('details'),
            ip_address=ip_address
        )
        
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify(audit_log.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error creating audit log: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create audit log'}), 500

@audit_bp.route('/audit-logs/cleanup', methods=['POST'])
def cleanup_old_logs():
    """Clean up old audit logs (admin only)"""
    try:
        data = request.get_json()
        days_to_keep = data.get('days_to_keep', 90)
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Delete old logs
        deleted_count = AuditLog.query.filter(
            AuditLog.timestamp < cutoff_date
        ).delete()
        
        db.session.commit()
        
        # Create audit log for this action
        cleanup_log = AuditLog(
            user_id=data.get('admin_user_id'),
            action='admin_action',
            details=f'{{"action": "audit_cleanup", "deleted_count": {deleted_count}, "days_kept": {days_to_keep}}}',
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr)
        )
        db.session.add(cleanup_log)
        db.session.commit()
        
        return jsonify({
            'message': f'Deleted {deleted_count} old audit logs',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up audit logs: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to cleanup audit logs'}), 500

def log_action(user_id, action, details=None, ip_address=None):
    """Helper function to create audit log entries"""
    try:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error logging action {action}: {e}")
        db.session.rollback()

