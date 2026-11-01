import json
import platform
import socket
import uuid
from datetime import datetime
from io import BytesIO
from platform import system, machine
from threading import Lock, Thread

import qrcode
import simple_websocket
from PySide6.QtCore import Signal, QObject, Qt, QSize
from PySide6.QtGui import QPixmap, QImage, QFont, QTextCursor, QTextCharFormat, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from flask import Flask, request, jsonify
from flask_sock import Sock
from werkzeug.serving import make_server
from qfluentwidgets import (
    CardWidget,
    BodyLabel,
    TitleLabel,
    PrimaryPushButton,
    PushButton,
    IconWidget,
    FluentIcon, TextEdit
)
from simple_websocket import Server
from wsproto.frame_protocol import CloseReason

from src.qtui.projects import ProjectsPage, project_manger
from src.core.utils import v_code


class NetworkBridge(QObject):
    trigger_signal = Signal(object)
    log_signal = Signal(str, str)
    connection_status_signal = Signal(bool, dict)
    send_ws_message = Signal(str)

    def __init__(self):
        super().__init__()
        self._websocket: Server | None = None
        self._websocket_lock = Lock()

    def attach_websocket(self, websocket: Server):
        with self._websocket_lock:
            previous = self._websocket
            if previous is not None:
                try:
                    self.send_ws_message.disconnect(previous.send)
                except (TypeError, RuntimeError):
                    pass
                try:
                    previous.close(CloseReason.NORMAL_CLOSURE, message="Replaced by a new connection.")
                except simple_websocket.errors.ConnectionClosed:
                    pass

            self._websocket = websocket
            self.send_ws_message.connect(websocket.send)

    def detach_websocket(self, websocket: Server | None = None):
        with self._websocket_lock:
            active_websocket = self._websocket
            if active_websocket is None or (websocket is not None and active_websocket is not websocket):
                return None

            self._websocket = None
            try:
                self.send_ws_message.disconnect(active_websocket.send)
            except (TypeError, RuntimeError):
                pass
            return active_websocket


flask_backend = Flask(__name__)
sock_app = Sock(flask_backend)
network_bridge = NetworkBridge()

ACTIVE_SESSION = {
    "token": None,
    "device_name": None,
    "device_ip": None,
    "verify_code": v_code(4),
}


def disconnect(close_websocket=False, websocket: Server | None = None):
    active_websocket = network_bridge.detach_websocket(websocket)
    if websocket is not None and active_websocket is None:
        return False

    ACTIVE_SESSION["token"] = None
    ACTIVE_SESSION["device_name"] = None
    ACTIVE_SESSION["device_ip"] = None
    if close_websocket and active_websocket is not None:
        try:
            active_websocket.close(CloseReason.NORMAL_CLOSURE, message="User Disconnect.[Desktop]")
        except simple_websocket.errors.ConnectionClosed:
            pass
    network_bridge.connection_status_signal.emit(False, {})
    return True


@flask_backend.route('/connect', methods=['POST'])
def handle_handshake():
    if ACTIVE_SESSION["token"]:
        return "Connected by another device.", 403
    request_data = request.get_json() or {}
    device_name = request_data.get("DeviceName", 'Device')
    if request_data['verify_code'] != ACTIVE_SESSION["verify_code"]:
        return "Invalid verification code.", 403
    device_ip = request.remote_addr

    generated_token = str(uuid.uuid4())

    ACTIVE_SESSION["token"] = generated_token
    ACTIVE_SESSION["device_name"] = device_name
    ACTIVE_SESSION["device_ip"] = device_ip

    network_bridge.connection_status_signal.emit(True, {"device": device_name, "ip": device_ip})
    network_bridge.log_signal.emit("SUCCESS", f"Session registered for {device_name} ({device_ip}). Token issued.")

    return jsonify({"token": generated_token}), 200


@flask_backend.route('/disconnect', methods=['POST'])
def handle_disconnect():
    if not ACTIVE_SESSION["token"]:
        return "Disconnected already.", 200
    auth_header = request.headers.get('Authorization', None)
    if not auth_header:
        return f"Unauthorized: Missing header", 401
    if auth_header != 'MioKey' + ACTIVE_SESSION["token"]:
        return f"Unauthorized: Invalid header", 403
    device_ip = request.remote_addr

    disconnect(close_websocket=True)
    network_bridge.log_signal.emit("SUCCESS", f"Disconnected by {device_ip}")

    return "Disconnected already.", 200


