# run_tests.py
"""Run all rbGyanX tests"""
import pytest
import sys

if __name__ == "__main__":
    # Run with coverage
    args = [
        "-v",                    # Verbose
        "--cov=.",              # Coverage for all modules
        "--cov-report=html",     # HTML coverage report
        "--cov-report=term",     # Terminal coverage report
        "tests/"                 # Test directory
    ]
    
    sys.exit(pytest.main(args))

