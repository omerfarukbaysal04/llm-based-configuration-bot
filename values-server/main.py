import argparse
import os
import uvicorn
from fastapi import FastAPI, HTTPException
import json
from fastapi.responses import JSONResponse

app = FastAPI()

VALUES_DIR = "/data/values"

@app.get("/{app_name}")
def get_values(app_name: str):
    if ".." in app_name or "/" in app_name:
        raise HTTPException(status_code=400, detail="Invalid application name")

    file_path = os.path.join(VALUES_DIR, f"{app_name}.value.json")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Values not found")
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return JSONResponse(content=data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--values-dir', type=str, default='/data/values')
    parser.add_argument('--schema-dir', type=str, dest='values_dir') 
    parser.add_argument('--listen', type=str, default='0.0.0.0:5002')
    
    args = parser.parse_args()

    VALUES_DIR = args.values_dir
    host, port = args.listen.split(':')
    
    uvicorn.run(app, host=host, port=int(port))