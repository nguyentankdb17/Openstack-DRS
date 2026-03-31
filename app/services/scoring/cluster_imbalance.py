import logging
import math
from typing import Dict, List, Optional

import pandas as pd


logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self):
        logger.info("ScoringService initialized")
    
    async def calculate_cluster_imbalance(
        self,
        metrics: Dict[str, float],
        weights: Optional[Dict[str, float]] = None
    ) -> float:
        try:
            if not metrics:
                logger.warning("Empty metrics for CII calculation")
                return 0.0
            
            values = list(metrics.values())
            mean = sum(values) / len(values)
            
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            cii = math.sqrt(variance)
            
            logger.info(f"Calculated CII: {cii:.4f} for {len(metrics)} hosts")
            return cii
        
        except Exception as e:
            logger.error(f"CII calculation failed: {e}")
            raise
    
    async def score_cluster_from_dataframe(
        self,
        df: pd.DataFrame,
        cpu_col: str = "cpu_usage",
        mem_col: str = "memory_usage",
        swap_col: str = "swap_usage",
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        try:
            if df.empty:
                logger.warning("Empty DataFrame for scoring")
                return {}
            
            # Default weights
            w = weights or {"cpu": 0.5, "memory": 0.3, "swap": 0.2}
            
            # Calculate weighted usage per host
            metrics = {}
            for idx, row in df.iterrows():
                host_id = row.get("host_id", f"host_{idx}")
                usage = (
                    w.get("cpu", 0.5) * row.get(cpu_col, 0) +
                    w.get("memory", 0.3) * row.get(mem_col, 0) +
                    w.get("swap", 0.2) * row.get(swap_col, 0)
                )
                metrics[host_id] = usage
            
            cii = await self.calculate_cluster_imbalance(metrics)
            
            return {
                "cii": cii,
                "host_count": len(metrics),
                "metrics": metrics,
            }
        
        except Exception as e:
            logger.error(f"DataFrame scoring failed: {e}")
            raise
    
    async def identify_problematic_hosts(
        self,
        metrics: Dict[str, float],
        threshold_percentile: float = 75.0
    ) -> List[str]:
        try:
            if not metrics:
                return []
            
            values = sorted(metrics.values())
            threshold_idx = int(len(values) * (threshold_percentile / 100))
            threshold = values[threshold_idx] if threshold_idx < len(values) else max(values)
            
            problematic = [
                host_id for host_id, usage in metrics.items()
                if usage > threshold
            ]
            
            logger.info(f"Found {len(problematic)} problematic hosts above {threshold:.2f}")
            return problematic
        
        except Exception as e:
            logger.error(f"Failed to identify problematic hosts: {e}")
            raise
