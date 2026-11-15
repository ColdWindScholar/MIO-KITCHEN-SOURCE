import json
import os
from pathlib import Path

from flask import Flask, jsonify, request

from src.qtui.projects import project_manger
from src.qtui.settings_cfg import cfg


MCP_PROTOCOL_VERSION = "2025-03-26"


class MCPServer:
    def __init__(self, app: Flask):
        self._app = app
        self._enabled = False
        self._tools = {
            "list_projects": {
                "description": "List the projects available in MIO-KITCHEN.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                "handler": self._list_projects,
            },
            "get_active_project": {
                "description": "Get the name and structure of the currently selected project.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                "handler": self._get_active_project,
            },
            "list_project_files": {
                "description": "List entries in a project folder; paths are relative to the project root.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string", "description": "Project name; defaults to the active project."},
                        "relative_path": {"type": "string", "description": "Folder path relative to the project root."},
                    },
                    "additionalProperties": False,
                },
                "handler": self._list_project_files,
            },
        }
        self._app.add_url_rule("/mcp", "mcp", self._handle_request, methods=["POST"])

    def _list_projects(self):
        return sorted(project_manger.get_projects())

    def _get_active_project(self):
        name = cfg.currentProjectName.value
        return {
            "name": name,
            "exists": bool(name and project_manger.exist(name)),
            "structure": cfg.projectStructure.value,
        }

    def _list_project_files(self, arguments):
        name = arguments.get("project_name") or cfg.currentProjectName.value
        relative_path = arguments.get("relative_path", "")
        if not isinstance(relative_path, str):
            raise ValueError("relative_path must be a string.")

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

    @staticmethod
    def _rpc_error(request_id, code, message):
        return jsonify({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})

    def _handle_request(self):
        if not self._enabled:
            return jsonify({"error": "MCP is stopped. Start it from the Connect page."}), 503
        if request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify({"error": "MCP endpoint is available only on localhost."}), 403
        if not request.is_json:
            return jsonify({"error": "Expected an application/json MCP request."}), 400

        try:
            payload = request.get_json()
        except (json.JSONDecodeError, ValueError):
            return self._rpc_error(None, -32700, "Parse error."), 400

        if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str):
            return self._rpc_error(None, -32600, "Invalid Request."), 400

        method = payload["method"]
        request_id = payload.get("id")
        is_notification = "id" not in payload
        params = payload.get("params") or {}
        if not isinstance(params, dict):
            return self._rpc_error(request_id, -32600, "Invalid params."), 400

        if is_notification:
            return "", 202

        if method == "initialize":
            result = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "MIO-KITCHEN", "version": "1.0.0"},
            }
            return jsonify({"jsonrpc": "2.0", "id": request_id, "result": result})

        if method == "ping":
            return jsonify({"jsonrpc": "2.0", "id": request_id, "result": {}})

        if method == "tools/list":
            tools = [
                {"name": name, "description": definition["description"], "inputSchema": definition["inputSchema"]}
                for name, definition in self._tools.items()
            ]
            return jsonify({"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}})

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            tool = self._tools.get(tool_name) if isinstance(tool_name, str) else None
            if tool is None:
                return jsonify(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True},
                    }
                )
            if not isinstance(arguments, dict):
                return self._rpc_error(request_id, -32602, "Tool arguments must be an object.")
            try:
                value = tool["handler"]() if tool_name != "list_project_files" else tool["handler"](arguments)
                return jsonify(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                            "isError": False,
                        },
                    }
                )
            except (OSError, ValueError) as error:
                return jsonify(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"content": [{"type": "text", "text": str(error)}], "isError": True},
                    }
                )

        return self._rpc_error(request_id, -32601, f"Method not found: {method}"), 404

    @property
    def is_running(self):
        return self._enabled

    def start(self):
        if self.is_running:
            return True
        self._enabled = True
        return True

    def stop(self):
        self._enabled = False
        return True
