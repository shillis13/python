#!/bin/bash
echo "--- Running smoke test for update_key.py ---"

# Setup
cat > test.yaml << EOF
persona:
  metadata:
    version: 1
    last_updated: "2025-06-26T20:00:00Z"
  data: "Initial Persona"
rules:
  metadata:
    version: 5
    last_updated: "2025-06-26T20:00:00Z"
  data:
    - "Rule 1"
EOF

# Test 1: Successful update
python update_key.py test.yaml --key=persona.data --value="Updated Persona"
if [ $? -ne 0 ]; then
    echo "❌ TEST FAILED: Script failed on a valid update."
    exit 1
fi

# Assert the change
grep -q "Updated Persona" test.yaml
if [ $? -ne 0 ]; then
    echo "❌ TEST FAILED: The value was not updated in the file."
    exit 1
fi

# Assert the archive
grep -q "persona_.*" test.yaml
if [ $? -ne 0 ]; then
    echo "❌ TEST FAILED: An archive key for 'persona' was not created."
    exit 1
fi
echo "✅ Test 1 Passed: Value updated and state archived."


# Teardown
rm test.yaml
echo "--- Test finished ---"
