"""
S3 Service — fetches S3 bucket data and access metrics.
Read-only operations only.
"""
from datetime import datetime, timedelta
from botocore.exceptions import ClientError


class S3Service:
    """Handles all S3-related AWS API calls."""

    def __init__(self, client_factory):
        self.s3 = client_factory.get_client('s3')
        self.cloudwatch = client_factory.get_client('cloudwatch')

    def get_buckets(self) -> list:
        """Fetch all S3 buckets with metadata."""
        try:
            response = self.s3.list_buckets()
            buckets = []

            for bucket in response.get('Buckets', []):
                bucket_name = bucket['Name']
                creation_date = bucket.get('CreationDate', '')

                # Get bucket size and object count from CloudWatch
                size_bytes = self._get_bucket_size(bucket_name)
                object_count = self._get_bucket_object_count(bucket_name)

                # Get bucket region
                try:
                    location = self.s3.get_bucket_location(Bucket=bucket_name)
                    region = location.get('LocationConstraint') or 'us-east-1'
                except ClientError:
                    region = 'unknown'

                buckets.append({
                    'bucket_name': bucket_name,
                    'creation_date': creation_date.isoformat() if creation_date else '',
                    'region': region,
                    'size_bytes': size_bytes,
                    'size_gb': round(size_bytes / (1024 ** 3), 3) if size_bytes else 0,
                    'object_count': object_count
                })

            return buckets
        except ClientError as e:
            return [{'error': str(e)}]

    def _get_bucket_size(self, bucket_name: str) -> int:
        """Get bucket size in bytes from CloudWatch."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=2)

            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='BucketSizeBytes',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'StorageType', 'Value': 'StandardStorage'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )
            datapoints = response.get('Datapoints', [])
            return int(datapoints[-1]['Average']) if datapoints else 0
        except ClientError:
            return 0

    def _get_bucket_object_count(self, bucket_name: str) -> int:
        """Get the number of objects in a bucket from CloudWatch."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=2)

            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='NumberOfObjects',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )
            datapoints = response.get('Datapoints', [])
            return int(datapoints[-1]['Average']) if datapoints else 0
        except ClientError:
            return 0

    def get_bucket_last_access(self, bucket_name: str) -> dict:
        """Estimate last access time based on request metrics."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=90)

            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='AllRequests',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'FilterId', 'Value': 'EntireBucket'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400 * 7,  # Weekly
                Statistics=['Sum']
            )

            datapoints = response.get('Datapoints', [])
            total_requests = sum(dp['Sum'] for dp in datapoints) if datapoints else 0

            days_since_access = 90 if total_requests == 0 else 0
            if datapoints and total_requests > 0:
                sorted_dps = sorted(datapoints, key=lambda x: x['Timestamp'], reverse=True)
                for dp in sorted_dps:
                    if dp['Sum'] > 0:
                        days_since_access = (end_time - dp['Timestamp'].replace(tzinfo=None)).days
                        break

            return {
                'bucket_name': bucket_name,
                'total_requests_90d': int(total_requests),
                'days_since_last_access': days_since_access,
                'is_cold': days_since_access >= 90
            }
        except ClientError:
            return {
                'bucket_name': bucket_name,
                'total_requests_90d': 0,
                'days_since_last_access': -1,
                'is_cold': False
            }
