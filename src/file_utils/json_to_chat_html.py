#!/usr/bin/env python3
"""
JSON to Chat HTML Converter
Converts ChatGPT JSON exports to nicely formatted HTML chat sessions
"""

import json
import html
import argparse
from datetime import datetime
from pathlib import Path

"""Escape HTML characters and preserve line breaks with smart spacing"""
def escape_html(text):
    if not text:
        return ""
    
    # Escape HTML characters
    escaped = html.escape(text)
    
    # Normalize whitespace: replace multiple consecutive newlines with max 2
    # This prevents excessive <br> tags while preserving intentional paragraph breaks
    import re
    
    # Replace 3+ consecutive newlines with just 2 newlines
    escaped = re.sub(r'\n{3,}', '\n\n', escaped)
    
    # Convert remaining newlines to HTML breaks
    escaped = escaped.replace('\n', '<br>')
    
    # Clean up any excessive <br> tags that might still exist
    escaped = re.sub(r'(<br>){3,}', '<br><br>', escaped)
    
    return escaped

def format_timestamp(timestamp_str):
    """Format timestamp for display"""
    if not timestamp_str:
        return ""
    
    try:
        # Try to parse common timestamp formats
        for fmt in ['%m/%d/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                return dt.strftime('%B %d, %Y at %I:%M %p')
            except ValueError:
                continue
        
        # If parsing fails, return original
        return timestamp_str
    except:
        return timestamp_str

def get_role_display_name(role):
    """Get display name for role"""
    role_map = {
        'user': 'You',
        'assistant': 'ChatGPT',
        'system': 'System',
        'Prompt': 'You',
        'Response': 'ChatGPT'
    }
    return role_map.get(role, role.title())

def get_role_class(role):
    """Get CSS class for role"""
    if role.lower() in ['user', 'prompt']:
        return 'user-message'
    elif role.lower() in ['assistant', 'response']:
        return 'assistant-message'
    else:
        return 'system-message'

def convert_json_to_html(json_file_path, output_file_path=None):
    """Convert ChatGPT JSON export to HTML chat format"""
    
    # Read JSON file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        chat_data = json.load(f)
    
    # Extract metadata
    title = chat_data.get('title', 'ChatGPT Conversation')
    metadata = chat_data.get('metadata', {})
    messages = chat_data.get('messages', [])
    
    # Get export info
    user_name = metadata.get('user', {}).get('name', 'User')
    dates = metadata.get('dates', {})
    created_date = dates.get('created', '')
    
    # Generate output filename if not provided
    if not output_file_path:
        input_path = Path(json_file_path)
        output_file_path = input_path.with_suffix('.html')
    
    # HTML template
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape_html(title)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background-color: #f7f7f8;
            color: #333;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            min-height: 100vh;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 24px;
            margin-bottom: 8px;
            font-weight: 600;
        }}
        
        .header .subtitle {{
            opacity: 0.9;
            font-size: 14px;
        }}
        
        .chat-container {{
            padding: 20px;
        }}
        
        .message {{
            margin-bottom: 24px;
            animation: fadeIn 0.3s ease-in;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .message-header {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            font-size: 14px;
            font-weight: 600;
        }}
        
        .role-badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .user-message .role-badge {{
            background-color: #e3f2fd;
            color: #1565c0;
        }}
        
        .assistant-message .role-badge {{
            background-color: #f3e5f5;
            color: #7b1fa2;
        }}
        
        .system-message .role-badge {{
            background-color: #fff3e0;
            color: #ef6c00;
        }}
        
        .message-content {{
            background: #fafafa;
            padding: 16px 20px;
            border-radius: 12px;
            border-left: 4px solid #ddd;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        
        .user-message .message-content {{
            background: linear-gradient(135deg, #e3f2fd 0%, #f8f9ff 100%);
            border-left-color: #2196f3;
        }}
        
        .assistant-message .message-content {{
            background: linear-gradient(135deg, #f3e5f5 0%, #faf8ff 100%);
            border-left-color: #9c27b0;
        }}
        
        .system-message .message-content {{
            background: linear-gradient(135deg, #fff3e0 0%, #fffef7 100%);
            border-left-color: #ff9800;
            font-style: italic;
        }}
        
        .message-content p {{
            margin-bottom: 12px;
        }}
        
        .message-content p:last-child {{
            margin-bottom: 0;
        }}
        
        .timestamp {{
            color: #666;
            font-size: 12px;
            margin-left: 12px;
        }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 12px;
            border-top: 1px solid #eee;
            background: #f9f9f9;
        }}
        
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 10px;
        }}
        
        .stat {{
            text-align: center;
        }}
        
        .stat-number {{
            font-weight: bold;
            color: #333;
            font-size: 16px;
        }}
        
        .stat-label {{
            color: #666;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* Code blocks */
        .message-content code {{
            background: rgba(0,0,0,0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 13px;
        }}
        
        /* Links */
        .message-content a {{
            color: #1976d2;
            text-decoration: none;
        }}
        
        .message-content a:hover {{
            text-decoration: underline;
        }}
        
        /* Responsive */
        @media (max-width: 600px) {{
            .container {{
                margin: 0;
                box-shadow: none;
            }}
            
            .chat-container {{
                padding: 15px;
            }}
            
            .message-content {{
                padding: 14px 16px;
            }}
            
            .stats {{
                flex-direction: column;
                gap: 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{escape_html(title)}</h1>
            <div class="subtitle">
                {escape_html(user_name)} • {format_timestamp(created_date)}
            </div>
        </div>
        
        <div class="chat-container">
"""
    
    # Add messages
    for i, message in enumerate(messages):
        role = message.get('role', 'unknown')
        content = message.get('say') or message.get('content', '')
        
        role_display = get_role_display_name(role)
        role_class = get_role_class(role)
        
        # Add message HTML
        html_template += f"""
            <div class="message {role_class}">
                <div class="message-header">
                    <span class="role-badge">{role_display}</span>
                </div>
                <div class="message-content">{escape_html(content)}</div>
            </div>
"""
    
    # Add footer with stats
    user_messages = len([m for m in messages if m.get('role', '').lower() in ['user', 'prompt']])
    assistant_messages = len([m for m in messages if m.get('role', '').lower() in ['assistant', 'response']])
    total_words = sum(len(str(m.get('say') or m.get('content', '')).split()) for m in messages)
    
    html_template += f"""
        </div>
        
        <div class="footer">
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(messages)}</div>
                    <div class="stat-label">Total Messages</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{user_messages}</div>
                    <div class="stat-label">User Messages</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{assistant_messages}</div>
                    <div class="stat-label">AI Messages</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{total_words:,}</div>
                    <div class="stat-label">Words</div>
                </div>
            </div>
            <div>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
        </div>
    </div>
</body>
</html>"""
    
    # Write HTML file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(html_template)
    
    return output_file_path

def main():
    parser = argparse.ArgumentParser(description='Convert ChatGPT JSON export to HTML')
    parser.add_argument('input_file', help='Input JSON file path')
    parser.add_argument('-o', '--output', help='Output HTML file path (optional)')
    parser.add_argument('--open', action='store_true', help='Open the HTML file after creation')
    
    args = parser.parse_args()
    
    try:
        output_file = convert_json_to_html(args.input_file, args.output)
        print(f"✅ Successfully converted to HTML: {output_file}")
        
        # Calculate file sizes
        input_size = Path(args.input_file).stat().st_size
        output_size = Path(output_file).stat().st_size
        
        print(f"📊 Input size: {input_size:,} bytes")
        print(f"📊 Output size: {output_size:,} bytes")
        
        if args.open:
            import webbrowser
            webbrowser.open(f'file://{Path(output_file).absolute()}')
            print("🌐 Opened in default browser")
            
    except FileNotFoundError:
        print(f"❌ Error: Input file '{args.input_file}' not found")
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON file - {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
