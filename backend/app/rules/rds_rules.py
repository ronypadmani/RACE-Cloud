"""
RDS Optimization Rules — Idle database detection.
"""
from typing import List
from .base_rule import BaseRule, RuleResult

# Approximate monthly on-demand costs for common RDS instance classes (us-east-1, MySQL, Single-AZ)
RDS_COST_MAP = {
    'db.t3.micro': 12.41, 'db.t3.small': 24.82, 'db.t3.medium': 49.64,
    'db.t3.large': 99.28,
    'db.m5.large': 124.10, 'db.m5.xlarge': 248.20, 'db.m5.2xlarge': 496.40,
    'db.r5.large': 175.20, 'db.r5.xlarge': 350.40,
}
DEFAULT_RDS_MONTHLY = 100.0


class IdleRDSRule(BaseRule):
    """Detects RDS instances with zero or near-zero connections."""

    rule_id = 'RDS_IDLE'
    rule_name = 'Idle RDS Instances'
    description = 'Flags RDS databases with zero connections over 7 days'
    resource_type = 'RDS'

    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        results = []
        rds_instances = aws_data.get('rds_instances', [])
        rds_connections = aws_data.get('rds_connections', {})

        for db in rds_instances:
            if db.get('error'):
                continue
            if db.get('status') != 'available':
                continue

            db_id = db['db_instance_id']
            conn_info = rds_connections.get(db_id, {})
            is_idle = conn_info.get('is_idle', False)
            max_connections = conn_info.get('max_connections', -1)

            if is_idle or max_connections == 0:
                db_class = db.get('db_instance_class', '')
                engine = db.get('engine', 'unknown')
                monthly_cost = RDS_COST_MAP.get(db_class, DEFAULT_RDS_MONTHLY)

                # Multi-AZ doubles the cost
                if db.get('multi_az'):
                    monthly_cost *= 2

                results.append(RuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    resource_id=db_id,
                    resource_type='RDS',
                    recommendation_text=(
                        f'RDS instance "{db_id}" ({db_class}, {engine}) has zero active '
                        f'connections over the past 7 days. Consider stopping or deleting '
                        f'this database to save ~${monthly_cost:.2f}/month.'
                    ),
                    severity='HIGH',
                    estimated_savings=monthly_cost,
                    details={
                        'db_instance_class': db_class,
                        'engine': engine,
                        'multi_az': db.get('multi_az', False),
                        'storage_gb': db.get('storage_gb', 0),
                        'avg_connections': conn_info.get('avg_connections', 0),
                        'max_connections': max_connections,
                        'monthly_cost': monthly_cost,
                    }
                ))

        return results
