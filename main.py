"""Un único proceso para cámara, códigos de barras, NFC, clima y dos pantallas HTML."""

import argparse
import logging
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Simular sin cámara, lectores ni API de clima")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--config", type=Path, help="Archivo JSON de configuración")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")

    import uvicorn
    from display_app.server import create_app

    app = create_app(args.config, demo=args.demo)
    print(f"Figuras: http://localhost:{args.port}/figuras")
    print(f"NFC:     http://localhost:{args.port}/nfc")
    print(f"Control: http://localhost:{args.port}/")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
