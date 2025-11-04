Parsers implement a single function:

```python
def parse(raw_path:str, exporter:str)->dict:
    '''
    Returns normalized staged dict conforming to staged.schema.json.
    '''
```

Provide one per AI as needed, e.g., `chatgpt_parser.py`, `claude_parser.py`.
