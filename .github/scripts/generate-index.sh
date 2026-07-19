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

_dir_title() {
  case "$1" in
    techradar/AI|./techradar/AI|AI|./AI)                 echo "AI Tech Radar" ;;
    techradar/Robotics|./techradar/Robotics|Robotics|./Robotics) echo "Robotics Tech Radar" ;;
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

  {
    echo "<html>"
    echo "<head>"
    echo '<meta charset="UTF-8">'
    echo '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">'
    echo '<meta http-equiv="Pragma" content="no-cache">'
    echo '<meta http-equiv="Expires" content="0">'
    local page_title
    page_title="$(_dir_title "$dir")"
    echo "<title>$page_title</title>"
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
    echo "<body><h2>$page_title</h2>"

    # Podcast link for techradar directories
    if [[ -f "$dir/podcast.rss" ]]; then
      local podcast_url
      podcast_url="https://keithfry.github.io/web-pages/$(echo "$dir" | sed 's|^\./||')/podcast.rss"
      echo '<style>'
      echo '.podcast-bar{display:flex;align-items:center;gap:10px;margin:8px 0 24px;font-family:sans-serif;}'
      echo '.podcast-bar a{color:#d4561d;font-weight:bold;text-decoration:none;}'
      echo '.podcast-bar a:hover{text-decoration:underline;}'
      echo '.copy-btn{background:#d4561d;color:#fff;border:none;border-radius:4px;padding:4px 10px;cursor:pointer;font-size:0.85em;}'
      echo '.copy-btn:active{opacity:0.7;}'
      echo '</style>'
      echo "<div class=\"podcast-bar\">"
      echo "  &#127897; <a href=\"./podcast.rss\" id=\"podcast-link\">Podcast RSS Feed</a>"
      echo "  <button class=\"copy-btn\" onclick=\"(function(){var url='${podcast_url}';navigator.clipboard.writeText(url).then(function(){var b=document.querySelector('.copy-btn');var orig=b.textContent;b.textContent='Copied!';setTimeout(function(){b.textContent=orig;},1500);});})();\">Copy URL</button>"
      echo "</div>"
    fi

    # Sort files by date (latest first), then group by month
    printf '%s\n' "${files_list[@]}" | sort -t'|' -k2 -r | {
      current_month=""
      while IFS='|' read -r month_key date month_label fname; do
        if [[ "$month_key" != "$current_month" ]]; then
          # Close previous month's list if any
          [[ -n "$current_month" ]] && echo "</ul>"

          # Start new month section
          echo "<h2>$month_label</h2>"
          echo "<ul>"
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

    echo "</body></html>"
  } > "$index"
}

# Walk every target directory and subdirectory
for base in "${TARGET_DIRS[@]}"; do
  find "$base" -type d | while read dir; do
    generate_index "$dir"
  done
done
