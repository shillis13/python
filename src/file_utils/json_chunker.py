import json
import os
import argparse
import sys

"""
Chunk a chat JSON file at message boundaries with configurable size and overlap.

Args:
    input_file: Path to the input JSON file
    output_base: Base name for output files (default: input filename without extension)
    max_chars: Maximum characters per chunk (default 30K, adjust as needed)
    overlap_messages: Number of messages to overlap between chunks for continuity
"""
def chunk_chat_json(input_file, output_base=None, max_chars=30000, overlap_messages=2):
    
    # Read the original JSON
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Assume the messages are in a list - adjust key name if different
    # Common structures: data['messages'], data['conversation'], or just data if it's a list
    if isinstance(data, list):
        messages = data
        wrapper_key = None
    elif 'messages' in data:
        messages = data['messages']
        wrapper_key = 'messages'
    elif 'conversation' in data:
        messages = data['conversation'] 
        wrapper_key = 'conversation'
    else:
        # Try to find the largest list in the data
        largest_list = max((k for k, v in data.items() if isinstance(v, list)), 
                          key=lambda k: len(data[k]), default=None)
        if largest_list:
            messages = data[largest_list]
            wrapper_key = largest_list
        else:
            raise ValueError("Could not find messages list in JSON structure")
    
    print(f"Found {len(messages)} messages in '{wrapper_key or 'root'}' key")
    
    chunks = []
    current_chunk_start = 0
    
    while current_chunk_start < len(messages):
        # Start building chunk
        current_chunk_end = current_chunk_start
        current_size = 0
        
        # Keep adding messages until we exceed the size limit
        while current_chunk_end < len(messages):
            # Create temporary chunk to test size
            chunk_messages = messages[current_chunk_start:current_chunk_end + 1]
            
            # Create the chunk structure
            if wrapper_key:
                temp_chunk = {**data}  # Copy other top-level keys
                temp_chunk[wrapper_key] = chunk_messages
            else:
                temp_chunk = chunk_messages
            
            # Check size
            temp_json = json.dumps(temp_chunk, ensure_ascii=False)
            
            if len(temp_json) > max_chars and current_chunk_end > current_chunk_start:
                # This message would make it too big, so stop at previous message
                break
            
            current_size = len(temp_json)
            current_chunk_end += 1
        
        # Make sure we got at least one message
        if current_chunk_end == current_chunk_start:
            current_chunk_end = current_chunk_start + 1
            print(f"Warning: Single message at index {current_chunk_start} exceeds size limit")
        
        # Create the actual chunk
        chunk_messages = messages[current_chunk_start:current_chunk_end]
        
        if wrapper_key:
            chunk_data = {**data}  # Copy other top-level keys
            chunk_data[wrapper_key] = chunk_messages
        else:
            chunk_data = chunk_messages
        
        chunks.append({
            'data': chunk_data,
            'start_idx': current_chunk_start,
            'end_idx': current_chunk_end - 1,
            'message_count': len(chunk_messages),
            'size': current_size
        })
        
        # Move to next chunk with overlap
        current_chunk_start = max(current_chunk_start + 1, 
                                current_chunk_end - overlap_messages)
    
    # Write chunk files
    if output_base is None:
        base_name = os.path.splitext(input_file)[0]
    else:
        base_name = output_base
    
    for i, chunk in enumerate(chunks, 1):
        output_file = f"{base_name}_chunk_{i}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunk['data'], f, ensure_ascii=False, indent=2)
        
        print(f"Chunk {i}: {output_file}")
        print(f"  Messages: {chunk['start_idx']}-{chunk['end_idx']} ({chunk['message_count']} total)")
        print(f"  Size: {chunk['size']:,} characters")
        print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Chunk a chat JSON file at message boundaries with configurable size and overlap."
    )
    
    parser.add_argument(
        "input_file",
        help="Path to the input JSON file"
    )
    
    parser.add_argument(
        "-o", "--output",
        dest="output_base",
        help="Base name for output files (default: input filename without extension)"
    )
    
    parser.add_argument(
        "-s", "--size",
        dest="max_size",
        type=int,
        default=30000,
        help="Maximum characters per chunk (default: 30000)"
    )
    
    parser.add_argument(
        "--overlap",
        type=int,
        default=2,
        help="Number of messages to overlap between chunks for continuity (default: 2)"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    try:
        chunk_chat_json(
            input_file=args.input_file,
            output_base=args.output_base,
            max_chars=args.max_size,
            overlap_messages=args.overlap
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
