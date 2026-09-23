#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pylibrelinkup import APIUrl, PyLibreLinkUp, RedirectError
from requests.exceptions import HTTPError


ROOT = Path(__file__).resolve().parents[2]

# Abbott blocks the login endpoint with HTTP 476 when clients authenticate too
# often. Back off login attempts after a 476: 30 min, doubling up to 6 h.
LOGIN_BACKOFF_BASE_SECONDS = 30 * 60
LOGIN_BACKOFF_MAX_SECONDS = 6 * 60 * 60


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def api_url_from_name(name: str) -> APIUrl:
    try:
        return APIUrl.from_string(name)
    except ValueError as exc:
        valid = ", ".join(member.name for member in APIUrl)
        raise SystemExit(f"Invalid API region {name!r}. Valid regions: {valid}") from exc


def authenticate(email: str, password: str, api_url: APIUrl) -> PyLibreLinkUp:
    client = PyLibreLinkUp(email=email, password=password, api_url=api_url)
    try:
        client.authenticate()
        return client
    except RedirectError as exc:
        client = PyLibreLinkUp(email=email, password=password, api_url=exc.region)
        client.authenticate()
        return client


def read_state(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return state if isinstance(state, dict) else {}


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))
    path.chmod(0o600)


def build_client(
    email: str, password: str, api_url: APIUrl, state_path: Path | None
) -> PyLibreLinkUp:
    """Return an authenticated client, reusing a cached session token when possible.

    Fresh logins are rate-limited by Abbott (HTTP 476), so only hit the login
    endpoint when there is no cached token or the cached token is rejected.
    """
    state = read_state(state_path)

    if state.get("token") and state.get("account_id_hash"):
        client = PyLibreLinkUp(email=email, password=password, api_url=api_url)
        client.api_url = state.get("api_url", client.api_url)
        client.token = state["token"]
        client.account_id_hash = state["account_id_hash"]
        try:
            client.get_patients()
            return client
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in (401, 403):
                raise
            # Token expired or revoked; fall through to a fresh login.

    blocked_until = state.get("login_blocked_until", 0)
    if time.time() < blocked_until:
        until = datetime.fromtimestamp(blocked_until, timezone.utc).isoformat()
        print(f"Skipping login: backing off after HTTP 476 until {until}", file=sys.stderr)
        raise SystemExit(0)

    try:
        client = authenticate(email, password, api_url)
    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 476 and state_path:
            failures = state.get("login_failures", 0) + 1
            delay = min(
                LOGIN_BACKOFF_BASE_SECONDS * 2 ** (failures - 1),
                LOGIN_BACKOFF_MAX_SECONDS,
            )
            state.pop("token", None)
            state.pop("account_id_hash", None)
            state["login_failures"] = failures
            state["login_blocked_until"] = time.time() + delay
            write_state(state_path, state)
            raise SystemExit(
                f"LibreLinkUp login rate-limited (HTTP 476); "
                f"backing off {delay // 60} min (failure #{failures})."
            ) from exc
        raise

    if state_path:
        write_state(
            state_path,
            {
                "account_id_hash": client.account_id_hash,
                "api_url": client.api_url,
                "token": client.token,
            },
        )
    return client


def model_to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [model_to_jsonable(item) for item in value]
    return value


def normalize_alarm_thresholds(response: Any) -> Any:
    """Adapt fractional Abbott alarm thresholds for pylibrelinkup 0.10.0.

    Abbott may return mmol/L-derived mg/dL thresholds such as 59.4, while the
    dependency models these configuration-only fields as integers. Glucose
    measurements are outside this path and are not modified.
    """
    if not isinstance(response, dict):
        return response
    try:
        rules = response["data"]["connection"]["alarmRules"]
    except (KeyError, TypeError):
        return response
    if not isinstance(rules, dict):
        return response
    for alarm_name in ("f", "l", "h"):
        alarm = rules.get(alarm_name)
        if not isinstance(alarm, dict):
            continue
        threshold = alarm.get("th")
        if isinstance(threshold, float) and not threshold.is_integer():
            alarm["th"] = round(threshold)
    return response


def install_graph_response_compatibility(client: PyLibreLinkUp) -> None:
    """Normalize graph payloads before pylibrelinkup validates them."""
    original = client._get_graph_data_json

    def compatible_graph_data(patient_id: Any) -> Any:
        return normalize_alarm_thresholds(original(patient_id))

    client._get_graph_data_json = compatible_graph_data


