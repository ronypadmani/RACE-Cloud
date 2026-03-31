"""
AWS API routes — credential management, resource fetching, cost data.
All AWS interactions go through the backend service layer.
Frontend NEVER communicates directly with AWS.
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..database import query_db, execute_db
from ..security import encrypt_credential, decrypt_credential, mask_string
from ..aws.client_factory import AWSClientFactory
from ..aws.ec2_service import EC2Service
from ..aws.cost_service import CostService
from ..aws.s3_service import S3Service
from ..aws.rds_service import RDSService
from ..demo.demo_loader import is_demo_mode, load_demo_data, get_current_scenario

aws_bp = Blueprint('aws', __name__)

# List of supported AWS regions
SUPPORTED_REGIONS = [
    'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
    'eu-west-1', 'eu-west-2', 'eu-central-1',
    'ap-south-1', 'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1',
    'sa-east-1', 'ca-central-1'
]


def _get_aws_account(user_id):
    """Retrieve the user's AWS account configuration."""
    return query_db(
        "SELECT * FROM aws_accounts WHERE user_id = ?",
        (user_id,), one=True
    )


def _get_client_factory(aws_account) -> AWSClientFactory:
    """Create an AWSClientFactory from a database AWS account record."""
    return AWSClientFactory(
        encrypted_access_key=aws_account['encrypted_access_key'],
        encrypted_secret_key=aws_account['encrypted_secret_key'],
        region=aws_account['region']
    )


# ── Credentials ────────────────────────────────────────────────────────────────

@aws_bp.route('/credentials', methods=['POST'])
@jwt_required()
def submit_credentials():
    """Submit and validate AWS IAM credentials."""
    user_id = get_jwt_identity()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    access_key = data.get('access_key', '').strip()
    secret_key = data.get('secret_key', '').strip()
    region = data.get('region', 'us-east-1').strip()

    # Validate inputs
    if not access_key or not secret_key:
        return jsonify({'error': 'Access Key and Secret Key are required'}), 400

    if not access_key.startswith('AKIA'):
        return jsonify({'error': 'Invalid Access Key format (should start with AKIA)'}), 400

    if len(secret_key) < 30:
        return jsonify({'error': 'Invalid Secret Key format'}), 400

    if region not in SUPPORTED_REGIONS:
        return jsonify({'error': f'Unsupported region. Supported: {", ".join(SUPPORTED_REGIONS)}'}), 400

    # Validate credentials against AWS
    validation = AWSClientFactory.validate_credentials(access_key, secret_key, region)

    if not validation['valid']:
        return jsonify({
            'error': 'AWS credential validation failed',
            'details': validation['error']
        }), 400

    # Encrypt and store credentials
    enc_access = encrypt_credential(access_key)
    enc_secret = encrypt_credential(secret_key)

    # Check if user already has AWS credentials
    existing = _get_aws_account(user_id)

    if existing:
        execute_db(
            """UPDATE aws_accounts
               SET encrypted_access_key = ?, encrypted_secret_key = ?,
                   region = ?, is_validated = 1, account_alias = ?,
                   last_synced = CURRENT_TIMESTAMP
               WHERE user_id = ?""",
            (enc_access, enc_secret, region,
             validation.get('account_id', ''), user_id)
        )
    else:
        execute_db(
            """INSERT INTO aws_accounts
               (user_id, encrypted_access_key, encrypted_secret_key, region,
                is_validated, account_alias, last_synced)
               VALUES (?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)""",
            (user_id, enc_access, enc_secret, region,
             validation.get('account_id', ''))
        )

    return jsonify({
        'message': 'AWS credentials validated and stored securely',
        'account_id': mask_string(validation['account_id']),
        'region': region,
        'arn': validation.get('arn', '')
    }), 200


@aws_bp.route('/status', methods=['GET'])
@jwt_required()
def check_status():
    """Check if user has valid AWS credentials configured."""
    user_id = get_jwt_identity()

    if is_demo_mode():
        return jsonify({
            'configured': True,
            'validated': True,
            'region': 'ap-south-1',
            'account_id': 'DEMO-****',
            'last_synced': 'Demo Mode',
            'demo_mode': True,
            'demo_scenario': get_current_scenario(),
        }), 200

    aws_account = _get_aws_account(user_id)

    if not aws_account:
        return jsonify({
            'configured': False,
            'validated': False,
            'message': 'No AWS credentials configured'
        }), 200

    return jsonify({
        'configured': True,
        'validated': bool(aws_account['is_validated']),
        'region': aws_account['region'],
        'account_id': mask_string(aws_account['account_alias']) if aws_account['account_alias'] else 'N/A',
        'last_synced': aws_account['last_synced']
    }), 200


@aws_bp.route('/regions', methods=['GET'])
@jwt_required()
def get_regions():
    """Return list of supported AWS regions."""
    return jsonify({'regions': SUPPORTED_REGIONS}), 200


# ── Resources ──────────────────────────────────────────────────────────────────

