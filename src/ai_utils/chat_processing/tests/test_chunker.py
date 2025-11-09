"""
Unit tests for ChatChunker.

Tests cover:
- Basic chunking functionality
- Threshold crossing with user prompts (CRITICAL)
- Oversized message handling
- Edge cases (empty content, missing fields, etc.)
- Q&A pair preservation validation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib_converters.chunker import ChatChunker, chunk_chat_file


class TestChatChunker:
    """Test suite for ChatChunker class."""
    
    def test_basic_instantiation(self):
        """Test basic ChatChunker instantiation."""
        chunker = ChatChunker()
        assert chunker.target_size == 4000
        assert chunker.strategy == "message_based"
        assert chunker.threshold_ratio == 0.8
    
    def test_custom_parameters(self):
        """Test custom initialization parameters."""
        chunker = ChatChunker(target_size=2000, threshold_ratio=0.9)
        assert chunker.target_size == 2000
        assert chunker.threshold_ratio == 0.9
    
    def test_validation_target_size_minimum(self):
        """Test that target_size < 1000 raises ValueError."""
        try:
            ChatChunker(target_size=500)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "at least 1000" in str(e)
    
    def test_validation_threshold_ratio(self):
        """Test threshold_ratio validation."""
        try:
            ChatChunker(threshold_ratio=1.5)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e)
    
    def test_basic_chunking_under_threshold(self):
        """Test simple chunking when messages are under threshold."""
        chunker = ChatChunker(target_size=4000)
        
        chat_data = {
            'metadata': {
                'chat_id': 'test_001',
                'platform': 'test',
                'created_at': '2025-11-06T10:00:00Z',
                'updated_at': '2025-11-06T10:00:00Z'
            },
            'messages': [
                {
                    'message_id': 'msg_001',
                    'role': 'user',
                    'content': 'Short message',
                    'timestamp': '2025-11-06T10:00:00Z'
                },
                {
                    'message_id': 'msg_002',
                    'role': 'assistant',
                    'content': 'Short response',
                    'timestamp': '2025-11-06T10:00:05Z'
                }
            ]
        }
        
        result = chunker.chunk_chat(chat_data)
        
        assert 'chunking' in result['metadata']
        assert result['metadata']['chunking']['total_chunks'] == 1
        assert result['metadata']['chunking']['strategy'] == 'message_based'
        assert result['metadata']['chunking']['target_size'] == 4000
    
    def test_threshold_crossing_user_prompt_preservation(self):
        """
        CRITICAL TEST: Verify chunks start with user prompts when threshold crossed.
        
        This test addresses the bug identified in Codex peer review.
        When threshold is exceeded, new chunk should START with user prompt,
        not end with it, to preserve Q&A pair coherence.
        """
        chunker = ChatChunker(target_size=4000, threshold_ratio=0.8)
        
        messages = [
            # 3000 tokens (approaching threshold of 3200)
            {
                'message_id': 'msg_001',
                'role': 'assistant',
                'content': 'x' * 12000,
                'timestamp': '2025-11-06T10:00:00Z'
            },
            # User prompt (should START new chunk)
            {
                'message_id': 'msg_002',
                'role': 'user',
                'content': 'How do I do this? ' * 125,  # ~500 tokens
                'timestamp': '2025-11-06T10:01:00Z'
            },
            # Assistant response (should be WITH user prompt)
            {
                'message_id': 'msg_003',
                'role': 'assistant',
                'content': 'Here is how: ' * 250,  # ~1000 tokens
                'timestamp': '2025-11-06T10:01:05Z'
            }
        ]
        
        chat_data = {
            'metadata': {
                'chat_id': 'test_critical',
                'platform': 'test',
                'created_at': '2025-11-06T10:00:00Z',
                'updated_at': '2025-11-06T10:01:05Z'
            },
            'messages': messages
        }
        
        result = chunker.chunk_chat(chat_data)
        chunks = result['metadata']['chunking']['chunk_metadata']
        
        # Should create 2 chunks
        assert len(chunks) >= 2, "Should create at least 2 chunks"
        
        # CRITICAL: Chunk 2 must start with user prompt
        chunk2_start = chunks[1]['message_range'][0]
        assert messages[chunk2_start]['role'] == 'user', \
            "Chunk 2 must start with user prompt to preserve Q&A pairs"
        
        # Verify Q&A pair is together
        chunk2_end = chunks[1]['message_range'][1]
        chunk2_messages = messages[chunk2_start:chunk2_end + 1]
        
        has_user = any(m['role'] == 'user' for m in chunk2_messages)
        has_assistant = any(m['role'] == 'assistant' for m in chunk2_messages)
        
        assert has_user and has_assistant, \
            "Q&A pair (user + assistant) must be in same chunk"
    
    def test_oversized_single_message(self):
        """Test handling of single message exceeding target_size."""
        chunker = ChatChunker(target_size=1000)
        
        chat_data = {
            'metadata': {
                'chat_id': 'test_oversized',
                'platform': 'test',
                'created_at': '2025-11-06T10:00:00Z',
                'updated_at': '2025-11-06T10:00:00Z'
            },
            'messages': [
                {
                    'message_id': 'msg_001',
                    'role': 'user',
                    'content': 'x' * 5000,  # Way over target
                    'timestamp': '2025-11-06T10:00:00Z'
                },
                {
                    'message_id': 'msg_002',
                    'role': 'assistant',
                    'content': 'Short',
                    'timestamp': '2025-11-06T10:00:05Z'
                }
            ]
        }
        
        result = chunker.chunk_chat(chat_data)
        
        # Should handle gracefully, not crash
        assert result['metadata']['chunking']['total_chunks'] >= 1
    
    def test_empty_content_handling(self):
        """Test messages with empty content."""
        chunker = ChatChunker()
        
        chat_data = {
            'metadata': {
                'chat_id': 'test_empty',
                'platform': 'test',
                'created_at': '2025-11-06T10:00:00Z',
                'updated_at': '2025-11-06T10:00:00Z'
            },
            'messages': [
                {
                    'message_id': 'msg_001',
                    'role': 'user',
                    'content': '',
                    'timestamp': '2025-11-06T10:00:00Z'
                },
                {
                    'message_id': 'msg_002',
                    'role': 'assistant',
                    'content': 'Response',
                    'timestamp': '2025-11-06T10:00:05Z'
                }
            ]
        }
        
        result = chunker.chunk_chat(chat_data)
        assert result['metadata']['chunking']['total_chunks'] >= 1
    
    def test_missing_content_field(self):
        """Test messages without content field."""
        chunker = ChatChunker()
        
        chat_data = {
            'metadata': {
                'chat_id': 'test_missing',
                'platform': 'test',
                'created_at': '2025-11-06T10:00:00Z',
                'updated_at': '2025-11-06T10:00:00Z'
            },
            'messages': [
                {
                    'message_id': 'msg_001',
                    'role': 'system',
                    'timestamp': '2025-11-06T10:00:00Z'
                    # No content field
                }
            ]
        }
        
        result = chunker.chunk_chat(chat_data)
        assert result['metadata']['chunking']['total_chunks'] == 1
    
    def test_single_message_chat(self):
        """Test chat with only one message."""
        chunker = ChatChunker()
        
        chat_data = {
            'metadata': {
                'chat_id': 'test_single',
                'platform': 'test',
                'created_at': '2025-11-06T10:00:00Z',
                'updated_at': '2025-11-06T10:00:00Z'
            },
            'messages': [
                {
                    'message_id': 'msg_001',
                    'role': 'user',
                    'content': 'Hello',
                    'timestamp': '2025-11-06T10:00:00Z'
                }
            ]
        }
        
        result = chunker.chunk_chat(chat_data)
        
        assert result['metadata']['chunking']['total_chunks'] == 1
        chunk = result['metadata']['chunking']['chunk_metadata'][0]
        assert chunk['message_range'] == [0, 0]
        assert chunk['chunk_id'] == 'chunk_001'
    
    def test_chunk_metadata_structure(self):
        """Verify chunk metadata has correct structure."""
        chunker = ChatChunker()
        
        chat_data = {
            'metadata': {
                'chat_id': 'test_structure',
                'platform': 'test',
                'created_at': '2025-11-06T10:00:00Z',
                'updated_at': '2025-11-06T10:00:00Z'
            },
            'messages': [
                {
                    'message_id': 'msg_001',
                    'role': 'user',
                    'content': 'Test',
                    'timestamp': '2025-11-06T10:00:00Z'
                }
            ]
        }
        
        result = chunker.chunk_chat(chat_data)
        chunk = result['metadata']['chunking']['chunk_metadata'][0]
        
        # Verify all required fields present
        assert 'chunk_id' in chunk
        assert 'sequence_number' in chunk
        assert 'message_range' in chunk
        assert 'token_count' in chunk
        assert 'timestamp_range' in chunk
        
        # Verify field types
        assert isinstance(chunk['chunk_id'], str)
        assert isinstance(chunk['sequence_number'], int)
        assert isinstance(chunk['message_range'], list)
        assert len(chunk['message_range']) == 2
        assert isinstance(chunk['token_count'], int)
        assert isinstance(chunk['timestamp_range'], dict)
        assert 'start' in chunk['timestamp_range']
        assert 'end' in chunk['timestamp_range']
    
    def test_convenience_function(self):
        """Test chunk_chat_file convenience function."""
        chat_data = {
            'metadata': {
                'chat_id': 'test_convenience',
                'platform': 'test',
                'created_at': '2025-11-06T10:00:00Z',
                'updated_at': '2025-11-06T10:00:00Z'
            },
            'messages': [
                {
                    'message_id': 'msg_001',
                    'role': 'user',
                    'content': 'Test',
                    'timestamp': '2025-11-06T10:00:00Z'
                }
            ]
        }
        
        result = chunk_chat_file(chat_data, target_size=2000)
        
        assert 'chunking' in result['metadata']
        assert result['metadata']['chunking']['target_size'] == 2000
    
    def test_input_validation(self):
        """Test various invalid inputs."""
        chunker = ChatChunker()
        
        # Empty dict
        try:
            chunker.chunk_chat({})
            assert False, "Should raise ValueError"
        except ValueError:
            pass
        
        # Missing messages
        try:
            chunker.chunk_chat({'metadata': {}})
            assert False, "Should raise ValueError"
        except ValueError:
            pass
        
        # Empty messages list
        try:
            chunker.chunk_chat({'metadata': {}, 'messages': []})
            assert False, "Should raise ValueError"
        except ValueError:
            pass


def run_all_tests():
    """Run all tests and report results."""
    test_suite = TestChatChunker()
    tests = [
        ('test_basic_instantiation', test_suite.test_basic_instantiation),
        ('test_custom_parameters', test_suite.test_custom_parameters),
        ('test_validation_target_size_minimum', test_suite.test_validation_target_size_minimum),
        ('test_validation_threshold_ratio', test_suite.test_validation_threshold_ratio),
        ('test_basic_chunking_under_threshold', test_suite.test_basic_chunking_under_threshold),
        ('test_threshold_crossing_user_prompt_preservation', test_suite.test_threshold_crossing_user_prompt_preservation),
        ('test_oversized_single_message', test_suite.test_oversized_single_message),
        ('test_empty_content_handling', test_suite.test_empty_content_handling),
        ('test_missing_content_field', test_suite.test_missing_content_field),
        ('test_single_message_chat', test_suite.test_single_message_chat),
        ('test_chunk_metadata_structure', test_suite.test_chunk_metadata_structure),
        ('test_convenience_function', test_suite.test_convenience_function),
        ('test_input_validation', test_suite.test_input_validation),
    ]
    
    passed = 0
    failed = 0
    
    print("Running ChatChunker Tests")
    print("=" * 70)
    
    for test_name, test_func in tests:
        try:
            test_func()
            print(f"✓ {test_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {test_name}: {e}")
            failed += 1
    
    print("=" * 70)
    print(f"\nResults: {passed} passed, {failed} failed out of {len(tests)} tests")
    
    if failed == 0:
        print("\n✅ All tests PASSED!")
    else:
        print(f"\n❌ {failed} test(s) FAILED")
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
