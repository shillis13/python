#!/bin/bash
echo "--- Running smoke test for delete_item.py ---"

# Setup
cat > test.yaml << EOF
rules:
  metadata:
    version: 1
    last_updated: "2025-06-26T20:00:00Z"
  data:
    - ItemToDelete
    - ItemToKeep
EOF

# Test 1: Successful deletion
python delete_item.py test.yaml --key=rules.data --index=0
if [ $? -ne 0 ]; then
    echo "❌ TEST FAILED: Script failed on a valid deletion."
    exit 1
fi

# Assert the change
if grep -q "ItemToDelete" test.yaml; then
    echo "❌ TEST FAILED: The item was not deleted from the file."
    exit 1
fi
if ! grep -q "ItemToKeep" test.yaml; then
    echo "❌ TEST FAILED: The wrong item was deleted."
    exit 1
fi
echo "✅ Test 1 Passed: Item successfully deleted."

# Teardown
rm test.yaml
echo "--- Test finished ---"
