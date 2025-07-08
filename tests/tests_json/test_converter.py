#!/usr/bin/env python3
"""
Test script for the markdown to JSON converter
"""

# Test with the sample data you provided
test_markdown = """You asked:
----------

* * *

P

How do I run the script?

Edit

---

You asked:
----------

* * *

The script I provided is in a code artifact that you can't directly execute. Let me create an HTML page that you can download and run in your browser:

Chat Content Cleaner - Runnable HTML

Interactive artifact 

How to Run the Script:
----------------------

**Option 1: Using the HTML Tool (Recommended)**

1.  **Download the HTML file** - Click the download button on the HTML artifact I just created above
2.  **Save it** to your computer (e.g., as `chat-cleaner.html`)
3.  **Double-click** the HTML file to open it in your web browser

The HTML tool runs entirely in your browser - no data is sent anywhere, it's all processed locally on your computer.

Would you like me to process the file directly here instead, or do you want to try the HTML tool?

Retry

---

You asked:
----------

* * *

P

If I save off the html, could I use it in the future to do something similar?

Edit

---

You asked:
----------

* * *

**Yes, absolutely!** The HTML file I created is a standalone, reusable tool that you can save and use anytime in the future for similar tasks.

What makes it reusable:
-----------------------

**✅ Completely self-contained:**

*   All code (HTML, CSS, JavaScript) is in one file
*   No external dependencies or internet connection required
*   Works entirely offline in your browser

This is much more convenient than having to recreate the tool each time or asking an AI to process files manually. You'll have your own personal content cleaning tool that works instantly!

Retry"""

# Test the parsing function
import re
import json
from datetime import datetime

"""
Test version of the markdown parser

Args:
    content (str): Raw markdown content to parse
    
Returns:
    Dict[str, Any]: Parsed chat data structure
"""
def parse_test_markdown(content: str):
    
    # Split by the separator pattern
    sections = re.split(r'(?:^|\n)---\s*\n\s*You asked:', content, flags=re.MULTILINE)
    
    messages = []
    
    for i, section in enumerate(sections):
        if not section.strip():
            continue
            
        # Add back "You asked:" for non-first sections
        if i > 0:
            section = "You asked:" + section
        
        # Parse the section
        lines = section.split('\n')
        message = {
            "index": i,
            "role": None,
            "content": "",
            "metadata": {}
        }
        
        content_started = False
        content_lines = []
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            
            if not content_started and not line:
                continue
                
            if line.startswith("You asked:"):
                message["role"] = "user"
                content_started = False
                continue
                
            if line in ["----------", "* * *"]:
                content_started = True
                continue
                
            if line in ["Edit", "Retry"] and line_num >= len(lines) - 5:
                break
                
            if content_started and not message["role"]:
                message["role"] = "assistant"
                
            if content_started:
                content_lines.append(line)
        
        if not message["role"] and content_lines:
            message["role"] = "user"
        
        parsed_content = '\n'.join(content_lines).strip()
        message["content"] = parsed_content
        
        # Handle P marker
        if message["content"].startswith("P\n") or message["content"].startswith("P "):
            message["metadata"]["has_p_marker"] = True
            cleaned_content = re.sub(r'^P\s*\n?\s*', '', message["content"])
            message["content"] = cleaned_content
        
        if message["content"]:
            messages.append(message)
    
    result_data = {
        "metadata": {
            "source": "test_conversion",
            "conversion_date": datetime.now().isoformat(),
            "total_messages": len(messages)
        },
        "messages": messages
    }
    
    return result_data

# Test the parser
test_result = parse_test_markdown(test_markdown)
print(json.dumps(test_result, indent=2))
