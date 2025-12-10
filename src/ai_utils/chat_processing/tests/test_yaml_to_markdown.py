"""Tests for YAML to Markdown conversion."""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_utils.chat_processing.lib_converters.lib_doc_converter import (
    yaml_to_markdown,
    _format_yaml_to_markdown,
    _format_key_as_header,
)


class TestFormatKeyAsHeader:
    """Tests for key-to-header formatting."""

    def test_snake_case_conversion(self):
        assert _format_key_as_header("snake_case_key") == "Snake Case Key"

    def test_dash_case_conversion(self):
        assert _format_key_as_header("dash-case-key") == "Dash Case Key"

    def test_mixed_case_conversion(self):
        assert _format_key_as_header("mixed_dash-case") == "Mixed Dash Case"

    def test_simple_key(self):
        assert _format_key_as_header("simple") == "Simple"

    def test_numeric_key(self):
        assert _format_key_as_header("10_exported") == "10 Exported"


class TestFormatYamlToMarkdown:
    """Tests for the recursive YAML-to-Markdown conversion."""

    def test_simple_string_value(self):
        data = {"title": "Hello World"}
        result = _format_yaml_to_markdown(data, level=2)
        assert "## Title" in result
        assert "Hello World" in result

    def test_list_of_strings(self):
        data = {"items": ["one", "two", "three"]}
        result = _format_yaml_to_markdown(data, level=2)
        assert "## Items" in result
        assert "- one" in result
        assert "- two" in result
        assert "- three" in result

    def test_nested_dict(self):
        data = {"parent": {"child": "value"}}
        result = _format_yaml_to_markdown(data, level=2)
        assert "## Parent" in result
        assert "### Child" in result
        assert "value" in result

    def test_none_value(self):
        data = {"empty_section": None}
        result = _format_yaml_to_markdown(data, level=2)
        assert "## Empty Section" in result

    def test_numeric_value(self):
        data = {"count": 42}
        result = _format_yaml_to_markdown(data, level=2)
        assert "## Count" in result
        assert "42" in result

    def test_skip_metadata(self):
        data = {"metadata": {"title": "Test"}, "content": "Body"}
        result = _format_yaml_to_markdown(data, level=2, skip_metadata=True)
        assert "## Metadata" not in result
        assert "## Content" in result
        assert "Body" in result


class TestYamlToMarkdown:
    """Tests for the top-level yaml_to_markdown function."""

    def test_extracts_title_from_metadata(self):
        data = {
            "metadata": {"title": "My Document"},
            "content": "Body text"
        }
        result = yaml_to_markdown(data)
        assert result.startswith("# My Document")

    def test_provided_title_overrides_metadata(self):
        data = {
            "metadata": {"title": "Original"},
            "content": "Body"
        }
        result = yaml_to_markdown(data, title="Override Title")
        assert "# Override Title" in result
        assert "# Original" not in result

    def test_metadata_info_line(self):
        data = {
            "metadata": {
                "title": "Test Doc",
                "version": "1.0",
                "status": "active",
                "created": "2025-01-01",
                "maintainer": "TestUser"
            },
            "content": "Body"
        }
        result = yaml_to_markdown(data)
        assert "**Version:** 1.0" in result
        assert "**Status:** active" in result
        assert "**Created:** 2025-01-01" in result
        assert "**Maintainer:** TestUser" in result

    def test_purpose_rendered_as_italics(self):
        data = {
            "metadata": {
                "title": "Test",
                "purpose": "This is the purpose."
            }
        }
        result = yaml_to_markdown(data)
        assert "*This is the purpose.*" in result

    def test_complex_nested_structure(self):
        data = {
            "metadata": {"title": "Architecture"},
            "layers": {
                "communication": {
                    "directory": "ai_comms/",
                    "contains": ["Tasks", "Messages", "Results"]
                },
                "implementation": {
                    "directory": "ai_claude/"
                }
            }
        }
        result = yaml_to_markdown(data)

        # Check headers are present at correct levels
        assert "# Architecture" in result
        assert "## Layers" in result
        assert "### Communication" in result
        assert "### Implementation" in result

        # Check content
        assert "ai_comms/" in result
        assert "- Tasks" in result
        assert "- Messages" in result
        assert "- Results" in result
        assert "ai_claude/" in result

    def test_multiline_string_preserved(self):
        data = {
            "description": "Line one.\nLine two.\nLine three."
        }
        result = yaml_to_markdown(data, title="Test")
        assert "Line one." in result
        assert "Line two." in result

    def test_list_of_dicts(self):
        data = {
            "items": [
                {"name": "First"},
                {"name": "Second"}
            ]
        }
        result = yaml_to_markdown(data, title="Test")
        assert "First" in result
        assert "Second" in result

    def test_no_excessive_blank_lines(self):
        """Result should not have more than 2 consecutive newlines."""
        data = {
            "section1": "Content 1",
            "section2": "Content 2",
            "section3": "Content 3"
        }
        result = yaml_to_markdown(data, title="Test")
        assert "\n\n\n" not in result


class TestYamlToMarkdownIntegration:
    """Integration tests with realistic document structures."""

    def test_architecture_style_document(self):
        """Test with a structure similar to architecture_overview.yml."""
        data = {
            "metadata": {
                "title": "Multi-AI Orchestration Architecture",
                "version": "1.0.0",
                "status": "active",
                "purpose": "High-level system architecture."
            },
            "vision": {
                "summary": "Scalable multi-AI coordination infrastructure.",
                "principles": [
                    "Brutal honesty over diplomacy",
                    "AIs as collaborative partners"
                ]
            },
            "workspace": {
                "root": "~/Documents/AI/ai_root/",
                "structure": {
                    "ai_claude": {
                        "purpose": "Claude-specific state"
                    },
                    "ai_memories": {
                        "purpose": "Processed chat histories"
                    }
                }
            }
        }

        result = yaml_to_markdown(data)

        # Title
        assert result.startswith("# Multi-AI Orchestration Architecture")

        # Metadata info
        assert "**Version:** 1.0.0" in result
        assert "**Status:** active" in result

        # Purpose in italics
        assert "*High-level system architecture.*" in result

        # Vision section
        assert "## Vision" in result
        assert "### Summary" in result
        assert "### Principles" in result
        assert "- Brutal honesty over diplomacy" in result

        # Workspace section
        assert "## Workspace" in result
        assert "~/Documents/AI/ai_root/" in result

        # Nested structure
        assert "Ai Claude" in result
        assert "Ai Memories" in result
        assert "Claude-specific state" in result

    def test_empty_data(self):
        """Test with empty dict."""
        result = yaml_to_markdown({}, title="Empty Doc")
        assert "# Empty Doc" in result

    def test_no_metadata(self):
        """Test document without metadata."""
        data = {
            "content": "Just some content.",
            "items": ["a", "b", "c"]
        }
        result = yaml_to_markdown(data, title="No Metadata Doc")
        assert "# No Metadata Doc" in result
        assert "## Content" in result
        assert "## Items" in result
