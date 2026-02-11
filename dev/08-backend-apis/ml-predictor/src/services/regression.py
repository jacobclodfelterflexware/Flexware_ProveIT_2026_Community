"""AutoGluon Tabular regression service for cross-machine correlation analysis."""

import logging
import tempfile
import shutil
from typing import Optional

import pandas as pd
import numpy as np
from scipy import stats

from src.config import get_settings
from src.models.schemas import FeatureInfo

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy import AutoGluon
_TabularPredictor = None


def _get_autogluon_tabular():
    """Lazy import AutoGluon Tabular."""
    global _TabularPredictor
    if _TabularPredictor is None:
        from autogluon.tabular import TabularPredictor
        _TabularPredictor = TabularPredictor
    return _TabularPredictor


def calculate_correlation_matrix(df: pd.DataFrame) -> dict:
    """
    Calculate correlation matrix for all columns.

    Args:
        df: DataFrame with feature columns

    Returns:
        Dictionary mapping column pairs to correlation values
    """
    if df.empty or len(df.columns) < 2:
        return {}

    corr_matrix = df.corr()

    # Convert to nested dict format, replacing NaN with 0.0
    result = {}
    for col1 in corr_matrix.columns:
        result[col1] = {}
        for col2 in corr_matrix.columns:
            val = corr_matrix.loc[col1, col2]
            result[col1][col2] = 0.0 if pd.isna(val) else float(val)

    return result


def calculate_p_values(df: pd.DataFrame, target_col: str) -> dict:
    """
    Calculate p-values for correlations between features and target.

    Args:
        df: DataFrame with features and target
        target_col: Name of target column

    Returns:
        Dictionary mapping feature names to p-values
    """
    p_values = {}
    target = df[target_col]

    for col in df.columns:
        if col == target_col:
            continue
        try:
            _, p_value = stats.pearsonr(df[col], target)
            p_values[col] = None if pd.isna(p_value) else float(p_value)
        except Exception:
            p_values[col] = None

    return p_values


