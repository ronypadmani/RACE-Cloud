"""
RDS Service — fetches RDS instance data and CloudWatch metrics.
Read-only operations only.
"""
from datetime import datetime, timedelta
from botocore.exceptions import ClientError


class RDSService:
    """Handles all RDS-related AWS API calls."""

    def __init__(self, client_factory):
        self.rds = client_factory.get_client('rds')
        self.cloudwatch = client_factory.get_client('cloudwatch')

    def get_instances(self) -> list:
        """Fetch all RDS instances with their details."""
        try:
            response = self.rds.describe_db_instances()
            instances = []

            for db in response.get('DBInstances', []):
                instances.append({
                    'db_instance_id': db['DBInstanceIdentifier'],
                    'db_instance_class': db['DBInstanceClass'],
                    'engine': db['Engine'],
                    'engine_version': db.get('EngineVersion', ''),
                    'status': db['DBInstanceStatus'],
                    'multi_az': db.get('MultiAZ', False),
                    'storage_gb': db.get('AllocatedStorage', 0),
                    'storage_type': db.get('StorageType', ''),
                    'endpoint': db.get('Endpoint', {}).get('Address', ''),
                    'port': db.get('Endpoint', {}).get('Port', 0),
                    'availability_zone': db.get('AvailabilityZone', ''),
                    'create_time': db.get('InstanceCreateTime', '').isoformat()
                        if db.get('InstanceCreateTime') else ''
                })

            return instances
        except ClientError as e:
            return [{'error': str(e)}]

    def get_connection_count(self, db_instance_id: str, days: int = 7) -> dict:
        """Get database connection count over N days."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='DatabaseConnections',
                Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': db_instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average', 'Maximum']
            )

            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return {
                    'db_instance_id': db_instance_id,
                    'avg_connections': 0,
                    'max_connections': 0,
                    'period_days': days,
                    'is_idle': True
                }

            avg_conn = sum(dp['Average'] for dp in datapoints) / len(datapoints)
            max_conn = max(dp['Maximum'] for dp in datapoints)

            return {
                'db_instance_id': db_instance_id,
                'avg_connections': round(avg_conn, 2),
                'max_connections': round(max_conn, 2),
                'period_days': days,
                'is_idle': max_conn == 0
            }
        except ClientError:
            return {
                'db_instance_id': db_instance_id,
                'avg_connections': 0,
                'max_connections': 0,
                'period_days': days,
                'is_idle': False,
                'error': 'Could not fetch metrics'
            }

    def get_cpu_utilization(self, db_instance_id: str, days: int = 7) -> dict:
        """Get RDS CPU utilization over N days."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': db_instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average', 'Maximum']
            )

            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return {
                    'db_instance_id': db_instance_id,
                    'avg_cpu': 0.0,
                    'max_cpu': 0.0,
                    'period_days': days
                }

            avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints)
            max_cpu = max(dp['Maximum'] for dp in datapoints)

            return {
                'db_instance_id': db_instance_id,
                'avg_cpu': round(avg_cpu, 2),
                'max_cpu': round(max_cpu, 2),
                'period_days': days
            }
        except ClientError:
            return {
                'db_instance_id': db_instance_id,
                'avg_cpu': 0.0,
                'max_cpu': 0.0,
                'period_days': days
            }
