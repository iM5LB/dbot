from flask import Blueprint, request, jsonify, current_app
from src.models.database import db, User, PaymentRecord, Transaction, AuditLog
import stripe
import os
import logging
import json
from datetime import datetime

payments_bp = Blueprint('payments', __name__)
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

@payments_bp.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """Create a Stripe payment intent for coin purchase"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount_usd = data.get('amount_usd')  # Amount in USD
        coins_to_purchase = data.get('coins')
        
        if not all([user_id, amount_usd, coins_to_purchase]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Get user
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        # Convert USD to cents for Stripe
        amount_cents = int(float(amount_usd) * 100)
        
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='usd',
            metadata={
                'user_id': str(user_id),
                'discord_id': user.discord_id,
                'username': user.username,
                'coins_to_purchase': str(coins_to_purchase)
            },
            description=f"Coin purchase for {user.username}"
        )
        
        # Create payment record
        payment_record = PaymentRecord(
            user_id=user_id,
            stripe_payment_id=intent.id,
            amount_cents=amount_cents,
            currency='USD',
            status='pending',
            payment_metadata=json.dumps({
                'coins_to_purchase': coins_to_purchase,
                'amount_usd': amount_usd
            })
        )
        
        db.session.add(payment_record)
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            user_id=user_id,
            action='payment_intent_created',
            details=f"Payment intent created for ${amount_usd} ({coins_to_purchase} coins)",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        return jsonify({'error': 'Payment processing error'}), 500
    except Exception as e:
        logger.error(f"Error creating payment intent: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_successful_payment(payment_intent)
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        handle_failed_payment(payment_intent)
    else:
        logger.info(f"Unhandled event type: {event['type']}")
    
    return jsonify({'status': 'success'})

def handle_successful_payment(payment_intent):
    """Handle successful payment and award coins"""
    try:
        payment_id = payment_intent['id']
        
        # Find payment record
        payment_record = PaymentRecord.query.filter_by(stripe_payment_id=payment_id).first()
        if not payment_record:
            logger.error(f"Payment record not found for {payment_id}")
            return
            
        # Update payment status
        payment_record.status = 'succeeded'
        payment_record.updated_at = datetime.utcnow()
        
        # Get user and metadata
        user = User.query.get(payment_record.user_id)
        if not user:
            logger.error(f"User not found for payment {payment_id}")
            return
            
        metadata = json.loads(payment_record.payment_metadata) if payment_record.payment_metadata else {}
        coins_to_award = int(metadata.get('coins_to_purchase', 0))
        
        if coins_to_award > 0:
            # Award coins to user
            user.coins += coins_to_award
            
            # Create transaction record
            transaction = Transaction(
                user_id=user.id,
                transaction_type='purchase',
                amount=coins_to_award,
                description=f"Coin purchase via payment (${payment_record.amount_cents / 100})",
                reference_id=payment_id
            )
            
            db.session.add(transaction)
            
            # Log the action
            audit_log = AuditLog(
                user_id=user.id,
                action='payment_succeeded',
                details=f"Payment succeeded: {coins_to_award} coins awarded for ${payment_record.amount_cents / 100}"
            )
            db.session.add(audit_log)
            
        db.session.commit()
        logger.info(f"Successfully processed payment {payment_id} for user {user.username}")
        
    except Exception as e:
        logger.error(f"Error handling successful payment: {e}")
        db.session.rollback()

def handle_failed_payment(payment_intent):
    """Handle failed payment"""
    try:
        payment_id = payment_intent['id']
        
        # Find payment record
        payment_record = PaymentRecord.query.filter_by(stripe_payment_id=payment_id).first()
        if not payment_record:
            logger.error(f"Payment record not found for {payment_id}")
            return
            
        # Update payment status
        payment_record.status = 'failed'
        payment_record.updated_at = datetime.utcnow()
        
        # Log the action
        audit_log = AuditLog(
            user_id=payment_record.user_id,
            action='payment_failed',
            details=f"Payment failed for ${payment_record.amount_cents / 100}"
        )
        db.session.add(audit_log)
        db.session.commit()
        
        logger.info(f"Payment failed: {payment_id}")
        
    except Exception as e:
        logger.error(f"Error handling failed payment: {e}")
        db.session.rollback()

@payments_bp.route('/payment-status/<payment_intent_id>', methods=['GET'])
def get_payment_status(payment_intent_id):
    """Get payment status"""
    try:
        payment_record = PaymentRecord.query.filter_by(stripe_payment_id=payment_intent_id).first()
        
        if not payment_record:
            return jsonify({'error': 'Payment not found'}), 404
            
        return jsonify({
            'status': payment_record.status,
            'amount_cents': payment_record.amount_cents,
            'currency': payment_record.currency,
            'created_at': payment_record.created_at.isoformat(),
            'updated_at': payment_record.updated_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting payment status: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@payments_bp.route('/coin-packages', methods=['GET'])
def get_coin_packages():
    """Get available coin packages"""
    packages = [
        {
            'id': 'starter',
            'name': 'Starter Pack',
            'coins': 100,
            'price_usd': 0.99,
            'bonus': 0,
            'popular': False
        },
        {
            'id': 'basic',
            'name': 'Basic Pack',
            'coins': 500,
            'price_usd': 4.99,
            'bonus': 50,
            'popular': False
        },
        {
            'id': 'premium',
            'name': 'Premium Pack',
            'coins': 1000,
            'price_usd': 9.99,
            'bonus': 150,
            'popular': True
        },
        {
            'id': 'ultimate',
            'name': 'Ultimate Pack',
            'coins': 2500,
            'price_usd': 19.99,
            'bonus': 500,
            'popular': False
        },
        {
            'id': 'mega',
            'name': 'Mega Pack',
            'coins': 5000,
            'price_usd': 39.99,
            'bonus': 1500,
            'popular': False
        }
    ]
    
    return jsonify({'packages': packages})

@payments_bp.route('/payment-history/<int:user_id>', methods=['GET'])
def get_payment_history(user_id):
    """Get payment history for a user"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        payments = PaymentRecord.query.filter_by(user_id=user_id).order_by(
            PaymentRecord.created_at.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'payments': [payment.to_dict() for payment in payments.items],
            'total': payments.total,
            'pages': payments.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error getting payment history: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@payments_bp.route('/refund', methods=['POST'])
