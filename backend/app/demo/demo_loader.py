"""
Demo Data Loader — reads mock AWS data from JSON files for demo mode.
"""
import os
import json

_DEMO_DIR = os.path.dirname(os.path.abspath(__file__))

# Runtime-switchable scenario (default comes from .env)
_current_file = os.getenv('DEMO_FILE', 'high_cost.json')

# Available scenarios
AVAILABLE_SCENARIOS = {
    'optimized': 'optimized.json',
    'high_cost': 'high_cost.json',
    'idle_resources': 'idle_resources.json',
}


def is_demo_mode() -> bool:
    """Check if demo mode is enabled."""
    return os.getenv('DEMO_MODE', 'false').lower() == 'true'


def get_current_scenario() -> str:
    """Return the name of the currently active scenario."""
    global _current_file
    for name, fname in AVAILABLE_SCENARIOS.items():
        if fname == _current_file:
            return name
    return _current_file


def set_scenario(scenario_name: str) -> bool:
    """Switch the active demo scenario at runtime. Returns True if valid."""
    global _current_file
    fname = AVAILABLE_SCENARIOS.get(scenario_name)
    if not fname:
        return False
    _current_file = fname
    return True


def load_demo_data() -> dict:
    """
    Load the current demo JSON file and return the full aws_data dict.
    The returned structure matches what _collect_aws_data() returns.
    """
    global _current_file
    path = os.path.join(_DEMO_DIR, _current_file)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Ensure the keys expected by the rule engine exist
    return {
        'ec2_instances': data.get('ec2_instances', []),
        'ebs_volumes': data.get('ebs_volumes', []),
        'elastic_ips': data.get('elastic_ips', []),
        's3_buckets': data.get('s3_buckets', []),
        'rds_instances': data.get('rds_instances', []),
        'cpu_metrics': data.get('cpu_metrics', {}),
        's3_access': data.get('s3_access', {}),
        'rds_connections': data.get('rds_connections', {}),
        'cost_data': data.get('cost_data', {}),
        # Extra keys used by specific endpoints
        'daily_costs': data.get('daily_costs', {}),
        'service_breakdown': data.get('service_breakdown', {}),
        'region_breakdown': data.get('region_breakdown', {}),
    }


def load_demo_cost_data() -> tuple:
    """Return (daily, monthly) cost dicts in the format CostService returns."""
    data = load_demo_data()
    daily = data.get('daily_costs', {'daily_costs': [], 'period_days': 30})
    monthly = data.get('cost_data', {'monthly_costs': [], 'currency': 'USD', 'total_period_cost': 0})
    return daily, monthly
