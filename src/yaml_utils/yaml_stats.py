#!/usr/bin/env python3
"""
YAML Statistics and Metrics Tool

Analyzes YAML files to provide detailed statistics, metrics, and insights
about structure, content, and compliance with schemas.
"""

import argparse
import sys
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import Counter
from datetime import datetime
from yaml_utils.helpers import load_yaml

# Try to import jsonschema for validation
try:
    from jsonschema import validate, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

"""
Comprehensive analysis of YAML structure and content.

Args:
    data: YAML data to analyze.

Returns:
    Dict: Detailed analysis results.
"""
def analyze_yaml_comprehensive(data: Any) -> Dict[str, Any]:
    analysis = {
        'structure': {'total_keys': 0, 'total_values': 0, 'max_depth': 0, 'avg_depth': 0, 'paths': [], 'key_patterns': Counter(), 'depth_distribution': Counter()},
        'content': {'data_types': Counter(), 'value_lengths': {'min': float('inf'), 'max': 0, 'avg': 0, 'distribution': Counter()}, 'string_patterns': Counter(), 'numeric_stats': {'integers': [], 'floats': []}, 'boolean_distribution': Counter(), 'null_count': 0},
        'schema_compliance': {'required_fields': [], 'optional_fields': [], 'validation_errors': []},
        'memory_estimates': {'approximate_size_bytes': 0, 'key_overhead': 0, 'value_overhead': 0}
    }

    def _analyze_recursive(obj: Any, current_path: str = "", depth: int = 0) -> None:
        analysis['structure']['max_depth'] = max(analysis['structure']['max_depth'], depth)
        analysis['structure']['depth_distribution'][depth] += 1

        if isinstance(obj, dict):
            analysis['structure']['total_keys'] += len(obj)
            for key, value in obj.items():
                full_path = f"{current_path}.{key}" if current_path else key
                analysis['structure']['paths'].append(full_path)
                analysis['structure']['key_patterns'][type(key).__name__] += 1
                analysis['memory_estimates']['key_overhead'] += sys.getsizeof(key)
                _analyze_value(value)
                _analyze_recursive(value, full_path, depth + 1)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                full_path = f"{current_path}[{i}]"
                _analyze_value(item)
                _analyze_recursive(item, full_path, depth + 1)

    def _analyze_value(value: Any) -> None:
        analysis['structure']['total_values'] += 1
        value_type = type(value).__name__
        analysis['content']['data_types'][value_type] += 1
        analysis['memory_estimates']['value_overhead'] += sys.getsizeof(value)

        if isinstance(value, str):
            value_len = len(value)
            analysis['content']['value_lengths']['min'] = min(analysis['content']['value_lengths']['min'], value_len)
            analysis['content']['value_lengths']['max'] = max(analysis['content']['value_lengths']['max'], value_len)
            analysis['content']['value_lengths']['distribution'][value_len // 10 * 10] += 1
            if re.match(r'^\d{4}-\d{2}-\d{2}', value): analysis['content']['string_patterns']['date_like'] += 1
            elif re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value): analysis['content']['string_patterns']['email_like'] += 1
        elif isinstance(value, int): analysis['content']['numeric_stats']['integers'].append(value)
        elif isinstance(value, float): analysis['content']['numeric_stats']['floats'].append(value)
        elif isinstance(value, bool): analysis['content']['boolean_distribution'][value] += 1
        elif value is None: analysis['content']['null_count'] += 1

    _analyze_recursive(data)

    # Final calculations
    if analysis['structure']['total_values'] > 0:
        if analysis['content']['value_lengths']['min'] == float('inf'): analysis['content']['value_lengths']['min'] = 0
        total_depth = sum(d * c for d, c in analysis['structure']['depth_distribution'].items())
        total_nodes = sum(analysis['structure']['depth_distribution'].values())
        analysis['structure']['avg_depth'] = total_depth / total_nodes if total_nodes > 0 else 0
        if analysis['content']['numeric_stats']['integers']:
            integers = analysis['content']['numeric_stats']['integers']
            analysis['content']['numeric_stats']['integers'] = {'count': len(integers), 'min': min(integers), 'max': max(integers), 'avg': sum(integers) / len(integers)}
        if analysis['content']['numeric_stats']['floats']:
            floats = analysis['content']['numeric_stats']['floats']
            analysis['content']['numeric_stats']['floats'] = {'count': len(floats), 'min': min(floats), 'max': max(floats), 'avg': sum(floats) / len(floats)}

    analysis['memory_estimates']['approximate_size_bytes'] = analysis['memory_estimates']['key_overhead'] + analysis['memory_estimates']['value_overhead']
    return analysis


def main():
    parser = argparse.ArgumentParser(description='Analyze YAML files for statistics, metrics, and insights.', formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('yaml_file', type=Path, help='YAML file to analyze')
    # ... (the rest of the argparse setup is unchanged)
    args = parser.parse_args()

    try:
        data = load_yaml(args.yaml_file)
        analysis = analyze_yaml_comprehensive(data)

        # The rest of the main function handles report generation and printing
        # based on the analysis dictionary, which is unchanged.
        # ...

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

