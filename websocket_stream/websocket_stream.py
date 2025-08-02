import asyncio  
import json  
import redis  
from datetime import datetime, timedelta  
from websockets import connect
import requests
import sys
import os
import time

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import (
        PAIRLIST, REDIS_HOST, REDIS_PORT, REDIS_DB,
        LIQUIDATION_URL, TRADE_URL_TEMPLATE, FUNDING_RATE_URL,
        AGGREGATION_INTERVAL_MINUTES, LARGE_TRADE_THRESHOLD_USD
    )
except ImportError:
    # Fallback to hardcoded values if config import fails
    print("Warning: Could not import config.py, using fallback values")
    PAIRLIST = [  
        "BTC/USDT", "ETH/USDT", "XRP/USDT", "SOL/USDT", "LINK/USDT",  
        "ADA/USDT", "TRX/USDT", "BNB/USDT", "SUI/USDT", "HBAR/USDT",  
        "LTC/USDT", "SUSHI/USDT", "UNI/USDT", "AVAX/USDT", "ALGO/USDT",  
        "ETC/USDT", "DOT/USDT", "FIL/USDT", "ARB/USDT", "BCH/USDT",  
        "WLD/USDT", "CRV/USDT", "NEAR/USDT", "XLM/USDT", "SAND/USDT",  
        "AAVE/USDT", "RENDER/USDT", "APT/USDT", "FTM/USDT", "OP/USDT"  
    ]
    REDIS_HOST, REDIS_PORT, REDIS_DB = 'redis', 6379, 0
    LIQUIDATION_URL = 'wss://fstream.binance.com/ws/!forceOrder@arr'  
    TRADE_URL_TEMPLATE = 'wss://stream.binance.com:9443/ws/{}@aggTrade'
    FUNDING_RATE_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
    AGGREGATION_INTERVAL_MINUTES = 1
    LARGE_TRADE_THRESHOLD_USD = 10000

# Redis-Verbindung with error handling
try:
    redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, 
                                   socket_connect_timeout=5, socket_timeout=5)
    # Test connection
    redis_client.ping()
    print("Redis connection established successfully")
except redis.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
    sys.exit(1)

# Aggregation Intervall
AGGREGATION_INTERVAL = timedelta(minutes=AGGREGATION_INTERVAL_MINUTES)  

# Speicher für Aggregation  
liquidation_data = {}  
trade_data = {}  

# Initialisiere Speicher für alle Symbole  
PAIRLIST_SYMBOLS = [pair.replace("/", "") for pair in PAIRLIST]  # Nur Symbole aus der PAIRLIST  
for symbol in PAIRLIST_SYMBOLS:  
    liquidation_data[symbol] = {"long_usd_size": 0, "short_usd_size": 0, "long_count": 0, "short_count": 0}  
    trade_data[symbol] = {"long_usd_size": 0, "short_usd_size": 0, "long_count": 0, "short_count": 0}  

