@echo off
chcp 65001 >nul
title API Connection Test Tool

cd /d "%~dp0"

echo.
echo ============================================================
echo   Light-Enterprise AI - API Connection Test
echo ============================================================
echo.

REM --- Python check ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

REM --- Choose python.exe with priority: venv -> global ---
if exist ".venv\Scripts\python.exe" (
    set "PYEXE=.venv\Scripts\python.exe"
) else (
    set "PYEXE=python"
)

echo [Step 1] Verifying API configuration ...
%PYEXE% -c "
import sys, os
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    print('  - python-dotenv not installed. Installing ...')
    os.system('\"' + sys.executable + '\" -m pip install python-dotenv httpx >nul 2>&1')
    from dotenv import load_dotenv

root = Path(r'%~dp0').resolve()
# Find backend/.env or .env.example
env_file = root / 'backend' / '.env'
if not env_file.exists():
    env_file = root / 'backend' / '.env.example'
if not env_file.exists():
    env_file = root / '.env'
load_dotenv(env_file)

api_key = os.getenv('CLOUD_API_KEY', '')
api_base = os.getenv('CLOUD_API_BASE', 'http://localhost:3000').rstrip('/')
model = os.getenv('CLOUD_MODEL_NAME', 'gpt-4o-mini')
emb_model = os.getenv('CLOUD_EMBEDDING_MODEL', 'text-embedding-3-small')

masked = api_key[:4] + '****' + api_key[-6:] if len(api_key) > 10 else (api_key or '(empty)')
print(f'  - env file     : {env_file}')
print(f'  - API base     : {api_base}')
print(f'  - chat model   : {model}')
print(f'  - embed model  : {emb_model}')
print(f'  - api key      : {masked}')
print()
" 2>nul

echo [Step 2] Testing /chat/completions ...
%PYEXE% -c "
import sys, os
from pathlib import Path
try:
    import httpx
except ImportError:
    os.system('\"' + sys.executable + '\" -m pip install httpx >nul 2>&1')
    import httpx
try:
    from dotenv import load_dotenv
except ImportError:
    os.system('\"' + sys.executable + '\" -m pip install python-dotenv >nul 2>&1')
    from dotenv import load_dotenv

root = Path(r'%~dp0').resolve()
env_file = root / 'backend' / '.env'
if not env_file.exists():
    env_file = root / 'backend' / '.env.example'
load_dotenv(env_file)

api_key = os.getenv('CLOUD_API_KEY', '')
api_base = os.getenv('CLOUD_API_BASE', 'http://localhost:3000').rstrip('/')
model = os.getenv('CLOUD_MODEL_NAME', 'gpt-4o-mini')
verify = api_base.startswith('https://')

try:
    with httpx.Client(timeout=30.0, verify=verify) as client:
        r = client.post(
            api_base + '/chat/completions',
            json={'model': model, 'messages': [{'role': 'user', 'content': 'Say hello in one sentence.'}], 'max_tokens': 80, 'temperature': 0.1},
            headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}
        )
        r.raise_for_status()
        data = r.json()
        answer = (data.get('choices', [{}])[0].get('message', {}).get('content', '') or
                  data.get('choices', [{}])[0].get('text', '') or
                  data.get('response', ''))
        print(f'  OK - model reply: {answer.strip()[:120]}')
except Exception as e:
    print(f'  FAILED: {e}')
    print('  Check: (1) is your proxy at ' + api_base + ' running? (2) is the model name correct?')
    sys.exit(1)
"
if errorlevel 1 (
    echo.
    echo [ERROR] Chat test failed - see message above.
    pause
    exit /b 1
)

echo.
echo [Step 3] Testing /embeddings (used by RAG retrieval) ...
%PYEXE% -c "
import sys, os
from pathlib import Path
import httpx
try:
    from dotenv import load_dotenv
except ImportError:
    os.system('\"' + sys.executable + '\" -m pip install python-dotenv >nul 2>&1')
    from dotenv import load_dotenv

root = Path(r'%~dp0').resolve()
env_file = root / 'backend' / '.env'
if not env_file.exists():
    env_file = root / 'backend' / '.env.example'
load_dotenv(env_file)

api_key = os.getenv('CLOUD_API_KEY', '')
api_base = os.getenv('CLOUD_API_BASE', 'http://localhost:3000').rstrip('/')
emb_model = os.getenv('CLOUD_EMBEDDING_MODEL', 'text-embedding-3-small')
verify = api_base.startswith('https://')

try:
    with httpx.Client(timeout=30.0, verify=verify) as client:
        r = client.post(
            api_base + '/embeddings',
            json={'model': emb_model, 'input': 'hello world test text'},
            headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}
        )
        r.raise_for_status()
        data = r.json()
        vec = data.get('data', [{}])[0].get('embedding', [])
        if vec:
            print(f'  OK - vector dimension = {len(vec)}')
        else:
            print('  WARN - endpoint returned empty vector; RAG will be disabled.')
except Exception as e:
    print(f'  WARN - {e}')
    print('  (You can still chat without RAG, just disable use_rag in the UI.)')
"

echo.
echo ============================================================
echo   All tests finished. You can now run start.bat to launch.
echo ============================================================
echo.
pause
