"""
Shared AWS Pricing Helper — fetches live EC2 / EBS prices from the
AWS Pricing API using the global keys in .env, with in-memory caching.
Falls back to hardcoded prices when the API is unavailable.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Region → Pricing API location mapping ──────────────────────────────────────

_REGION_LOCATION_MAP = {
    'us-east-1': 'US East (N. Virginia)',
    'us-west-2': 'US West (Oregon)',
    'eu-west-1': 'EU (Ireland)',
    'ap-south-1': 'Asia Pacific (Mumbai)',
    'ap-southeast-1': 'Asia Pacific (Singapore)',
}


def _region_to_location(region: str) -> str:
    return _REGION_LOCATION_MAP.get(region, 'US East (N. Virginia)')


# ── Hardcoded fallbacks ────────────────────────────────────────────────────────

FALLBACK_EC2_COSTS = {
    't2.micro': 8.50, 't2.small': 16.79, 't2.medium': 33.41,
    't2.large': 66.82, 't2.xlarge': 133.63,
    't3.micro': 7.59, 't3.small': 15.18, 't3.medium': 30.37,
    't3.large': 60.74, 't3.xlarge': 121.47,
    'm5.large': 70.08, 'm5.xlarge': 140.16,
    'c5.large': 62.05, 'c5.xlarge': 124.10,
    'r5.large': 91.98, 'r5.xlarge': 183.96,
}

FALLBACK_EBS_COSTS = {
    'gp2': 0.10, 'gp3': 0.08, 'io1': 0.125, 'io2': 0.125,
    'st1': 0.045, 'sc1': 0.015, 'standard': 0.05,
}

# ── In-memory cache (TTL = 1 hour) ────────────────────────────────────────────

_CACHE_TTL = 3600  # seconds
_price_cache: dict[str, tuple[float, float]] = {}  # key → (timestamp, price)


def _cache_get(key: str) -> Optional[float]:
    entry = _price_cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, price: float):
    _price_cache[key] = (time.time(), price)


# ── Pricing API client (lazy singleton) ────────────────────────────────────────

_pricing_client = None
_pricing_client_checked = False


def _get_pricing_client():
    """Return a boto3 Pricing API client, or None if credentials are missing."""
    global _pricing_client, _pricing_client_checked
    if _pricing_client_checked:
        return _pricing_client
    _pricing_client_checked = True

    access_key = os.getenv('AWS_PRICING_ACCESS_KEY', '').strip()
    secret_key = os.getenv('AWS_PRICING_SECRET_KEY', '').strip()
    if not access_key or not secret_key:
        logger.debug('No AWS_PRICING keys in .env — using fallback prices')
        return None

    try:
        import boto3
        client = boto3.client(
            'pricing',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='us-east-1',
        )
        client.describe_services(ServiceCode='AmazonEC2', MaxResults=1)
        _pricing_client = client
        logger.info('AWS Pricing API connected for recommendation pricing')
        return client
    except Exception as exc:
        logger.warning('AWS Pricing API unavailable: %s — using fallback prices', exc)
        return None


# ── Public helpers ─────────────────────────────────────────────────────────────

def get_ec2_monthly_cost(instance_type: str, region: str = 'us-east-1') -> float:
    """
    Return the monthly on-demand cost for an EC2 instance type.
    Tries live AWS Pricing API first, then falls back to hardcoded map.
    """
    cache_key = f'ec2:{instance_type}:{region}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    client = _get_pricing_client()
    if client:
        try:
            resp = client.get_products(
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
                            monthly = round(price * 730, 2)
                            _cache_set(cache_key, monthly)
                            return monthly
        except Exception as exc:
            logger.debug('EC2 live pricing failed for %s: %s', instance_type, exc)

    # Fallback
    cost = FALLBACK_EC2_COSTS.get(instance_type, 50.0)
    _cache_set(cache_key, cost)
    return cost


def get_ebs_cost_per_gb(volume_type: str, region: str = 'us-east-1') -> float:
    """
    Return the per-GB/month cost for an EBS volume type.
    Tries live AWS Pricing API first, then falls back to hardcoded map.
    """
    cache_key = f'ebs:{volume_type}:{region}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    client = _get_pricing_client()
    if client:
        try:
            # Map volume type codes to Pricing API values
            vol_api_map = {
                'gp2': 'General Purpose',
                'gp3': 'General Purpose',
                'io1': 'Provisioned IOPS',
                'io2': 'Provisioned IOPS',
                'st1': 'Throughput Optimized HDD',
                'sc1': 'Cold HDD',
                'standard': 'Magnetic',
            }
            vol_api_name = vol_api_map.get(volume_type)
            if vol_api_name:
                resp = client.get_products(
                    ServiceCode='AmazonEC2',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': _region_to_location(region)},
                        {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'},
                        {'Type': 'TERM_MATCH', 'Field': 'volumeApiName', 'Value': volume_type},
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
                                _cache_set(cache_key, price)
                                return price
        except Exception as exc:
            logger.debug('EBS live pricing failed for %s: %s', volume_type, exc)

    # Fallback
    cost = FALLBACK_EBS_COSTS.get(volume_type, 0.10)
    _cache_set(cache_key, cost)
    return cost
