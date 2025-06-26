def main():
    parser = argparse.ArgumentParser(
        description='Advanced filtering for ChatGPT JSON exports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Filter Types and Examples:

INDEX FILTERING:
  --keep-msgs "1-10,20,30-40,50-"    Keep messages 1-10, 20, 30-40, and 50 to end
  --remove-msgs "5,10-15,25-"        Remove messages 5, 10-15, and 25 to end
  
ROLE FILTERING:
  --roles "user,prompt"               Keep only user/prompt messages
  --roles "assistant,response"        Keep only AI responses
  
KEYWORD FILTERING:
  --include-kw "python,code"          Keep only messages containing "python" OR "code"
  --exclude-kw "error,bug"            Remove messages containing "error" OR "bug"
  --case-sensitive                    Make keyword matching case-sensitive
  
LENGTH FILTERING:
  --min-length 100                    Keep messages with at least 100 characters
  --max-length 1000                   Keep messages with at most 1000 characters
  --min-words 10                      Keep messages with at least 10 words
  --max-words 200                     Keep messages with at most 200 words

COMBINATION EXAMPLES:
  # Extract long user messages about Python
  python filter_chat.py input.json --roles "user" --include-kw "python" --min-words 20
  
  # Remove short messages and system responses
  python filter_chat.py input.json --remove-msgs "1-5" --exclude-kw "system" --min-length 50
  
  # Keep specific conversation section
  python filter_chat.py input.json --keep-msgs "10-50" --text -o section.txt
        """
    )
    
    parser.add_argument('input_file', help='Input JSON file path')
    parser.add_argument('-o', '--output', help='Output file path (auto-generated if not specified)')
    
    # Index filtering (mutually exclusive)
    index_group = parser.add_mutually_exclusive_group()
    index_group.add_argument('--keep-msgs', metavar='RANGES', 
                           help='Keep specific message indices (e.g., "1-10,20,30-40,50-")')
    index_group.add_argument('--remove-msgs', metavar='RANGES',
                           help='Remove specific message indices (e.g., "5,10-15,25-")')
    
    # Role filtering
    parser.add_argument('--roles', metavar='ROLES',
                       help='Comma-separated list of roles to keep (e.g., "user,assistant")')
    
    # Keyword filtering
    parser.add_argument('--include-kw', metavar='KEYWORDS',
                       help='Keep only messages containing these keywords (comma-separated)')
    parser.add_argument('--exclude-kw', metavar='KEYWORDS',
                       help='Remove messages containing these keywords (comma-separated)')
    parser.add_argument('--case-sensitive', action='store_true',
                       help='Make keyword matching case-sensitive')
    
    # Length filtering
    parser.add_argument('--min-length', type=int, metavar='N',
                       help='Minimum character length for messages')
    parser.add_argument('--max-length', type=int, metavar='N',
                       help='Maximum character length for messages')
    parser.add_argument('--min-words', type=int, metavar='N',
                       help='Minimum word count for messages')
    parser.add_argument('--max-words', type=int, metavar='N',
                       help='Maximum word count for messages')
    
    # Legacy support for simple filtering
    legacy_group = parser.add_mutually_exclusive_group()
    legacy_group.add_argument('--prompts', action='store_true', 
                            help='Extract only user prompts (legacy: use --roles "user,prompt")')
    legacy_group.add_argument('--responses', action='store_true',
                            help='Extract only AI responses (legacy: use --roles "assistant,response")')
    
    # Output format
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument('--json', action='store_true', default=True, help='Output as JSON (default)')
    format_group.add_argument('--text', action='store_true', help='Output as plain text')
    format_group.add_argument('--markdown', action='store_true', help='Output as Markdown')
    
    # Options
    parser.add_argument('--simple', action='store_true', help='Use simple JSON structure (no metadata preservation)')
    parser.add_argument('--no-roles', action='store_true', help='Exclude role labels in text output')
    parser.add_argument('--stats', action='store_true', help='Show statistics only (no file output)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be filtered without creating output')
    
    args = parser.parse_args()
    
    # Build filter configuration
    filter_config = {}
    
    # Handle legacy arguments
    if args.prompts:
        filter_config['roles'] = ['user', 'prompt']
    elif args.responses:
        filter_config['roles'] = ['assistant', 'response']
    
    # Index filtering
    if args.keep_msgs:
        filter_config['keep_indices'] = parse_range_spec(args.keep_msgs)
    elif args.remove_msgs:
        filter_config['remove_indices'] = parse_range_spec(args.remove_msgs)
    
    # Role filtering
    if args.roles:
        filter_config['roles'] = [role.strip() for role in args.roles.split(',')]
    
    # Keyword filtering
    if args.include_kw:
        filter_config['include_keywords'] = parse_keyword_spec(args.include_kw, args.case_sensitive)
        filter_config['case_sensitive'] = args.case_sensitive
    
    if args.exclude_kw:
        filter_config['exclude_keywords'] = parse_keyword_spec(args.exclude_kw, args.case_sensitive)
        filter_config['case_sensitive'] = args.case_sensitive
    
    # Length filtering
    if args.min_length:
        filter_config['min_length'] = args.min_length
    if args.max_length:
        filter_config['max_length'] = args.max_length
    if args.min_words:
        filter_config['min_words'] = args.min_words
    if args.max_words:
        filter_config['max_words'] = args.max_words
    
    # Check if any filters were specified
    if not filter_config and not args.stats:
        parser.error("No filters specified. Use --help to see available options.")
    
    try:
        # Read file and apply filters for stats/dry-run
        with open(args.input_file, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        
        messages = chat_data.get('messages', [])
        filtered_messages, filter_stats = filter_messages_advanced(messages, filter_config)
        
        # Show statistics or dry run results
        if args.stats or args.dry_run:
            print(f"📊 Filter Results for {args.input_file}:")
            print(f"   Original messages: {filter_stats['original_count']}")
            print(f"   Filtered messages: {filter_stats['filtered_count']}")
            print(f"   Retention rate: {filter_stats['filtered_count']/filter_stats['original_count']*100:.1f}%")
            
            if filter_config:
                print(f"\n🔍 Filters applied:")
                for key, value in filter_config.items():
                    if key == 'case_sensitive':
                        continue
                    print(f"   {key.replace('_', ' ').title()}: {value}")
            
            if args.dry_run:
                print(f"\n💡 Would create output with {filter_stats['filtered_count']} messages")
                if filtered_messages:
                    print(f"   Sample kept indices: {[m.get('_original_index') for m in filtered_messages[:5]]}")
            
            return
        
        # Generate output filename if not provided
        if not args.output:
            input_path = Path(args.input_file)
            suffix = '.json'
            if args.text:
                suffix = '.txt'
            elif args.markdown:
                suffix = '.md'
            
            # Create descriptive filename
            filter_parts = []
            if filter_config.get('roles'):
                filter_parts.append('roles')
            if filter_config.get('keep_indices') or filter_config.get('remove_indices'):
                filter_parts.append('indices')
            if filter_config.get('include_keywords') or filter_config.get('exclude_keywords'):
                filter_parts.append('keywords')
            if any(k in filter_config for k in ['min_length', 'max_length', 'min_words', 'max_words']):
                filter_parts.append('length')
            
            filter_desc = '_'.join(filter_parts) if filter_parts else 'filtered'
            args.output = input_path.with_name(f"{input_path.stem}_{filter_desc}{suffix}")
        
        # Process based on output format
        if args.text:
            count = create_text_export(args.input_file, args.output, filter_config, not args.no_roles)
            print(f"✅ Exported {count} filtered messages to text file: {args.output}")
        
        elif args.markdown:
            count = create_markdown_export(args.input_file, args.output, filter_config)
            print(f"✅ Exported {count} filtered messages to markdown file: {args.output}")
        
        else:  # JSON output
            filter_stats = create_filtered_json(
                args.input_file, args.output, filter_config, not args.simple
            )
            print(f"✅ Filtered {filter_stats['filtered_count']} messages from {filter_stats['original_count']} total")
            print(f"📁 Output file: {args.output}")
        
        # Show file size
        output_size = Path(args.output).stat().st_size
        print(f"📊 Output size: {output_size:,} bytes")
        
    except FileNotFoundError:
        print(f"❌ Error: Input file '{args.input_file}' not found")
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON file - {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()#!/usr/bin/env python3
"""
JSON Chat Filter
Advanced filtering for ChatGPT JSON exports with multiple filter types
"""

import json
import argparse
import re
from pathlib import Path
from datetime import datetime

"""
Parse range specification like "1-10,20,30-40,50-"

Args:
    range_spec: String with comma-separated ranges
    
Returns:
    Set of integers representing all included indices
"""
def parse_range_spec(range_spec):
    if not range_spec:
        return set()
    
    indices = set()
    parts = [part.strip() for part in range_spec.split(',')]
    
    for part in parts:
        if '-' in part:
            # Handle range like "1-10" or "50-" (open-ended)
            if part.endswith('-'):
                # Open-ended range like "50-"
                start = int(part[:-1])
                # We'll handle open-ended ranges in the filter function
                indices.add(('range_open', start))
            else:
                # Closed range like "1-10"
                start, end = map(int, part.split('-'))
                indices.update(range(start, end + 1))
        else:
            # Single number
            indices.add(int(part))
    
    return indices

"""
Expand open-ended ranges based on actual message count

Args:
    indices_set: Set containing indices and open range tuples
    max_index: Maximum message index available
    
Returns:
    Set of actual integer indices
"""
def expand_open_ranges(indices_set, max_index):
    expanded = set()
    
    for item in indices_set:
        if isinstance(item, tuple) and item[0] == 'range_open':
            # Expand open range like "50-" to "50" through max_index
            start = item[1]
            expanded.update(range(start, max_index + 1))
        else:
            expanded.add(item)
    
    return expanded

"""
Parse keyword specification

Args:
    keyword_spec: Comma-separated keywords
    case_sensitive: Whether to match case-sensitively
    
Returns:
    List of keywords
"""
def parse_keyword_spec(keyword_spec, case_sensitive=False):
    if not keyword_spec:
        return []
    
    keywords = [kw.strip() for kw in keyword_spec.split(',')]
    if not case_sensitive:
        keywords = [kw.lower() for kw in keywords]
    
    return keywords

"""
Check if message contains any of the keywords

Args:
    message: Message object
    keywords: List of keywords to search for
    case_sensitive: Whether to match case-sensitively
    
Returns:
    Boolean indicating if any keyword was found
"""
def message_contains_keywords(message, keywords, case_sensitive=False):
    if not keywords:
        return True
    
    content = message.get('say') or message.get('content', '')
    if not case_sensitive:
        content = content.lower()
    
    return any(keyword in content for keyword in keywords)

"""
Advanced message filtering with multiple criteria

Args:
    messages: List of message objects
    filter_config: Dictionary with filter configuration
    
Returns:
    Tuple of (filtered_messages, filter_stats)
"""
def filter_messages_advanced(messages, filter_config):
    filtered = []
    stats = {
        'original_count': len(messages),
        'filtered_count': 0,
        'filters_applied': []
    }
    
    for i, message in enumerate(messages):
        message_index = i + 1  # 1-based indexing for user convenience
        include_message = True
        exclusion_reasons = []
        
        # Role filtering
        if filter_config.get('roles'):
            role = message.get('role', '').lower()
            target_roles = [r.lower() for r in filter_config['roles']]
            if role not in target_roles:
                include_message = False
                exclusion_reasons.append(f"role '{role}' not in {target_roles}")
        
        # Index filtering - keep specific indices
        if filter_config.get('keep_indices'):
            keep_set = expand_open_ranges(filter_config['keep_indices'], len(messages))
            if message_index not in keep_set:
                include_message = False
                exclusion_reasons.append(f"index {message_index} not in keep list")
        
        # Index filtering - remove specific indices
        if filter_config.get('remove_indices'):
            remove_set = expand_open_ranges(filter_config['remove_indices'], len(messages))
            if message_index in remove_set:
                include_message = False
                exclusion_reasons.append(f"index {message_index} in remove list")
        
        # Keyword filtering - include messages with keywords
        if filter_config.get('include_keywords'):
            if not message_contains_keywords(
                message, 
                filter_config['include_keywords'], 
                filter_config.get('case_sensitive', False)
            ):
                include_message = False
                exclusion_reasons.append("no required keywords found")
        
        # Keyword filtering - exclude messages with keywords
        if filter_config.get('exclude_keywords'):
            if message_contains_keywords(
                message, 
                filter_config['exclude_keywords'], 
                filter_config.get('case_sensitive', False)
            ):
                include_message = False
                exclusion_reasons.append("contains excluded keywords")
        
        # Length filtering
        content = message.get('say') or message.get('content', '')
        content_length = len(content)
        
        if filter_config.get('min_length') and content_length < filter_config['min_length']:
            include_message = False
            exclusion_reasons.append(f"length {content_length} < {filter_config['min_length']}")
        
        if filter_config.get('max_length') and content_length > filter_config['max_length']:
            include_message = False
            exclusion_reasons.append(f"length {content_length} > {filter_config['max_length']}")
        
        # Word count filtering
        word_count = len(content.split())
        
        if filter_config.get('min_words') and word_count < filter_config['min_words']:
            include_message = False
            exclusion_reasons.append(f"words {word_count} < {filter_config['min_words']}")
        
        if filter_config.get('max_words') and word_count > filter_config['max_words']:
            include_message = False
            exclusion_reasons.append(f"words {word_count} > {filter_config['max_words']}")
        
        if include_message:
            # Add original index to message for reference
            filtered_message = message.copy()
            filtered_message['_original_index'] = message_index
            filtered.append(filtered_message)
    
    stats['filtered_count'] = len(filtered)
    stats['filters_applied'] = list(filter_config.keys())
    
    return filtered, stats

"""
Create a filtered JSON file based on advanced filter configuration

Args:
    input_file: Path to input JSON file
    output_file: Path to output JSON file
    filter_config: Dictionary with filter configuration
    preserve_structure: Whether to keep original JSON structure
"""
def create_filtered_json(input_file, output_file, filter_config, preserve_structure=True):
    
    # Read input file
    with open(input_file, 'r', encoding='utf-8') as f:
        chat_data = json.load(f)
    
    # Get messages
    messages = chat_data.get('messages', [])
    
    # Apply advanced filtering
    filtered_messages, filter_stats = filter_messages_advanced(messages, filter_config)
    
    if preserve_structure:
        # Keep original structure, just replace messages
        filtered_data = chat_data.copy()
        filtered_data['messages'] = filtered_messages
        
        # Update title to reflect filtering
        original_title = filtered_data.get('title', 'Chat Export')
        filter_description = describe_filters(filter_config)
        filtered_data['title'] = f"{original_title} - {filter_description}"
        
        # Add filter metadata
        if 'metadata' not in filtered_data:
            filtered_data['metadata'] = {}
        
        filtered_data['metadata']['filter_applied'] = {
            'config': filter_config,
            'stats': filter_stats,
            'filtered_date': datetime.now().isoformat()
        }
    else:
        # Simple structure with just the filtered messages
        filtered_data = {
            'filter_config': filter_config,
            'filter_stats': filter_stats,
            'filtered_date': datetime.now().isoformat(),
            'messages': filtered_messages
        }
    
    # Write output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)
    
    return filter_stats

"""Generate human-readable description of applied filters"""
def describe_filters(filter_config):
    descriptions = []
    
    if filter_config.get('roles'):
        roles_str = ', '.join(filter_config['roles'])
        descriptions.append(f"Roles: {roles_str}")
    
    if filter_config.get('keep_indices'):
        descriptions.append("Specific indices kept")
    
    if filter_config.get('remove_indices'):
        descriptions.append("Specific indices removed")
    
    if filter_config.get('include_keywords'):
        descriptions.append("Keyword filtered")
    
    if filter_config.get('exclude_keywords'):
        descriptions.append("Keywords excluded")
    
    if filter_config.get('min_length') or filter_config.get('max_length'):
        descriptions.append("Length filtered")
    
    if filter_config.get('min_words') or filter_config.get('max_words'):
        descriptions.append("Word count filtered")
    
    return '; '.join(descriptions) if descriptions else "Filtered"

"""
Create a plain text export of filtered messages

Args:
    input_file: Path to input JSON file
    output_file: Path to output text file
    filter_config: Dictionary with filter configuration
    include_roles: Whether to include role labels
"""
def create_text_export(input_file, output_file, filter_config, include_roles=True):
    
    # Read input file
    with open(input_file, 'r', encoding='utf-8') as f:
        chat_data = json.load(f)
    
    # Get and filter messages
    messages = chat_data.get('messages', [])
    filtered_messages, filter_stats = filter_messages_advanced(messages, filter_config)
    
    # Create text content
    lines = []
    
    # Add header
    title = chat_data.get('title', 'Chat Export')
    filter_description = describe_filters(filter_config)
    lines.append(f"{title} - {filter_description}")
    lines.append("=" * len(lines[0]))
    lines.append(f"Extracted {filter_stats['filtered_count']} messages from {filter_stats['original_count']} total")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Add messages
    for i, message in enumerate(filtered_messages, 1):
        role = message.get('role', 'unknown')
        content = message.get('say') or message.get('content', '')
        original_index = message.get('_original_index', 'unknown')
        
        if include_roles:
            lines.append(f"--- Message {i} (Original #{original_index}, {role.title()}) ---")
        else:
            lines.append(f"--- Message {i} (Original #{original_index}) ---")
        
        lines.append(content.strip())
        lines.append("")  # Empty line between messages
    
    # Write text file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    return filter_stats['filtered_count']

"""
Create a Markdown export of filtered messages

Args:
    input_file: Path to input JSON file
    output_file: Path to output markdown file
    filter_config: Dictionary with filter configuration
"""
def create_markdown_export(input_file, output_file, filter_config):
    
    # Read input file
    with open(input_file, 'r', encoding='utf-8') as f:
        chat_data = json.load(f)
    
    # Get and filter messages
    messages = chat_data.get('messages', [])
    filtered_messages, filter_stats = filter_messages_advanced(messages, filter_config)
    
    # Create markdown content
    lines = []
    
    # Add header
    title = chat_data.get('title', 'Chat Export')
    filter_description = describe_filters(filter_config)
    lines.append(f"# {title} - {filter_description}")
    lines.append("")
    lines.append(f"**Extracted:** {filter_stats['filtered_count']} messages from {filter_stats['original_count']} total")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Add filter details
    if filter_config:
        lines.append("## Filter Configuration")
        for key, value in filter_config.items():
            if key == 'case_sensitive':
                continue
            lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        lines.append("")
    
    # Add table of contents if many messages
    if len(filtered_messages) > 5:
        lines.append("## Table of Contents")
        for i, message in enumerate(filtered_messages, 1):
            content_preview = (message.get('say') or message.get('content', ''))[:50]
            content_preview = content_preview.replace('\n', ' ').strip()
            if len(content_preview) >= 50:
                content_preview += "..."
            original_index = message.get('_original_index', 'unknown')
            lines.append(f"{i}. [Message {i} (#{original_index}): {content_preview}](#message-{i})")
        lines.append("")
    
    # Add messages
    for i, message in enumerate(filtered_messages, 1):
        role = message.get('role', 'unknown')
        content = message.get('say') or message.get('content', '')
        original_index = message.get('_original_index', 'unknown')
        
        lines.append(f"## Message {i}")
        lines.append(f"**Original Index:** #{original_index}")
        lines.append(f"**Role:** {role.title()}")
        lines.append("")
        lines.append(content.strip())
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # Write markdown file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    return filter_stats['filtered_count']

def main():
    parser = argparse.ArgumentParser(
        description='Filter ChatGPT JSON exports to extract prompts or responses',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract only user prompts to JSON
  python filter_chat.py input.json --prompts -o prompts_only.json
  
  # Extract only AI responses to text file
  python filter_chat.py input.json --responses --text -o responses.txt
  
  # Extract prompts to markdown
  python filter_chat.py input.json --prompts --markdown -o prompts.md
  
  # Simple structure (no metadata preservation)
  python filter_chat.py input.json --responses --simple
        """
    )
    
    parser.add_argument('input_file', help='Input JSON file path')
    parser.add_argument('-o', '--output', help='Output file path (auto-generated if not specified)')
    
    # Filter type (mutually exclusive)
    filter_group = parser.add_mutually_exclusive_group(required=True)
    filter_group.add_argument('--prompts', action='store_true', help='Extract only user prompts')
    filter_group.add_argument('--responses', action='store_true', help='Extract only AI responses')
    
    # Output format
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument('--json', action='store_true', default=True, help='Output as JSON (default)')
    format_group.add_argument('--text', action='store_true', help='Output as plain text')
    format_group.add_argument('--markdown', action='store_true', help='Output as Markdown')
    
    # Options
    parser.add_argument('--simple', action='store_true', help='Use simple JSON structure (no metadata preservation)')
    parser.add_argument('--no-roles', action='store_true', help='Exclude role labels in text output')
    parser.add_argument('--stats', action='store_true', help='Show statistics only (no file output)')
    
    args = parser.parse_args()
    
    # Determine filter type
    filter_type = 'prompts' if args.prompts else 'responses'
    
    # Show stats only
    if args.stats:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        
        messages = chat_data.get('messages', [])
        filtered_messages = filter_messages(messages, filter_type)
        
        print(f"📊 Statistics for {args.input_file}:")
        print(f"   Total messages: {len(messages)}")
        print(f"   {filter_type.title()}: {len(filtered_messages)}")
        print(f"   Percentage: {len(filtered_messages)/len(messages)*100:.1f}%")
        return
    
    # Generate output filename if not provided
    if not args.output:
        input_path = Path(args.input_file)
        suffix = '.json'
        if args.text:
            suffix = '.txt'
        elif args.markdown:
            suffix = '.md'
        
        args.output = input_path.with_name(f"{input_path.stem}_{filter_type}{suffix}")
    
    try:
        # Process based on output format
        if args.text:
            count = create_text_export(args.input_file, args.output, filter_type, not args.no_roles)
            print(f"✅ Extracted {count} {filter_type} to text file: {args.output}")
        
        elif args.markdown:
            count = create_markdown_export(args.input_file, args.output, filter_type)
            print(f"✅ Extracted {count} {filter_type} to markdown file: {args.output}")
        
        else:  # JSON output
            original_count, filtered_count = create_filtered_json(
                args.input_file, args.output, filter_type, not args.simple
            )
            print(f"✅ Extracted {filtered_count} {filter_type} from {original_count} total messages")
            print(f"📁 Output file: {args.output}")
        
        # Show file size
        output_size = Path(args.output).stat().st_size
        print(f"📊 Output size: {output_size:,} bytes")
        
    except FileNotFoundError:
        print(f"❌ Error: Input file '{args.input_file}' not found")
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON file - {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
