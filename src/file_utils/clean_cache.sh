#!/usr/local/bin/bash

Dir="FILE"
Verbose=true

echo "find ${Dir} -type d -name \"__pycache__\" -exec rm -rf {} \;"
if [ $Verbose ]; then
    echo "Deleting:"
    find $Dir -type d -name "__pycache__" 
fi
find $Dir -type d -name "__pycache__" -exec rm -rf {} \;

echo "find $Dir -type f -name \"*.pyc\" -delete"
if [ $Verbose ]; then
    echo "Deleting:"
    find $Dir -type f -name "*.pyc" 
fi
find $Dir -type f -name "*.pyc" -delete

