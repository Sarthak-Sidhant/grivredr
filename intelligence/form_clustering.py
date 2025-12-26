"""
Form Clustering - Automatically group similar forms using ML
Groups municipalities with similar form structures to optimize training
"""
import numpy as np
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter
from dataclasses import dataclass
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FormCluster:
    """Represents a cluster of similar forms"""
    cluster_id: int
    centroid: Dict[str, Any]
    municipalities: List[str]
    similarity_score: float
    representative_form: Optional[str] = None


class FormClusterer:
    """
    Cluster forms based on structure similarity
    Uses field types, counts, and patterns to group similar forms
    """

    def __init__(self):
        self.clusters: List[FormCluster] = []
        self.form_vectors: Dict[str, np.ndarray] = {}

    def vectorize_form(self, form_schema: Dict[str, Any]) -> np.ndarray:
        """
        Convert form schema to feature vector

        Features:
        - Field type counts (text, email, tel, select, file, etc.)
        - Total fields
        - Required fields ratio
        - Has captcha
        - Has multi-step
        - Has file upload
        - Has cascading dropdowns
        """
        fields = form_schema.get("fields", [])

        # Count field types
        field_types = Counter([f.get("type", "unknown") for f in fields])

        # Create feature vector
        features = [
            len(fields),                                    # Total fields
            sum(1 for f in fields if f.get("required")),   # Required fields
            field_types.get("text", 0),                    # Text inputs
            field_types.get("email", 0),                   # Email inputs
            field_types.get("tel", 0),                     # Phone inputs
            field_types.get("number", 0),                  # Number inputs
            field_types.get("select", 0),                  # Dropdowns
            field_types.get("textarea", 0),                # Text areas
            field_types.get("file", 0),                    # File uploads
            field_types.get("radio", 0),                   # Radio buttons
            field_types.get("checkbox", 0),                # Checkboxes
            field_types.get("date", 0),                    # Date inputs
            1 if form_schema.get("captcha_present") else 0,      # Has CAPTCHA
            1 if form_schema.get("multi_step") else 0,            # Multi-step
            len([f for f in fields if "depends_on" in f]),        # Cascading fields
        ]

        return np.array(features, dtype=float)

    def calculate_similarity(
        self,
        form1: Dict[str, Any],
        form2: Dict[str, Any]
    ) -> float:
        """
        Calculate cosine similarity between two forms

        Returns:
            Similarity score (0.0 - 1.0)
        """
        vec1 = self.vectorize_form(form1)
        vec2 = self.vectorize_form(form2)

        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        return float(similarity)

    def cluster_forms(
        self,
        forms: Dict[str, Dict[str, Any]],
        similarity_threshold: float = 0.75,
        min_cluster_size: int = 2
    ) -> List[FormCluster]:
        """
        Cluster forms using hierarchical clustering

        Args:
            forms: Dict mapping municipality name to form schema
            similarity_threshold: Minimum similarity to be in same cluster (0.75 = 75%)
            min_cluster_size: Minimum municipalities per cluster

        Returns:
            List of form clusters
        """
        if len(forms) < 2:
            logger.warning("Need at least 2 forms to cluster")
            return []

        municipality_names = list(forms.keys())
        n = len(municipality_names)

        # Calculate similarity matrix
        similarity_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i+1, n):
                sim = self.calculate_similarity(
                    forms[municipality_names[i]],
                    forms[municipality_names[j]]
                )
                similarity_matrix[i][j] = sim
                similarity_matrix[j][i] = sim

        # Simple agglomerative clustering
        clusters = [[i] for i in range(n)]  # Start with each form in its own cluster

        while True:
            # Find most similar pair of clusters
            max_sim = -1
            merge_i, merge_j = -1, -1

            for i in range(len(clusters)):
                for j in range(i+1, len(clusters)):
                    # Average linkage: average similarity between all pairs
                    sims = []
                    for idx1 in clusters[i]:
                        for idx2 in clusters[j]:
                            sims.append(similarity_matrix[idx1][idx2])

                    avg_sim = np.mean(sims) if sims else 0

                    if avg_sim > max_sim:
                        max_sim = avg_sim
                        merge_i, merge_j = i, j

            # Stop if no clusters are similar enough
            if max_sim < similarity_threshold:
                break

            # Merge clusters
            clusters[merge_i].extend(clusters[merge_j])
            del clusters[merge_j]

        # Convert to FormCluster objects
        form_clusters = []

        for cluster_id, cluster_indices in enumerate(clusters):
            if len(cluster_indices) < min_cluster_size:
                continue  # Skip small clusters

            # Get municipalities in this cluster
            cluster_munis = [municipality_names[i] for i in cluster_indices]

            # Calculate centroid (average feature vector)
            vectors = [self.vectorize_form(forms[m]) for m in cluster_munis]
            centroid_vec = np.mean(vectors, axis=0)

            # Find representative (closest to centroid)
            distances = [np.linalg.norm(v - centroid_vec) for v in vectors]
            rep_idx = np.argmin(distances)
            representative = cluster_munis[rep_idx]

            # Calculate average similarity within cluster
            intra_sims = []
            for i in range(len(cluster_indices)):
                for j in range(i+1, len(cluster_indices)):
                    intra_sims.append(similarity_matrix[cluster_indices[i]][cluster_indices[j]])

            avg_similarity = float(np.mean(intra_sims)) if intra_sims else 0.0

            # Create cluster
            form_cluster = FormCluster(
                cluster_id=cluster_id,
                centroid=self._vector_to_dict(centroid_vec),
                municipalities=cluster_munis,
                similarity_score=avg_similarity,
                representative_form=representative
            )

            form_clusters.append(form_cluster)

        self.clusters = form_clusters

        logger.info(f"✅ Clustered {len(forms)} forms into {len(form_clusters)} clusters")

        return form_clusters

    def _vector_to_dict(self, vector: np.ndarray) -> Dict[str, float]:
        """Convert feature vector to human-readable dict"""
        feature_names = [
            "total_fields", "required_fields", "text_inputs", "email_inputs",
            "phone_inputs", "number_inputs", "dropdowns", "text_areas",
            "file_uploads", "radio_buttons", "checkboxes", "date_inputs",
            "has_captcha", "multi_step", "cascading_fields"
        ]

        return {name: float(value) for name, value in zip(feature_names, vector)}

    def suggest_training_order(
        self,
        forms: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Suggest optimal training order

        Strategy:
        1. Cluster forms
        2. Train representative from each cluster first
        3. Train similar forms next (can reuse patterns)

        Returns:
            List of dicts with municipality, priority, cluster_id
        """
        # Cluster forms
        clusters = self.cluster_forms(forms)

        if not clusters:
            # No clustering possible, return original order
            return [
                {"municipality": m, "priority": 0, "cluster_id": None}
                for m in forms.keys()
            ]

        training_order = []

        # Phase 1: Train representatives (high priority)
        for cluster in clusters:
            training_order.append({
                "municipality": cluster.representative_form,
                "priority": 2,  # High priority
                "cluster_id": cluster.cluster_id,
                "role": "representative",
                "cluster_size": len(cluster.municipalities),
                "similarity_score": cluster.similarity_score
            })

        # Phase 2: Train similar forms (normal priority)
        for cluster in clusters:
            for muni in cluster.municipalities:
                if muni != cluster.representative_form:
                    training_order.append({
                        "municipality": muni,
                        "priority": 1,  # Normal priority
                        "cluster_id": cluster.cluster_id,
                        "role": "similar",
                        "representative": cluster.representative_form,
                        "similarity_score": cluster.similarity_score
                    })

        # Phase 3: Outliers (low priority)
        clustered_munis = set()
        for cluster in clusters:
            clustered_munis.update(cluster.municipalities)

        for muni in forms.keys():
            if muni not in clustered_munis:
                training_order.append({
                    "municipality": muni,
                    "priority": 0,  # Low priority
                    "cluster_id": None,
                    "role": "outlier"
                })

        logger.info(f"📋 Training order suggested:")
        logger.info(f"   Representatives: {sum(1 for t in training_order if t.get('role') == 'representative')}")
        logger.info(f"   Similar forms: {sum(1 for t in training_order if t.get('role') == 'similar')}")
        logger.info(f"   Outliers: {sum(1 for t in training_order if t.get('role') == 'outlier')}")

        return training_order

    def get_cluster_insights(self) -> Dict[str, Any]:
        """
        Get insights about form clusters

        Returns:
            Dict with cluster statistics and recommendations
        """
        if not self.clusters:
            return {"message": "No clusters available. Run cluster_forms() first."}

        insights = {
            "total_clusters": len(self.clusters),
            "clusters": []
        }

        for cluster in self.clusters:
            cluster_info = {
                "cluster_id": cluster.cluster_id,
                "size": len(cluster.municipalities),
                "municipalities": cluster.municipalities,
                "representative": cluster.representative_form,
                "similarity_score": f"{cluster.similarity_score*100:.1f}%",
                "characteristics": cluster.centroid,
                "recommendation": self._get_cluster_recommendation(cluster)
            }

            insights["clusters"].append(cluster_info)

        # Overall recommendations
        large_clusters = [c for c in self.clusters if len(c.municipalities) >= 5]
        if large_clusters:
            insights["recommendations"] = [
                f"Found {len(large_clusters)} large clusters (≥5 forms). "
                f"Train representatives first to maximize pattern reuse.",
                f"Estimated time savings: {self._estimate_time_savings()}%"
            ]

        return insights

    def _get_cluster_recommendation(self, cluster: FormCluster) -> str:
        """Get recommendation for a cluster"""
        size = len(cluster.municipalities)
        sim = cluster.similarity_score

        if size >= 5 and sim >= 0.85:
            return f"High priority cluster ({size} forms, {sim*100:.0f}% similar). Train representative '{cluster.representative_form}' first, then clone for others."
        elif size >= 3 and sim >= 0.75:
            return f"Medium cluster ({size} forms, {sim*100:.0f}% similar). Can reuse patterns with minor modifications."
        else:
            return f"Small cluster ({size} forms, {sim*100:.0f}% similar). May still benefit from pattern reuse."

    def _estimate_time_savings(self) -> int:
        """Estimate time savings from clustering"""
        if not self.clusters:
            return 0

        # Assume representatives take 100% time, similar forms take 40% time
        total_forms = sum(len(c.municipalities) for c in self.clusters)
        representatives = len(self.clusters)
        similar_forms = total_forms - representatives

        time_without_clustering = total_forms * 100
        time_with_clustering = (representatives * 100) + (similar_forms * 40)

        savings = ((time_without_clustering - time_with_clustering) / time_without_clustering) * 100

        return int(savings)


# For testing
if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING FORM CLUSTERING")
    print("="*80)

    # Sample forms
    forms = {
        "ranchi": {
            "fields": [
                {"type": "text", "required": True},
                {"type": "email", "required": True},
                {"type": "tel", "required": True},
                {"type": "textarea", "required": True},
                {"type": "select", "required": False},
            ],
            "captcha_present": False,
            "multi_step": False
        },
        "patna": {
            "fields": [
                {"type": "text", "required": True},
                {"type": "email", "required": True},
                {"type": "tel", "required": True},
                {"type": "textarea", "required": True},
                {"type": "select", "required": False},
                {"type": "file", "required": False},
            ],
            "captcha_present": False,
            "multi_step": False
        },
        "mumbai": {
            "fields": [
                {"type": "text", "required": True},
                {"type": "email", "required": True},
                {"type": "number", "required": True},
                {"type": "textarea", "required": True},
                {"type": "select", "required": True},
                {"type": "select", "required": True, "depends_on": "state"},
                {"type": "file", "required": False},
            ],
            "captcha_present": True,
            "multi_step": True
        },
        "delhi": {
            "fields": [
                {"type": "text", "required": True},
                {"type": "email", "required": True},
                {"type": "tel", "required": True},
                {"type": "textarea", "required": True},
            ],
            "captcha_present": False,
            "multi_step": False
        }
    }

    clusterer = FormClusterer()

    # Test clustering
    print("\n📊 Clustering forms...")
    clusters = clusterer.cluster_forms(forms, similarity_threshold=0.75)

    print(f"\n✅ Found {len(clusters)} clusters:")
    for cluster in clusters:
        print(f"\n   Cluster {cluster.cluster_id}:")
        print(f"      Size: {len(cluster.municipalities)}")
        print(f"      Municipalities: {', '.join(cluster.municipalities)}")
        print(f"      Representative: {cluster.representative_form}")
        print(f"      Similarity: {cluster.similarity_score*100:.1f}%")

    # Test training order suggestion
    print("\n" + "="*80)
    print("SUGGESTED TRAINING ORDER")
    print("="*80)

    training_order = clusterer.suggest_training_order(forms)

    for i, item in enumerate(training_order, 1):
        priority_label = {2: "HIGH", 1: "NORMAL", 0: "LOW"}[item["priority"]]
        role_emoji = {"representative": "👑", "similar": "🔄", "outlier": "⭐"}
        emoji = role_emoji.get(item["role"], "")

        print(f"{i}. {emoji} {item['municipality']:15s} [{priority_label:6s}] - {item.get('role', 'unknown')}")

    # Get insights
    print("\n" + "="*80)
    print("CLUSTER INSIGHTS")
    print("="*80)

    insights = clusterer.get_cluster_insights()
    print(json.dumps(insights, indent=2))

    print("\n" + "="*80)
