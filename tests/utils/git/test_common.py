import pytest
from trxo.utils.git.common import extract_branch_name_from_ref


def test_extract_branch_name_refs_remotes_origin_simple():
    ref = "refs/remotes/origin/main"
    assert extract_branch_name_from_ref(ref) == "main"


def test_extract_branch_name_refs_remotes_origin_nested():
    ref = "refs/remotes/origin/scripts/export"
    assert extract_branch_name_from_ref(ref) == "scripts/export"


def test_extract_branch_name_origin_prefix():
    ref = "origin/dev"
    assert extract_branch_name_from_ref(ref) == "dev"


def test_extract_branch_name_origin_prefix_nested():
    ref = "origin/feature/export"
    assert extract_branch_name_from_ref(ref) == "feature/export"


def test_extract_branch_name_already_clean():
    ref = "main"
    assert extract_branch_name_from_ref(ref) == "main"


def test_extract_branch_name_already_nested_clean():
    ref = "feature/export"
    assert extract_branch_name_from_ref(ref) == "feature/export"


def test_extract_branch_name_weird_ref_without_origin():
    ref = "refs/heads/main"
    assert extract_branch_name_from_ref(ref) == "refs/heads/main"


def test_extract_branch_name_empty_string():
    ref = ""
    assert extract_branch_name_from_ref(ref) == ""


def test_extract_branch_name_only_origin():
    ref = "origin/"
    assert extract_branch_name_from_ref(ref) == ""


def test_extract_branch_name_with_multiple_origin_tokens():
    ref = "refs/remotes/origin/origin/feature"
    assert extract_branch_name_from_ref(ref) == "origin/feature"