@aws_bp.route('/resources', methods=['GET'])
@jwt_required()
def get_resources():
    """Fetch a summary of all AWS resources."""
    user_id = get_jwt_identity()

    if is_demo_mode():
        try:
            data = load_demo_data()
            instances = data['ec2_instances']
            volumes = data['ebs_volumes']
            elastic_ips = data['elastic_ips']
            buckets = data['s3_buckets']
            rds_instances = data['rds_instances']

            running_instances = len([i for i in instances if i.get('state') == 'running'])
            stopped_instances = len([i for i in instances if i.get('state') == 'stopped'])
            unattached_volumes = len([v for v in volumes if v.get('state') == 'available'])
            unassociated_eips = len([e for e in elastic_ips if not e.get('is_associated')])

            return jsonify({
                'summary': {
                    'ec2_total': len(instances),
                    'ec2_running': running_instances,
                    'ec2_stopped': stopped_instances,
                    'ebs_volumes': len(volumes),
                    'ebs_unattached': unattached_volumes,
                    'elastic_ips': len(elastic_ips),
                    'elastic_ips_unassociated': unassociated_eips,
                    's3_buckets': len(buckets),
                    'rds_instances': len(rds_instances),
                },
                'ec2_instances': instances,
                'ebs_volumes': volumes,
                'elastic_ips': elastic_ips,
                's3_buckets': buckets,
                'rds_instances': rds_instances,
                'region': 'ap-south-1',
                'demo_mode': True,
            }), 200
        except Exception as e:
            current_app.logger.error(f'Demo resources error: {e}')
            return jsonify({'error': 'Failed to load demo resources'}), 500

    aws_account = _get_aws_account(user_id)

    if not aws_account or not aws_account['is_validated']:
        return jsonify({'error': 'AWS credentials not configured or invalid'}), 400

    try:
        factory = _get_client_factory(aws_account)
        ec2_svc = EC2Service(factory)
        s3_svc = S3Service(factory)
        rds_svc = RDSService(factory)

        instances = ec2_svc.get_instances()
        volumes = ec2_svc.get_volumes()
        elastic_ips = ec2_svc.get_elastic_ips()
        buckets = s3_svc.get_buckets()
        rds_instances = rds_svc.get_instances()

        # Summary counts
        running_instances = len([i for i in instances if i.get('state') == 'running'])
        stopped_instances = len([i for i in instances if i.get('state') == 'stopped'])
        unattached_volumes = len([v for v in volumes if v.get('state') == 'available'])
        unassociated_eips = len([e for e in elastic_ips if not e.get('is_associated')])

        return jsonify({
            'summary': {
                'ec2_total': len(instances),
                'ec2_running': running_instances,
                'ec2_stopped': stopped_instances,
                'ebs_volumes': len(volumes),
                'ebs_unattached': unattached_volumes,
                'elastic_ips': len(elastic_ips),
                'elastic_ips_unassociated': unassociated_eips,
                's3_buckets': len(buckets),
                'rds_instances': len(rds_instances),
            },
            'ec2_instances': instances,
            'ebs_volumes': volumes,
            'elastic_ips': elastic_ips,
            's3_buckets': buckets,
            'rds_instances': rds_instances,
            'region': aws_account['region']
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f'Error fetching resources: {e}')
        return jsonify({'error': 'Failed to fetch AWS resources'}), 500


# ── Cost Data ──────────────────────────────────────────────────────────────────

@aws_bp.route('/costs', methods=['GET'])
@jwt_required()
def get_costs():
    """Fetch cost overview data."""
    user_id = get_jwt_identity()

    if is_demo_mode():
        try:
            data = load_demo_data()
            return jsonify({
                'monthly': data['cost_data'],
                'daily_trend': data['daily_costs'],
                'region': 'ap-south-1',
                'demo_mode': True,
            }), 200
        except Exception as e:
            current_app.logger.error(f'Demo costs error: {e}')
            return jsonify({'error': 'Failed to load demo costs'}), 500

    aws_account = _get_aws_account(user_id)

    if not aws_account or not aws_account['is_validated']:
        return jsonify({'error': 'AWS credentials not configured or invalid'}), 400

    try:
        factory = _get_client_factory(aws_account)
        cost_svc = CostService(factory)

        monthly_cost = cost_svc.get_monthly_cost(months=3)
        daily_trend = cost_svc.get_daily_cost_trend(days=30)

        return jsonify({
            'monthly': monthly_cost,
            'daily_trend': daily_trend,
            'region': aws_account['region']
        }), 200

    except Exception as e:
        current_app.logger.error(f'Error fetching costs: {e}')
        return jsonify({'error': 'Failed to fetch cost data'}), 500


@aws_bp.route('/costs/breakdown', methods=['GET'])
@jwt_required()
def get_cost_breakdown():
    """Fetch cost breakdown by service and region."""
    user_id = get_jwt_identity()

    if is_demo_mode():
        try:
            data = load_demo_data()
            return jsonify({
                'service_breakdown': data['service_breakdown'],
                'region_breakdown': data['region_breakdown'],
                'demo_mode': True,
            }), 200
        except Exception as e:
            current_app.logger.error(f'Demo breakdown error: {e}')
            return jsonify({'error': 'Failed to load demo breakdown'}), 500

    aws_account = _get_aws_account(user_id)

    if not aws_account or not aws_account['is_validated']:
        return jsonify({'error': 'AWS credentials not configured or invalid'}), 400

    try:
        factory = _get_client_factory(aws_account)
        cost_svc = CostService(factory)

        service_breakdown = cost_svc.get_service_breakdown(days=30)
        region_breakdown = cost_svc.get_region_breakdown(days=30)

        return jsonify({
            'service_breakdown': service_breakdown,
            'region_breakdown': region_breakdown
        }), 200

    except Exception as e:
        current_app.logger.error(f'Error fetching cost breakdown: {e}')
        return jsonify({'error': 'Failed to fetch cost breakdown'}), 500
