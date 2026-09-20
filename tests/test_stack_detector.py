from stack_detector import detect_stack, find_readme


def test_detect_stack_python(tmp_path):
    (tmp_path / "requirements.txt").write_text("streamlit\n")
    detected = detect_stack(str(tmp_path))
    assert "python" in detected


def test_detect_stack_node(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    detected = detect_stack(str(tmp_path))
    assert "node" in detected


def test_detect_stack_multiple(tmp_path):
    (tmp_path / "go.mod").write_text("module example\n")
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    detected = detect_stack(str(tmp_path))
    assert "go" in detected
    assert "docker" in detected


def test_detect_stack_empty_dir(tmp_path):
    assert detect_stack(str(tmp_path)) == {}


def test_find_readme_case_insensitive(tmp_path):
    (tmp_path / "readme.md").write_text("# Hi\n")
    found = find_readme(str(tmp_path))
    assert found is not None
    assert found.lower().endswith("readme.md")


def test_find_readme_missing(tmp_path):
    assert find_readme(str(tmp_path)) is None
