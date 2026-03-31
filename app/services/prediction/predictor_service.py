import logging
import pandas as pd
from typing import Optional
from chronos import BaseChronosPipeline

logger = logging.getLogger(__name__)


class PredictorService:
    def __init__(self):
        logger.info("PredictorService initialized")
        self._pipeline: Optional[BaseChronosPipeline] = None
    
    def _load_pipeline(self) -> BaseChronosPipeline:
        if self._pipeline is None:
            try:
                self._pipeline = BaseChronosPipeline.from_pretrained(
                    "amazon/chronos-2", device_map="auto"
                )
                logger.info("Pipeline loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load pipeline: {e}")
                raise
        return self._pipeline
    
    def predict_metrics(
        self,
        metric_history: pd.DataFrame,
        length: int = 60
    ) -> pd.DataFrame:
        if metric_history is None or metric_history.empty:
            raise ValueError("metric_history cannot be None or empty")
        
        if length <= 0:
            raise ValueError("length must be positive")
        
        try:
            pipeline = self._load_pipeline()
            pred_df = pipeline.predict_df(
                metric_history,
                prediction_length=length,
                quantile_levels=[0.1, 0.5, 0.9]
            )
            return pred_df
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise
