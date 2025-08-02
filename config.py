# Shared configuration for the freqtrade liquidation system

# Trading pairs to monitor
PAIRLIST = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "SOL/USDT", "LINK/USDT",
    "ADA/USDT", "TRX/USDT", "BNB/USDT", "SUI/USDT", "HBAR/USDT",
    "LTC/USDT", "SUSHI/USDT", "UNI/USDT", "AVAX/USDT", "ALGO/USDT",
    "ETC/USDT", "DOT/USDT", "FIL/USDT", "ARB/USDT", "BCH/USDT",
    "WLD/USDT", "CRV/USDT", "NEAR/USDT", "XLM/USDT", "SAND/USDT",
    "AAVE/USDT", "RENDER/USDT", "APT/USDT", "FTM/USDT", "OP/USDT"
]

# Redis configuration
REDIS_HOST = 'redis'
REDIS_PORT = 6379
REDIS_DB = 0

# WebSocket URLs
LIQUIDATION_URL = 'wss://fstream.binance.com/ws/!forceOrder@arr'
TRADE_URL_TEMPLATE = 'wss://stream.binance.com:9443/ws/{}@aggTrade'

# Binance API URLs
FUNDING_RATE_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"

# Aggregation settings
AGGREGATION_INTERVAL_MINUTES = 1
LARGE_TRADE_THRESHOLD_USD = 10000

# File paths
DEFAULT_CSV_PATH = '/home/olav/freqtrade_redis_ws/freqtrade/user_data/strategies/market_data.csv'