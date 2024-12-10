import csv  
import time  
import redis  
import os  # Für die Verzeichnisprüfung  

# Pairlist  
PAIRLIST = [  
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "SOL/USDT", "LINK/USDT",  
    "ADA/USDT", "TRX/USDT", "BNB/USDT", "SUI/USDT", "HBAR/USDT",  
    "LTC/USDT", "SUSHI/USDT", "UNI/USDT", "AVAX/USDT", "ALGO/USDT",  
    "ETC/USDT", "DOT/USDT", "FIL/USDT", "ARB/USDT", "BCH/USDT",  
    "WLD/USDT", "CRV/USDT", "NEAR/USDT", "XLM/USDT", "SAND/USDT",  
    "AAVE/USDT", "RENDER/USDT", "APT/USDT", "FTM/USDT", "OP/USDT"  
]  

# Redis-Verbindung  
redis_client = redis.StrictRedis(host='redis', port=6379, db=0)  

# Pfad zur CSV-Datei  
csv_file_path = './freqtrade_redis_ws/freqtrade/user_data/strategies/market_data.csv'  

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

                if liquidation_data or trade_data or funding_data:  
                    print(f"Writing data for {symbol} to CSV...")  
                    writer.writerow([  
                        symbol,  
                        liquidation_data.get(b'timestamp', b'').decode('utf-8'),  
                        int(liquidation_data.get(b'long_count', b'0').decode('utf-8')),  
                        int(liquidation_data.get(b'short_count', b'0').decode('utf-8')),  
                        float(liquidation_data.get(b'long_usd_size', b'0').decode('utf-8')),  
                        float(liquidation_data.get(b'short_usd_size', b'0').decode('utf-8')),  
                        int(trade_data.get(b'long_count', b'0').decode('utf-8')),  
                        int(trade_data.get(b'short_count', b'0').decode('utf-8')),  
                        float(trade_data.get(b'long_usd_size', b'0').decode('utf-8')),  
                        float(trade_data.get(b'short_usd_size', b'0').decode('utf-8')),  
                        float(funding_data.get(b'funding_rate', b'0').decode('utf-8'))  
                    ])  
                    file.flush()  
                    print(f"Data for {symbol} written to CSV.")
                else:  
                    print(f"No data for {symbol} to write to CSV.")  

            # Alle 5 Minuten speichern  
            print("Sleeping for 1 minutes...")  
            time.sleep(60)  

try:  
    write_to_csv()  
except Exception as e:  
    print(f"Error in CSV Writer: {e}")  