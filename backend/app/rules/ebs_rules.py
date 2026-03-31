"""
EBS Volume Optimization Rules — Unused EBS detection.
"""
from typing import List
from .base_rule import BaseRule, RuleResult


EBS_COST_PER_GB = {
    'gp2': 0.10, 'gp3': 0.08, 'io1': 0.125, 'io2': 0.125,
    'st1': 0.045, 'sc1': 0.015, 'standard': 0.05,
}


class UnusedEBSRule(BaseRule):
    """Detects EBS volumes not attached to any instance."""

    rule_id = 'EBS_UNUSED'
    rule_name = 'Unused EBS Volumes'
    description = 'Flags EBS volumes in "available" state (not attached to any instance)'
    resource_type = 'EBS'

    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        results = []
        volumes = aws_data.get('ebs_volumes', [])

        for vol in volumes:
            if vol.get('state') == 'available' and not vol.get('attached_to'):
                vol_id = vol['volume_id']
                vol_type = vol.get('volume_type', 'gp2')
                size_gb = vol.get('size_gb', 0)
                cost_per_gb = EBS_COST_PER_GB.get(vol_type, 0.10)
                monthly_cost = round(size_gb * cost_per_gb, 2)

                results.append(RuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    resource_id=vol_id,
                    resource_type='EBS',
                    recommendation_text=(
                        f'EBS volume {vol_id} ({size_gb} GB, {vol_type}) is not attached '
                        f'to any instance. Consider creating a snapshot and deleting this '
                        f'volume to save ~${monthly_cost}/month.'
                    ),
                    severity='MEDIUM',
                    estimated_savings=monthly_cost,
                    details={
                        'volume_type': vol_type,
                        'size_gb': size_gb,
                        'monthly_cost': monthly_cost,
                        'availability_zone': vol.get('availability_zone', '')
                    }
                ))

        return results
