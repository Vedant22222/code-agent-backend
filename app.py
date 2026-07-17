import re
import os
import sys
import subprocess
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

# 1. Load Keys
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI(title="Hybrid Code Agent API")

# 2. CORS Bypass
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerationRequest(BaseModel):
    prompt: str

def generate_code_cloud(prompt: str, error_log: str = None) -> str:
    """Uses Groq Llama 3.1 to write code in milliseconds."""
    system_instruction = (
        "You are an automated Python code generation engine. "
        "Write functional, clean code based on the user's problem. "
        "CRITICAL: Return ONLY raw, executable Python code. Do NOT use markdown formatting. "
        "CRITICAL RULE: You MUST include an execution block at the bottom of your script "
        "that calls the functions with sample data and uses print() to output results."
    )
    
    user_message = prompt
    if error_log:
        user_message = f"Your previous code crashed with this error:\n{error_log}\n\nPlease fix it. Original request: {prompt}"

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_message}
        ],
        model="llama-3.1-8b-instant", 
        temperature=0.2
    )
    
    code = response.choices[0].message.content.strip()
    
    # NEW ROBUST CLEANING LOGIC
    # Scan for code inside markdown blocks, ignoring surrounding conversation
    match = re.search(r'```(?:python|py)?\n?(.*?)```', code, re.DOTALL | re.IGNORECASE)
    
    if match:
        # Extract just the code inside the backticks
        code = match.group(1).strip()
    else:
        # Fallback: aggressively strip any stray backticks just in case
        code = code.replace("```python", "").replace("```", "").strip()
        
    return code

def execute_sandbox_hybrid(code: str) -> tuple[int, str]:
    """Executes code securely using an isolated temporary file."""
    unique_id = uuid.uuid4().hex
    temp_filename = f"sandbox_{unique_id}.py"
    
    try:
        with open(temp_filename, "w", encoding="utf-8") as f:
            f.write(code)
            
        result = subprocess.run(
            [sys.executable, temp_filename],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return 0, result.stdout
        else:
            return result.returncode, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "Execution Error: Timeout limit hit. Possible infinite loop."
    finally:
        # Guarantee cleanup even if it crashes
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.post("/generate")
async def generate_and_heal(request: GenerationRequest):
    current_error = None
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        generated_code = generate_code_cloud(request.prompt, current_error)
        exit_code, log = execute_sandbox_hybrid(generated_code)
        
        if exit_code == 0:
            return {
                "status": "success",
                "attempts": attempt,
                "output": log.strip(),
                "code": generated_code
            }
        else:
            current_error = log
            
    raise HTTPException(status_code=500, detail=f"Failed to heal code. Last error: {current_error}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)