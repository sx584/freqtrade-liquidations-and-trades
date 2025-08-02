# Freqtrade Liquidations and Trades Data Collection

This project launches Freqtrade with a Redis server to collect liquidation and trade data from Binance WebSocket streams. The data is stored in CSV format and can be accessed by Freqtrade, with the most recent data fetched from Redis.

**⚠️ Educational Purpose Only**: This project is for educational purposes and should not be used in live trading.

## Architecture

The system consists of four main components:

1. **WebSocket Stream Service** (`websocket_stream/`): Connects to Binance WebSocket to collect liquidation and trade data
2. **CSV Writer Service** (`csv_writer/`): Writes aggregated data from Redis to CSV files
3. **Redis**: In-memory data store for real-time data exchange
4. **Freqtrade**: Trading bot that uses the collected data via the `LiquidationStrategy`

## Recent Bug Fixes and Improvements

### 🐛 **Critical Bugs Fixed:**
- **Fixed CSV path mismatch** between csv_writer.py and Docker volume mount
- **Fixed Docker volume mount inconsistencies** in docker-compose.yaml
- **Eliminated PAIRLIST duplication** by creating shared configuration
- **Fixed timing synchronization** between services

### 🚀 **Improvements Made:**
- **Enhanced error handling** with retry logic and exponential backoff
- **Added Redis connection validation** with proper timeout handling
- **Improved WebSocket reliability** with better connection parameters
- **Added Docker health checks** for better service monitoring
- **Centralized configuration** in `config.py` to avoid hardcoded values
- **Better data validation** in CSV writer to prevent empty rows
- **Added restart policies** for Docker containers

### 📝 **Configuration Management:**
- All shared configuration is now centralized in `config.py`
- Environment variables supported for flexible deployment
- Fallback values ensure system works even if config import fails

## Quick Start

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository>
   cd freqtrade_redis_ws
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Monitor logs:**
   ```bash
   docker-compose logs -f
   ```

4. **Stop services:**
   ```bash
   docker-compose down
   ```

## Configuration

### Environment Variables
- `CSV_FILE_PATH`: Custom path for CSV output file
- `REDIS_HOST`: Redis server hostname (default: redis)
- `REDIS_PORT`: Redis server port (default: 6379)

### Customizing Trading Pairs
Edit `config.py` to modify the `PAIRLIST` array with your desired trading pairs.

## Data Structure

The CSV file contains the following columns:
- `symbol`: Trading pair symbol
- `timestamp`: Data timestamp
- `liq_long_count`: Number of long liquidations
- `liq_short_count`: Number of short liquidations  
- `liq_long_usd_size`: USD value of long liquidations
- `liq_short_usd_size`: USD value of short liquidations
- `trade_long_count`: Number of large long trades
- `trade_short_count`: Number of large short trades
- `trade_long_usd_size`: USD value of large long trades
- `trade_short_usd_size`: USD value of large short trades
- `funding_rate`: Current funding rate

## Known Limitations

- Data aggregation interval is currently fixed at 1 minute
- Large trade threshold is set to $10,000 USD
- First data collection round may return empty data
- Comments in some files are in German

## Troubleshooting

### Common Issues:
1. **Redis connection failed**: Ensure Redis container is healthy
2. **WebSocket connection issues**: Check internet connectivity and Binance API status
3. **CSV file not created**: Verify volume mounts and file permissions
4. **Empty data in CSV**: Wait for market activity or check WebSocket connections

### Health Checks:
```bash
# Check Redis health
docker exec redis redis-cli ping

# Check service logs
docker-compose logs websocket_stream
docker-compose logs csv_writer
```

## Development

### File Structure:
```
├── config.py                 # Shared configuration
├── docker-compose.yaml       # Service orchestration
├── websocket_stream/         # WebSocket data collection
│   ├── Dockerfile
│   └── websocket_stream.py
├── csv_writer/              # CSV data writer
│   ├── Dockerfile
│   └── csv_writer.py
└── freqtrade/              # Trading bot
    ├── Dockerfile
    └── user_data/
        └── strategies/
            └── LiquidationStrategy.py
```

### Adding New Features:
1. Update `config.py` for new configuration options
2. Modify the appropriate service (websocket_stream or csv_writer)
3. Update Docker containers and test

## License

This project is for educational purposes only. Use at your own risk.
