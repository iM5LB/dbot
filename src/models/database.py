from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import CheckConstraint
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255))
    minecraft_uuid = db.Column(db.String(36))
    coins = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    purchases = db.relationship('Purchase', backref='user', lazy=True, cascade='all, delete-orphan')
    payment_records = db.relationship('PaymentRecord', backref='user', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)
    
    __table_args__ = (
        CheckConstraint('coins >= 0', name='check_coins_non_negative'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'discord_id': self.discord_id,
            'username': self.username,
            'email': self.email,
            'minecraft_uuid': self.minecraft_uuid,
            'coins': self.coins,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_admin': self.is_admin,
            'is_active': self.is_active
        }

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reference_id = db.Column(db.String(100))
    
    __table_args__ = (
        CheckConstraint("transaction_type IN ('earn', 'spend', 'purchase', 'admin_add', 'admin_remove', 'refund', 'gift_sent', 'gift_received')", 
                       name='check_transaction_type'),
        CheckConstraint("status IN ('pending', 'completed', 'failed', 'cancelled')", 
                       name='check_transaction_status'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reference_id': self.reference_id
        }

class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Integer, nullable=False)  # Price in coins
    category = db.Column(db.String(50), nullable=False)
    
    # Item type: 'discord', 'minecraft', or 'both'
    item_type = db.Column(db.String(20), nullable=False, default='minecraft')
    
    # Discord-specific fields
    discord_role_id = db.Column(db.String(20))  # Discord role ID to assign
    
    # Minecraft-specific fields
    minecraft_command_template = db.Column(db.Text)  # Command template for Minecraft
    
    # General fields
    image_url = db.Column(db.String(255))
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    purchases = db.relationship('Purchase', backref='item', lazy=True)
    
    __table_args__ = (
        CheckConstraint('price > 0', name='check_price_positive'),
        CheckConstraint("item_type IN ('discord', 'minecraft', 'both')", name='check_item_type'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'item_type': self.item_type,
            'discord_role_id': self.discord_role_id,
            'minecraft_command_template': self.minecraft_command_template,
            'image_url': self.image_url,
            'is_available': self.is_available,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    total_cost = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    fulfilled_at = db.Column(db.DateTime)
    minecraft_command = db.Column(db.Text)
    discord_role_assigned = db.Column(db.Boolean, default=False)
    
    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
        CheckConstraint('total_cost > 0', name='check_total_cost_positive'),
        CheckConstraint("status IN ('pending', 'processing', 'fulfilled', 'failed', 'refunded')", 
                       name='check_purchase_status'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'item_id': self.item_id,
            'quantity': self.quantity,
            'total_cost': self.total_cost,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'fulfilled_at': self.fulfilled_at.isoformat() if self.fulfilled_at else None,
            'minecraft_command': self.minecraft_command,
            'discord_role_assigned': self.discord_role_assigned
        }

class PaymentRecord(db.Model):
    __tablename__ = 'payment_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stripe_payment_id = db.Column(db.String(100), unique=True, nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    payment_metadata = db.Column(db.Text)  # JSON string
    
    __table_args__ = (
        CheckConstraint('amount_cents > 0', name='check_amount_positive'),
        CheckConstraint("status IN ('pending', 'succeeded', 'failed', 'cancelled', 'refunded')", 
                       name='check_payment_status'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'stripe_payment_id': self.stripe_payment_id,
            'amount_cents': self.amount_cents,
            'currency': self.currency,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': json.loads(self.payment_metadata) if self.payment_metadata else None
        }

class MinecraftServer(db.Model):
    __tablename__ = 'minecraft_servers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, default=25565)
    rcon_host = db.Column(db.String(255))
    rcon_port = db.Column(db.Integer, default=25575)
    rcon_password = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    server_status = db.relationship('ServerStatus', backref='server', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'rcon_host': self.rcon_host,
            'rcon_port': self.rcon_port,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ServerStatus(db.Model):
    __tablename__ = 'server_status'
    
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('minecraft_servers.id'), nullable=False)
    is_online = db.Column(db.Boolean, nullable=False)
    players_online = db.Column(db.Integer, default=0)
    max_players = db.Column(db.Integer, default=0)
    version = db.Column(db.String(50))
    tps = db.Column(db.Numeric(4, 2))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'server_id': self.server_id,
            'is_online': self.is_online,
            'players_online': self.players_online,
            'max_players': self.max_players,
            'version': self.version,
            'tps': float(self.tps) if self.tps else None,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class BotConfig(db.Model):
    __tablename__ = 'bot_config'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'details': self.details,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class Gift(db.Model):
    __tablename__ = 'gifts'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_gifts')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_gifts')
    
    __table_args__ = (
        CheckConstraint('amount > 0', name='check_gift_amount_positive'),
        CheckConstraint("status IN ('pending', 'completed', 'cancelled')", name='check_gift_status'),
        CheckConstraint('sender_id != recipient_id', name='check_gift_different_users'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'amount': self.amount,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }

