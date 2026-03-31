"""
Rule Engine — discovers, loads, and executes optimization rules.
Simplified to essential rules (idle EC2, unused EBS, cost alerts).
"""
import logging
from typing import List, Dict
from .base_rule import BaseRule, RuleResult
from .ec2_rules import IdleEC2Rule
from .ebs_rules import UnusedEBSRule
from .cost_rules import HighMonthlyCostRule

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Modular rule engine that evaluates AWS resources against
    registered optimization rules. Rules are self-contained and
    pluggable — adding a new rule requires only creating a new
    Rule class and registering it here.
    """

    def __init__(self):
        self._rules: List[BaseRule] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """Register essential optimization rules."""
        self._rules = [
            IdleEC2Rule(),              # CPU < 2% — high savings
            UnusedEBSRule(),            # Unattached EBS — easy win
            HighMonthlyCostRule(),      # Monthly cost alert
        ]

    def register_rule(self, rule: BaseRule):
        """Register a custom rule at runtime."""
        self._rules.append(rule)

    def get_registered_rules(self) -> List[dict]:
        """Return metadata for all registered rules."""
        return [rule.get_info() for rule in self._rules]

    def run_analysis(self, aws_data: dict) -> Dict:
        """
        Execute all registered rules against the provided AWS data.

        Args:
            aws_data: Dictionary with keys like 'ec2_instances', 'ebs_volumes',
                      'cpu_metrics', 's3_buckets', 'rds_instances', 'cost_data', etc.

        Returns:
            Dictionary with analysis results, summary, and total savings.
        """
        all_results: List[RuleResult] = []
        rule_summaries = []
        errors = []

        for rule in self._rules:
            try:
                logger.info('Running rule: %s (%s)', rule.rule_id, rule.rule_name)
                results = rule.evaluate(aws_data)
                all_results.extend(results)
                rule_summaries.append({
                    'rule_id': rule.rule_id,
                    'rule_name': rule.rule_name,
                    'findings_count': len(results),
                    'total_savings': round(sum(r.estimated_savings for r in results), 2)
                })
                logger.info(
                    '  → %s: %d findings, $%.2f savings',
                    rule.rule_id, len(results),
                    sum(r.estimated_savings for r in results),
                )
            except Exception as e:
                logger.error('Rule %s failed: %s', rule.rule_id, e)
                errors.append({
                    'rule_id': rule.rule_id,
                    'error': str(e)
                })

        # Classify by severity
        high = [r for r in all_results if r.severity == 'HIGH']
        medium = [r for r in all_results if r.severity == 'MEDIUM']
        low = [r for r in all_results if r.severity == 'LOW']

        total_savings = round(sum(r.estimated_savings for r in all_results), 2)

        return {
            'total_findings': len(all_results),
            'total_estimated_savings': total_savings,
            'severity_breakdown': {
                'high': len(high),
                'medium': len(medium),
                'low': len(low)
            },
            'recommendations': [r.to_dict() for r in all_results],
            'recommendations_by_severity': {
                'high': [r.to_dict() for r in high],
                'medium': [r.to_dict() for r in medium],
                'low': [r.to_dict() for r in low],
            },
            'rule_summaries': rule_summaries,
            'errors': errors,
            'rules_executed': len(self._rules),
        }
