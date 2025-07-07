#========================================
#region detect_message_gaps
"""
Detect gaps in message sequences across all loaded chat histories.

Analyzes message registry to find missing message numbers and creates
gap descriptors for merging process. Identifies patterns in skipped
messages to determine likely reasons for gaps.

Args:
    message_registry (dict): Registry of all messages by number and session

Returns:
    dict: Gap information with ranges, reasons, and metadata
"""
#========================================
#endregion
def detect_message_gaps(message_registry):
    gap_info = {
        'gaps': [],
        'total_gaps': 0,
        'total_missing_messages': 0,
        'continuity_assessment': 'unknown'
    }
    
    # Get all message numbers present
    all_message_numbers = set()
    max_message_number = 0
    
    for session_id, messages in message_registry.items():
        for msg_num in messages.keys():
            all_message_numbers.add(msg_num)
            max_message_number = max(max_message_number, msg_num)
    
    # Find gaps in sequence
    expected_numbers = set(range(1, max_message_number + 1))
    missing_numbers = expected_numbers - all_message_numbers
    
    if not missing_numbers:
        gap_info['continuity_assessment'] = 'complete'
        return gap_info
    
    # Group consecutive missing numbers into gap ranges
    gap_ranges = group_consecutive_numbers(sorted(missing_numbers))
    
    # Create gap descriptors
    for gap_range in gap_ranges:
        start_num = gap_range[0]
        end_num = gap_range[-1]
        gap_size = len(gap_range)
        
        gap_descriptor = create_gap_descriptor(start_num, end_num, gap_size, message_registry)
        gap_info['gaps'].append(gap_descriptor)
    
    gap_info['total_gaps'] = len(gap_ranges)
    gap_info['total_missing_messages'] = len(missing_numbers)
    gap_info['continuity_assessment'] = determine_continuity_level(gap_info)
    
    return gap_info