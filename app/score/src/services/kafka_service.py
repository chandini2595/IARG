"""
Kafka service for event streaming
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Callable
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

from src.utils.logging import LoggerMixin
from src.config import settings


class KafkaService(LoggerMixin):
    """Kafka service for event streaming"""
    
    def __init__(self, brokers: List[str]):
        self.brokers = brokers
        self.producer: Optional[KafkaProducer] = None
        self.consumer: Optional[KafkaConsumer] = None
        self.consumer_group = settings.kafka_consumer_group
        self.topics = settings.kafka_topics
        
        # Consumer state
        self.is_consuming = False
        self.consumer_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """Connect to Kafka"""
        try:
            # Initialize producer
            self.producer = KafkaProducer(
                bootstrap_servers=self.brokers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3,
                retry_backoff_ms=1000,
                request_timeout_ms=30000
            )
            
            self.log_event("Connected to Kafka", brokers=self.brokers)
            
        except Exception as e:
            self.log_error(e, {"component": "kafka_connection"})
            raise
    
    async def close(self) -> None:
        """Close Kafka connections"""
        try:
            # Stop consumer
            if self.is_consuming and self.consumer_task:
                self.is_consuming = False
                self.consumer_task.cancel()
                try:
                    await self.consumer_task
                except asyncio.CancelledError:
                    pass
            
            # Close consumer
            if self.consumer:
                self.consumer.close()
            
            # Close producer
            if self.producer:
                self.producer.close()
            
            self.log_event("Kafka connections closed")
            
        except Exception as e:
            self.log_error(e, {"component": "kafka_close"})
    
    async def publish_event(self, topic: str, event: Dict[str, Any], 
                          key: Optional[str] = None) -> bool:
        """Publish event to Kafka topic"""
        try:
            if not self.producer:
                raise RuntimeError("Kafka producer not initialized")
            
            # Add metadata
            event_with_metadata = {
                **event,
                'timestamp': event.get('timestamp') or asyncio.get_event_loop().time(),
                'service': 'iarg-score'
            }
            
            # Send message
            future = self.producer.send(topic, value=event_with_metadata, key=key)
            record_metadata = future.get(timeout=10)
            
            self.log_event("Event published", 
                         topic=topic, 
                         partition=record_metadata.partition,
                         offset=record_metadata.offset)
            
            return True
            
        except Exception as e:
            self.log_error(e, {"topic": topic, "event_type": event.get('type')})
            return False
    
    async def start_consumer(self, event_handler: Callable[[Dict[str, Any]], None]) -> None:
        """Start Kafka consumer"""
        try:
            # Initialize consumer
            self.consumer = KafkaConsumer(
                *self.topics.values(),
                bootstrap_servers=self.brokers,
                group_id=self.consumer_group,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                consumer_timeout_ms=1000
            )
            
            self.is_consuming = True
            self.log_event("Started Kafka consumer", 
                         topics=list(self.topics.values()),
                         group_id=self.consumer_group)
            
            # Start consuming in background
            self.consumer_task = asyncio.create_task(
                self._consume_messages(event_handler)
            )
            
        except Exception as e:
            self.log_error(e, {"component": "kafka_consumer"})
            raise
    
    async def _consume_messages(self, event_handler: Callable[[Dict[str, Any]], None]) -> None:
        """Consume messages from Kafka"""
        while self.is_consuming:
            try:
                # Poll for messages
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        try:
                            # Process message
                            event_data = message.value
                            
                            self.log_event("Processing event",
                                         topic=message.topic,
                                         partition=message.partition,
                                         offset=message.offset,
                                         event_type=event_data.get('type'))
                            
                            # Handle event asynchronously
                            await event_handler(event_data)
                            
                        except Exception as e:
                            self.log_error(e, {
                                "topic": message.topic,
                                "partition": message.partition,
                                "offset": message.offset,
                                "component": "message_processing"
                            })
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                if self.is_consuming:  # Only log if we're still supposed to be consuming
                    self.log_error(e, {"component": "kafka_consume_loop"})
                    await asyncio.sleep(1)  # Wait before retrying
    
    async def publish_risk_score_event(self, asset_id: str, risk_score: float, 
                                     risk_level: str, model_version: str) -> bool:
        """Publish risk score event"""
        event = {
            'type': 'risk.score.v1',
            'asset_id': asset_id,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'model_version': model_version,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        return await self.publish_event(self.topics['risk_score'], event, key=asset_id)
    
    async def publish_model_update_event(self, model_version: str, 
                                       metrics: Dict[str, Any]) -> bool:
        """Publish model update event"""
        event = {
            'type': 'model.updated.v1',
            'model_version': model_version,
            'metrics': metrics,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        return await self.publish_event(self.topics['events'], event, key=model_version)
    
    async def publish_anomaly_detected_event(self, asset_id: str, 
                                           anomaly_score: float,
                                           details: Dict[str, Any]) -> bool:
        """Publish anomaly detection event"""
        event = {
            'type': 'anomaly.detected.v1',
            'asset_id': asset_id,
            'anomaly_score': anomaly_score,
            'details': details,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        return await self.publish_event(self.topics['events'], event, key=asset_id)
    
    def get_consumer_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics"""
        if not self.consumer:
            return {}
        
        try:
            metrics = self.consumer.metrics()
            return {
                'consumer_group': self.consumer_group,
                'subscribed_topics': list(self.consumer.subscription()),
                'assignment': [
                    {'topic': tp.topic, 'partition': tp.partition}
                    for tp in self.consumer.assignment()
                ],
                'is_consuming': self.is_consuming,
                'metrics': {
                    'records_consumed_total': metrics.get('consumer-fetch-manager-metrics', {}).get('records-consumed-total', 0),
                    'bytes_consumed_total': metrics.get('consumer-fetch-manager-metrics', {}).get('bytes-consumed-total', 0),
                    'fetch_latency_avg': metrics.get('consumer-fetch-manager-metrics', {}).get('fetch-latency-avg', 0)
                }
            }
        except Exception as e:
            self.log_error(e, {"component": "consumer_metrics"})
            return {'error': str(e)}
    
    def get_producer_metrics(self) -> Dict[str, Any]:
        """Get producer metrics"""
        if not self.producer:
            return {}
        
        try:
            metrics = self.producer.metrics()
            return {
                'metrics': {
                    'record_send_total': metrics.get('producer-metrics', {}).get('record-send-total', 0),
                    'byte_total': metrics.get('producer-metrics', {}).get('byte-total', 0),
                    'record_error_total': metrics.get('producer-metrics', {}).get('record-error-total', 0),
                    'request_latency_avg': metrics.get('producer-metrics', {}).get('request-latency-avg', 0)
                }
            }
        except Exception as e:
            self.log_error(e, {"component": "producer_metrics"})
            return {'error': str(e)}