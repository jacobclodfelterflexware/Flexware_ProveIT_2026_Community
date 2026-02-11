"""AutoGluon Time Series prediction service."""

import logging
import tempfile
import shutil
import sys
import io
import threading
import queue
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Generator

import pandas as pd
import numpy as np

from src.config import get_settings
from src.models.schemas import PredictionPoint, PredictionMetrics

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy import AutoGluon to avoid startup overhead
_TimeSeriesDataFrame = None
_TimeSeriesPredictor = None


def _get_autogluon_imports():
    """Lazy import AutoGluon components."""
    global _TimeSeriesDataFrame, _TimeSeriesPredictor
    if _TimeSeriesDataFrame is None:
        from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor
        _TimeSeriesDataFrame = TimeSeriesDataFrame
        _TimeSeriesPredictor = TimeSeriesPredictor
    return _TimeSeriesDataFrame, _TimeSeriesPredictor


def prepare_time_series_data(df: pd.DataFrame, field_name: str, time_col: str = "date") -> pd.DataFrame:
    """
    Prepare data for AutoGluon TimeSeriesPredictor.

    Args:
        df: DataFrame with time column and 'value' columns
        field_name: Name of the field being predicted
        time_col: Name of the time column ('date' or 'timestamp')

    Returns:
        DataFrame formatted for AutoGluon
    """
    if df.empty:
        return pd.DataFrame()

    # Ensure proper datetime format
    ts_df = df.copy()
    ts_df["timestamp"] = pd.to_datetime(ts_df[time_col])
    ts_df = ts_df.sort_values("timestamp")

    # Add item_id column (required by AutoGluon for single series)
    ts_df["item_id"] = field_name

    # Rename value column to target
    ts_df = ts_df.rename(columns={"value": "target"})

    # Select and order columns
    ts_df = ts_df[["item_id", "timestamp", "target"]]

    return ts_df


def train_time_series_model(
    df: pd.DataFrame,
    field_name: str,
    prediction_length: int,
    time_limit: int = 300,
    time_col: str = "date"
) -> tuple[Optional[object], Optional[PredictionMetrics]]:
    """
    Train an AutoGluon time series model.

    Args:
        df: DataFrame with time and value columns
        field_name: Name of the field
        prediction_length: Number of future periods to predict
        time_limit: Training time limit in seconds
        time_col: Name of time column ('date' or 'timestamp')

    Returns:
        Tuple of (trained predictor, metrics) or (None, None) if failed
    """
    TimeSeriesDataFrame, TimeSeriesPredictor = _get_autogluon_imports()

    min_points = settings.min_data_points  # Use same threshold for all horizons
    if len(df) < min_points:
        logger.warning(f"Insufficient data points ({len(df)}) for training. Minimum: {min_points}")
        return None, None

    # Prepare data
    ts_df = prepare_time_series_data(df, field_name, time_col)
    if ts_df.empty:
        return None, None

    # Convert to AutoGluon format
    train_data = TimeSeriesDataFrame.from_data_frame(
        ts_df,
        id_column="item_id",
        timestamp_column="timestamp"
    )

    # Create temporary directory for model
    temp_dir = tempfile.mkdtemp(prefix="ag_ts_")

    try:
        # Train predictor
        predictor = TimeSeriesPredictor(
            prediction_length=prediction_length,
            path=temp_dir,
            target="target",
            eval_metric="MAPE",
            freq="T",  # 1-minute frequency (T = minutely)
            verbosity=1
        )

        predictor.fit(
            train_data,
            time_limit=time_limit,
            presets="medium_quality",  # Better model quality
        )

        # Get model performance metrics
        leaderboard = predictor.leaderboard(train_data)
        best_score = leaderboard.iloc[0]["score_val"] if not leaderboard.empty else None

        metrics = PredictionMetrics(
            mape=abs(best_score) if best_score else None
        )

        logger.info(f"Model trained for {field_name}, MAPE: {metrics.mape}")
        # Store temp_dir path on predictor so we can clean up later
        predictor._temp_dir = temp_dir
        return predictor, metrics

    except Exception as e:
        logger.error(f"Failed to train time series model: {e}")
        # Clean up on error
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        return None, None


