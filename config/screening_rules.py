WEEKLY_SCREENING_RULES = {
    "monday": {
        "sector": "Consumer Defensive",
        "betaLowerThan": 0.8,
        "marketCapMoreThan": 10000000000,
        "dividendMoreThan": 0.02,
        "isActivelyTrading": "true",
        "isEtf": "false",
        "isFund": "false",
        "country": "US",
        "limit": 2
    },
    "tuesday": {
        "sector": "Financial Services",
        "dividendMoreThan": 0.03,
        "marketCapMoreThan": 5000000000,
        "isActivelyTrading": "true",
        "isEtf": "false",
        "isFund": "false",        
        "country": "US",
        "limit": 2
    },
    "wednesday": {
        "sector": "Energy",
        "marketCapMoreThan": 5000000000,
        "volumeMoreThan": 500000,
        "betaMoreThan": 1.0,
        "isActivelyTrading": "true",
        "country": "US",
        "limit": 2
    },
    "thursday": {
        "sector": "Technology",
        "marketCapMoreThan": 5000000000,
        "isActivelyTrading": "true",
        "country": "US",
        "limit": 2
    },
    "friday": {
        "sector": "Healthcare",
        "marketCapMoreThan": 5000000000,
        "isActivelyTrading": "true",
        "country": "US",
        "limit": 3
    },
}
