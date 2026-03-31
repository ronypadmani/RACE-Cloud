"""
Dependency & Simulation routes — cross-service analysis and what-if cost simulation.
"""
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..database import query_db
from ..aws.client_factory import AWSClientFactory
from ..aws.ec2_service import EC2Service
from ..aws.cost_service import CostService
from ..analysis.dependency_engine import DependencyEngine
from ..analysis.simulation_engine import SimulationEngine, VALID_ACTIONS
from ..demo.demo_loader import is_demo_mode, load_demo_data

dependency_bp = Blueprint('dependency', __name__)
simulation_bp = Blueprint('simulation', __name__)


# ── helpers (shared) ───────────────────────────────────────────────────────────

def _get_aws_account(user_id):
    return query_db(
        "SELECT * FROM aws_accounts WHERE user_id = ?",
        (user_id,), one=True
    )


def _collect_ec2_data(aws_account) -> dict:
    """Collect EC2 / EBS / EIP data + CPU metrics for dependency analysis."""
    factory = AWSClientFactory(
        encrypted_access_key=aws_account['encrypted_access_key'],
        encrypted_secret_key=aws_account['encrypted_secret_key'],
        region=aws_account['region'],
    )
    ec2_svc = EC2Service(factory)

    instances = ec2_svc.get_instances()
    volumes = ec2_svc.get_volumes()
    eips = ec2_svc.get_elastic_ips()

    cpu_metrics = {}
    for inst in instances:
        if inst.get('state') == 'running' and not inst.get('error'):
            iid = inst['instance_id']
            cpu_metrics[iid] = ec2_svc.get_cpu_utilization(iid, days=14)

    return {
        'ec2_instances': instances,
        'ebs_volumes': volumes,
        'elastic_ips': eips,
        'cpu_metrics': cpu_metrics,
    }


# ── Dependency Chains ─────────────────────────────────────────────────────────

@dependency_bp.route('/dependency-chains', methods=['GET'])
@jwt_required()
def get_dependency_chains():
    """Detect cross-service waste chains for the user's AWS account."""
    user_id = get_jwt_identity()

    if is_demo_mode():
        try:
            aws_data = load_demo_data()
        except Exception as e:
            current_app.logger.error(f'Demo dependency error: {e}')
            return jsonify({'error': 'Failed to load demo data'}), 500
    else:
        aws_account = _get_aws_account(user_id)
        if not aws_account or not aws_account['is_validated']:
            return jsonify({'error': 'AWS credentials not configured or invalid'}), 400
        try:
            aws_data = _collect_ec2_data(aws_account)
        except Exception as e:
            current_app.logger.error(f'Dependency data error: {e}')
            return jsonify({'error': 'Dependency analysis failed. Check AWS credentials and permissions.'}), 500

    try:
        engine = DependencyEngine(aws_data)
        chains = engine.detect_chains()

        total_waste = sum(c['total_waste'] for c in chains)
        impact_breakdown = {
            'high': len([c for c in chains if c['impact'] == 'HIGH']),
            'medium': len([c for c in chains if c['impact'] == 'MEDIUM']),
            'low': len([c for c in chains if c['impact'] == 'LOW']),
        }

        return jsonify({
            'chains': chains,
            'total_chains': len(chains),
            'total_waste': round(total_waste, 2),
            'impact_breakdown': impact_breakdown,
        }), 200

    except Exception as e:
        current_app.logger.error(f'Dependency analysis error: {e}')
        return jsonify({'error': 'Dependency analysis failed.'}), 500


# ── What-If Simulation ────────────────────────────────────────────────────────

@simulation_bp.route('/run', methods=['POST'])
@jwt_required()
def run_simulation():
    """
    Simulate a cost-impact action.

    Body JSON:
        { "action_type": "terminate_ec2", "resource_id": "i-0abc123" }
    """
    user_id = get_jwt_identity()
    aws_account = _get_aws_account(user_id)

    if not is_demo_mode() and (not aws_account or not aws_account['is_validated']):
        return jsonify({'error': 'AWS credentials not configured or invalid'}), 400

    body = request.get_json(silent=True) or {}
    action_type = body.get('action_type', '').strip()
    resource_id = body.get('resource_id', '').strip()

    if not action_type or not resource_id:
        return jsonify({
            'error': 'Both action_type and resource_id are required.',
            'valid_actions': sorted(VALID_ACTIONS),
        }), 400

    if action_type not in VALID_ACTIONS:
        return jsonify({
            'error': f"Invalid action_type '{action_type}'.",
            'valid_actions': sorted(VALID_ACTIONS),
        }), 400

    try:
        if is_demo_mode():
            aws_data = load_demo_data()
        else:
            aws_data = _collect_ec2_data(aws_account)
        sim = SimulationEngine(aws_data)
        result = sim.simulate(action_type, resource_id)

        if 'error' in result and result.get('current_cost', 0) == 0:
            return jsonify(result), 404

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f'Simulation error: {e}')
        return jsonify({'error': 'Simulation failed. Check AWS credentials and permissions.'}), 500


@simulation_bp.route('/run-chain', methods=['POST'])
@jwt_required()
def run_chain_simulation():
    """
    Simulate removing an entire dependency chain.

    Body JSON — pass the chain object exactly as returned by /dependency-chains:
        { "chain": { "chain_type": "...", "resources": [...], ... } }
    """
    user_id = get_jwt_identity()
    aws_account = _get_aws_account(user_id)

    if not is_demo_mode() and (not aws_account or not aws_account['is_validated']):
        return jsonify({'error': 'AWS credentials not configured or invalid'}), 400

    body = request.get_json(silent=True) or {}
    chain = body.get('chain')
    if not chain or not isinstance(chain.get('resources'), list):
        return jsonify({'error': 'A valid chain object with resources is required.'}), 400

    try:
        if is_demo_mode():
            aws_data = load_demo_data()
        else:
            aws_data = _collect_ec2_data(aws_account)
        sim = SimulationEngine(aws_data)
        result = sim.simulate_chain(chain)
        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f'Chain simulation error: {e}')
        return jsonify({'error': 'Chain simulation failed.'}), 500
