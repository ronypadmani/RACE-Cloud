"""
Analysis routes — runs the rule engine and returns optimization recommendations.
"""
import logging
from flask import Blueprint, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..database import query_db, execute_db
from ..security import mask_string
from ..aws.client_factory import AWSClientFactory
from ..aws.ec2_service import EC2Service
from ..aws.cost_service import CostService
from ..aws.s3_service import S3Service
from ..aws.rds_service import RDSService
from ..rules import RuleEngine
from ..demo.demo_loader import is_demo_mode, load_demo_data

logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)


def _get_aws_account(user_id):
    return query_db(
        "SELECT * FROM aws_accounts WHERE user_id = ?",
        (user_id,), one=True
    )


def _ensure_demo_account(user_id):
    """Create or retrieve a demo aws_accounts row so FK constraints pass."""
    demo = query_db(
        "SELECT id FROM aws_accounts WHERE user_id = ? AND account_alias = '__DEMO__'",
        (user_id,), one=True
    )
    if demo:
        return demo['id']
    return execute_db(
        """INSERT INTO aws_accounts
           (user_id, account_alias, encrypted_access_key, encrypted_secret_key, region, is_validated)
           VALUES (?, '__DEMO__', 'demo', 'demo', 'ap-south-1', 1)""",
        (user_id,)
    )


def _collect_aws_data(aws_account) -> dict:
    """
    Collect all AWS data needed for rule engine analysis.
    This is the SINGLE point where all AWS API calls are made for analysis.
    """
    factory = AWSClientFactory(
        encrypted_access_key=aws_account['encrypted_access_key'],
        encrypted_secret_key=aws_account['encrypted_secret_key'],
        region=aws_account['region']
    )

    ec2_svc = EC2Service(factory)
    cost_svc = CostService(factory)
    s3_svc = S3Service(factory)
    rds_svc = RDSService(factory)

    # Fetch all resource data
    ec2_instances = ec2_svc.get_instances()
    ebs_volumes = ec2_svc.get_volumes()
    elastic_ips = ec2_svc.get_elastic_ips()
    s3_buckets = s3_svc.get_buckets()
    rds_instances = rds_svc.get_instances()

    # Fetch CPU metrics for all running instances
    cpu_metrics = {}
    for inst in ec2_instances:
        if inst.get('state') == 'running':
            iid = inst['instance_id']
            cpu_metrics[iid] = ec2_svc.get_cpu_utilization(iid, days=14)

    # Fetch S3 access data
    s3_access = {}
    for bucket in s3_buckets:
        if not bucket.get('error'):
            bname = bucket['bucket_name']
            s3_access[bname] = s3_svc.get_bucket_last_access(bname)

    # Fetch RDS connection data
    rds_connections = {}
    for db in rds_instances:
        if not db.get('error') and db.get('status') == 'available':
            db_id = db['db_instance_id']
            rds_connections[db_id] = rds_svc.get_connection_count(db_id)

    # Fetch cost data
    cost_data = cost_svc.get_monthly_cost(months=3)

    return {
        'ec2_instances': ec2_instances,
        'ebs_volumes': ebs_volumes,
        'elastic_ips': elastic_ips,
        's3_buckets': s3_buckets,
        'rds_instances': rds_instances,
        'cpu_metrics': cpu_metrics,
        's3_access': s3_access,
        'rds_connections': rds_connections,
        'cost_data': cost_data,
    }


# ── Run Analysis ───────────────────────────────────────────────────────────────

@analysis_bp.route('/run', methods=['POST'])
@jwt_required()
def run_analysis():
    """Run the complete rule engine analysis on the user's AWS account."""
    user_id = get_jwt_identity()

    try:
        analysis_results = _run_analysis_for_user(user_id)
        if analysis_results is None:
            return jsonify({'error': 'AWS credentials not configured or invalid'}), 400

        logger.info(
            'Rule engine complete: %d findings, $%.2f potential savings',
            analysis_results['total_findings'],
            analysis_results['total_estimated_savings'],
        )
        for rs in analysis_results.get('rule_summaries', []):
            logger.info(
                '  Rule %s: %d findings, $%.2f savings',
                rs['rule_id'], rs['findings_count'], rs['total_savings'],
            )

        # Reconstruct aws_data for resource_summary response
        if is_demo_mode():
            aws_data = load_demo_data()
        else:
            aws_account = _get_aws_account(user_id)
            aws_data = _collect_aws_data(aws_account)

        return jsonify({
            'message': 'Analysis complete',
            'results': analysis_results,
            'resource_summary': {
                'ec2_instances': len(aws_data.get('ec2_instances', [])),
                'ebs_volumes': len(aws_data.get('ebs_volumes', [])),
                'elastic_ips': len(aws_data.get('elastic_ips', [])),
                's3_buckets': len(aws_data.get('s3_buckets', [])),
                'rds_instances': len(aws_data.get('rds_instances', [])),
            },
            'demo_mode': is_demo_mode(),
        }), 200

    except Exception as e:
        current_app.logger.error(f'Analysis error: {e}')
        return jsonify({'error': 'Analysis failed. Check AWS credentials and permissions.'}), 500