def train_regression_model(
    df: pd.DataFrame,
    target_col: str,
    time_limit: int = 300
) -> tuple[Optional[object], Optional[dict], float]:
    """
    Train an AutoGluon tabular regression model.

    Args:
        df: DataFrame with features and target
        target_col: Name of target column
        time_limit: Training time limit in seconds

    Returns:
        Tuple of (predictor, feature_importance, r_squared)
    """
    TabularPredictor = _get_autogluon_tabular()

    if len(df) < settings.min_data_points:
        logger.warning(f"Insufficient data points ({len(df)}) for regression")
        return None, None, 0.0

    if target_col not in df.columns:
        logger.error(f"Target column {target_col} not found in data")
        return None, None, 0.0

    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="ag_tab_")

    try:
        predictor = TabularPredictor(
            label=target_col,
            path=temp_dir,
            problem_type="regression",
            eval_metric="r2",
            verbosity=1
        )

        predictor.fit(
            df,
            time_limit=time_limit,
            presets="medium_quality"
        )

        # Get feature importance
        importance = predictor.feature_importance(df)
        importance_dict = importance.to_dict() if hasattr(importance, "to_dict") else {}

        # Calculate R-squared
        predictions = predictor.predict(df)
        ss_res = np.sum((df[target_col] - predictions) ** 2)
        ss_tot = np.sum((df[target_col] - df[target_col].mean()) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r_squared = 0.0 if np.isnan(r_squared) else float(r_squared)

        logger.info(f"Regression model trained, R-squared: {r_squared:.4f}")
        return predictor, importance_dict, float(r_squared)

    except Exception as e:
        logger.error(f"Failed to train regression model: {e}")
        return None, None, 0.0
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def extract_linear_coefficients(
    df: pd.DataFrame,
    target_col: str
) -> tuple[dict, float]:
    """
    Extract linear regression coefficients using sklearn as fallback.

    Args:
        df: DataFrame with features and target
        target_col: Name of target column

    Returns:
        Tuple of (coefficients dict, intercept)
    """
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler

    feature_cols = [c for c in df.columns if c != target_col]

    if not feature_cols:
        return {}, 0.0

    X = df[feature_cols].values
    y = df[target_col].values

    # Standardize features for comparable coefficients
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LinearRegression()
    model.fit(X_scaled, y)

    coefficients = {}
    for i, col in enumerate(feature_cols):
        coef = model.coef_[i]
        coefficients[col] = 0.0 if np.isnan(coef) else float(coef)

    intercept = model.intercept_
    return coefficients, 0.0 if np.isnan(intercept) else float(intercept)


async def run_regression_analysis(
    df: pd.DataFrame,
    target_col: str,
    feature_metadata: dict  # Maps column names to (machine_id, machine_name, topic, field)
) -> tuple[list[FeatureInfo], float, float, dict, int]:
    """
    Run complete regression analysis.

    Args:
        df: DataFrame with target and feature columns
        target_col: Name of target column
        feature_metadata: Metadata about each feature column

    Returns:
        Tuple of (features, intercept, r_squared, correlation_matrix, data_points)
    """
    if df.empty or target_col not in df.columns:
        return [], 0.0, 0.0, {}, 0

    # Calculate correlation matrix
    corr_matrix = calculate_correlation_matrix(df)

    # Calculate p-values
    p_values = calculate_p_values(df, target_col)

    # Train model and get importance
    predictor, importance_dict, r_squared = train_regression_model(
        df, target_col, settings.training_time_limit
    )

    # If insufficient data, return early with empty results
    if predictor is None:
        logger.info(f"Insufficient data for regression ({len(df)} points, need {settings.min_data_points})")
        return [], 0.0, 0.0, {}, len(df)

    # Get linear coefficients as fallback/supplement
    coefficients, intercept = extract_linear_coefficients(df, target_col)

    # Build feature info list
    features = []
    feature_cols = [c for c in df.columns if c != target_col]

    for col in feature_cols:
        meta = feature_metadata.get(col, {})

        # Get importance (use coefficient magnitude if AutoGluon importance unavailable)
        importance = None
        if importance_dict and col in importance_dict:
            importance = float(importance_dict[col].get("importance", 0))

        feature_info = FeatureInfo(
            machineId=meta.get("machine_id", ""),
            machineName=meta.get("machine_name"),
            topic=meta.get("topic", col.split(":")[1] if ":" in col else ""),
            field=meta.get("field", col.split(":")[-1] if ":" in col else col),
            coefficient=coefficients.get(col, 0.0),
            pValue=p_values.get(col),
            importance=importance
        )
        features.append(feature_info)

    # Sort by absolute coefficient value
    features.sort(key=lambda f: abs(f.coefficient), reverse=True)

    return features, intercept, r_squared, corr_matrix, len(df)


def simple_correlation_analysis(
    df: pd.DataFrame,
    target_col: str,
    feature_metadata: dict
) -> tuple[list[FeatureInfo], dict]:
    """
    Simple correlation analysis without AutoGluon (fallback).

    Args:
        df: DataFrame with columns
        target_col: Target column name
        feature_metadata: Feature metadata

    Returns:
        Tuple of (features sorted by correlation, correlation matrix)
    """
    if df.empty or target_col not in df.columns:
        return [], {}

    corr_matrix = calculate_correlation_matrix(df)
    p_values = calculate_p_values(df, target_col)

    features = []
    for col in df.columns:
        if col == target_col:
            continue

        meta = feature_metadata.get(col, {})
        correlation = corr_matrix.get(target_col, {}).get(col, 0.0)

        features.append(FeatureInfo(
            machineId=meta.get("machine_id", ""),
            machineName=meta.get("machine_name"),
            topic=meta.get("topic", ""),
            field=meta.get("field", col),
            coefficient=correlation,  # Use correlation as coefficient
            pValue=p_values.get(col),
            importance=abs(correlation)
        ))

    features.sort(key=lambda f: abs(f.coefficient), reverse=True)
    return features, corr_matrix


async def run_fast_linear_regression(
    df: pd.DataFrame,
    target_col: str,
    feature_metadata: dict
) -> tuple[list[FeatureInfo], float, float, dict, int]:
    """
    Run fast linear regression using sklearn only (no AutoGluon).

    This is much faster than the full regression analysis (~1 second vs ~2 minutes)
    and is suitable for custom regression where we just need linear coefficients.

    Args:
        df: DataFrame with target and feature columns
        target_col: Name of target column
        feature_metadata: Metadata about each feature column

    Returns:
        Tuple of (features, intercept, r_squared, correlation_matrix, data_points)
    """
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import r2_score

    if df.empty or target_col not in df.columns:
        return [], 0.0, 0.0, {}, 0

    feature_cols = [c for c in df.columns if c != target_col]
    if not feature_cols:
        return [], 0.0, 0.0, {}, 0

    # Calculate correlation matrix
    corr_matrix = calculate_correlation_matrix(df)

    # Calculate p-values
    p_values = calculate_p_values(df, target_col)

    # Fit linear regression
    X = df[feature_cols].values
    y = df[target_col].values

    model = LinearRegression()
    model.fit(X, y)

    # Calculate R-squared
    predictions = model.predict(X)
    r_squared = r2_score(y, predictions)
    r_squared = 0.0 if np.isnan(r_squared) else float(r_squared)

    # Build feature info list with actual coefficients (not standardized)
    features = []
    for i, col in enumerate(feature_cols):
        meta = feature_metadata.get(col, {})
        coef = model.coef_[i]
        coef_val = 0.0 if np.isnan(coef) else float(coef)

        feature_info = FeatureInfo(
            machineId=meta.get("machine_id", ""),
            machineName=meta.get("machine_name"),
            topic=meta.get("topic", col.split(":")[1] if ":" in col else ""),
            field=meta.get("field", col.split(":")[-1] if ":" in col else col),
            coefficient=coef_val,
            pValue=p_values.get(col),
            importance=abs(coef_val)
        )
        features.append(feature_info)

    # Sort by absolute coefficient value
    features.sort(key=lambda f: abs(f.coefficient), reverse=True)

    intercept = model.intercept_
    intercept_val = 0.0 if np.isnan(intercept) else float(intercept)
    logger.info(f"Fast linear regression completed, R-squared: {r_squared:.4f}")
    return features, intercept_val, r_squared, corr_matrix, len(df)
