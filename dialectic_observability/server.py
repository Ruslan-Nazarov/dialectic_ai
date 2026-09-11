"""
dialectic_observability/server.py

DIALECTICAL DESCRIPTION:
  Origin: Previously, the dashboard operated on a blocking http.server from the standard library.
  Contradiction: The standard server does not support asynchronous operations and WebSocket, 
    making it impossible to stream real-time updates (without constant polling).
  How it resolves: Using FastAPI and Uvicorn provides high performance 
    and native support for WebSockets. Alternatives (pure Starlette, aiohttp, 
    or SSE without WebSocket) were rejected due to less convenient auto-documentation 
    and a more complex API for streaming.
  What it leads to: The ability to stream the agent's state of mind and knowledge graph in the browser
    without delays and page reloads.
  Own contradictions: Third-party dependencies (fastapi, uvicorn) are added, 
    so observability is moved to an optional package.
"""
import json
import asyncio
from pathlib import Path
from dialectic_ai.observability.tracer import TraceReader

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


if FASTAPI_AVAILABLE:
    app = FastAPI(title="DialecticAI Observability Dashboard")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"
    TRACE_FILE = "trace.jsonl"

    def get_trace_reader() -> TraceReader:
        return TraceReader(TRACE_FILE)

    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    async def serve_dashboard():
        return DASHBOARD_PATH.read_text(encoding="utf-8")

    @app.get("/api/trace")
    async def get_trace():
        reader = get_trace_reader()
        return JSONResponse(content=reader.get_summary())

    @app.get("/api/graph")
    async def get_graph():
        reader = get_trace_reader()
        return JSONResponse(content=reader.get_knowledge_graph())

    @app.websocket("/ws/stream")
    async def websocket_stream(websocket: WebSocket):
        await websocket.accept()
        last_graph_state = None
        last_trace_count = 0
        try:
            while True:
                # In reality, watchfiles or inotify could be used here
                # For simplicity, we use polling (every second)
                reader = get_trace_reader()
                summary = reader.get_summary()
                graph = reader.get_knowledge_graph()
                
                events_count = summary.get("total_events", 0)
                
                # Send updates only if something has changed
                if events_count != last_trace_count or graph != last_graph_state:
                    last_trace_count = events_count
                    last_graph_state = graph
                    
                    await websocket.send_json({
                        "type": "update",
                        "summary": summary,
                        "graph": graph
                    })
                
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            pass


def run(host: str = "localhost", port: int = 7860, trace_file: str = "trace.jsonl"):
    """Runs the dashboard server based on FastAPI."""
    if not FASTAPI_AVAILABLE:
        print("[-] Error: Optional dependencies must be installed to run the dashboard.")
        print("    Run: pip install fastapi uvicorn")
        import sys
        sys.exit(1)
        
    global TRACE_FILE
    TRACE_FILE = trace_file
    
    print(f"\n{'='*50}")
    print(f"  DialecticAI Dashboard (FastAPI)")
    print(f"  URL: http://{host}:{port}")
    print(f"  WebSocket: ws://{host}:{port}/ws/stream")
    print(f"  Trace: {trace_file}")
    print(f"  Ctrl+C to stop")
    print(f"{'='*50}\n")
    
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", default="trace.jsonl")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    run(port=args.port, trace_file=args.trace)