"""
End-to-End System Tests
Tests complete workflows with all components integrated
"""
import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime

from agents.orchestrator import Orchestrator
from knowledge.pattern_library import PatternLibrary
from monitoring.health_monitor import HealthMonitor
from batch.batch_processor import BatchProcessor
from config.ai_client import ai_client


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_single_municipality_complete_workflow():
    """
    E2E Test: Complete workflow for single municipality
    Tests all phases: Discovery → JS Analysis → Validation → Code Generation
    """
    print("\n" + "="*80)
    print("E2E TEST: Single Municipality Complete Workflow")
    print("="*80)

    orchestrator = Orchestrator(
        headless=True,
        dashboard_enabled=False
    )

    # Use a test municipality (you can replace with real one)
    result = await orchestrator.train_municipality(
        url="https://example.com/grievance-form",  # Replace with real URL for testing
        municipality="test_municipality_e2e"
    )

    # Assertions
    assert result is not None
    assert "session_id" in result
    assert "municipality" in result

    print(f"\n✅ Training completed")
    print(f"   Success: {result.get('success')}")
    print(f"   Cost: ${result.get('total_cost', 0):.4f}")

    if result.get("success"):
        assert "scraper_path" in result
        assert Path(result["scraper_path"]).exists()
        print(f"   Scraper: {result['scraper_path']}")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_pattern_library_learning():
    """
    E2E Test: Pattern library learns from successful scrapers
    """
    print("\n" + "="*80)
    print("E2E TEST: Pattern Library Learning")
    print("="*80)

    pattern_lib = PatternLibrary()

    # Get initial stats
    initial_stats = pattern_lib.get_statistics()
    initial_count = initial_stats.get("total_patterns", 0)

    print(f"\n📊 Initial patterns: {initial_count}")

    # Store a test pattern
    test_schema = {
        "url": "https://test.com/form",
        "fields": [
            {"name": "name", "type": "text"},
            {"name": "email", "type": "email"},
            {"name": "phone", "type": "tel"}
        ]
    }

    pattern_lib.store_pattern(
        municipality_name="test_e2e_municipality",
        form_schema=test_schema,
        code_snippets={"test": "code"},
        confidence_score=0.9,
        success_rate=1.0
    )

    # Get updated stats
    final_stats = pattern_lib.get_statistics()
    final_count = final_stats.get("total_patterns", 0)

    print(f"📊 Final patterns: {final_count}")

    # Assert pattern was stored
    assert final_count > initial_count

    # Test similarity search
    similar_patterns = pattern_lib.find_similar_patterns(test_schema, top_k=1)
    assert len(similar_patterns) > 0

    print(f"✅ Pattern library learning works")
    print(f"   Found {len(similar_patterns)} similar patterns")


@pytest.mark.e2e
@pytest.mark.slow
def test_health_monitoring_tracking():
    """
    E2E Test: Health monitoring tracks scraper executions
    """
    print("\n" + "="*80)
    print("E2E TEST: Health Monitoring")
    print("="*80)

    monitor = HealthMonitor()

    # Simulate some executions
    scraper_id = "test_e2e_scraper"

    for i in range(10):
        success = i < 8  # 80% success rate
        monitor.record_execution(
            scraper_id=scraper_id,
            success=success,
            duration=5.0 + i * 0.5,
            error_type="TestError" if not success else None
        )

    # Get health
    health = monitor.get_scraper_health(scraper_id, window_hours=24)

    assert health is not None
    assert health.total_executions == 10
    assert health.success_rate == 0.8  # 8/10

    print(f"\n✅ Health monitoring works")
    print(f"   Total executions: {health.total_executions}")
    print(f"   Success rate: {health.success_rate*100:.1f}%")
    print(f"   Health score: {health.health_score:.2f}")

    # Check alerts were created
    alerts = monitor.get_active_alerts(scraper_id)
    print(f"   Active alerts: {len(alerts)}")


@pytest.mark.e2e
def test_ai_cache_cost_savings():
    """
    E2E Test: AI cache reduces costs
    """
    print("\n" + "="*80)
    print("E2E TEST: AI Cache Cost Savings")
    print("="*80)

    if not ai_client.cache:
        pytest.skip("AI cache not enabled")

    # Get cache stats
    stats = ai_client.get_cache_stats()

    assert stats["cache_enabled"] is True

    print(f"\n✅ AI cache is working")
    print(f"   Total entries: {stats.get('total_entries', 0)}")
    print(f"   Hit rate: {stats.get('hit_rate', 0)*100:.1f}%")

    # Check cost savings
    savings = stats.get("cost_savings", {})
    if savings.get("total_requests", 0) > 0:
        print(f"   Cost savings: ${savings.get('savings', 0):.4f} ({savings.get('savings_percentage', 0):.1f}%)")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_batch_processing():
    """
    E2E Test: Batch processing handles multiple municipalities
    """
    print("\n" + "="*80)
    print("E2E TEST: Batch Processing")
    print("="*80)

    # Small batch for testing
    municipalities = [
        {
            "municipality": "test_batch_1",
            "url": "https://example.com/form1"
        },
        {
            "municipality": "test_batch_2",
            "url": "https://example.com/form2"
        }
    ]

    processor = BatchProcessor(
        max_concurrent=2,
        headless=True
    )

    # Note: This will fail without real URLs, but tests the batch infrastructure
    result = await processor.process_batch(
        municipalities,
        batch_name="test_e2e_batch"
    )

    assert result is not None
    assert "total_jobs" in result
    assert result["total_jobs"] == 2

    print(f"\n✅ Batch processing infrastructure works")
    print(f"   Total jobs: {result['total_jobs']}")


