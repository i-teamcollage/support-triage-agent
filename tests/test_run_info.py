import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from support_triage_agent.llm import linux_machine, machine_description, ollama_info

RESPONSES = {
    "/api/version": {"version": "0.12.6"},
    "/api/tags": {
        "models": [
            {"name": "gemma4:12b", "model": "gemma4:12b", "digest": "111"},
            {"name": "ministral-3:8b", "model": "ministral-3:8b", "digest": "a5c1f00d"},
        ]
    },
}


class StubOllama(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = json.dumps(RESPONSES[self.path]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_ollama_info_reports_the_version_and_the_model_digest():
    server = HTTPServer(("127.0.0.1", 0), StubOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        info = ollama_info("ministral-3:8b", f"http://127.0.0.1:{server.server_port}")
    finally:
        server.shutdown()
    assert info == {"ollama_version": "0.12.6", "model_digest": "a5c1f00d"}


def test_ollama_info_without_a_server_is_empty():
    assert ollama_info("ministral-3:8b", "http://127.0.0.1:9") == {}


def test_machine_description_is_a_short_label():
    description = machine_description()
    assert description and len(description) < 80


def test_on_linux_the_machine_is_described_by_its_processor_cores_and_memory(tmp_path):
    (tmp_path / "cpuinfo").write_text(
        "processor\t: 0\nmodel name\t: Intel(R) Xeon(R) Processor @ 2.10GHz\n\n"
        "processor\t: 1\nmodel name\t: Intel(R) Xeon(R) Processor @ 2.10GHz\n"
    )
    (tmp_path / "meminfo").write_text("MemTotal:       16374536 kB\nMemFree:        15000000 kB\n")
    assert linux_machine(tmp_path) == "Intel Xeon Processor @ 2.10GHz, 2 cores, 16 GB"


def test_without_proc_files_there_is_no_linux_description(tmp_path):
    assert linux_machine(tmp_path) is None
