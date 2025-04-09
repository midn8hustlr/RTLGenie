#!/bin/bash

# Check if problem ID is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <problem_id>"
    echo "Example: $0 Prob156_review2015_fancytimer"
    exit 1
fi

# Get the problem ID from command line
PROBLEM_ID=$1

# Construct the file paths based on problem ID
SPEC_FILE="./verilog-eval/dataset_spec-to-rtl/${PROBLEM_ID}_prompt.txt"
TESTBENCH_FILE="./verilog-eval/dataset_spec-to-rtl/${PROBLEM_ID}_test.sv"
REFERENCE_FILE="./verilog-eval/dataset_spec-to-rtl/${PROBLEM_ID}_ref.sv"

# Check if the files exist
if [ ! -f "$SPEC_FILE" ]; then
    echo "Error: Specification file not found: $SPEC_FILE"
    exit 1
fi

if [ ! -f "$TESTBENCH_FILE" ]; then
    echo "Error: Testbench file not found: $TESTBENCH_FILE"
    exit 1
fi

if [ ! -f "$REFERENCE_FILE" ]; then
    echo "Error: Reference file not found: $REFERENCE_FILE"
    exit 1
fi

# Run the Python script with the constructed file paths
echo "Running for problem: $PROBLEM_ID"
echo "Specification file: $SPEC_FILE"
echo "Testbench file: $TESTBENCH_FILE"
echo "Reference file: $REFERENCE_FILE"
echo

python main.py --spec-id "$PROBLEM_ID" \
                  --spec-file "$SPEC_FILE" \
                  --testbench-file "$TESTBENCH_FILE" \
                  --reference-file "$REFERENCE_FILE"

# Check if the execution was successful
if [ $? -eq 0 ]; then
    echo
    echo "Execution completed successfully."
    echo "Output files are in: ./checkpoints/$PROBLEM_ID/"
else
    echo
    echo "Execution failed."
fi
