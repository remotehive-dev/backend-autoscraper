#!/usr/bin/env python3
"""
ML Integration Test Runner

This script runs all ML-related tests and generates a comprehensive report
showing the status of each ML component integration.
"""

import subprocess
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path


class MLTestRunner:
    """Test runner for ML integration components"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        
        # Define all ML-related test files
        self.ml_test_files = [
            "backend/services/test_gemini_client.py",
            "backend/services/test_ml_parsing_service.py", 
            "backend/services/test_enhanced_scraper_manager.py",
            "backend/services/test_job_data_validator.py",
            "backend/services/test_ml_config_service.py",
            "backend/services/test_scraper_integration.py"
        ]
        
        # Test categories for reporting
        self.test_categories = {
            "Core ML Components": [
                "test_gemini_client.py",
                "test_ml_parsing_service.py"
            ],
            "Enhanced Scraping": [
                "test_enhanced_scraper_manager.py",
                "test_scraper_integration.py"
            ],
            "Data Validation & Quality": [
                "test_job_data_validator.py"
            ],
            "Configuration Management": [
                "test_ml_config_service.py"
            ]
        }
    
    def run_single_test(self, test_file: str) -> Dict[str, Any]:
        """Run a single test file and return results"""
        print(f"\n🧪 Running {test_file}...")
        
        try:
            # Run pytest with verbose output and JSON report
            cmd = [
                "python", "-m", "pytest", 
                test_file, 
                "-v", 
                "--tb=short",
                "--disable-warnings"
            ]
            
            start_time = time.time()
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=120  # 2 minute timeout per test file
            )
            end_time = time.time()
            
            # Parse test results
            test_result = {
                "file": test_file,
                "status": "PASSED" if result.returncode == 0 else "FAILED",
                "duration": round(end_time - start_time, 2),
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "test_count": self._extract_test_count(result.stdout),
                "warnings": self._extract_warnings(result.stdout)
            }
            
            # Print immediate feedback
            if test_result["status"] == "PASSED":
                print(f"✅ {test_file} - {test_result['test_count']} tests passed in {test_result['duration']}s")
            else:
                print(f"❌ {test_file} - FAILED (return code: {result.returncode})")
                if result.stderr:
                    print(f"   Error: {result.stderr[:200]}...")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_file} - TIMEOUT (exceeded 2 minutes)")
            return {
                "file": test_file,
                "status": "TIMEOUT",
                "duration": 120,
                "return_code": -1,
                "stdout": "",
                "stderr": "Test execution timed out",
                "test_count": "Unknown",
                "warnings": []
            }
        except Exception as e:
            print(f"💥 {test_file} - ERROR: {str(e)}")
            return {
                "file": test_file,
                "status": "ERROR",
                "duration": 0,
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "test_count": "Unknown",
                "warnings": []
            }
    
    def _extract_test_count(self, stdout: str) -> str:
        """Extract test count from pytest output"""
        try:
            lines = stdout.split('\n')
            for line in reversed(lines):
                if 'passed' in line and ('warning' in line or 'failed' in line or line.strip().endswith('passed')):
                    return line.strip().split('=')[-1].strip()
            return "Unknown"
        except:
            return "Unknown"
    
    def _extract_warnings(self, stdout: str) -> List[str]:
        """Extract warnings from pytest output"""
        warnings = []
        try:
            lines = stdout.split('\n')
            for line in lines:
                if 'warning' in line.lower() and ('deprecation' in line.lower() or 'moved' in line.lower()):
                    warnings.append(line.strip())
        except:
            pass
        return warnings[:5]  # Limit to first 5 warnings
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all ML integration tests"""
        print("🚀 Starting ML Integration Test Suite")
        print("=" * 50)
        
        self.start_time = datetime.now()
        
        # Run each test file
        for test_file in self.ml_test_files:
            result = self.run_single_test(test_file)
            self.test_results[test_file] = result
        
        self.end_time = datetime.now()
        
        return self.generate_report()
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_duration = (self.end_time - self.start_time).total_seconds()
        
        # Calculate summary statistics
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results.values() if r['status'] == 'PASSED')
        failed_tests = sum(1 for r in self.test_results.values() if r['status'] == 'FAILED')
        error_tests = sum(1 for r in self.test_results.values() if r['status'] in ['ERROR', 'TIMEOUT'])
        
        # Generate report
        report = {
            "summary": {
                "total_test_files": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "success_rate": round((passed_tests / total_tests) * 100, 1) if total_tests > 0 else 0,
                "total_duration": round(total_duration, 2),
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat()
            },
            "test_results": self.test_results,
            "category_results": self._generate_category_results(),
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_category_results(self) -> Dict[str, Any]:
        """Generate results by test category"""
        category_results = {}
        
        for category, test_files in self.test_categories.items():
            category_tests = []
            for test_file in test_files:
                full_path = f"backend/services/{test_file}"
                if full_path in self.test_results:
                    category_tests.append(self.test_results[full_path])
            
            if category_tests:
                passed = sum(1 for t in category_tests if t['status'] == 'PASSED')
                total = len(category_tests)
                
                category_results[category] = {
                    "total_files": total,
                    "passed": passed,
                    "failed": total - passed,
                    "success_rate": round((passed / total) * 100, 1) if total > 0 else 0,
                    "status": "HEALTHY" if passed == total else "ISSUES" if passed > 0 else "CRITICAL"
                }
        
        return category_results
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check for failed tests
        failed_tests = [r for r in self.test_results.values() if r['status'] != 'PASSED']
        if failed_tests:
            recommendations.append(f"🔧 Fix {len(failed_tests)} failing test file(s) before deployment")
        
        # Check for warnings
        warning_count = sum(len(r.get('warnings', [])) for r in self.test_results.values())
        if warning_count > 10:
            recommendations.append(f"⚠️  Address {warning_count} deprecation warnings for future compatibility")
        
        # Check performance
        slow_tests = [r for r in self.test_results.values() if r.get('duration', 0) > 30]
        if slow_tests:
            recommendations.append(f"🐌 Optimize {len(slow_tests)} slow-running test file(s)")
        
        # Overall health check
        success_rate = self.test_results and (sum(1 for r in self.test_results.values() if r['status'] == 'PASSED') / len(self.test_results)) * 100
        if success_rate == 100:
            recommendations.append("✅ All ML components are functioning correctly")
        elif success_rate >= 80:
            recommendations.append("⚡ ML integration is mostly stable with minor issues")
        else:
            recommendations.append("🚨 ML integration requires immediate attention")
        
        return recommendations
    
    def print_report(self, report: Dict[str, Any]):
        """Print formatted test report"""
        print("\n" + "=" * 60)
        print("🧪 ML INTEGRATION TEST REPORT")
        print("=" * 60)
        
        # Summary
        summary = report['summary']
        print(f"\n📊 SUMMARY:")
        print(f"   Total Test Files: {summary['total_test_files']}")
        print(f"   Passed: {summary['passed']} ✅")
        print(f"   Failed: {summary['failed']} ❌")
        print(f"   Errors: {summary['errors']} 💥")
        print(f"   Success Rate: {summary['success_rate']}%")
        print(f"   Total Duration: {summary['total_duration']}s")
        
        # Category Results
        print(f"\n📋 CATEGORY RESULTS:")
        for category, results in report['category_results'].items():
            status_emoji = "✅" if results['status'] == 'HEALTHY' else "⚠️" if results['status'] == 'ISSUES' else "🚨"
            print(f"   {status_emoji} {category}: {results['passed']}/{results['total_files']} ({results['success_rate']}%)")
        
        # Individual Test Results
        print(f"\n📝 DETAILED RESULTS:")
        for test_file, result in report['test_results'].items():
            status_emoji = "✅" if result['status'] == 'PASSED' else "❌"
            test_name = test_file.split('/')[-1]
            print(f"   {status_emoji} {test_name}: {result['test_count']} ({result['duration']}s)")
            
            if result['status'] != 'PASSED' and result['stderr']:
                print(f"      Error: {result['stderr'][:100]}...")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        for rec in report['recommendations']:
            print(f"   {rec}")
        
        print("\n" + "=" * 60)
    
    def save_report(self, report: Dict[str, Any], filename: str = "ml_test_report.json"):
        """Save report to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"\n💾 Report saved to {filename}")
        except Exception as e:
            print(f"\n❌ Failed to save report: {e}")


def main():
    """Main function to run ML integration tests"""
    runner = MLTestRunner()
    
    try:
        # Run all tests
        report = runner.run_all_tests()
        
        # Print and save report
        runner.print_report(report)
        runner.save_report(report)
        
        # Exit with appropriate code
        if report['summary']['failed'] > 0 or report['summary']['errors'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n💥 Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()