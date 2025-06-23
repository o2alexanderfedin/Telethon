"""
Comprehensive Test Runner for Voice Transcription

This module implements Epic 1 User Story 1.8: Basic Testing Infrastructure
providing a unified test runner with coverage monitoring, performance benchmarks,
and organized test execution for all voice transcription components.

Features:
- Unified test execution across all components
- Test coverage monitoring and reporting
- Performance benchmark execution
- Test result aggregation and reporting
- Integration test coordination
- Mock server management
"""

import asyncio
import pytest
import sys
import os
import time
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import coverage


class TestResult:
    """Test execution result"""
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.errors = []
        self.duration = 0.0
        self.coverage_percentage = 0.0
        
    @property
    def success_rate(self) -> float:
        """Calculate test success rate"""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting"""
        return {
            'total_tests': self.total_tests,
            'passed_tests': self.passed_tests,
            'failed_tests': self.failed_tests,
            'skipped_tests': self.skipped_tests,
            'success_rate': self.success_rate,
            'duration': self.duration,
            'coverage_percentage': self.coverage_percentage,
            'errors': self.errors
        }


class VoiceTranscriptionTestRunner:
    """
    Comprehensive test runner for voice transcription components.
    
    Provides organized test execution with coverage monitoring,
    performance benchmarks, and detailed reporting.
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize test runner.
        
        Args:
            base_path: Base path for voice transcription module
        """
        self.base_path = Path(base_path) if base_path else Path(__file__).parent.parent
        self.results = {}
        self.coverage_data = None
        
        # Test categories
        self.test_categories = {
            'unit': [
                'test_state_manager.py',
                'test_transcription_manager.py', 
                'test_automatic_cleanup.py',
                'test_error_handling.py',
                'tests/test_basic_request.py',
                'tests/test_update_handler.py'
            ],
            'integration': [
                'test_integration.py'  # Will create
            ],
            'performance': [
                'test_performance.py'  # Will create
            ]
        }
        
    def run_all_tests(
        self,
        include_coverage: bool = True,
        include_performance: bool = True,
        verbose: bool = True
    ) -> Dict[str, TestResult]:
        """
        Run all test categories.
        
        Args:
            include_coverage: Whether to include coverage analysis
            include_performance: Whether to run performance tests
            verbose: Whether to show verbose output
            
        Returns:
            Dictionary of test results by category
        """
        print("🧪 Starting Voice Transcription Test Suite")
        print("=" * 50)
        
        start_time = time.time()
        
        try:
            # Initialize coverage if requested
            if include_coverage:
                self._start_coverage()
                
            # Run unit tests
            print("\n📋 Running Unit Tests...")
            self.results['unit'] = self._run_test_category('unit', verbose)
            
            # Run integration tests
            print("\n🔗 Running Integration Tests...")
            self.results['integration'] = self._run_test_category('integration', verbose)
            
            # Run performance tests
            if include_performance:
                print("\n⚡ Running Performance Tests...")
                self.results['performance'] = self._run_test_category('performance', verbose)
                
            # Generate coverage report
            if include_coverage:
                self._generate_coverage_report()
                
        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            raise
        finally:
            total_duration = time.time() - start_time
            
        # Print summary
        self._print_summary(total_duration)
        
        return self.results
        
    def run_unit_tests(self, verbose: bool = True) -> TestResult:
        """Run only unit tests"""
        print("📋 Running Unit Tests Only...")
        return self._run_test_category('unit', verbose)
        
    def run_integration_tests(self, verbose: bool = True) -> TestResult:
        """Run only integration tests"""
        print("🔗 Running Integration Tests Only...")
        return self._run_test_category('integration', verbose)
        
    def run_performance_tests(self, verbose: bool = True) -> TestResult:
        """Run only performance tests"""
        print("⚡ Running Performance Tests Only...")
        return self._run_test_category('performance', verbose)
        
    def run_coverage_analysis(self) -> float:
        """Run coverage analysis and return percentage"""
        print("📊 Running Coverage Analysis...")
        
        self._start_coverage()
        
        # Run all unit tests for coverage
        for test_file in self.test_categories['unit']:
            test_path = self.base_path / test_file
            if test_path.exists():
                self._run_single_test(test_path, verbose=False)
                
        return self._generate_coverage_report()
        
    def _run_test_category(self, category: str, verbose: bool) -> TestResult:
        """Run tests for a specific category"""
        result = TestResult()
        start_time = time.time()
        
        test_files = self.test_categories.get(category, [])
        
        for test_file in test_files:
            test_path = self.base_path / test_file
            
            if not test_path.exists():
                if verbose:
                    print(f"⚠️  Test file not found: {test_file}")
                continue
                
            if verbose:
                print(f"  Running {test_file}...")
                
            file_result = self._run_single_test(test_path, verbose)
            
            # Aggregate results
            result.total_tests += file_result.total_tests
            result.passed_tests += file_result.passed_tests
            result.failed_tests += file_result.failed_tests
            result.skipped_tests += file_result.skipped_tests
            result.errors.extend(file_result.errors)
            
        result.duration = time.time() - start_time
        
        if verbose:
            self._print_category_summary(category, result)
            
        return result
        
    def _run_single_test(self, test_path: Path, verbose: bool) -> TestResult:
        """Run a single test file"""
        result = TestResult()
        
        try:
            # Run pytest on the file
            cmd = [
                sys.executable, '-m', 'pytest',
                str(test_path),
                '--tb=short',
                '-q' if not verbose else '-v',
                '--json-report',
                '--json-report-file=/tmp/pytest_report.json'
            ]
            
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.base_path
            )
            
            # Parse results
            try:
                with open('/tmp/pytest_report.json', 'r') as f:
                    report = json.load(f)
                    
                result.total_tests = report['summary']['total']
                result.passed_tests = report['summary'].get('passed', 0)
                result.failed_tests = report['summary'].get('failed', 0)
                result.skipped_tests = report['summary'].get('skipped', 0)
                
                # Collect error details
                for test in report.get('tests', []):
                    if test['outcome'] == 'failed':
                        result.errors.append({
                            'test': test['nodeid'],
                            'error': test.get('call', {}).get('longrepr', 'Unknown error')
                        })
                        
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                # Fallback to parsing stdout
                if proc.returncode == 0:
                    result.total_tests = 1
                    result.passed_tests = 1
                else:
                    result.total_tests = 1
                    result.failed_tests = 1
                    result.errors.append({
                        'test': str(test_path),
                        'error': proc.stderr or proc.stdout
                    })
                    
        except Exception as e:
            result.total_tests = 1
            result.failed_tests = 1
            result.errors.append({
                'test': str(test_path),
                'error': str(e)
            })
            
        return result
        
    def _start_coverage(self):
        """Start coverage monitoring"""
        try:
            self.coverage_data = coverage.Coverage(
                source=['voice_transcription'],
                omit=['*/test*', '*/tests/*', '*/__pycache__/*']
            )
            self.coverage_data.start()
        except Exception as e:
            print(f"⚠️  Could not start coverage monitoring: {e}")
            
    def _generate_coverage_report(self) -> float:
        """Generate coverage report and return percentage"""
        if not self.coverage_data:
            return 0.0
            
        try:
            self.coverage_data.stop()
            
            # Generate report
            coverage_percentage = self.coverage_data.report(
                show_missing=True,
                skip_covered=False
            )
            
            # Generate HTML report
            html_dir = self.base_path / 'coverage_html'
            self.coverage_data.html_report(directory=str(html_dir))
            
            print(f"📊 Coverage Report: {coverage_percentage:.1f}%")
            print(f"📄 HTML Report: {html_dir}/index.html")
            
            return coverage_percentage
            
        except Exception as e:
            print(f"⚠️  Could not generate coverage report: {e}")
            return 0.0
            
    def _print_category_summary(self, category: str, result: TestResult):
        """Print summary for a test category"""
        status = "✅" if result.failed_tests == 0 else "❌"
        print(f"  {status} {category.title()} Tests: "
              f"{result.passed_tests}/{result.total_tests} passed "
              f"({result.success_rate:.1f}%) in {result.duration:.2f}s")
              
        if result.failed_tests > 0:
            print(f"    ❌ {result.failed_tests} failed tests")
            
        if result.skipped_tests > 0:
            print(f"    ⏭️  {result.skipped_tests} skipped tests")
            
    def _print_summary(self, total_duration: float):
        """Print overall test summary"""
        print("\n" + "=" * 50)
        print("🏁 Test Execution Summary")
        print("=" * 50)
        
        total_tests = sum(r.total_tests for r in self.results.values())
        total_passed = sum(r.passed_tests for r in self.results.values())
        total_failed = sum(r.failed_tests for r in self.results.values())
        total_skipped = sum(r.skipped_tests for r in self.results.values())
        
        overall_success = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"📊 Overall Results:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {total_passed}")
        print(f"   Failed: {total_failed}")
        print(f"   Skipped: {total_skipped}")
        print(f"   Success Rate: {overall_success:.1f}%")
        print(f"   Total Duration: {total_duration:.2f}s")
        
        # Category breakdown
        print(f"\n📋 Category Breakdown:")
        for category, result in self.results.items():
            status = "✅" if result.failed_tests == 0 else "❌"
            print(f"   {status} {category.title()}: "
                  f"{result.passed_tests}/{result.total_tests} "
                  f"({result.success_rate:.1f}%)")
                  
        # Coverage information
        if any(hasattr(r, 'coverage_percentage') for r in self.results.values()):
            avg_coverage = sum(getattr(r, 'coverage_percentage', 0) 
                             for r in self.results.values()) / len(self.results)
            print(f"\n📊 Average Coverage: {avg_coverage:.1f}%")
            
        # Failure details
        if total_failed > 0:
            print(f"\n❌ Failed Tests:")
            for category, result in self.results.items():
                if result.errors:
                    print(f"   {category.title()}:")
                    for error in result.errors[:3]:  # Show first 3 errors
                        print(f"     - {error['test']}")
                        
        # Overall status
        if total_failed == 0:
            print(f"\n🎉 All tests passed! System is ready for deployment.")
        else:
            print(f"\n⚠️  {total_failed} tests failed. Review failures before deployment.")
            
    def generate_report(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_tests': sum(r.total_tests for r in self.results.values()),
                'passed_tests': sum(r.passed_tests for r in self.results.values()),
                'failed_tests': sum(r.failed_tests for r in self.results.values()),
                'skipped_tests': sum(r.skipped_tests for r in self.results.values()),
            },
            'categories': {
                category: result.to_dict() 
                for category, result in self.results.items()
            },
            'epic1_requirements': {
                'unit_tests_complete': 'unit' in self.results and self.results['unit'].failed_tests == 0,
                'integration_tests_complete': 'integration' in self.results and self.results['integration'].failed_tests == 0,
                'performance_tests_complete': 'performance' in self.results and self.results['performance'].failed_tests == 0,
                'coverage_threshold_met': any(getattr(r, 'coverage_percentage', 0) >= 90 for r in self.results.values())
            }
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"📄 Test report saved to: {output_file}")
            
        return report


# CLI Interface
def main():
    """Main CLI interface for test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Voice Transcription Test Runner')
    parser.add_argument('--category', choices=['unit', 'integration', 'performance', 'all'], 
                       default='all', help='Test category to run')
    parser.add_argument('--coverage', action='store_true', default=True,
                       help='Include coverage analysis')
    parser.add_argument('--no-performance', action='store_true',
                       help='Skip performance tests')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--report', help='Output file for test report')
    parser.add_argument('--base-path', help='Base path for voice transcription module')
    
    args = parser.parse_args()
    
    # Create test runner
    runner = VoiceTranscriptionTestRunner(base_path=args.base_path)
    
    try:
        if args.category == 'all':
            results = runner.run_all_tests(
                include_coverage=args.coverage,
                include_performance=not args.no_performance,
                verbose=args.verbose
            )
        elif args.category == 'unit':
            results = {'unit': runner.run_unit_tests(args.verbose)}
        elif args.category == 'integration':
            results = {'integration': runner.run_integration_tests(args.verbose)}
        elif args.category == 'performance':
            results = {'performance': runner.run_performance_tests(args.verbose)}
            
        # Generate report if requested
        if args.report:
            runner.generate_report(args.report)
            
        # Exit with appropriate code
        total_failed = sum(r.failed_tests for r in results.values())
        sys.exit(0 if total_failed == 0 else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️  Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()