def process_refund():
    """Process a refund (admin only)"""
    try:
        data = request.get_json()
        payment_intent_id = data.get('payment_intent_id')
        reason = data.get('reason', 'Requested by admin')
        
        if not payment_intent_id:
            return jsonify({'error': 'Payment intent ID required'}), 400
            
        # Find payment record
        payment_record = PaymentRecord.query.filter_by(stripe_payment_id=payment_intent_id).first()
        if not payment_record:
            return jsonify({'error': 'Payment not found'}), 404
            
        if payment_record.status != 'succeeded':
            return jsonify({'error': 'Can only refund succeeded payments'}), 400
            
        # Process refund with Stripe
        refund = stripe.Refund.create(
            payment_intent=payment_intent_id,
            reason='requested_by_customer'
        )
        
        # Update payment record
        payment_record.status = 'refunded'
        payment_record.updated_at = datetime.utcnow()
        
        # Get user and deduct coins if they still have them
        user = User.query.get(payment_record.user_id)
        if user:
            metadata = json.loads(payment_record.payment_metadata) if payment_record.payment_metadata else {}
            coins_to_deduct = int(metadata.get('coins_to_purchase', 0))
            
            if user.coins >= coins_to_deduct:
                user.coins -= coins_to_deduct
                
                # Create transaction record
                transaction = Transaction(
                    user_id=user.id,
                    transaction_type='refund',
                    amount=-coins_to_deduct,
                    description=f"Refund: {reason}",
                    reference_id=payment_intent_id
                )
                db.session.add(transaction)
            
            # Log the action
            audit_log = AuditLog(
                user_id=user.id,
                action='payment_refunded',
                details=f"Payment refunded: ${payment_record.amount_cents / 100} - {reason}"
            )
            db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Refund processed successfully',
            'refund_id': refund.id
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe refund error: {e}")
        return jsonify({'error': 'Refund processing failed'}), 500
    except Exception as e:
        logger.error(f"Error processing refund: {e}")
        return jsonify({'error': 'Internal server error'}), 500

