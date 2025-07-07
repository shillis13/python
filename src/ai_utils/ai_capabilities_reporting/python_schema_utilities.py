#!/usr/bin/env python3
"""
Python AI Capabilities Schema Integration Utilities
Equivalent to schema_integration_utilities.js for managing AI platform assessments
"""

import copy
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Import existing utilities
try:
    from helpers import get_utc_timestamp, load_yaml, save_yaml
except ImportError:
    # Fallback implementations
    def get_utc_timestamp():
        return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    
    def load_yaml(filepath):
        import yaml
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    
    def save_yaml(data, filepath):
        import yaml
        with open(filepath, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, indent=2, sort_keys=False)


class AICapabilitiesManager:
    """Python equivalent of JavaScript AICapabilitiesManager class"""
    
    def __init__(self):
        self.capabilities: Dict[str, Dict[str, Any]] = {}
        self.universal_schema = self.get_universal_schema()
        self.supported_platforms = ["claude", "chatgpt", "gemini", "grok"]
    
    def initialize_assessment(self, platform: str, version: str = "", 
                            assessor_name: str = "") -> Dict[str, Any]:
        """
        Initialize a new capabilities assessment for a platform
        
        Args:
            platform: AI platform name (claude, chatgpt, gemini, grok)
            version: Platform version string
            assessor_name: Name of person doing assessment
            
        Returns:
            Dict: Initialized assessment structure
        """
        platform_lower = platform.lower()
        if platform_lower not in self.supported_platforms:
            raise ValueError(f"Unknown platform: {platform}. Supported: {', '.join(self.supported_platforms)}")
        
        # Deep copy the universal schema
        assessment = copy.deepcopy(self.universal_schema)
        
        # Update metadata with platform-specific information
        assessment['metadata']['platform'] = platform_lower
        assessment['metadata']['platform_version'] = version or self.get_default_version(platform_lower)
        assessment['metadata']['assessment_date'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        assessment['metadata']['assessor_info']['evaluator_name'] = assessor_name
        
        # Calculate next assessment date (3 months from now)
        from datetime import timedelta
        next_assessment = datetime.now(timezone.utc) + timedelta(days=90)
        assessment['metadata']['next_assessment_due'] = next_assessment.isoformat().replace('+00:00', 'Z')
        
        self.capabilities[platform_lower] = assessment
        return assessment
    
    def get_default_version(self, platform: str) -> str:
        """Get default version for platform"""
        defaults = {
            'claude': 'claude-4-Opus',
            'chatgpt': 'gpt-4.5',
            'gemini': 'gemini-2.5-pro',
            'grok': 'grok-3'
        }
        return defaults.get(platform, 'unknown')
    
    def update_capability(self, platform: str, capability_path: str, new_value: Any,
                         evidence: List[str] = None, confidence: str = "medium") -> None:
        """
        Update a capability with new findings
        
        Args:
            platform: Platform name
            capability_path: Dot-notation path to capability (e.g., 'core_capabilities.reasoning.logical_reasoning.capability_level')
            new_value: New value to set
            evidence: List of evidence supporting the update
            confidence: Confidence level (low, medium, high)
        """
        if evidence is None:
            evidence = []
            
        if platform not in self.capabilities:
            raise ValueError(f"No assessment initialized for platform: {platform}")
        
        assessment = self.capabilities[platform]
        path_array = capability_path.split('.')
        
        # Navigate to the capability location
        current = assessment
        for i in range(len(path_array) - 1):
            if path_array[i] not in current:
                current[path_array[i]] = {}
            current = current[path_array[i]]
        
        # Store old value for changelog
        old_value = current.get(path_array[-1])
        
        # Update the value
        current[path_array[-1]] = new_value
        
        # Update metadata if structure supports it
        if isinstance(current, dict):
            if 'confidence' in current:
                current['confidence'] = confidence
            if 'evidence' in current:
                current['evidence'] = list(evidence)
            if 'testing_date' in current:
                current['testing_date'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Add to changelog
        self.add_to_changelog(platform, capability_path, old_value, new_value, evidence)
        
        # Update assessment metadata
        assessment['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        current_version = float(assessment['metadata']['assessment_version'])
        assessment['metadata']['assessment_version'] = f"{current_version + 0.1:.1f}"
    
    def add_to_changelog(self, platform: str, capability_path: str, old_value: Any, 
                        new_value: Any, evidence: List[str]) -> None:
        """Add entry to changelog"""
        assessment = self.capabilities[platform]
        
        change_entry = {
            'version': assessment['metadata']['assessment_version'],
            'date': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'change_type': 'capability_update',
            'impact_level': self.determine_impact_level(old_value, new_value),
            'summary': f"Updated {capability_path}: {old_value} -> {new_value}",
            'changes': {
                'improved_capabilities': [capability_path] if (old_value != new_value and self.is_improvement(old_value, new_value)) else [],
                'deprecated_capabilities': [capability_path] if (old_value and not new_value) else [],
                'new_capabilities': [capability_path] if (not old_value and new_value) else [],
                'performance_changes': []
            },
            'testing_notes': f"Evidence: {', '.join(evidence)}"
        }
        
        assessment['changelog'].insert(0, change_entry)  # Add to beginning
    
    def determine_impact_level(self, old_value: Any, new_value: Any) -> str:
        """Determine impact level of change"""
        if not old_value and new_value:
            return "major"  # New capability
        if old_value and not new_value:
            return "major"  # Removed capability
        
        # For capability levels
        levels = ["none", "basic", "intermediate", "advanced", "expert"]
        try:
            old_index = levels.index(old_value)
            new_index = levels.index(new_value)
            difference = abs(new_index - old_index)
            if difference >= 2:
                return "major"
            elif difference == 1:
                return "minor"
            else:
                return "patch"
        except (ValueError, TypeError):
            pass
        
        return "minor"  # Default for other changes
    
    def is_improvement(self, old_value: Any, new_value: Any) -> bool:
        """Check if change is improvement"""
        levels = ["none", "basic", "intermediate", "advanced", "expert"]
        try:
            old_index = levels.index(old_value)
            new_index = levels.index(new_value)
            return new_index > old_index
        except (ValueError, TypeError):
            pass
        
        # For boolean values
        if isinstance(old_value, bool) and isinstance(new_value, bool):
            return not old_value and new_value
        
        return True  # Default assumption
    
    def compare_capabilities(self, platforms: List[str], capability_path: str) -> Dict[str, Any]:
        """
        Compare capabilities across platforms
        
        Args:
            platforms: List of platform names to compare
            capability_path: Dot-notation path to capability
            
        Returns:
            Dict: Comparison results
        """
        comparison = {}
        
        for platform in platforms:
            if platform in self.capabilities:
                path_array = capability_path.split('.')
                current = self.capabilities[platform]
                
                for segment in path_array:
                    if isinstance(current, dict) and segment in current:
                        current = current[segment]
                    else:
                        current = "not_available"
                        break
                
                comparison[platform] = current
            else:
                comparison[platform] = "no_assessment"
        
        return comparison
    
    def generate_comparison_report(self, platforms: List[str]) -> Dict[str, Any]:
        """
        Generate comparison report using comparison_framework schema
        
        Args:
            platforms: List of platforms to compare
            
        Returns:
            Dict: Comparison report
        """
        report = {
            'metadata': {
                'comparison_date': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'platforms_compared': platforms,
                'comparison_version': '1.0.0'
            },
            'capability_matrix': {},
            'strengths_weaknesses': {},
            'use_case_recommendations': {},
            'market_positioning': {},
            'future_outlook': {}
        }
        
        # Key capability areas to compare (updated for Universal schema)
        key_capabilities = [
            "core_capabilities.reasoning_analysis.logical_reasoning.capability_level",
            "core_capabilities.text_generation.quality_coherence.capability_level",
            "core_capabilities.code_capabilities.python.proficiency",
            "context_scale_assessment.context_window.token_limit",
            "customization_adaptation.user_personalization.writing_style_learning",
            "development_support.github_integration.direct_integration",
            "external_integrations.integration_quality.third_party_ecosystem_size"
        ]
        
        for capability in key_capabilities:
            capability_name = capability.split('.')[-1]
            report['capability_matrix'][capability_name] = self.compare_capabilities(platforms, capability)
        
        # Generate summary insights for each platform
        for platform in platforms:
            if platform in self.capabilities:
                assessment = self.capabilities[platform]
                positioning = assessment.get('competitive_positioning', {})
                
                report['strengths_weaknesses'][platform] = {
                    'unique_strengths': positioning.get('unique_strengths', []),
                    'competitive_advantages': positioning.get('competitive_advantages', []),
                    'areas_for_improvement': positioning.get('areas_for_improvement', []),
                    'last_updated': assessment['metadata']['assessment_date']
                }
        
        return report
    
    def add_testing_evidence(self, platform: str, capability_path: str, 
                           evidence: List[str], testing_notes: str = "") -> None:
        """
        Add testing evidence to capability
        
        Args:
            platform: Platform name
            capability_path: Dot-notation path to capability
            evidence: List of evidence items
            testing_notes: Additional testing notes
        """
        if platform not in self.capabilities:
            raise ValueError(f"No assessment initialized for platform: {platform}")
        
        path_array = capability_path.split('.')
        current = self.capabilities[platform]
        
        for segment in path_array:
            if segment not in current:
                current[segment] = {}
            current = current[segment]
        
        # Add evidence and testing information
        if 'evidence' not in current:
            current['evidence'] = []
        if 'testing_examples' not in current:
            current['testing_examples'] = []
        
        current['evidence'].extend(evidence)
        current['testing_date'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        if testing_notes:
            current['testing_examples'].append({
                'date': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                '