# ── Get Recommendations ────────────────────────────────────────────────────────

def _run_analysis_for_user(user_id):
    """Internal helper: run the rule engine and store results for a given user."""
    if is_demo_mode():
        aws_data = load_demo_data()
        account_id = _ensure_demo_account(user_id)
    else:
        aws_account = _get_aws_account(user_id)
        if not aws_account or not aws_account['is_validated']:
            return None
        aws_data = _collect_aws_data(aws_account)
        account_id = aws_account['id']

    engine = RuleEngine()
    analysis_results = engine.run_analysis(aws_data)

    execute_db(
        "DELETE FROM recommendations WHERE user_id = ? AND aws_account_id = ?",
        (user_id, account_id)
    )
    for rec in analysis_results.get('recommendations', []):
        execute_db(
            """INSERT INTO recommendations
               (user_id, aws_account_id, rule_id, resource_id, resource_type,
                recommendation_text, severity, estimated_savings)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, account_id, rec['rule_id'], rec['resource_id'],
             rec['resource_type'], rec['recommendation_text'],
             rec['severity'], rec['estimated_savings'])
        )

    execute_db(
        "UPDATE aws_accounts SET last_synced = CURRENT_TIMESTAMP WHERE id = ?",
        (account_id,)
    )

    return analysis_results


@analysis_bp.route('/recommendations', methods=['GET'])
@jwt_required()
def get_recommendations():
    """Get stored recommendations from the last analysis run."""
    user_id = get_jwt_identity()

    # Auto-run analysis in demo mode if no recommendations exist yet
    if is_demo_mode():
        count = query_db(
            "SELECT COUNT(*) AS cnt FROM recommendations WHERE user_id = ? AND status = 'ACTIVE'",
            (user_id,), one=True
        )
        if count and count['cnt'] == 0:
            logger.info('Demo mode: auto-running analysis for user %s', user_id)
            try:
                _run_analysis_for_user(user_id)
            except Exception as e:
                logger.error('Auto-analysis failed: %s', e)

    recommendations = query_db(
        """SELECT r.*, COALESCE(a.region, 'demo') AS region,
                  COALESCE(a.account_alias, 'Demo') AS account_alias
           FROM recommendations r
           LEFT JOIN aws_accounts a ON r.aws_account_id = a.id
           WHERE r.user_id = ? AND r.status = 'ACTIVE'
           ORDER BY
               CASE r.severity
                   WHEN 'HIGH' THEN 1
                   WHEN 'MEDIUM' THEN 2
                   WHEN 'LOW' THEN 3
               END,
               r.estimated_savings DESC""",
        (user_id,)
    )

    results = []
    total_savings = 0.0
    for rec in recommendations:
        savings = rec['estimated_savings']
        total_savings += savings
        results.append({
            'id': rec['id'],
            'rule_id': rec['rule_id'],
            'resource_id': rec['resource_id'],
            'resource_type': rec['resource_type'],
            'recommendation_text': rec['recommendation_text'],
            'severity': rec['severity'],
            'estimated_savings': round(savings, 2),
            'status': rec['status'],
            'created_at': rec['created_at'],
            'region': rec['region']
        })

    return jsonify({
        'recommendations': results,
        'total_count': len(results),
        'total_estimated_savings': round(total_savings, 2),
        'severity_breakdown': {
            'high': len([r for r in results if r['severity'] == 'HIGH']),
            'medium': len([r for r in results if r['severity'] == 'MEDIUM']),
            'low': len([r for r in results if r['severity'] == 'LOW']),
        }
    }), 200


@analysis_bp.route('/recommendations/<int:rec_id>/dismiss', methods=['PUT'])
@jwt_required()
def dismiss_recommendation(rec_id):
    """Dismiss a recommendation."""
    user_id = get_jwt_identity()

    rec = query_db(
        "SELECT id FROM recommendations WHERE id = ? AND user_id = ?",
        (rec_id, user_id), one=True
    )

    if not rec:
        return jsonify({'error': 'Recommendation not found'}), 404

    execute_db(
        "UPDATE recommendations SET status = 'DISMISSED' WHERE id = ?",
        (rec_id,)
    )

    return jsonify({'message': 'Recommendation dismissed'}), 200


@analysis_bp.route('/rules', methods=['GET'])
@jwt_required()
def get_rules():
    """List all registered optimization rules."""
    engine = RuleEngine()
    return jsonify({'rules': engine.get_registered_rules()}), 200
