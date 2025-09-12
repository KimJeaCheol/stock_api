#주식 API 서버

## Overview

This API server provides stock market data and analysis.

## Setup

1. Create conda environment:

```bash
conda create -n stocksfastapi python=3.9
conda activate stocksfastapi
```

## Dependencies

```bash
pip install fastapi
pip install uvicorn
```

## Running the Server

```bash
uvicorn main:app --reload
```

## API Endpoints

- `/stocks` - Get list of available stocks
- `/stock/{symbol}` - Get stock details
- `/analysis/{symbol}` - Get stock analysis
