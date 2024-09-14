import asyncio
import os

import uvicorn
from chainlit.utils import mount_chainlit
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

APP_PORT = os.environ.get("APP_PORT", "8000")

app = FastAPI(title="llm-chainlit-playground",
              description="LLM Chainlit Playground",
              version="0.0.1",
              docs_url='/v2/api/docs',
              redoc_url='/v2/api/redoc',
              openapi_url='/v2/api/openapi.json')


@app.get("/hello")
def read_main():
    return {"message": "hello world"}


async def main():
    mount_chainlit(app=app, target="chainlit_app.py", path="")
    config = uvicorn.Config(
        app, host="0.0.0.0",
        port=int(APP_PORT),
        log_level="info",
        ws_max_queue=500,
        forwarded_allow_ips="*"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == '__main__':
    asyncio.run(main())
