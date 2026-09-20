import pytest

# pi-lens-ignore: reportMissingImports
from oma_info_system.json_utils import parse_json_response


def test_parse_json_response_tolerates_markdown_fence_and_prefix():
    result = parse_json_response('Here is the result:\n```json\n{"ok": true}\n```')
    assert result == {"ok": True}


def test_parse_json_response_rejects_empty_content():
    with pytest.raises(ValueError, match="empty content"):
        parse_json_response("\n")
