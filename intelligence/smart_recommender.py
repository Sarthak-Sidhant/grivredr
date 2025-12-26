"""
Smart Recommender - Suggest optimizations and patterns
Provides intelligent recommendations for form training and scraper improvement
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from knowledge.pattern_library import PatternLibrary
from intelligence.form_clustering import FormClusterer
from monitoring.health_monitor import HealthMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """A single recommendation"""
    type: str  # clone, modify, retrain, optimize
    priority: str  # high, medium, low
    municipality: str
    confidence: float
    action: str
    reason: str
    details: Dict[str, Any]


class SmartRecommender:
    """
    Provide intelligent recommendations for scraper training and optimization
    """

    def __init__(self):
        self.pattern_library = PatternLibrary()
        self.form_clusterer = FormClusterer()
        self.health_monitor = HealthMonitor()

    def recommend_for_new_form(
        self,
        form_schema: Dict[str, Any],
        municipality: str
    ) -> List[Recommendation]:
        """
        Get recommendations for training a new municipality

        Returns:
            List of recommendations (clone, modify, train from scratch)
        """
        recommendations = []

        # Find similar patterns
        similar_patterns = self.pattern_library.find_similar_patterns(
            form_schema,
            top_k=3
        )

        if similar_patterns:
            # Get most similar
            similarity, best_pattern = similar_patterns[0]

            if similarity >= 0.95:
                # Very similar - recommend cloning
                recommendations.append(Recommendation(
                    type="clone",
                    priority="high",
                    municipality=municipality,
                    confidence=similarity,
                    action=f"Clone scraper from '{best_pattern.municipality_name}'",
                    reason=f"{similarity*100:.0f}% similarity - minimal changes needed",
                    details={
                        "source_municipality": best_pattern.municipality_name,
                        "similarity": similarity,
                        "confidence_score": best_pattern.confidence_score,
                        "success_rate": best_pattern.success_rate,
                        "estimated_time": "5-10 minutes",
                        "estimated_cost": "$0.10-0.20"
                    }
                ))

            elif similarity >= 0.80:
                # Similar - recommend modifying
                recommendations.append(Recommendation(
                    type="modify",
                    priority="medium",
                    municipality=municipality,
                    confidence=similarity,
                    action=f"Use '{best_pattern.municipality_name}' as template and modify",
                    reason=f"{similarity*100:.0f}% similarity - some customization needed",
                    details={
                        "source_municipality": best_pattern.municipality_name,
                        "similarity": similarity,
                        "modifications_needed": self._identify_modifications(form_schema, best_pattern),
                        "estimated_time": "10-15 minutes",
                        "estimated_cost": "$0.30-0.50"
                    }
                ))

            else:
                # Somewhat similar - can use patterns but need new training
                recommendations.append(Recommendation(
                    type="train_with_hints",
                    priority="medium",
                    municipality=municipality,
                    confidence=similarity,
                    action=f"Train from scratch using patterns from '{best_pattern.municipality_name}'",
                    reason=f"{similarity*100:.0f}% similarity - use as reference",
                    details={
                        "reference_municipality": best_pattern.municipality_name,
                        "similarity": similarity,
                        "reusable_patterns": self._extract_reusable_patterns(best_pattern),
                        "estimated_time": "15-20 minutes",
                        "estimated_cost": "$0.50-0.80"
                    }
                ))

        else:
            # No similar patterns - train from scratch
            recommendations.append(Recommendation(
                type="train_from_scratch",
                priority="low",
                municipality=municipality,
                confidence=0.0,
                action="Train from scratch - no similar patterns found",
                reason="First time seeing this form structure",
                details={
                    "estimated_time": "20-30 minutes",
                    "estimated_cost": "$0.80-1.20"
                }
            ))

        return recommendations

    def _identify_modifications(
        self,
        target_schema: Dict[str, Any],
        source_pattern
    ) -> List[str]:
        """Identify what needs to be modified"""
        modifications = []

        target_fields = target_schema.get("fields", [])
        source_field_types = set(f.get("type") for f in source_pattern.field_types)
        target_field_types = set(f.get("type") for f in target_fields)

        # Field type differences
        new_types = target_field_types - source_field_types
        if new_types:
            modifications.append(f"Add support for: {', '.join(new_types)}")

        removed_types = source_field_types - target_field_types
        if removed_types:
            modifications.append(f"Remove: {', '.join(removed_types)}")

        # CAPTCHA
        if target_schema.get("captcha_present") and not source_pattern.form_schema.get("captcha_present"):
            modifications.append("Add CAPTCHA handling")

        # Multi-step
        if target_schema.get("multi_step") and not source_pattern.form_schema.get("multi_step"):
            modifications.append("Add multi-step navigation")

        return modifications

    def _extract_reusable_patterns(self, pattern) -> List[str]:
        """Extract patterns that can be reused"""
        reusable = []

        if pattern.code_snippets:
            if "selector_fallbacks" in pattern.code_snippets:
                reusable.append("Selector fallback strategy")
            if "error_handling" in pattern.code_snippets:
                reusable.append("Error handling patterns")
            if "wait_strategies" in pattern.code_snippets:
                reusable.append("Wait/timing strategies")

        return reusable

    def recommend_optimizations(
        self,
        scraper_id: str
    ) -> List[Recommendation]:
        """
        Recommend optimizations for an existing scraper

        Based on:
        - Health metrics
        - Performance data
        - Error patterns
        """
        recommendations = []

        # Get health
        health = self.health_monitor.get_scraper_health(scraper_id, window_hours=24*7)  # 1 week

        if not health:
            return [Recommendation(
                type="info",
                priority="low",
                municipality=scraper_id,
                confidence=0.0,
                action="No health data available",
                reason="Need at least 5 executions to provide recommendations",
                details={}
            )]

        # Check success rate
        if health.success_rate < 0.85:
            recommendations.append(Recommendation(
                type="retrain",
                priority="high",
                municipality=scraper_id,
                confidence=1.0 - health.success_rate,
                action=f"Retrain scraper (current success rate: {health.success_rate*100:.1f}%)",
                reason="Success rate below 85% threshold",
                details={
                    "current_success_rate": health.success_rate,
                    "consecutive_failures": health.consecutive_failures,
                    "total_executions": health.total_executions
                }
            ))

        # Check duration
        if health.avg_duration > 30:
            recommendations.append(Recommendation(
                type="optimize",
                priority="medium",
                municipality=scraper_id,
                confidence=min(health.avg_duration / 60, 1.0),
                action=f"Optimize for speed (current avg: {health.avg_duration:.1f}s)",
                reason="Execution time exceeds 30 seconds",
                details={
                    "current_avg_duration": health.avg_duration,
                    "target_duration": 20.0,
                    "optimization_suggestions": [
                        "Reduce explicit waits",
                        "Use faster selectors",
                        "Remove unnecessary screenshots"
                    ]
                }
            ))

        # Check for consecutive failures
        if health.consecutive_failures >= 3:
            recommendations.append(Recommendation(
                type="urgent_retrain",
                priority="high",
                municipality=scraper_id,
                confidence=1.0,
                action=f"URGENT: {health.consecutive_failures} consecutive failures detected",
                reason="Scraper is currently broken",
                details={
                    "consecutive_failures": health.consecutive_failures,
                    "action_required": "Immediate attention required"
                }
            ))

        # If healthy, suggest proactive maintenance
        if health.success_rate >= 0.95 and health.health_score >= 0.9:
            recommendations.append(Recommendation(
                type="maintenance",
                priority="low",
                municipality=scraper_id,
                confidence=health.health_score,
                action="Scraper is healthy - no immediate action needed",
                reason=f"Success rate: {health.success_rate*100:.1f}%, Health score: {health.health_score:.2f}",
                details={
                    "next_maintenance": "Consider testing after 3 months or 100 executions",
                    "health_score": health.health_score
                }
            ))

        return recommendations

    def recommend_batch_strategy(
        self,
        municipalities: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Recommend optimal batch training strategy

        Returns:
            Strategy with training order, estimated time, and cost
        """
        # Cluster forms
        clusters = self.form_clusterer.cluster_forms(municipalities, similarity_threshold=0.75)

        # Get training order
        training_order = self.form_clusterer.suggest_training_order(municipalities)

        # Calculate estimates
        total_munis = len(municipalities)
        representatives = sum(1 for t in training_order if t.get("role") == "representative")
        similar = sum(1 for t in training_order if t.get("role") == "similar")
        outliers = sum(1 for t in training_order if t.get("role") == "outlier")

        # Time estimates (minutes)
        representative_time = representatives * 20
        similar_time = similar * 8  # 60% faster with patterns
        outlier_time = outliers * 20

        total_time = representative_time + similar_time + outlier_time
        sequential_time = total_munis * 20  # Without clustering

        # Cost estimates
        representative_cost = representatives * 0.80
        similar_cost = similar * 0.32  # 60% cheaper
        outlier_cost = outliers * 0.80

        total_cost = representative_cost + similar_cost + outlier_cost
        sequential_cost = total_munis * 0.80  # Without clustering

        strategy = {
            "total_municipalities": total_munis,
            "clusters_found": len(clusters),
            "phases": {
                "phase_1_representatives": {
                    "count": representatives,
                    "estimated_time_minutes": representative_time,
                    "estimated_cost": representative_cost,
                    "priority": "Train these first"
                },
                "phase_2_similar": {
                    "count": similar,
                    "estimated_time_minutes": similar_time,
                    "estimated_cost": similar_cost,
                    "priority": "Clone and customize"
                },
                "phase_3_outliers": {
                    "count": outliers,
                    "estimated_time_minutes": outlier_time,
                    "estimated_cost": outlier_cost,
                    "priority": "Train from scratch"
                }
            },
            "totals": {
                "estimated_time_minutes": total_time,
                "estimated_time_hours": total_time / 60,
                "estimated_cost": total_cost
            },
            "savings": {
                "time_saved_minutes": sequential_time - total_time,
                "time_saved_percentage": ((sequential_time - total_time) / sequential_time) * 100,
                "cost_saved": sequential_cost - total_cost,
                "cost_saved_percentage": ((sequential_cost - total_cost) / sequential_cost) * 100
            },
            "training_order": training_order,
            "recommendation": self._generate_batch_recommendation(
                total_munis, len(clusters), representatives, similar, outliers
            )
        }

        return strategy

    def _generate_batch_recommendation(
        self,
        total: int,
        clusters: int,
        reps: int,
        similar: int,
        outliers: int
    ) -> str:
        """Generate human-readable recommendation"""
        if clusters == 0:
            return f"No clusters found among {total} municipalities. Train sequentially."

        if similar == 0:
            return f"Found {clusters} small clusters. Limited pattern reuse available."

        savings_potential = (similar / total) * 100

        if savings_potential >= 50:
            return (
                f"🎯 HIGH OPTIMIZATION POTENTIAL: {clusters} clusters with {similar} similar forms ({savings_potential:.0f}%). "
                f"Train {reps} representatives first, then rapidly deploy to similar forms. "
                f"Estimated time savings: 40-60%."
            )
        elif savings_potential >= 25:
            return (
                f"✅ GOOD OPTIMIZATION POTENTIAL: {clusters} clusters with {similar} similar forms ({savings_potential:.0f}%). "
                f"Training representatives first will save significant time."
            )
        else:
            return (
                f"📊 MODERATE OPTIMIZATION: {clusters} clusters found. "
                f"Some pattern reuse possible but most forms need individual training."
            )


