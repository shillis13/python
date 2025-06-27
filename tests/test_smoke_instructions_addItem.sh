#!/bin/bash
echo "--- Running smoke test for add_item.py ---"

# Setup
cat > test.yaml << EOF
rules:
  metadata:
    version: 1
    last_updated: "2025-06-26T20:00:00Z"
  data:
    - "Rule 1"
EOF

# Test 1: Successful addition
python add_item.py test.yaml --key=rules.data --value="Rule 2"
if [ $? -ne 0 ]; then
    echo "❌ TEST FAILED: Script failed on a valid addition."
    exit 1
fi

# Assert the change
grep -q "Rule 2" test.yaml
if [ $? -ne 0 ]; then
    echo "❌ TEST FAILED: The new item was not added to the file."
    exit 1
fi
echo "✅ Test 1 Passed: Item added to list."

# Teardown
rm test.yaml
echo "--- Test finished ---"
