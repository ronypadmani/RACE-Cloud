"""
Cross-Service Dependency Engine — detects waste chains by correlating
EC2 instances, EBS volumes, and Elastic IPs.
Read-only analysis only; never modifies AWS resources.
"""

# Approximate hourly on-demand costs (USD) used for estimation.
# These are conservative averages; real pricing varies by region and type.
INSTANCE_TYPE_HOURLY_COST = {
    't2.micro': 0.0116, 't2.small': 0.023, 't2.medium': 0.0464,
    't2.large': 0.0928, 't2.xlarge': 0.1856,
    't3.micro': 0.0104, 't3.small': 0.0208, 't3.medium': 0.0416,
    't3.large': 0.0832, 't3.xlarge': 0.1664,
    'm5.large': 0.096, 'm5.xlarge': 0.192, 'm5.2xlarge': 0.384,
    'm4.large': 0.10, 'm4.xlarge': 0.20,
    'c5.large': 0.085, 'c5.xlarge': 0.17,
    'r5.large': 0.126, 'r5.xlarge': 0.252,
}
DEFAULT_INSTANCE_HOURLY_COST = 0.10

EBS_GB_MONTHLY_COST = {
    'gp2': 0.10, 'gp3': 0.08,
    'io1': 0.125, 'io2': 0.125,
    'st1': 0.045, 'sc1': 0.015,
    'standard': 0.05,
}
DEFAULT_EBS_GB_MONTHLY = 0.10

EIP_IDLE_MONTHLY_COST = 3.60  # ~$0.005/hr when not associated


class DependencyEngine:
    """Analyzes cross-service relationships to find waste chains."""

    def __init__(self, aws_data: dict, cpu_metrics: dict | None = None):
        self.instances = aws_data.get('ec2_instances', [])
        self.volumes = aws_data.get('ebs_volumes', [])
        self.eips = aws_data.get('elastic_ips', [])
        self.cpu_metrics = cpu_metrics or aws_data.get('cpu_metrics', {})

    # ── public API ─────────────────────────────────────────────

    def detect_chains(self) -> list[dict]:
        """Return all detected dependency waste chains."""
        chains: list[dict] = []
        chains.extend(self._dead_infrastructure_chains())
        chains.extend(self._orphan_volume_chains())
        chains.extend(self._idle_eip_chains())
        # Sort by total waste descending
        chains.sort(key=lambda c: c['total_waste'], reverse=True)
        return chains

    # ── chain detectors ────────────────────────────────────────

    def _dead_infrastructure_chains(self) -> list[dict]:
        """
        EC2 is stopped **or** idle (CPU < 5 %) AND has attached EBS and/or EIP.
        """
        chains = []
        for inst in self.instances:
            if inst.get('error'):
                continue

            iid = inst['instance_id']
            is_stopped = inst['state'] == 'stopped'
            is_idle = False

            if inst['state'] == 'running':
                metrics = self.cpu_metrics.get(iid, {})
                avg_cpu = metrics.get('avg_cpu', 100)
                is_idle = avg_cpu < 5.0

            if not (is_stopped or is_idle):
                continue

            # Gather attached EBS volumes
            attached_vols = [
                v for v in self.volumes
                if not v.get('error') and v.get('attached_to') == iid
            ]
            # Gather associated EIPs
            attached_eips = [
                e for e in self.eips
                if not e.get('error') and e.get('instance_id') == iid
            ]

            if not attached_vols and not attached_eips:
                continue  # No chain — isolated instance

            resources = [{'type': 'EC2', 'id': iid, 'detail': inst['instance_type']}]
            total = self._ec2_monthly_cost(inst)

            for vol in attached_vols:
                cost = self._ebs_monthly_cost(vol)
                total += cost
                resources.append({
                    'type': 'EBS',
                    'id': vol['volume_id'],
                    'detail': f"{vol['size_gb']}GB {vol['volume_type']}",
                })

            for eip in attached_eips:
                # EIP attached to stopped/idle instance still costs when instance is stopped
                eip_cost = EIP_IDLE_MONTHLY_COST if is_stopped else 0
                total += eip_cost
                resources.append({
                    'type': 'EIP',
                    'id': eip.get('allocation_id') or eip['public_ip'],
                    'detail': eip['public_ip'],
                })

            status = 'stopped' if is_stopped else 'idle'
            chains.append({
                'chain_type': 'DEAD_INFRASTRUCTURE',
                'impact': 'HIGH' if total > 10 else ('MEDIUM' if total > 3 else 'LOW'),
                'trigger': f"EC2 {iid} is {status}",
                'resources': resources,
                'total_waste': round(total, 2),
                'recommendation': (
                    f"Terminate EC2 {iid} and delete associated resources to save "
                    f"~${total:.2f}/mo"
                ),
            })

        return chains

    def _orphan_volume_chains(self) -> list[dict]:
        """EBS volumes not attached to any instance."""
        chains = []
        for vol in self.volumes:
            if vol.get('error') or vol.get('attached_to'):
                continue
            if vol['state'] != 'available':
                continue
            cost = self._ebs_monthly_cost(vol)
            chains.append({
                'chain_type': 'ORPHAN_VOLUME',
                'impact': 'MEDIUM' if cost > 5 else 'LOW',
                'trigger': f"EBS {vol['volume_id']} is unattached",
                'resources': [{
                    'type': 'EBS',
                    'id': vol['volume_id'],
                    'detail': f"{vol['size_gb']}GB {vol['volume_type']}",
                }],
                'total_waste': round(cost, 2),
                'recommendation': (
                    f"Delete unattached volume {vol['volume_id']} to save ~${cost:.2f}/mo"
                ),
            })
        return chains

    def _idle_eip_chains(self) -> list[dict]:
        """Elastic IPs not associated with any resource."""
        chains = []
        for eip in self.eips:
            if eip.get('error') or eip.get('is_associated'):
                continue
            cost = EIP_IDLE_MONTHLY_COST
            eip_id = eip.get('allocation_id') or eip['public_ip']
            chains.append({
                'chain_type': 'IDLE_EIP',
                'impact': 'LOW',
                'trigger': f"EIP {eip['public_ip']} is unassociated",
                'resources': [{
                    'type': 'EIP',
                    'id': eip_id,
                    'detail': eip['public_ip'],
                }],
                'total_waste': round(cost, 2),
                'recommendation': (
                    f"Release Elastic IP {eip['public_ip']} to save ~${cost:.2f}/mo"
                ),
            })
        return chains

    # ── cost helpers ───────────────────────────────────────────

    @staticmethod
    def _ec2_monthly_cost(instance: dict) -> float:
        hourly = INSTANCE_TYPE_HOURLY_COST.get(
            instance.get('instance_type', ''),
            DEFAULT_INSTANCE_HOURLY_COST,
        )
        return hourly * 730  # avg hours/month

    @staticmethod
    def _ebs_monthly_cost(volume: dict) -> float:
        per_gb = EBS_GB_MONTHLY_COST.get(
            volume.get('volume_type', 'gp2'),
            DEFAULT_EBS_GB_MONTHLY,
        )
        return per_gb * volume.get('size_gb', 0)
