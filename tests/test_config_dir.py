"""Tests for platform-appropriate config directory selection."""

import os

import pytest

from soco_cli.config_dir import get_config_dir


@pytest.fixture
def home(tmp_path):
    return str(tmp_path)


def _env(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}


def test_legacy_dir_takes_precedence_on_linux(home):
    legacy = os.path.join(home, ".soco-cli")
    os.mkdir(legacy)
    env = _env(XDG_CONFIG_HOME=os.path.join(home, "xdg"))
    assert get_config_dir(system="Linux", home=home, environ=env) == legacy


def test_legacy_dir_takes_precedence_on_windows(home):
    legacy = os.path.join(home, ".soco-cli")
    os.mkdir(legacy)
    env = _env(LOCALAPPDATA=os.path.join(home, "AppData", "Local"))
    assert get_config_dir(system="Windows", home=home, environ=env) == legacy


def test_legacy_file_not_dir_is_ignored(home):
    with open(os.path.join(home, ".soco-cli"), "w") as f:
        f.write("")
    expected = os.path.join(home, ".config", "soco-cli")
    assert get_config_dir(system="Linux", home=home, environ={}) == expected


def test_linux_uses_xdg_config_home(home):
    xdg = os.path.join(home, "xdg")
    env = _env(XDG_CONFIG_HOME=xdg)
    assert get_config_dir(system="Linux", home=home, environ=env) == os.path.join(
        xdg, "soco-cli"
    )


def test_linux_falls_back_to_dot_config(home):
    expected = os.path.join(home, ".config", "soco-cli")
    assert get_config_dir(system="Linux", home=home, environ={}) == expected


@pytest.mark.parametrize("xdg", ["", "relative/path"])
def test_linux_ignores_empty_or_relative_xdg(home, xdg):
    # XDG spec: empty or relative values must be ignored
    expected = os.path.join(home, ".config", "soco-cli")
    assert (
        get_config_dir(system="Linux", home=home, environ={"XDG_CONFIG_HOME": xdg})
        == expected
    )


@pytest.mark.parametrize("system", ["FreeBSD", "OpenBSD", "NetBSD"])
def test_other_posix_uses_xdg(home, system):
    expected = os.path.join(home, ".config", "soco-cli")
    assert get_config_dir(system=system, home=home, environ={}) == expected


def test_windows_uses_localappdata(home):
    lad = os.path.join(home, "AppData", "Local")
    env = _env(LOCALAPPDATA=lad)
    assert get_config_dir(system="Windows", home=home, environ=env) == os.path.join(
        lad, "soco-cli"
    )


def test_windows_without_localappdata_uses_legacy(home):
    expected = os.path.join(home, ".soco-cli")
    assert get_config_dir(system="Windows", home=home, environ={}) == expected


def test_macos_uses_legacy(home):
    expected = os.path.join(home, ".soco-cli")
    assert get_config_dir(system="Darwin", home=home, environ={}) == expected


def test_env_override_wins(home):
    legacy = os.path.join(home, ".soco-cli")
    os.mkdir(legacy)
    custom = os.path.join(home, "custom")
    env = _env(SOCO_CLI_CONFIG_DIR=custom, XDG_CONFIG_HOME=os.path.join(home, "xdg"))
    assert get_config_dir(system="Linux", home=home, environ=env) == custom


def test_env_override_expands_user(home, monkeypatch):
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("USERPROFILE", home)
    env = {"SOCO_CLI_CONFIG_DIR": "~/custom"}
    assert get_config_dir(system="Linux", home=home, environ=env) == os.path.join(
        home, "custom"
    )


def test_ensure_config_dir_creates_nested(tmp_path):
    from soco_cli.config_dir import ensure_config_dir

    target = str(tmp_path / "a" / "b" / "soco-cli")
    assert ensure_config_dir(target) is True
    assert os.path.isdir(target)
    # Idempotent
    assert ensure_config_dir(target) is True
