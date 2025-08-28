from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/ingest")
async def ingest(request: Request):
    data = await request.json()
    print("Received:", data)
    return JSONResponse(content={"status": "ok", "received": data})
