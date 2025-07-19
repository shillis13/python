#!/usr/bin/env python3
#========================================
#region merge_chat_histories
"""
Merge multiple chat history YAML files into a single comprehensive history.

Handles message gaps, session consolidation, and maintains conversation 
continuity across multiple source files. Follows enhanced schema with
skipped message tracking for proper merger capabilities.

Args:
    source_files (List[str]): Paths to YAML chat history files to merge
    output_path (str): Path for merged output file
    merge_strategy (str): 'chronological' or 'session_based'

Returns:
    bool: True if merge successful, False otherwise
"""
#========================================
#endregion
def merge_chat_histories(source_files, output_path, merge_strategy='chronological'):
    import yaml
    from datetime import datetime
    from pathlib import Path
    
    merged_history = None
    all_sessions = []
    message_registry = {}
    
    # Load and validate all source files
    for file_path in source_files:
        file_content = load_chat_history_file(file_path)
        if not file_content:
            continue
            
        # Register messages for gap detection
        register_messages_from_file(file_content, file_path, message_registry)
        
        # Collect sessions
        collect_sessions_from_file(file_content, all_sessions)
        
        # Use first file as base metadata
        if merged_history is None:
            merged_history = initialize_merged_history(file_content)
    
    # Sort and merge sessions
    sorted_sessions = sort_sessions_by_strategy(all_sessions, merge_strategy)
    
    # Detect and mark message gaps
    gap_info = detect_message_gaps(message_registry)
    
    # Apply gap information to sessions
    apply_gap_markers_to_sessions(sorted_sessions, gap_info)
    
    # Finalize merged history
    merged_history['chat_sessions'] = sorted_sessions
    update_merged_metadata(merged_history, gap_info)
    
    # Write output
    result = write_merged_history(merged_history, output_path)
    return result
