#!/usr/bin/env python3
"""
Chat Continuity System Packager

Assembles chat continuity documentation and utilities from component parts
based on YAML configuration. Can create combined markdown files, tar archives,
and zip files for distribution.
"""

import os
import sys
import yaml
import tarfile
import zipfile
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class ChatPackager:
    """Assembles chat continuity system files from configuration."""

    def __init__(self, config_path: str):
        """Initialize packager with configuration file."""
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.base_dir = self.config_path.parent

    def load_config(self) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config {self.config_path}: {e}")
            sys.exit(1)

    def read_file_content(self, file_path: str) -> str:
        """Read content from a file."""
        full_path = self.base_dir / file_path
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading {full_path}: {e}")
            return f"<!-- ERROR: Could not read {file_path}: {e} -->"

    def process_template(self, content: str, context: Dict[str, Any]) -> str:
        """Process template variables in content."""
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, str(value))
        return content

    def assemble_markdown(self, output_config: Dict[str, Any]) -> str:
        """Assemble markdown document from components."""
        sections = []

        # Add header if specified
        if "header" in output_config:
            header_content = self.read_file_content(output_config["header"])
            sections.append(header_content)

        # Process sections in order
        for section in output_config.get("sections", []):
            if isinstance(section, str):
                # Simple file inclusion
                content = self.read_file_content(section)
                sections.append(content)
            elif isinstance(section, dict):
                # Section with metadata
                title = section.get("title", "")
                file_path = section.get("file", "")

                if title:
                    sections.append(f"\n## {title}\n")

                if file_path:
                    content = self.read_file_content(file_path)

                    # Handle code blocks
                    if section.get("code_block"):
                        language = section.get("language", "")
                        content = f"```{language}\n{content}\n```"

                    sections.append(content)

        # Add footer if specified
        if "footer" in output_config:
            footer_content = self.read_file_content(output_config["footer"])
            sections.append(footer_content)

        # Join all sections
        assembled = "\n\n---\n\n".join(filter(None, sections))

        # Process template variables
        context = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "version": self.config.get("metadata", {}).get("version", "1.0"),
            **self.config.get("variables", {}),
        }

        return self.process_template(assembled, context)

    def create_combined_files(self):
        """Create all combined output files specified in config."""
        outputs = self.config.get("outputs", {})

        for output_name, output_config in outputs.items():
            output_type = output_config.get("type", "markdown")
            output_path = Path(output_config.get("path", f"{output_name}.md"))

            print(f"Creating {output_type}: {output_path}")

            if output_type == "markdown":
                content = self.assemble_markdown(output_config)

                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Write assembled content
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)

                print(f"  ✅ Created markdown: {output_path}")

            else:
                print(f"  ❌ Unknown output type: {output_type}")

    def create_archive(self, archive_type: str, output_path: str):
        """Create tar or zip archive with specified files."""
        files_config = self.config.get("archive_files", [])

        if not files_config:
            print("No files specified for archive")
            return

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if archive_type == "tar":
            with tarfile.open(output_path, "w:gz") as tar:
                for file_config in files_config:
                    self._add_file_to_tar(tar, file_config)

        elif archive_type == "zip":
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_config in files_config:
                    self._add_file_to_zip(zip_file, file_config)

        print(f"  ✅ Created {archive_type} archive: {output_path}")

    def _add_file_to_tar(self, tar: tarfile.TarFile, file_config: Dict[str, str]):
        """Add file to tar archive."""
        source = file_config.get("source", "")
        target = file_config.get("target", source)

        source_path = self.base_dir / source
        if source_path.exists():
            tar.add(source_path, arcname=target)
            print(f"    Added: {source} -> {target}")
        else:
            print(f"    ❌ Missing: {source}")

    def _add_file_to_zip(self, zip_file: zipfile.ZipFile, file_config: Dict[str, str]):
        """Add file to zip archive."""
        source = file_config.get("source", "")
        target = file_config.get("target", source)

        source_path = self.base_dir / source
        if source_path.exists():
            zip_file.write(source_path, arcname=target)
            print(f"    Added: {source} -> {target}")
        else:
            print(f"    ❌ Missing: {source}")

    def package_all(self, create_tar: bool = False, create_zip: bool = False):
        """Create all specified outputs and optionally archives."""
        print(f"Chat Continuity System Packager")
        print(f"Config: {self.config_path}")
        print(f"Base dir: {self.base_dir}")
        print()

        # Create combined markdown files
        self.create_combined_files()

        # Create archives if requested
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if create_tar:
            tar_path = f"dist/chat_continuity_system_{timestamp}.tar.gz"
            self.create_archive("tar", tar_path)

        if create_zip:
            zip_path = f"dist/chat_continuity_system_{timestamp}.zip"
            self.create_archive("zip", zip_path)

        print("\n✅ Packaging complete!")


"""Main entry point."""


def main():
    parser = argparse.ArgumentParser(
        description="Chat Continuity System Packager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Create combined markdown files only
    python chat_packager.py config.yml
    
    # Create markdown files and tar archive
    python chat_packager.py config.yml --tar
    
    # Create all formats
    python chat_packager.py config.yml --tar --zip
        """,
    )

    parser.add_argument("config", help="YAML configuration file")
    parser.add_argument("--tar", action="store_true", help="Create tar.gz archive")
    parser.add_argument("--zip", action="store_true", help="Create zip archive")
    parser.add_argument("--all", action="store_true", help="Create all archive formats")

    args = parser.parse_args()

    if args.all:
        args.tar = args.zip = True

    # Create packager and run
    packager = ChatPackager(args.config)
    packager.package_all(create_tar=args.tar, create_zip=args.zip)


if __name__ == "__main__":
    main()
