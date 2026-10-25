#!/bin/bash

# Install or uninstall the signalblast watchdog for the current user, see docker/watchdog.sh
#
# Install:
#   curl -fsSL https://github.com/Gara-Dorta/signalblast/releases/latest/download/install_watchdog.sh | bash
# Uninstall:
#   curl -fsSL https://github.com/Gara-Dorta/signalblast/releases/latest/download/install_watchdog.sh | bash -s -- --uninstall
# The files are downloaded from the latest release by default, install from a branch or tag instead with:
#   ... | bash -s -- --ref <branch or tag>

# Print the tag of the latest signalblast release, fails if it can't be found. Read from where the latest release
# redirects to, .../releases/tag/<tag>, which unlike the GitHub API has no rate limit
latest_release_tag() {
    local url
    url="$(curl -fsSLI -o /dev/null -w '%{url_effective}' --connect-timeout 5 --max-time 10 \
        "https://github.com/Gara-Dorta/signalblast/releases/latest")" || return 1
    [[ "$url" == */releases/tag/* ]] || return 1
    printf '%s\n' "${url##*/}"
}

# Write the output of a command to a file, replacing the old one in a single step, so that a failure leaves the old
# one unchanged and a script that is running keeps reading the old version: write_file <file> <mode> <command...>
write_file() {
    local file="$1" mode="$2" tmp
    shift 2
    tmp="$(mktemp "$file.XXXXXX")"
    if ! "$@" > "$tmp"; then
        rm -f "$tmp"
        return 1
    fi
    chmod "$mode" "$tmp"
    mv "$tmp" "$file"
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
        local files=("$bin_path" "$unit_dir/signalblast-watchdog.service" "$unit_dir/signalblast-watchdog.timer")
        local installed=false file
        for file in "${files[@]}"; do
            if [ -e "$file" ]; then
                installed=true
            fi
        done
        if [ "$installed" = false ]; then
            echo "signalblast watchdog is not installed"
            exit 0
        fi

        # Without systemd, or without a user session, there is no timer to stop, only the files to remove
        local systemd=false
        if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
            systemd=true
        fi
        if [ "$systemd" = true ]; then
            systemctl --user disable --now signalblast-watchdog.timer 2>/dev/null || true
        fi
        rm -f "${files[@]}"
        # The files are already removed, a failed reload only means systemd keeps the old units loaded until the next one
        if [ "$systemd" = true ]; then
            systemctl --user daemon-reload || true
        fi
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
    write_file "$bin_path" 755 curl -fsSL "$base_url/docker/watchdog.sh"
    write_file "$unit_dir/signalblast-watchdog.service" 644 curl -fsSL "$base_url/systemd/signalblast-watchdog.service"
    write_file "$unit_dir/signalblast-watchdog.timer" 644 curl -fsSL "$base_url/systemd/signalblast-watchdog.timer"

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
    systemctl --user --no-pager list-timers signalblast-watchdog.timer
}

main "$@"
