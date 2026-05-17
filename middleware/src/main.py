"""
SIGINT Middleware — Main Entry Point
Async orchestrator for SDR control, signal classification, and metadata extraction.
"""
import asyncio
import signal
import os
import structlog
from aiohttp import web

from sdr_controller import SDRController
from hopping_engine import HoppingEngine
from classifier import SignalClassifier
from decoder_pipeline import DecoderPipeline
from metadata_extractor import MetadataExtractor
from gps_parser import GPSParser
from api_bridge import APIBridge

log = structlog.get_logger()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:4000")
BACKEND_WS = os.environ.get("BACKEND_WS", "ws://backend:4001")
MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "5555"))

class SIGINTMiddleware:
    def __init__(self):
        self.running = False
        self.api = APIBridge(BACKEND_URL, BACKEND_WS)
        self.sdr_controller = SDRController(mock_mode=MOCK_MODE)
        self.classifier = SignalClassifier()
        self.decoder = DecoderPipeline()
        self.extractor = MetadataExtractor()
        self.gps_parser = GPSParser()
        self.hopping_engine = None

    async def start(self):
        self.running = True
        log.info("middleware.starting", mock_mode=MOCK_MODE)

        # Detect SDRs
        devices = await self.sdr_controller.detect_devices()
        log.info("sdr.detected", count=len(devices), devices=[d.serial for d in devices])

        # Initialize hopping engine
        multi_sdr = len(devices) > 1
        self.hopping_engine = HoppingEngine(
            devices=devices,
            multi_sdr=multi_sdr,
            classifier=self.classifier
        )

        # Register devices with backend
        for dev in devices:
            await self.api.register_sdr(dev)

        # Start main processing loop
        await asyncio.gather(
            self._processing_loop(),
            self._health_server(),
        )

    async def _processing_loop(self):
        log.info("pipeline.starting")
        while self.running:
            try:
                # Get next frequency assignment from hopping engine
                assignment = await self.hopping_engine.next_assignment()
                if not assignment:
                    await asyncio.sleep(0.1)
                    continue

                # Tune SDR and capture samples
                samples = await self.sdr_controller.capture(
                    device=assignment.device,
                    frequency=assignment.frequency,
                    duration_ms=assignment.dwell_ms
                )

                if samples is None:
                    continue

                # Classify signal
                classification = self.classifier.classify(samples, assignment.frequency)
                log.info("signal.classified",
                    freq=assignment.frequency,
                    protocol=classification.protocol,
                    snr=classification.snr_db,
                    confidence=classification.confidence
                )

                # Update hopping engine with activity info
                await self.hopping_engine.report_activity(
                    frequency=assignment.frequency,
                    is_active=classification.is_active,
                    snr=classification.snr_db
                )

                # Log signal to backend
                await self.api.log_signal({
                    "frequency": assignment.frequency,
                    "bandwidth_khz": classification.bandwidth_khz,
                    "snr_db": classification.snr_db,
                    "power_dbm": classification.power_dbm,
                    "protocol_guess": classification.protocol,
                    "protocol_confidence": classification.confidence,
                    "sdr_device_serial": assignment.device.serial,
                })

                # If active signal, attempt decode
                if classification.is_active and classification.protocol != "UNKNOWN":
                    decoded = await self.decoder.decode(
                        samples=samples,
                        protocol=classification.protocol,
                        frequency=assignment.frequency
                    )

                    if decoded:
                        # Extract metadata
                        metadata = self.extractor.extract(decoded, classification.protocol)
                        if metadata:
                            log.info("metadata.extracted", metadata=metadata.to_dict())
                            await self.api.push_metadata(metadata.to_dict())

                        # Check for GPS data
                        gps_fix = self.gps_parser.parse(decoded, classification.protocol)
                        if gps_fix:
                            log.info("gps.fix", radio_id=gps_fix.radio_id,
                                lat=gps_fix.latitude, lon=gps_fix.longitude)
                            await self.api.push_gps(gps_fix.to_dict())

            except Exception as e:
                log.error("pipeline.error", error=str(e))
                await asyncio.sleep(1)

    async def _health_server(self):
        app = web.Application()
        app.router.add_get('/health', self._health_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', HEALTH_PORT)
        await site.start()
        log.info("health.server.started", port=HEALTH_PORT)

    async def _health_handler(self, request):
        return web.json_response({
            "status": "healthy",
            "running": self.running,
            "mock_mode": MOCK_MODE,
            "devices": len(self.sdr_controller.devices)
        })

    async def stop(self):
        self.running = False
        log.info("middleware.stopping")

async def main():
    middleware = SIGINTMiddleware()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(middleware.stop()))
    await middleware.start()

if __name__ == "__main__":
    asyncio.run(main())