def train_with_output_capture(
    df: pd.DataFrame,
    field_name: str,
    prediction_length: int,
    time_limit: int = 300,
    time_col: str = "date"
) -> Generator[dict, None, None]:
    """
    Train model while capturing stdout and logging output.

    Yields dicts with:
    - {"type": "output", "line": str} for captured output lines
    - {"type": "heartbeat"} when no output but still training
    - {"type": "complete", "predictor": obj, "metrics": obj} on success
    - {"type": "error", "message": str} on failure
    """
    output_queue: queue.Queue = queue.Queue()
    result = {"predictor": None, "metrics": None, "error": None}

    class QueueHandler(logging.Handler):
        """Custom logging handler that puts records in a queue and echoes to stdout."""
        def emit(self, record):
            try:
                msg = self.format(record)
                if msg.strip():
                    output_queue.put(msg.strip())
                    # Also print to stdout for container logs
                    print(msg, flush=True)
            except Exception:
                pass

    class OutputCapture:
        """Capture stdout/stderr and forward to both queue and original stream."""
        def __init__(self, original_stream, q):
            self.original = original_stream
            self.queue = q

        def write(self, s):
            # Always write to original stream so it appears in container logs
            self.original.write(s)
            self.original.flush()
            # Also send to queue for SSE streaming
            if s.strip():
                self.queue.put(s.strip())

        def flush(self):
            self.original.flush()

    def train_in_thread():
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        capture_stdout = OutputCapture(old_stdout, output_queue)
        capture_stderr = OutputCapture(old_stderr, output_queue)
        sys.stdout = capture_stdout
        sys.stderr = capture_stderr

        # Add queue handler to capture logging output from autogluon
        queue_handler = QueueHandler()
        queue_handler.setLevel(logging.INFO)
        queue_handler.setFormatter(logging.Formatter('%(message)s'))

        # Capture autogluon and related loggers
        loggers_to_capture = [
            logging.getLogger('autogluon'),
            logging.getLogger('autogluon.timeseries'),
            logging.getLogger('autogluon.core'),
        ]
        for lg in loggers_to_capture:
            lg.addHandler(queue_handler)
            lg.setLevel(logging.INFO)

        try:
            predictor, metrics = train_time_series_model(
                df, field_name, prediction_length, time_limit, time_col
            )
            result["predictor"] = predictor
            result["metrics"] = metrics
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Training thread error: {e}")
        finally:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            # Remove queue handlers
            for lg in loggers_to_capture:
                lg.removeHandler(queue_handler)
            output_queue.put(None)  # Signal completion

    thread = threading.Thread(target=train_in_thread)
    thread.start()

    # Yield output lines while training
    while True:
        try:
            line = output_queue.get(timeout=0.5)
            if line is None:
                break
            yield {"type": "output", "line": line}
        except queue.Empty:
            yield {"type": "heartbeat"}

    thread.join()

    if result["error"]:
        yield {"type": "error", "message": result["error"]}
    else:
        yield {"type": "complete", "predictor": result["predictor"], "metrics": result["metrics"]}


def generate_predictions(
    predictor: object,
    df: pd.DataFrame,
    field_name: str,
    prediction_length: int,
    time_col: str = "date",
    horizon: str = "week"
) -> list[PredictionPoint]:
    """
    Generate predictions using a trained model.

    Args:
        predictor: Trained AutoGluon predictor
        df: Historical data DataFrame
        field_name: Name of the field
        prediction_length: Number of periods to predict
        time_col: Name of time column ('date' or 'timestamp')
        horizon: Prediction horizon ('day', 'week', 'month')

    Returns:
        List of PredictionPoint objects
    """
    TimeSeriesDataFrame, _ = _get_autogluon_imports()

    try:
        # Prepare historical data
        ts_df = prepare_time_series_data(df, field_name, time_col)
        train_data = TimeSeriesDataFrame.from_data_frame(
            ts_df,
            id_column="item_id",
            timestamp_column="timestamp"
        )

        # Generate predictions
        predictions_df = predictor.predict(train_data)

        # Extract predictions
        predictions = []
        last_time = df[time_col].max()

        # Always use 1-minute time steps for all predictions
        time_step = timedelta(minutes=1)
        date_format = "%Y-%m-%dT%H:%M:%S"

        for idx, (i, row) in enumerate(predictions_df.iterrows()):
            # Calculate prediction time (use enumerate index to avoid numpy int issues)
            step_num = idx + 1
            pred_time = last_time + time_step * step_num

            # Get mean and quantiles if available
            mean_val = row.get("mean", row.iloc[0]) if hasattr(row, "get") else float(row)

            # Try to get confidence intervals
            lower = row.get("0.1", mean_val * 0.9) if hasattr(row, "get") else mean_val * 0.9
            upper = row.get("0.9", mean_val * 1.1) if hasattr(row, "get") else mean_val * 1.1

            predictions.append(PredictionPoint(
                date=pred_time.strftime(date_format) if hasattr(pred_time, "strftime") else str(pred_time),
                value=float(mean_val),
                lower=float(lower),
                upper=float(upper)
            ))

        return predictions[:prediction_length]

    except Exception as e:
        logger.error(f"Failed to generate predictions: {e}")
        return []
    finally:
        # Clean up temp directory after predictions are generated
        if hasattr(predictor, '_temp_dir'):
            try:
                shutil.rmtree(predictor._temp_dir)
            except Exception:
                pass


