"""
AWS Client Factory — creates boto3 clients using decrypted IAM credentials.
The ONLY place in the application that instantiates AWS SDK clients.
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
from ..security import decrypt_credential


class AWSClientFactory:
    """Creates boto3 clients from encrypted credentials stored in the database."""

    def __init__(self, encrypted_access_key: str, encrypted_secret_key: str, region: str):
        self._access_key = decrypt_credential(encrypted_access_key)
        self._secret_key = decrypt_credential(encrypted_secret_key)
        self._region = region

    def get_client(self, service_name: str):
        """Create a boto3 client for the specified AWS service."""
        return boto3.client(
            service_name,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region
        )

    def get_resource(self, service_name: str):
        """Create a boto3 resource for the specified AWS service."""
        return boto3.resource(
            service_name,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region
        )

    @staticmethod
    def validate_credentials(access_key: str, secret_key: str, region: str) -> dict:
        """
        Validate AWS credentials by making a simple STS call.
        Returns account info if valid, error details if not.
        """
        try:
            sts = boto3.client(
                'sts',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            identity = sts.get_caller_identity()
            return {
                'valid': True,
                'account_id': identity['Account'],
                'arn': identity['Arn'],
                'user_id': identity['UserId']
            }
        except NoCredentialsError:
            return {'valid': False, 'error': 'No credentials provided'}
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidClientTokenId':
                return {'valid': False, 'error': 'Invalid Access Key ID'}
            elif error_code == 'SignatureDoesNotMatch':
                return {'valid': False, 'error': 'Invalid Secret Access Key'}
            elif error_code == 'AccessDenied':
                return {'valid': False, 'error': 'Access denied — check IAM permissions'}
            return {'valid': False, 'error': f'AWS Error: {error_code}'}
        except EndpointConnectionError:
            return {'valid': False, 'error': 'Cannot connect to AWS — check region and network'}
        except Exception as e:
            return {'valid': False, 'error': f'Unexpected error: {str(e)}'}
