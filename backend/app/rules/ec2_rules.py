"""
EC2 Optimization Rules — Idle, Underutilized, Oversized, and Old-Gen detection.
"""
from typing import List
from .base_rule import BaseRule, RuleResult
from .pricing_helper import get_ec2_monthly_cost, FALLBACK_EC2_COSTS


# Kept for reference / offline use — live prices are preferred when available
INSTANCE_COST_MAP = FALLBACK_EC2_COSTS

# Instance families considered old-generation
_OLD_GEN_FAMILIES = {'t2', 'm4', 'c4', 'r4', 'i3', 'd2', 'g3', 'p2', 'x1'}

# Suggested modern replacements for old-gen families
_UPGRADE_MAP = {
    't2': 't3', 'm4': 'm5', 'c4': 'c5', 'r4': 'r5',
    'i3': 'i3en', 'd2': 'd3', 'g3': 'g4dn', 'p2': 'p3', 'x1': 'x2idn',
}

# Size ordering for downsizing recommendations
_SIZE_ORDER = ['nano', 'micro', 'small', 'medium', 'large', 'xlarge', '2xlarge',
               '4xlarge', '8xlarge', '12xlarge', '16xlarge', '24xlarge', 'metal']


def _parse_instance_type(itype: str):
    """Return (family, size) from an instance type string like 'm5.xlarge'."""
    parts = itype.split('.', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return itype, ''


def _one_size_down(itype: str) -> str | None:
    """Return the next smaller instance type, or None if already the smallest."""
    family, size = _parse_instance_type(itype)
    if size not in _SIZE_ORDER:
        return None
    idx = _SIZE_ORDER.index(size)
    if idx == 0:
        return None
    return f'{family}.{_SIZE_ORDER[idx - 1]}'


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
                monthly_cost = get_ec2_monthly_cost(itype)
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


class UnderutilizedEC2Rule(BaseRule):
    """Detects running instances with CPU between 2–10% — candidates for downsizing."""

    rule_id = 'EC2_UNDERUTILIZED'
    rule_name = 'Underutilized EC2 Instances'
    description = 'Flags running instances with avg CPU 2–10%: consider a smaller size'
    resource_type = 'EC2'

    CPU_LOW = 2.0
    CPU_HIGH = 10.0

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

            if self.CPU_LOW <= avg_cpu < self.CPU_HIGH:
                itype = instance.get('instance_type', '')
                smaller = _one_size_down(itype)
                if not smaller:
                    continue  # already the smallest size

                current_cost = get_ec2_monthly_cost(itype)
                smaller_cost = get_ec2_monthly_cost(smaller)
                savings = round(current_cost - smaller_cost, 2)
                if savings <= 0:
                    continue

                results.append(RuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    resource_id=iid,
                    resource_type='EC2',
                    recommendation_text=(
                        f'Instance {iid} ({itype}) is underutilized at {avg_cpu:.1f}% avg CPU. '
                        f'Downsize to {smaller} to save ~${savings:.2f}/month.'
                    ),
                    severity='MEDIUM',
                    estimated_savings=savings,
                    details={
                        'instance_type': itype,
                        'suggested_type': smaller,
                        'avg_cpu': avg_cpu,
                        'max_cpu': metrics.get('max_cpu', 0),
                        'current_cost': current_cost,
                        'suggested_cost': smaller_cost,
                    }
                ))

        return results


class OversizedEC2Rule(BaseRule):
    """Detects large/xlarge+ instances with very low utilisation (< 10%)."""

    rule_id = 'EC2_OVERSIZED'
    rule_name = 'Oversized EC2 Instances'
    description = 'Flags large+ instances with avg CPU < 10%: significantly oversized'
    resource_type = 'EC2'

    CPU_THRESHOLD = 10.0
    # Only flag instances at 'large' or bigger
    _MIN_SIZE_IDX = _SIZE_ORDER.index('large')

    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        results = []
        instances = aws_data.get('ec2_instances', [])
        cpu_metrics = aws_data.get('cpu_metrics', {})

        for instance in instances:
            if instance.get('state') != 'running':
                continue

            iid = instance['instance_id']
            itype = instance.get('instance_type', '')
            _, size = _parse_instance_type(itype)
            if size not in _SIZE_ORDER:
                continue
            if _SIZE_ORDER.index(size) < self._MIN_SIZE_IDX:
                continue  # skip small instances

            metrics = cpu_metrics.get(iid, {})
            avg_cpu = metrics.get('avg_cpu', -1)
            if avg_cpu < 0 or avg_cpu >= self.CPU_THRESHOLD:
                continue

            current_cost = get_ec2_monthly_cost(itype)
            smaller = _one_size_down(itype)
            smaller_cost = get_ec2_monthly_cost(smaller) if smaller else current_cost * 0.5
            savings = round(current_cost - smaller_cost, 2)

            results.append(RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                resource_id=iid,
                resource_type='EC2',
                recommendation_text=(
                    f'Instance {iid} ({itype}) is significantly oversized at '
                    f'{avg_cpu:.1f}% avg CPU. Consider downsizing to {smaller or "a smaller type"} '
                    f'to save ~${savings:.2f}/month.'
                ),
                severity='HIGH',
                estimated_savings=savings,
                details={
                    'instance_type': itype,
                    'suggested_type': smaller,
                    'avg_cpu': avg_cpu,
                    'max_cpu': metrics.get('max_cpu', 0),
                    'current_cost': current_cost,
                    'suggested_cost': smaller_cost,
                }
            ))

        return results


class OldGenEC2Rule(BaseRule):
    """Detects instances running on old-generation instance families."""

    rule_id = 'EC2_OLD_GEN'
    rule_name = 'Old Generation EC2 Instances'
    description = 'Flags instances on old-gen families (t2, m4, c4, etc.)'
    resource_type = 'EC2'

    # Old-gen instances are typically ~10-20% more expensive per vCPU
    _ESTIMATED_SAVINGS_PCT = 0.15

    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        results = []
        instances = aws_data.get('ec2_instances', [])

        for instance in instances:
            if instance.get('state') != 'running':
                continue

            iid = instance['instance_id']
            itype = instance.get('instance_type', '')
            family, size = _parse_instance_type(itype)

            if family not in _OLD_GEN_FAMILIES:
                continue

            current_cost = get_ec2_monthly_cost(itype)
            new_family = _UPGRADE_MAP.get(family, family)
            new_type = f'{new_family}.{size}'
            new_cost = get_ec2_monthly_cost(new_type)
            # If we can't look up the new type, estimate savings
            if new_cost >= current_cost:
                savings = round(current_cost * self._ESTIMATED_SAVINGS_PCT, 2)
            else:
                savings = round(current_cost - new_cost, 2)

            results.append(RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                resource_id=iid,
                resource_type='EC2',
                recommendation_text=(
                    f'Instance {iid} ({itype}) uses old-generation family "{family}". '
                    f'Upgrading to {new_type} offers better performance at ~${savings:.2f}/mo less.'
                ),
                severity='LOW',
                estimated_savings=savings,
                details={
                    'instance_type': itype,
                    'suggested_type': new_type,
                    'family': family,
                    'new_family': new_family,
                    'current_cost': current_cost,
                }
            ))

        return results
