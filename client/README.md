# Company Brain desktop client

The PySide6 window checks the backend using `GET /api/health` and displays the result.

## Run on Windows

Start the API using the [backend setup instructions](../backend/README.md). With Python 3.12 on your PATH, run the following from the repository root in PowerShell.

```powershell
cd client
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\company-brain-client.exe
```

Click **Check server connection**. The default backend address is `http://127.0.0.1:8000`. Set `$env:COMPANY_BRAIN_API_URL` before launching to use a different base URL, such as the Nginx HTTPS address.
