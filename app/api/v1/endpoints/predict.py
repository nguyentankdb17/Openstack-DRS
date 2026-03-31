"""Prediction endpoints using Chronos model"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
import logging
import pandas as pd

from schemas import PredictionRequest, PredictionResponse, PredictionValueResponse
from services.prediction.predictor_service import PredictorService
from dependencies import get_predictor_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["Predictions"])


@router.post("/", response_model=PredictionResponse)
async def predict_metric(
    request: PredictionRequest,
    predictor: PredictorService = Depends(get_predictor_service),
) -> PredictionResponse:
    try:
        # Convert list to DataFrame (Chronos expects DataFrame)
        df = pd.DataFrame({"value": request.data})
        
        # Predict metrics
        pred_df = predictor.predict_metrics(
            metric_history=df,
            length=request.prediction_length
        )
        
        # Parse predictions and extract quantiles
        predictions = []
        
        # Assuming pred_df has columns for different quantiles
        # The structure depends on Chronos output format
        quantile_cols = [col for col in pred_df.columns if isinstance(col, float)]
        sorted_quantiles = sorted(quantile_cols)
        
        for idx, row in pred_df.iterrows():
            pred_vals = {}
            for q in sorted_quantiles:
                pred_vals[q] = float(row[q])
            
            # Map quantiles to p10, p50, p90
            prediction = PredictionValueResponse(
                timestamp=int(idx + 1),
                p10=pred_vals.get(0.1, pred_vals[sorted_quantiles[0]]),
                p50=pred_vals.get(0.5, pred_vals[sorted_quantiles[1]]),
                p90=pred_vals.get(0.9, pred_vals[sorted_quantiles[-1]]),
            )
            predictions.append(prediction)
        
        return PredictionResponse(
            success=True,
            predictions=predictions,
            prediction_length=len(predictions),
            quantiles=[0.1, 0.5, 0.9],
        )
        
    except ValueError as e:
        logger.error(f"Invalid input for prediction: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/batch", response_model=List[PredictionResponse])
async def predict_metrics_batch(
    requests: List[PredictionRequest],
    predictor: PredictorService = Depends(get_predictor_service),
) -> List[PredictionResponse]:
    """
    Predict future values for multiple metric histories in batch.
    
    Args:
        requests: List of PredictionRequest objects
        predictor: PredictorService instance (injected)
    
    Returns:
        List of PredictionResponse objects
        
    Raises:
        HTTPException: If batch size exceeds limit or prediction fails
    """
    if len(requests) > 100:
        raise HTTPException(
            status_code=400,
            detail="Batch size cannot exceed 100 requests"
        )
    
    results = []
    for request in requests:
        try:
            # Reuse the single prediction endpoint logic
            df = pd.DataFrame({"value": request.data})
            
            pred_df = predictor.predict_metrics(
                metric_history=df,
                length=request.prediction_length
            )
            
            predictions = []
            quantile_cols = [col for col in pred_df.columns if isinstance(col, float)]
            sorted_quantiles = sorted(quantile_cols)
            
            for idx, row in pred_df.iterrows():
                pred_vals = {}
                for q in sorted_quantiles:
                    pred_vals[q] = float(row[q])
                
                prediction = PredictionValueResponse(
                    timestamp=int(idx + 1),
                    p10=pred_vals.get(0.1, pred_vals[sorted_quantiles[0]]),
                    p50=pred_vals.get(0.5, pred_vals[sorted_quantiles[1]]),
                    p90=pred_vals.get(0.9, pred_vals[sorted_quantiles[-1]]),
                )
                predictions.append(prediction)
            
            results.append(
                PredictionResponse(
                    success=True,
                    predictions=predictions,
                    prediction_length=len(predictions),
                    quantiles=[0.1, 0.5, 0.9],
                )
            )
            
        except ValueError as e:
            logger.error(f"Invalid input in batch prediction: {e}")
            results.append(
                PredictionResponse(
                    success=False,
                    predictions=[],
                    prediction_length=0,
                    quantiles=[0.1, 0.5, 0.9],
                )
            )
        except Exception as e:
            logger.error(f"Batch prediction failed for one request: {e}")
            results.append(
                PredictionResponse(
                    success=False,
                    predictions=[],
                    prediction_length=0,
                    quantiles=[0.1, 0.5, 0.9],
                )
            )
    
    return results


@router.get("/health")
async def prediction_health(
    predictor: PredictorService = Depends(get_predictor_service),
) -> dict:
    try:
        # Try to load the pipeline
        _ = predictor._load_pipeline()
        return {
            "status": "healthy",
            "model": "amazon/chronos-2",
            "message": "Prediction service is ready"
        }
    except Exception as e:
        logger.error(f"Prediction service health check failed: {e}")
        return {
            "status": "unhealthy",
            "model": "amazon/chronos-2",
            "error": str(e)
        }
