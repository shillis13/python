#!/usr/bin/env python3
"""
Python AI Capabilities Schema Integration Utilities
Equivalent to schema_integration_utilities.js, leveraging existing Python YAML utilities
"""

import copy
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import argparse
import sys

# Import existing utilities from your yaml utilities
from helpers import get_utc_timestamp, load_yaml, save_yaml, archive_and_update_metadata


class AICapabilitiesManager:
    """Python equivalent of JavaScript AICapabilitiesManager class using existing utilities"""
    
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
        assessment['metadata']['assessment_date'] = self.get_iso_timestamp()
        assessment['metadata']['assessor_info']['evaluator_name'] = assessor_name
        
        # Calculate next assessment date (3 months from now)
        next_assessment = datetime.now(timezone.utc) + timedelta(days=90)
        assessment['metadata']['next_assessment_due'] = next_assessment.isoformat().replace('+00:00', 'Z')
        
        self.capabilities[platform_lower] = assessment
        return assessment
    
    def get_default_version(self, platform: str) -> str:
        """Get default version for platform"""
        defaults = {
            'claude': 'claude-3.5-sonnet',
            'chatgpt': 'gpt-4o',
            'gemini': 'gemini-1.5-pro',
            'grok': 'grok-2'
        }
        return defaults.get(platform, 'unknown')
    
    def get_iso_timestamp(self) -> str:
        """Get ISO timestamp in Z format (consistent with existing utilities)"""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    def update_capability(self, platform: str, capability_path: str, new_value: Any,
                         evidence: List[str] = None, confidence: str = "medium") -> None:
        """
        Update a capability with new findings
        
        Args:
            platform: Platform name
            capability_path: Dot-notation path to capability
            new_value: New value to set
            evidence: List of evidence supporting the update
            confidence: Confidence level (low, medium, high)
        """
        if evidence is None:
            evidence = []
            
        if platform not in self.capabilities:
            raise ValueError(f"No assessment initialized for platform: {platform}")
        
        # Archive the assessment before making changes (following helpers.py pattern)
        self.capabilities[platform] = archive_and_update_metadata(
            self.capabilities[platform], 'core_capabilities'
        )
        
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
                current['testing_date'] = self.get_iso_timestamp()
        
        # Add to changelog
        self.add_to_changelog(platform, capability_path, old_value, new_value, evidence)
        
        # Update assessment metadata (following helpers.py metadata pattern)
        if 'metadata' in assessment:
            assessment['metadata']['last_updated'] = self.get_iso_timestamp()
            current_version = assessment['metadata'].get('version', 0)
            assessment['metadata']['version'] = current_version + 1
    
    def add_to_changelog(self, platform: str, capability_path: str, old_value: Any, 
                        new_value: Any, evidence: List[str]) -> None:
        """Add entry to changelog"""
        assessment = self.capabilities[platform]
        
        change_entry = {
            'version': assessment['metadata']['assessment_version'],
            'date': self.get_iso_timestamp(),
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
                'comparison_date': self.get_iso_timestamp(),
                'platforms_compared': platforms,
                'comparison_version': '1.0.0'
            },
            'capability_matrix': {},
            'strengths_weaknesses': {},
            'use_case_recommendations': {},
            'market_positioning': {},
            '