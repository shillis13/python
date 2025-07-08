#!/bin/bash
echo "--- Running smoke test for merge.py ---"

# Setup
cat > base.yaml << EOF
persona:
  metadata:
    version: 2
  data: "Base Persona"
EOF
cat > changes.yaml << EOF
persona:
  metadata:
    version: 1 # Deliberate conflict
  data: "Changed Persona"
rules:
  metadata:
    version: 1
  data: ["New Rule"]
EOF

# Test 1: Test a conflicting merge
python merge.py base.yaml changes.yaml merged.yaml
if [ $? -eq 0 ]; then
    echo "❌ TEST FAILED: Script should have failed on a conflicting merge but it succeeded."
    exit 1
fi
echo "✅ Test 1 Passed: Script correctly identified a conflict."

# Setup for a clean merge
cat > base.yaml << EOF
persona:
  metadata:
    version: 1
  data: "Base Persona"
EOF
cat > changes.yaml << EOF
rules:
  metadata:
    version: 1
  data: ["New Rule"]
EOF

# Test 2: Test a clean merge
python merge.py base.yaml changes.yaml merged.yaml
if [ $? -ne 0 ]; then
    echo "❌ TEST FAILED: Script failed on a clean merge."
    exit 1
fi

# Assert the result
if ! grep -q "persona:" merged.yaml || ! grep -q "rules:" merged.yaml; then
    echo "❌ TEST FAILED: Merged file is missing expected keys."
    exit 1
fi
echo "✅ Test 2 Passed: Script correctly performed a clean merge."

# Teardown
rm base.yaml changes.yaml merged.yaml
echo "--- Test finished ---"