def pick_patient(client: PyLibreLinkUp, patient: str | None, index: int | None) -> Any:
    patients = client.get_patients()
    if not patients:
        raise SystemExit("No LibreLinkUp patients/connections found.")
    if patient:
        for item in patients:
            if patient in {str(item.id), str(item.patient_id)}:
                return item
        raise SystemExit(f"Patient id not found: {patient}")
    if index is None:
        if len(patients) != 1:
            raise SystemExit("Multiple connections: select --patient or --patient-index explicitly.")
        index = 0
    try:
        return patients[index]
    except IndexError as exc:
        raise SystemExit(f"Patient index {index} out of range; found {len(patients)}") from exc


def print_text(command: str, data: Any) -> None:
    if command == "patients":
        for index, patient in enumerate(data):
            print(f"{index}: {patient.first_name} {patient.last_name} patient_id={patient.patient_id}")
        return

    if command == "latest":
        trend = getattr(data, "trend", None)
        trend_text = trend.name if trend is not None else "unknown"
        print(f"timestamp: {data.timestamp}")
        print(f"value: {data.value}")
        print(f"value_in_mg_per_dl: {data.value_in_mg_per_dl}")
        print(f"trend: {trend_text}")
        print(f"is_low: {data.is_low}")
        print(f"is_high: {data.is_high}")
        return

    for measurement in data:
        print(
            f"{measurement.timestamp}\tvalue={measurement.value}\t"
            f"mg_dl={measurement.value_in_mg_per_dl}\t"
            f"is_low={measurement.is_low}\tis_high={measurement.is_high}"
        )


def write_output(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model_to_jsonable(data), indent=2, sort_keys=True))
    path.chmod(0o640)


def pull_raw_once(client: PyLibreLinkUp, patient: Any, raw_dir: Path) -> list[Path]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    written: list[Path] = []

    outputs: list[tuple[str, Any]] = [
        ("graph", client.graph(patient)),
        ("latest", client.latest(patient)),
    ]

    if not any(raw_dir.glob(f"logbook-{day}*.json")):
        outputs.append(("logbook", client.logbook(patient)))

    for name, data in outputs:
        path = raw_dir / f"{name}-{ts}.json"
        write_output(path, data)
        written.append(path)

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch LibreLinkUp glucose data.")
    parser.add_argument(
        "command",
        choices=["patients", "latest", "graph", "logbook", "pull"],
        help="Data to fetch.",
    )
    parser.add_argument("--env-file", default=str(Path.home() / ".config/health-notebook/librelinkup.env"))
    parser.add_argument("--api-url", default=None, help="API region, e.g. EU, EU2, US.")
    parser.add_argument("--patient", default=None, help="Patient id/UUID. Defaults to patient index.")
    parser.add_argument("--patient-index", type=int, default=None)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--raw-dir", type=Path, default=None, help="Directory for the pull command.")
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path.home() / ".local/state/health-notebook/librelinkup-session.json",
        help="JSON file for caching the session token between runs "
        "(default: ~/.local/state/health-notebook/librelinkup-session.json).",
    )
    parser.add_argument("--quiet", action="store_true", help="Do not print fetched data.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file(Path(args.env_file))

    email = os.environ.get("LIBRELINKUP_EMAIL", "")
    password = os.environ.get("LIBRELINKUP_PASSWORD", "")
    api_url_name = args.api_url or os.environ.get("LIBRELINKUP_API_URL", "EU")

    if not email or not password:
        raise SystemExit(
            "Missing LIBRELINKUP_EMAIL or LIBRELINKUP_PASSWORD. "
            "Set them in the environment or an ignored .env file."
        )

    state_file = args.state_file
    state_path = Path(state_file) if state_file else None

    client = build_client(email, password, api_url_from_name(api_url_name), state_path)
    install_graph_response_compatibility(client)

    if args.command == "patients":
        data = client.get_patients()
    elif args.command == "pull":
        if not args.raw_dir:
            raise SystemExit("pull requires --raw-dir")
        patient = pick_patient(client, args.patient, args.patient_index)
        written = pull_raw_once(client, patient, args.raw_dir)
        if not args.quiet:
            for path in written:
                print(path)
        return 0
    else:
        patient = pick_patient(client, args.patient, args.patient_index)
        if args.command == "latest":
            data = client.latest(patient)
        elif args.command == "graph":
            data = client.graph(patient)
        elif args.command == "logbook":
            data = client.logbook(patient)
        else:
            raise AssertionError(args.command)

    if args.output:
        write_output(args.output, data)
    if args.quiet:
        return 0
    if args.format == "json":
        print(json.dumps(model_to_jsonable(data), indent=2, sort_keys=True))
    else:
        print_text(args.command, data)

    return 0


if __name__ == "__main__":
    sys.exit(main())
