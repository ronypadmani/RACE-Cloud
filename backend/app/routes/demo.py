"""
Demo routes — switch demo scenarios and check demo status at runtime.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ..demo.demo_loader import (
    is_demo_mode, get_current_scenario, set_scenario, AVAILABLE_SCENARIOS,
)

demo_bp = Blueprint('demo', __name__)


@demo_bp.route('/status', methods=['GET'])
@jwt_required()
def demo_status():
    """Return current demo mode status and available scenarios."""
    return jsonify({
        'demo_mode': is_demo_mode(),
        'current_scenario': get_current_scenario(),
        'available_scenarios': list(AVAILABLE_SCENARIOS.keys()),
    }), 200


@demo_bp.route('/switch', methods=['POST'])
@jwt_required()
def switch_scenario():
    """Switch the active demo scenario at runtime."""
    if not is_demo_mode():
        return jsonify({'error': 'Demo mode is not enabled'}), 400

    data = request.get_json(silent=True) or {}
    scenario = data.get('scenario', '').strip()

    if not scenario:
        return jsonify({
            'error': 'scenario is required',
            'available': list(AVAILABLE_SCENARIOS.keys()),
        }), 400

    if not set_scenario(scenario):
        return jsonify({
            'error': f"Unknown scenario '{scenario}'",
            'available': list(AVAILABLE_SCENARIOS.keys()),
        }), 400

    return jsonify({
        'message': f'Switched to {scenario} scenario',
        'current_scenario': get_current_scenario(),
    }), 200
