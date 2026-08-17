#!/usr/bin/env bash

input=$(cat)

# ANSI colors
blue='\033[38;2;0;153;255m'
orange='\033[38;2;255;176;85m'
green='\033[38;2;0;160;0m'
cyan='\033[38;2;46;149;153m'
red='\033[38;2;255;85;85m'
yellow='\033[38;2;230;200;0m'
white='\033[38;2;220;220;220m'
gray='\033[38;2;110;110;110m'
dim='\033[2m'
reset='\033[0m'

sep="${dim}${white} | ${reset}"

# --- Model ---
model=$(echo "$input" | jq -r '.model.display_name // "unknown"')
model_short=$(echo "$model" | sed 's/Claude //' | sed 's/ (.*)//')
model_part="${blue}${model_short}${reset}"

# --- CWD @ Branch ---
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
cwd_name=$(basename "$cwd")
branch=$(git -C "$cwd" --no-optional-locks rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ -n "$branch" ]; then
  location_part="${cyan}${cwd_name}${reset}${dim}@${reset}${red}${branch}${reset}"
else
  location_part="${cyan}${cwd_name}${reset}"
fi

# --- Tokens ---
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
total_ctx=$(echo "$input" | jq -r '.context_window.context_window_size // empty')

format_k() {
  local n=$1
  if [ -z "$n" ] || [ "$n" = "null" ]; then
    echo "?"
  elif [ "$n" -ge 1000000 ]; then
    printf "%.1fM" "$(echo "scale=2; $n / 1000000" | bc)"
  elif [ "$n" -ge 1000 ]; then
    printf "%.0fK" "$(echo "scale=1; $n / 1000" | bc)"
  else
    echo "$n"
  fi
}

if [ -n "$total_ctx" ] && [ -n "$used_pct" ]; then
  used_tokens=$(echo "scale=0; $total_ctx * $used_pct / 100" | bc)
  used_fmt=$(format_k "$used_tokens")
  total_fmt=$(format_k "$total_ctx")
  pct_int=$(printf "%.0f" "$used_pct")
  if [ "$pct_int" -ge 80 ]; then
    pct_color="$red"
  elif [ "$pct_int" -ge 50 ]; then
    pct_color="$yellow"
  else
    pct_color="$green"
  fi
  tokens_part="${white}${used_fmt}/${total_fmt}${reset} ${pct_color}${pct_int}%${reset}"
else
  tokens_part=""
fi

# --- Effort ---
effort=$(echo "$input" | jq -r '.output_style.name // empty')
if [ -z "$effort" ] || [ "$effort" = "null" ] || [ "$effort" = "default" ]; then
  effort_level=$(jq -r '.effortLevel // empty' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json" 2>/dev/null)
  if [ -n "$effort_level" ]; then
    effort_part="${dim}effort: ${reset}${orange}${effort_level}${reset}"
  else
    effort_part=""
  fi
else
  effort_lower=$(echo "$effort" | tr '[:upper:]' '[:lower:]')
  effort_part="${dim}effort: ${reset}${orange}${effort_lower}${reset}"
fi

# --- Rate limit stat builder ---
# build_stat LABEL budget_pct time_pct
# Renders: LABEL budget_pct% pace×
build_stat() {
  local label="$1"
  local budget_pct="$2"
  local time_pct="$3"

  local pace_str
  if [ "$(echo "$time_pct < 1" | bc)" -eq 1 ]; then
    pace_str="--"
  else
    pace_str=$(awk -v b="$budget_pct" -v t="$time_pct" 'BEGIN {
      pace = b / t
      if (pace > 10) pace = 10
      printf "%.2f", pace
    }')
  fi

  local budget_int
  budget_int=$(printf "%.0f" "$budget_pct")

  printf "%b" "${white}${label}${reset} ${white}${budget_int}%${reset} ${gray}${pace_str}x${reset}"
}

# --- Rate limits ---
five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
seven_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
seven_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')

# Compute time_pct for a window given its reset epoch and window duration in seconds
window_time_pct() {
  local reset_epoch="$1"
  local window_secs="$2"
  if [ -z "$reset_epoch" ] || [ "$reset_epoch" = "null" ]; then
    echo "50"
    return
  fi
  local now
  now=$(date +%s)
  local start=$(( reset_epoch - window_secs ))
  local elapsed=$(( now - start ))
  awk -v e="$elapsed" -v w="$window_secs" 'BEGIN {
    pct = e * 100 / w
    if (pct < 0) pct = 0
    if (pct > 100) pct = 100
    printf "%.2f\n", pct
  }'
}

# Format a reset epoch as a compact time or date string.
# Same-day resets → "3:42pm"; future-day resets → "Sat 2pm"
format_reset() {
  local epoch="$1"
  if [ -z "$epoch" ] || [ "$epoch" = "null" ]; then
    echo ""
    return
  fi
  local today
  today=$(date +%Y-%m-%d)
  local reset_day
  reset_day=$(date -r "$epoch" +%Y-%m-%d 2>/dev/null || date -d "@$epoch" +%Y-%m-%d 2>/dev/null)
  if [ "$reset_day" = "$today" ]; then
    # Same day: show time like "3:42pm"
    date -r "$epoch" +"%-I:%M%p" 2>/dev/null | tr '[:upper:]' '[:lower:]' \
      || date -d "@$epoch" +"%-I:%M%p" 2>/dev/null | tr '[:upper:]' '[:lower:]'
  else
    # Different day: show "Sat 2pm"
    date -r "$epoch" +"%a %-I%p" 2>/dev/null | sed 's/AM/am/;s/PM/pm/' \
      || date -d "@$epoch" +"%a %-I%p" 2>/dev/null | sed 's/AM/am/;s/PM/pm/'
  fi
}

five_part=""
if [ -n "$five_pct" ]; then
  five_time_pct=$(window_time_pct "$five_reset" 18000)   # 5h = 18000s
  five_reset_str=$(format_reset "$five_reset")
  five_label=$(printf "%b" "${gray}${five_reset_str:-5h}${reset}")
  five_part=$(build_stat "$five_label" "$five_pct" "$five_time_pct")
fi

seven_part=""
if [ -n "$seven_pct" ]; then
  seven_time_pct=$(window_time_pct "$seven_reset" 604800) # 7d = 604800s
  seven_reset_str=$(format_reset "$seven_reset")
  seven_label=$(printf "%b" "${gray}${seven_reset_str:-7d}${reset}")
  seven_part=$(build_stat "$seven_label" "$seven_pct" "$seven_time_pct")
fi

# --- Assemble single line ---
parts=("$model_part")
[ -n "$effort_part" ] && parts+=("$effort_part")
parts+=("$location_part")
[ -n "$tokens_part" ] && parts+=("$tokens_part")
[ -n "$five_part" ] && parts+=("$five_part")
[ -n "$seven_part" ] && parts+=("$seven_part")

line=""
for i in "${!parts[@]}"; do
  if [ $i -eq 0 ]; then
    line="${parts[$i]}"
  else
    line="${line}${sep}${parts[$i]}"
  fi
done

printf "%b\n" "$line"
