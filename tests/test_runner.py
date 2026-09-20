from runner import detect_port_from_logs


def test_detect_port_localhost():
    assert detect_port_from_logs(["Server running at localhost:8501"]) == "8501"


def test_detect_port_0000():
    assert detect_port_from_logs(["Listening on 0.0.0.0:3000"]) == "3000"


def test_detect_port_none_found():
    assert detect_port_from_logs(["Starting up...", "Ready."]) is None


def test_detect_port_first_match_wins():
    lines = ["Ignore http://example.com", "Local: http://127.0.0.1:5000/"]
    assert detect_port_from_logs(lines) == "5000"
