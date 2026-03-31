"""
Base Rule — abstract class that all optimization rules must extend.
Provides a consistent interface for the rule engine.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class RuleResult:
    """Represents a single finding from a rule evaluation."""
    rule_id: str
    rule_name: str
    resource_id: str
    resource_type: str
    recommendation_text: str
    severity: str           # 'LOW', 'MEDIUM', 'HIGH'
    estimated_savings: float  # Monthly USD savings estimate
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'resource_id': self.resource_id,
            'resource_type': self.resource_type,
            'recommendation_text': self.recommendation_text,
            'severity': self.severity,
            'estimated_savings': round(self.estimated_savings, 2),
            'details': self.details
        }


class BaseRule(ABC):
    """Abstract base class for all optimization rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique identifier for this rule (e.g., 'EC2_IDLE')."""
        pass

    @property
    @abstractmethod
    def rule_name(self) -> str:
        """Human-readable name for this rule."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this rule checks."""
        pass

    @property
    @abstractmethod
    def resource_type(self) -> str:
        """AWS resource type this rule analyzes (e.g., 'EC2', 'EBS', 'S3')."""
        pass

    @abstractmethod
    def evaluate(self, aws_data: dict) -> List[RuleResult]:
        """
        Evaluate the rule against collected AWS data.

        Args:
            aws_data: Dictionary containing all fetched AWS resource data.

        Returns:
            List of RuleResult objects for each finding.
        """
        pass

    def get_info(self) -> dict:
        """Return rule metadata."""
        return {
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'description': self.description,
            'resource_type': self.resource_type
        }