def get_historical_points(df: pd.DataFrame, num_points: int = 30, time_col: str = "date", horizon: str = "week") -> list[PredictionPoint]:
    """
    Convert recent historical data to PredictionPoint format.

    Args:
        df: Historical DataFrame with time and value columns
        num_points: Number of recent points to include
        time_col: Name of time column ('date' or 'timestamp')
        horizon: Prediction horizon for date formatting

    Returns:
        List of PredictionPoint objects
    """
    if df.empty:
        return []

    recent_df = df.tail(num_points)
    points = []

    # Determine date format based on horizon
    if horizon == "day":
        date_format = "%Y-%m-%dT%H:%M:%S"
    else:
        date_format = "%Y-%m-%d"

    for _, row in recent_df.iterrows():
        time_val = row[time_col]
        if hasattr(time_val, "strftime"):
            date_str = time_val.strftime(date_format)
        else:
            date_str = str(time_val)

        points.append(PredictionPoint(
            date=date_str,
            value=float(row["value"]),
            lower=float(row["value"]),  # No confidence interval for historical
            upper=float(row["value"])
        ))

    return points


async def run_time_series_prediction(
    df: pd.DataFrame,
    field_name: str,
    horizon: str = "week"
) -> tuple[list[PredictionPoint], list[PredictionPoint], PredictionMetrics, int]:
    """
    Run complete time series prediction workflow.

    Args:
        df: Historical data with 'date'/'timestamp' and 'value' columns
        field_name: Name of the field to predict
        horizon: "day", "week" or "month"

    Returns:
        Tuple of (predictions, historical, metrics, data_points_used)
    """
    # Determine settings based on horizon
    if horizon == "day":
        prediction_length = settings.prediction_horizon_day
        time_col = "timestamp"
        historical_points = min(48, len(df))  # Show up to 1 day of historical data
    elif horizon == "week":
        prediction_length = settings.prediction_horizon_week
        time_col = "date"
        historical_points = 30
    else:  # month
        prediction_length = settings.prediction_horizon_month
        time_col = "date"
        historical_points = 30

    # AutoGluon requires at least 2 * prediction_length + 1 observations
    # Adjust prediction_length if we don't have enough data
    max_prediction_length = max(1, (len(df) - 1) // 2)
    if prediction_length > max_prediction_length:
        logger.info(f"Reducing prediction_length from {prediction_length} to {max_prediction_length} due to limited data ({len(df)} points)")
        prediction_length = max_prediction_length

    # Train model
    predictor, metrics = train_time_series_model(
        df,
        field_name,
        prediction_length,
        settings.training_time_limit,
        time_col
    )

    if predictor is None:
        logger.warning(f"Model training failed for {field_name}")
        return [], get_historical_points(df, historical_points, time_col, horizon), PredictionMetrics(), len(df)

    # Generate predictions
    predictions = generate_predictions(predictor, df, field_name, prediction_length, time_col, horizon)

    # Get historical context
    historical = get_historical_points(df, num_points=historical_points, time_col=time_col, horizon=horizon)

    return predictions, historical, metrics or PredictionMetrics(), len(df)


# Fallback simple prediction when AutoGluon isn't available or fails
def simple_moving_average_prediction(
    df: pd.DataFrame,
    prediction_length: int,
    window: int = 7,
    horizon: str = "week"
) -> list[PredictionPoint]:
    """
    Simple moving average prediction as fallback.

    Args:
        df: Historical data
        prediction_length: Number of periods to predict
        window: Moving average window size
        horizon: Prediction horizon for time step

    Returns:
        List of predictions
    """
    if df.empty or len(df) < window:
        return []

    values = df["value"].values

    # Always use 1-minute time steps
    time_col = "timestamp"
    time_step = timedelta(minutes=1)
    date_format = "%Y-%m-%dT%H:%M:%S"

    last_time = df[time_col].max()

    # Calculate moving average and std
    ma = np.mean(values[-window:])
    std = np.std(values[-window:])

    predictions = []
    for i in range(prediction_length):
        pred_time = last_time + time_step * (i + 1)
        predictions.append(PredictionPoint(
            date=pred_time.strftime(date_format),
            value=float(ma),
            lower=float(ma - 2 * std),
            upper=float(ma + 2 * std)
        ))

    return predictions
