"""Cluster scoring and imbalance index endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
import logging
import pandas as pd
import statistics

from schemas import (
    ClusterImbalanceRequest,
    ClusterImbalanceResponse,
    HostImbalanceInfo,
    DataframeScoringScoringRequest,
    ProblematicHostsResponse,
)
from services.scoring.cluster_imbalance import ScoringService
from dependencies import get_scoring_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scoring", tags=["Scoring"])


@router.post("/cluster-imbalance", response_model=ClusterImbalanceResponse)
async def calculate_cluster_imbalance(
    request: ClusterImbalanceRequest,
    scoring: ScoringService = Depends(get_scoring_service),
) -> ClusterImbalanceResponse:
    try:
        if not request.metrics:
            raise ValueError("Metrics dictionary cannot be empty")
        
        if any(v < 0 for v in request.metrics.values()):
            raise ValueError("All metric values must be non-negative")
        
        # Calculate CII
        cii = await scoring.calculate_cluster_imbalance(
            metrics=request.metrics,
            weights=request.weights
        )
        
        # Calculate statistics
        values = list(request.metrics.values())
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
        min_val = min(values)
        max_val = max(values)
        
        # Calculate host details
        host_details = []
        for idx, (host_id, usage) in enumerate(sorted(request.metrics.items(), key=lambda x: x[1])):
            deviation = usage - mean
            percentile = (idx / len(request.metrics)) * 100 if len(request.metrics) > 1 else 0.0
            
            host_details.append(
                HostImbalanceInfo(
                    host_id=host_id,
                    usage=usage,
                    deviation=deviation,
                    percentile=percentile,
                )
            )
        
        return ClusterImbalanceResponse(
            success=True,
            cluster_imbalance_index=cii,
            host_count=len(request.metrics),
            mean_usage=mean,
            std_deviation=std_dev,
            min_usage=min_val,
            max_usage=max_val,
            usage_range=max_val - min_val,
            host_details=host_details,
        )
        
    except ValueError as e:
        logger.error(f"Invalid input for CII calculation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"CII calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"CII calculation failed: {str(e)}")


@router.post("/identify-problematic-hosts", response_model=ProblematicHostsResponse)
async def identify_problematic_hosts(
    metrics: Dict[str, float],
    threshold_percentile: float = 75.0,
    scoring: ScoringService = Depends(get_scoring_service),
) -> ProblematicHostsResponse:
    try:
        if not metrics:
            raise ValueError("Metrics dictionary cannot be empty")
        
        if not 0 <= threshold_percentile <= 100:
            raise ValueError("threshold_percentile must be between 0 and 100")
        
        # Identify problematic hosts
        problematic = await scoring.identify_problematic_hosts(
            metrics=metrics,
            threshold_percentile=threshold_percentile
        )
        
        # Calculate threshold value
        values = sorted(metrics.values())
        threshold_idx = int(len(values) * (threshold_percentile / 100))
        threshold_value = values[threshold_idx] if threshold_idx < len(values) else max(values)
        
        return ProblematicHostsResponse(
            success=True,
            problematic_hosts=problematic,
            count=len(problematic),
            threshold_value=threshold_value,
            threshold_percentile=threshold_percentile,
            total_hosts=len(metrics),
        )
        
    except ValueError as e:
        logger.error(f"Invalid input for problematic hosts identification: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Problematic hosts identification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/score-from-dataframe", response_model=ClusterImbalanceResponse)
async def score_from_dataframe(
    request: DataframeScoringScoringRequest,
    scoring: ScoringService = Depends(get_scoring_service),
) -> ClusterImbalanceResponse:
    try:
        if not request.dataframe_data:
            raise ValueError("Dataframe data cannot be empty")
        
        # Convert to DataFrame
        df = pd.DataFrame(request.dataframe_data)
        
        # Score from DataFrame
        result = await scoring.score_cluster_from_dataframe(
            df=df,
            cpu_col=request.cpu_column,
            mem_col=request.memory_column,
            swap_col=request.swap_column,
            weights=request.weights,
        )
        
        # Extract metrics and calculate statistics
        metrics = result.get("metrics", {})
        values = list(metrics.values())
        
        mean = statistics.mean(values) if values else 0.0
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
        min_val = min(values) if values else 0.0
        max_val = max(values) if values else 0.0
        
        # Calculate host details
        host_details = []
        for idx, (host_id, usage) in enumerate(sorted(metrics.items(), key=lambda x: x[1])):
            deviation = usage - mean
            percentile = (idx / len(metrics)) * 100 if len(metrics) > 1 else 0.0
            
            host_details.append(
                HostImbalanceInfo(
                    host_id=host_id,
                    usage=usage,
                    deviation=deviation,
                    percentile=percentile,
                )
            )
        
        return ClusterImbalanceResponse(
            success=True,
            cluster_imbalance_index=result.get("cii", 0.0),
            host_count=result.get("host_count", 0),
            mean_usage=mean,
            std_deviation=std_dev,
            min_usage=min_val,
            max_usage=max_val,
            usage_range=max_val - min_val,
            host_details=host_details,
        )
        
    except ValueError as e:
        logger.error(f"Invalid input for DataFrame scoring: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"DataFrame scoring failed: {e}")
        raise HTTPException(status_code=500, detail=f"DataFrame scoring failed: {str(e)}")


@router.get("/health")
async def scoring_health(
    scoring: ScoringService = Depends(get_scoring_service),
) -> dict:
    try:
        return {
            "status": "healthy",
            "service": "clustering_scoring",
            "message": "Scoring service is ready"
        }
    except Exception as e:
        logger.error(f"Scoring service health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "clustering_scoring",
            "error": str(e)
        }


@router.post("/batch-imbalance", response_model=List[ClusterImbalanceResponse])
async def batch_cluster_imbalance(
    requests: List[ClusterImbalanceRequest],
    scoring: ScoringService = Depends(get_scoring_service),
) -> List[ClusterImbalanceResponse]:
    if len(requests) > 100:
        raise HTTPException(
            status_code=400,
            detail="Batch size cannot exceed 100 requests"
        )
    
    results = []
    for request in requests:
        try:
            if not request.metrics:
                results.append(
                    ClusterImbalanceResponse(
                        success=False,
                        cluster_imbalance_index=0.0,
                        host_count=0,
                        mean_usage=0.0,
                        std_deviation=0.0,
                        min_usage=0.0,
                        max_usage=0.0,
                        usage_range=0.0,
                    )
                )
                continue
            
            # Calculate CII
            cii = await scoring.calculate_cluster_imbalance(
                metrics=request.metrics,
                weights=request.weights
            )
            
            # Calculate statistics
            values = list(request.metrics.values())
            mean = statistics.mean(values)
            std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
            min_val = min(values)
            max_val = max(values)
            
            # Calculate host details
            host_details = []
            for idx, (host_id, usage) in enumerate(sorted(request.metrics.items(), key=lambda x: x[1])):
                deviation = usage - mean
                percentile = (idx / len(request.metrics)) * 100 if len(request.metrics) > 1 else 0.0
                
                host_details.append(
                    HostImbalanceInfo(
                        host_id=host_id,
                        usage=usage,
                        deviation=deviation,
                        percentile=percentile,
                    )
                )
            
            results.append(
                ClusterImbalanceResponse(
                    success=True,
                    cluster_imbalance_index=cii,
                    host_count=len(request.metrics),
                    mean_usage=mean,
                    std_deviation=std_dev,
                    min_usage=min_val,
                    max_usage=max_val,
                    usage_range=max_val - min_val,
                    host_details=host_details,
                )
            )
            
        except Exception as e:
            logger.error(f"Batch CII calculation failed for one request: {e}")
            results.append(
                ClusterImbalanceResponse(
                    success=False,
                    cluster_imbalance_index=0.0,
                    host_count=0,
                    mean_usage=0.0,
                    std_deviation=0.0,
                    min_usage=0.0,
                    max_usage=0.0,
                    usage_range=0.0,
                )
            )
    
    return results
