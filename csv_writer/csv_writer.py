import csv  
import time  
import redis  
import os  # Für die Verzeichnisprüfung
import sys

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import (
        PAIRLIST, REDIS_HOST, REDIS_PORT, REDIS_DB, DEFAULT_CSV_PATH
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
    DEFAULT_CSV_PATH = '/home/olav/freqtrade_redis_ws/freqtrade/user_data/strategies/market_data.csv'

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

# Pfad zur CSV-Datei - using environment variable or default
csv_file_path = os.getenv('CSV_FILE_PATH', DEFAULT_CSV_PATH)  

def write_to_csv():  
    """Schreibe Redis-Daten in eine CSV-Datei."""  
    print("CSV Writer started...")  

    csv_dir = os.path.dirname(csv_file_path)  

    # Verzeichnis erstellen, falls es nicht existiert  
    if not os.path.exists(csv_dir):  
        print(f"Directory {csv_dir} does not exist. Creating it...")  
        os.makedirs(csv_dir)  

    # Überprüfen, ob die Datei existiert  
    file_exists = os.path.exists(csv_file_path)  

    # Datei im Anhängemodus öffnen  
    with open(csv_file_path, mode='a', newline='') as file:  
        print(f"CSV file opened for writing at {csv_file_path}...")  
        writer = csv.writer(file)  

        # Schreibe Header nur, wenn die Datei noch nicht existiert  
        if not file_exists:  
            writer.writerow([  
                'symbol', 'timestamp',  
                'liq_long_count', 'liq_short_count', 'liq_long_usd_size', 'liq_short_usd_size',  
                'trade_long_count', 'trade_short_count', 'trade_long_usd_size', 'trade_short_usd_size',  
                'funding_rate'  
            ])  
            print("CSV header written...")  
        else:  
            print("CSV file already exists. Header not written.")   

        while True:  
            for pair in PAIRLIST:  
                symbol = pair.replace("/", "")  

                # Liquidationsdaten abrufen  
                liquidation_data = redis_client.hgetall(f"liquidation:{symbol}")  
                trade_data = redis_client.hgetall(f"large_trade:{symbol}")  
                funding_data = redis_client.hgetall(f"funding_rate:{symbol}")  

                print(f"Checking data for {symbol}...")  
                print(f"Liquidation data: {liquidation_data}")  
                print(f"Trade data: {trade_data}")  
                print(f"Funding data: {funding_data}")  

                # Only write if we have meaningful data (not just empty or zero values)
                has_meaningful_data = (
                    (liquidation_data and any(float(liquidation_data.get(k, b'0').decode('utf-8')) > 0 
                                            for k in [b'long_count', b'short_count', b'long_usd_size', b'short_usd_size'])) or
                    (trade_data and any(float(trade_data.get(k, b'0').decode('utf-8')) > 0 
                                      for k in [b'long_count', b'short_count', b'long_usd_size', b'short_usd_size'])) or
                    (funding_data and funding_data.get(b'funding_rate'))
                )
                
                if has_meaningful_data:  
                    try:
                        print(f"Writing data for {symbol} to CSV...")
                        # Safe value extraction with error handling
                        def safe_decode_float(data_dict, key, default='0'):
                            try:
                                return float(data_dict.get(key, default.encode()).decode('utf-8'))
                            except (ValueError, AttributeError):
                                return 0.0
                        
                        def safe_decode_int(data_dict, key, default='0'):
                            try:
                                return int(data_dict.get(key, default.encode()).decode('utf-8'))
                            except (ValueError, AttributeError):
                                return 0
                        
                        def safe_decode_str(data_dict, key, default=''):
                            try:
                                return data_dict.get(key, default.encode()).decode('utf-8')
                            except AttributeError:
                                return default
                        
                        writer.writerow([  
                            symbol,  
                            safe_decode_str(liquidation_data, b'timestamp') or safe_decode_str(trade_data, b'timestamp'),
                            safe_decode_int(liquidation_data, b'long_count'),  
                            safe_decode_int(liquidation_data, b'short_count'),  
                            safe_decode_float(liquidation_data, b'long_usd_size'),  
                            safe_decode_float(liquidation_data, b'short_usd_size'),  
                            safe_decode_int(trade_data, b'long_count'),  
                            safe_decode_int(trade_data, b'short_count'),  
                            safe_decode_float(trade_data, b'long_usd_size'),  
                            safe_decode_float(trade_data, b'short_usd_size'),  
                            safe_decode_float(funding_data, b'funding_rate')  
                        ])  
                        file.flush()  
                        print(f"Data for {symbol} written to CSV.")
                    except Exception as e:
                        print(f"Error writing data for {symbol}: {e}")
                else:  
                    print(f"No meaningful data for {symbol} to write to CSV.")  

            # Wait for next minute boundary to synchronize with aggregation
            current_time = time.time()
            seconds_until_next_minute = 60 - (current_time % 60)
            print(f"Sleeping for {seconds_until_next_minute:.1f} seconds until next minute...")  
            time.sleep(seconds_until_next_minute)  

try:  
    write_to_csv()  
except Exception as e:  
    print(f"Error in CSV Writer: {e}")  