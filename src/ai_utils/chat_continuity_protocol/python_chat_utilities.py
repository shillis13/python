#!/usr/bin/env python3
"""
Python Chat History Utilities
Equivalent to yaml_chat_utilities.js, leveraging existing Python YAML utilities
"""

import copy
import random
import string
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Import existing utilities from your yaml utilities
from helpers import get_utc_timestamp, load_yaml, save_yaml


class ChatHistoryManager:
    """Python equivalent of BackgroundChatHistory JavaScript class using existing utilities"""
    
    def __init__(self):
        self.history: Dict[str, Any] = {}
        self.auto_save_enabled = True
        self.initialize_history()
    
    def initialize_history(self) -> None:
        """Initialize a new chat history structure"""
        self.history = {
            'metadata': {
                'conversation_id': self.generate_conversation_id(),
                'created': self.get_iso_timestamp(),
                'last_updated': self.get_iso_timestamp(),
                'version': 1,
                'total_messages': 0,
                'total_exchanges': 0,
                'tags': ['chat-continuity', 'python-utilities'],
                'format_version': '1.0'
            },
            'chat_sessions': [{
                'session_id': self.generate_session_id(),
                'started': self.get_iso_timestamp(),
                'ended': None,
                'platform': 'claude',
                'continued_from': None,
                'tags': ['active-session'],
                'messages': []
            }]
        }
    
    def generate_conversation_id(self) -> str:
        """Generate unique conversation ID using existing timestamp utility"""
        timestamp = get_utc_timestamp()
        return f"conv_{timestamp}"
    
    def generate_message_id(self) -> str:
        """Generate unique message ID using existing timestamp utility"""
        timestamp = get_utc_timestamp()
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        return f"msg_{timestamp}_{suffix}"
    
    def generate_session_id(self) -> str:
        """Generate unique session ID using existing timestamp utility"""
        timestamp = get_utc_timestamp()
        return f"session_{timestamp}"
    
    def get_iso_timestamp(self) -> str:
        """Get ISO timestamp in Z format (consistent with existing utilities)"""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    def get_current_session(self) -> Dict[str, Any]:
        """Get the current active session"""
        return self.history['chat_sessions'][-1]
    
    def record_message(self, role: str, content: str, tags: List[str] = None, 
                      attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Record a message in the chat history
        
        Args:
            role: 'user', 'assistant', or 'system'
            content: Message content
            tags: Optional tags for the message
            attachments: Optional file/artifact attachments
            
        Returns:
            Dict: The created message object
        """
        if tags is None:
            tags = []
        if attachments is None:
            attachments = []
        
        # Calculate metadata
        word_count = len([w for w in content.split() if w.strip()])
        estimated_tokens = max(1, len(content) // 4)  # Rough estimate
        
        message = {
            'message_id': self.generate_message_id(),
            'message_number': self.history['metadata']['total_messages'] + 1,
            'conversation_id': self.history['metadata']['conversation_id'],
            'session_id': self.get_current_session()['session_id'],
            'timestamp': self.get_iso_timestamp(),
            'role': role,
            'content': content,
            'attachments': attachments,
            'tags': tags,
            'metadata': {
                'estimated_tokens': estimated_tokens,
                'char_count': len(content),
                'word_count': word_count
            }
        }
        
        # Add to current session
        self.get_current_session()['messages'].append(message)
        
        # Update conversation metadata
        self.history['metadata']['total_messages'] += 1
        self.history['metadata']['last_updated'] = self.get_iso_timestamp()
        self.history['metadata']['version'] += 1
        
        # Update exchange count if this completes an exchange
        if role == 'assistant':
            self.history['metadata']['total_exchanges'] += 1
        
        return message
    
    def record_claude_response(self, content: str, artifact_ids: List[str] = None, 
                             tags: List[str] = None) -> Dict[str, Any]:
        """
        Record Claude's response with artifacts
        
        Args:
            content: Response content
            artifact_ids: List of artifact IDs created
            tags: Optional tags
            
        Returns:
            Dict: The created message object
        """
        if artifact_ids is None:
            artifact_ids = []
        if tags is None:
            tags = []
        
        # Convert artifact IDs to attachment objects
        attachments = []
        for artifact_id in artifact_ids:
            attachments.append({
                'type': 'artifact',
                'artifact_id': artifact_id,
                'artifact_type': 'code',  # Could be determined from artifact
                'title': artifact_id.replace('_', ' '),
                'created_at': self.get_iso_timestamp()
            })
        
        return self.record_message('assistant', content, tags, attachments)
    
    def add_file_attachment(self, filename: str, filepath: Optional[str] = None, 
                           description: str = '', file_size: Optional[int] = None,
                           file_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a file attachment object
        
        Args:
            filename: Name of the file
            filepath: Path to the file (optional)
            description: Description of the file
            file_size: Size in bytes
            file_type: MIME type or extension
            
        Returns:
            Dict: File attachment object
        """
        attachment = {
            'type': 'file',
            'filename': filename,
            'description': description,
            'uploaded_at': self.get_iso_timestamp()
        }
        
        if filepath:
            attachment['filepath'] = filepath
        if file_size is not None:
            attachment['filesize'] = file_size
        if file_type:
            attachment['filetype'] = file_type
            
        return attachment
    
    def start_new_session(self, continued_from: Optional[str] = None, 
                         tags: List[str] = None) -> Dict[str, Any]:
        """
        Start a new chat session
        
        Args:
            continued_from: Previous session ID or 'import'
            tags: Tags for the new session
            
        Returns:
            Dict: New session object
        """
        if tags is None:
            tags = ['new-session']
        
        # Close current session
        current_session = self.get_current_session()
        if current_session['ended'] is None:
            current_session['ended'] = self.get_iso_timestamp()
        
        # Create new session
        new_session = {
            'session_id': self.generate_session_id(),
            'started': self.get_iso_timestamp(),
            'ended': None,
            'platform': 'claude',
            'continued_from': continued_from or current_session['session_id'],
            'tags': tags,
            'messages': []
        }
        
        self.history['chat_sessions'].append(new_session)
        self.history['metadata']['version'] += 1
        
        return new_session
    
    def import_previous_history(self, imported_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import previous conversation history
        
        Args:
            imported_data: Previously exported chat history
            
        Returns:
            Dict: Updated history
        """
        # Mark current session as ended
        current_session = self.get_current_session()
        current_session['ended'] = self.get_iso_timestamp()
        
        # Store original conversation ID
        original_conversation_id = self.history['metadata']['conversation_id']
        
        # Merge imported data
        self.history = copy.deepcopy(imported_data)
        
        # Update metadata for continuation
        self.history['metadata'].update({
            'imported_at': self.get_iso_timestamp(),
            'previous_conversation_id': imported_data['metadata']['conversation_id'],
            'conversation_id': original_conversation_id,
            'version': imported_data['metadata']['version'] + 1,
            'continued_from_import': True
        })
        
        # Start new session for continuation
        self.start_new_session('import', ['imported-continuation'])
        
        return self.history
    
    def export_to_yaml(self) -> str:
        """
        Export history to YAML string using existing utilities
        
        Returns:
            str: YAML representation of chat history
        """
        import yaml
        return yaml.dump(self.history, default_flow_style=False, indent=2, sort_keys=False)
    
    def export_for_handoff(self) -> str:
        """
        Export for handoff when approaching usage limits
        
        Returns:
            str: YAML formatted for handoff to new session
        """
        # Close current session
        current_session = self.get_current_session()
        current_session['ended'] = self.get_iso_timestamp()
        
        handoff_data = copy.deepcopy(self.history)
        handoff_data['metadata'].update({
            'exported_for_handoff': self.get_iso_timestamp(),
            'usage_limit_approaching': True,
            'handoff_instructions': [
                "Import this file in new Claude session",
                "Tell Claude: 'Continue our conversation from this imported history'",
                "Claude will automatically resume background tracking"
            ]
        })
        
        import yaml
        return yaml.dump(handoff_data, default_flow_style=False, indent=2, sort_keys=False)
    
    def save_to_file(self, filepath: Union[str, Path]) -> None:
        """
        Save history to file using existing save_yaml utility
        
        Args:
            filepath: Path where to save the YAML file
        """
        save_yaml(self.history, filepath)
    
    def load_from_file(self, filepath: Union[str, Path]) -> Dict[str, Any]:
        """
        Load history from file using existing load_yaml utility
        
        Args:
            filepath: Path to YAML file to load
            
        Returns:
            Dict: Loaded history data
        """
        self.history = load_yaml(filepath)
        return self.history
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current conversation statistics
        
        Returns:
            Dict: Statistics about the conversation
        """
        all_messages = []
        for session in self.history['chat_sessions']:
            all_messages.extend(session['messages'])
        
        estimated_tokens = sum(msg['metadata']['estimated_tokens'] for msg in all_messages)
        
        return {
            'conversation_id': self.history['metadata']['conversation_id'],
            'total_sessions': len(self.history['chat_sessions']),
            'total_messages': self.history['metadata']['total_messages'],
            'total_exchanges': self.history['metadata']['total_exchanges'],
            'estimated_tokens': estimated_tokens,
            'created': self.history['metadata']['created'],
            'last_updated': self.history['metadata']['last_updated'],
            'tags': self.history['metadata']['tags'],
            'approaching_limit': estimated_tokens > 15000
        }
    
    def add_tags(self, tags: List[str]) -> None:
        """
        Add tags to current conversation
        
        Args:
            tags: List of tags to add
        """
        existing_tags = set(self.history['metadata']['tags'])
        new_tags = [tag for tag in tags if tag not in existing_tags]
        
        if new_tags:
            self.history['metadata']['tags'].extend(new_tags)
            self.history['metadata']['version'] += 1
    
    def get_all_messages(self) -> List[Dict[str, Any]]:
        """
        Get all messages across all sessions in chronological order
        
        Returns:
            List: All messages sorted by message number
        """
        all_messages = []
        for session in self.history['chat_sessions']:
            all_messages.extend(session['messages'])
        
        return sorted(all_messages, key=lambda x: x['message_number'])
    
    def find_messages_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Find messages with specific tag
        
        Args:
            tag: Tag to search for
            
        Returns:
            List: Messages containing the tag
        """
        matching_messages = []
        for session in self.history['chat_sessions']:
            for message in session['messages']:
                if tag in message['tags']:
                    matching_messages.append(message)
        
        return matching_messages
    
    def search_content(self, query: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        Search message content for specific text
        
        Args:
            query: Text to search for
            case_sensitive: Whether search should be case sensitive
            
        Returns:
            List: Messages containing the query text
        """
        if not case_sensitive:
            query = query.lower()
        
        matching_messages = []
        for session in self.history['chat_sessions']:
            for message in session['messages']:
                content = message['content']
                if not case_sensitive:
                    content = content.lower()
                
                if query in content:
                    matching_messages.append(message)
        
        return matching_messages
    
    def archive_conversation_section(self, section_key: str) -> Dict[str, Any]:
        """
        Archive a section using the existing archive_and_update_metadata utility pattern
        
        Args:
            section_key: Top-level key to archive
            
        Returns:
            Dict: Updated history with archived section
        """
        # Import the archive function from helpers
        from helpers import archive_and_update_metadata
        
        # Archive the section (this modifies history in place)
        self.history = archive_and_update_metadata(self.history, section_key)
        
        return self.history


# Command-line interface following the pattern from existing utilities
def main():
    """Command-line interface for chat history management"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description='Manage chat history in YAML format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Initialize new chat history
    python chat_utilities.py --init chat_history.yaml
    
    # Add a message
    python chat_utilities.py --add-message chat_history.yaml --role user --content "Hello Claude"
    
    # Export for handoff
    python chat_utilities.py --export-handoff chat_history.yaml
    
    # Get statistics
    python chat_utilities.py --stats chat_history.yaml
        """
    )
    
    parser.add_argument('yaml_file', nargs='?', type=Path, 
                       help='YAML chat history file to work with')
    parser.add_argument('--init', action='store_true',
                       help='Initialize new chat history file')
    parser.add_argument('--add-message', action='store_true',
                       help='Add a message to the chat history')
    parser.add_argument('--role', choices=['user', 'assistant', 'system'],
                       help='Role for the message (with --add-message)')
    parser.add_argument('--content', help='Message content (with --add-message)')
    parser.add_argument('--tags', nargs='*', default=[],
                       help='Tags for the message (with --add-message)')
    parser.add_argument('--export-handoff', action='store_true',
                       help='Export for handoff to new session')
    parser.add_argument('--stats', action='store_true',
                       help='Show conversation statistics')
    parser.add_argument('--search', help='Search message content')
    parser.add_argument('--archive', help='Archive a conversation section')
    
    args = parser.parse_args()
    
    if not args.yaml_file:
        parser.error('yaml_file is required')
    
    try:
        # Initialize or load chat manager
        if args.init:
            if args.yaml_file.exists():
                print(f"Error: File {args.yaml_file} already exists", file=sys.stderr)
                sys.exit(1)
            
            chat = ChatHistoryManager()
            chat.save_to_file(args.yaml_file)
            print(f"✅ Initialized new chat history: {args.yaml_file}")
            
        elif args.add_message:
            if not args.role or not args.content:
                parser.error('--role and --content are required with --add-message')
            
            chat = ChatHistoryManager()
            chat.load_from_file(args.yaml_file)
            chat.record_message(args.role, args.content, args.tags)
            chat.save_to_file(args.yaml_file)
            print(f"✅ Added {args.role} message to {args.yaml_file}")
            
        elif args.export_handoff:
            chat = ChatHistoryManager()
            chat.load_from_file(args.yaml_file)
            handoff_yaml = chat.export_for_handoff()
            
            handoff_file = args.yaml_file.with_suffix('.handoff.yaml')
            with open(handoff_file, 'w') as f:
                f.write(handoff_yaml)
            print(f"✅ Exported handoff to: {handoff_file}")
            
        elif args.stats:
            chat = ChatHistoryManager()
            chat.load_from_file(args.yaml_file)
            stats = chat.get_stats()
            
            print(f"📊 Chat History Statistics for {args.yaml_file}")
            print(f"   Conversation ID: {stats['conversation_id']}")
            print(f"   Total Messages: {stats['total_messages']}")
            print(f"   Total Exchanges: {stats['total_exchanges']}")
            print(f"   Estimated Tokens: {stats['estimated_tokens']}")
            print(f"   Sessions: {stats['total_sessions']}")
            print(f"   Created: {stats['created']}")
            print(f"   Last Updated: {stats['last_updated']}")
            if stats['approaching_limit']:
                print(f"   ⚠️  Approaching token limit!")
                
        elif args.search:
            chat = ChatHistoryManager()
            chat.load_from_file(args.yaml_file)
            results = chat.search_content(args.search)
            
            print(f"🔍 Search results for '{args.search}':")
            for msg in results:
                print(f"   [{msg['role']}] {msg['content'][:100]}...")
                
        elif args.archive:
            chat = ChatHistoryManager()
            chat.load_from_file(args.yaml_file)
            chat.archive_conversation_section(args.archive)
            chat.save_to_file(args.yaml_file)
            print(f"✅ Archived section '{args.archive}' in {args.yaml_file}")
            
        else:
            # Default: show stats
            chat = ChatHistoryManager()
            chat.load_from_file(args.yaml_file)
            stats = chat.get_stats()
            print(f"📄 {args.yaml_file}: {stats['total_messages']} messages, {stats['estimated_tokens']} tokens")
            
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


# Convenience functions for easy usage
def initialize_chat_history() -> ChatHistoryManager:
    """Initialize a new chat history manager"""
    return ChatHistoryManager()

def load_chat_history(filepath: Union[str, Path]) -> ChatHistoryManager:
    """
    Load chat history from file using existing load_yaml utility
    
    Args:
        filepath: Path to YAML file
        
    Returns:
        ChatHistoryManager: Loaded chat history manager
    """
    manager = ChatHistoryManager()
    manager.load_from_file(filepath)
    return manager


if __name__ == "__main__":
    main()
