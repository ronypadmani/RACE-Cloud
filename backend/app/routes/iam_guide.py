"""
IAM Setup Guide route — provides educational content for creating IAM users.
This is displayed to users who haven't configured AWS credentials yet.
"""
from flask import Blueprint, jsonify

iam_guide_bp = Blueprint('iam_guide', __name__)


@iam_guide_bp.route('/guide', methods=['GET'])
def get_iam_guide():
    """Return the step-by-step IAM setup guide."""
    guide = {
        'title': 'How to Create an IAM User for RACE-Cloud',
        'description': (
            'RACE-Cloud requires read-only AWS credentials to monitor your resources. '
            'Follow these steps to create a secure IAM user with minimal permissions.'
        ),
        'prerequisites': [
            'An AWS account (Free Tier is sufficient)',
            'Access to the AWS Management Console',
            'Root account access (one-time only for IAM setup)'
        ],
        'important_notes': [
            'NEVER share your root account credentials',
            'The IAM user should have READ-ONLY access only',
            'RACE-Cloud will NEVER modify your AWS resources',
            'Store your access keys securely — they cannot be retrieved again after creation'
        ],
        'steps': [
            {
                'step': 1,
                'title': 'Sign in to AWS Console',
                'description': 'Go to https://console.aws.amazon.com and sign in with your root account.',
                'details': 'This is the only time you should use your root account for this project.',
                'icon': '🔐'
            },
            {
                'step': 2,
                'title': 'Navigate to IAM',
                'description': 'In the AWS Console, search for "IAM" in the search bar and select "IAM" from the results.',
                'details': 'IAM (Identity and Access Management) lets you create users with specific permissions.',
                'icon': '👤'
            },
            {
                'step': 3,
                'title': 'Create a New IAM User',
                'description': 'Click "Users" in the left sidebar, then click "Create user".',
                'details': 'Choose a descriptive name like "racecloud-readonly" for easy identification.',
                'icon': '➕'
            },
            {
                'step': 4,
                'title': 'Set Permissions',
                'description': 'Select "Attach policies directly" and search for "ReadOnlyAccess".',
                'details': (
                    'Attach the AWS managed policy "ReadOnlyAccess". '
                    'This policy allows viewing resources but prevents any modifications. '
                    'Additionally, attach "AWSBillingReadOnlyAccess" for cost data access.'
                ),
                'icon': '🛡️',
                'policies': [
                    {
                        'name': 'ReadOnlyAccess',
                        'arn': 'arn:aws:iam::aws:policy/ReadOnlyAccess',
                        'description': 'Provides read-only access to all AWS services'
                    },
                    {
                        'name': 'AWSBillingReadOnlyAccess',
                        'arn': 'arn:aws:iam::aws:policy/AWSBillingReadOnlyAccess',
                        'description': 'Provides read-only access to AWS billing data'
                    }
                ]
            },
            {
                'step': 5,
                'title': 'Review and Create',
                'description': 'Review the user details and click "Create user".',
                'details': 'Verify that only read-only policies are attached.',
                'icon': '✅'
            },
            {
                'step': 6,
                'title': 'Create Access Keys',
                'description': 'Click on the new user → "Security credentials" tab → "Create access key".',
                'details': (
                    'Select "Third-party service" as the use case. '
                    'You will receive an Access Key ID and Secret Access Key. '
                    'IMPORTANT: Save both keys immediately — the Secret Key is shown only once!'
                ),
                'icon': '🔑'
            },
            {
                'step': 7,
                'title': 'Enter Credentials in RACE-Cloud',
                'description': 'Go back to RACE-Cloud and enter your Access Key ID, Secret Access Key, and select your AWS region.',
                'details': (
                    'RACE-Cloud encrypts your credentials before storing them. '
                    'They are never stored in plain text and are only used for read-only API calls.'
                ),
                'icon': '📤'
            },
            {
                'step': 8,
                'title': 'Enable Cost Explorer (Optional)',
                'description': 'To see cost data, enable Cost Explorer in your AWS account.',
                'details': (
                    'Go to AWS Billing Console → Cost Explorer → Enable Cost Explorer. '
                    'Note: It may take 24 hours for cost data to become available after enabling. '
                    'Cost Explorer itself is free for the first year on the AWS Free Tier.'
                ),
                'icon': '💰'
            }
        ],
        'security_assurance': {
            'title': 'How RACE-Cloud Protects Your Credentials',
            'points': [
                'Credentials are encrypted using Fernet (AES-128-CBC) before storage',
                'Credentials are NEVER logged, displayed, or included in reports',
                'Only read-only API calls are made — your resources cannot be modified',
                'You can revoke the IAM access key at any time from the AWS Console',
                'Deleting your RACE-Cloud account removes all stored credentials'
            ]
        }
    }

    return jsonify(guide), 200
