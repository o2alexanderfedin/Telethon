"""
Test Coverage Configuration and Monitoring

This module implements test coverage monitoring for Epic 1 User Story 1.8: Basic Testing Infrastructure
providing automated coverage tracking, reporting, and validation for the voice transcription system.

Features:
- Automated coverage collection during test runs
- HTML and terminal coverage reporting
- Coverage threshold validation (>90% requirement)
- Module-specific coverage tracking
- CI/CD integration support
- Coverage trend monitoring
"""

import coverage
import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import subprocess


class CoverageConfig:
    """Coverage configuration for voice transcription testing"""
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path(__file__).parent
        
        # Coverage settings
        self.source_packages = ['voice_transcription']
        self.omit_patterns = [
            '*/test*',
            '*/tests/*', 
            '*/__pycache__/*',
            '*/.*',
            '*/venv/*',
            '*/site-packages/*'
        ]
        
        # Coverage thresholds
        self.minimum_coverage = 90.0  # Epic 1 requirement
        self.module_thresholds = {
            'basic_request': 95.0,
            'transcription_manager': 95.0,
            'state_manager': 95.0,
            'error_handling': 95.0,
            'update_handler': 90.0,
            'automatic_cleanup': 90.0,
            'validation': 85.0,
            'response_parser': 85.0,
            'integration': 80.0
        }
        
        # Report settings
        self.html_dir = self.base_path / 'coverage_html'
        self.json_file = self.base_path / 'coverage.json'
        self.txt_file = self.base_path / 'coverage.txt'
        
    def get_coverage_instance(self) -> coverage.Coverage:
        """Create configured coverage instance"""
        return coverage.Coverage(
            source=self.source_packages,
            omit=self.omit_patterns,
            config_file=False,  # Use programmatic configuration
            data_suffix=True    # Handle concurrent execution
        )


