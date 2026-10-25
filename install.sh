#!/bin/bash

# Install or update signalblast with docker compose for the current user
#
# Set up signal-cli-rest-api for the bot's phone number first, see the README, then run:
#   curl -fsSL https://raw.githubusercontent.com/Gara-Dorta/signalblast/main/install.sh | bash
# Run it again to update, the settings in .env are kept.
# It asks for the version to install, the latest release by default, and for the folder where docker-compose.yaml
# and .env are stored, ~/.config/signalblast by default. The defaults are used when it is run without a terminal.

# Where signal-cli-rest-api stores its data, it is mounted by docker-compose.yaml
SIGNAL_API_DIR="$HOME/.local/share/signal-api"

# Print the tag of the latest signalblast release, fails if it can't be found
latest_release_tag() {
    local response tag
    response="$(curl -fsSL --connect-timeout 5 --max-time 10 https://api.github.com/repos/Gara-Dorta/signalblast/releases/latest)" || return 1
    tag="$(printf '%s\n' "$response" | sed -nE 's/.*"tag_name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p')"
    # Keep only the first match
    tag="${tag%%$'\n'*}"
    [ -n "$tag" ] || return 1
    printf '%s\n' "$tag"
}

# Ask a question on the terminal and print the answer: ask <question> [--secret]
ask() {
    local answer="" char
    if [ "${2:-}" = "--secret" ]; then
        # Read one character at a time to show a * for each, read returns an empty character on enter
        printf '%s' "$1" >&2
        while IFS= read -r -s -n 1 char < /dev/tty && [ -n "$char" ]; do
            # Backspace or delete
            if [ "$char" = $'\x7f' ] || [ "$char" = $'\b' ]; then
                if [ -n "$answer" ]; then
                    answer="${answer%?}"
                    printf '\b \b' >&2
                fi
            else
                answer+="$char"
                printf '*' >&2
            fi
        done
        echo >&2
    else
        read -r -p "$1" answer < /dev/tty
    fi
    printf '%s\n' "$answer"
}

# Ask a yes/no question on the terminal, defaults to no: ask_yes <question> [--default-yes]
ask_yes() {
    local answer
    if [ "${2:-}" = "--default-yes" ]; then
        answer="$(ask "$1 [Y/n] ")"
        [[ ! "$answer" =~ ^[Nn] ]]
    else
        answer="$(ask "$1 [y/N] ")"
        [[ "$answer" =~ ^[Yy] ]]
    fi
}

# Print the phone number of the signal-cli account, only if there is exactly one
detected_number() {
    local numbers
    numbers="$(grep -oE '"number"[[:space:]]*:[[:space:]]*"[^"]+"' "$SIGNAL_API_DIR/data/accounts.json" 2>/dev/null \
        | sed -E 's/.*"([^"]+)"$/\1/')" || return 0
    if [ "$(printf '%s\n' "$numbers" | grep -c .)" -eq 1 ]; then
        printf '%s\n' "$numbers"
    fi
}

# Whether a variable has a value in an .env file, i.e. it is not empty or empty quotes: env_is_set <file> <name>
env_is_set() {
    grep -qE "^$2=(\"[^\"]|'[^']|[^\"'[:space:]])" "$1"
}

# Set a variable in an .env file, replacing its first line, commented or not: set_env <file> <name> <value>
set_env() {
    # Double quoted, docker compose reads \\, \" and \$ in them as \, " and a $ that doesn't start a variable
    local value="${3//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//\$/\\\$}"
    local updated
    updated="$(NAME="$2" VALUE="\"$value\"" awk '
        !done && $0 ~ ("^#? ?" ENVIRON["NAME"] "=") { print ENVIRON["NAME"] "=" ENVIRON["VALUE"]; done = 1; next }
        { print }
        END { if (!done) print ENVIRON["NAME"] "=" ENVIRON["VALUE"] }
    ' "$1")"
    # Written in place so that the file keeps its permissions
    printf '%s\n' "$updated" > "$1"
}

