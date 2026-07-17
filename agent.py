import subprocess
import os
import sys
from ollama import chat

# Core Configuration
MODEL_NAME = "llama3:latest"
TEMP_FILE = "sandbox_run.py"

def generate_code(prompt: str, error_log: str = None) -> str:
    """
    Queries Ollama to generate or fix Python code based on system instructions.
    """
    system_instruction = (
        "You are an automated Python code generation engine. "
        "Your task is to write functional, clean, and executable code based on the user's problem. "
        "CRITICAL: Return ONLY the raw code inside your response. Do NOT use markdown code blocks "
        "(do not use ```python), do not add descriptions, and do not include conversational text. "
        "Your output must be directly writable to a file and run by a Python interpreter."
    )
    
    # If this is a retry due to a crash, we append the error context
    user_message = prompt
    if error_log:
        user_message = f"Your previous code crashed with this error:\n{error_log}\n\nPlease fix it. Original request: {prompt}"

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_message}
    ]
    
    print("\n[Agent] Thinking and generating code...")
    response = chat(model=MODEL_NAME, messages=messages)
    
    # Clean up potential stray markdown formatting if the LLM slips up
    code = response['message']['content'].strip()
    if code.startswith("```"):
        code = "\n".join(code.split("\n")[1:-1])
    return code

def run_in_sandbox() -> tuple[int, str]:
    """
    Executes the generated code in an isolated subprocess with a timeout constraint.
    Returns a tuple of (exit_code, output_or_error_log).
    """
    print("[Sandbox] Triggering execution...")
    try:
        # Run the script as a totally separate process
        # stdout and stderr capture outputs/errors; timeout prevents infinite loops
        result = subprocess.run(
            [sys.executable, TEMP_FILE],
            capture_output=True,
            text=True,
            timeout=5  # Strict execution limit
        )
        
        if result.returncode == 0:
            return 0, result.stdout
        else:
            return result.returncode, result.stderr

    except subprocess.TimeoutExpired:
        return -1, "Execution Error: The script hit a strict 5-second timeout limit. An infinite loop or resource lock was detected."
def main():
    user_prompt = "Write a Python script that fetches the current Bitcoin price using the public CoinDesk API (https://api.coindesk.com/v1/bpi/currentprice.json). You MUST use the built-in 'urllib' module. Do not use the 'requests' library. Parse the JSON and print only the float value of the USD price."
    
    current_error = None
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        print(f"\n--- ATTEMPT {attempt} ---")
        
        # 1. Generate code
        generated_code = generate_code(user_prompt, current_error)
        
        # 2. Write code to a local temporary runtime file
        with open(TEMP_FILE, "w", encoding="utf-8") as f:
            f.write(generated_code)
            
        # 3. Test execution in sandbox
        exit_code, log = run_in_sandbox()
        
        if exit_code == 0:
            print("\n[SUCCESS] Code executed successfully without errors!")
            print(f"Output:\n{log}")
            print(f"\nFinal Verified Script written to: {TEMP_FILE}")
            return
        else:
            print(f"\n[CRASH DETECTED] Exit Code: {exit_code}")
            print(f"Captured Error Log:\n{log}")
            current_error = log  # Set error context for the next iteration
            
    print("\n[FAILURE] Agent failed to heal the code within the retry limit.")

if __name__ == "__main__":
    main()    
  