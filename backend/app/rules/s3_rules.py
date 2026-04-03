"""
S3 Optimization Rules — Cold/unused bucket detection.
"""
from typing import List
from .base_rule import BaseRule, RuleResult


# S3 Standard vs Glacier cost per GB/month (approximate)
S3_STANDARD_PER_GB = 0.023
S3_GLACIER_PER_GB = 0.004


class S3ColdDataRule(BaseRule):
    """Detects S3 buckets with cold data that could be moved to cheaper storage."""

    rule_id = 'S3_COLD_DATA'
    rule_name = 'S3 Cold Data'
    description = 'Flags S3 buckets with no access in 60+ days — candidates for Glacier/IA'
    resource_type = 'S3'

    COLD_DAYS_THRESHOLD = 60  # days without access

    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        results = []
        buckets = aws_data.get('s3_buckets', [])
        s3_access = aws_data.get('s3_access', {})

        for bucket in buckets:
            if bucket.get('error'):
                continue
            bname = bucket['bucket_name']
            access_info = s3_access.get(bname, {})

            is_cold = access_info.get('is_cold', False)
            days_since = access_info.get('days_since_last_access', 0)

            if is_cold or days_since >= self.COLD_DAYS_THRESHOLD:
                size_gb = bucket.get('size_gb', 0)
                if size_gb <= 0:
                    continue

                # Savings = moving from Standard to Glacier
                current_cost = round(size_gb * S3_STANDARD_PER_GB, 2)
                glacier_cost = round(size_gb * S3_GLACIER_PER_GB, 2)
                savings = round(current_cost - glacier_cost, 2)

                if savings <= 0:
                    continue

                results.append(RuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    resource_id=bname,
                    resource_type='S3',
                    recommendation_text=(
                        f'S3 bucket "{bname}" ({size_gb:.1f} GB) has not been accessed '
                        f'in {days_since} days. Move to S3 Glacier or Infrequent Access '
                        f'to save ~${savings:.2f}/month.'
                    ),
                    severity='MEDIUM' if size_gb >= 50 else 'LOW',
                    estimated_savings=savings,
                    details={
                        'bucket_name': bname,
                        'size_gb': size_gb,
                        'days_since_last_access': days_since,
                        'current_monthly_cost': current_cost,
                        'glacier_monthly_cost': glacier_cost,
                        'total_requests_90d': access_info.get('total_requests_90d', 0),
                    }
                ))

        return results
