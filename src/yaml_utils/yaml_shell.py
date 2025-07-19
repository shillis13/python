#!/usr/bin/env python3
"""
Interactive YAML Shell Explorer

A Unix-like interactive shell for exploring YAML files with commands like
cd, ls, cat, find, grep, and more. Non-destructive exploration only.
"""

import argparse
import sys
import re
import json
import shlex
from pathlib import Path
from typing import Any, Dict, List, Union, Optional
from yaml_utils.yaml_helpers import load_yaml

# Try to import readline for command history and completion
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

# Try to import colorama for colored output
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    class Fore:
        RED = GREEN = BLUE = YELLOW = CYAN = MAGENTA = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""
    COLORS_AVAILABLE = False

class YamlShell:
    """Interactive shell for exploring YAML data structures"""
    
    def __init__(self, yaml_file: Path):
        self.yaml_file = yaml_file
        self.data = load_yaml(yaml_file)
        self.current_path = []
        self.history = []
        self.bookmarks = {}
        
        # Setup readline if available
        if READLINE_AVAILABLE:
            readline.set_completer(self.complete)
            readline.parse_and_bind("tab: complete")
    
    """
    Get the current data object based on the current path
    
    Returns:
        Any: Current data object
    """
    def get_current_data(self) -> Any:
        current = self.data
        for segment in self.current_path:
            if isinstance(current, dict):
                current = current.get(segment)
            elif isinstance(current, list):
                try:
                    current = current[int(segment)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current
    
    """
    Get the current path as a string
    
    Returns:
        str: Current path representation
    """
    def get_current_path_str(self) -> str:
        if not self.current_path:
            return "/"
        return "/" + "/".join(self.current_path)
    
    """
    Format a value for display
    
    Args:
        value: Value to format
        truncate: Maximum length before truncation
        
    Returns:
        str: Formatted value
    """
    def format_value(self, value: Any, truncate: int = 60) -> str:
        if isinstance(value, dict):
            return f"{Fore.BLUE}{{}} ({len(value)} keys){Style.RESET_ALL}"
        elif isinstance(value, list):
            return f"{Fore.GREEN}[] ({len(value)} items){Style.RESET_ALL}"
        else:
            value_str = str(value)
            if len(value_str) > truncate:
                value_str = value_str[:truncate-3] + "..."
            
            if isinstance(value, bool):
                color = Fore.MAGENTA
            elif isinstance(value, (int, float)):
                color = Fore.YELLOW
            elif isinstance(value, str):
                color = Fore.GREEN
            elif value is None:
                color = Fore.RED
                value_str = "null"
            else:
                color = Fore.WHITE
            
            return f"{color}{value_str}{Style.RESET_ALL}"
    
    """
    Tab completion for commands and paths
    
    Args:
        text: Current text being completed
        state: Completion state
        
    Returns:
        str: Next completion option
    """
    def complete(self, text: str, state: int) -> Optional[str]:
        try:
            line = readline.get_line_buffer()
            parts = shlex.split(line)
            
            # Command completion
            commands = ['cd', 'ls', 'cat', 'pwd', 'find', 'grep', 'tree', 'type', 'size', 
                       'help', 'history', 'bookmark', 'goto', 'export', 'search', 'quit', 'exit']
            
            if len(parts) <= 1:
                matches = [cmd for cmd in commands if cmd.startswith(text)]
                return matches[state] if state < len(matches) else None
            
            # Path completion
            command = parts[0]
            if command in ['cd', 'cat', 'find', 'tree', 'type', 'size']:
                current_data = self.get_current_data()
                if isinstance(current_data, dict):
                    keys = list(current_data.keys())
                    matches = [key for key in keys if str(key).startswith(text)]
                    return matches[state] if state < len(matches) else None
            
        except Exception:
            pass
        
        return None
    
    """
    Change directory command
    
    Args:
        args: Command arguments
    """
    def cmd_cd(self, args: List[str]) -> None:
        if not args:
            # Go to root
            self.current_path = []
            return
        
        path = args[0]
        
        if path == "/":
            self.current_path = []
        elif path == "..":
            if self.current_path:
                self.current_path.pop()
        elif path == "-":
            # Go back to previous directory (if in history)
            if len(self.history) >= 2:
                prev_path = self.history[-2].split()[1:] if len(self.history[-2].split()) > 1 else []
                self.current_path = prev_path
        elif path.startswith("/"):
            # Absolute path
            new_path = [p for p in path.split("/") if p]
            if self.navigate_to_path(new_path):
                self.current_path = new_path
            else:
                print(f"cd: {path}: No such key or index")
        else:
            # Relative path
            new_path = self.current_path + [path]
            if self.navigate_to_path(new_path):
                self.current_path = new_path
            else:
                print(f"cd: {path}: No such key or index")
    
    """
    Navigate to a specific path and validate it exists
    
    Args:
        path: List of path segments
        
    Returns:
        bool: True if path exists
    """
    def navigate_to_path(self, path: List[str]) -> bool:
        current = self.data
        for segment in path:
            if isinstance(current, dict):
                if segment not in current:
                    return False
                current = current[segment]
            elif isinstance(current, list):
                try:
                    idx = int(segment)
                    if idx < 0 or idx >= len(current):
                        return False
                    current = current[idx]
                except ValueError:
                    return False
            else:
                return False
        return True
    
    """
    List directory contents
    
    Args:
        args: Command arguments
    """
    def cmd_ls(self, args: List[str]) -> None:
        show_values = "-v" in args or "--values" in args
        show_types = "-t" in args or "--types" in args
        long_format = "-l" in args or "--long" in args
        
        current_data = self.get_current_data()
        
        if current_data is None:
            print("ls: cannot access current location")
            return
        
        if isinstance(current_data, dict):
            items = list(current_data.items())
            print(f"Total: {len(items)} keys")
            
            for key, value in items:
                key_color = Fore.BLUE if isinstance(value, dict) else Fore.GREEN if isinstance(value, list) else Fore.WHITE
                
                if long_format:
                    type_info = type(value).__name__
                    if isinstance(value, (dict, list)):
                        size_info = f"({len(value)})"
                    else:
                        size_info = f"({len(str(value))} chars)" if isinstance(value, str) else ""
                    
                    print(f"{key_color}{key:<20}{Style.RESET_ALL} {type_info:<10} {size_info:<15}", end="")
                    if show_values:
                        print(f" = {self.format_value(value)}")
                    else:
                        print()
                else:
                    print(f"{key_color}{key}{Style.RESET_ALL}", end="")
                    if show_types:
                        type_name = type(value).__name__
                        print(f" ({type_name})", end="")
                    if show_values:
                        print(f" = {self.format_value(value)}")
                    else:
                        print()
        
        elif isinstance(current_data, list):
            print(f"Total: {len(current_data)} items")
            for i, item in enumerate(current_data):
                item_color = Fore.CYAN
                
                if long_format:
                    type_info = type(item).__name__
                    size_info = f"({len(item)})" if isinstance(item, (dict, list)) else ""
                    print(f"{item_color}[{i}]<-15{Style.RESET_ALL} {type_info:<10} {size_info:<15}", end="")
                    if show_values:
                        print(f" = {self.format_value(item)}")
                    else:
                        print()
                else:
                    print(f"{item_color}[{i}]{Style.RESET_ALL}", end="")
                    if show_types:
                        type_name = type(item).__name__
                        print(f" ({type_name})", end="")
                    if show_values:
                        print(f" = {self.format_value(item)}")
                    else:
                        print()
        else:
            print(f"Current location contains: {self.format_value(current_data)}")
    
    """
    Display content of current location or specified path
    
    Args:
        args: Command arguments
    """
    def cmd_cat(self, args: List[str]) -> None:
        if args:
            # Navigate to specified path temporarily
            if args[0].startswith("/"):
                path_segments = [p for p in args[0].split("/") if p]
            else:
                path_segments = self.current_path + [args[0]]
            
            current = self.data
            for segment in path_segments:
                if isinstance(current, dict):
                    current = current.get(segment)
                elif isinstance(current, list):
                    try:
                        current = current[int(segment)]
                    except (ValueError, IndexError):
                        current = None
                        break
                else:
                    current = None
                    break
        else:
            current = self.get_current_data()
        
        if current is None:
            print("cat: No such key or index")
            return
        
        if isinstance(current, (dict, list)):
            try:
                # Pretty print JSON
                print(json.dumps(current, indent=2, ensure_ascii=False))
            except Exception:
                print(str(current))
        else:
            print(self.format_value(current, truncate=1000))
    
    """
    Print current working directory
    
    Args:
        args: Command arguments
    """
    def cmd_pwd(self, args: List[str]) -> None:
        print(self.get_current_path_str())
    
    """
    Find keys or values matching a pattern
    
    Args:
        args: Command arguments
    """
    def cmd_find(self, args: List[str]) -> None:
        if not args:
            print("find: missing search pattern")
            return
        
        pattern = args[0]
        search_keys = "-k" in args or "--keys" in args
        search_values = "-v" in args or "--values" in args
        case_insensitive = "-i" in args or "--ignore-case" in args
        
        if not search_keys and not search_values:
            search_keys = search_values = True  # Search both by default
        
        flags = re.IGNORECASE if case_insensitive else 0
        
        def search_recursive(data, path=""):
            results = []
            
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}/{key}" if path else key
                    
                    # Search in keys
                    if search_keys and re.search(pattern, str(key), flags):
                        results.append(f"{Fore.BLUE}{current_path}{Style.RESET_ALL} (key match)")
                    
                    # Search in values
                    if search_values and not isinstance(value, (dict, list)):
                        if re.search(pattern, str(value), flags):
                            results.append(f"{Fore.GREEN}{current_path}{Style.RESET_ALL} = {self.format_value(value)}")
                    
                    # Recurse
                    results.extend(search_recursive(value, current_path))
            
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    current_path = f"{path}[{i}]" if path else f"[{i}]"
                    
                    # Search in values
                    if search_values and not isinstance(item, (dict, list)):
                        if re.search(pattern, str(item), flags):
                            results.append(f"{Fore.GREEN}{current_path}{Style.RESET_ALL} = {self.format_value(item)}")
                    
                    # Recurse
                    results.extend(search_recursive(item, current_path))
            
            return results
        
        current_data = self.get_current_data()
        results = search_recursive(current_data, self.get_current_path_str().rstrip('/'))
        
        if results:
            for result in results:
                print(result)
        else:
            print(f"find: no matches found for '{pattern}'")
    
    """
    Search for text in values (like grep)
    
    Args:
        args: Command arguments
    """
    def cmd_grep(self, args: List[str]) -> None:
        if not args:
            print("grep: missing search pattern")
            return
        
        pattern = args[0]
        case_insensitive = "-i" in args
        
        flags = re.IGNORECASE if case_insensitive else 0
        
        def grep_recursive(data, path=""):
            results = []
            
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}/{key}" if path else key
                    if isinstance(value, str) and re.search(pattern, value, flags):
                        results.append(f"{Fore.CYAN}{current_path}{Style.RESET_ALL}: {self.format_value(value)}")
                    results.extend(grep_recursive(value, current_path))
            
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    current_path = f"{path}[{i}]" if path else f"[{i}]"
                    if isinstance(item, str) and re.search(pattern, item, flags):
                        results.append(f"{Fore.CYAN}{current_path}{Style.RESET_ALL}: {self.format_value(item)}")
                    results.extend(grep_recursive(item, current_path))
            
            return results
        
        current_data = self.get_current_data()
        results = grep_recursive(current_data, self.get_current_path_str().rstrip('/'))
        
        if results:
            for result in results:
                print(result)
        else:
            print(f"grep: no matches found for '{pattern}'")
    
    """
    Display tree structure
    
    Args:
        args: Command arguments
    """
    def cmd_tree(self, args: List[str]) -> None:
        max_depth = 3  # Default depth
        show_values = "-v" in args
        
        # Parse depth argument
        for i, arg in enumerate(args):
            if arg == "-d" or arg == "--depth":
                if i + 1 < len(args):
                    try:
                        max_depth = int(args[i + 1])
                    except ValueError:
                        print(f"tree: invalid depth '{args[i + 1]}'")
                        return
        
        def print_tree(data, prefix="", depth=0):
            if depth > max_depth:
                return
            
            if isinstance(data, dict):
                items = list(data.items())
                for i, (key, value) in enumerate(items):
                    is_last = i == len(items) - 1
                    current_prefix = "└── " if is_last else "├── "
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    
                    value_display = ""
                    if show_values and not isinstance(value, (dict, list)):
                        value_display = f" = {self.format_value(value, 30)}"
                    
                    print(f"{prefix}{current_prefix}{Fore.BLUE}{key}{Style.RESET_ALL}{value_display}")
                    
                    if isinstance(value, (dict, list)) and depth < max_depth:
                        print_tree(value, next_prefix, depth + 1)
            
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    is_last = i == len(data) - 1
                    current_prefix = "└── " if is_last else "├── "
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    
                    value_display = ""
                    if show_values and not isinstance(item, (dict, list)):
                        value_display = f" = {self.format_value(item, 30)}"
                    
                    print(f"{prefix}{current_prefix}{Fore.CYAN}[{i}]{Style.RESET_ALL}{value_display}")
                    
                    if isinstance(item, (dict, list)) and depth < max_depth:
                        print_tree(item, next_prefix, depth + 1)
        
        current_data = self.get_current_data()
        print(f"{Fore.YELLOW}{self.get_current_path_str()}{Style.RESET_ALL}")
        print_tree(current_data)
    
    """
    Show type information
    
    Args:
        args: Command arguments
    """
    def cmd_type(self, args: List[str]) -> None:
        current_data = self.get_current_data()
        if current_data is None:
            print("type: current location is None")
            return
        
        type_name = type(current_data).__name__
        print(f"Type: {type_name}")
        
        if isinstance(current_data, (dict, list)):
            print(f"Length: {len(current_data)}")
        elif isinstance(current_data, str):
            print(f"Length: {len(current_data)} characters")
    
    """
    Show size information
    
    Args:
        args: Command arguments
    """
    def cmd_size(self, args: List[str]) -> None:
        current_data = self.get_current_data()
        if current_data is None:
            print("size: current location is None")
            return
        
        if isinstance(current_data, (dict, list)):
            print(f"Items: {len(current_data)}")
        elif isinstance(current_data, str):
            print(f"Characters: {len(current_data)}")
        else:
            print(f"Value: {current_data}")
        
        # Estimate memory size
        try:
            import sys
            size_bytes = sys.getsizeof(json.dumps(current_data))
            print(f"Estimated size: {size_bytes:,} bytes ({size_bytes/1024:.1f} KB)")
        except Exception:
            pass
    
    """
    Show command history
    
    Args:
        args: Command arguments
    """
    def cmd_history(self, args: List[str]) -> None:
        for i, cmd in enumerate(self.history, 1):
            print(f"{i:3d}  {cmd}")
    
    """
    Bookmark management
    
    Args:
        args: Command arguments
    """
    def cmd_bookmark(self, args: List[str]) -> None:
        if not args:
            # List bookmarks
            if self.bookmarks:
                print("Bookmarks:")
                for name, path in self.bookmarks.items():
                    print(f"  {name} -> {path}")
            else:
                print("No bookmarks set")
        elif len(args) == 1:
            # Add bookmark
            name = args[0]
            self.bookmarks[name] = self.get_current_path_str()
            print(f"Bookmark '{name}' set to {self.get_current_path_str()}")
        else:
            print("bookmark: usage: bookmark [name]")
    
    """
    Go to bookmark
    
    Args:
        args: Command arguments
    """
    def cmd_goto(self, args: List[str]) -> None:
        if not args:
            print("goto: missing bookmark name")
            return
        
        name = args[0]
        if name in self.bookmarks:
            path_str = self.bookmarks[name]
            if path_str == "/":
                self.current_path = []
            else:
                new_path = [p for p in path_str.split("/") if p]
                if self.navigate_to_path(new_path):
                    self.current_path = new_path
                else:
                    print(f"goto: bookmark '{name}' points to invalid path")
        else:
            print(f"goto: bookmark '{name}' not found")
    
    """
    Export current data to file
    
    Args:
        args: Command arguments
    """
    def cmd_export(self, args: List[str]) -> None:
        if not args:
            print("export: missing filename")
            return
        
        filename = args[0]
        current_data = self.get_current_data()
        
        try:
            if filename.endswith('.json'):
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(current_data, f, indent=2, ensure_ascii=False)
            elif filename.endswith('.yaml') or filename.endswith('.yml'):
                import yaml
                with open(filename, 'w', encoding='utf-8') as f:
                    yaml.dump(current_data, f, default_flow_style=False, indent=2)
            else:
                # Default to JSON
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(current_data, f, indent=2, ensure_ascii=False)
            
            print(f"Exported current data to {filename}")
        except Exception as e:
            print(f"export: error writing file: {e}")
    
    """
    Search command (alias for find)
    
    Args:
        args: Command arguments
    """
    def cmd_search(self, args: List[str]) -> None:
        self.cmd_find(args)
    
    """
    Display help
    
    Args:
        args: Command arguments
    """
    def cmd_help(self, args: List[str]) -> None:
        help_text = f"""
{Style.BRIGHT}YAML Shell Commands:{Style.RESET_ALL}

Navigation:
  cd [path]         Change to directory (path, .., /, -)
  ls [-l] [-v] [-t] List contents (long, values, types)
  pwd               Print current path

Content:
  cat [path]        Display content at path
  tree [-d N] [-v]  Show tree structure (depth N, values)
  type              Show type information
  size              Show size information

Search:
  find [-k] [-v] [-i] pattern   Find keys/values matching pattern
  grep [-i] pattern             Search text in values
  search pattern                Alias for find

Navigation aids:
  bookmark [name]   Set/list bookmarks
  goto name         Go to bookmark
  history           Show command history

Export:
  export filename   Export current data to file

Other:
  help              Show this help
  quit, exit        Exit the shell

{Style.BRIGHT}Options:{Style.RESET_ALL}
  -l, --long        Long format listing
  -v, --values      Show values
  -t, --types       Show types
  -k, --keys        Search keys only
  -i, --ignore-case Case insensitive search
  -d, --depth N     Tree depth limit
        """
        print(help_text)
    
    """
    Main command processing loop
    """
    def run(self) -> None:
        print(f"{Style.BRIGHT}YAML Shell - Exploring: {self.yaml_file}{Style.RESET_ALL}")
        print("Type 'help' for available commands, 'quit' to exit")
        
        while True:
            try:
                # Create prompt
                path_str = self.get_current_path_str()
                prompt = f"{Fore.CYAN}yaml:{path_str}${Style.RESET_ALL} "
                
                # Read command
                try:
                    line = input(prompt).strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nBye!")
                    break
                
                if not line:
                    continue
                
                # Add to history
                self.history.append(line)
                
                # Parse command
                try:
                    parts = shlex.split(line)
                except ValueError as e:
                    print(f"Error parsing command: {e}")
                    continue
                
                if not parts:
                    continue
                
                command = parts[0].lower()
                args = parts[1:]
                
                # Handle built-in commands
                if command in ['quit', 'exit']:
                    print("Bye!")
                    break
                elif command == 'cd':
                    self.cmd_cd(args)
                elif command == 'ls':
                    self.cmd_ls(args)
                elif command == 'cat':
                    self.cmd_cat(args)
                elif command == 'pwd':
                    self.cmd_pwd(args)
                elif command == 'find':
                    self.cmd_find(args)
                elif command == 'grep':
                    self.cmd_grep(args)
                elif command == 'tree':
                    self.cmd_tree(args)
                elif command == 'type':
                    self.cmd_type(args)
                elif command == 'size':
                    self.cmd_size(args)
                elif command == 'history':
                    self.cmd_history(args)
                elif command == 'bookmark':
                    self.cmd_bookmark(args)
                elif command == 'goto':
                    self.cmd_goto(args)
                elif command == 'export':
                    self.cmd_export(args)
                elif command == 'search':
                    self.cmd_search(args)
                elif command == 'help':
                    self.cmd_help(args)
                else:
                    print(f"Unknown command: {command}. Type 'help' for available commands.")
                    
            except Exception as e:
                print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(
        description='Interactive shell for exploring YAML files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start interactive shell
    python yaml_shell.py config.yaml
    
    # In the shell:
    yaml:/$ ls -v
    yaml:/$ cd metadata
    yaml:/metadata$ cat version
    yaml:/metadata$ find -i "test"
    yaml:/metadata$ tree -d 2
        """
    )
    
    parser.add_argument('yaml_file', type=Path, help='YAML file to explore')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    
    args = parser.parse_args()
    
    # Disable colors if requested
    if args.no_color:
        global COLORS_AVAILABLE
        COLORS_AVAILABLE = False
    
    try:
        shell = YamlShell(args.yaml_file)
        shell.run()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
