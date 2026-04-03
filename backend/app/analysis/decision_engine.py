"""
Cloud Decision Intelligence Engine (CDIE) — ranks recommendations into a
prioritised action plan, incorporating user behaviour signals.

Pure computation — never modifies AWS resources.
"""
from __future__ import annotations

SEVERITY_SCORE = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
SAVINGS_WEIGHT = 1.5  # amplify savings in ranking

# ── effort mapping ─────────────────────────────────────────────────────────────
# Maps rule_id prefixes / keywords to an effort level and numeric penalty.
# Lower effort_score → easier → higher priority.

_EFFORT_TABLE: list[tuple[str, str, float]] = [
    # (rule_id substring, effort label, effort score)
    ('EC2_IDLE',            'LOW',    1),
    ('EC2_UNDERUTILIZED',   'MEDIUM', 2),
    ('EC2_OVERSIZED',       'MEDIUM', 2),
    ('EC2_OLD_GEN',         'MEDIUM', 2),
    ('EBS_UNUSED',          'LOW',    1),
    ('EBS_GP2_TO_GP3',      'LOW',    1),
    ('EIP_UNASSOCIATED',    'LOW',    1),
    ('S3_COLD_DATA',        'MEDIUM', 2),
    ('RDS_IDLE',            'LOW',    1),
    ('COST_HIGH_MONTHLY',   'HIGH',   3),
]

def _effort_for_rule(rule_id: str) -> tuple[str, float]:
    """Return (effort_label, effort_score) for a given rule_id."""
    for substr, label, score in _EFFORT_TABLE:
        if substr in rule_id:
            return label, score
    return 'MEDIUM', 2


# ── beginner / expert explanations ─────────────────────────────────────────────

_BEGINNER_TEMPLATES: dict[str, str] = {
    'EC2_IDLE':
        'This server is running but nobody is using it. '
        'Stopping it is like turning off a light in an empty room — instant savings.',
    'EC2_UNDERUTILIZED':
        'This server is barely working. You could switch to a smaller, cheaper one '
        'and it would still handle the load easily.',
    'EC2_OVERSIZED':
        'This server is way bigger than it needs to be. Downsizing it is like '
        'trading a truck for a car when you only carry groceries.',
    'EC2_OLD_GEN':
        'This server uses an older chip. AWS has newer, cheaper options that are '
        'also faster — upgrading is a win-win.',
    'EBS_UNUSED':
        'This is a storage disk that isn\'t attached to anything. '
        'It\'s like paying rent on a storage locker you never visit.',
    'EBS_GP2_TO_GP3':
        'This disk can be upgraded to a newer type (gp3) that costs less and '
        'performs better — no downtime required.',
    'EIP_UNASSOCIATED':
        'This is a public IP address sitting unused. AWS charges you for unused '
        'IPs, so releasing it saves money immediately.',
    'S3_COLD_DATA':
        'This storage bucket hasn\'t been accessed in months. Moving it to a '
        'cheaper storage class is like switching from a prime shelf to the archive.',
    'RDS_IDLE':
        'This database has zero connections. It\'s running with no one using it — '
        'stopping it saves a significant amount.',
    'COST_HIGH_MONTHLY':
        'Your overall cloud bill is higher than expected. The actions below will '
        'help bring it down.',
}

_DEFAULT_BEGINNER = (
    'This resource is costing you money but isn\'t being used effectively. '
    'Taking the recommended action will reduce your bill.'
)


def _beginner_explanation(rule_id: str) -> str:
    for key, text in _BEGINNER_TEMPLATES.items():
        if key in rule_id:
            return text
    return _DEFAULT_BEGINNER


def _expert_explanation(rec: dict) -> str:
    """Build a concise technical explanation from recommendation data."""
    parts = [rec.get('recommendation_text', '')]
    severity = rec.get('severity', '')
    savings = rec.get('estimated_savings', 0)
    if severity:
        parts.append(f'Severity: {severity}.')
    if savings:
        parts.append(f'Est. savings: ${savings:.2f}/mo.')
    return ' '.join(parts)


