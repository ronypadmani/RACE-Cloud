"""
EBS Volume Optimization Rules — Unused EBS and gp2→gp3 upgrade detection.
"""
from typing import List
from .base_rule import BaseRule, RuleResult
from .pricing_helper import get_ebs_cost_per_gb, FALLBACK_EBS_COSTS


# Kept for reference / offline use — live prices are preferred when available
EBS_COST_PER_GB = FALLBACK_EBS_COSTS


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
                cost_per_gb = get_ebs_cost_per_gb(vol_type)
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


class GP2ToGP3Rule(BaseRule):
    """Detects in-use gp2 volumes that should be migrated to gp3."""

    rule_id = 'EBS_GP2_TO_GP3'
    rule_name = 'Upgrade gp2 Volumes to gp3'
    description = 'Flags gp2 volumes attached to instances — gp3 is cheaper and faster'
    resource_type = 'EBS'

    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        results = []
        volumes = aws_data.get('ebs_volumes', [])

        for vol in volumes:
            if vol.get('volume_type') != 'gp2':
                continue
            # Only flag in-use volumes (unused ones are caught by UnusedEBSRule)
            if vol.get('state') != 'in-use':
                continue

            vol_id = vol['volume_id']
            size_gb = vol.get('size_gb', 0)
            gp2_cost = get_ebs_cost_per_gb('gp2')
            gp3_cost = get_ebs_cost_per_gb('gp3')
            savings = round(size_gb * (gp2_cost - gp3_cost), 2)

            if savings <= 0:
                continue

            results.append(RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                resource_id=vol_id,
                resource_type='EBS',
                recommendation_text=(
                    f'EBS volume {vol_id} ({size_gb} GB) is gp2. Migrate to gp3 for '
                    f'better baseline performance (3000 IOPS, 125 MB/s) and save '
                    f'~${savings:.2f}/month. No downtime required.'
                ),
                severity='LOW' if savings < 5 else 'MEDIUM',
                estimated_savings=savings,
                details={
                    'size_gb': size_gb,
                    'current_type': 'gp2',
                    'suggested_type': 'gp3',
                    'gp2_monthly': round(size_gb * gp2_cost, 2),
                    'gp3_monthly': round(size_gb * gp3_cost, 2),
                    'attached_to': vol.get('attached_to', ''),
                }
            ))

        return results
