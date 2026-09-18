import pytest

from app.tools.calculator import safe_eval


def test_basic_arithmetic():
    assert safe_eval("3 * 129.9") == pytest.approx(389.7)


def test_complex_expression():
    assert safe_eval("3 * 129.9 * 1.15") == pytest.approx(448.155)


def test_round_function():
    assert safe_eval("round(448.155, 2)") == pytest.approx(448.15)


def test_traversal_attack_rejected():
    with pytest.raises(Exception):
        safe_eval("__import__('os').system('id')")


def test_builtins_rejected():
    with pytest.raises(Exception):
        safe_eval("open('/etc/passwd').read()")