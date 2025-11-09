"""
Chat Chunker - Intelligent conversation splitting module.

This module provides functionality to split large chat histories into manageable
chunks while preserving conversation coherence. The primary strategy is message-based
chunking that breaks BEFORE user prompts to keep Q&A pairs together.

Author: AI (Claude CLI)
Created: 2025-11-06
Version: 1.0.1
"""

from typing import Dict, List, Optional


class ChatChunker:
    """
    Intelligent chat chunker that preserves conversation coherence.
    
    Chunking Strategy:
    1. Count tokens for each message
    2. Accumulate messages until approaching target_size
    3. When close to threshold (80-100%), look ahead
    4. Break BEFORE next user prompt (not after assistant response)
    5. If single message exceeds target, include it as standalone chunk
    
    The goal is to maintain semantic coherence by keeping conversational
    exchanges (user prompt + assistant response) together whenever possible.
    """
    
    def __init__(
        self,
        target_size: int = 4000,
        strategy: str = "message_based",
        threshold_ratio: float = 0.8
    ):
        """
        Initialize the ChatChunker.
        
        Args:
            target_size: Soft maximum chunk size in tokens (default: 4000)
            strategy: Chunking strategy to use (default: "message_based")
            threshold_ratio: When to start looking for break points (default: 0.8 = 80%)
        
        Raises:
            ValueError: If target_size < 1000 or threshold_ratio not in (0, 1]
        """
        if target_size < 1000:
            raise ValueError("target_size must be at least 1000 tokens")
        
        if not (0 < threshold_ratio <= 1.0):
            raise ValueError("threshold_ratio must be between 0 and 1")
        
        self.target_size = target_size
        self.strategy = strategy
        self.threshold_ratio = threshold_ratio
    
    def chunk_chat(self, chat_data: Dict) -> Dict:
        """
        Main entry point. Add chunking metadata to chat data.
        
        This method takes a v2.0 chat history dictionary and adds chunking
        metadata to the metadata section. The original chat_data is modified
        in place and also returned.
        
        Args:
            chat_data: Dictionary containing v2.0 chat history
                      (must have 'metadata' and 'messages' keys)
        
        Returns:
            Modified chat_data dictionary with chunking metadata added
        
        Raises:
            ValueError: If chat_data is missing required fields
        """
        result = self._validate_chat_data(chat_data)
        if result is not None:
            raise ValueError(result)
        
        messages = chat_data['messages']
        chunks = self._compute_chunks(messages)
        
        # Add chunking metadata to chat_data
        if 'metadata' not in chat_data:
            chat_data['metadata'] = {}
        
        chat_data['metadata']['chunking'] = {
            'strategy': self.strategy,
            'target_size': self.target_size,
            'total_chunks': len(chunks),
            'chunk_metadata': chunks
        }
        
        return chat_data
    
    def _validate_chat_data(self, chat_data: Dict) -> Optional[str]:
        """
        Validate that chat_data has required structure.
        
        Args:
            chat_data: Dictionary to validate
        
        Returns:
            Error message string if invalid, None if valid
        """
        if not isinstance(chat_data, dict):
            return "chat_data must be a dictionary"
        
        if 'messages' not in chat_data:
            return "chat_data must contain 'messages' key"
        
        if not isinstance(chat_data['messages'], list):
            return "'messages' must be a list"
        
        if len(chat_data['messages']) == 0:
            return "'messages' list cannot be empty"
        
        return None
    
    def _compute_chunks(self, messages: List[Dict]) -> List[Dict]:
        """
        Core chunking logic. Compute chunk boundaries and metadata.
        
        Algorithm:
        1. Iterate through messages, tracking token count
        2. When current_tokens >= threshold, look for break point
        3. Break BEFORE next user prompt if possible
        4. Create chunk metadata for each completed chunk
        5. Handle edge cases (very long single messages)
        
        Args:
            messages: List of message dictionaries from v2.0 schema
        
        Returns:
            List of chunk metadata dictionaries
        """
        chunks = []
        current_chunk_start = 0
        current_token_count = 0
        threshold = self.target_size * self.threshold_ratio
        
        i = 0
        while i < len(messages):
            msg = messages[i]
            msg_tokens = self._count_tokens(msg.get('content', ''))
            
            # Edge case: Single message exceeds target size
            if msg_tokens > self.target_size:
                # If we have accumulated messages, finalize that chunk first
                if i > current_chunk_start:
                    chunk_meta = self._create_chunk_metadata(
                        chunk_num=len(chunks) + 1,
                        message_range=[current_chunk_start, i - 1],
                        messages=messages[current_chunk_start:i]
                    )
                    chunks.append(chunk_meta)

                # Create chunk with just this oversized message
                chunk_meta = self._create_chunk_metadata(
                    chunk_num=len(chunks) + 1,
                    message_range=[i, i],
                    messages=[msg]
                )
                chunks.append(chunk_meta)

                current_chunk_start = i + 1
                current_token_count = 0
                i += 1
                continue

            # CRITICAL FIX: Check if current message is user prompt and adding it would exceed threshold
            # If so, finalize chunk BEFORE this message to keep Q&A pairs together
            if msg.get('role') == 'user' and current_token_count + msg_tokens >= threshold:
                # Adding this user prompt would exceed threshold
                # Finalize current chunk WITHOUT this message
                if i > current_chunk_start:
                    chunk_meta = self._create_chunk_metadata(
                        chunk_num=len(chunks) + 1,
                        message_range=[current_chunk_start, i - 1],
                        messages=messages[current_chunk_start:i]
                    )
                    chunks.append(chunk_meta)

                    # Start new chunk WITH this user message
                    current_chunk_start = i
                    current_token_count = msg_tokens
                    i += 1
                    continue

            # Check if we've exceeded the hard limit (target_size, not just threshold)
            if current_token_count + msg_tokens > self.target_size:
                # Force break here even if not ideal
                if i > current_chunk_start:
                    chunk_meta = self._create_chunk_metadata(
                        chunk_num=len(chunks) + 1,
                        message_range=[current_chunk_start, i - 1],
                        messages=messages[current_chunk_start:i]
                    )
                    chunks.append(chunk_meta)

                    current_chunk_start = i
                    current_token_count = msg_tokens
                else:
                    # Single message case, include it
                    current_token_count += msg_tokens
            else:
                # Under limit, keep accumulating
                current_token_count += msg_tokens
            
            i += 1
        
        # Final chunk (remaining messages)
        if current_chunk_start < len(messages):
            chunk_meta = self._create_chunk_metadata(
                chunk_num=len(chunks) + 1,
                message_range=[current_chunk_start, len(messages) - 1],
                messages=messages[current_chunk_start:]
            )
            chunks.append(chunk_meta)
        
        return chunks
    
    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text. Uses simple approximation for now.
        
        Approximation: ~4 characters per token for English text.
        This is a conservative estimate that works reasonably well
        for most use cases.
        
        Future enhancement: Integrate tiktoken for accurate GPT token counting.
        
        Args:
            text: Text content to count tokens for
        
        Returns:
            Approximate token count as integer
        """
        if not text:
            return 0
        
        # Simple approximation: 4 chars per token
        # Add 1 to avoid zero for very short texts
        char_count = len(text)
        token_count = (char_count // 4) + 1
        
        return token_count
    
    def _create_chunk_metadata(
        self,
        chunk_num: int,
        message_range: List[int],
        messages: List[Dict]
    ) -> Dict:
        """
        Build chunk metadata dictionary.
        
        Creates a complete chunk metadata object including:
        - chunk_id (formatted as chunk_NNN)
        - sequence_number (1-indexed)
        - message_range (start and end indices, inclusive)
        - token_count (sum of all message tokens in chunk)
        - timestamp_range (first and last message timestamps)
        
        Args:
            chunk_num: Sequence number for this chunk (1-indexed)
            message_range: [start_index, end_index] (inclusive)
            messages: List of message dictionaries in this chunk
        
        Returns:
            Dictionary containing chunk metadata
        """
        chunk_id = f'chunk_{chunk_num:03d}'
        
        # Calculate total token count for chunk
        total_tokens = sum(
            self._count_tokens(msg.get('content', ''))
            for msg in messages
        )
        
        # Extract timestamp range
        first_timestamp = messages[0].get('timestamp', '')
        last_timestamp = messages[-1].get('timestamp', '')
        
        chunk_metadata = {
            'chunk_id': chunk_id,
            'sequence_number': chunk_num,
            'message_range': message_range,
            'token_count': total_tokens,
            'timestamp_range': {
                'start': first_timestamp,
                'end': last_timestamp
            }
        }
        
        return chunk_metadata


def chunk_chat_file(
    chat_data: Dict,
    target_size: int = 4000,
    strategy: str = "message_based"
) -> Dict:
    """
    Convenience function to chunk a chat file.
    
    This is a simple wrapper around ChatChunker for quick usage.
    
    Args:
        chat_data: v2.0 chat history dictionary
        target_size: Soft maximum chunk size in tokens
        strategy: Chunking strategy to use
    
    Returns:
        Modified chat_data with chunking metadata
    
    Example:
        >>> chat = load_chat('conversation.yaml')
        >>> chunked = chunk_chat_file(chat, target_size=4000)
        >>> print(chunked['metadata']['chunking']['total_chunks'])
        3
    """
    chunker = ChatChunker(target_size=target_size, strategy=strategy)
    result = chunker.chunk_chat(chat_data)
    
    return result
