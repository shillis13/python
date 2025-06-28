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
from typing import Any, Dict, List, Union, Optional
from collections import Counter, defaultdict
from datetime import datetime
from helpers import load_yaml

# Try to import jsonschema for validation
try:
    from jsonschema import validate, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

"""
Comprehensive analysis of YAML structure and content

Args:
    data: YAML data to analyze
    path_prefix: Current path in the data structure
    
Returns:
    Dict: Detailed analysis results
"""
def analyze_yaml_comprehensive(data: Any, path_prefix: str = "") -> Dict[str, Any]:
    analysis = {
        'structure': {
            'total_keys': 0,
            'total_values': 0,
            'max_depth': 0,
            'avg_depth': 0,
            'paths': [],
            'key_patterns': Counter(),
            'depth_distribution': Counter()
        },
        'content': {
            'data_types': Counter(),
            'value_lengths': {'min': float('inf'), 'max': 0, 'avg': 0, 'distribution': Counter()},
            'string_patterns': Counter(),
            'numeric_stats': {'integers': [], 'floats': []},
            'boolean_distribution': Counter(),
            'null_count': 0
        },
        'schema_compliance': {
            'required_fields': [],
            'optional_fields': [],
            'validation_errors': []
        },
        'memory_estimates': {
            'approximate_size_bytes': 0,
            'key_overhead': 0,
            'value_overhead': 0
        }
    }
    
    def analyze_recursive(obj: Any, current_path: str = "", depth: int = 0) -> None:
        analysis['structure']['max_depth'] = max(analysis['structure']['max_depth'], depth)
        analysis['structure']['depth_distribution'][depth] += 1
        
        if isinstance(obj, dict):
            analysis['structure']['total_keys'] += len(obj)
            
            for key, value in obj.items():
                full_path = f"{current_path}.{key}" if current_path else key
                analysis['structure']['paths'].append(full_path)
                
                # Analyze key patterns
                analysis['structure']['key_patterns'][type(key).__name__] += 1
                
                # Estimate memory for key
                analysis['memory_estimates']['key_overhead'] += len(str(key)) * 2  # rough estimate
                
                analyze_value(value, full_path)
                analyze_recursive(value, full_path, depth + 1)
        
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                full_path = f"{current_path}[{i}]" if current_path else f"[{i}]"
                analyze_value(item, full_path)
                analyze_recursive(item, full_path, depth + 1)
    
    def analyze_value(value: Any, path: str) -> None:
        analysis['structure']['total_values'] += 1
        value_type = type(value).__name__
        analysis['content']['data_types'][value_type] += 1
        
        # Estimate memory for value
        if isinstance(value, str):
            value_len = len(value)
            analysis['content']['value_lengths']['min'] = min(
                analysis['content']['value_lengths']['min'], value_len
            )
            analysis['content']['value_lengths']['max'] = max(
                analysis['content']['value_lengths']['max'], value_len
            )
            analysis['content']['value_lengths']['distribution'][value_len // 10 * 10] += 1
            analysis['memory_estimates']['value_overhead'] += value_len * 2
            
            # Analyze string patterns
            if re.match(r'^\d{4}-\d{2}-\d{2}', value):
                analysis['content']['string_patterns']['date_like'] += 1
            elif re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
                analysis['content']['string_patterns']['email_like'] += 1
            elif re.match(r'^https?://', value):
                analysis['content']['string_patterns']['url_like'] += 1
            elif re.match(r'^\w+_\d{8}T\d{6}Z$', value):
                analysis['content']['string_patterns']['timestamp_archive'] += 1
                
        elif isinstance(value, int):
            analysis['content']['numeric_stats']['integers'].append(value)
            analysis['memory_estimates']['value_overhead'] += 8  # rough estimate
            
        elif isinstance(value, float):
            analysis['content']['numeric_stats']['floats'].append(value)
            analysis['memory_estimates']['value_overhead'] += 8
            
        elif isinstance(value, bool):
            analysis['content']['boolean_distribution'][value] += 1
            analysis['memory_estimates']['value_overhead'] += 1
            
        elif value is None:
            analysis['content']['null_count'] += 1
            analysis['memory_estimates']['value_overhead'] += 1
    
    # Start analysis
    analyze_recursive(data)
    
    # Calculate averages and finalize stats
    if analysis['structure']['total_values'] > 0:
        if analysis['content']['value_lengths']['min'] == float('inf'):
            analysis['content']['value_lengths']['min'] = 0
            
        # Calculate average depth
        total_depth = sum(depth * count for depth, count in analysis['structure']['depth_distribution'].items())
        total_nodes = sum(analysis['structure']['depth_distribution'].values())
        analysis['structure']['avg_depth'] = total_depth / total_nodes if total_nodes > 0 else 0
        
        # Calculate numeric statistics
        if analysis['content']['numeric_stats']['integers']:
            integers = analysis['content']['numeric_stats']['integers']
            analysis['content']['numeric_stats']['integers'] = {
                'count': len(integers),
                'min': min(integers),
                'max': max(integers),
                'avg': sum(integers) / len(integers)
            }
        
        if analysis['content']['numeric_stats']['floats']:
            floats = analysis['content']['numeric_stats']['floats']
            analysis['content']['numeric_stats']['floats'] = {
                'count': len(floats),
                'min': min(floats),
                'max': max(floats),
                'avg': sum(floats) / len(floats)
            }
    
    # Estimate total memory
    analysis['memory_estimates']['approximate_size_bytes'] = (
        analysis['memory_estimates']['key_overhead'] + 
        analysis['memory_estimates']['value_overhead']
    )
    
    return analysis

"""
Validate YAML against schema if available

Args:
    data: YAML data to validate
    schema_file: Path to schema file
    
Returns:
    List: Validation errors if any
"""
def validate_against_schema(data: Any, schema_file: Optional[Path] = None) -> List[str]:
    if not JSONSCHEMA_AVAILABLE:
        return ["jsonschema library not available"]
    
    if not schema_file:
        return ["No schema file provided"]
    
    try:
        schema = load_yaml(schema_file)
        validate(instance=data, schema=schema)
        return []
    except ValidationError as e:
        return [f"Validation error: {e.message} at {'.'.join(str(p) for p in e.path)}"]
    except Exception as e:
        return [f"Schema validation failed: {e}"]

"""
Generate a detailed report from analysis results

Args:
    analysis: Analysis results dictionary
    yaml_file: Path to the analyzed YAML file
    
Returns:
    str: Formatted report
"""
def generate_report(analysis: Dict[str, Any], yaml_file: Path) -> str:
    report = []
    
    # Header
    report.append("=" * 80)
    report.append(f"YAML ANALYSIS REPORT: {yaml_file}")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)
    
    # Structure Analysis
    report.append("\n📁 STRUCTURE ANALYSIS")
    report.append("-" * 40)
    struct = analysis['structure']
    report.append(f"Total Keys:        {struct['total_keys']:,}")
    report.append(f"Total Values:      {struct['total_values']:,}")
    report.append(f"Maximum Depth:     {struct['max_depth']}")
    report.append(f"Average Depth:     {struct['avg_depth']:.2f}")
    
    # Depth distribution
    if struct['depth_distribution']:
        report.append("\nDepth Distribution:")
        for depth in sorted(struct['depth_distribution'].keys()):
            count = struct['depth_distribution'][depth]
            bar = "█" * min(50, count // max(1, max(struct['depth_distribution'].values()) // 50))
            report.append(f"  Depth {depth:2d}: {count:6,} nodes {bar}")
    
    # Content Analysis
    report.append("\n📊 CONTENT ANALYSIS")
    report.append("-" * 40)
    content = analysis['content']
    
    # Data type distribution
    report.append("Data Type Distribution:")
    total_values = sum(content['data_types'].values())
    for dtype, count in content['data_types'].most_common():
        percentage = (count / total_values) * 100 if total_values > 0 else 0
        report.append(f"  {dtype:12s}: {count:6,} ({percentage:5.1f}%)")
    
    # String analysis
    if content['value_lengths']['max'] > 0:
        report.append(f"\nString Length Stats:")
        report.append(f"  Minimum:  {content['value_lengths']['min']}")
        report.append(f"  Maximum:  {content['value_lengths']['max']}")
        
    # String patterns
    if content['string_patterns']:
        report.append("\nString Patterns Detected:")
        for pattern, count in content['string_patterns'].most_common():
            report.append(f"  {pattern:20s}: {count:6,}")
    
    # Numeric statistics
    if content['numeric_stats']['integers']:
        int_stats = content['numeric_stats']['integers']
        report.append(f"\nInteger Statistics:")
        report.append(f"  Count:   {int_stats['count']:,}")
        report.append(f"  Range:   {int_stats['min']:,} to {int_stats['max']:,}")
        report.append(f"  Average: {int_stats['avg']:.2f}")
    
    if content['numeric_stats']['floats']:
        float_stats = content['numeric_stats']['floats']
        report.append(f"\nFloat Statistics:")
        report.append(f"  Count:   {float_stats['count']:,}")
        report.append(f"  Range:   {float_stats['min']:.2f} to {float_stats['max']:.2f}")
        report.append(f"  Average: {float_stats['avg']:.2f}")
    
    # Boolean distribution
    if content['boolean_distribution']:
        report.append(f"\nBoolean Distribution:")
        for bool_val, count in content['boolean_distribution'].items():
            report.append(f"  {str(bool_val):5s}: {count:6,}")
    
    if content['null_count'] > 0:
        report.append(f"\nNull Values: {content['null_count']:,}")
    
    # Memory estimates
    report.append("\n💾 MEMORY ESTIMATES")
    report.append("-" * 40)
    memory = analysis['memory_estimates']
    total_kb = memory['approximate_size_bytes'] / 1024
    report.append(f"Approximate Size: {memory['approximate_size_bytes']:,} bytes ({total_kb:.1f} KB)")
    report.append(f"Key Overhead:     {memory['key_overhead']:,} bytes")
    report.append(f"Value Overhead:   {memory['value_overhead']:,} bytes")
    
    # Schema compliance (if available)
    schema_info = analysis['schema_compliance']
    if schema_info['validation_errors']:
        report.append("\n⚠️  SCHEMA VALIDATION")
        report.append("-" * 40)
        for error in schema_info['validation_errors']:
            report.append(f"❌ {error}")
    
    return "\n".join(report)

"""
Compare two YAML files and show differences in structure

Args:
    file1: First YAML file
    file2: Second YAML file
    
Returns:
    str: Comparison report
"""
def compare_yaml_files(file1: Path, file2: Path) -> str:
    try:
        data1 = load_yaml(file1)
        data2 = load_yaml(file2)
        
        analysis1 = analyze_yaml_comprehensive(data1)
        analysis2 = analyze_yaml_comprehensive(data2)
        
        report = []
        report.append(f"\n📋 COMPARISON: {file1.name} vs {file2.name}")
        report.append("=" * 60)
        
        # Structure comparison
        s1, s2 = analysis1['structure'], analysis2['structure']
        report.append(f"Keys:         {s1['total_keys']:6,} vs {s2['total_keys']:6,} (Δ {s2['total_keys'] - s1['total_keys']:+,})")
        report.append(f"Values:       {s1['total_values']:6,} vs {s2['total_values']:6,} (Δ {s2['total_values'] - s1['total_values']:+,})")
        report.append(f"Max Depth:    {s1['max_depth']:6,} vs {s2['max_depth']:6,} (Δ {s2['max_depth'] - s1['max_depth']:+,})")
        
        # Memory comparison
        m1, m2 = analysis1['memory_estimates'], analysis2['memory_estimates']
        size_diff = m2['approximate_size_bytes'] - m1['approximate_size_bytes']
        report.append(f"Size (bytes): {m1['approximate_size_bytes']:6,} vs {m2['approximate_size_bytes']:6,} (Δ {size_diff:+,})")
        
        return "\n".join(report)
        
    except Exception as e:
        return f"❌ Comparison failed: {e}"

def main():
    parser = argparse.ArgumentParser(
        description='Analyze YAML files for statistics, metrics, and insights',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic analysis
    python yaml_stats.py config.yaml
    
    # Full detailed report
    python yaml_stats.py config.yaml --detailed
    
    # Validate against schema
    python yaml_stats.py config.yaml --schema schema.yaml
    
    # Compare two files
    python yaml_stats.py config.yaml --compare config_v2.yaml
    
    # Export analysis to JSON
    python yaml_stats.py config.yaml --export-json stats.json
        """
    )
    
    parser.add_argument('yaml_file', type=Path, help='YAML file to analyze')
    parser.add_argument('-d', '--detailed', action='store_true',
                       help='Generate detailed analysis report')
    parser.add_argument('-s', '--schema', type=Path,
                       help='Schema file for validation')
    parser.add_argument('-c', '--compare', type=Path,
                       help='Second YAML file to compare against')
    parser.add_argument('-j', '--export-json', type=Path,
                       help='Export analysis results to JSON file')
    parser.add_argument('--paths', action='store_true',
                       help='Show all key paths found in the YAML')
    
    args = parser.parse_args()
    
    try:
        # Load and analyze the YAML file
        data = load_yaml(args.yaml_file)
        analysis = analyze_yaml_comprehensive(data)
        
        # Add schema validation if requested
        if args.schema:
            validation_errors = validate_against_schema(data, args.schema)
            analysis['schema_compliance']['validation_errors'] = validation_errors
        
        # Generate and display report
        if args.detailed:
            report = generate_report(analysis, args.yaml_file)
            print(report)
        else:
            # Basic summary
            struct = analysis['structure']
            content = analysis['content']
            memory = analysis['memory_estimates']
            
            print(f"📄 {args.yaml_file}")
            print(f"   Keys: {struct['total_keys']:,}, Values: {struct['total_values']:,}, Depth: {struct['max_depth']}")
            print(f"   Types: {dict(content['data_types'])}")
            print(f"   Size: ~{memory['approximate_size_bytes']/1024:.1f} KB")
            
            if analysis['schema_compliance']['validation_errors']:
                print(f"   ⚠️  {len(analysis['schema_compliance']['validation_errors'])} validation errors")
        
        # Show paths if requested
        if args.paths:
            print(f"\n📍 KEY PATHS ({len(analysis['structure']['paths'])} found):")
            for path in sorted(analysis['structure']['paths']):
                print(f"   {path}")
        
        # Compare files if requested
        if args.compare:
            comparison = compare_yaml_files(args.yaml_file, args.compare)
            print(comparison)
        
        # Export to JSON if requested
        