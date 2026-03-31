"""
Authentication routes for RACE-Cloud.
Handles user registration, login, and profile retrieval.
"""
import re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity
)
from ..database import query_db, execute_db
from ..security import hash_password, verify_password

auth_bp = Blueprint('auth', __name__)


def _validate_email(email: str) -> bool:
    """Basic email format validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _validate_password(password: str) -> tuple:
    """Validate password strength. Returns (is_valid, message)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit"
    return True, "Valid"


# ── Register ───────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new platform user."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    # Validation
    if not username or not email or not password:
        return jsonify({'error': 'Username, email, and password are required'}), 400

    if len(username) < 3 or len(username) > 30:
        return jsonify({'error': 'Username must be 3-30 characters'}), 400

    if not _validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    valid, msg = _validate_password(password)
    if not valid:
        return jsonify({'error': msg}), 400

    # Check duplicates
    existing = query_db(
        "SELECT id FROM users WHERE username = ? OR email = ?",
        (username, email), one=True
    )
    if existing:
        return jsonify({'error': 'Username or email already exists'}), 409

    # Create user
    pw_hash = hash_password(password)
    user_id = execute_db(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, pw_hash)
    )

    token = create_access_token(identity=str(user_id))
    return jsonify({
        'message': 'Registration successful',
        'token': token,
        'user': {
            'id': user_id,
            'username': username,
            'email': email
        }
    }), 201


# ── Login ──────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = query_db(
        "SELECT id, username, email, password_hash FROM users WHERE email = ?",
        (email,), one=True
    )

    if not user or not verify_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = create_access_token(identity=str(user['id']))
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email']
        }
    }), 200


# ── Profile ────────────────────────────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile."""
    user_id = get_jwt_identity()
    user = query_db(
        "SELECT id, username, email, created_at FROM users WHERE id = ?",
        (user_id,), one=True
    )

    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Check if user has AWS credentials configured
    aws_account = query_db(
        "SELECT id, region, is_validated, last_synced FROM aws_accounts WHERE user_id = ?",
        (user_id,), one=True
    )

    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'created_at': user['created_at']
        },
        'aws_configured': aws_account is not None,
        'aws_validated': bool(aws_account['is_validated']) if aws_account else False,
        'aws_region': aws_account['region'] if aws_account else None
    }), 200
