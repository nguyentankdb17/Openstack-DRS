"""Decision engine for live migration recommendations."""

import logging
from typing import Dict, List, Optional

from services.analytic.analytic_service import AnalyticService
from services.scoring.cluster_imbalance import ScoringService
from services.migration_detector import MigrationEventDetector

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    DRS Decision Engine - determines if live migration is needed based on:
    1. Current cluster imbalance index (CII)
    2. Predicted future CII
    3. Migration history (don't migrate if events happened recently)
    """
    
    def __init__(
        self,
        analytic_service: AnalyticService,
        scoring_service: ScoringService,
        migration_detector: MigrationEventDetector,
        settings
    ):
        """
        Initialize decision engine.
        
        Args:
            analytic_service: Service for metric analysis and prediction
            scoring_service: Service for CII calculation
            migration_detector: Service for detecting migration events
            settings: Configuration object with thresholds
        """
        self.analytic_service = analytic_service
        self.scoring_service = scoring_service
        self.migration_detector = migration_detector
        self.settings = settings
        logger.info("DecisionEngine initialized")
    
    async def execute_decision_cycle(self) -> Dict:
        """
        Execute one complete decision cycle (5-minute interval).
        
        Workflow:
        1. Check if migration events occurred in last 5 minutes
        2. If events exist → Skip decision (return early)
        3. If no events → Calculate current CII
        4. If current CII > threshold → Recommend migration (return problematic hosts)
        5. If current CII ≤ threshold → Predict future CII
        6. If predicted CII > threshold → Recommend migration based on prediction
        
        Returns:
            {
                "timestamp": ISO timestamp,
                "decision": "skip" | "no_action" | "migrate",
                "reason": str,
                "current_cii": float (optional),
                "predicted_cii": float (optional),
                "problematic_hosts": list (optional),
                "migration_reason": str (optional)
            }
        """
        try:
            logger.info("=" * 60)
            logger.info("Starting 5-minute decision cycle")
            logger.info("=" * 60)
            
            from datetime import datetime
            result = {
                "timestamp": datetime.utcnow().isoformat(),
                "decision": None,
                "reason": None,
            }
            
            # Step 1: Check for recent migration events
            logger.info("Step 1: Checking for migration events...")
            has_events = await self._check_migration_events()
            
            if has_events:
                result["decision"] = "skip"
                result["reason"] = f"Live migration/create/delete events detected in last {self.settings.app.cii_threshold_current}min - skipping decision"
                logger.info(f"✓ {result['reason']}")
                return result
            
            logger.info("✓ No migration events detected - proceed to analysis")
            
            # Step 2: Calculate current CII
            logger.info("Step 2: Calculating current cluster imbalance...")
            current_result = await self.analytic_service.calculate_cluster_imbalance()
            
            if not current_result:
                result["decision"] = "no_action"
                result["reason"] = "Failed to calculate current metrics"
                logger.warning(result["reason"])
                return result
            
            current_cii = current_result.get("cii", 0.0)
            result["current_cii"] = current_cii
            current_metrics = current_result.get("metrics", {})
            
            logger.info(f"✓ Current CII: {current_cii:.4f}")
            logger.debug(f"  Current metrics by host: {current_metrics}")
            
            # Step 3: Check if current CII exceeds threshold
            cii_threshold = self.settings.app.cii_threshold_current
            
            if current_cii > cii_threshold:
                # Current imbalance is already high - recommend migration
                problematic = await self._identify_problematic_hosts(
                    current_metrics,
                    percentile=self.settings.app.problematic_hosts_percentile
                )
                
                result["decision"] = "migrate"
                result["reason"] = f"Current CII {current_cii:.4f} exceeds threshold {cii_threshold:.4f}"
                result["migration_reason"] = "High current cluster imbalance"
                result["problematic_hosts"] = problematic
                
                logger.info(f"⚠ {result['reason']}")
                logger.info(f"  Problematic hosts: {problematic}")
                return result
            
            logger.info(f"✓ Current CII {current_cii:.4f} ≤ threshold {cii_threshold:.4f} - check prediction")
            
            # Step 4: Predict future CII
            logger.info("Step 3: Predicting future cluster imbalance...")
            predicted_result = await self.analytic_service.calculate_predicted_imbalance(
                lookback_hours=self.settings.app.prediction_lookback_hours,
                prediction_horizon_minutes=self.settings.app.prediction_horizon_minutes
            )
            
            if not predicted_result:
                result["decision"] = "no_action"
                result["reason"] = "Current CII OK, but prediction failed - no action taken"
                logger.info(result["reason"])
                return result
            
            predicted_cii = predicted_result.get("cii", 0.0)
            result["predicted_cii"] = predicted_cii
            predicted_metrics = predicted_result.get("metrics", {})
            
            logger.info(f"✓ Predicted CII (next {self.settings.app.prediction_horizon_minutes}min): {predicted_cii:.4f}")
            logger.debug(f"  Predicted metrics by host: {predicted_metrics}")
            
            # Step 5: Check if predicted CII exceeds threshold
            if predicted_cii > cii_threshold:
                # Future imbalance will be high - recommend proactive migration
                problematic = await self._identify_problematic_hosts(
                    predicted_metrics,
                    percentile=self.settings.app.problematic_hosts_percentile
                )
                
                result["decision"] = "migrate"
                result["reason"] = f"Predicted CII {predicted_cii:.4f} exceeds threshold {cii_threshold:.4f}"
                result["migration_reason"] = "Predicted cluster imbalance will exceed threshold"
                result["problematic_hosts"] = problematic
                
                logger.info(f"⚠ {result['reason']}")
                logger.info(f"  Predicted problematic hosts: {problematic}")
                return result
            
            # All checks passed - no action needed
            result["decision"] = "no_action"
            result["reason"] = f"Current CII {current_cii:.4f} and Predicted CII {predicted_cii:.4f} both ≤ threshold {cii_threshold:.4f}"
            logger.info(f"✓ {result['reason']}")
            
            return result
        
        except Exception as e:
            logger.error(f"Decision cycle failed: {e}", exc_info=True)
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "decision": "error",
                "reason": f"Decision cycle failed: {str(e)}"
            }
    
    async def _check_migration_events(self) -> bool:
        """
        Check if migration events occurred in recent window.
        
        Returns:
            True if events found, False otherwise
        """
        try:
            has_events = await self.migration_detector.check_migration_events(
                lookback_minutes=self.settings.openstack.migration_check_minutes
            )
            return has_events
        except Exception as e:
            logger.warning(f"Failed to check migration events: {e}")
            return False
    
    async def _identify_problematic_hosts(
        self,
        metrics_by_host: Dict[str, float],
        percentile: float = 75.0
    ) -> List[Dict]:
        """
        Identify problematic hosts using percentile-based threshold.
        
        Returns:
            Sorted list of problematic hosts with scores:
            [
                {"host_id": "10.10.10.137", "usage_score": 75.5},
                {"host_id": "10.10.10.138", "usage_score": 72.1},
            ]
        """
        try:
            problematic = await self.scoring_service.identify_problematic_hosts(
                metrics=metrics_by_host,
                threshold_percentile=percentile
            )
            
            # Enrich with detailed scores and sort by usage score (highest first)
            problematic_hosts = []
            for host_id in problematic:
                usage_score = metrics_by_host.get(host_id, 0.0)
                problematic_hosts.append({
                    "host_id": host_id,
                    "usage_score": round(usage_score, 2)
                })
            
            # Sort by usage score (highest first)
            problematic_hosts.sort(key=lambda x: x["usage_score"], reverse=True)
            
            logger.debug(f"Identified {len(problematic_hosts)} problematic hosts")
            return problematic_hosts
        
        except Exception as e:
            logger.error(f"Failed to identify problematic hosts: {e}")
            return []