class CoverageMonitor:
    """Coverage monitoring and reporting system"""
    
    def __init__(self, config: Optional[CoverageConfig] = None):
        self.config = config or CoverageConfig()
        self.coverage_data = None
        self.results = {}
        
    def start_coverage(self) -> coverage.Coverage:
        """Start coverage monitoring"""
        self.coverage_data = self.config.get_coverage_instance()
        self.coverage_data.start()
        return self.coverage_data
        
    def stop_coverage(self) -> Dict[str, Any]:
        """Stop coverage and generate reports"""
        if not self.coverage_data:
            raise ValueError("Coverage not started")
            
        self.coverage_data.stop()
        self.coverage_data.save()
        
        # Generate all reports
        results = {
            'console_report': self._generate_console_report(),
            'html_report': self._generate_html_report(),
            'json_report': self._generate_json_report(),
            'validation': self._validate_coverage_thresholds()
        }
        
        self.results = results
        return results
        
    def _generate_console_report(self) -> Dict[str, Any]:
        """Generate console coverage report"""
        try:
            # Capture stdout for parsing
            import io
            from contextlib import redirect_stdout
            
            output = io.StringIO()
            with redirect_stdout(output):
                total_coverage = self.coverage_data.report(
                    show_missing=True,
                    skip_covered=False
                )
            
            report_text = output.getvalue()
            
            # Save text report
            with open(self.config.txt_file, 'w') as f:
                f.write(report_text)
                
            return {
                'total_coverage': total_coverage,
                'report_text': report_text,
                'report_file': str(self.config.txt_file)
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'total_coverage': 0.0
            }
            
    def _generate_html_report(self) -> Dict[str, Any]:
        """Generate HTML coverage report"""
        try:
            # Ensure output directory exists
            self.config.html_dir.mkdir(exist_ok=True)
            
            # Generate HTML report
            total_coverage = self.coverage_data.html_report(
                directory=str(self.config.html_dir),
                title="Voice Transcription Coverage Report"
            )
            
            index_file = self.config.html_dir / 'index.html'
            
            return {
                'total_coverage': total_coverage,
                'html_dir': str(self.config.html_dir),
                'index_file': str(index_file),
                'success': index_file.exists()
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'total_coverage': 0.0,
                'success': False
            }
            
    def _generate_json_report(self) -> Dict[str, Any]:
        """Generate JSON coverage report"""
        try:
            # Generate JSON data
            json_data = {}
            self.coverage_data.get_data().write_file(str(self.config.json_file))
            
            # Create summary JSON
            summary = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_coverage': 0.0,
                'modules': {},
                'files': {},
                'thresholds': self.config.module_thresholds,
                'minimum_threshold': self.config.minimum_coverage
            }
            
            # Get detailed file coverage
            analysis_data = self.coverage_data.get_data()
            for filename in analysis_data.measured_files():
                try:
                    file_coverage = self.coverage_data.analysis2(filename)
                    module_name = self._extract_module_name(filename)
                    
                    file_info = {
                        'filename': filename,
                        'module': module_name,
                        'statements': len(file_coverage.statements),
                        'missing': len(file_coverage.missing),
                        'excluded': len(file_coverage.excluded),
                        'coverage_percent': file_coverage.pc_covered
                    }
                    
                    summary['files'][filename] = file_info
                    
                    # Aggregate by module
                    if module_name not in summary['modules']:
                        summary['modules'][module_name] = {
                            'statements': 0,
                            'missing': 0,
                            'excluded': 0,
                            'files': []
                        }
                    
                    mod_data = summary['modules'][module_name]
                    mod_data['statements'] += file_info['statements']
                    mod_data['missing'] += file_info['missing']
                    mod_data['excluded'] += file_info['excluded']
                    mod_data['files'].append(filename)
                    
                except Exception as e:
                    print(f"Error analyzing {filename}: {e}")
                    
            # Calculate module coverage percentages
            for module_name, mod_data in summary['modules'].items():
                if mod_data['statements'] > 0:
                    covered = mod_data['statements'] - mod_data['missing']
                    mod_data['coverage_percent'] = (covered / mod_data['statements']) * 100
                else:
                    mod_data['coverage_percent'] = 100.0
                    
            # Calculate total coverage
            total_statements = sum(m['statements'] for m in summary['modules'].values())
            total_missing = sum(m['missing'] for m in summary['modules'].values())
            
            if total_statements > 0:
                summary['total_coverage'] = ((total_statements - total_missing) / total_statements) * 100
            
            # Save JSON summary
            summary_file = self.config.base_path / 'coverage_summary.json'
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
                
            return {
                'summary': summary,
                'json_file': str(self.config.json_file),
                'summary_file': str(summary_file),
                'success': True
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'success': False
            }
            
    def _extract_module_name(self, filename: str) -> str:
        """Extract module name from filename"""
        path = Path(filename)
        
        # Remove .py extension
        name = path.stem
        
        # Handle special cases
        if name == '__init__':
            return path.parent.name
        elif name.startswith('test_'):
            return name[5:]  # Remove 'test_' prefix
        else:
            return name
            
    def _validate_coverage_thresholds(self) -> Dict[str, Any]:
        """Validate coverage against thresholds"""
        if 'json_report' not in self.results:
            return {'error': 'JSON report not available for validation'}
            
        json_data = self.results['json_report']
        if not json_data.get('success'):
            return {'error': 'JSON report generation failed'}
            
        summary = json_data['summary']
        validation = {
            'overall_pass': summary['total_coverage'] >= self.config.minimum_coverage,
            'total_coverage': summary['total_coverage'],
            'minimum_required': self.config.minimum_coverage,
            'module_results': {},
            'failures': []
        }
        
        # Validate module thresholds
        for module_name, threshold in self.config.module_thresholds.items():
            if module_name in summary['modules']:
                module_coverage = summary['modules'][module_name]['coverage_percent']
                module_pass = module_coverage >= threshold
                
                validation['module_results'][module_name] = {
                    'coverage': module_coverage,
                    'threshold': threshold,
                    'pass': module_pass
                }
                
                if not module_pass:
                    validation['failures'].append({
                        'module': module_name,
                        'coverage': module_coverage,
                        'required': threshold,
                        'deficit': threshold - module_coverage
                    })
            else:
                validation['module_results'][module_name] = {
                    'coverage': 0.0,
                    'threshold': threshold,
                    'pass': False,
                    'error': 'Module not found'
                }
                
                validation['failures'].append({
                    'module': module_name,
                    'coverage': 0.0,
                    'required': threshold,
                    'error': 'Module not found'
                })
        
        validation['all_modules_pass'] = len(validation['failures']) == 0
        validation['success'] = validation['overall_pass'] and validation['all_modules_pass']
        
        return validation
        
    def print_coverage_summary(self):
        """Print formatted coverage summary"""
        if not self.results:
            print("❌ No coverage results available")
            return
            
        print("\n📊 Voice Transcription Coverage Summary")
        print("=" * 50)
        
        # Overall coverage
        if 'json_report' in self.results and self.results['json_report'].get('success'):
            summary = self.results['json_report']['summary']
            total_coverage = summary['total_coverage']
            
            status = "✅" if total_coverage >= self.config.minimum_coverage else "❌"
            print(f"{status} Overall Coverage: {total_coverage:.1f}% (required: {self.config.minimum_coverage:.1f}%)")
            
            # Module breakdown
            print(f"\n📋 Module Coverage:")
            for module_name, mod_data in summary['modules'].items():
                threshold = self.config.module_thresholds.get(module_name, 0)
                module_coverage = mod_data['coverage_percent']
                status = "✅" if module_coverage >= threshold else "❌"
                
                print(f"   {status} {module_name}: {module_coverage:.1f}% "
                      f"({mod_data['statements']} statements, {mod_data['missing']} missing)")
                      
        # Validation results
        if 'validation' in self.results:
            validation = self.results['validation']
            
            if validation.get('success'):
                print(f"\n🎉 All coverage thresholds met!")
            else:
                print(f"\n⚠️  Coverage validation failed:")
                for failure in validation.get('failures', []):
                    if 'error' in failure:
                        print(f"   ❌ {failure['module']}: {failure['error']}")
                    else:
                        print(f"   ❌ {failure['module']}: {failure['coverage']:.1f}% "
                              f"(need {failure['required']:.1f}%, deficit: {failure['deficit']:.1f}%)")
                              
        # Report locations
        print(f"\n📄 Coverage Reports:")
        if 'html_report' in self.results and self.results['html_report'].get('success'):
            print(f"   HTML: {self.results['html_report']['index_file']}")
        if 'console_report' in self.results:
            print(f"   Text: {self.results['console_report'].get('report_file', 'console only')}")
        if 'json_report' in self.results and self.results['json_report'].get('success'):
            print(f"   JSON: {self.results['json_report']['summary_file']}")


