# chat chunker

**Created:** 2025-11-02  
**Updated:** 2025-11-02

## Description
Build intelligent chat splitting functionality that breaks large chat histories into multiple chunks, with smart logic to break before prompts rather than mid-conversation. Located at ~/bin/python/src/ai_utils/chat_processing/

## Requirements
- Split large chats into manageable chunks
- Break before prompts (not mid-conversation)
- Configurable target_size parameter (bytes or words, soft max)
- Intelligent back-splitting logic near size thresholds
- Preserve conversation coherence across chunks
- Handle edge cases (very long single messages, nested conversations)

## Dependencies
**Parent:** none (top-level)  
**Depends on:** none  
**Related:** Chat history digest experiments, memory system

## Outputs
- chat_chunker.py in ~/bin/python/src/ai_utils/chat_processing/
- Unit tests for various chunk sizes and edge cases
- Documentation of chunking algorithm
- Example usage in chat processing pipeline

## Done When
- [ ] Basic split logic implemented (break on prompts)
- [ ] target_size parameter added and functional
- [ ] Intelligent back-splitting near thresholds working
- [ ] Edge cases handled (long messages, etc.)
- [ ] Unit tests passing
- [ ] Integrated into chat processing workflow
- [ ] Documentation complete

## Notes
2025-11-02: Task created. This is critical for handling large chat exports that exceed context limits.
