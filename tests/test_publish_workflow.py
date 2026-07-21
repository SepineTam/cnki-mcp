from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/publish.yml")


def test_publish_workflow_uses_pypi_trusted_publishing() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "release:" in workflow
    assert "types: [published]" in workflow
    assert "environment: pypi" in workflow
    assert "id-token: write" in workflow
    assert "uv run playwright install --with-deps chromium" in workflow
    assert "uv build" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "secrets." not in workflow
    assert "password:" not in workflow
