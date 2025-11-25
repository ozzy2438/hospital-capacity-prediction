# Hospital Capacity Surge Prediction

This repository contains the predictive models and monitoring framework for forecasting hospital capacity surges (e.g. ICU and general beds) using hospital data, weather, and Google Trends.

## Overview
- Goal: Predict when hospital occupancy will exceed 95% capacity.
- Current best model: Logistic Regression (AUC-ROC ~0.96).
- Key predictors: 7-day average occupancy, previous day occupancy, flu bed usage, and weather/flu indicators.

## Structure
- model_documentation.txt: Detailed model performance summary and usage notes.
- retraining_plan.txt: Strategy for monitoring drift and retraining cadence.
- retrain.py: Script for scheduled retraining and candidate model generation.
- requirements.txt: Python dependencies.

## Getting Started
1. Install dependencies: pip install -r requirements.txt
2. Place your merged training data at data/merged_hospital_data.csv (or adjust DATA_PATH in retrain.py).
3. Run python retrain.py to train a candidate model.

## Monitoring & Retraining
See retraining_plan.txt for thresholds and recommended monthly/quarterly retrain logic.
