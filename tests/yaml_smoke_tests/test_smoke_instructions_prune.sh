#!/bin/bash
echo "--- Running smoke test for prune.py ---"

# Setup
cat > test.yaml << EOF
persona:
  metadata:
    version: 8
  data: "Current persona"
persona_20250101T000000Z: {}
persona_20250201T000000Z: {}
persona_20250301T000000Z: {}
persona_20250401T000000Z: {}
persona_20250501T000000Z: {}
persona_20250601T000000Z: {} # 6 archives
rules:
  metadata:
    version: 3
  data: []
rules_20250101T000000Z: {}
rules_20250201T000000Z: {} # 2 archives
EOF

# Test 1: Prune with --keep=3
python prune.py test.yaml --keep=3
if [ $? -ne 0 ]; then
    echo "❌ TEST FAILED: Script failed on a valid prune operation."
    exit 1
fi

# Assert the change
persona_archives=$(grep -c "persona_" test.yaml)
rules_archives=$(grep -c "rules_" test.yaml)

if [ "$persona_archives" -ne 3 ]; then
    echo "❌ TEST FAILED: Expected 3 persona archives, found $persona_archives."
    exit 1
fi
if [ "$rules_archives" -ne 2 ]; then
    echo "❌ TEST FAILED: Expected 2 rules archives, found $rules_archives."
    exit 1
fi
echo "✅ Test 1 Passed: Pruning correctly removed older archives."

# Teardown
rm test.yaml
echo "--- Test finished ---"
