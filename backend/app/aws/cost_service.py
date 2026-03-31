"""
Cost Explorer Service — fetches billing and cost data from AWS.
Read-only operations only.
"""
from datetime import datetime, timedelta
from botocore.exceptions import ClientError


class CostService:
    """Handles all AWS Cost Explorer API calls."""

    def __init__(self, client_factory):
        # Cost Explorer endpoint is always us-east-1
        self.ce = client_factory.get_client('ce')

    def get_monthly_cost(self, months: int = 3) -> dict:
        """Fetch monthly costs for the last N months."""
        try:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            start_date = (datetime.utcnow() - timedelta(days=months * 30)).strftime('%Y-%m-%d')

            response = self.ce.get_cost_and_usage(
                TimePeriod={'Start': start_date, 'End': end_date},
                Granularity='MONTHLY',
                Metrics=['UnblendedCost', 'UsageQuantity'],
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
            )

            monthly_data = []
            for result in response.get('ResultsByTime', []):
                period_start = result['TimePeriod']['Start']
                period_end = result['TimePeriod']['End']
                services = []
                total_cost = 0.0

                for group in result.get('Groups', []):
                    service_name = group['Keys'][0]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    usage = float(group['Metrics']['UsageQuantity']['Amount'])

                    if cost > 0.001:  # Filter near-zero costs
                        services.append({
                            'service': service_name,
                            'cost': round(cost, 2),
                            'usage': round(usage, 2),
                            'unit': group['Metrics']['UnblendedCost']['Unit']
                        })
                        total_cost += cost

                monthly_data.append({
                    'period_start': period_start,
                    'period_end': period_end,
                    'total_cost': round(total_cost, 2),
                    'services': sorted(services, key=lambda x: x['cost'], reverse=True)
                })

            return {
                'monthly_costs': monthly_data,
                'currency': 'USD',
                'total_period_cost': round(sum(m['total_cost'] for m in monthly_data), 2)
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                return {
                    'monthly_costs': [],
                    'currency': 'USD',
                    'total_period_cost': 0,
                    'error': 'Cost Explorer access denied. Enable Cost Explorer in AWS Console and ensure IAM has ce:GetCostAndUsage permission.'
                }
            return {
                'monthly_costs': [],
                'currency': 'USD',
                'total_period_cost': 0,
                'error': str(e)
            }

    def get_service_breakdown(self, days: int = 30) -> dict:
        """Get cost breakdown by service for the last N days."""
        try:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            start_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')

            response = self.ce.get_cost_and_usage(
                TimePeriod={'Start': start_date, 'End': end_date},
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
            )

            services = {}
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    service_name = group['Keys'][0]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    services[service_name] = services.get(service_name, 0) + cost

            breakdown = [
                {'service': k, 'cost': round(v, 2)}
                for k, v in sorted(services.items(), key=lambda x: x[1], reverse=True)
                if v > 0.001
            ]

            return {
                'period_days': days,
                'breakdown': breakdown,
                'total_cost': round(sum(item['cost'] for item in breakdown), 2)
            }
        except ClientError as e:
            return {'period_days': days, 'breakdown': [], 'total_cost': 0, 'error': str(e)}

    def get_daily_cost_trend(self, days: int = 30) -> dict:
        """Get daily cost trend for the last N days."""
        try:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            start_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')

            response = self.ce.get_cost_and_usage(
                TimePeriod={'Start': start_date, 'End': end_date},
                Granularity='DAILY',
                Metrics=['UnblendedCost']
            )

            daily_costs = []
            for result in response.get('ResultsByTime', []):
                date = result['TimePeriod']['Start']
                cost = float(result['Total']['UnblendedCost']['Amount'])
                daily_costs.append({
                    'date': date,
                    'cost': round(cost, 4)
                })

            return {
                'daily_costs': daily_costs,
                'period_days': days
            }
        except ClientError as e:
            return {'daily_costs': [], 'period_days': days, 'error': str(e)}

    def get_region_breakdown(self, days: int = 30) -> dict:
        """Get cost breakdown by region."""
        try:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            start_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')

            response = self.ce.get_cost_and_usage(
                TimePeriod={'Start': start_date, 'End': end_date},
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'REGION'}]
            )

            regions = {}
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    region = group['Keys'][0] or 'global'
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    regions[region] = regions.get(region, 0) + cost

            breakdown = [
                {'region': k, 'cost': round(v, 2)}
                for k, v in sorted(regions.items(), key=lambda x: x[1], reverse=True)
                if v > 0.001
            ]

            return {
                'period_days': days,
                'regions': breakdown,
                'total_cost': round(sum(item['cost'] for item in breakdown), 2)
            }
        except ClientError as e:
            return {'period_days': days, 'regions': [], 'total_cost': 0, 'error': str(e)}
