#!/usr/bin/env python3
"""
Test runner for Voice Transcription Basic Request Implementation

This script runs all tests and provides a comprehensive test report.
"""

import sys
import os
import unittest
import asyncio
import time
from typing import Dict, List, Any
from io import StringIO

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class AsyncTestResult(unittest.TestResult):
    """Custom test result class for async tests"""
    
    def __init__(self):
        super().__init__()
        self.test_times = {}
        self.async_tests = []
        
    def startTest(self, test):
        super().startTest(test)
        self.test_times[test] = time.time()
        
    def stopTest(self, test):
        super().stopTest(test)
        if test in self.test_times:
            self.test_times[test] = time.time() - self.test_times[test]
            
    def addAsyncTest(self, test_name):
        """Mark a test as async"""
        self.async_tests.append(test_name)


class AsyncTestRunner:
    """Test runner that handles async tests"""
    
    def __init__(self, verbosity=2):
        self.verbosity = verbosity
        self.results = AsyncTestResult()
        
    async def run_async_test(self, test_method):
        """Run a single async test method"""
        try:
            await test_method()
            return True, None
        except Exception as e:
            return False, e
            
    def run_test_suite(self, test_suite):
        """Run a complete test suite"""
        print(f"Running {test_suite.countTestCases()} tests...\n")
        
        for test_group in test_suite:
            if hasattr(test_group, '_tests'):
                for test in test_group._tests:
                    self._run_single_test(test)
            else:
                self._run_single_test(test_group)
                
        return self.results
        
    def _run_single_test(self, test):
        """Run a single test"""
        test_name = f"{test.__class__.__name__}.{test._testMethodName}"
        
        print(f"Running {test_name}... ", end="")
        
        self.results.startTest(test)
        
        try:
            # Check if test method is async
            test_method = getattr(test, test._testMethodName)
            
            if asyncio.iscoroutinefunction(test_method):
                # Run async test
                self.results.addAsyncTest(test_name)
                success, error = asyncio.run(self._run_async_test_safely(test))
            else:
                # Run sync test
                test.debug()
                success, error = True, None
                
            if success:
                print("✅ PASS")
                self.results.addSuccess(test)
            else:
                print("❌ FAIL")
                self.results.addFailure(test, (type(error), error, None))
                if self.verbosity > 1:
                    print(f"   Error: {error}")
                    
        except Exception as e:
            print("💥 ERROR")
            self.results.addError(test, (type(e), e, None))
            if self.verbosity > 1:
                print(f"   Error: {e}")
                
        finally:
            self.results.stopTest(test)
            
    async def _run_async_test_safely(self, test):
        """Safely run an async test with proper setup/teardown"""
        try:
            # Setup
            test.setUp()
            
            # Run the actual test method
            test_method = getattr(test, test._testMethodName)
            await test_method()
            
            return True, None
            
        except Exception as e:
            return False, e
            
        finally:
            # Teardown
            try:
                test.tearDown()
            except:
                pass  # Ignore teardown errors
                

def discover_tests() -> unittest.TestSuite:
    """Discover all test cases"""
    loader = unittest.TestLoader()
    
    # Discover tests in current directory
    suite = loader.discover(
        start_dir=os.path.dirname(__file__),
        pattern='test_*.py'
    )
    
    return suite


def print_test_summary(results: AsyncTestResult):
    """Print a comprehensive test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    total_tests = results.testsRun
    failures = len(results.failures)
    errors = len(results.errors)
    success_count = total_tests - failures - errors
    
    print(f"Total tests run: {total_tests}")
    print(f"Successes: {success_count}")
    print(f"Failures: {failures}")
    print(f"Errors: {errors}")
    print(f"Async tests: {len(results.async_tests)}")
    
    # Success rate
    if total_tests > 0:
        success_rate = (success_count / total_tests) * 100
        print(f"Success rate: {success_rate:.1f}%")
        
    # Timing information
    if results.test_times:
        total_time = sum(results.test_times.values())
        avg_time = total_time / len(results.test_times)
        print(f"Total time: {total_time:.2f}s")
        print(f"Average time per test: {avg_time:.3f}s")
        
        # Slowest tests
        slowest = sorted(results.test_times.items(), key=lambda x: x[1], reverse=True)[:3]
        if slowest:
            print("\nSlowest tests:")
            for test, duration in slowest:
                test_name = f"{test.__class__.__name__}.{test._testMethodName}"
                print(f"  {test_name}: {duration:.3f}s")
    
    # Failure details
    if results.failures:
        print(f"\n❌ FAILURES ({len(results.failures)}):")
        for test, error in results.failures:
            test_name = f"{test.__class__.__name__}.{test._testMethodName}"
            print(f"  - {test_name}")
            if len(str(error[1])) < 100:
                print(f"    {error[1]}")
                
    # Error details
    if results.errors:
        print(f"\n💥 ERRORS ({len(results.errors)}):")
        for test, error in results.errors:
            test_name = f"{test.__class__.__name__}.{test._testMethodName}"
            print(f"  - {test_name}")
            if len(str(error[1])) < 100:
                print(f"    {error[1]}")
                
    print("\n" + "="*60)
    
    # Overall result
    if failures == 0 and errors == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
        
    return success_count == total_tests


def check_dependencies():
    """Check if required dependencies are available"""
    missing_deps = []
    
    try:
        import asyncio
    except ImportError:
        missing_deps.append("asyncio")
        
    try:
        import unittest
    except ImportError:
        missing_deps.append("unittest")
        
    if missing_deps:
        print(f"❌ Missing dependencies: {', '.join(missing_deps)}")
        return False
        
    print("✅ All dependencies available")
    return True


def main():
    """Main test runner"""
    print("Voice Transcription Basic Request Implementation - Test Suite")
    print("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
        
    # Discover tests
    print("Discovering tests...")
    test_suite = discover_tests()
    
    if test_suite.countTestCases() == 0:
        print("❌ No tests found!")
        sys.exit(1)
        
    print(f"Found {test_suite.countTestCases()} tests")
    
    # Run tests
    runner = AsyncTestRunner(verbosity=2)
    results = runner.run_test_suite(test_suite)
    
    # Print summary
    success = print_test_summary(results)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()