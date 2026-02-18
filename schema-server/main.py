import argparse
import os
import uvicorn
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()

SCHEMA_DIR = "/data/schemas"

@app.get("/{app_name}")
def get_schema(app_name: str):
    if ".." in app_name or "/" in app_name:
        raise HTTPException(status_code=400, detail="Invalid application name")

    file_path = os.path.join(SCHEMA_DIR, f"{app_name}.schema.json")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Schema not found")
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load schema file")

    
    return JSONResponse(content=data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--schema-dir', type=str, default='/data/schemas')
    parser.add_argument('--listen', type=str, default='0.0.0.0:5001')
    args = parser.parse_args()

    SCHEMA_DIR = args.schema_dir
    host, port = args.listen.split(':')
    
    uvicorn.run(app, host=host, port=int(port))