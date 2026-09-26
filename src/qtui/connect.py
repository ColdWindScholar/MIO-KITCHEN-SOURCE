import json
import os
import socket
import uuid
from datetime import datetime
from io import BytesIO
from platform import system, machine
from threading import Thread

import qrcode
from PySide6.QtCore import Signal, QObject, Qt, QSize
from PySide6.QtGui import QPixmap, QImage, QFont, QTextCursor, QTextCharFormat, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from flask import Flask, request, jsonify
from qfluentwidgets import (
    CardWidget,
    BodyLabel,
    TitleLabel,
    PrimaryPushButton,
    IconWidget,
    FluentIcon, TextEdit
)

from src.core.utils import v_code


class NetworkBridge(QObject):
    trigger_signal = Signal(dict)
    log_signal = Signal(str, str)
    connection_status_signal = Signal(bool, dict)

flask_backend = Flask(__name__)
network_bridge = NetworkBridge()


ACTIVE_SESSION = {
    "token": None,
    "device_name": None,
    "device_ip": None,
    "verify_code": v_code(4),
}


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
    if not not auth_header != 'MioKey' + ACTIVE_SESSION["token"]:
        return f"Unauthorized: Invalid header", 403
    device_ip = request.remote_addr

    ACTIVE_SESSION["token"] = None
    ACTIVE_SESSION["device_name"] = None
    ACTIVE_SESSION["device_ip"] = None
    network_bridge.connection_status_signal.emit(False, {})
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
    json_text = json.dumps({"device_name": os.environ['HOSTNAME'], "system": system(), "machine":machine()},
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


def fetch_linux_lan_ip():
    try:
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_socket.connect(("8.8.8.8", 80))
        local_ip = temp_socket.getsockname()[0]
        temp_socket.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


class ConnectPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConnectPage")

        base_horizontal_layout = QHBoxLayout(self)
        base_horizontal_layout.setContentsMargins(24, 24, 24, 24)
        base_horizontal_layout.setSpacing(24)

        # ==================== LEFT SIDE: FLUENT CARD HUB ====================
        self.left_card = CardWidget(self)
        left_layout = QVBoxLayout(self.left_card)
        left_layout.setContentsMargins(24, 24, 24, 24)
        left_layout.setSpacing(16)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Header Typography Node
        self.title_label = TitleLabel("Connect ImageStudio", self)
        left_layout.addWidget(self.title_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Container elements for dynamic visibility toggle
        self.instructions = BodyLabel(
            "Scan via ImageStudio to manage your projects and images on your Android phone.", self)
        self.instructions.setWordWrap(True)
        self.instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.instructions)

        # Vector Icon Layer (Fluent Design standard)
        self.phone_icon_widget = IconWidget(FluentIcon.CONNECT, self)
        self.phone_icon_widget.setFixedSize(72, 72)
        self.phone_icon_widget.hide()  # Hidden initially while waiting for connection
        left_layout.addWidget(self.phone_icon_widget, alignment=Qt.AlignmentFlag.AlignHCenter)

        # QR Matrix Frame Wrapper
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

        # Device connection status text widgets
        self.status_device = BodyLabel("", self)
        self.status_ip = BodyLabel("", self)
        left_layout.addWidget(self.status_device, alignment=Qt.AlignmentFlag.AlignHCenter)
        left_layout.addWidget(self.status_ip, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Action: Break connection
        self.disconnect_btn = PrimaryPushButton(self.tr("Disconnect"), self)
        self.disconnect_btn.clicked.connect(self.manually_terminate_session)
        self.disconnect_btn.hide()
        left_layout.addWidget(self.disconnect_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        base_horizontal_layout.addWidget(self.left_card, stretch=2)

        # ==================== RIGHT SIDE: LIVE CONSOLE LOGS ====================
        right_panel_container = QVBoxLayout()
        right_panel_container.setSpacing(8)


        self.console_log_view = TextEdit(self)
        self.console_log_view.setFont(QFont("Consolas", 10))
        self.console_log_view.setReadOnly(True)
        right_panel_container.addWidget(self.console_log_view)

        base_horizontal_layout.addLayout(right_panel_container, stretch=3)

        # ==================== INITIALIZATION ====================
        self.lan_ip = fetch_linux_lan_ip()
        json_text = json.dumps({"url":f"http://{self.lan_ip}:5000", "verify_code":ACTIVE_SESSION["verify_code"]}, ensure_ascii=True)
        self.address_label.setText(f"http://{self.lan_ip}:5000")
        self.address_label.setStyleSheet("color: green; font-style: bold;")
        self.render_qr_matrix(json_text)

        # Connect core communication bridges
        network_bridge.trigger_signal.connect(self.execute_desktop_function)
        network_bridge.log_signal.connect(self.append_native_console_log)
        network_bridge.connection_status_signal.connect(self.toggle_state)

        self.network_thread = Thread(target=lambda :flask_backend.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True)
        self.network_thread.start()

    def render_qr_matrix(self, encoding_data_payload):
        qr_generator = qrcode.QRCode(version=1, box_size=10, border=0)
        qr_generator.add_data(encoding_data_payload)
        qr_generator.make(fit=True)

        pil_image_layer = qr_generator.make_image(fill_color="#000000", back_color="#FFFFFF")
        image_io_stream = BytesIO()
        pil_image_layer.save(image_io_stream, format="PNG")
        qt_image_raw = QImage.fromData(image_io_stream.getvalue())
        self.qr_display_container.setPixmap(QPixmap.fromImage(qt_image_raw))
    def toggle_state(self, is_connected, device_info_dict=None):
        if not is_connected:
            self.render_qr_matrix(
                json.dumps({"url": f"http://{self.lan_ip}:5000", "verify_code": ACTIVE_SESSION["verify_code"]},
                           ensure_ascii=True))
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
        global ACTIVE_SESSION
        ACTIVE_SESSION = {
            "token": None,
            "device_name": None,
            "device_ip": None,
            "verify_code": v_code(4),
        }
        self.toggle_workspace_ui_state(False)
        network_bridge.connection_status_signal.emit(False, {})
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
            "SUCCESS":QColor("#16A34A"),
            "INFO":QColor("#2563EB"),
            "WARN":QColor("#D97706"),
            "ERROR":QColor("#DC2626"),
            "DEFAULT":QColor("#475569")
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

    def execute_desktop_function(self, action_id:dict):
        print(action_id)
