import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from config import API_HOST, API_PORT, WEBSOCKET_UPDATE_INTERVAL
from data.database import CalibrationDatabase
from data.report_generator import generate_calibration_certificate

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Temperature Calibration System API",
    description="REST API i WebSocket dla systemu wzorcowania czujników temperatury",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()
calibration_engine = None
database = CalibrationDatabase()


class SessionCreate(BaseModel):
    operator: str
    client: str = ""
    order_number: str = ""
    ambient_temperature: Optional[float] = None
    relative_humidity: Optional[float] = None
    notes: str = ""


class FurnaceSetpoint(BaseModel):
    temperature: float


class CalibrationConfig(BaseModel):
    channels: List[str]
    sensor_types: Dict[str, str]
    calibration_points: List[float]


def set_calibration_engine(engine):
    global calibration_engine
    calibration_engine = engine
    logger.info("Calibration engine set for API")


@app.get("/")
async def root():
    return {
        "message": "Temperature Calibration System Remote API",
        "version": "1.0.0",
        "endpoints": {
            "status": "/api/status",
            "sessions": "/api/sessions",
            "websocket": "/ws/realtime"
        }
    }


@app.get("/api/status")
async def get_system_status():
    if calibration_engine is None:
        return {
            "connected": False,
            "message": "System not initialized"
        }
    
    try:
        status = calibration_engine.get_current_status()
        return {
            "connected": True,
            "timestamp": datetime.now().isoformat(),
            **status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/start")
async def start_session(session_data: SessionCreate):
    if calibration_engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        session_id = calibration_engine.start_session(
            operator=session_data.operator,
            client=session_data.client,
            order_number=session_data.order_number,
            ambient_temp=session_data.ambient_temperature,
            humidity=session_data.relative_humidity,
            notes=session_data.notes
        )
        return {"session_id": session_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/end")
async def end_session():
    if calibration_engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    calibration_engine.stop_calibration()
    return {"status": "stopped"}


@app.post("/api/calibration/start")
async def start_calibration(config: CalibrationConfig):
    if calibration_engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        calibration_engine.configure_channels(config.channels, config.sensor_types)
        calibration_engine.set_calibration_points(config.calibration_points)
        calibration_engine.start_calibration()
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calibration/stop")
async def stop_calibration():
    if calibration_engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    calibration_engine.stop_calibration()
    return {"status": "stopped"}


@app.post("/api/calibration/pause")
async def pause_calibration():
    if calibration_engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    calibration_engine.pause_calibration()
    return {"status": "paused"}


@app.post("/api/calibration/resume")
async def resume_calibration():
    if calibration_engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    calibration_engine.resume_calibration()
    return {"status": "resumed"}


@app.post("/api/furnace/setpoint")
async def set_furnace_setpoint(setpoint: FurnaceSetpoint):
    if calibration_engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        success = calibration_engine.furnace.set_setpoint(setpoint.temperature)
        if success:
            return {"status": "ok", "setpoint": setpoint.temperature}
        else:
            raise HTTPException(status_code=500, detail="Failed to set setpoint")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/current-reading")
async def get_current_reading():
    if calibration_engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        reading = calibration_engine.read_current_channel()
        if reading:
            return reading
        return {"message": "No reading available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/plot-data")
async def get_plot_data():
    if calibration_engine is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        return calibration_engine.get_plot_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def get_sessions(limit: int = 50):
    try:
        sessions = database.get_all_sessions(limit=limit)
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: int):
    try:
        session = database.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/results")
async def get_session_results(session_id: int):
    try:
        results = database.get_session_results(session_id)
        return {"session_id": session_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/measurements")
async def get_session_measurements(session_id: int):
    try:
        measurements = database.get_session_measurements(session_id)
        return {"session_id": session_id, "measurements": measurements}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/report")
async def generate_session_report(session_id: int):
    try:
        session_data = database.get_full_session_data(session_id)
        if session_data.get('session') is None:
            raise HTTPException(status_code=404, detail="Session not found")
        
        report_path = generate_calibration_certificate(session_data)
        return FileResponse(
            report_path,
            media_type='application/pdf',
            filename=f"swiadectwo_wzorcowania_{session_id}.pdf"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int):
    try:
        database.delete_session(session_id)
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            if calibration_engine:
                try:
                    status = calibration_engine.get_current_status()
                    reading = calibration_engine.read_current_channel()
                    
                    data = {
                        'type': 'realtime_update',
                        'timestamp': datetime.now().isoformat(),
                        'status': status,
                        'reading': reading
                    }
                    
                    await websocket.send_json(data)
                except Exception as e:
                    await websocket.send_json({
                        'type': 'error',
                        'message': str(e)
                    })
            else:
                await websocket.send_json({
                    'type': 'status',
                    'message': 'System not initialized',
                    'timestamp': datetime.now().isoformat()
                })
            
            await asyncio.sleep(WEBSOCKET_UPDATE_INTERVAL)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


def run_api_server(host: str = None, port: int = None):
    host = host or API_HOST
    port = port or API_PORT
    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_api_server()
