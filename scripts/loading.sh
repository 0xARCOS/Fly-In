#!/usr/bin/env bash
# Fly-In · pantallas de carga del Makefile.
#
# Todo se escribe en stderr: `make run > out.txt` sigue dejando en el fichero
# solo las líneas de turno del subject. Sin terminal, con NO_COLOR o con
# TERM=dumb, la salida es texto plano y sin animación.
#
# Uso (desde el Makefile):
#   loading.sh menu
#   loading.sh header "TITLE" "subtitle"
#   loading.sh step [--tail|--show] "N/M" "Label" -- command args...
#   loading.sh launch MAP
#   loading.sh finish "TITLE" "hint"

set -u

if [ -t 2 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != "dumb" ]; then
    FANCY=1
else
    FANCY=0
fi

# --- estilo --------------------------------------------------------------

# Repite un carácter N veces (tr no sirve: trabaja byte a byte y rompe los
# caracteres multibyte como · o ═).
repeat() {
    local text
    text=$(printf '%*s' "$2" '')
    printf '%s' "${text// /$1}"
}

# Rellena con espacios hasta N caracteres (printf '%-Ns' cuenta bytes y
# desalinea los textos con caracteres multibyte).
padr() {
    local text="$1" n=$(( $2 - ${#1} ))
    [ "$n" -lt 0 ] && n=0
    printf '%s%*s' "$text" "$n" ''
}

esc() { [ "$FANCY" = 1 ] && printf '\033[%sm' "$1"; return 0; }
RESET=$(esc 0); BOLD=$(esc 1); DIM=$(esc "38;5;244")
CYAN=$(esc "1;38;5;51"); PINK=$(esc "1;38;5;201"); GREEN=$(esc "1;38;5;46")
YELLOW=$(esc "1;38;5;226"); RED=$(esc "1;38;5;196"); WHITE=$(esc "1;38;5;255")
BLUE=$(esc "38;5;63")

say() { printf '%b\n' "$*" >&2; }

SPINNER=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
TIPS=(
    "Drones entering a restricted zone spend 2 turns in the air."
    "Waiting is a move too: it is how a drone yields a bottleneck."
    "Priority zones win ties between equally short routes."
    "start_hub and end_hub never run out of room."
    "WHCA* searches in space AND time: every state is (zone, turn)."
    "Every turn is double-checked: zero capacity violations allowed."
    "make run opens a pygame window; the event log stays here."
    "In the window: SPACE pauses, ESC closes it (the log keeps going)."
    "No display? The same run plays as a colored log in this terminal."
    "Skip the animation with  ARGS=\"--delay 0\""
    "A drone in the air cannot stop, turn back or be replanned."
    "Planning order matters: the first drone gets the best bookings."
)

now() {
    # Segundos con décimas; EPOCHREALTIME existe desde bash 5.
    if [ -n "${EPOCHREALTIME:-}" ]; then
        printf '%s' "${EPOCHREALTIME/,/.}"
    else
        printf '%s' "$SECONDS"
    fi
}

elapsed() { awk -v a="$1" -v b="$(now)" 'BEGIN { printf "%.1fs", b - a }'; }

cursor_off() { [ "$FANCY" = 1 ] && printf '\033[?25l' >&2; return 0; }
cursor_on() { [ "$FANCY" = 1 ] && printf '\033[?25h' >&2; return 0; }

# --- piezas --------------------------------------------------------------

logo() {
    local colors=(51 50 49 48 47 46) i=0 line
    local rows=(
        "███████╗██╗  ██╗   ██╗      ██╗███╗   ██╗"
        "██╔════╝██║  ╚██╗ ██╔╝      ██║████╗  ██║"
        "█████╗  ██║   ╚████╔╝ █████╗██║██╔██╗ ██║"
        "██╔══╝  ██║    ╚██╔╝  ╚════╝██║██║╚██╗██║"
        "██║     ███████╗██║         ██║██║ ╚████║"
        "╚═╝     ╚══════╝╚═╝         ╚═╝╚═╝  ╚═══╝"
    )
    say ""
    for line in "${rows[@]}"; do
        say "  $(esc "1;38;5;${colors[$i]}")${line}${RESET}"
        i=$((i + 1))
    done
    say "  ${PINK}DRONE SWARM ROUTING SIMULATOR${RESET}${DIM}  ·  WHCA* space-time A*${RESET}"
    say ""
}

header() {
    local title="$1" subtitle="${2:-}"
    say ""
    say "  ${CYAN}▌FLY-IN▐${RESET} ${BLUE}━━━━${RESET} ${WHITE}${title}${RESET} ${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    [ -n "$subtitle" ] && say "  ${DIM}${subtitle}${RESET}"
    say ""
}

# Una barra que rebota: la tarea no dice cuánto le falta, así que se
# enseña que está viva, como en un juego que carga un nivel.
bounce_bar() {
    local frame="$1" width=22 block=6 span pos bar="" k
    span=$((width - block))
    pos=$((frame % (2 * span)))
    [ "$pos" -gt "$span" ] && pos=$((2 * span - pos))
    for ((k = 0; k < width; k++)); do
        if [ "$k" -ge "$pos" ] && [ "$k" -lt $((pos + block)) ]; then
            bar+="■"
        else
            bar+="·"
        fi
    done
    printf '%s' "$bar"
}

dots() {
    # Relleno de puntos hasta la columna 46, como un índice de menú.
    local text="$1" n
    n=$((44 - ${#text}))
    [ "$n" -lt 2 ] && n=2
    repeat '·' "$n"
}

step() {
    local mode="plain"
    case "$1" in --tail) mode="tail"; shift ;; --show) mode="show"; shift ;; esac
    local stage="$1" label="$2"
    shift 2
    [ "${1:-}" = "--" ] && shift

    local log start rc
    log=$(mktemp "${TMPDIR:-/tmp}/flyin.XXXXXX")
    start=$(now)

    if [ "$FANCY" = 0 ]; then
        say "  [$stage] $label ..."
        "$@" >"$log" 2>&1
        rc=$?
    else
        "$@" >"$log" 2>&1 &
        local pid=$! frame=0 tip
        cursor_off
        trap 'kill "$pid" 2>/dev/null; cursor_on; printf "\n\n" >&2; rm -f "$log"; exit 130' INT TERM
        while kill -0 "$pid" 2>/dev/null; do
            tip=${TIPS[$(( (frame / 30 + RANDOM_SEED) % ${#TIPS[@]} ))]}
            printf '\r\033[K  %s%s%s %sSTAGE %s%s  %s%s%s %s[%s]%s %s%s%s\n\033[K     %sTIP%s %s%s%s\033[1A' \
                "$CYAN" "${SPINNER[$((frame % 10))]}" "$RESET" \
                "$PINK" "$stage" "$RESET" \
                "$WHITE" "$(padr "$label" 34)" "$RESET" \
                "$BLUE" "$(bounce_bar "$frame")" "$RESET" \
                "$DIM" "$(elapsed "$start")" "$RESET" \
                "$YELLOW" "$RESET" "$DIM" "$tip" "$RESET" >&2
            sleep 0.08
            frame=$((frame + 1))
        done
        wait "$pid"
        rc=$?
        trap - INT TERM
        printf '\r\033[K\n\033[K\033[1A' >&2
        cursor_on
    fi

    local time
    time=$(elapsed "$start")
    if [ "$rc" -ne 0 ]; then
        say "  ${RED}✘${RESET} ${WHITE}${label}${RESET} ${DIM}$(dots "$label")${RESET} ${RED}FAILED${RESET} ${DIM}${time}${RESET}"
        say ""
        say "  ${RED}━━ GAME OVER ━━${RESET} ${DIM}last lines of the log:${RESET}"
        tail -n 40 "$log" | sed 's/^/    /' >&2
        rm -f "$log"
        say ""
        exit "$rc"
    fi
    say "  ${GREEN}✔${RESET} ${WHITE}${label}${RESET} ${DIM}$(dots "$label") ${time}${RESET}"
    case "$mode" in
        tail) say "    ${DIM}↳${RESET} ${GREEN}$(tail -n 1 "$log" | sed 's/=//g; s/^ *//; s/ *$//')${RESET}" ;;
        show) say ""; cat "$log" >&2 ;;
    esac
    rm -f "$log"
}

launch() {
    local map="$1" name frame pct filled bar k
    name=$(basename "$map")
    [ "$FANCY" = 0 ] && return 0
    cursor_off
    local tip=${TIPS[$((RANDOM_SEED % ${#TIPS[@]}))]}
    for ((frame = 0; frame <= 20; frame++)); do
        pct=$((frame * 5))
        filled=$((frame * 26 / 20))
        bar=""
        for ((k = 0; k < 26; k++)); do
            if [ "$k" -lt "$filled" ]; then bar+="█"; else bar+="░"; fi
        done
        printf '\r\033[K  %sLOADING%s %s%s%s %s%s%s %s%3d%%%s\n\033[K     %sTIP%s %s%s%s\033[1A' \
            "$PINK" "$RESET" "$WHITE" "$(padr "$name" 28)" "$RESET" \
            "$GREEN" "$bar" "$RESET" "$DIM" "$pct" "$RESET" \
            "$YELLOW" "$RESET" "$DIM" "$tip" "$RESET" >&2
        sleep 0.025
    done
    printf '\r\033[K\n\033[K\033[1A' >&2
    say "  ${CYAN}▶ PRESS START${RESET} ${DIM}· ${name}${RESET}"
    cursor_on
}

finish() {
    local title="$1" hint="${2:-}" width
    width=$(( ${#title} + 8 ))
    say ""
    say "  ${GREEN}╔$(repeat '═' "$width")╗${RESET}"
    say "  ${GREEN}║    ${title}    ║${RESET}"
    say "  ${GREEN}╚$(repeat '═' "$width")╝${RESET}"
    [ -n "$hint" ] && say "  ${DIM}${hint}${RESET}"
    say ""
}

menu() {
    logo
    say "  ${WHITE}MAIN MENU${RESET}"
    say ""
    local entries=(
        "▶|NEW GAME|make install|install Fly-In and its dev tools"
        " |PLAY|make run MAP=<map>|pygame window + event log here"
        " |HIGH SCORES|make bench|official benchmarks + config comparison"
        " |TRAINING|make test|run the test suite"
        " |ANTI-CHEAT|make lint · make lint-strict|flake8 + mypy"
        " |DEBUG MODE|make debug MAP=<map>|run under pdb"
        " |SAVE CLEANUP|make clean · make fclean|caches · also the .venv"
    )
    local entry arrow name cmd desc
    for entry in "${entries[@]}"; do
        IFS='|' read -r arrow name cmd desc <<<"$entry"
        say "  ${PINK}${arrow}${RESET} ${WHITE}$(padr "$name" 12)${RESET} ${CYAN}$(padr "$cmd" 29)${RESET} ${DIM}${desc}${RESET}"
    done
    say ""
    say "  ${WHITE}LEVEL SELECT${RESET}  ${DIM}make run MAP=maps/oficial_maps/<level>/<map>.txt${RESET}"
    local level file names
    for level in easy medium hard challenger; do
        names=""
        for file in maps/oficial_maps/"$level"/*.txt; do
            [ -e "$file" ] || continue
            file=$(basename "$file" .txt)
            names+="${names:+ · }${file}"
        done
        say "  ${YELLOW}$(padr "${level^^}" 11)${RESET} ${names}"
    done
    say ""
    say "  ${DIM}TIP${RESET} ${DIM}${TIPS[$((RANDOM_SEED % ${#TIPS[@]}))]}${RESET}"
    say ""
}

RANDOM_SEED=$((RANDOM % 10))

cmd="${1:-menu}"
shift || true
case "$cmd" in
    menu) menu ;;
    logo) logo ;;
    header) header "$@" ;;
    step) step "$@" ;;
    launch) launch "$@" ;;
    finish) finish "$@" ;;
    *) say "loading.sh: unknown command '$cmd'"; exit 2 ;;
esac
