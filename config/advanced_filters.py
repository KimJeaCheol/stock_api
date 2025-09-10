ADVANCED_FILTERS = {
    "monday": {
        "returnOnEquityTTM": (">", 0.12),
        "dividendYieldTTM": (">", 0.02),
        "debtToAssetsRatioTTM": ("<", 1.0)
    },
    "tuesday": {
        "returnOnEquityTTM": (">", 0.1),
        "priceEarningsRatioTTM": ("<", 15),
        "dividendYieldTTM": (">", 0.03)
    },
    "wednesday": {
        "returnOnEquityTTM": (">", 0.1),
        "debtToAssetsRatioTTM": ("<", 1.5)
    },
    "thursday": {
        "returnOnEquityTTM": (">", 0.15),
        "revenueGrowthTTM": (">", 0.1)
    },
    "friday": {
        "returnOnEquityTTM": (">", 0.12),
        "dividendYieldTTM": (">", 0.02)
    }
}
