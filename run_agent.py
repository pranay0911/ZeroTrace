import uvicorn # type: ignore
from agent import app

if __name__ == "__main__":
    print("🛡️ ZeroTrace Agent is booting up...")
    print("Listening for Central Command on port 8000...")
    # This tells Python to run our FastAPI app directly from the script
    uvicorn.run(app, host="127.0.0.1", port=8000)