# Set to track unknown symbols (to avoid spamming logs)  
unknown_symbols = set()  
def fetch_funding_rates():  
    """  
    Ruft die aktuellen Funding Rates von Binance ab.  
    """  
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(FUNDING_RATE_URL, timeout=10)  
            if response.status_code == 200:  
                data = response.json()  
                funding_rates = {}  
                for item in data:  
                    symbol = item['symbol']  
                    funding_rate = float(item['lastFundingRate'])  
                    funding_rates[symbol] = funding_rate  
                return funding_rates  
            else:  
                print(f"Error fetching funding rates: HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as e:
            print(f"Unexpected error fetching funding rates: {e}")
            break
    
    print("Failed to fetch funding rates after all retries")
    return {}  

async def fetch_and_store_funding_rates():  
    """  
    Ruft die Funding Rates ab und speichert sie in Redis.  
    """  
    while True:  
        funding_rates = fetch_funding_rates()  
        for symbol, rate in funding_rates.items():  
            if symbol in PAIRLIST_SYMBOLS:  
                redis_client.hset(f"funding_rate:{symbol}", mapping={  
                    "funding_rate": rate,  
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")  
                })  
        print("Funding rates updated in Redis.")  
        await asyncio.sleep(3600)  # Funding Rates alle 1 Stunde aktualisieren  

async def connect_with_retries(url, max_retries=5):  
    """Stellt eine WebSocket-Verbindung mit automatischen Reconnects her."""  
    print(f"Connecting to {url}")  
    retries = 0  
    while retries < max_retries:  
        try:  
            websocket = await connect(
                url, 
                ping_interval=20, 
                ping_timeout=10,
                close_timeout=10,
                max_size=2**20,  # 1MB max message size
                compression=None  # Disable compression for better performance
            )
            print(f"Successfully connected to {url}")  
            return websocket  
        except Exception as e:  
            retries += 1
            backoff_time = min(5 * (2 ** (retries - 1)), 60)  # Exponential backoff, max 60s
            print(f"WebSocket connection failed (attempt {retries}/{max_retries}): {e}")
            if retries < max_retries:
                print(f"Retrying in {backoff_time} seconds...")
                await asyncio.sleep(backoff_time)  
    raise Exception(f"Max retries ({max_retries}) reached. Could not connect to WebSocket: {url}")  

async def stream_liquidations():  
    """Stream Liquidationen und aggregiere sie."""  
    while True:  # Automatischer Reconnect bei Verbindungsabbruch  
        try:  
            async with await connect_with_retries(LIQUIDATION_URL) as websocket:  
                while True:  
                    try:  
                        msg = await websocket.recv()  
                        order_data = json.loads(msg)['o']  
                        symbol = order_data['s']  

                        # Verarbeite nur Symbole aus der PAIRLIST  
                        if symbol not in PAIRLIST_SYMBOLS:  
                            if symbol not in unknown_symbols:  
                                unknown_symbols.add(symbol)  
                                # print(f"Unknown symbol encountered: {symbol}")  
                            continue  

                        # print(f"Collecting liquidation data for symbol: {symbol}")  

                        side = order_data['S']  
                        price = float(order_data['p'])  
                        quantity = float(order_data['q'])  
                        usd_size = price * quantity  

                        # Aggregiere Liquidationen  
                        if side == "BUY":  # Long-Liquidation  
                            liquidation_data[symbol]["long_count"] += 1  
                            liquidation_data[symbol]["long_usd_size"] += usd_size  
                        else:  # Short-Liquidation  
                            liquidation_data[symbol]["short_count"] += 1  
                            liquidation_data[symbol]["short_usd_size"] += usd_size  

                    except Exception as e:  
                        print(f"Error in liquidation stream: {e}")  
                        await asyncio.sleep(5)  
        except Exception as e:  
            print(f"WebSocket connection error: {e}. Reconnecting...")  
            await asyncio.sleep(5)  

async def stream_large_trades():  
    """Stream große Trades und aggregiere sie."""  
    print('Getting trades')  
    tasks = []  
    for pair in PAIRLIST:  
        symbol = pair.replace("/", "").lower()  
        url = TRADE_URL_TEMPLATE.format(symbol)  
        tasks.append(stream_trades_for_pair(pair, url))  
    await asyncio.gather(*tasks)  

async def stream_trades_for_pair(pair, url):  
    """Stream Trades für ein einzelnes Paar."""  
    symbol = pair.replace("/", "")  
    while True:  # Automatischer Reconnect bei Verbindungsabbruch  
        try:  
            async with await connect_with_retries(url) as websocket:  
                while True:  
                    try:  
                        msg = await websocket.recv()  
                        trade_data_msg = json.loads(msg)  
                        price = float(trade_data_msg['p'])  
                        quantity = float(trade_data_msg['q'])  
                        usd_size = price * quantity  

                        # Aggregiere große Trades  
                        if usd_size > LARGE_TRADE_THRESHOLD_USD:  # Schwellenwert für große Trades  
                            if trade_data_msg['m']:  # Maker-Side: SELL -> Short-Trade  
                                trade_data[symbol]["short_count"] += 1  
                                trade_data[symbol]["short_usd_size"] += usd_size  
                            else:  # Maker-Side: BUY -> Long-Trade  
                                trade_data[symbol]["long_count"] += 1  
                                trade_data[symbol]["long_usd_size"] += usd_size  

                    except Exception as e:  
                        print(f"Error in trade stream for {pair}: {e}")  
                        await asyncio.sleep(5)  
        except Exception as e:  
            print(f"WebSocket connection error for {pair}: {e}. Reconnecting...")  
            await asyncio.sleep(5)  

async def aggregate_and_store():  
    """Aggregiere Daten und speichere sie in Redis."""  
    while True:  
        await asyncio.sleep(AGGREGATION_INTERVAL.total_seconds())  
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")  

        # Speichere Liquidationen  
        for symbol, data in liquidation_data.items():  
            redis_client.hset(f"liquidation:{symbol}", mapping={  
                "timestamp": timestamp,  
                "long_count": data["long_count"],  
                "short_count": data["short_count"],  
                "long_usd_size": data["long_usd_size"],  
                "short_usd_size": data["short_usd_size"]  
            })  
            # Zurücksetzen der Aggregation  
            liquidation_data[symbol] = {"long_usd_size": 0, "short_usd_size": 0, "long_count": 0, "short_count": 0}  

        # Speichere große Trades  
        for symbol, data in trade_data.items():  
            redis_client.hset(f"large_trade:{symbol}", mapping={  
                "timestamp": timestamp,  
                "long_count": data["long_count"],  
                "short_count": data["short_count"],  
                "long_usd_size": data["long_usd_size"],  
                "short_usd_size": data["short_usd_size"]  
            })  
            # Zurücksetzen der Aggregation  
            trade_data[symbol] = {"long_usd_size": 0, "short_usd_size": 0, "long_count": 0, "short_count": 0}  

        print(f"Aggregated data stored at {timestamp}")  

async def main():  
    """Starte alle Streams und die Aggregation."""  
    print('############################### Starting streams and aggregation ###############################')  
    await asyncio.gather(  
        stream_liquidations(),  
        stream_large_trades(),  
        aggregate_and_store(),
        fetch_and_store_funding_rates() 
    )  

asyncio.run(main())  