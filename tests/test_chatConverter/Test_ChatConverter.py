import pytest
import os
import subprocess
import json
import yaml
from bs4 import BeautifulSoup

# The main script to be tested
CONVERTER_SCRIPT = "chat_history_converter.py"

# --- Helper Functions ---

def run_converter(args):
    """Runs the converter script with given arguments using subprocess."""
    command = ["python", CONVERTER_SCRIPT] + args
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, f"Converter script failed with error:\n{result.stderr}"
    return result

def deep_sort(obj):
    """Recursively sort lists and dicts to allow for comparison."""
    if isinstance(obj, dict):
        return sorted((k, deep_sort(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(deep_sort(x) for x in obj)
    return obj

def compare_data(d1, d2):
    """Compare two data structures after sorting them to ignore order."""
    return deep_sort(d1) == deep_sort(d2)

# --- Fixtures ---

@pytest.fixture(scope="module")
def sample_chat_data():
    """Provides a sample chat history object for testing."""
    metadata = {
        'title': 'Sample Test Chat',
        'conversation_id': 'conv_20250716T120000Z_test',
        'tags': ['testing', 'sample'],
        'version': 1
    }
    messages = [
        {'role': 'user', 'content': 'Hello, world!'},
        {'role': 'assistant', 'content': 'Hello! How can I help you today?\n\nHere is some `code`.'}
    ]
    return metadata, messages

@pytest.fixture
def temp_dir(tmpdir):
    """Creates a temporary directory for test files."""
    return str(tmpdir)

# --- Test Cases ---

@pytest.mark.parametrize("start_format", ["yml", "json", "md"])
def test_roundtrip_conversion_generated_data(sample_chat_data, temp_dir, start_format):
    """
    Tests a full data conversion round-trip (e.g., yml -> json -> md -> yml)
    starting with generated data to ensure lossless conversion.
    """
    initial_metadata, initial_messages = sample_chat_data

    # Define the conversion chain
    conversion_chain = ["yml", "json", "md"]

    # Rotate the chain to start with the specified format
    start_index = conversion_chain.index(start_format)
    chain = conversion_chain[start_index:] + conversion_chain[:start_index]

    # Add the starting format again at the end to complete the loop
    chain.append(start_format)

    print(f"Testing chain: {' -> '.join(chain)}")

    # Create the initial file
    current_file = os.path.join(temp_dir, f"start.{chain[0]}")
    if chain[0] == 'yml':
        with open(current_file, 'w', encoding='utf-8') as f:
            yaml.dump({'metadata': initial_metadata, 'messages': initial_messages}, f)
    elif chain[0] == 'json':
        with open(current_file, 'w', encoding='utf-8') as f:
            json.dump({'metadata': initial_metadata, 'messages': initial_messages}, f)
    elif chain[0] == 'md':
        from chat_history_converter import to_markdown
        md_content = to_markdown(initial_metadata, initial_messages)
        with open(current_file, 'w', encoding='utf-8') as f:
            f.write(md_content)

    # Run the conversion chain
    for i in range(len(chain) - 1):
        input_file = current_file
        output_format = chain[i+1]
        output_file = os.path.join(temp_dir, f"step_{i}.{output_format}")

        run_converter([input_file, "-o", output_file, "--force"])

        assert os.path.exists(output_file)
        current_file = output_file

    # Load the final file and compare
    final_file = current_file
    from chat_history_converter import parse_yaml_chat, parse_json_chat, parse_markdown_chat
    parsers = {'yml': parse_yaml_chat, 'json': parse_json_chat, 'md': parse_markdown_chat}

    final_metadata, final_messages = parsers[start_format](final_file)

    # Compare metadata and messages
    assert compare_data(initial_metadata, final_metadata)
    assert compare_data(initial_messages, final_messages)

def test_html_metadata_embedding(sample_chat_data, temp_dir):
    """
    Tests that when converting to HTML, the full metadata is correctly
    embedded in the machine-readable script tag.
    """
    initial_metadata, initial_messages = sample_chat_data

    # Create an initial YAML file
    start_file = os.path.join(temp_dir, "start.yml")
    with open(start_file, 'w', encoding='utf-8') as f:
        yaml.dump({'metadata': initial_metadata, 'messages': initial_messages}, f)

    # Convert to HTML
    output_file = os.path.join(temp_dir, "output.html")
    run_converter([start_file, "-o", output_file, "--force"])

    # Parse the HTML and extract the embedded metadata
    with open(output_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, "html.parser")

    script_tag = soup.find("script", {"id": "chat-metadata"})
    assert script_tag is not None, "Metadata script tag not found in HTML output"

    embedded_metadata = json.loads(script_tag.string)

    # Compare the embedded metadata with the original
    assert compare_data(initial_metadata, embedded_metadata)

# Note: A test for provided files would look similar to test_roundtrip_conversion_generated_data
# but would start by pointing to a real file path instead of creating one from a fixture.
# Example:
# @pytest.mark.parametrize("input_file_path", ["claude_chat_limitationsAndFiles_20259629.yml"])
# def test_roundtrip_on_provided_data(input_file_path, temp_dir):
#     # ... logic to copy file to temp_dir and run the chain ...
#     pass


