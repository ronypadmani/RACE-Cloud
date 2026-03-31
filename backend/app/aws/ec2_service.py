"""
EC2 Service — fetches EC2 instance data and CloudWatch metrics.
Read-only operations only.
"""
from datetime import datetime, timedelta
from botocore.exceptions import ClientError


class EC2Service:
    """Handles all EC2-related AWS API calls."""

    def __init__(self, client_factory):
        self.ec2 = client_factory.get_client('ec2')
        self.cloudwatch = client_factory.get_client('cloudwatch')

    def get_instances(self) -> list:
        """Fetch all EC2 instances with their details."""
        try:
            response = self.ec2.describe_instances()
            instances = []

            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    name = ''
                    for tag in instance.get('Tags', []):
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                            break

                    instances.append({
                        'instance_id': instance['InstanceId'],
                        'name': name,
                        'instance_type': instance['InstanceType'],
                        'state': instance['State']['Name'],
                        'launch_time': instance.get('LaunchTime', '').isoformat()
                            if instance.get('LaunchTime') else '',
                        'availability_zone': instance.get('Placement', {}).get('AvailabilityZone', ''),
                        'public_ip': instance.get('PublicIpAddress', ''),
                        'private_ip': instance.get('PrivateIpAddress', ''),
                        'platform': instance.get('Platform', 'linux'),
                        'monitoring': instance.get('Monitoring', {}).get('State', 'disabled'),
                    })

            return instances
        except ClientError as e:
            return [{'error': str(e)}]

    def get_cpu_utilization(self, instance_id: str, days: int = 14) -> dict:
        """Fetch average CPU utilization for an EC2 instance over N days."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Average', 'Maximum']
            )

            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return {
                    'instance_id': instance_id,
                    'avg_cpu': 0.0,
                    'max_cpu': 0.0,
                    'datapoints': 0,
                    'period_days': days
                }

            avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints)
            max_cpu = max(dp['Maximum'] for dp in datapoints)

            return {
                'instance_id': instance_id,
                'avg_cpu': round(avg_cpu, 2),
                'max_cpu': round(max_cpu, 2),
                'datapoints': len(datapoints),
                'period_days': days
            }
        except ClientError:
            return {
                'instance_id': instance_id,
                'avg_cpu': 0.0,
                'max_cpu': 0.0,
                'datapoints': 0,
                'period_days': days,
                'error': 'Could not fetch metrics'
            }

    def get_network_utilization(self, instance_id: str, days: int = 7) -> dict:
        """Fetch network I/O metrics for an EC2 instance."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            result = {}

            for metric in ['NetworkIn', 'NetworkOut']:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName=metric,
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=['Average']
                )
                datapoints = response.get('Datapoints', [])
                avg = sum(dp['Average'] for dp in datapoints) / len(datapoints) if datapoints else 0
                result[metric.lower()] = round(avg, 2)

            return {'instance_id': instance_id, **result}
        except ClientError:
            return {'instance_id': instance_id, 'networkin': 0, 'networkout': 0}

    def get_volumes(self) -> list:
        """Fetch all EBS volumes."""
        try:
            response = self.ec2.describe_volumes()
            volumes = []

            for vol in response.get('Volumes', []):
                name = ''
                for tag in vol.get('Tags', []):
                    if tag['Key'] == 'Name':
                        name = tag['Value']
                        break

                attachments = vol.get('Attachments', [])
                attached_to = attachments[0]['InstanceId'] if attachments else None

                volumes.append({
                    'volume_id': vol['VolumeId'],
                    'name': name,
                    'size_gb': vol['Size'],
                    'volume_type': vol['VolumeType'],
                    'state': vol['State'],
                    'attached_to': attached_to,
                    'availability_zone': vol['AvailabilityZone'],
                    'iops': vol.get('Iops', 0),
                    'create_time': vol.get('CreateTime', '').isoformat()
                        if vol.get('CreateTime') else ''
                })

            return volumes
        except ClientError as e:
            return [{'error': str(e)}]

    def get_elastic_ips(self) -> list:
        """Fetch all Elastic IPs and their association status."""
        try:
            response = self.ec2.describe_addresses()
            eips = []

            for addr in response.get('Addresses', []):
                eips.append({
                    'public_ip': addr['PublicIp'],
                    'allocation_id': addr.get('AllocationId', ''),
                    'association_id': addr.get('AssociationId', ''),
                    'instance_id': addr.get('InstanceId', ''),
                    'is_associated': bool(addr.get('AssociationId')),
                    'domain': addr.get('Domain', '')
                })

            return eips
        except ClientError as e:
            return [{'error': str(e)}]

    def get_instance_type_info(self) -> dict:
        """Map of common old-gen instance types to current-gen equivalents."""
        return {
            't1.micro': 't3.micro',
            'm1.small': 't3.small',
            'm1.medium': 't3.medium',
            'm1.large': 'm5.large',
            'm1.xlarge': 'm5.xlarge',
            'm3.medium': 'm5.medium',
            'm3.large': 'm5.large',
            'm3.xlarge': 'm5.xlarge',
            'c1.medium': 'c5.large',
            'c1.xlarge': 'c5.xlarge',
            'c3.large': 'c5.large',
            'c3.xlarge': 'c5.xlarge',
            'r3.large': 'r5.large',
            'r3.xlarge': 'r5.xlarge',
            'i2.xlarge': 'i3.xlarge',
            't2.micro': 't3.micro',
            't2.small': 't3.small',
            't2.medium': 't3.medium',
        }
