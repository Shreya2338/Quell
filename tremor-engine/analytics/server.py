import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from shared.contracts import SensorPacket, VibrationPacket, CalibrationPacket, AggregatedDeviceState
from niya.tass_actuator import TASSActuator

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

actuator_helper = TASSActuator()
current_device_state = AggregatedDeviceState()

active_connections = set()

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            text_data = await websocket.receive_text()
            payload = json.loads(text_data)

            # Route messages based on structure
            if "gyroscope" in payload and "accelerometer" in payload:
                sensor = SensorPacket(**payload)
                current_device_state.gyro_x, current_device_state.gyro_y, current_device_state.gyro_z = sensor.gyroscope
                current_device_state.accel_x, current_device_state.accel_y, current_device_state.accel_z = sensor.accelerometer

            elif "actuation_state" in payload:
                vib = VibrationPacket(**payload)
                current_device_state.actuation_state = vib.actuation_state
                current_device_state.actuation_intensity_hz = vib.actuation_intensity
                current_device_state.actuation_intensity_pct = actuator_helper.hz_to_percent(vib.actuation_intensity)

            elif "caliberation_status" in payload:
                cal = CalibrationPacket(**payload)
                current_device_state.calibration_status = cal.caliberation_status

            # Broadcast the updated aggregated state to the UI
            broadcast_payload = current_device_state.model_dump_json()
            for connection in list(active_connections):
                await connection.send_text(broadcast_payload)

    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        print(f"Error handling message: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.post("/api/command/vibrate")
async def trigger_vibration(length_ms: int, intensity_hz: int):
    command = actuator_helper.create_vibration_command(length_ms, intensity_hz)
    # Forward `command` to hardware serial/BLE connection here
    return {"status": "sent", "command": command}

@app.post("/api/command/calibrate")
async def trigger_calibration():
    command = actuator_helper.create_calibration_command()
    # Forward `command` to hardware serial/BLE connection here
    return {"status": "sent", "command": command}
