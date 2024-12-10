# freqtrade liquidations and trades
 Launches Freqtrade and a Redis Server to collect data of Liquidations and trades from Binance Websocket. The data is stored in a CSV and can be accessed by Freqtrade. The most recent data is fetched from Redis. 
 
 This is just for educational purpose and shouldnt be used in livetrading (:


Known errors and flaws:
- Timeframe and csv-Location are hardcoded
- First round can return empty data, which Freqtarde doesnt like. You must clean this row from hand
- Comments are mostly german
- Funding rate looks weird
