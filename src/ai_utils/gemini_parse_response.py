#!/usr/bin/env python3
"""
Gemini Response Parser - Extract VBA code from Gemini's response
Parses structured output and writes files back to disk.

Usage:
    python gemini_parse_response.py <response_file> --output-dir ./refactored/
    
Expected format in response:
    ## FILE: ModuleName (filename.bas)
    ```vba
    ... code ...
    ```

Or simpler:
    === ModuleName.bas ===
    ... code ...
    === END ===
"""
import argparse
import re
from pathlib import Path

def parse_gemini_response(response_file: str, output_dir: str, dry_run: bool = False):
    """Parse Gemini response and extract VBA files"""
    
    content = Path(response_file).read_text(encoding='utf-8')
    output = Path(output_dir)
    
    if not dry_run:
        output.mkdir(parents=True, exist_ok=True)
    
    # Pattern 1: Markdown code blocks with file headers
    # ## FILE: ModuleName (filename.bas)
    # ```vba
    # code
    # ```
    pattern1 = r'##\s*FILE:\s*(\w+)\s*\(([^)]+)\)[^\n]*\n```(?:vba|vb)?\n(.*?)```'
    
    # Pattern 2: Simple delimiters
    # === ModuleName.bas ===
    # code
    # === END ===
    pattern2 = r'===\s*(\w+\.(bas|cls))\s*===\n(.*?)===\s*END\s*==='
    
    # Pattern 3: Just filename headers
    # --- filename.bas ---
    # code
    # --- END ---
    pattern3 = r'---\s*(\w+\.(bas|cls))\s*---\n(.*?)---\s*(?:END|$)'
    
    files_found = []
    
    # Try each pattern
    for pattern, name in [(pattern1, 'markdown'), (pattern2, 'equals'), (pattern3, 'dashes')]:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        if matches:
            print(f"Found {len(matches)} files using {name} pattern")
            for match in matches:
                if name == 'markdown':
                    module_name, filename, code = match
                else:
                    filename, ext, code = match
                    module_name = filename.rsplit('.', 1)[0]
                
                code = code.strip()
                files_found.append((filename, module_name, code))
    
    if not files_found:
        print("No VBA files found in response. Trying line-by-line scan...")
        # Fallback: look for Attribute VB_Name markers
        current_file = None
        current_code = []
        
        for line in content.splitlines():
            if 'Attribute VB_Name' in line:
                # Save previous file
                if current_file and current_code:
                    files_found.append((current_file, current_file.rsplit('.', 1)[0], '\n'.join(current_code)))
                # Start new file
                match = re.search(r'Attribute VB_Name = "([^"]+)"', line)
                if match:
                    name = match.group(1)
                    current_file = f"{name}.bas"  # Guess extension
                    current_code = [line]
            elif current_file:
                current_code.append(line)
        
        # Don't forget last file
        if current_file and current_code:
            files_found.append((current_file, current_file.rsplit('.', 1)[0], '\n'.join(current_code)))
    
    # Write files
    print(f"\n{'DRY RUN - ' if dry_run else ''}Writing {len(files_found)} files to {output_dir}:")
    
    for filename, module_name, code in files_found:
        filepath = output / filename
        lines = len(code.splitlines())
        print(f"  {filename}: {lines} lines")
        
        if not dry_run:
            filepath.write_text(code, encoding='utf-8')
    
    print(f"\n{'Would create' if dry_run else 'Created'} {len(files_found)} files")
    return files_found

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse Gemini response and extract VBA files")
    parser.add_argument("response_file", help="File containing Gemini's response")
    parser.add_argument("--output-dir", "-o", default="./gemini_output/", help="Output directory")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    parse_gemini_response(args.response_file, args.output_dir, args.dry_run)
