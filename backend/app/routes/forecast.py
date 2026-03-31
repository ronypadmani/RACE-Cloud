"""
Forecast routes — cost prediction, anomaly detection, and budget management.
All read-only AWS operations. Budget data stored in local SQLite only.
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..database import query_db, execute_db
from ..aws.client_factory import AWSClientFactory
from ..aws.cost_service import CostService
from ..aws.forecast_service import ForecastService
from ..demo.demo_loader import is_demo_mode, load_demo_cost_data

forecast_bp = Blueprint('forecast', __name__)


def _get_aws_account(user_id):
    """Retrieve the user's AWS account configuration."""
    return query_db(
        "SELECT * FROM aws_accounts WHERE user_id = ?",
        (user_id,), one=True
    )


def _get_cost_data(aws_account) -> tuple:
    """Fetch daily and monthly cost data from AWS."""
    factory = AWSClientFactory(
        encrypted_access_key=aws_account['encrypted_access_key'],
        encrypted_secret_key=aws_account['encrypted_secret_key'],
        region=aws_account['region']
    )
    cost_svc = CostService(factory)
    daily = cost_svc.get_daily_cost_trend(days=30)
    monthly = cost_svc.get_monthly_cost(months=3)
    return daily, monthly


# ── Predicted Cost ─────────────────────────────────────────────────────────────

@forecast_bp.route('/cost', methods=['GET'])
@jwt_required()
def get_predicted_cost():
    """Return predicted monthly cost using linear regression / moving average."""
    user_id = get_jwt_identity()

    if is_demo_mode():
        try:
            daily, monthly = load_demo_cost_data()
            svc = ForecastService(
                daily_costs=daily.get('daily_costs', []),
                monthly_costs=monthly.get('monthly_costs', [])
            )
            prediction = svc.get_cost_prediction(forecast_days=30)
            return jsonify(prediction), 200
        except Exception as e:
            current_app.logger.error(f'Demo forecast error: {e}')
            return jsonify({'error': 'Failed to generate demo forecast'}), 500

    aws_account = _get_aws_account(user_id)

    if not aws_account or not aws_account['is_validated']:
        return jsonify({'error': 'AWS credentials not configured or invalid'}), 400

    try:
        daily, monthly = _get_cost_data(aws_account)
        svc = ForecastService(
            daily_costs=daily.get('daily_costs', []),
            monthly_costs=monthly.get('monthly_costs', [])
        )
        prediction = svc.get_cost_prediction(forecast_days=30)
        return jsonify(prediction), 200
    except Exception as e:
        current_app.logger.error(f'Forecast error: {e}')
        return jsonify({'error': 'Failed to generate cost forecast'}), 500


# ── Anomalies ──────────────────────────────────────────────────────────────────

@forecast_bp.route('/anomalies', methods=['GET'])
@jwt_required()
def get_anomalies():
    """Return abnormal cost spikes in the last 30 days."""
    user_id = get_jwt_identity()

    if is_demo_mode():
        try:
            daily, _ = load_demo_cost_data()
            svc = ForecastService(daily_costs=daily.get('daily_costs', []))
            anomalies = svc.detect_anomalies(sensitivity=2.0)
            return jsonify(anomalies), 200
        except Exception as e:
            current_app.logger.error(f'Demo anomaly error: {e}')
            return jsonify({'error': 'Failed to detect demo anomalies'}), 500

    aws_account = _get_aws_account(user_id)

    if not aws_account or not aws_account['is_validated']:
        return jsonify({'error': 'AWS credentials not configured or invalid'}), 400

    try:
        daily, _ = _get_cost_data(aws_account)
        svc = ForecastService(daily_costs=daily.get('daily_costs', []))
        anomalies = svc.detect_anomalies(sensitivity=2.0)
        return jsonify(anomalies), 200
    except Exception as e:
        current_app.logger.error(f'Anomaly detection error: {e}')
        return jsonify({'error': 'Failed to detect anomalies'}), 500


# ── Budget Management ──────────────────────────────────────────────────────────

@forecast_bp.route('/budget', methods=['POST'])
@jwt_required()
def set_budget():
    """Store or update the user's monthly budget limit."""
    user_id = get_jwt_identity()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    monthly_limit = data.get('monthly_limit')
    if monthly_limit is None or not isinstance(monthly_limit, (int, float)) or monthly_limit < 0:
        return jsonify({'error': 'monthly_limit must be a non-negative number'}), 400

    existing = query_db(
        "SELECT id FROM budgets WHERE user_id = ?",
        (user_id,), one=True
    )

    if existing:
        execute_db(
            "UPDATE budgets SET monthly_limit = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (monthly_limit, user_id)
        )
    else:
        execute_db(
            "INSERT INTO budgets (user_id, monthly_limit) VALUES (?, ?)",
            (user_id, monthly_limit)
        )

    return jsonify({
        'message': 'Budget updated successfully',
        'monthly_limit': monthly_limit
    }), 200


@forecast_bp.route('/budget/status', methods=['GET'])
@jwt_required()
def get_budget_status():
    """Compare predicted cost against the user's budget."""
    user_id = get_jwt_identity()
    aws_account = _get_aws_account(user_id)

    # Get budget
    budget = query_db(
        "SELECT monthly_limit, created_at, updated_at FROM budgets WHERE user_id = ?",
        (user_id,), one=True
    )

    if not budget:
        return jsonify({
            'has_budget': False,
            'status': 'no_budget',
            'message': 'No budget set. Set a monthly budget to track spending.',
            'alert_level': 'NONE',
        }), 200

    monthly_limit = budget['monthly_limit']

    # If no AWS credentials, return budget-only info
    if not is_demo_mode() and (not aws_account or not aws_account['is_validated']):
        return jsonify({
            'has_budget': True,
            'monthly_limit': monthly_limit,
            'status': 'no_aws',
            'message': 'AWS credentials not configured. Cannot compare against predicted cost.',
            'alert_level': 'NONE',
        }), 200

    try:
        if is_demo_mode():
            daily, monthly = load_demo_cost_data()
        else:
            daily, monthly = _get_cost_data(aws_account)
        svc = ForecastService(
            daily_costs=daily.get('daily_costs', []),
            monthly_costs=monthly.get('monthly_costs', [])
        )
        prediction = svc.get_cost_prediction(forecast_days=30)
        comparison = ForecastService.compare_budget(
            predicted_cost=prediction['predicted_monthly_cost'],
            monthly_limit=monthly_limit
        )

        return jsonify({
            'has_budget': True,
            'prediction': prediction,
            **comparison,
        }), 200
    except Exception as e:
        current_app.logger.error(f'Budget status error: {e}')
        return jsonify({'error': 'Failed to compute budget status'}), 500
