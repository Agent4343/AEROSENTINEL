"""MQTTService -- async MQTT client for DJI Cloud API communication.

Connects to an EMQX broker, subscribes to DJI Cloud API topics, routes
incoming messages to the appropriate handlers, and provides helpers for
publishing commands back to drones.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import suppress
from typing import Any, Callable, Coroutine, Dict, List, Optional

import aiomqtt

logger = logging.getLogger("aerosentinel.mqtt")

# Type alias for async message handlers
MessageHandler = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]


class MQTTService:
    """Manages the MQTT lifecycle for DJI Cloud API communication.

    Responsibilities:
    - Connect to the EMQX broker with reconnection logic.
    - Subscribe to per-device telemetry, event, and flight-task topics.
    - Route incoming messages to registered handlers.
    - Provide convenience methods for publishing commands.
    """

    # DJI Cloud API topic templates
    TOPIC_OSD = "thing/product/{gateway_sn}/osd"
    TOPIC_EVENTS = "thing/product/{gateway_sn}/events"
    TOPIC_SERVICES = "thing/product/{gateway_sn}/services"
    TOPIC_SERVICES_REPLY = "thing/product/{gateway_sn}/services_reply"
    TOPIC_REQUESTS = "thing/product/{gateway_sn}/requests"
    TOPIC_REQUESTS_REPLY = "thing/product/{gateway_sn}/requests_reply"

    # Flight-task sub-topics (published under services / events)
    METHOD_FLIGHTTASK_PREPARE = "flighttask_prepare"
    METHOD_FLIGHTTASK_EXECUTE = "flighttask_execute"
    METHOD_FLIGHTTASK_PROGRESS = "flighttask_progress"

    # Live-streaming methods
    METHOD_LIVE_START_PUSH = "live_start_push"
    METHOD_LIVE_STOP_PUSH = "live_stop_push"

    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        reconnect_interval: float = 5.0,
    ) -> None:
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._username = username
        self._password = password
        self._client_id = client_id or f"aerosentinel-{uuid.uuid4().hex[:8]}"
        self._reconnect_interval = reconnect_interval

        self._client: Optional[aiomqtt.Client] = None
        self._running = False
        self._listen_task: Optional[asyncio.Task[None]] = None

        # Handler registries
        self._osd_handlers: List[MessageHandler] = []
        self._event_handlers: List[MessageHandler] = []
        self._services_reply_handlers: List[MessageHandler] = []
        self._method_handlers: Dict[str, List[MessageHandler]] = {}

        # Gateway serial numbers we are tracking
        self._gateway_sns: set[str] = set()

    # -- handler registration -----------------------------------------------

    def on_osd(self, handler: MessageHandler) -> None:
        """Register a handler for OSD telemetry messages."""
        self._osd_handlers.append(handler)

    def on_event(self, handler: MessageHandler) -> None:
        """Register a handler for device event messages."""
        self._event_handlers.append(handler)

    def on_services_reply(self, handler: MessageHandler) -> None:
        """Register a handler for service reply messages."""
        self._services_reply_handlers.append(handler)

    def on_method(self, method: str, handler: MessageHandler) -> None:
        """Register a handler for a specific DJI Cloud API method."""
        self._method_handlers.setdefault(method, []).append(handler)

    # -- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        """Start the MQTT client and background listener."""
        self._running = True
        self._listen_task = asyncio.create_task(self._connection_loop())
        logger.info(
            "MQTTService connecting to %s:%d as %s",
            self._broker_host,
            self._broker_port,
            self._client_id,
        )

    async def disconnect(self) -> None:
        """Gracefully shut down."""
        self._running = False
        if self._listen_task is not None:
            self._listen_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._listen_task
            self._listen_task = None
        logger.info("MQTTService disconnected")

    async def _connection_loop(self) -> None:
        """Maintain a persistent connection with automatic reconnection."""
        while self._running:
            try:
                async with aiomqtt.Client(
                    hostname=self._broker_host,
                    port=self._broker_port,
                    username=self._username,
                    password=self._password,
                    identifier=self._client_id,
                    clean_session=True,
                ) as client:
                    self._client = client
                    logger.info("MQTT connected to %s:%d", self._broker_host, self._broker_port)

                    await self._subscribe_all(client)
                    await self._listen(client)

            except aiomqtt.MqttError as exc:
                logger.warning("MQTT connection lost (%s), reconnecting in %.1fs", exc, self._reconnect_interval)
            except Exception:
                logger.exception("Unexpected error in MQTT connection loop")
            finally:
                self._client = None

            if self._running:
                await asyncio.sleep(self._reconnect_interval)

    async def _subscribe_all(self, client: aiomqtt.Client) -> None:
        """Subscribe to topics for all registered gateway serial numbers."""
        # Wildcard subscriptions for discovery
        await client.subscribe("thing/product/+/osd", qos=1)
        await client.subscribe("thing/product/+/events", qos=1)
        await client.subscribe("thing/product/+/services_reply", qos=1)
        await client.subscribe("thing/product/+/requests", qos=1)
        logger.info("Subscribed to wildcard DJI Cloud API topics")

    async def _listen(self, client: aiomqtt.Client) -> None:
        """Process incoming messages until disconnected."""
        async for message in client.messages:
            try:
                topic = str(message.topic)
                payload = self._decode_payload(message.payload)
                if payload is None:
                    continue
                await self._route(topic, payload)
            except Exception:
                logger.exception("Error handling message on %s", message.topic)

    # -- message routing ----------------------------------------------------

    def _decode_payload(self, raw: Any) -> Optional[Dict[str, Any]]:
        try:
            if isinstance(raw, (bytes, bytearray)):
                return json.loads(raw.decode("utf-8"))
            if isinstance(raw, str):
                return json.loads(raw)
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Failed to decode MQTT payload")
            return None

    async def _route(self, topic: str, payload: Dict[str, Any]) -> None:
        """Route a decoded message to the appropriate handlers."""
        parts = topic.split("/")
        if len(parts) < 4:
            return

        gateway_sn = parts[2]
        topic_type = parts[3]

        # Track newly-seen gateways
        self._gateway_sns.add(gateway_sn)

        if topic_type == "osd":
            for handler in self._osd_handlers:
                await handler(gateway_sn, payload)

        elif topic_type == "events":
            for handler in self._event_handlers:
                await handler(gateway_sn, payload)
            # Dispatch method-specific handlers
            method = payload.get("method", "")
            await self._dispatch_method(method, gateway_sn, payload)

        elif topic_type == "services_reply":
            for handler in self._services_reply_handlers:
                await handler(gateway_sn, payload)
            method = payload.get("method", "")
            await self._dispatch_method(method, gateway_sn, payload)

        elif topic_type == "requests":
            # Device requests (e.g. config, log upload)
            method = payload.get("method", "")
            await self._dispatch_method(method, gateway_sn, payload)

    async def _dispatch_method(
        self, method: str, gateway_sn: str, payload: Dict[str, Any]
    ) -> None:
        handlers = self._method_handlers.get(method, [])
        for handler in handlers:
            await handler(gateway_sn, payload)

    # -- publishing ---------------------------------------------------------

    async def publish_service(
        self,
        gateway_sn: str,
        method: str,
        data: Dict[str, Any],
        bid: Optional[str] = None,
        tid: Optional[str] = None,
    ) -> None:
        """Publish a command to a device's services topic.

        Parameters
        ----------
        gateway_sn : serial number of the gateway / dock.
        method : DJI Cloud API method name (e.g. ``flighttask_prepare``).
        data : method-specific parameters.
        bid, tid : optional business / transaction IDs (auto-generated if omitted).
        """
        if self._client is None:
            raise RuntimeError("MQTT client is not connected")

        topic = self.TOPIC_SERVICES.format(gateway_sn=gateway_sn)
        message = {
            "bid": bid or uuid.uuid4().hex,
            "tid": tid or uuid.uuid4().hex,
            "timestamp": int(time.time() * 1000),
            "method": method,
            "data": data,
        }
        payload = json.dumps(message)
        await self._client.publish(topic, payload, qos=1)
        logger.info("Published %s to %s", method, topic)

    # -- convenience methods ------------------------------------------------

    async def send_flighttask_prepare(
        self,
        gateway_sn: str,
        flight_id: str,
        file_url: str,
        file_md5: str,
    ) -> None:
        """Send a flighttask_prepare command."""
        await self.publish_service(
            gateway_sn,
            self.METHOD_FLIGHTTASK_PREPARE,
            {
                "flight_id": flight_id,
                "type": "wayline",
                "file": {
                    "url": file_url,
                    "fingerprint": file_md5,
                },
            },
        )

    async def send_flighttask_execute(
        self,
        gateway_sn: str,
        flight_id: str,
    ) -> None:
        """Send a flighttask_execute command."""
        await self.publish_service(
            gateway_sn,
            self.METHOD_FLIGHTTASK_EXECUTE,
            {"flight_id": flight_id},
        )

    async def send_live_start_push(
        self,
        gateway_sn: str,
        url_type: int = 1,
        video_id: str = "normal-0",
        video_quality: int = 0,
    ) -> None:
        """Start live video streaming from a device."""
        await self.publish_service(
            gateway_sn,
            self.METHOD_LIVE_START_PUSH,
            {
                "url_type": url_type,
                "video_id": video_id,
                "video_quality": video_quality,
            },
        )

    async def send_live_stop_push(
        self,
        gateway_sn: str,
        video_id: str = "normal-0",
    ) -> None:
        """Stop live video streaming from a device."""
        await self.publish_service(
            gateway_sn,
            self.METHOD_LIVE_STOP_PUSH,
            {"video_id": video_id},
        )

    async def reply_to_request(
        self,
        gateway_sn: str,
        tid: str,
        bid: str,
        method: str,
        data: Optional[Dict[str, Any]] = None,
        result: int = 0,
    ) -> None:
        """Reply to a device request."""
        if self._client is None:
            raise RuntimeError("MQTT client is not connected")

        topic = self.TOPIC_REQUESTS_REPLY.format(gateway_sn=gateway_sn)
        message = {
            "bid": bid,
            "tid": tid,
            "timestamp": int(time.time() * 1000),
            "method": method,
            "data": {
                "result": result,
                **(data or {}),
            },
        }
        payload = json.dumps(message)
        await self._client.publish(topic, payload, qos=1)
        logger.debug("Replied to request %s on %s", method, topic)

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def tracked_gateways(self) -> set[str]:
        return set(self._gateway_sns)