def run_coverage_analysis(test_pattern: str = "test_*.py") -> Dict[str, Any]:
    """Run coverage analysis for specified test pattern"""
    config = CoverageConfig()
    monitor = CoverageMonitor(config)
    
    print(f"🔍 Starting coverage analysis for pattern: {test_pattern}")
    print(f"📂 Base path: {config.base_path}")
    
    try:
        # Start coverage
        cov = monitor.start_coverage()
        
        # Run tests with coverage
        import pytest
        pytest_args = [
            str(config.base_path),
            '-k', test_pattern,
            '--tb=short',
            '-v'
        ]
        
        exit_code = pytest.main(pytest_args)
        
        # Stop coverage and generate reports
        results = monitor.stop_coverage()
        
        # Print summary
        monitor.print_coverage_summary()
        
        # Return results with test exit code
        results['test_exit_code'] = exit_code
        results['test_success'] = exit_code == 0
        
        return results
        
    except Exception as e:
        print(f"❌ Coverage analysis failed: {e}")
        return {'error': str(e), 'success': False}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Voice Transcription Coverage Analysis')
    parser.add_argument('--pattern', default='test_*.py', 
                       help='Test file pattern to run (default: test_*.py)')
    parser.add_argument('--html-only', action='store_true',
                       help='Generate only HTML report')
    parser.add_argument('--validate-only', action='store_true', 
                       help='Only validate existing coverage data')
    
    args = parser.parse_args()
    
    if args.validate_only:
        # Validate existing coverage
        config = CoverageConfig()
        monitor = CoverageMonitor(config)
        
        # Load existing coverage data
        try:
            cov = config.get_coverage_instance()
            cov.load()
            monitor.coverage_data = cov
            results = {
                'json_report': monitor._generate_json_report(),
                'validation': monitor._validate_coverage_thresholds()
            }
            monitor.results = results
            monitor.print_coverage_summary()
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            sys.exit(1)
    else:
        # Run full coverage analysis
        results = run_coverage_analysis(args.pattern)
        
        if not results.get('success', False):
            sys.exit(1)
        elif not results.get('test_success', False):
            print("⚠️  Tests failed but coverage was collected")
            sys.exit(2)