# ── behaviour modifiers ────────────────────────────────────────────────────────

def _behaviour_modifier(rule_id: str, behaviour_stats: dict) -> float:
    """
    Return a bonus/penalty based on past user actions for this rule_id.

    behaviour_stats  –  { rule_id: { 'applied': N, 'dismissed': N, 'ignored': N } }
    """
    stats = behaviour_stats.get(rule_id, {})
    applied   = stats.get('applied', 0)
    dismissed = stats.get('dismissed', 0)
    # Each past "applied" boosts score; each "dismissed" lowers it
    return (applied * 2.0) - (dismissed * 3.0)


# ── public entry point ─────────────────────────────────────────────────────────

def generate_action_plan(
    recommendations: list[dict],
    behaviour_stats: dict | None = None,
) -> dict:
    """
    Rank recommendations into a prioritised action plan.

    Parameters
    ----------
    recommendations : list[dict]
        List of recommendation dicts (as returned by the analysis routes).
    behaviour_stats : dict | None
        Per-rule behaviour counts; see `_behaviour_modifier`.

    Returns
    -------
    dict  with `top_actions` (sorted list) and `total_savings`.
    """
    behaviour_stats = behaviour_stats or {}
    scored: list[dict] = []

    for rec in recommendations:
        rule_id       = rec.get('rule_id', '')
        severity      = rec.get('severity', 'LOW')
        savings       = rec.get('estimated_savings', 0.0)
        effort_label, effort_score = _effort_for_rule(rule_id)

        sev_score     = SEVERITY_SCORE.get(severity, 1)
        behaviour_adj = _behaviour_modifier(rule_id, behaviour_stats)

        priority_score = round(
            (savings * SAVINGS_WEIGHT) + (sev_score * 10) - (effort_score * 5) + behaviour_adj,
            2,
        )
        # Confidence: higher when savings data and severity agree
        confidence = min(99, max(30, int(50 + sev_score * 10 + min(savings, 30))))

        scored.append({
            'title': _action_title(rec),
            'resource_id': rec.get('resource_id', ''),
            'resource_type': rec.get('resource_type', ''),
            'rule_id': rule_id,
            'estimated_savings': round(savings, 2),
            'priority_score': priority_score,
            'confidence': confidence,
            'effort': effort_label,
            'severity': severity,
            'explanation_beginner': _beginner_explanation(rule_id),
            'explanation_expert': _expert_explanation(rec),
            'recommendation_id': rec.get('id'),
        })

    scored.sort(key=lambda a: a['priority_score'], reverse=True)
    total_savings = round(sum(a['estimated_savings'] for a in scored), 2)

    return {
        'top_actions': scored,
        'total_savings': total_savings,
    }


# ── helpers ────────────────────────────────────────────────────────────────────

_TITLE_MAP: dict[str, str] = {
    'EC2_IDLE':           'Stop idle EC2 instance',
    'EC2_UNDERUTILIZED':  'Downsize underutilized EC2 instance',
    'EC2_OVERSIZED':      'Downsize oversized EC2 instance',
    'EC2_OLD_GEN':        'Upgrade old-gen EC2 to current gen',
    'EBS_UNUSED':         'Delete unattached EBS volume',
    'EBS_GP2_TO_GP3':     'Migrate gp2 volume to gp3',
    'EIP_UNASSOCIATED':   'Release unused Elastic IP',
    'S3_COLD_DATA':       'Move cold S3 data to Glacier',
    'RDS_IDLE':           'Stop idle RDS instance',
    'COST_HIGH_MONTHLY':  'Review high monthly spend',
}

def _action_title(rec: dict) -> str:
    rule_id = rec.get('rule_id', '')
    for key, title in _TITLE_MAP.items():
        if key in rule_id:
            return title
    return rec.get('recommendation_text', 'Review recommendation')[:60]
