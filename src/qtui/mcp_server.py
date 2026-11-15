import os
import threading
import time
from pathlib import Path

import uvicorn
from mcp.server.mcpserver import MCPServer as FastMCP
from src.qtui.projects import project_manger
from src.qtui.settings_cfg import cfg


MCP_HOST = "127.0.0.1"
MCP_PORT = 8765


class MCPServer:
    def __init__(self):
        self._server = None
        self._thread = None
        self._error = None
        self._mcp = FastMCP(
            "MIO-KITCHEN",
        )
        self._register_tools()

    def _register_tools(self):
        @self._mcp.tool()
        def list_projects() -> list[str]:
            """List the projects available in MIO-KITCHEN."""
            return sorted(project_manger.get_projects())

        @self._mcp.tool()
        def get_active_project() -> dict[str, str | bool]:
            """Get the name and structure of the currently selected project."""
            name = cfg.currentProjectName.value
            return {
                "name": name,
                "exists": bool(name and project_manger.exist(name)),
                "structure": cfg.projectStructure.value,
            }

        @self._mcp.tool()
        def list_project_files(project_name: str | None = None, relative_path: str = "") -> list[str]:
            """List entries in a project folder; paths are relative to the project root."""
            name = project_name or cfg.currentProjectName.value
            projects = set(project_manger.get_projects())
            if not name or name not in projects:
                raise ValueError(f"Unknown project: {name or '(none selected)'}")

            project_root = Path(project_manger.get_work_path(name)).resolve()
            requested_path = (project_root / relative_path).resolve()
            try:
                if os.path.commonpath((str(project_root), str(requested_path))) != str(project_root):
                    raise ValueError("The requested path must stay inside the project.")
            except ValueError as error:
                raise ValueError("The requested path must stay inside the project.") from error
            if not requested_path.is_dir():
                raise ValueError(f"Project directory does not exist: {relative_path or '.'}")

            entries = sorted(requested_path.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.casefold()))
            results = []
            for entry in entries[:200]:
                resolved_entry = entry.resolve()
                if os.path.commonpath((str(project_root), str(resolved_entry))) != str(project_root):
                    continue
                results.append(f"{entry.name}/" if entry.is_dir() else entry.name)
            return results

    @property
    def is_running(self):
        return bool(self._thread and self._thread.is_alive() and self._server and self._server.started)

    def start(self):
        if self.is_running:
            return True

        self._error = None
        server = uvicorn.Server(
            uvicorn.Config(
                self._mcp.streamable_http_app(),
                host=MCP_HOST,
                port=MCP_PORT,
                log_level="error",
            )
        )

        def run_server():
            try:
                server.run()
            except Exception as error:
                self._error = error

        thread = threading.Thread(target=run_server, name="MioMCPServer", daemon=True)
        self._server = server
        self._thread = thread
        thread.start()

        deadline = time.monotonic() + 5
        while thread.is_alive() and not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        if server.started:
            return True

        server.should_exit = True
        thread.join(timeout=3)
        self._server = None
        self._thread = None
        if self._error:
            raise RuntimeError(f"Unable to start MCP server: {self._error}") from self._error
        raise RuntimeError(f"Unable to start MCP server on {MCP_HOST}:{MCP_PORT}.")

    def stop(self):
        server = self._server
        thread = self._thread
        if server is None or thread is None or not thread.is_alive():
            self._server = None
            self._thread = None
            return True

        server.should_exit = True
        thread.join(timeout=3)
        if thread.is_alive():
            return False

        self._server = None
        self._thread = None
        return True
