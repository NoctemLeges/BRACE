import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"

MSF_RPC_HOST = os.getenv("MSF_RPC_HOST", "127.0.0.1")
MSF_RPC_PORT = int(os.getenv("MSF_RPC_PORT", "55553"))
MSF_RPC_USER = os.getenv("MSF_RPC_USER", "msf")
MSF_RPC_PASS = os.getenv("MSF_RPC_PASS", "")
MSF_RPC_SSL = os.getenv("MSF_RPC_SSL", "true").lower() in ("1", "true", "yes")

RED_TEAM_ALLOWLIST = os.getenv("RED_TEAM_ALLOWLIST", "")
