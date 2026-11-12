#!/bin/bash
set -e

# If directories are passed as arguments, use them.
# Otherwise process the entire repo.
if [ "$#" -gt 0 ]; then
  TARGET_DIRS=("$@")
else
  TARGET_DIRS=(".")
fi

echo "Directories to process:"
printf " - %s\n" "${TARGET_DIRS[@]}"

_month_name() {
  case "$1" in
    01) echo "January" ;;  02) echo "February" ;; 03) echo "March" ;;
    04) echo "April" ;;    05) echo "May" ;;       06) echo "June" ;;
    07) echo "July" ;;     08) echo "August" ;;    09) echo "September" ;;
    10) echo "October" ;;  11) echo "November" ;;  12) echo "December" ;;
  esac
}

# Pages under techradar/ link techradar/radar.css and get a bar linking back to
# keithfry.net. The bar markup must match news-radar's site_bar_html().
RADAR_ROOT="techradar"
HOME_URL="https://keithfry.net/"
HOME_LABEL="Keith Fry"
SECTION_LABEL="Tech Radar"

# Print the relative path from DIR up to techradar/ ("", "../", "../../").
# Returns 1 for a directory outside techradar/.
_radar_prefix() {
  local d="${1#./}"
  d="${d%/}"
  if [[ "$d" == "$RADAR_ROOT" ]]; then
    echo ""
    return 0
  fi
  if [[ "$d" == "$RADAR_ROOT"/* ]]; then
    local rest="${d#"$RADAR_ROOT"/}" prefix="" part
    local IFS=/
    for part in $rest; do prefix+="../"; done
    echo "$prefix"
    return 0
  fi
  return 1
}

# Print the site bar for a directory under techradar/.
_site_bar() {
  local d="${1#./}" prefix="$2"
  d="${d%/}"
  local rest="${d#"$RADAR_ROOT"}"
  rest="${rest#/}"
  echo '<nav class="site-bar" aria-label="Site">'
  echo "  <a class=\"site-bar-home\" href=\"$HOME_URL\">$HOME_LABEL</a>"
  echo '  <ol class="site-bar-crumbs">'
  if [[ -z "$rest" ]]; then
    echo "    <li aria-current=\"page\">$SECTION_LABEL</li>"
  else
    echo "    <li><a href=\"$prefix\">$SECTION_LABEL</a></li>"
    local IFS=/
    local parts=($rest)
    unset IFS
    local n=${#parts[@]} i up label
    for ((i = 0; i < n; i++)); do
      label="${parts[$i]}"
      if [[ "$label" =~ ^([0-9]{4})-([0-9]{2})$ ]]; then
        label="$(_month_name "${BASH_REMATCH[2]}") ${BASH_REMATCH[1]}"
      fi
      if ((i == n - 1)); then
        echo "    <li aria-current=\"page\">$label</li>"
      else
        up=""
        for ((j = i + 1; j < n; j++)); do up+="../"; done
        echo "    <li><a href=\"$up\">$label</a></li>"
      fi
    done
  fi
  echo '  </ol>'
  echo '</nav>'
}

_dir_title() {
  case "$1" in
    techradar|./techradar|techradar/|./techradar/)    echo "Tech Radar" ;;
    techradar/AI|./techradar/AI|AI|./AI)                 echo "AI Tech Radar" ;;
    techradar/Robotics|./techradar/Robotics|Robotics|./Robotics) echo "Robotics Tech Radar" ;;
    techradar/Research|./techradar/Research|Research|./Research) echo "Research Tech Radar" ;;
    resume/certifications|./resume/certifications) echo "Certifications" ;;
    *) echo "$(basename "$1")" ;;
  esac
}

generate_index() {
  local dir="$1"
  local index="$dir/index.html"

  # Skip .git and .github (both at root and nested)
  if [[ "$dir" == .git* ]] || [[ "$dir" == .github* ]] || [[ "$dir" == *"/.git"* ]] || [[ "$dir" == *"/.github"* ]]; then
    return
  fi

  # Skip if index.html exists and no files in this dir are newer than it
  if [[ -f "$index" ]]; then
    newer=$(find "$dir" -maxdepth 1 ! -name "index.html" -newer "$index" | head -1)
    if [[ -z "$newer" ]]; then
      echo " → Skipping $index (up to date)"
      return
    fi
  fi

  echo " → Generating $index"

  # Collect files and extract dates
  declare -a files_list

  for f in "$dir"/*; do
    [[ -e "$f" ]] || continue
    [[ "$f" == "$index" ]] && continue

    fname=$(basename "$f")
    [[ "$fname" == favicon.* ]] && continue

    # Year-month subdir (e.g. 2026-06): expand its HTML files with relative paths
    if [[ -d "$f" ]] && [[ "$fname" =~ ^([0-9]{4})-([0-9]{2})$ ]]; then
      ym="$fname"
      ym_year="${BASH_REMATCH[1]}"
      ym_month="${BASH_REMATCH[2]}"
      ym_month_name="$(_month_name "$ym_month")"
      ym_month_key="$ym_year-$ym_month"
      ym_month_label="$ym_month_name $ym_year"

      for sub_f in "$f"/*.html; do
        [[ -e "$sub_f" ]] || continue
        sub_fname=$(basename "$sub_f")
        [[ "$sub_fname" == "index.html" ]] && continue
        if [[ "$sub_fname" =~ ([0-9]{4})-([0-9]{2})-([0-9]{2}) ]]; then
          sub_day="${BASH_REMATCH[3]}"
          rel_path="$ym/$sub_fname"
          files_list+=("$ym_month_key|$ym_year-$ym_month-$sub_day|$ym_month_label|$rel_path")
        fi
      done
      continue
    fi

    # Skip non-HTML files and non-directories
    if [[ ! -d "$f" ]] && [[ "$fname" != *.html ]]; then continue; fi

    # Try to extract date in YYYY-MM-DD format from filename
    if [[ "$fname" =~ ([0-9]{4})-([0-9]{2})-([0-9]{2}) ]]; then
      year="${BASH_REMATCH[1]}"
      month="${BASH_REMATCH[2]}"
      day="${BASH_REMATCH[3]}"
      month_name="$(_month_name "$month")"
      month_key="$year-$month"
      month_label="$month_name $year"
      files_list+=("$month_key|$year-$month-$day|$month_label|$fname")
    else
      # No date found, use a default group
      files_list+=("0000-00|0000-00-00|Other|$fname")
    fi
  done

  local radar_prefix="" is_radar=0
  if radar_prefix="$(_radar_prefix "$dir")"; then
    is_radar=1
  fi

  local page_title
  page_title="$(_dir_title "$dir")"

  {
    echo '<!DOCTYPE html>'
    echo '<html lang="en">'
    echo "<head>"
    echo '<meta charset="UTF-8">'
    echo '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    echo '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">'
    echo '<meta http-equiv="Pragma" content="no-cache">'
    echo '<meta http-equiv="Expires" content="0">'
    echo "<title>$page_title</title>"
    if ((is_radar)); then
      echo "<link rel=\"stylesheet\" href=\"${radar_prefix}radar.css\">"
    fi
    echo '<script>'
    echo '(function() {'
    echo '  var reloadKey = "reload_" + window.location.pathname;'
    echo '  var isReloading = false;'
    echo '  if (sessionStorage.getItem(reloadKey) === "true") {'
    echo '    sessionStorage.removeItem(reloadKey);'
    echo '    isReloading = true;'
    echo '    location.reload(true);'
    echo '  }'
    echo '  window.addEventListener("pagehide", function() {'
    echo '    if (!isReloading) {'
    echo '      sessionStorage.setItem(reloadKey, "true");'
    echo '    }'
    echo '  });'
    echo '})();'
    echo '</script>'
    echo "</head>"
    echo "<body>"
    if ((is_radar)); then
      _site_bar "$dir" "$radar_prefix"
    fi
    echo '<main class="container">'
    echo "<h1 class=\"index-title\">$page_title</h1>"

    # Podcast link for techradar directories
    if [[ -f "$dir/podcast.rss" ]]; then
      local podcast_url
      podcast_url="https://keithfry.net/$(echo "$dir" | sed 's|^\./||')/podcast.rss"
      echo "<div class=\"podcast-bar\">"
      echo "  &#127897; <a href=\"./podcast.rss\" id=\"podcast-link\">Podcast RSS Feed</a>"
      echo "  <button class=\"copy-btn\" onclick=\"(function(){var url='${podcast_url}';navigator.clipboard.writeText(url).then(function(){var b=document.querySelector('.copy-btn');var orig=b.textContent;b.textContent='Copied!';setTimeout(function(){b.textContent=orig;},1500);});})();\">Copy URL</button>"
      echo "</div>"
    fi

    # Dated entries newest first, grouped by month. Undated entries (topic
    # folders on the landing page) come last, A to Z, with no group heading.
    [[ ${#files_list[@]} -gt 0 ]] && printf '%s\n' "${files_list[@]}" | sort -t'|' -k2,2r -k4,4 | {
      current_month=""
      while IFS='|' read -r month_key date month_label fname; do
        if [[ "$month_key" != "$current_month" ]]; then
          # Close previous month's list if any
          [[ -n "$current_month" ]] && echo "</ul>"

          if [[ "$month_key" == "0000-00" ]]; then
            echo '<ul class="topic-list">'
          else
            echo "<h2>$month_label</h2>"
            echo '<ul class="digest-list">'
          fi
          current_month="$month_key"
        fi

        audio_badge=""
        if [[ "$fname" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
          date_part="${BASH_REMATCH[1]}"
          # fname may be "2026-06/ai-radar-2026-06-11.html" or "ai-radar-2026-06-11.html"
          fsubdir=$(dirname "$fname")
          if [[ "$fsubdir" == "." ]]; then
            mp3_search_dir="$dir"
            mp3_prefix=""
          else
            mp3_search_dir="$dir/$fsubdir"
            mp3_prefix="$fsubdir/"
          fi
          mp3_file=$(find "$mp3_search_dir" -maxdepth 1 -name "*-radar-${date_part}.mp3" | head -1)
          if [[ -n "$mp3_file" ]]; then
            mp3_name="${mp3_prefix}$(basename "$mp3_file")"
            audio_badge=" <a href=\"./${mp3_name}\" title=\"Listen to podcast\" style=\"text-decoration:none;\">&#127897;</a>"
          fi
        fi
        display_name=$(basename "$fname")
        echo "<li><a href=\"./$fname\">$display_name</a>${audio_badge}</li>"
      done

      # Close final list
      [[ -n "$current_month" ]] && echo "</ul>"
    }

    echo "</main>"
    echo "</body></html>"
  } > "$index"
}

# Walk every target directory and subdirectory
for base in "${TARGET_DIRS[@]}"; do
  find "$base" -type d | while read dir; do
    generate_index "$dir"
  done
done
