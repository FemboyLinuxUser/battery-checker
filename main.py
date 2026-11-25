import logging
import sys

from PyQt5.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app import AppController
from config import load_config, setup_logging, validate_config


def main():
    log_path = setup_logging()
    logging.getLogger(__name__).info("Лог: %s", log_path)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Ошибка", "Системный трей недоступен.")
        return 1

    cfg = load_config()
    errors = validate_config(cfg)
    if errors:
        QMessageBox.warning(
            None,
            "Проверьте конфиг",
            "Конфиг содержит ошибки:\n" + "\n".join(f"• {e}" for e in errors),
        )

    controller = AppController(app, cfg)
    return controller.run()


if __name__ == "__main__":
    sys.exit(main())