@flask_backend.route('/get_info', methods=['POST'])
def get_device_info():
    auth_header = request.headers.get('Authorization', None)
    if not auth_header or not auth_header.startswith('MioKey'):
        network_bridge.log_signal.emit("WARN", f"Refused unauthenticated client request.")
        return "Unauthorized: Missing header", 401
    if ACTIVE_SESSION["token"] is None or auth_header[6:] != ACTIVE_SESSION["token"]:
        network_bridge.log_signal.emit("WARN", "Request dropped. Bad verification signature.")
        return "Unauthorized: Invalid key token", 403
    json_text = json.dumps(
        {"device_name": platform.node(), "system": system(), "machine": machine(), "kernel": platform.release()},
        ensure_ascii=True)
    return json_text, 200


@flask_backend.route('/action', methods=['POST'])
def handle_incoming_phone_action():
    auth_header = request.headers.get('Authorization', None)
    if not auth_header or not auth_header.startswith('MioKey'):
        network_bridge.log_signal.emit("WARN", f"Refused unauthenticated client request.")
        return "Unauthorized: Missing header", 401

    if ACTIVE_SESSION["token"] is None or auth_header[6:] != ACTIVE_SESSION["token"]:
        network_bridge.log_signal.emit("WARN", "Request dropped. Bad verification signature.")
        return "Unauthorized: Invalid key token", 403

    network_bridge.log_signal.emit("INFO", f"Action request  authorized. Processing task...")
    payload = request.get_json() or {}
    network_bridge.trigger_signal.emit(payload)
    return f"Action handled securely", 200


#
@sock_app.route('/socket')
def handle_actions(ws: Server):
    auth_header = request.headers.get('Authorization', None)
    if not auth_header or not auth_header.startswith('MioKey'):
        network_bridge.log_signal.emit("WARN", f"Refused unauthenticated client request.")
        return "Unauthorized: Missing header", 401

    if ACTIVE_SESSION["token"] is None or auth_header[6:] != ACTIVE_SESSION["token"]:
        network_bridge.log_signal.emit("WARN", "Request dropped. Bad verification signature.")
        return "Unauthorized: Invalid key token", 403

    network_bridge.log_signal.emit("INFO", "Websocket connected...")
    network_bridge.attach_websocket(ws)
    try:
        while True:
            try:
                data = ws.receive(timeout=15)
            except Exception as e:
                network_bridge.log_signal.emit("WARN", f"TCP connection collapsed {e}")
                break
            if data is None:
                break
            network_bridge.trigger_signal.emit(data)
    finally:
        disconnect(websocket=ws)


def fetch_linux_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temp_socket:
            temp_socket.connect(("8.8.8.8", 80))
            return temp_socket.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def list_project():
    return list(project_manger.get_projects())


