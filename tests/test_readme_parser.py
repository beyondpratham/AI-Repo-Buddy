from readme_parser import extract_commands


def test_extract_install_and_run_from_fenced_block():
    readme = """
    # My Project

    ```bash
    pip install -r requirements.txt
    streamlit run app.py
    ```
    """
    install_cmds, run_cmds = extract_commands(readme)
    assert install_cmds == ["pip install -r requirements.txt"]
    assert run_cmds == ["streamlit run app.py"]


def test_extract_ignores_comments_and_dedupes():
    readme = """
    ```
    # this is a comment
    npm install
    npm install
    ```
    """
    install_cmds, run_cmds = extract_commands(readme)
    assert install_cmds == ["npm install"]


def test_extract_strips_shell_prompt_prefixes():
    readme = """
    ```
    $ pip install -r requirements.txt
    > npm start
    ```
    """
    install_cmds, run_cmds = extract_commands(readme)
    assert install_cmds == ["pip install -r requirements.txt"]
    assert run_cmds == ["npm start"]


def test_extract_returns_empty_lists_when_nothing_found():
    install_cmds, run_cmds = extract_commands("Just a plain description with no commands.")
    assert install_cmds == []
    assert run_cmds == []
