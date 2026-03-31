"""
Decision routes — AI-Powered Decision Intelligence Engine.
Combines local AI (LLaMA/Ollama) or Gemini architecture suggestions,
real-time cost analysis, and prioritised action plans.
"""
import hashlib
import json
import logging

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..database import query_db, execute_db
from ..analysis.decision_engine import generate_action_plan
from ..decision.ai_engine import generate_ai_architecture
from ..decision.cost_engine import calculate_cost_options
from ..aws.client_factory import AWSClientFactory
from ..demo.demo_loader import is_demo_mode

logger = logging.getLogger(__name__)

decision_bp = Blueprint('decision', __name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _get_behaviour_stats(user_id) -> dict:
    rows = query_db(
        """SELECT rule_id, action_type, COUNT(*) as cnt
           FROM user_behavior
           WHERE user_id = ?
           GROUP BY rule_id, action_type""",
        (user_id,)
    )
    stats: dict = {}
    for row in rows:
        rid = row['rule_id']
        if rid not in stats:
            stats[rid] = {'applied': 0, 'dismissed': 0, 'ignored': 0}
        stats[rid][row['action_type']] = row['cnt']
    return stats


def _input_hash(text: str) -> str:
    """Deterministic hash for caching similar requests."""
    normalized = ' '.join(text.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def _get_client_factory(user_id):
    """Try to build an AWSClientFactory from the user's stored credentials."""
    aws_account = query_db(
        "SELECT * FROM aws_accounts WHERE user_id = ?",
        (user_id,), one=True
    )
    if aws_account and aws_account['is_validated']:
        try:
            return AWSClientFactory(
                encrypted_access_key=aws_account['encrypted_access_key'],
                encrypted_secret_key=aws_account['encrypted_secret_key'],
                region=aws_account['region'],
            )
        except Exception:
            pass
    return None


# ── GET /api/decision/plan ─────────────────────────────────────────────────────

@decision_bp.route('/plan', methods=['GET'])
@jwt_required()
def get_action_plan():
    """Return a ranked action plan based on active recommendations + behaviour."""
    user_id = get_jwt_identity()

    # Auto-run analysis in demo mode if no recommendations exist
    if is_demo_mode():
        count = query_db(
            "SELECT COUNT(*) AS cnt FROM recommendations WHERE user_id = ? AND status = 'ACTIVE'",
            (user_id,), one=True
        )
        if count and count['cnt'] == 0:
            logger.info('Demo mode: auto-running analysis for action plan (user %s)', user_id)
            try:
                from .analysis import _run_analysis_for_user
                _run_analysis_for_user(user_id)
            except Exception as e:
                logger.error('Auto-analysis for action plan failed: %s', e)

    recommendations = query_db(
        """SELECT r.*, COALESCE(a.region, 'demo') AS region,
                  COALESCE(a.account_alias, 'Demo') AS account_alias
           FROM recommendations r
           LEFT JOIN aws_accounts a ON r.aws_account_id = a.id
           WHERE r.user_id = ? AND r.status = 'ACTIVE'
           ORDER BY r.estimated_savings DESC""",
        (user_id,)
    )

    if not recommendations:
        return jsonify({
            'top_actions': [],
            'total_savings': 0,
            'message': 'No active recommendations. Run an analysis first.'
        }), 200

    rec_list = [
        {
            'id': rec['id'],
            'rule_id': rec['rule_id'],
            'resource_id': rec['resource_id'],
            'resource_type': rec['resource_type'],
            'recommendation_text': rec['recommendation_text'],
            'severity': rec['severity'],
            'estimated_savings': rec['estimated_savings'],
        }
        for rec in recommendations
    ]

    behaviour_stats = _get_behaviour_stats(user_id)
    plan = generate_action_plan(rec_list, behaviour_stats)
    return jsonify(plan), 200


# ── POST /api/decision/behavior ────────────────────────────────────────────────

@decision_bp.route('/behavior', methods=['POST'])
@jwt_required()
def record_behavior():
    """Record a user action on a recommendation."""
    user_id = get_jwt_identity()
    body = request.get_json(silent=True) or {}

    rule_id = body.get('rule_id', '').strip()
    action_type = body.get('action_type', '').strip()
    recommendation_id = body.get('recommendation_id')

    if not rule_id or action_type not in ('applied', 'dismissed', 'ignored'):
        return jsonify({
            'error': 'rule_id and action_type (applied|dismissed|ignored) are required.'
        }), 400

    execute_db(
        """INSERT INTO user_behavior (user_id, rule_id, recommendation_id, action_type)
           VALUES (?, ?, ?, ?)""",
        (user_id, rule_id, recommendation_id, action_type)
    )
    if action_type == 'dismissed' and recommendation_id:
        execute_db(
            "UPDATE recommendations SET status = 'DISMISSED' WHERE id = ? AND user_id = ?",
            (recommendation_id, user_id)
        )

    return jsonify({'message': 'Behavior recorded'}), 201


# ── POST /api/decision/ai-suggest ──────────────────────────────────────────────

@decision_bp.route('/ai-suggest', methods=['POST'])
@jwt_required()
def ai_suggest():
    """
    AI-powered architecture suggestion with cost analysis.

    Body JSON:
        { "user_input": "...", "budget": 100, "priority": "balanced" }

    Returns combined AI suggestion + 3 cost options + top_actions + final recommendation.
    Caches results for identical inputs (24h).
    """
    user_id = get_jwt_identity()
    body = request.get_json(silent=True) or {}

    user_input = body.get('user_input', '').strip()
    if not user_input:
        return jsonify({'error': 'user_input is required.'}), 400

    budget = body.get('budget', 100)
    try:
        budget = float(budget)
        if budget < 0:
            budget = 100
    except (TypeError, ValueError):
        budget = 100

    priority = body.get('priority', 'balanced').strip().lower()
    if priority not in ('cheap', 'balanced', 'performance'):
        priority = 'balanced'

    # ── Check cache ────────────────────────────────────────────
    ihash = _input_hash(user_input)
    cached = query_db(
        """SELECT ai_response, cost_analysis FROM ai_requests
           WHERE input_hash = ? AND created_at > datetime('now', '-24 hours')
           ORDER BY created_at DESC LIMIT 1""",
        (ihash,), one=True
    )
    if cached:
        try:
            ai_data = json.loads(cached['ai_response'])
            cost_data = json.loads(cached['cost_analysis'])
            if abs(cost_data.get('budget', 100) - budget) <= 1:
                # Fetch top_actions for the full response
                top_actions = _get_top_actions(user_id)
                return jsonify({
                    'ai_suggestion': ai_data,
                    'cost_options': cost_data['options'],
                    'region_comparison': cost_data.get('region_comparison', []),
                    'top_actions': top_actions,
                    'final_recommendation': _generate_final_recommendation(
                        ai_data, cost_data, priority
                    ),
                    'confidence': ai_data.get('confidence', 70),
                    'pricing_source': cost_data.get('pricing_source', 'estimated'),
                    'ai_provider': ai_data.get('ai_provider', 'cached'),
                    'cached': True,
                }), 200
        except (json.JSONDecodeError, TypeError):
            pass

    # ── Generate AI suggestion ─────────────────────────────────
    try:
        ai_data = generate_ai_architecture(user_input)
    except EnvironmentError as e:
        return jsonify({'error': str(e)}), 503
    except RuntimeError as e:
        current_app.logger.error('AI engine error (all retries exhausted): %s', e)
        return jsonify({
            'error': f'AI failed after multiple attempts: {e}'
        }), 500
    except Exception as e:
        err_str = str(e)
        current_app.logger.error('AI engine error: %s', e)
        if '429' in err_str or 'quota' in err_str.lower() or 'rate' in err_str.lower():
            return jsonify({
                'error': 'AI rate limit reached. Please wait a minute and try again.'
            }), 429
        return jsonify({'error': f'AI error: {e}'}), 500

    # ── Calculate cost options ─────────────────────────────────
    client_factory = _get_client_factory(user_id)
    try:
        cost_data = calculate_cost_options(
            services=ai_data['services'],
            base_scalability=ai_data.get('scalability', 'High'),
            budget=budget,
            estimated_usage=ai_data.get('estimated_usage'),
            client_factory=client_factory,
        )
    except Exception as e:
        current_app.logger.error(f'Cost engine error: {e}')
        return jsonify({'error': 'Failed to calculate costs.'}), 500

    # ── Cache the result ───────────────────────────────────────
    try:
        execute_db(
            """INSERT INTO ai_requests
               (user_id, input, input_hash, ai_response, cost_analysis)
               VALUES (?, ?, ?, ?, ?)""",
            (
                user_id,
                user_input,
                ihash,
                json.dumps(ai_data),
                json.dumps(cost_data),
            )
        )
    except Exception:
        pass

    top_actions = _get_top_actions(user_id)
    final_rec = _generate_final_recommendation(ai_data, cost_data, priority)

    return jsonify({
        'ai_suggestion': ai_data,
        'cost_options': cost_data['options'],
        'region_comparison': cost_data.get('region_comparison', []),
        'top_actions': top_actions,
        'final_recommendation': final_rec,
        'confidence': ai_data.get('confidence', 70),
        'pricing_source': cost_data.get('pricing_source', 'estimated'),
        'ai_provider': ai_data.get('ai_provider', 'unknown'),
        'cached': False,
    }), 200


# ── POST /api/decision/intelligence (alias) ───────────────────────────────────

@decision_bp.route('/intelligence', methods=['POST'])
@jwt_required()
def intelligence():
    """Alias for ai_suggest — POST /api/decision/intelligence."""
    return ai_suggest()


def _get_top_actions(user_id) -> list:
    """Fetch top 3 active recommendations for the user."""
    recommendations = query_db(
        """SELECT r.*, COALESCE(a.region, 'demo') AS region
           FROM recommendations r
           LEFT JOIN aws_accounts a ON r.aws_account_id = a.id
           WHERE r.user_id = ? AND r.status = 'ACTIVE'
           ORDER BY r.estimated_savings DESC
           LIMIT 3""",
        (user_id,)
    )
    if not recommendations:
        return []

    rec_list = [
        {
            'id': rec['id'],
            'rule_id': rec['rule_id'],
            'resource_id': rec['resource_id'],
            'resource_type': rec['resource_type'],
            'recommendation_text': rec['recommendation_text'],
            'severity': rec['severity'],
            'estimated_savings': rec['estimated_savings'],
        }
        for rec in recommendations
    ]
    plan = generate_action_plan(rec_list, _get_behaviour_stats(user_id))
    return plan.get('top_actions', [])[:3]


def _generate_final_recommendation(ai_data: dict, cost_data: dict, priority: str) -> str:
    """Generate a final recommendation string based on AI + cost analysis."""
    priority_map = {'cheap': 'CHEAP', 'balanced': 'BALANCED', 'performance': 'PERFORMANCE'}
    tier = priority_map.get(priority, 'BALANCED')

    matched = None
    for opt in cost_data.get('options', []):
        if opt.get('type') == tier:
            matched = opt
            break

    if not matched:
        matched = cost_data.get('options', [{}])[0]

    project = ai_data.get('project_type', 'your project')
    cost = matched.get('estimated_cost', 0)
    region = matched.get('region', 'us-east-1')
    scalability = matched.get('scalability', 'High')

    return (
        f"For {project}, we recommend the {matched.get('label', 'Balanced')} "
        f"option at ${cost:.2f}/mo in {region}. "
        f"This provides {scalability} scalability using "
        f"{len(ai_data.get('services', []))} AWS services. "
        f"AI confidence: {ai_data.get('confidence', 70)}%."
    )
