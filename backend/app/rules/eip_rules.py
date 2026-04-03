"""
EIP Optimization Rules — Unassociated Elastic IP detection.
"""
from typing import List
from .base_rule import BaseRule, RuleResult

EIP_IDLE_MONTHLY_COST = 3.60  # ~$0.005/hr when not associated


class UnassociatedEIPRule(BaseRule):
    """Detects Elastic IPs not associated with any running instance."""

    rule_id = 'EIP_UNASSOCIATED'
    rule_name = 'Unassociated Elastic IPs'
    description = 'Flags Elastic IPs not associated with any instance — AWS charges for idle EIPs'
    resource_type = 'EIP'

    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        results = []
        eips = aws_data.get('elastic_ips', [])

        for eip in eips:
            if eip.get('error'):
                continue
            if not eip.get('is_associated', True):
                ip = eip.get('public_ip', 'unknown')
                alloc_id = eip.get('allocation_id', ip)

                results.append(RuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    resource_id=alloc_id,
                    resource_type='EIP',
                    recommendation_text=(
                        f'Elastic IP {ip} ({alloc_id}) is not associated with any instance. '
                        f'AWS charges ${EIP_IDLE_MONTHLY_COST:.2f}/month for idle EIPs. '
                        f'Release it if no longer needed.'
                    ),
                    severity='LOW',
                    estimated_savings=EIP_IDLE_MONTHLY_COST,
                    details={
                        'public_ip': ip,
                        'allocation_id': alloc_id,
                        'monthly_cost': EIP_IDLE_MONTHLY_COST,
                    }
                ))

        return results
