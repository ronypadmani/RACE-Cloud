"""
What-If Simulation Engine — estimates cost impact of hypothetical actions
without touching AWS resources.  Pure read-only computation.
"""
from .dependency_engine import (
    INSTANCE_TYPE_HOURLY_COST,
    DEFAULT_INSTANCE_HOURLY_COST,
    EBS_GB_MONTHLY_COST,
    DEFAULT_EBS_GB_MONTHLY,
    EIP_IDLE_MONTHLY_COST,
)

VALID_ACTIONS = {'terminate_ec2', 'delete_ebs', 'release_eip'}


class SimulationEngine:
    """Simulates the cost effect of resource-level actions."""

    def __init__(self, aws_data: dict, cpu_metrics: dict | None = None):
        self.instances = {i['instance_id']: i for i in aws_data.get('ec2_instances', []) if not i.get('error')}
        self.volumes = {v['volume_id']: v for v in aws_data.get('ebs_volumes', []) if not v.get('error')}
        self.eips = {}
        for e in aws_data.get('elastic_ips', []):
            if not e.get('error'):
                key = e.get('allocation_id') or e['public_ip']
                self.eips[key] = e
        self.cpu_metrics = cpu_metrics or aws_data.get('cpu_metrics', {})

    # ── public API ─────────────────────────────────────────────

    def simulate(self, action_type: str, resource_id: str) -> dict:
        """
        Simulate a single action and return current vs projected cost.

        Returns
        -------
        dict  with keys: action, resource_id, current_cost, new_cost, savings,
              affected_resources, warnings
        """
        if action_type not in VALID_ACTIONS:
            return {
                'error': f"Unknown action '{action_type}'. "
                         f"Valid actions: {', '.join(sorted(VALID_ACTIONS))}"
            }

        handler = {
            'terminate_ec2': self._sim_terminate_ec2,
            'delete_ebs': self._sim_delete_ebs,
            'release_eip': self._sim_release_eip,
        }[action_type]

        result = handler(resource_id)
        result['action'] = action_type
        result['resource_id'] = resource_id
        return result

    def simulate_chain(self, chain: dict) -> dict:
        """Simulate removing every resource in a dependency chain at once."""
        total_current = 0.0
        affected: list[dict] = []

        for res in chain.get('resources', []):
            rtype = res['type']
            rid = res['id']
            action_map = {'EC2': 'terminate_ec2', 'EBS': 'delete_ebs', 'EIP': 'release_eip'}
            action = action_map.get(rtype)
            if not action:
                continue
            sim = self.simulate(action, rid)
            if 'error' not in sim:
                total_current += sim['current_cost']
                affected.append({'type': rtype, 'id': rid, 'savings': sim['savings']})

        return {
            'chain_type': chain.get('chain_type', ''),
            'current_cost': round(total_current, 2),
            'new_cost': 0.0,
            'savings': round(total_current, 2),
            'affected_resources': affected,
        }

    # ── simulation handlers ────────────────────────────────────

    def _sim_terminate_ec2(self, instance_id: str) -> dict:
        inst = self.instances.get(instance_id)
        if not inst:
            return self._not_found('EC2 instance', instance_id)

        ec2_cost = self._ec2_monthly(inst)
        cascade_cost = 0.0
        affected = [{'type': 'EC2', 'id': instance_id, 'savings': round(ec2_cost, 2)}]

        # Attached EBS volumes would also be deleted (unless DeleteOnTermination=false,
        # but we include them in the projection for max-savings estimate).
        for vol in self.volumes.values():
            if vol.get('attached_to') == instance_id:
                vol_cost = self._ebs_monthly(vol)
                cascade_cost += vol_cost
                affected.append({'type': 'EBS', 'id': vol['volume_id'], 'savings': round(vol_cost, 2)})

        # Associated EIP becomes idle → incurs cost itself, so releasing it saves more
        for eip in self.eips.values():
            if eip.get('instance_id') == instance_id:
                eip_id = eip.get('allocation_id') or eip['public_ip']
                affected.append({
                    'type': 'EIP', 'id': eip_id,
                    'savings': round(EIP_IDLE_MONTHLY_COST, 2),
                    'warning': 'EIP will become idle and incur charges; release it too.',
                })
                cascade_cost += EIP_IDLE_MONTHLY_COST

        current = ec2_cost + cascade_cost
        return {
            'current_cost': round(current, 2),
            'new_cost': 0.0,
            'savings': round(current, 2),
            'affected_resources': affected,
            'warnings': [a['warning'] for a in affected if 'warning' in a],
        }

    def _sim_delete_ebs(self, volume_id: str) -> dict:
        vol = self.volumes.get(volume_id)
        if not vol:
            return self._not_found('EBS volume', volume_id)

        cost = self._ebs_monthly(vol)
        warnings = []
        if vol.get('attached_to'):
            warnings.append(
                f"Volume is attached to {vol['attached_to']}; detach before deleting."
            )

        return {
            'current_cost': round(cost, 2),
            'new_cost': 0.0,
            'savings': round(cost, 2),
            'affected_resources': [{'type': 'EBS', 'id': volume_id, 'savings': round(cost, 2)}],
            'warnings': warnings,
        }

    def _sim_release_eip(self, eip_id: str) -> dict:
        eip = self.eips.get(eip_id)
        if not eip:
            return self._not_found('Elastic IP', eip_id)

        # Cost only applies when EIP is idle (not associated)
        is_idle = not eip.get('is_associated')
        cost = EIP_IDLE_MONTHLY_COST if is_idle else 0.0
        warnings = []
        if eip.get('is_associated'):
            warnings.append(
                f"EIP is currently associated to {eip.get('instance_id', 'unknown')}; "
                "releasing will disassociate it first."
            )

        return {
            'current_cost': round(cost, 2),
            'new_cost': 0.0,
            'savings': round(cost, 2),
            'affected_resources': [{'type': 'EIP', 'id': eip_id, 'savings': round(cost, 2)}],
            'warnings': warnings,
        }

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _ec2_monthly(instance: dict) -> float:
        hourly = INSTANCE_TYPE_HOURLY_COST.get(
            instance.get('instance_type', ''), DEFAULT_INSTANCE_HOURLY_COST
        )
        return hourly * 730

    @staticmethod
    def _ebs_monthly(volume: dict) -> float:
        per_gb = EBS_GB_MONTHLY_COST.get(
            volume.get('volume_type', 'gp2'), DEFAULT_EBS_GB_MONTHLY
        )
        return per_gb * volume.get('size_gb', 0)

    @staticmethod
    def _not_found(resource_type: str, resource_id: str) -> dict:
        return {
            'error': f"{resource_type} '{resource_id}' not found in current data.",
            'current_cost': 0, 'new_cost': 0, 'savings': 0,
            'affected_resources': [], 'warnings': [],
        }
