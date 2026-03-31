"""
Cost Optimization Rules
- Rule 7: High Monthly Cost Alert
"""
from typing import List
from .base_rule import BaseRule, RuleResult


class HighMonthlyCostRule(BaseRule):
    """Rule 7: Alerts when monthly cost exceeds a configurable threshold."""

    rule_id = 'COST_HIGH_MONTHLY'
    rule_name = 'High Monthly Cost Alert'
    description = 'Alerts when total monthly AWS cost exceeds threshold'
    resource_type = 'COST'

    # Default threshold (configurable per user in future)
    COST_THRESHOLD = 50.0  # USD — suitable for Free Tier users

    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        results = []
        cost_data = aws_data.get('cost_data', {})
        monthly_costs = cost_data.get('monthly_costs', [])

        if not monthly_costs:
            return results

        # Check the most recent month
        latest_month = monthly_costs[-1] if monthly_costs else {}
        total_cost = latest_month.get('total_cost', 0)
        period = latest_month.get('period_start', 'Unknown')

        if total_cost > self.COST_THRESHOLD:
            # Find top spending services
            top_services = latest_month.get('services', [])[:5]
            top_service_names = ', '.join(
                f"{s['service']} (${s['cost']})" for s in top_services
            )

            results.append(RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                resource_id=f'Monthly-{period}',
                resource_type='COST',
                recommendation_text=(
                    f'Monthly AWS cost for {period} is ${total_cost}, exceeding '
                    f'the ${self.COST_THRESHOLD} threshold. Top services: '
                    f'{top_service_names}. Review resource usage and consider '
                    f'right-sizing or stopping unused resources.'
                ),
                severity='HIGH',
                estimated_savings=round(total_cost * 0.20, 2),  # Estimate 20% can be saved
                details={
                    'period': period,
                    'total_cost': total_cost,
                    'threshold': self.COST_THRESHOLD,
                    'top_services': top_services
                }
            ))

        # Also check for month-over-month increase > 25%
        if len(monthly_costs) >= 2:
            current = monthly_costs[-1].get('total_cost', 0)
            previous = monthly_costs[-2].get('total_cost', 0)

            if previous > 0 and current > 0:
                increase_pct = ((current - previous) / previous) * 100
                if increase_pct > 25:
                    results.append(RuleResult(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        resource_id=f'Trend-{period}',
                        resource_type='COST',
                        recommendation_text=(
                            f'Monthly cost increased by {increase_pct:.0f}% '
                            f'(${previous:.2f} → ${current:.2f}). Investigate '
                            f'which services are driving the increase.'
                        ),
                        severity='MEDIUM',
                        estimated_savings=round(current - previous, 2),
                        details={
                            'current_cost': current,
                            'previous_cost': previous,
                            'increase_percentage': round(increase_pct, 1)
                        }
                    ))

        return results
