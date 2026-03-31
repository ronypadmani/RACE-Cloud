"""
Cost Engine — calculates AWS costs using the AWS Pricing API (boto3).
Falls back to curated pricing only when AWS credentials are unavailable.
Generates Cheap / Balanced / Performance options across regions.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Regions for multi-option comparison ────────────────────────────────────────

REGIONS = ['ap-south-1', 'us-east-1', 'eu-west-1']

# ── Tier configuration ─────────────────────────────────────────────────────────

TIER_CONFIG = {
    'CHEAP': {
        'label': 'Cheapest',
        'icon': '💰',
        'region': 'ap-south-1',
        'instance_family': 't3.micro',
        'rds_class': 'db.t3.micro',
        'multiplier': 1.0,
        'description': 'Minimal resources in the cheapest AWS region. Best for prototypes and low-traffic apps.',
    },
    'BALANCED': {
        'label': 'Balanced',
        'icon': '⚖️',
        'region': 'us-east-1',
        'instance_family': 't3.medium',
        'rds_class': 'db.t3.medium',
        'multiplier': 2.5,
        'description': 'Solid price-performance balance. Suitable for production workloads with moderate traffic.',
    },
    'PERFORMANCE': {
        'label': 'Performance',
        'icon': '🚀',
        'region': 'us-east-1',
        'instance_family': 'm5.large',
        'rds_class': 'db.m5.large',
        'multiplier': 5.0,
        'description': 'Maximum performance and high availability. Built for scale-intensive production systems.',
    },
}

_SCALABILITY_LEVELS = ['Low', 'Medium', 'High', 'Very High']

_SCAL_ADJ = {'CHEAP': -1, 'BALANCED': 0, 'PERFORMANCE': 1}


# ── AWS Pricing API integration ────────────────────────────────────────────────

def _fetch_ec2_price(pricing_client, region: str, instance_type: str) -> Optional[float]:
    """Fetch on-demand EC2 hourly price from AWS Pricing API."""
    try:
        resp = pricing_client.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': _region_to_location(region)},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
            ],
            MaxResults=1,
        )
        for item in resp.get('PriceList', []):
            data = json.loads(item) if isinstance(item, str) else item
            terms = data.get('terms', {}).get('OnDemand', {})
            for term in terms.values():
                for dim in term.get('priceDimensions', {}).values():
                    price = float(dim['pricePerUnit'].get('USD', 0))
                    if price > 0:
                        return price * 730  # monthly
    except Exception as exc:
        logger.debug('EC2 pricing lookup failed: %s', exc)
    return None


def _fetch_rds_price(pricing_client, region: str, db_class: str) -> Optional[float]:
    """Fetch on-demand RDS hourly price from AWS Pricing API."""
    try:
        resp = pricing_client.get_products(
            ServiceCode='AmazonRDS',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': db_class},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': _region_to_location(region)},
                {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': 'MySQL'},
                {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': 'Single-AZ'},
            ],
            MaxResults=1,
        )
        for item in resp.get('PriceList', []):
            data = json.loads(item) if isinstance(item, str) else item
            terms = data.get('terms', {}).get('OnDemand', {})
            for term in terms.values():
                for dim in term.get('priceDimensions', {}).values():
                    price = float(dim['pricePerUnit'].get('USD', 0))
                    if price > 0:
                        return price * 730
    except Exception as exc:
        logger.debug('RDS pricing lookup failed: %s', exc)
    return None


def _fetch_s3_price(pricing_client, region: str) -> Optional[float]:
    """Fetch S3 standard storage price per GB/month."""
    try:
        resp = pricing_client.get_products(
            ServiceCode='AmazonS3',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': _region_to_location(region)},
                {'Type': 'TERM_MATCH', 'Field': 'storageClass', 'Value': 'General Purpose'},
                {'Type': 'TERM_MATCH', 'Field': 'volumeType', 'Value': 'Standard'},
            ],
            MaxResults=1,
        )
        for item in resp.get('PriceList', []):
            data = json.loads(item) if isinstance(item, str) else item
            terms = data.get('terms', {}).get('OnDemand', {})
            for term in terms.values():
                for dim in term.get('priceDimensions', {}).values():
                    price = float(dim['pricePerUnit'].get('USD', 0))
                    if price > 0:
                        return price
    except Exception as exc:
        logger.debug('S3 pricing lookup failed: %s', exc)
    return None


def _fetch_lambda_price(pricing_client, region: str) -> Optional[float]:
    """Fetch Lambda per-request price."""
    try:
        resp = pricing_client.get_products(
            ServiceCode='AWSLambda',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': _region_to_location(region)},
                {'Type': 'TERM_MATCH', 'Field': 'group', 'Value': 'AWS-Lambda-Requests'},
            ],
            MaxResults=1,
        )
        for item in resp.get('PriceList', []):
            data = json.loads(item) if isinstance(item, str) else item
            terms = data.get('terms', {}).get('OnDemand', {})
            for term in terms.values():
                for dim in term.get('priceDimensions', {}).values():
                    price = float(dim['pricePerUnit'].get('USD', 0))
                    if price > 0:
                        return price
    except Exception as exc:
        logger.debug('Lambda pricing lookup failed: %s', exc)
    return None


def _fetch_cloudfront_price(pricing_client, region: str) -> Optional[float]:
    """Fetch CloudFront per-GB transfer price."""
    try:
        resp = pricing_client.get_products(
            ServiceCode='AmazonCloudFront',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': _region_to_location(region)},
            ],
            MaxResults=1,
        )
        for item in resp.get('PriceList', []):
            data = json.loads(item) if isinstance(item, str) else item
            terms = data.get('terms', {}).get('OnDemand', {})
            for term in terms.values():
                for dim in term.get('priceDimensions', {}).values():
                    price = float(dim['pricePerUnit'].get('USD', 0))
                    if price > 0:
                        return price
    except Exception as exc:
        logger.debug('CloudFront pricing lookup failed: %s', exc)
    return None


_REGION_LOCATION_MAP = {
    'us-east-1': 'US East (N. Virginia)',
    'us-west-2': 'US West (Oregon)',
    'eu-west-1': 'EU (Ireland)',
    'ap-south-1': 'Asia Pacific (Mumbai)',
    'ap-southeast-1': 'Asia Pacific (Singapore)',
}


def _region_to_location(region: str) -> str:
    return _REGION_LOCATION_MAP.get(region, 'US East (N. Virginia)')


# ── Fallback pricing (used when no AWS credentials) ───────────────────────────

_FALLBACK_PRICES: dict[str, dict[str, float]] = {
    'us-east-1': {
        'EC2': 8.50, 'S3': 0.55, 'Lambda': 0.20, 'RDS': 14.00,
        'CloudFront': 1.10, 'DynamoDB': 1.30, 'ElastiCache': 13.00,
        'SageMaker': 28.00, 'ECS': 11.00, 'API Gateway': 0.55,
        'EBS': 1.10, 'SNS': 0.10, 'SQS': 0.10, 'Route 53': 0.50,
        'Cognito': 0.00, 'CloudWatch': 0.30, 'EKS': 73.00,
        'Fargate': 9.50, 'Step Functions': 0.25, 'EventBridge': 0.10,
        'Kinesis': 13.00, 'Redshift': 180.00, 'Athena': 5.00,
        'Glue': 4.40, 'Bedrock': 3.00, 'AppSync': 0.40,
    },
    'ap-south-1': {
        'EC2': 7.50, 'S3': 0.50, 'Lambda': 0.20, 'RDS': 12.50,
        'CloudFront': 1.00, 'DynamoDB': 1.25, 'ElastiCache': 12.00,
        'SageMaker': 25.00, 'ECS': 10.00, 'API Gateway': 0.50,
        'EBS': 1.00, 'SNS': 0.10, 'SQS': 0.10, 'Route 53': 0.50,
        'Cognito': 0.00, 'CloudWatch': 0.25, 'EKS': 73.00,
        'Fargate': 8.50, 'Step Functions': 0.25, 'EventBridge': 0.10,
        'Kinesis': 12.00, 'Redshift': 160.00, 'Athena': 5.00,
        'Glue': 4.40, 'Bedrock': 3.00, 'AppSync': 0.40,
    },
    'eu-west-1': {
        'EC2': 9.50, 'S3': 0.60, 'Lambda': 0.22, 'RDS': 15.50,
        'CloudFront': 1.20, 'DynamoDB': 1.40, 'ElastiCache': 14.50,
        'SageMaker': 30.00, 'ECS': 12.00, 'API Gateway': 0.60,
        'EBS': 1.20, 'SNS': 0.12, 'SQS': 0.12, 'Route 53': 0.50,
        'Cognito': 0.00, 'CloudWatch': 0.35, 'EKS': 73.00,
        'Fargate': 10.50, 'Step Functions': 0.25, 'EventBridge': 0.10,
        'Kinesis': 14.00, 'Redshift': 195.00, 'Athena': 5.00,
        'Glue': 4.40, 'Bedrock': 3.00, 'AppSync': 0.40,
    },
}


def _get_live_prices(services: list[str], region: str, tier: str,
                     client_factory) -> Optional[dict[str, float]]:
    """
    Attempt to fetch real prices from AWS Pricing API.
    Returns a dict {service: monthly_cost} or None if unavailable.
    """
    try:
        # Pricing API is only in us-east-1 / ap-south-1
        import boto3
        pricing = boto3.client(
            'pricing',
            aws_access_key_id=client_factory._access_key,
            aws_secret_access_key=client_factory._secret_key,
            region_name='us-east-1',
        )
        # Quick probe
        pricing.describe_services(ServiceCode='AmazonEC2', MaxResults=1)
    except Exception:
        return None

    tier_cfg = TIER_CONFIG[tier]
    prices: dict[str, float] = {}

    for svc in services:
        if svc == 'EC2':
            p = _fetch_ec2_price(pricing, region, tier_cfg['instance_family'])
            if p is not None:
                prices[svc] = p
        elif svc == 'RDS':
            p = _fetch_rds_price(pricing, region, tier_cfg['rds_class'])
            if p is not None:
                prices[svc] = p
        elif svc == 'S3':
            p = _fetch_s3_price(pricing, region)
            if p is not None:
                prices[svc] = max(p * 50, 0.50)  # estimate 50GB
        elif svc == 'Lambda':
            p = _fetch_lambda_price(pricing, region)
            if p is not None:
                prices[svc] = max(p * 1_000_000, 0.20)  # 1M requests
        elif svc == 'CloudFront':
            p = _fetch_cloudfront_price(pricing, region)
            if p is not None:
                prices[svc] = max(p * 100, 1.00)  # 100 GB transfer

    return prices if prices else None


def _get_service_cost(
    services: list[str],
    region: str,
    tier: str,
    estimated_usage: dict,
    client_factory=None,
) -> tuple[float, dict[str, float], bool]:
    """
    Calculate total monthly cost for a set of services.
    Returns (total, per_service_breakdown, used_live_pricing).
    """
    live_prices = None
    if client_factory:
        live_prices = _get_live_prices(services, region, tier, client_factory)

    fallback = _FALLBACK_PRICES.get(region, _FALLBACK_PRICES['us-east-1'])
    multiplier = TIER_CONFIG[tier]['multiplier']

    # Adjust multiplier based on estimated_usage
    usage_factor = 1.0
    compute = estimated_usage.get('compute_hours', 0)
    storage = estimated_usage.get('storage_gb', 0)
    requests = estimated_usage.get('requests', 0)
    if compute > 500:
        usage_factor += 0.5
    if storage > 100:
        usage_factor += 0.3
    if requests > 1_000_000:
        usage_factor += 0.4

    breakdown: dict[str, float] = {}
    for svc in services:
        if live_prices and svc in live_prices:
            base = live_prices[svc]
        else:
            base = fallback.get(svc, 5.0)
        cost = base * multiplier * usage_factor
        breakdown[svc] = round(cost, 2)

    total = round(sum(breakdown.values()), 2)
    return total, breakdown, live_prices is not None


def _resolve_scalability(base: str, tier: str) -> str:
    idx = _SCALABILITY_LEVELS.index(base) if base in _SCALABILITY_LEVELS else 2
    adj = _SCAL_ADJ.get(tier, 0)
    idx = max(0, min(len(_SCALABILITY_LEVELS) - 1, idx + adj))
    return _SCALABILITY_LEVELS[idx]


# ── Public entry point ─────────────────────────────────────────────────────────

def calculate_cost_options(
    services: list[str],
    base_scalability: str = 'High',
    budget: float = 100.0,
    estimated_usage: dict | None = None,
    client_factory=None,
) -> dict:
    """
    Generate 3 cost tiers (Cheap/Balanced/Performance) with per-region comparison.

    Returns
    -------
    dict with keys:
        options: list of 3 tier dicts (each with breakdown)
        region_comparison: list of costs across all 3 regions
        cheapest_cost, highest_cost, budget, within_budget
        pricing_source: 'live' | 'estimated'
    """
    estimated_usage = estimated_usage or {'compute_hours': 0, 'storage_gb': 0, 'requests': 0}
    options: list[dict] = []
    any_live = False

    for tier, cfg in TIER_CONFIG.items():
        region = cfg['region']
        total, breakdown, is_live = _get_service_cost(
            services, region, tier, estimated_usage, client_factory,
        )
        if is_live:
            any_live = True

        options.append({
            'type': tier,
            'label': cfg['label'],
            'icon': cfg['icon'],
            'region': region,
            'estimated_cost': total,
            'scalability': _resolve_scalability(base_scalability, tier),
            'description': cfg['description'],
            'breakdown': breakdown,
            'services': services,
        })

    # Region comparison — show each tier's cost in all 3 regions
    region_comparison: list[dict] = []
    for region in REGIONS:
        costs: dict[str, float] = {}
        for tier in TIER_CONFIG:
            total, _, _ = _get_service_cost(
                services, region, tier, estimated_usage, client_factory,
            )
            costs[tier] = total
        region_comparison.append({'region': region, **costs})

    cheapest = min(o['estimated_cost'] for o in options)
    highest = max(o['estimated_cost'] for o in options)

    return {
        'options': options,
        'region_comparison': region_comparison,
        'cheapest_cost': cheapest,
        'highest_cost': highest,
        'budget': budget,
        'within_budget': cheapest <= budget,
        'pricing_source': 'live' if any_live else 'estimated',
    }
