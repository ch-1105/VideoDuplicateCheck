from .app import create_app
from .gui.main_window import MainWindow


def main() -> int:
    app = create_app()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
