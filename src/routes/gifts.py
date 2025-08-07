from flask import Blueprint, request, jsonify
from src.models.database import db, Gift, User, Transaction, AuditLog
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

gifts_bp = Blueprint('gifts', __name__)

@gifts_bp.route('/gifts', methods=['GET'])
def get_gifts():
    """Get all gifts with pagination and filtering"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        status_filter = request.args.get('status')
        user_id = request.args.get('user_id')
        
        query = Gift.query
        
        # Apply filters
        if status_filter and status_filter != 'all':
            query = query.filter(Gift.status == status_filter)
        
        if user_id and user_id != 'all':
            query = query.filter(
                (Gift.sender_id == user_id) | (Gift.recipient_id == user_id)
            )
        
        # Order by creation date (newest first)
        query = query.order_by(Gift.created_at.desc())
        
        # Paginate
        offset = (page - 1) * limit
        gifts = query.offset(offset).limit(limit).all()
        total = query.count()
        
        # Convert to dict with user information
        gifts_data = []
        for gift in gifts:
            gift_dict = gift.to_dict()
            gift_dict['sender'] = gift.sender.to_dict() if gift.sender else None
            gift_dict['recipient'] = gift.recipient.to_dict() if gift.recipient else None
            gifts_data.append(gift_dict)
        
        return jsonify({
            'gifts': gifts_data,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit
        })
        
    except Exception as e:
        logger.error(f"Error fetching gifts: {e}")
        return jsonify({'error': 'Failed to fetch gifts'}), 500

@gifts_bp.route('/gifts/<int:gift_id>', methods=['GET'])
def get_gift(gift_id):
    """Get a specific gift by ID"""
    try:
        gift = Gift.query.get(gift_id)
        if not gift:
            return jsonify({'error': 'Gift not found'}), 404
        
        gift_dict = gift.to_dict()
        gift_dict['sender'] = gift.sender.to_dict() if gift.sender else None
        gift_dict['recipient'] = gift.recipient.to_dict() if gift.recipient else None
        
        return jsonify(gift_dict)
        
    except Exception as e:
        logger.error(f"Error fetching gift {gift_id}: {e}")
        return jsonify({'error': 'Failed to fetch gift'}), 500

@gifts_bp.route('/gifts/send', methods=['POST'])
def send_gift():
    """Send a gift from one user to another"""
    try:
        data = request.get_json()
        
        required_fields = ['sender_id', 'recipient_id', 'amount']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        sender_id = data['sender_id']
        recipient_id = data['recipient_id']
        amount = int(data['amount'])
        message = data.get('message', '')
        
        # Validation
        if amount <= 0:
            return jsonify({'error': 'Amount must be positive'}), 400
        
        if sender_id == recipient_id:
            return jsonify({'error': 'Cannot send gift to yourself'}), 400
        
        # Get users
        sender = User.query.get(sender_id)
        recipient = User.query.get(recipient_id)
        
        if not sender:
            return jsonify({'error': 'Sender not found'}), 404
        
        if not recipient:
            return jsonify({'error': 'Recipient not found'}), 404
        
        # Check if sender has enough coins
        if sender.coins < amount:
            return jsonify({'error': 'Insufficient coins'}), 400
        
        # Create gift record
        gift = Gift(
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=amount,
            message=message,
            status='completed',
            processed_at=datetime.utcnow()
        )
        
        # Transfer coins
        sender.coins -= amount
        recipient.coins += amount
        
        # Create transaction records
        sender_transaction = Transaction(
            user_id=sender_id,
            transaction_type='gift_sent',
            amount=-amount,
            description=f'Gift sent to {recipient.username}',
            reference_id=f'gift_{gift.id}'
        )
        
        recipient_transaction = Transaction(
            user_id=recipient_id,
            transaction_type='gift_received',
            amount=amount,
            description=f'Gift received from {sender.username}',
            reference_id=f'gift_{gift.id}'
        )
        
        # Create audit log entries
        sender_audit = AuditLog(
            user_id=sender_id,
            action='gift_sent',
            details=f'{{"amount": {amount}, "recipient": "{recipient.username}", "message": "{message}"}}'
        )
        
        recipient_audit = AuditLog(
            user_id=recipient_id,
            action='gift_received',
            details=f'{{"amount": {amount}, "sender": "{sender.username}", "message": "{message}"}}'
        )
        
        db.session.add(gift)
        db.session.add(sender_transaction)
        db.session.add(recipient_transaction)
        db.session.add(sender_audit)
        db.session.add(recipient_audit)
        db.session.commit()
        
        # Return gift with user information
        gift_dict = gift.to_dict()
        gift_dict['sender'] = sender.to_dict()
        gift_dict['recipient'] = recipient.to_dict()
        
        return jsonify(gift_dict), 201
        
    except Exception as e:
        logger.error(f"Error sending gift: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to send gift'}), 500

@gifts_bp.route('/gifts/admin-send', methods=['POST'])
def admin_send_gift():
    """Send a gift from admin to a user"""
    try:
        data = request.get_json()
        
        required_fields = ['recipient_id', 'amount']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        recipient_id = int(data['recipient_id'])
        amount = int(data['amount'])
        message = data.get('message', '')
        
        # Validation
        if amount <= 0:
            return jsonify({'error': 'Amount must be positive'}), 400
        
        # Get recipient
        recipient = User.query.get(recipient_id)
        if not recipient:
            return jsonify({'error': 'Recipient not found'}), 404
        
        # Create gift record (no sender for admin gifts)
        gift = Gift(
            sender_id=None,  # Admin gift
            recipient_id=recipient_id,
            amount=amount,
            message=message,
            status='completed',
            processed_at=datetime.utcnow()
        )
        
        # Add coins to recipient
        recipient.coins += amount
        
        # Create transaction record
        transaction = Transaction(
            user_id=recipient_id,
            transaction_type='admin_add',
            amount=amount,
            description=f'Administrative gift: {message}' if message else 'Administrative gift',
            reference_id=f'admin_gift_{gift.id}'
        )
        
        # Create audit log entry
        audit = AuditLog(
            user_id=recipient_id,
            action='gift_received',
            details=f'{{"amount": {amount}, "sender": "Admin", "message": "{message}"}}'
        )
        
        db.session.add(gift)
        db.session.add(transaction)
        db.session.add(audit)
        db.session.commit()
        
        # Return gift with user information
        gift_dict = gift.to_dict()
        gift_dict['sender'] = None
        gift_dict['recipient'] = recipient.to_dict()
        
        return jsonify(gift_dict), 201
        
    except Exception as e:
        logger.error(f"Error sending admin gift: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to send gift'}), 500

@gifts_bp.route('/gifts/<int:gift_id>/cancel', methods=['POST'])
def cancel_gift(gift_id):
    """Cancel a pending gift"""
    try:
        gift = Gift.query.get(gift_id)
        if not gift:
            return jsonify({'error': 'Gift not found'}), 404
        
        if gift.status != 'pending':
            return jsonify({'error': 'Can only cancel pending gifts'}), 400
        
        # Update gift status
        gift.status = 'cancelled'
        gift.processed_at = datetime.utcnow()
        
        # If there was a sender, refund the coins
        if gift.sender_id:
            sender = User.query.get(gift.sender_id)
            if sender:
                sender.coins += gift.amount
                
                # Create refund transaction
                refund_transaction = Transaction(
                    user_id=gift.sender_id,
                    transaction_type='refund',
                    amount=gift.amount,
                    description=f'Gift cancelled - refund to {sender.username}',
                    reference_id=f'gift_cancel_{gift.id}'
                )
                db.session.add(refund_transaction)
        
        # Create audit log entry
        audit = AuditLog(
            user_id=gift.sender_id,
            action='admin_action',
            details=f'{{"action": "gift_cancelled", "gift_id": {gift.id}, "amount": {gift.amount}}}'
        )
        db.session.add(audit)
        
        db.session.commit()
        
        # Return updated gift
        gift_dict = gift.to_dict()
        gift_dict['sender'] = gift.sender.to_dict() if gift.sender else None
        gift_dict['recipient'] = gift.recipient.to_dict() if gift.recipient else None
        
        return jsonify(gift_dict)
        
    except Exception as e:
        logger.error(f"Error cancelling gift {gift_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to cancel gift'}), 500

@gifts_bp.route('/gifts/stats', methods=['GET'])
def get_gift_stats():
    """Get gift statistics"""
    try:
        # Total gifts
        total_gifts = Gift.query.count()
        
        # Gifts by status
        completed_gifts = Gift.query.filter_by(status='completed').count()
        pending_gifts = Gift.query.filter_by(status='pending').count()
        cancelled_gifts = Gift.query.filter_by(status='cancelled').count()
        
        # Total value of completed gifts
        total_value = db.session.query(db.func.sum(Gift.amount)).filter(
            Gift.status == 'completed'
        ).scalar() or 0
        
        # Recent activity (last 7 days)
        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_gifts = Gift.query.filter(Gift.created_at >= week_ago).count()
        
        # Top gift senders (excluding admin gifts)
        top_senders = db.session.query(
            User.username,
            db.func.count(Gift.id).label('gift_count'),
            db.func.sum(Gift.amount).label('total_sent')
        ).join(Gift, User.id == Gift.sender_id).filter(
            Gift.status == 'completed'
        ).group_by(User.id).order_by(
            db.func.sum(Gift.amount).desc()
        ).limit(5).all()
        
        # Top gift recipients
        top_recipients = db.session.query(
            User.username,
            db.func.count(Gift.id).label('gift_count'),
            db.func.sum(Gift.amount).label('total_received')
        ).join(Gift, User.id == Gift.recipient_id).filter(
            Gift.status == 'completed'
        ).group_by(User.id).order_by(
            db.func.sum(Gift.amount).desc()
        ).limit(5).all()
        
        return jsonify({
            'total_gifts': total_gifts,
            'completed_gifts': completed_gifts,
            'pending_gifts': pending_gifts,
            'cancelled_gifts': cancelled_gifts,
            'total_value': total_value,
            'recent_gifts': recent_gifts,
            'top_senders': [
                {
                    'username': sender.username,
                    'gift_count': sender.gift_count,
                    'total_sent': sender.total_sent
                }
                for sender in top_senders
            ],
            'top_recipients': [
                {
                    'username': recipient.username,
                    'gift_count': recipient.gift_count,
                    'total_received': recipient.total_received
                }
                for recipient in top_recipients
            ]
        })
        
    except Exception as e:
        logger.error(f"Error fetching gift stats: {e}")
        return jsonify({'error': 'Failed to fetch gift statistics'}), 500

@gifts_bp.route('/gifts/user/<int:user_id>', methods=['GET'])
def get_user_gifts(user_id):
    """Get gifts for a specific user (sent and received)"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get sent gifts
        sent_gifts = Gift.query.filter_by(sender_id=user_id).order_by(Gift.created_at.desc()).all()
        
        # Get received gifts
        received_gifts = Gift.query.filter_by(recipient_id=user_id).order_by(Gift.created_at.desc()).all()
        
        # Convert to dict with user information
        sent_data = []
        for gift in sent_gifts:
            gift_dict = gift.to_dict()
            gift_dict['recipient'] = gift.recipient.to_dict()
            sent_data.append(gift_dict)
        
        received_data = []
        for gift in received_gifts:
            gift_dict = gift.to_dict()
            gift_dict['sender'] = gift.sender.to_dict() if gift.sender else None
            received_data.append(gift_dict)
        
        return jsonify({
            'user': user.to_dict(),
            'sent_gifts': sent_data,
            'received_gifts': received_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching user gifts for {user_id}: {e}")
        return jsonify({'error': 'Failed to fetch user gifts'}), 500

