"""
MQTT History Injector for Home Assistant

This addon subscribes to MQTT topics containing historical sensor data,
creates entities if they don't exist, and injects data directly into 
the Home Assistant history database, preserving the original timestamps.

Expected MQTT payload format:
{
    "state": "23.5",
    "timestamp": "2023-04-15T02:30:00",
    "attributes": {
        "unit_of_measurement": "°C",
        "friendly_name": "Bedroom Temperature"
    }
}

You can also send multiple records at once:
{
    "records": [
        {
            "state": "23.5", 
            "timestamp": "2023-04-15T02:30:00",
            "attributes": {"unit_of_measurement": "°C", "friendly_name": "Bedroom Temperature"}
        },
        {
            "state": "23.1", 
            "timestamp": "2023-04-15T03:30:00",
            "attributes": {"unit_of_measurement": "°C", "friendly_name": "Bedroom Temperature"}
        }
    ]
}
"""
import os
import json
import time
import sqlite3
import logging
from datetime import datetime
import paho.mqtt.client as mqtt
import uuid
import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mqtt_history_injector")

# Configuration defaults
DEFAULT_CONFIG = {
    "mqtt_host": "core-mosquitto",
    "mqtt_port": 1883,
    "mqtt_username": "",
    "mqtt_password": "",
    "mqtt_topic": "homeassistant/history/+",
    "ha_database_path": "/config/home-assistant_v2.db",
    "ha_api_url": "http://supervisor/core/api",
    "ha_token": "",
    "max_timestamp_offset_days": 30,  # Limit how far back in time we'll accept
    "default_entity_id_prefix": "sensor.",
    "create_missing_entities": True
}

def load_config():
    """Load the addon configuration."""
    config_path = "/data/options.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            user_config = json.load(f)
        
        # Merge with defaults
        config = DEFAULT_CONFIG.copy()
        config.update(user_config)
        
        # If token not provided, try to get from environment
        if not config["ha_token"] and "SUPERVISOR_TOKEN" in os.environ:
            config["ha_token"] = os.environ["SUPERVISOR_TOKEN"]
            
        return config
    return DEFAULT_CONFIG

def verify_ha_database(db_path):
    """Verify that the Home Assistant database exists and has the expected schema."""
    if not os.path.exists(db_path):
        logger.error(f"Home Assistant database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for required tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('states', 'state_attributes')")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        if 'states' not in table_names or 'state_attributes' not in table_names:
            logger.error(f"Required tables not found in Home Assistant database. Found: {table_names}")
            conn.close()
            return False
            
        conn.close()
        logger.info(f"Home Assistant database verified at {db_path}")
        return True
    except Exception as e:
        logger.error(f"Error verifying Home Assistant database: {e}")
        return False

def get_entity_id_from_topic(topic):
    """Extract entity_id from MQTT topic.
    
    Expected format: homeassistant/history/sensor.bedroom_temperature
    Will return: sensor.bedroom_temperature
    """
    parts = topic.split('/')
    if len(parts) >= 3:
        return parts[2]
    return None

def check_entity_exists(conn, entity_id):
    """Check if an entity exists in the Home Assistant database."""
    cursor = conn.cursor()
    cursor.execute("SELECT entity_id FROM states WHERE entity_id = ? LIMIT 1", (entity_id,))
    result = cursor.fetchone()
    return result is not None

