# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Dict, Optional, Union, Tuple

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,  # @informative decorator
    # Hyperopt Parameters
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    # timeframe helpers
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    # Strategy helper functions
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta
from technical import qtpylib
import redis
import os
import technical.indicators as ftt

class LiquidationStrategy(IStrategy):  
    def __init__(self, config: dict) -> None:  
        super().__init__(config)  
        # Redis-Verbindung herstellen  
        self.redis_client = redis.StrictRedis(host='redis', port=6379, db=0)  
        print("Redis connection established")  

        
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy.
    timeframe = "1m"

    # Can this strategy go short?
    can_short: bool = True

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 1
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.99

    # Trailing stoploss
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 100

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False
    }

    # Optional order time in force.
    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC"
    }
    @property
    def plot_config(self):
        return {
            # Main plot indicators (Moving averages, ...)
            "main_plot": {
                "tema": {},
                "sar": {"color": "white"},
            },
            "subplots": {
                # Subplots - each dict defines one additional plot
                "MACD": {
                    "macd": {"color": "blue"},
                    "macdsignal": {"color": "orange"},
                },
                "RSI": {
                    "rsi": {"color": "red"},
                }
            }
        }

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []  

    def bybit_to_binance_pair(self, bybit_pair: str) -> str:  
        """  
        Konvertiert ein Bybit-Paar (z. B. BTC/USDT:USDT) in das Binance-Format (z. B. BTCUSDT).  
        """  
        return bybit_pair.replace("/", "").replace(":USDT", "")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  
        """  
        Diese Methode fügt die Liquidations- und großen Trade-Daten aus Redis und der CSV-Datei in den DataFrame ein.  
        """  
        # Binance-Symbol aus dem Freqtrade-Pair ableiten  
        bybit_pair = metadata['pair']  
        binance_pair = self.bybit_to_binance_pair(bybit_pair)  

        # Pfad zur CSV-Datei  
        csv_file_path = '/freqtrade/user_data/strategies/market_data.csv'  

        # 1. Historische Daten aus der CSV-Datei laden  
        if os.path.exists(csv_file_path):  
            print(f"Lade historische Daten aus {csv_file_path}...")  
            if os.access(csv_file_path, os.R_OK):  
                # print(f"Zugriff auf die Datei ist möglich: {csv_file_path}")  
                try:  
                    # CSV-Datei laden  
                    historical_data = pd.read_csv(csv_file_path)  
                    # print(f"CSV-Daten geladen: {len(historical_data)} Zeilen gefunden.")  

                    # Sicherstellen, dass die Spalte 'timestamp' existiert  
                    if 'timestamp' not in historical_data.columns:  
                        raise KeyError("Die Spalte 'timestamp' fehlt in der CSV-Datei.")  

                    # Filtere die Daten für das aktuelle Symbol  
                    historical_data = historical_data[historical_data['symbol'] == binance_pair]  
                    # print(f"Gefilterte Daten für {binance_pair}: {len(historical_data)} Zeilen gefunden.")  

                    # Sicherstellen, dass der Timestamp als Datumsformat vorliegt  
                    historical_data['timestamp'] = pd.to_datetime(historical_data['timestamp'], errors='coerce')  
                    if historical_data['timestamp'].isnull().any():  
                        raise ValueError("Ungültige Werte in der Spalte 'timestamp' in der CSV-Datei.")  

                    # Runden der Timestamps auf die Minute  
                    historical_data['timestamp'] = historical_data['timestamp'].dt.floor('min')  

                    # Zeitzoneninformation hinzufügen (UTC)  
                    historical_data['timestamp'] = historical_data['timestamp'].dt.tz_localize('UTC')  

                    # Sicherstellen, dass die Spalte 'date' im DataFrame als Datumsformat vorliegt  
                    if 'date' in dataframe.columns:  
                        dataframe['date'] = pd.to_datetime(dataframe['date'], errors='coerce')  
                        if dataframe['date'].isnull().any():  
                            raise ValueError("Ungültige Werte in der Spalte 'date' im DataFrame.")  

                        # Runden der Timestamps auf die Minute  
                        dataframe['date'] = dataframe['date'].dt.floor('min')  

                    # Debugging: Zeige die ersten paar Timestamps aus beiden DataFrames  
                    # print("Erste Timestamps in historical_data:", historical_data['timestamp'].head())  
                    # print("Erste Timestamps im dataframe (date):", dataframe['date'].head())  

                    # Überprüfen, ob es Übereinstimmungen gibt  
                    common_timestamps = set(dataframe['date']).intersection(set(historical_data['timestamp']))  
                    if not common_timestamps:  
                        print("Warnung: Keine gemeinsamen Timestamps zwischen dataframe und historical_data gefunden!")  
                        print("Timestamps im dataframe (date):", dataframe['date'].unique())  
                        print("Timestamps in historical_data:", historical_data['timestamp'].unique())  

                    # Mappen der historischen Daten auf den bestehenden DataFrame basierend auf dem Timestamp  
                    for col in ['liq_long_count', 'liq_short_count', 'liq_long_usd_size', 'liq_short_usd_size',  
                                'trade_long_count', 'trade_short_count', 'trade_long_usd_size', 'trade_short_usd_size',  
                                'funding_rate']:  
                        if col in historical_data.columns:  
                            # Werte basierend auf dem Timestamp übernehmen  
                            dataframe[col] = dataframe['date'].map(  
                                historical_data.set_index('timestamp')[col]  
                            ).fillna(0.0)  # Fehlende Werte mit 0.0 auffüllen  
                        else:  
                            dataframe[col] = 0.0  # Falls die Spalte fehlt, mit 0.0 auffüllen  

                except Exception as e:  
                    print(f"Fehler beim Lesen der CSV-Datei: {e}")  
            else:  
                print(f"Keine Leseberechtigung für die Datei: {csv_file_path}")  
        else:  
            print(f"CSV-Datei {csv_file_path} nicht gefunden. Historische Daten werden übersprungen.")  

        # 2. Aktuelle Daten aus Redis abrufen und in die letzte Zeile einfügen  
        # Liquidationsdaten aus Redis abrufen  
        liquidation_key = f"liquidation:{binance_pair}"  
        liquidation_data = self.redis_client.hgetall(liquidation_key)  
        if liquidation_data:  
            dataframe.loc[dataframe.index[-1], 'liq_long_count'] = int(liquidation_data.get(b'long_count', b'0').decode('utf-8'))  
            dataframe.loc[dataframe.index[-1], 'liq_short_count'] = int(liquidation_data.get(b'short_count', b'0').decode('utf-8'))  
            dataframe.loc[dataframe.index[-1], 'liq_long_usd_size'] = float(liquidation_data.get(b'long_usd_size', b'0').decode('utf-8'))  
            dataframe.loc[dataframe.index[-1], 'liq_short_usd_size'] = float(liquidation_data.get(b'short_usd_size', b'0').decode('utf-8'))  
        else:  
            dataframe.loc[dataframe.index[-1], 'liq_long_count'] = 0  
            dataframe.loc[dataframe.index[-1], 'liq_short_count'] = 0  
            dataframe.loc[dataframe.index[-1], 'liq_long_usd_size'] = 0.0  
            dataframe.loc[dataframe.index[-1], 'liq_short_usd_size'] = 0.0  

        # Große Trades aus Redis abrufen  
        trade_key = f"large_trade:{binance_pair}"  
        trade_data = self.redis_client.hgetall(trade_key)  
        if trade_data:  
            dataframe.loc[dataframe.index[-1], 'trade_long_count'] = int(trade_data.get(b'long_count', b'0').decode('utf-8'))  
            dataframe.loc[dataframe.index[-1], 'trade_short_count'] = int(trade_data.get(b'short_count', b'0').decode('utf-8'))  
            dataframe.loc[dataframe.index[-1], 'trade_long_usd_size'] = float(trade_data.get(b'long_usd_size', b'0').decode('utf-8'))  
            dataframe.loc[dataframe.index[-1], 'trade_short_usd_size'] = float(trade_data.get(b'short_usd_size', b'0').decode('utf-8'))  
        else:  
            dataframe.loc[dataframe.index[-1], 'trade_long_count'] = 0  
            dataframe.loc[dataframe.index[-1], 'trade_short_count'] = 0  
            dataframe.loc[dataframe.index[-1], 'trade_long_usd_size'] = 0.0  
            dataframe.loc[dataframe.index[-1], 'trade_short_usd_size'] = 0.0  

        # Funding Rate aus Redis abrufen  
        funding_key = f"funding_rate:{binance_pair}"  
        funding_data = self.redis_client.hgetall(funding_key)  
        if funding_data:  
            dataframe.loc[dataframe.index[-1], 'funding_rate'] = float(funding_data.get(b'funding_rate', b'0').decode('utf-8'))  
        else:  
            dataframe.loc[dataframe.index[-1], 'funding_rate'] = 0.0  

        dataframe["y_funding_rates"] = (dataframe["funding_rate"] * 3 * 365) * 100 

        ################################ Hier beginnt die eigene Strategie ################################
        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]
        dataframe["bb_percent"] = (
            (dataframe["close"] - dataframe["bb_lowerband"]) /
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"])
        )
        dataframe["bb_width"] = (
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        )

        bollinger2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=1)
        dataframe["bb_lowerband2"] = bollinger2["lower"]
        dataframe["bb_middleband2"] = bollinger2["mid"]
        dataframe["bb_upperband2"] = bollinger2["upper"]
        dataframe["bb_percent2"] = (
            (dataframe["close"] - dataframe["bb_lowerband2"]) /
            (dataframe["bb_upperband2"] - dataframe["bb_lowerband2"])
        )
        dataframe["bb_width2"] = (
            (dataframe["bb_upperband2"] - dataframe["bb_lowerband2"]) / dataframe["bb_middleband2"]
        )

        dataframe["liq_long_count_60"] = dataframe["liq_long_count"].rolling(60).sum()
        dataframe["liq_short_count_60"] = dataframe["liq_short_count"].rolling(60).sum()
        dataframe["liq_long_usd_size_60"] = dataframe["liq_long_usd_size"].rolling(60).sum()
        dataframe["liq_short_usd_size_60"] = dataframe["liq_short_usd_size"].rolling(60).sum()

        dataframe["trade_long_count_60"] = dataframe["trade_long_count"].rolling(60).sum()
        dataframe["trade_short_count_60"] = dataframe["trade_short_count"].rolling(60).sum()
        dataframe["trade_long_usd_size_60"] = dataframe["trade_long_usd_size"].rolling(60).sum()
        dataframe["trade_short_usd_size_60"] = dataframe["trade_short_usd_size"].rolling(60).sum()

        dataframe["vwma20"] = ftt.vwma(dataframe, 20, "close")
        dataframe["vwma41"] = ftt.vwma(dataframe, 41, "close")
        dataframe["vwma75"] = ftt.vwma(dataframe, 75, "close")

        dataframe["sma20"] = ta.SMA(dataframe, timeperiod=20)
        dataframe["sma41"] = ta.SMA(dataframe, timeperiod=41)
        dataframe["sma75"] = ta.SMA(dataframe, timeperiod=75)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[
            (
                (dataframe["volume"] < 0)  # Make sure Volume is not 0
            ),
            "enter_long"] = 1
        
        dataframe.loc[
            (
                (dataframe['volume'] < -20)  # Make sure Volume is not 0
            ),
            'enter_short'] = 1
        

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe["volume"] == -50)
            ),
            "exit_long"] = 1
        
        dataframe.loc[
            (
                (dataframe['volume'] == -80)  # Make sure Volume is not 0
            ),
            'exit_short'] = 1
        
        return dataframe