# Everything is inside a function so that nothing runs if the download is interrupted
main() {
    set -euo pipefail

    # Whether the user can be asked, stdin is the script itself when it is piped into bash so the terminal is used
    local interactive=false
    if (: < /dev/tty) 2>/dev/null; then
        interactive=true
    fi

    for cmd in curl docker; do
        if ! command -v "$cmd" >/dev/null; then
            echo "$cmd is required but it is not installed" >&2
            exit 1
        fi
    done

    if ! docker info >/dev/null 2>&1; then
        echo "$(id -un) can't run docker, add it to the docker group or use rootless docker" >&2
        exit 1
    fi

    if ! docker compose version >/dev/null 2>&1; then
        echo "docker compose is required but it is not installed" >&2
        exit 1
    fi

    if [ ! -d "$SIGNAL_API_DIR/data" ]; then
        echo "signal-cli-rest-api is not set up in $SIGNAL_API_DIR, set it up first as described in" >&2
        echo "  https://github.com/Gara-Dorta/signalblast#installation" >&2
        exit 1
    fi

    # Defaults to the latest release
    local ref answer
    if ! ref="$(latest_release_tag)"; then
        echo "Warning: could not find the latest signalblast release, defaulting to main" >&2
        ref="main"
    fi
    local dir="${XDG_CONFIG_HOME:-$HOME/.config}/signalblast"
    if [ "$interactive" = true ]; then
        answer="$(ask "Version of signalblast to install, a release tag or a branch [$ref]: ")"
        ref="${answer:-$ref}"
        answer="$(ask "Folder for docker-compose.yaml and the settings [$dir]: ")"
        dir="${answer:-$dir}"
        # A ~ typed by the user is not expanded by read
        dir="${dir/#\~/$HOME}"
    fi

    echo "Installing signalblast from $ref in $dir"
    local base_url="https://raw.githubusercontent.com/Gara-Dorta/signalblast/$ref"

    mkdir -p "$dir" "$HOME/.local/share/signalblast"

    # Always downloaded, so that running the script again updates signalblast
    curl -fsSL "$base_url/docker-compose.yaml" -o "$dir/docker-compose.yaml"

    local env_file="$dir/.env"
    local new_env=false
    if [ -e "$env_file" ]; then
        echo "Keeping the settings in $env_file"
    else
        # Not readable by others, as it may contain the admin password
        (umask 077 && curl -fsSL "$base_url/.env.example" -o "$env_file")
        new_env=true
    fi

    if ! env_is_set "$env_file" SIGNALBLAST_PHONE_NUMBER; then
        local phone detected
        detected="$(detected_number)"
        if [ "$interactive" = true ]; then
            while true; do
                phone="$(ask "Phone number of the bot${detected:+ [$detected]}: ")"
                phone="${phone:-$detected}"
                [[ "$phone" =~ ^\+[0-9]+$ ]] && break
                echo "The phone number must start with + followed by digits" >&2
            done
        elif [ -n "$detected" ]; then
            phone="$detected"
        else
            echo "Fill in SIGNALBLAST_PHONE_NUMBER in $env_file and run the script again" >&2
            exit 1
        fi
        set_env "$env_file" SIGNALBLAST_PHONE_NUMBER "$phone"
    fi

    # The optional settings are only asked on the first install, change them later in .env
    if [ "$new_env" = true ] && [ "$interactive" = true ]; then
        local password confirmation receiver instructions_url
        while true; do
            password="$(ask "Password to become an admin, empty for none: " --secret)"
            [ -z "$password" ] && break
            confirmation="$(ask "Repeat the password: " --secret)"
            [ "$password" = "$confirmation" ] && break
            echo "The passwords don't match" >&2
        done
        if [ -n "$password" ]; then
            set_env "$env_file" SIGNALBLAST_PASSWORD "$password"
        else
            echo "Warning: without a password nobody can become an admin, set SIGNALBLAST_PASSWORD in $env_file" >&2
        fi

        receiver="$(ask "Contact or group that receives the health check pings, empty to disable it: ")"
        [ -z "$receiver" ] || set_env "$env_file" SIGNALBLAST_HEALTHCHECK_RECEIVER "$receiver"

        instructions_url="$(ask "Link with instructions shown in the help, empty for none: ")"
        [ -z "$instructions_url" ] || set_env "$env_file" SIGNALBLAST_INSTRUCTIONS_URL "$instructions_url"
    fi

    # Containers outside the signalblast compose project conflict if they use the signal-cli data, like the
    # signal-cli-rest-api container used to set up the number, or if they have the container names of docker-compose.yaml
    local conflicts=() descriptions=() containers name image project mounts
    mapfile -t containers < <(docker ps -aq)
    if [ ${#containers[@]} -gt 0 ]; then
        # Not separated by tabs, as read merges consecutive whitespace separators and the project is often empty
        while IFS=',' read -r name image project mounts; do
            name="${name#/}"
            if [[ "$project" != signalblast && ( "$name" == signalblast || "$name" == signal-cli-rest-api
                || "$mounts" == *"|$SIGNAL_API_DIR|"* ) ]]; then
                conflicts+=("$name")
                descriptions+=("  $name ($image)")
            fi
        done < <(docker inspect --format \
            '{{.Name}},{{.Config.Image}},{{index .Config.Labels "com.docker.compose.project"}},{{range .Mounts}}|{{.Source}}{{end}}|' \
            "${containers[@]}")
    fi
    if [ ${#conflicts[@]} -gt 0 ]; then
        echo "These containers have to be removed, the data of signal-cli-rest-api is kept in $SIGNAL_API_DIR:"
        printf '%s\n' "${descriptions[@]}"
        if [ "$interactive" = false ] || ! ask_yes "Remove them?" --default-yes; then
            echo "Remove them with \`docker rm -f ${conflicts[*]}\` and run the script again" >&2
            exit 1
        fi
        docker rm -f "${conflicts[@]}" >/dev/null
    fi

    # The folder of the compose file is the project directory, where .env is read from
    local compose=(docker compose -f "$dir/docker-compose.yaml")
    "${compose[@]}" up -d --pull always

    # The watchdog restarts the containers when the health check fails, so it needs a receiver for the pings
    # An installed watchdog is updated without asking
    if env_is_set "$env_file" SIGNALBLAST_HEALTHCHECK_RECEIVER \
        && { [ -e "$HOME/.local/bin/signalblast-watchdog" ] \
            || { [ "$interactive" = true ] && command -v systemctl >/dev/null \
                && ask_yes "Install the watchdog, which restarts the containers when the health check fails?"; }; }; then
        curl -fsSL "$base_url/docker/install_watchdog.sh" | bash -s -- --ref "$ref"
    fi

    "${compose[@]}" ps
    echo
    echo "signalblast is installed and running"
    echo "* Become an admin by sending \`!add admin <password>\` to the bot"
    echo "* Run this script again to update signalblast, or to apply changes to the settings in $env_file"
    echo "* See the logs with \`cd $dir && docker compose logs -f\`"
}

main "$@"
