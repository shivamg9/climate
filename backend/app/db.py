from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class ClimateDatabase:
    def __init__(self, mongodb_uri: str, database_name: str):
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.mongodb_uri)
            self.db = self.client[self.database_name]

            # Verify connection
            await self.client.admin.command('ping')
            logger.info("Connected to MongoDB")

            # Create indexes
            await self._create_indexes()

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    async def _create_indexes(self):
        """Create necessary indexes for performance"""
        try:
            # Daily weather collection: composite index on cell_key and year range
            daily_weather = self.db.daily_weather
            await daily_weather.create_index([
                ("cell_key", 1),
                ("start_year", 1),
                ("end_year", 1)
            ], unique=True)

            # TTL index for automatic cache expiration (30 days)
            await daily_weather.create_index(
                [("fetched_at", 1)],
                expireAfterSeconds=30 * 24 * 60 * 60  # 30 days
            )

            # Hazard summaries collection
            hazard_summaries = self.db.hazard_summaries
            await hazard_summaries.create_index([
                ("cell_key", 1),
                ("start_year", 1),
                ("end_year", 1),
                ("hazard_type", 1)
            ], unique=True)

            logger.info("Database indexes created")

        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")

    async def store_daily_weather(
        self,
        cell_key: str,
        start_year: int,
        end_year: int,
        temperature_data: List[Dict[str, Any]],
        data_quality: Optional[Dict[str, Any]] = None,
        fetched_at: Optional[datetime] = None
    ):
        """Store daily weather data in cache"""
        if fetched_at is None:
            fetched_at = datetime.utcnow()

        document = {
            "cell_key": cell_key,
            "start_year": start_year,
            "end_year": end_year,
            "temperature_data": temperature_data,
            "fetched_at": fetched_at
        }

        if data_quality:
            document["data_quality"] = data_quality

        try:
            await self.db.daily_weather.replace_one(
                {
                    "cell_key": cell_key,
                    "start_year": start_year,
                    "end_year": end_year
                },
                document,
                upsert=True
            )
            logger.debug(f"Stored daily weather for cell {cell_key}, {start_year}-{end_year}")
        except Exception as e:
            logger.error(f"Error storing daily weather: {e}")
            raise

    async def get_daily_weather(
        self,
        cell_key: str,
        start_year: int,
        end_year: int
    ) -> Optional[Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]]:
        """Retrieve daily weather data from cache"""
        try:
            document = await self.db.daily_weather.find_one({
                "cell_key": cell_key,
                "start_year": start_year,
                "end_year": end_year
            })

            if document:
                logger.debug(f"Cache hit for cell {cell_key}, {start_year}-{end_year}")
                return document["temperature_data"], document.get("data_quality")
            else:
                logger.debug(f"Cache miss for cell {cell_key}, {start_year}-{end_year}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving daily weather: {e}")
            return None

    async def store_hazard_summary(
        self,
        cell_key: str,
        start_year: int,
        end_year: int,
        hazard_type: str,
        yearly_results: List[Dict[str, Any]],
        trend_data: Dict[str, Any],
        computed_at: Optional[datetime] = None
    ):
        """Store hazard summary results"""
        if computed_at is None:
            computed_at = datetime.utcnow()

        document = {
            "cell_key": cell_key,
            "start_year": start_year,
            "end_year": end_year,
            "hazard_type": hazard_type,
            "yearly_results": yearly_results,
            "trend_data": trend_data,
            "computed_at": computed_at
        }

        try:
            await self.db.hazard_summaries.replace_one(
                {
                    "cell_key": cell_key,
                    "start_year": start_year,
                    "end_year": end_year,
                    "hazard_type": hazard_type
                },
                document,
                upsert=True
            )
            logger.debug(f"Stored hazard summary for cell {cell_key}, {start_year}-{end_year}")
        except Exception as e:
            logger.error(f"Error storing hazard summary: {e}")
            raise

    async def get_hazard_summary(
        self,
        cell_key: str,
        start_year: int,
        end_year: int,
        hazard_type: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve hazard summary from cache"""
        try:
            document = await self.db.hazard_summaries.find_one({
                "cell_key": cell_key,
                "start_year": start_year,
                "end_year": end_year,
                "hazard_type": hazard_type
            })

            if document:
                logger.debug(f"Cache hit for hazard summary: {cell_key}, {start_year}-{end_year}")
                return {
                    "yearly_results": document["yearly_results"],
                    "trend_data": document["trend_data"]
                }
            else:
                logger.debug(f"Cache miss for hazard summary: {cell_key}, {start_year}-{end_year}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving hazard summary: {e}")
            return None

    async def health_check(self) -> bool:
        """Check database connection health"""
        try:
            if self.client:
                await self.client.admin.command('ping')
                return True
            return False
        except Exception:
            return False

# Global database instance
db_instance: Optional[ClimateDatabase] = None

async def get_database() -> ClimateDatabase:
    """Get database instance (singleton pattern)"""
    global db_instance
    if db_instance is None:
        # In a real app, this would come from config
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return db_instance

async def init_db(mongodb_uri: str, database_name: str):
    """Initialize database connection"""
    global db_instance
    db_instance = ClimateDatabase(mongodb_uri, database_name)
    await db_instance.connect()
    return db_instance

async def close_db():
    """Close database connection"""
    global db_instance
    if db_instance:
        await db_instance.disconnect()
        db_instance = None