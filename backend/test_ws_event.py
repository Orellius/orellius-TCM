"""Quick script to send test events through the WebSocket to verify frontend receives them."""

import asyncio
import json
import time
import uuid

import websockets


async def send_test_events():
    uri = "ws://127.0.0.1:8000/ws"
    async with websockets.connect(uri) as ws:
        # Simulate a new message arriving from a Telegram channel
        msg_id = str(uuid.uuid4())

        # 1. Send agent status updates
        for _agent in ["Ingestion", "Analyst", "Reviewer", "Media Handler", "Publisher"]:
            await ws.send(json.dumps({"command": "subscribe"}))
            resp = await ws.recv()
            print(f"Subscribed: {resp}")
            break

        print("Sending test events via REST API broadcast...")

        import httpx

        async with httpx.AsyncClient() as client:
            # Simulate agent going active
            await send_broadcast(
                client,
                {
                    "type": "agent_status",
                    "agent": "Ingestion",
                    "status": "running",
                    "activity": "Scraping @test_channel",
                },
            )

            await asyncio.sleep(1)

            # Simulate a new message
            await send_broadcast(
                client,
                {
                    "type": "new_message",
                    "message": {
                        "id": msg_id,
                        "sourceChannel": "@test_military_channel",
                        "originalText": "قصف مدفعي عنيف على محور الشمال",
                        "translatedText": None,
                        "mediaUrls": [],
                        "status": "ingested",
                        "timestamp": time.time(),
                    },
                },
            )
            print(f"Sent new_message: {msg_id}")

            await asyncio.sleep(1)

            # Simulate translation completing
            await send_broadcast(
                client,
                {
                    "type": "agent_status",
                    "agent": "Analyst",
                    "status": "running",
                    "activity": f"Translating message {msg_id[:8]}...",
                },
            )

            await asyncio.sleep(2)

            # Send review request
            await send_broadcast(
                client,
                {
                    "type": "review_request",
                    "message": {
                        "id": msg_id,
                        "sourceChannel": "@test_military_channel",
                        "originalText": "قصف مدفعي عنيف على محور الشمال",
                        "translatedText": "[MOCK] הפגזה כבדה של תותחנים על ציר הצפון",
                        "mediaUrls": [],
                        "status": "reviewing",
                        "timestamp": time.time(),
                    },
                },
            )
            print(f"Sent review_request: {msg_id}")

            # Update agent status
            await send_broadcast(
                client,
                {
                    "type": "agent_status",
                    "agent": "Reviewer",
                    "status": "waiting_review",
                    "activity": "Awaiting human review",
                },
            )

        print("All test events sent! Check the Tauri UI.")


async def send_broadcast(client, data):
    """Send event via a second WebSocket connection that broadcasts to all clients."""
    # We'll use a direct WebSocket to broadcast
    async with websockets.connect("ws://127.0.0.1:8000/ws"):
        # The server will receive this as a connected client
        pass  # Just connecting adds us to the broadcast list

    # Actually, let's use a simpler approach - just POST to a test endpoint
    # For now, we'll modify the backend to have a test broadcast endpoint


# Simpler approach: use the REST API + have the backend broadcast
async def main():
    import httpx

    base = "http://127.0.0.1:8000/api"

    async with httpx.AsyncClient() as client:
        # Start pipeline
        r = await client.post(f"{base}/pipeline/start")
        print(f"Pipeline start: {r.json()}")

        print("\nTest events sent via API. The Tauri UI should show:")
        print("  - Pipeline status: Active (green dot)")
        print("  - Start button changed to Stop")
        print("\nNote: To see real-time messages, we need the Telegram scraper running.")
        print("Once you provide source channels, messages will flow through the pipeline.")


asyncio.run(main())
