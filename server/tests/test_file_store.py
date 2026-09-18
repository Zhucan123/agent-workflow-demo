import pytest


@pytest.mark.asyncio
async def test_file_store_write_and_read(tmp_path):
    from app.tools.file_store import FileStoreTool

    tool = FileStoreTool(tmp_path)
    result = await tool.run(
        {"action": "write", "filename": "a.txt", "content": "hello"}, None
    )
    assert result["ok"] is True
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hello"

    result = await tool.run({"action": "read", "filename": "a.txt"}, None)
    assert result["ok"] is True and result["output"]["content"] == "hello"


@pytest.mark.asyncio
async def test_file_store_blocks_traversal(tmp_path):
    from app.tools.file_store import FileStoreTool

    tool = FileStoreTool(tmp_path)
    result = await tool.run(
        {"action": "read", "filename": "../outside.txt"}, None
    )
    assert result["ok"] is False
    assert not (tmp_path.parent / "outside.txt").exists()