class ConnectPage(QWidget):
    def __init__(self, parent=None, projectPage: ProjectsPage = None):
        super().__init__(parent)
        self.setObjectName("ConnectPage")
        self.projectPage = projectPage
        base_horizontal_layout = QHBoxLayout(self)
        base_horizontal_layout.setContentsMargins(24, 24, 24, 24)
        base_horizontal_layout.setSpacing(24)

        self.left_card = CardWidget(self)
        left_layout = QVBoxLayout(self.left_card)
        left_layout.setContentsMargins(24, 24, 24, 24)
        left_layout.setSpacing(16)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Header Typography Node
        self.title_label = TitleLabel(self.tr("Connect ImageStudio"), self)
        left_layout.addWidget(self.title_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Container elements for dynamic visibility toggle
        self.instructions = BodyLabel(
           self.tr("Scan via ImageStudio to manage your projects and images on your Android phone."), self)
        self.instructions.setWordWrap(True)
        self.instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.instructions)

        # Vector Icon Layer (Fluent Design standard)
        self.phone_icon_widget = IconWidget(FluentIcon.CONNECT, self)
        self.phone_icon_widget.setFixedSize(72, 72)
        self.phone_icon_widget.hide()  # Hidden initially while waiting for connection
        left_layout.addWidget(self.phone_icon_widget, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.qr_wrapper = CardWidget(self)
        qr_wrapper_layout = QVBoxLayout(self.qr_wrapper)
        qr_wrapper_layout.setContentsMargins(8, 8, 8, 8)
        self.qr_display_container = BodyLabel(self)
        self.qr_display_container.setFixedSize(QSize(200, 200))
        self.qr_display_container.setScaledContents(True)
        qr_wrapper_layout.addWidget(self.qr_display_container)
        left_layout.addWidget(self.qr_wrapper, alignment=Qt.AlignmentFlag.AlignCenter)

        self.address_label = BodyLabel(self)
        self.address_label.setFont(QFont("Consolas", 12))
        left_layout.addWidget(self.address_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.status_device = BodyLabel("", self)
        self.status_ip = BodyLabel("", self)
        left_layout.addWidget(self.status_device, alignment=Qt.AlignmentFlag.AlignHCenter)
        left_layout.addWidget(self.status_ip, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.disconnect_btn = PrimaryPushButton(self.tr("Disconnect"), self)
        self.disconnect_btn.clicked.connect(self.manually_terminate_session)
        self.disconnect_btn.hide()
        left_layout.addWidget(self.disconnect_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        base_horizontal_layout.addWidget(self.left_card, stretch=2)

        right_panel_container = QVBoxLayout()
        right_panel_container.setSpacing(8)

        self.console_log_view = TextEdit(self)
        self.console_log_view.setFont(QFont("Consolas", 10))
        self.console_log_view.setReadOnly(True)
        right_panel_container.addWidget(self.console_log_view)

        base_horizontal_layout.addLayout(right_panel_container, stretch=3)

        self.lan_ip = fetch_linux_lan_ip()
        self.address_label.setText(f"http://{self.lan_ip}:5000")
        self.address_label.setStyleSheet("color: green; font-style: bold;")
        self.refresh_qr_matrix()

        server_controls = QHBoxLayout()
        self.server_status_label = BodyLabel(self.tr("Server: stopped"), self)
        self.server_toggle_btn = PrimaryPushButton(self.tr("Start Server"), self)
        self.server_toggle_btn.clicked.connect(self.toggle_server)
        self.server_restart_btn = PushButton(self.tr("Restart Server"), self)
        self.server_restart_btn.clicked.connect(self.restart_server)
        self.server_restart_btn.setEnabled(False)
        server_controls.addWidget(self.server_status_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        server_controls.addWidget(self.server_toggle_btn)
        server_controls.addWidget(self.server_restart_btn)
        left_layout.addLayout(server_controls)

        # Connect core communication bridges
        network_bridge.trigger_signal.connect(self.execute)
        network_bridge.log_signal.connect(self.append_native_console_log)
        network_bridge.connection_status_signal.connect(self.toggle_state)

        self.server = None
        self.network_thread = None
        self.start_server()

    def start_server(self):
        if self.network_thread and self.network_thread.is_alive():
            return True
        if self.server:
            self.server.server_close()
            self.server = None

        try:
            server = make_server("0.0.0.0", 5000, flask_backend, threaded=True)
        except (OSError, SystemExit) as error:
            # werkzeug calls sys.exit(1) when the port is already in use.
            message = "port 5000 is already in use" if isinstance(error, SystemExit) else str(error)
            self.append_native_console_log("ERROR", f"Unable to start server: {message}")
            self.server_status_label.setText(self.tr("Server: stopped"))
            self.server_toggle_btn.setText(self.tr("Start Server"))
            self.server_restart_btn.setEnabled(False)
            return False

        self.server = server

        def serve():
            try:
                server.serve_forever()
            except Exception as error:
                network_bridge.log_signal.emit("ERROR", f"Server stopped unexpectedly: {error}")

        self.network_thread = Thread(target=serve, name="MioConnectServer", daemon=True)
        self.network_thread.start()
        self.server_status_label.setText(self.tr("Server: Running"))
        self.server_toggle_btn.setText(self.tr("Stop Server"))
        self.server_restart_btn.setEnabled(True)
        self.append_native_console_log("SUCCESS", "Connect server started on port 5000.")
        return True

    def stop_server(self):
        server = self.server
        thread = self.network_thread
        if server is None or thread is None or not thread.is_alive():
            if server:
                server.server_close()
            self.server = None
            self.network_thread = None
            self.server_status_label.setText(self.tr("Server: stopped"))
            self.server_toggle_btn.setText(self.tr("Start Server"))
            self.server_restart_btn.setEnabled(False)
            return True

        self.manually_terminate_session()
        server.shutdown()
        thread.join(timeout=3)
        if thread.is_alive():
            self.append_native_console_log("ERROR", "Connect server did not stop within 3 seconds.")
            return False

        server.server_close()
        self.server = None
        self.network_thread = None
        self.server_status_label.setText(self.tr("Server: stopped"))
        self.server_toggle_btn.setText(self.tr("Start Server"))
        self.server_restart_btn.setEnabled(False)
        self.append_native_console_log("INFO", "Connect server stopped.")
        return True

    def toggle_server(self):
        if self.server and self.network_thread and self.network_thread.is_alive():
            self.stop_server()
        else:
            self.start_server()

    def restart_server(self):
        if self.stop_server():
            self.start_server()

    def closeEvent(self, event):
        self.stop_server()
        super().closeEvent(event)

    def render_qr_matrix(self, encoding_data_payload):
        qr_generator = qrcode.QRCode(version=1, box_size=10, border=0)
        qr_generator.add_data(encoding_data_payload)
        qr_generator.make(fit=True)

        pil_image_layer = qr_generator.make_image(fill_color="#000000", back_color="#FFFFFF")
        image_io_stream = BytesIO()
        pil_image_layer.save(image_io_stream, format="PNG")
        qt_image_raw = QImage.fromData(image_io_stream.getvalue())
        self.qr_display_container.setPixmap(QPixmap.fromImage(qt_image_raw))

    def refresh_qr_matrix(self):
        payload = {
            "url": f"http://{self.lan_ip}:5000",
            "ws": f"ws://{self.lan_ip}:5000",
            "verify_code": ACTIVE_SESSION["verify_code"],
        }
        self.render_qr_matrix(json.dumps(payload, ensure_ascii=True))

    def toggle_state(self, is_connected, device_info_dict=None):
        if not is_connected:
            self.refresh_qr_matrix()
        self.toggle_workspace_ui_state(is_connected, device_info_dict)

    def toggle_workspace_ui_state(self, is_connected, device_info_dict=None):
        """ Replaces the QR layout view space with Fluent Icon metrics natively """
        if is_connected and device_info_dict:
            self.instructions.hide()
            self.qr_wrapper.hide()
            self.address_label.hide()

            self.status_device.setText(f"Model: {device_info_dict['device']}")
            self.status_ip.setText(f"Remote IP: {device_info_dict['ip']}")

            self.phone_icon_widget.show()
            self.disconnect_btn.show()
        else:
            self.phone_icon_widget.hide()
            self.disconnect_btn.hide()
            self.status_device.setText("")
            self.status_ip.setText("")
            self.instructions.show()
            self.qr_wrapper.show()
            self.address_label.show()

    def manually_terminate_session(self):
        ACTIVE_SESSION["verify_code"] = v_code(4)
        disconnect(close_websocket=True)
        self.append_native_console_log("WARN", "Current device session closed manually by host system. Token revoked.")

    def append_native_console_log(self, log_level, message_text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        cursor = self.console_log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        timestamp_format = QTextCharFormat()
        timestamp_format.setForeground(QColor("#71717A"))

        tag_format = QTextCharFormat()
        tag_format.setFontWeight(QFont.Weight.Bold)

        message_format = QTextCharFormat()
        LOG_LEVELS = {
            "SUCCESS": QColor("#16A34A"),
            "INFO": QColor("#2563EB"),
            "WARN": QColor("#D97706"),
            "ERROR": QColor("#DC2626"),
            "DEFAULT": QColor("#475569")
        }
        tag_format.setForeground(LOG_LEVELS.get(log_level, "DEFAULT"))

        cursor.setCharFormat(timestamp_format)
        cursor.insertText(f"[{timestamp}] ")

        cursor.setCharFormat(tag_format)
        cursor.insertText(f"[{log_level}] ")

        cursor.setCharFormat(message_format)
        cursor.insertText(f"{message_text}\n")

        self.console_log_view.setTextCursor(cursor)
        self.console_log_view.moveCursor(QTextCursor.MoveOperation.End)

    def execute(self, action_data: str | bytes | dict):
        if isinstance(action_data, bytes):
            action_data = action_data.decode('utf-8')
        # action_types:native_cmd log create_project remove_project refresh_project unpack
        # payload: {argv1, argv2}
        if action_data == '1':
            network_bridge.send_ws_message.emit('1')
            return "1"
        try:
            json_data = json.loads(action_data) if isinstance(action_data, str) else action_data
        except json.JSONDecodeError as error:
            network_bridge.log_signal.emit("WARN", f"Invalid action payload: {error}")
            return "Invalid action payload."
        if not isinstance(json_data, dict):
            network_bridge.log_signal.emit("WARN", "Invalid action payload: expected an object.")
            return "Invalid action payload."

        if json_data.get("argv1") == "list_project":
            response = json.dumps({"argv1": "list_project", "argv2": list_project()})
            network_bridge.send_ws_message.emit(response)
            return response
        return "Action"
