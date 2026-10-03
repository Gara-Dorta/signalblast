#!/bin/bash

# Install or uninstall the signalblast watchdog for the current user, see docker/watchdog.sh
#
# Install:
#   curl -fsSL https://raw.githubusercontent.com/Gara-Dorta/signalblast/main/docker/install_watchdog.sh | bash
# Uninstall:
#   curl -fsSL https://raw.githubusercontent.com/Gara-Dorta/signalblast/main/docker/install_watchdog.sh | bash -s -- --uninstall
# The files are downloaded from the latest release by default, install from a branch or tag instead with:
#   ... | bash -s -- --ref <branch or tag>

# Print the tag of the latest signalblast release, fails if it can't be found
latest_release_tag() {
    local response tag
    response="$(curl -fsSL https://api.github.com/repos/Gara-Dorta/signalblast/releases/latest)" || return 1
    tag="$(printf '%s\n' "$response" | sed -nE 's/.*"tag_name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p')"
    # Keep only the first match
    tag="${tag%%$'\n'*}"
    [ -n "$tag" ] || return 1
    printf '%s\n' "$tag"
}

# Everything is inside a function so that nothing runs if the download is interrupted
main() {
    set -euo pipefail

    # Defaults to the latest release, it is resolved after parsing the arguments
    local ref=""
    local uninstall=false

    while [ $# -gt 0 ]; do
        case "$1" in
            --uninstall) uninstall=true ;;
            --ref)
                ref="${2:?--ref requires a value}"
                shift
                ;;
            *)
                echo "Unknown argument: $1" >&2
                exit 1
                ;;
        esac
        shift
    done

    local bin_path="$HOME/.local/bin/signalblast-watchdog"
    local unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

    if [ "$uninstall" = true ]; then
        systemctl --user disable --now signalblast-watchdog.timer 2>/dev/null || true
        rm -f "$bin_path" "$unit_dir/signalblast-watchdog.service" "$unit_dir/signalblast-watchdog.timer"
        systemctl --user daemon-reload
        echo "signalblast watchdog uninstalled"
        exit 0
    fi

    for cmd in curl docker systemctl; do
        if ! command -v "$cmd" >/dev/null; then
            echo "$cmd is required but it is not installed" >&2
            exit 1
        fi
    done

    if ! docker info >/dev/null 2>&1; then
        echo "$(id -un) can't run docker, add it to the docker group or use rootless docker" >&2
        exit 1
    fi

    if [ -z "$ref" ]; then
        if ! ref="$(latest_release_tag)"; then
            echo "Warning: could not find the latest signalblast release, installing from main" >&2
            ref="main"
        fi
    fi
    echo "Installing the signalblast watchdog from $ref"
    local base_url="https://raw.githubusercontent.com/Gara-Dorta/signalblast/$ref"

    mkdir -p "$(dirname "$bin_path")" "$unit_dir"
    curl -fsSL "$base_url/docker/watchdog.sh" -o "$bin_path"
    chmod 755 "$bin_path"
    curl -fsSL "$base_url/systemd/signalblast-watchdog.service" -o "$unit_dir/signalblast-watchdog.service"
    curl -fsSL "$base_url/systemd/signalblast-watchdog.timer" -o "$unit_dir/signalblast-watchdog.timer"

    systemctl --user daemon-reload
    systemctl --user enable --now signalblast-watchdog.timer

    # Without lingering, user timers only run while the user is logged in
    if [ "$(loginctl show-user "$(id -un)" --property=Linger --value 2>/dev/null)" != "yes" ]; then
        if ! loginctl enable-linger 2>/dev/null; then
            echo "Warning: the watchdog only runs while you are logged in, enable it at all times with:" >&2
            echo "  sudo loginctl enable-linger $(id -un)" >&2
        fi
    fi

    echo "signalblast watchdog installed"
    systemctl --user list-timers signalblast-watchdog.timer
}

main "$@"
