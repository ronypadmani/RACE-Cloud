"""
EC2 Optimization Rules — Idle EC2 detection.
"""
from typing import List
from .base_rule import BaseRule, RuleResult


# Approximate monthly cost for common instance types (on-demand, us-east-1)
INSTANCE_COST_MAP = {
    't2.micro': 8.50, 't2.small': 16.79, 't2.medium': 33.41,
    't2.large': 66.82, 't2.xlarge': 133.63,
    't3.micro': 7.59, 't3.small': 15.18, 't3.medium': 30.37,
    't3.large': 60.74, 't3.xlarge': 121.47,
    'm5.large': 70.08, 'm5.xlarge': 140.16,
    'c5.large': 62.05, 'c5.xlarge': 124.10,
    'r5.large': 91.98, 'r5.xlarge': 183.96,
}


class IdleEC2Rule(BaseRule):
    """Detects EC2 instances that are essentially idle (CPU < 2%)."""

    rule_id = 'EC2_IDLE'
    rule_name = 'Idle EC2 Instances'
    description = 'Flags running EC2 instances with average CPU < 2% over 7 days'
    resource_type = 'EC2'

    CPU_THRESHOLD = 2.0
    PERIOD_DAYS = 7

    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        results = []
        instances = aws_data.get('ec2_instances', [])
        cpu_metrics = aws_data.get('cpu_metrics', {})

        for instance in instances:
            if instance.get('state') != 'running':
                continue

            iid = instance['instance_id']
            metrics = cpu_metrics.get(iid, {})
            avg_cpu = metrics.get('avg_cpu', -1)

            if 0 <= avg_cpu < self.CPU_THRESHOLD:
                itype = instance.get('instance_type', '')
                monthly_cost = INSTANCE_COST_MAP.get(itype, 50.0)
                savings = monthly_cost

                results.append(RuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    resource_id=iid,
                    resource_type='EC2',
                    recommendation_text=(
                        f'Instance {iid} ({itype}) appears idle with avg CPU of {avg_cpu}% '
                        f'over {self.PERIOD_DAYS} days. Consider stopping or terminating '
                        f'this instance if it is no longer needed.'
                    ),
                    severity='HIGH',
                    estimated_savings=savings,
                    details={
                        'instance_type': itype,
                        'avg_cpu': avg_cpu,
                        'max_cpu': metrics.get('max_cpu', 0),
                        'period_days': self.PERIOD_DAYS
                    }
                ))

        return results