# For testing
if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING SMART RECOMMENDER")
    print("="*80)

    recommender = SmartRecommender()

    # Test: Recommend for new form
    print("\n📋 Recommendations for new form:")

    new_form = {
        "fields": [
            {"type": "text", "required": True},
            {"type": "email", "required": True},
            {"type": "tel", "required": True},
            {"type": "textarea", "required": True},
        ],
        "captcha_present": False,
        "multi_step": False
    }

    recommendations = recommender.recommend_for_new_form(new_form, "bangalore")

    for rec in recommendations:
        print(f"\n   {rec.priority.upper()}: {rec.action}")
        print(f"   Reason: {rec.reason}")
        print(f"   Confidence: {rec.confidence*100:.0f}%")
        if rec.details:
            for key, value in rec.details.items():
                print(f"      {key}: {value}")

    # Test: Batch strategy
    print("\n" + "="*80)
    print("BATCH TRAINING STRATEGY")
    print("="*80)

    municipalities = {
        f"city_{i}": {
            "fields": [
                {"type": "text"}, {"type": "email"}, {"type": "tel"}, {"type": "textarea"}
            ] + ([{"type": "select"}] if i % 3 == 0 else []),
            "captcha_present": i % 5 == 0,
            "multi_step": False
        }
        for i in range(20)
    }

    strategy = recommender.recommend_batch_strategy(municipalities)

    print(f"\n📊 Total Municipalities: {strategy['total_municipalities']}")
    print(f"🔍 Clusters Found: {strategy['clusters_found']}")

    print(f"\n💰 Cost Estimate:")
    print(f"   With clustering: ${strategy['totals']['estimated_cost']:.2f}")
    print(f"   Savings: ${strategy['savings']['cost_saved']:.2f} ({strategy['savings']['cost_saved_percentage']:.0f}%)")

    print(f"\n⏱️  Time Estimate:")
    print(f"   With clustering: {strategy['totals']['estimated_time_hours']:.1f} hours")
    print(f"   Savings: {strategy['savings']['time_saved_minutes']:.0f} minutes ({strategy['savings']['time_saved_percentage']:.0f}%)")

    print(f"\n💡 Recommendation:")
    print(f"   {strategy['recommendation']}")

    print("\n" + "="*80)
