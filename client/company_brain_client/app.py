import os

import httpx
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

DEFAULT_API_URL = "http://127.0.0.1:8000"


class HealthCheckSignals(QObject):
    completed = Signal(str)


class HealthCheck(QRunnable):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = HealthCheckSignals()

    def run(self) -> None:
        try:
            response = httpx.get(self.url, timeout=5.0)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as error:
            status = f"Backend reported HTTP {error.response.status_code}."
        except (httpx.RequestError, httpx.InvalidURL):
            status = "Could not reach the backend. Check the server address and try again."
        except ValueError:
            status = "The backend returned an invalid health response."
        else:
            if (
                isinstance(payload, dict)
                and payload.get("status") == payload.get("database") == "ok"
            ):
                status = "Backend and database are reachable."
            else:
                status = "The backend did not report a healthy database."

        self.signals.completed.emit(status)


class HealthWindow(QWidget):
    def __init__(self, api_url: str) -> None:
        super().__init__()
        self.health_url = f"{api_url.rstrip('/')}/api/health"
        self.setWindowTitle("Company Brain")
        self.setMinimumWidth(400)

        endpoint = QLabel(self.health_url)
        endpoint.setTextFormat(Qt.TextFormat.PlainText)
        endpoint.setWordWrap(True)
        self.status = QLabel("Ready to check the backend.")
        self.status.setWordWrap(True)
        self.check_button = QPushButton("Check server connection")
        self.check_button.clicked.connect(self.check_backend)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Server connection"))
        layout.addWidget(endpoint)
        layout.addWidget(self.check_button)
        layout.addWidget(self.status)

    @Slot()
    def check_backend(self) -> None:
        self.check_button.setEnabled(False)
        self.status.setText("Checking server connection…")
        check = HealthCheck(self.health_url)
        check.signals.completed.connect(self.show_result)
        QThreadPool.globalInstance().start(check)

    @Slot(str)
    def show_result(self, message: str) -> None:
        self.status.setText(message)
        self.check_button.setEnabled(True)


def main() -> int:
    app = QApplication([])
    window = HealthWindow(os.getenv("COMPANY_BRAIN_API_URL", DEFAULT_API_URL))
    window.show()
    return app.exec()
