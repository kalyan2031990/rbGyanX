"""Run all rbGyanX tests with comprehensive reporting"""
import pytest
import sys
from pathlib import Path

def main():
    """Run all tests with coverage and reporting"""
    
    args = [
        "-v",                           # Verbose output
        "--tb=short",                   # Short traceback
        "--strict-markers",             # Strict marker checking
        "--cov=.",                      # Coverage for all code
        "--cov-report=html",            # HTML coverage report
        "--cov-report=term-missing",    # Terminal report with missing lines
        "--cov-report=xml",             # XML for CI/CD
        "--html=test_report.html",      # HTML test report
        "--self-contained-html",        # Self-contained HTML
        "tests/"                        # Test directory
    ]
    
    print("=" * 70)
    print("rbGyanX BASIC v1.0.0 - Comprehensive Test Suite")
    print("=" * 70)
    print()
    
    exit_code = pytest.main(args)
    
    if exit_code == 0:
        print()
        print("=" * 70)
        print("✓ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Coverage report: htmlcov/index.html")
        print("Test report: test_report.html")
    else:
        print()
        print("=" * 70)
        print("✗ SOME TESTS FAILED")
        print("=" * 70)
        print()
        print("Please review the output above for details.")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())

