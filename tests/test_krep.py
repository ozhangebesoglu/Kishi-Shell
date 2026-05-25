import os
import sys
import pytest
from unittest.mock import patch
from kishi.krep import (
    get_semantic_vector,
    vectorize_text,
    cosine_similarity,
    render_3d_scatter,
    krep_search
)

def test_get_semantic_vector():
    # Test error category (X axis)
    assert get_semantic_vector("error") == [1.0, 0.0, 0.0]
    assert get_semantic_vector("failed") == [1.0, 0.0, 0.0]
    assert get_semantic_vector("crash") == [1.0, 0.0, 0.0]

    # Test security/auth category (Y axis)
    assert get_semantic_vector("login") == [0.0, 1.0, 0.0]
    assert get_semantic_vector("password") == [0.0, 1.0, 0.0]
    assert get_semantic_vector("auth") == [0.0, 1.0, 0.0]

    # Test data/db category (Z axis)
    assert get_semantic_vector("database") == [0.0, 0.0, 1.0]
    assert get_semantic_vector("sql") == [0.0, 0.0, 1.0]
    assert get_semantic_vector("query") == [0.0, 0.0, 1.0]

    # Test empty or unrelated words
    assert get_semantic_vector("") == [0.0, 0.0, 0.0]
    assert get_semantic_vector("banana") == [0.0, 0.0, 0.0]

def test_vectorize_text():
    # Single term vectorization
    vec_err = vectorize_text("error occurred")
    assert vec_err[0] > 0.0
    assert vec_err[1] == 0.0
    assert vec_err[2] == 0.0

    # Normalization check (unit vector)
    length = (vec_err[0]**2 + vec_err[1]**2 + vec_err[2]**2)**0.5
    assert pytest.approx(length) == 1.0

    # Combined term vectorization
    vec_mixed = vectorize_text("login query")
    assert vec_mixed[0] == 0.0
    assert vec_mixed[1] > 0.0
    assert vec_mixed[2] > 0.0

    # Unrelated text
    assert vectorize_text("just some unrelated words here") == [0.0, 0.0, 0.0]

def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2)) == 1.0

    v3 = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v3)) == 0.0

    assert cosine_similarity([0.0, 0.0, 0.0], v1) == 0.0

def test_render_3d_scatter():
    q_vec = [1.0, 0.0, 0.0]
    matches = [([1.0, 0.0, 0.0], 1.0, "error detail")]
    chart = render_3d_scatter(q_vec, matches)
    assert "KREP AI" in chart
    assert "X (Hata)" in chart
    assert "Y (Guvenlik)" in chart
    assert "Z (Veri)" in chart

def test_krep_search_files(tmp_path, capsys):
    test_file = tmp_path / "syslog.txt"
    test_file.write_text(
        "system started successfully\n"
        "auth token expired for user admin\n"
        "database connection error occurred in backend\n"
    )

    # Search for login/security concept
    res = krep_search("login authorization", [str(test_file)])
    assert res == 0
    captured = capsys.readouterr()
    assert "auth token expired" in captured.out
    assert "KREP AI" in captured.out

def test_krep_search_recursive(tmp_path, capsys):
    subdir = tmp_path / "logs"
    subdir.mkdir()
    test_file = subdir / "error.log"
    test_file.write_text("system crashed due to segmentation fault\n")

    res = krep_search("system crash bug", [str(tmp_path)], recursive=True)
    assert res == 0
    captured = capsys.readouterr()
    assert "system crashed" in captured.out

def test_krep_search_stdin(capsys):
    stdin_content = "auth token expired for user admin\ndatabase save failed\n"
    with patch("sys.stdin.readline", side_effect=stdin_content.splitlines() + [""]):
        res = krep_search("login user", [])
        assert res == 0
        captured = capsys.readouterr()
        assert "auth token expired" in captured.out
