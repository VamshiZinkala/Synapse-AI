import os
from langchain_mcp_adapters.client import MultiServerMCPClient

SERVERS = {
    # "ocr_engine": {
    #     "command": "python",
    #     "args": [r"C:\Users\z005a42h\Documents\Rag-application\ocr-mcp-server\ocr_server.py"],
    #     "env": {},
    #     "transport": "stdio"
    # },
    "expense_tracker": {
        "command": r"C:\Users\z005a42h\AppData\Local\Programs\Python\Python313\Scripts\uv.exe",
        "args": [
            "--directory", 
            r"C:\Users\z005a42h\Documents\Rag-application\expense-mcp-server", 
            "run", 
            "main.py"
        ],
        "transport": "stdio"
    }
}


class MCPToolManager:
    def __init__(self):
        self.mcp_tools = []
        self.client = None
        self.mcp_resources = []
    async def initialize(self, config_dicts):
        """Connects to all user-configured MCP Servers and extracts their tools."""
        print("Initializing MCP Client Connections...")

        self.client = MultiServerMCPClient(config_dicts)

        self.mcp_tools = await self.client.get_tools()
        
        print(f"Successfully loaded {len(self.mcp_tools)} dynamic MCP tools!")

        return self.mcp_tools

mcp_manager = MCPToolManager()
