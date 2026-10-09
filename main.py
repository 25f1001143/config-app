import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow browser-based checks from any origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# This example uses the development YAML file.
YAML_FILE = Path(__file__).with_name("config.development.yaml")


def apply_layer(config, values, prefix=""):
    """Copy recognized settings from one layer into config."""
    for raw_key, value in values.items():
        if value is None:
            continue

        key = str(raw_key).lower()

        if prefix:
            if not key.startswith(prefix.lower()):
                continue
            key = key[len(prefix):]

        key = key.lower()

        # Handle the special .env alias.
        if key == "num_workers":
            key = "workers"

        if key in config:
            config[key] = value


def coerce(config):
    """Convert values to the types required by the assignment."""
    config["port"] = int(config["port"])
    config["workers"] = int(config["workers"])

    if isinstance(config["debug"], bool):
        pass
    else:
        config["debug"] = str(config["debug"]).strip().lower() in {
            "true", "1", "yes", "on"
        }

    config["log_level"] = str(config["log_level"])
    config["api_key"] = str(config["api_key"])
    return config


@app.get("/effective-config")
def effective_config(set: list[str] | None = Query(default=None)):
    config = DEFAULTS.copy()

    # Layer 2: YAML file
    if YAML_FILE.exists():
        with YAML_FILE.open("r", encoding="utf-8") as file:
            yaml_values = yaml.safe_load(file) or {}
        apply_layer(config, yaml_values)

    # Layer 3: .env file
    env_file = Path(__file__).with_name(".env")
    apply_layer(config, dotenv_values(env_file), prefix="APP_")

    # NUM_WORKERS is a special alias in the .env layer.
    dotenv_data = dotenv_values(env_file)
    if dotenv_data.get("NUM_WORKERS") is not None:
        config["workers"] = dotenv_data["NUM_WORKERS"]

    # Layer 4: operating-system environment variables.
    apply_layer(config, os.environ, prefix="APP_")

    # Layer 5: repeated query parameters such as set=port=9000.
    for item in set or []:
        key, separator, value = item.partition("=")
        if not separator:
            continue

        key = key.strip().lower()
        if key in config:
            config[key] = value

    config = coerce(config)

    # Never return the real secret.
    config["api_key"] = "****"
    return config