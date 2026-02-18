import argparse
import os
import json
import requests
import jsonschema
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class UserRequest(BaseModel):
    input: str

SCHEMA_SERVICE_URL = os.getenv('SCHEMA_SERVICE_URL', 'http://localhost:5001')
VALUES_SERVICE_URL = os.getenv('VALUES_SERVICE_URL', 'http://localhost:5002')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://host.docker.internal:11434')
OLLAMA_MODEL = "qwen2.5:3b-instruct"

def query_ollama(prompt, system_prompt="You are a helpful assistant."):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,    
            "num_ctx": 8192,       
            "num_predict": -1      
        }
    }
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate", 
            json=payload, 
            timeout=180  
        )
        return response.json().get("response", "").strip()
    except Exception as e:
        print(f"Ollama Error: {e}")
        return None

def extract_json_from_text(text):
    """
    JSON'u text içinden çıkarır. 
    Geliştirilmiş versiyon: İlk '}' gördüğü yerde durmaz, 
    en son geçerli '}' parantezine kadar bakar (Greedy Match).
    """
    if not text:
        return text

    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    start = text.find("{")
    end = text.rfind("}") 

    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    
    return text

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def fill_required_objects(schema: dict, instance: dict):
    if not isinstance(schema, dict) or not isinstance(instance, dict):
        return

    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for key in required:
        if key not in instance:
            prop = properties.get(key)
            if prop and prop.get("type") == "object":
                instance[key] = {}

    for key, subschema in properties.items():
        if key in instance and isinstance(instance[key], dict):
            fill_required_objects(subschema, instance[key])

def cleanup_k8s_probe_fields(obj):
    if isinstance(obj, dict):
        if "livenessProbe" in obj:
            if "liveness" not in obj:
                obj["liveness"] = obj["livenessProbe"]
            del obj["livenessProbe"]

        if "readinessProbe" in obj:
            del obj["readinessProbe"]

        if "startupProbe" in obj:
            del obj["startupProbe"]

        for v in obj.values():
            cleanup_k8s_probe_fields(v)

    elif isinstance(obj, list):
        for item in obj:
            cleanup_k8s_probe_fields(item)

# ---------------------------------------------------------
# MAIN LOGIC
# ---------------------------------------------------------

def process_request_jk(user_input):

    identify_prompt = f"""
Input: "{user_input}"

Task: Identify which application this request belongs to.
Options: chat, matchmaking, tournament.

Return ONLY the single word. Nothing else.
"""

    raw = query_ollama(
        identify_prompt,
        "You are a classifier. Output only one word: chat, matchmaking, or tournament."
    )

    if not raw:
        return None, "AI failed to identify app."

    raw = raw.lower().strip().replace('"', '').replace("'", "")
    print("IDENTIFY RAW:", raw)

    app_name = None
    for name in ["chat", "matchmaking", "tournament"]:
        if name in raw:
            app_name = name
            break

    if not app_name:
        return None, "AI failed to identify app."

    try:
        s_resp = requests.get(f"{SCHEMA_SERVICE_URL}/{app_name}", timeout=10)
        v_resp = requests.get(f"{VALUES_SERVICE_URL}/{app_name}", timeout=10)

        if s_resp.status_code != 200 or v_resp.status_code != 200:
            return None, "App not found."

    except Exception as e:
        return None, f"Service connection error: {e}"

    schema_json = s_resp.json()
    values_json = v_resp.json()

    mod_prompt = f"""
You are a Configuration Bot. Your goal is to update the JSON below based on the user request.

### INSTRUCTIONS:
1. Parse the "Current JSON".
2. Apply the "User Request" modification.
3. Output the FULL Valid JSON.
4. **CRITICAL RULE**: Do NOT repeat keys. (e.g., Do not write "services" twice).
5. **CRITICAL RULE**: Ensure "namespace" and other root keys are preserved.

### DATA:
User Request: "{user_input}"

Current JSON:
{json.dumps(values_json)}

### OUTPUT:
Return ONLY the JSON code. No explanations.
"""

    llm_resp = query_ollama(mod_prompt, "You are a JSON generator. Output valid JSON only. Do not duplicate keys.")

    if not llm_resp:
        return None, "LLM did not return a response."

    clean_json = extract_json_from_text(llm_resp)

    print("--- LLM RAW RESPONSE ---")
    print(clean_json[:500] + "... [truncated] ..." + clean_json[-200:]) 
    print("------------------------")
    
    try:
        new_values = json.loads(clean_json)

        cleanup_k8s_probe_fields(new_values)
        fill_required_objects(schema_json, new_values)

        jsonschema.validate(new_values, schema_json)

        return new_values, None

    except Exception as first_error:
        print(f"Validation Error 1: {first_error}")

        retry_prompt = f"""
ERROR: The JSON you generated is invalid.
Reason: {str(first_error)}

You must fix the JSON structure.
1. Make sure there are NO duplicate keys.
2. Make sure all required fields (like 'namespace') are present.
3. Return the FULL corrected JSON.

Previous Invalid Output:
{clean_json}
"""

        retry_resp = query_ollama(retry_prompt, "Fix the JSON. Output ONLY valid JSON.")

        if not retry_resp:
            return None, f"Validation failed: {str(first_error)}"

        retry_clean = extract_json_from_text(retry_resp)

        try:
            fixed = json.loads(retry_clean)

            cleanup_k8s_probe_fields(fixed)
            fill_required_objects(schema_json, fixed)

            jsonschema.validate(fixed, schema_json)

            return fixed, None

        except Exception as e2:
            return None, f"Validation failed after retry: {str(e2)}"


@app.post("/message")
def handle_message(request: UserRequest):
    result, error = process_request_jk(request.input)

    if error:
        print(f"ERROR DETAILS: {error}")
        raise HTTPException(status_code=500, detail=error)

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--listen', type=str, default='0.0.0.0:5003')
    args = parser.parse_args()

    host, port = args.listen.split(':')
    uvicorn.run(app, host=host, port=int(port))