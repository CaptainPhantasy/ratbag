"""Start the workbench: python3 -m swarm."""
import argparse
import json
import os
from pathlib import Path
import sys

from .interview import QUESTIONS, Answers, Interview
from .sdlc import SdlcClient, SdlcError
from .server import Application, create_server


def _ask(answers: dict[str, str]) -> Answers:
    print("The interview. Plain answers, no jargon.\n", flush=True)
    for key, question in QUESTIONS:
        current = answers.get(key, "")
        suffix = f" [{current}]" if current else ""
        try:
            reply = input(f"{question}{suffix}\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit("Stopped before anything was built.")
        answers[key] = reply or current
    return Answers.from_mapping(answers)


def _interview(args) -> int:
    if args.sdlc_status:
        status = SdlcClient().status()
        print(json.dumps(status, indent=2))
        return 0 if status.get("reachable") else 2

    if args.answers:
        answers = Answers.from_mapping(json.loads(Path(args.answers).read_text(encoding="utf-8")))
    else:
        answers = _ask({})

    def note(step):
        mark = {"ok": "ok  ", "failed": "FAIL", "skipped": "skip"}.get(step.status, step.status)
        print(f"[{mark}] {step.name}: {step.detail}", flush=True)

    interview = Interview(answers, note=note)
    try:
        result = interview.run()
    except SdlcError as exc:
        print(f"\nStopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Swarm Control workbench")
    parser.add_argument("--host", default=os.getenv("SWARM_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("SWARM_PORT", "8765")))
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("SWARM_DATA_DIR", ".swarm-data")))
    parser.add_argument("--base-path", default=os.getenv("SWARM_BASE_PATH", ""), help="URL prefix when served through the server, for example /swarm.")
    parser.add_argument("--session-keys-stdin", action="store_true", help="Read role keys from one JSON line on hidden standard input.")
    parser.add_argument("--interview", action="store_true", help="Interview the user, then drive the SDLC factory from the answers.")
    parser.add_argument("--answers", type=Path, help="Read interview answers from a JSON file instead of asking.")
    parser.add_argument("--sdlc-status", action="store_true", help="Report whether the SDLC factory can be reached, then exit.")
    args = parser.parse_args()
    if args.interview or args.answers or args.sdlc_status:
        raise SystemExit(_interview(args))
    project = Path(__file__).resolve().parent.parent
    hosts = {"localhost", "127.0.0.1", "::1"} | {h.strip() for h in os.getenv("SWARM_ALLOWED_HOSTS", "").split(",") if h.strip()}
    app = Application(args.data_dir, project / "web", os.getenv("SWARM_ACCESS_TOKEN", ""), hosts,
                      base_path=args.base_path)
    if args.session_keys_stdin:
        old_settings = None
        if sys.stdin.isatty():
            import termios
            old_settings = termios.tcgetattr(sys.stdin)
            quiet = list(old_settings)
            quiet[3] &= ~termios.ECHO
            termios.tcsetattr(sys.stdin, termios.TCSANOW, quiet)
        print("Ready for role keys on hidden input.", flush=True)
        try:
            entries = json.loads(sys.stdin.readline())
            if not isinstance(entries, dict):
                raise ValueError("Expected role keys as an object.")
            for role, key in entries.items():
                app.registry.set_key(role, key)
                if role == "router":
                    app.registry.configure(role, {"enabled": True})
            entries.clear()
        finally:
            if old_settings is not None:
                termios.tcsetattr(sys.stdin, termios.TCSANOW, old_settings)
    server = create_server(app, args.host, args.port)
    print(f"Swarm Control is listening on {args.host}:{server.server_port}.", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("Stopping the current operation and preserving its evidence.", flush=True)
    finally:
        server.server_close()
        app.shutdown()


if __name__ == "__main__":
    main()