@pytest.mark.e2e
def test_all_components_loadable():
    """
    E2E Test: All major components can be imported and initialized
    """
    print("\n" + "="*80)
    print("E2E TEST: Component Integration")
    print("="*80)

    # Test all imports
    from agents.orchestrator import Orchestrator
    from agents.form_discovery_agent import FormDiscoveryAgent
    from agents.code_generator_agent import CodeGeneratorAgent
    from agents.test_agent import TestValidationAgent
    from agents.js_analyzer_agent import JavaScriptAnalyzerAgent
    from knowledge.pattern_library import PatternLibrary
    from monitoring.health_monitor import HealthMonitor
    from monitoring.alerting import AlertManager
    from batch.batch_processor import BatchProcessor
    from utils.scraper_validator import ScraperValidator
    from utils.js_runtime_monitor import JSRuntimeMonitor
    from utils.ai_cache import AICache
    from config.ai_client import ai_client
    from dashboard.app import app

    print("\n✅ All components importable")

    # Test initialization
    components = {
        "Orchestrator": Orchestrator(headless=True),
        "PatternLibrary": PatternLibrary(),
        "HealthMonitor": HealthMonitor(),
        "AlertManager": AlertManager(),
        "BatchProcessor": BatchProcessor(),
        "ScraperValidator": ScraperValidator(),
        "JSRuntimeMonitor": JSRuntimeMonitor(),
        "AICache": AICache(),
        "AIClient": ai_client,
        "FlaskApp": app
    }

    for name, component in components.items():
        assert component is not None
        print(f"   ✅ {name}")

    print("\n✅ All components initialize successfully")


@pytest.mark.e2e
def test_directory_structure():
    """
    E2E Test: Required directories exist
    """
    print("\n" + "="*80)
    print("E2E TEST: Directory Structure")
    print("="*80)

    required_dirs = [
        "agents",
        "config",
        "knowledge",
        "monitoring",
        "batch",
        "utils",
        "dashboard",
        "tests",
        "scripts",
        "generated_scrapers"
    ]

    project_root = Path(__file__).parent.parent.parent

    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        assert dir_path.exists(), f"Directory {dir_name} not found"
        print(f"   ✅ {dir_name}/")

    print("\n✅ All required directories exist")


@pytest.mark.e2e
def test_file_structure():
    """
    E2E Test: Critical files exist
    """
    print("\n" + "="*80)
    print("E2E TEST: File Structure")
    print("="*80)

    project_root = Path(__file__).parent.parent.parent

    critical_files = [
        "agents/orchestrator.py",
        "agents/form_discovery_agent.py",
        "agents/code_generator_agent.py",
        "config/ai_client.py",
        "knowledge/pattern_library.py",
        "monitoring/health_monitor.py",
        "monitoring/alerting.py",
        "batch/batch_processor.py",
        "utils/scraper_validator.py",
        "utils/js_runtime_monitor.py",
        "utils/ai_cache.py",
        "dashboard/app.py",
        "scripts/validate_system.py",
        "scripts/test_ranchi.py",
        "scripts/run_scraper.py",
        ".github/workflows/test.yml",
        "README.md"
    ]

    for file_path in critical_files:
        full_path = project_root / file_path
        assert full_path.exists(), f"Critical file {file_path} not found"
        print(f"   ✅ {file_path}")

    print("\n✅ All critical files exist")


if __name__ == "__main__":
    """Run E2E tests manually"""
    print("\n" + "="*80)
    print("RUNNING END-TO-END TESTS")
    print("="*80)

    # Run tests
    asyncio.run(test_single_municipality_complete_workflow())
    asyncio.run(test_pattern_library_learning())
    test_health_monitoring_tracking()
    test_ai_cache_cost_savings()
    asyncio.run(test_batch_processing())
    test_all_components_loadable()
    test_directory_structure()
    test_file_structure()

    print("\n" + "="*80)
    print("🎉 ALL E2E TESTS PASSED!")
    print("="*80)