def create_entity_via_api(config, entity_id, attributes=None):
    """Create an entity using the Home Assistant API."""
    if not config["ha_token"]:
        logger.error("No Home Assistant API token provided, cannot create entity")
        return False
        
    # Default attributes if none provided
    if not attributes:
        attributes = {}
    
    # Extract domain and object_id from entity_id
    parts = entity_id.split('.')
    if len(parts) != 2:
        logger.error(f"Invalid entity_id format: {entity_id}")
        return False
        
    domain, object_id = parts
    
    # Determine friendly name if not in attributes
    if 'friendly_name' not in attributes:
        friendly_name = object_id.replace('_', ' ').title()
        attributes['friendly_name'] = friendly_name
    
    # Format depends on entity type
    if domain == 'sensor':
        # Create a sensor entity
        headers = {
            "Authorization": f"Bearer {config['ha_token']}",
            "Content-Type": "application/json"
        }
        
        # First, check if entity already exists via API
        try:
            response = requests.get(
                f"{config['ha_api_url']}/states/{entity_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info(f"Entity {entity_id} already exists according to API")
                return True
                
        except Exception as e:
            logger.error(f"Error checking entity via API: {e}")
        
        # Create entity via API
        try:
            payload = {
                "state": "unknown",
                "attributes": attributes
            }
            
            response = requests.post(
                f"{config['ha_api_url']}/states/{entity_id}",
                headers=headers,
                json=payload
            )
            
            if response.status_code in (200, 201):
                logger.info(f"Successfully created entity {entity_id} via API")
                return True
            else:
                logger.error(f"Failed to create entity via API: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating entity via API: {e}")
            return False
    else:
        # Other entity types might need different approaches
        logger.warning(f"Creating entities of domain {domain} is not fully supported")
        return False

def create_entity_in_db(conn, entity_id, attributes=None):
    """Create an entity directly in the Home Assistant database."""
    try:
        cursor = conn.cursor()
        
        # Check if entity already exists
        if check_entity_exists(conn, entity_id):
            logger.info(f"Entity {entity_id} already exists in database")
            return True
            
        # Convert attributes to JSON
        attributes_json = None
        if attributes:
            attributes_json = json.dumps(attributes)
        
        # Get current timestamp
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        # Insert initial state
        cursor.execute(
            "INSERT INTO states (entity_id, state, last_changed, last_updated, old_state_id, attributes_id) "
            "VALUES (?, ?, ?, ?, NULL, NULL)",
            (entity_id, "unknown", now, now)
        )
        
        state_id = cursor.lastrowid
        
        # Insert attributes if provided
        if attributes_json:
            # Insert into state_attributes
            cursor.execute("INSERT INTO state_attributes (shared_attrs) VALUES (?)", (attributes_json,))
            attributes_id = cursor.lastrowid
            
            # Update states record with attributes_id
            cursor.execute(
                "UPDATE states SET attributes_id = ? WHERE state_id = ?", 
                (attributes_id, state_id)
            )
        
        conn.commit()
        logger.info(f"Successfully created entity {entity_id} in database")
        return True
        
    except Exception as e:
        logger.error(f"Error creating entity in database: {e}")
        conn.rollback()
        return False

def create_entity(conn, config, entity_id, attributes=None):
    """Create an entity using the appropriate method."""
    # Try API method first (preferred)
    if config.get("ha_token"):
        if create_entity_via_api(config, entity_id, attributes):
            return True
    
    # Fallback to direct DB method
    return create_entity_in_db(conn, entity_id, attributes)

def get_last_state_id(conn, entity_id):
    """Get the last state_id for an entity."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT state_id FROM states WHERE entity_id = ? ORDER BY last_updated DESC LIMIT 1", 
        (entity_id,)
    )
    result = cursor.fetchone()
    return result[0] if result else None

def insert_state_attribute(conn, state_id, attributes):
    """Insert state attributes into the database."""
    if not attributes:
        return
    
    try:
        cursor = conn.cursor()
        
        # Check if shared_attrs exists
        cursor.execute("SELECT attributes_id FROM state_attributes WHERE shared_attrs = ?", (attributes,))
        existing = cursor.fetchone()
        
        if existing:
            # Re-use existing attributes
            cursor.execute(
                "UPDATE states SET attributes_id = ? WHERE state_id = ?", 
                (existing[0], state_id)
            )
        else:
            # Insert new attributes
            cursor.execute("INSERT INTO state_attributes (shared_attrs) VALUES (?)", (attributes,))
            attributes_id = cursor.lastrowid
            
            cursor.execute(
                "UPDATE states SET attributes_id = ? WHERE state_id = ?", 
                (attributes_id, state_id)
            )
    except Exception as e:
        logger.error(f"Error inserting attributes: {e}")

def insert_historical_state(conn, entity_id, state, timestamp, attributes_json=None):
    """Insert a historical state into the Home Assistant database."""
    try:
        cursor = conn.cursor()
        
        # Format the timestamp to match Home Assistant's format
        if 'T' not in timestamp:
            # If only date is provided, assume midnight
            timestamp = f"{timestamp}T00:00:00"
            
        if '.' not in timestamp and 'Z' not in timestamp:
            # Add milliseconds if not present
            timestamp = f"{timestamp}.000000"
            
        if 'Z' not in timestamp and '+' not in timestamp:
            # Add timezone if not present
            timestamp = f"{timestamp}Z"
            
        # Create state entry
        cursor.execute(
            "INSERT INTO states (entity_id, state, last_changed, last_updated, old_state_id, attributes_id) "
            "VALUES (?, ?, ?, ?, NULL, NULL)",
            (entity_id, state, timestamp, timestamp)
        )
        
        state_id = cursor.lastrowid
        
        # Insert attributes if provided
        if attributes_json:
            insert_state_attribute(conn, state_id, attributes_json)
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error inserting historical state: {e}")
        conn.rollback()
        return False

def parse_timestamp(timestamp_str):
    """Parse timestamp string to datetime object."""
    try:
        # Try various formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
                
        raise ValueError(f"Could not parse timestamp: {timestamp_str}")
    except Exception as e:
        logger.error(f"Error parsing timestamp {timestamp_str}: {e}")
        return None

def is_timestamp_valid(timestamp_str, max_offset_days):
    """Check if timestamp is valid and not too far in the past or future."""
    parsed = parse_timestamp(timestamp_str)
    if not parsed:
        return False
        
    now = datetime.now()
    diff = abs((now - parsed).days)
    
    return diff <= max_offset_days

def process_single_record(conn, config, entity_id, record, max_offset_days):
    """Process a single historical record."""
    try:
        # Extract data
        state = str(record.get('state', ''))
        timestamp = record.get('timestamp')
        attributes = record.get('attributes', {})
        
        # Validate data
        if not state or not timestamp:
            logger.error(f"Missing required fields (state or timestamp) in record: {record}")
            return False
            
        # Validate timestamp
        if not is_timestamp_valid(timestamp, max_offset_days):
            logger.error(f"Timestamp {timestamp} is invalid or too far from current time")
            return False
            
        # Convert attributes to JSON if needed
        attributes_json = json.dumps(attributes) if attributes else None
        
        # Insert state
        return insert_historical_state(conn, entity_id, state, timestamp, attributes_json)
    except Exception as e:
        logger.error(f"Error processing record: {e}")
        return False

def process_message(conn, config, topic, payload):
    """Process an MQTT message containing historical data."""
    try:
        # Parse payload
        data = json.loads(payload)
        
        # Extract entity_id from topic
        entity_id = get_entity_id_from_topic(topic)
        if not entity_id:
            # For topics without entity_id, try to extract from payload
            entity_id = data.get('entity_id')
            
            # If still no entity_id, use device_id as fallback with prefix
            if not entity_id and 'device_id' in data:
                entity_id = f"{config['default_entity_id_prefix']}{data['device_id']}"
                
        if not entity_id:
            logger.error(f"Could not determine entity_id from topic {topic} or payload")
            return False
            
        # Extract attributes for entity creation
        attributes = None
        if 'records' in data and isinstance(data['records'], list) and data['records']:
            # Get attributes from the first record
            attributes = data['records'][0].get('attributes', {})
        else:
            # Get attributes from the single record
            attributes = data.get('attributes', {})
            
        # Check if entity exists and create if needed
        if not check_entity_exists(conn, entity_id):
            if config['create_missing_entities']:
                logger.info(f"Entity {entity_id} does not exist. Creating it...")
                if not create_entity(conn, config, entity_id, attributes):
                    logger.error(f"Failed to create entity {entity_id}")
                    return False
            else:
                logger.warning(f"Entity {entity_id} does not exist and creation is disabled")
        
        # Process records
        success = False
        if 'records' in data and isinstance(data['records'], list):
            # Process multiple records
            for record in data['records']:
                if process_single_record(conn, config, entity_id, record, config['max_timestamp_offset_days']):
                    success = True
        else:
            # Process single record
            success = process_single_record(conn, config, entity_id, data, config['max_timestamp_offset_days'])
            
        return success
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON payload: {payload}")
        return False
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return False

def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the MQTT broker."""
    if rc == 0:
        logger.info("Connected to MQTT broker")
        topic = userdata['config']['mqtt_topic']
        client.subscribe(topic)
        logger.info(f"Subscribed to {topic}")
    else:
        logger.error(f"Failed to connect to MQTT broker with code: {rc}")

def on_message(client, userdata, msg):
    """Callback for when a message is received from the MQTT broker."""
    try:
        payload = msg.payload.decode('utf-8')
        logger.debug(f"Received message on topic {msg.topic}: {payload}")
        
        # Connect to Home Assistant database
        conn = sqlite3.connect(userdata['config']['ha_database_path'])
        
        # Process message
        success = process_message(conn, userdata['config'], msg.topic, payload)
        
        # Close connection
        conn.close()
        
        if success:
            logger.info(f"Successfully processed historical data for topic {msg.topic}")
        else:
            logger.warning(f"Failed to process historical data for topic {msg.topic}")
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")

def main():
    """Main function."""
    # Load configuration
    config = load_config()
    logger.info("Configuration loaded")
    
    # Verify Home Assistant database
    if not verify_ha_database(config['ha_database_path']):
        logger.error("Exiting due to database verification failure")
        return
    
    # Set up MQTT client
    client_id = f"mqtt-history-injector-{uuid.uuid4().hex[:8]}"
    userdata = {
        'config': config,
    }
    
    client = mqtt.Client(client_id=client_id, userdata=userdata)
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Set username and password if provided
    if config['mqtt_username'] and config['mqtt_password']:
        client.username_pw_set(config['mqtt_username'], config['mqtt_password'])
    
    # Connect to MQTT broker
    connected = False
    while not connected:
        try:
            client.connect(config['mqtt_host'], config['mqtt_port'], 60)
            connected = True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            logger.info("Retrying in 10 seconds...")
            time.sleep(10)
    
    # Start the MQTT loop
    client.loop_start()
    
    # Main loop to keep the script running
    try:
        while True:
            time.sleep(60)  # Sleep for a minute
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()