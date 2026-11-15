#!/usr/bin/env bash
# Tải font mã nguồn mở (OFL/Apache, có tiếng Việt) vào thư mục này cho libass khi xuất video trên server
# Linux không có font hệ thống. Chạy một lần: bash fonts/tai-font-xuat-video.sh
set -euo pipefail
cd "$(dirname "$0")"
GF=https://github.com/google/fonts/raw/main
tai() { [[ -s "$2" ]] || curl -fsSL --retry 3 -o "$2" "$1"; }
tai "$GF/ofl/bevietnampro/BeVietnamPro-Regular.ttf" BeVietnamPro-Regular.ttf
tai "$GF/ofl/bevietnampro/BeVietnamPro-Bold.ttf" BeVietnamPro-Bold.ttf
tai "$GF/ofl/bevietnampro/BeVietnamPro-Italic.ttf" BeVietnamPro-Italic.ttf
tai "$GF/ofl/montserrat/Montserrat%5Bwght%5D.ttf" Montserrat.ttf
tai "$GF/ofl/roboto/Roboto%5Bwdth,wght%5D.ttf" Roboto.ttf
if ! ls LiberationSans-Regular.ttf >/dev/null 2>&1; then
    tai https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz lib.tgz
    tar -xzf lib.tgz --strip-components=1 --wildcards '*/LiberationSans-*.ttf' '*/LiberationSerif-*.ttf'
    rm -f lib.tgz
fi
if ! ls DejaVuSans.ttf >/dev/null 2>&1; then
    tai https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2 dv.tbz
    tar -xjf dv.tbz --strip-components=2 --wildcards '*/ttf/DejaVuSans.ttf' '*/ttf/DejaVuSans-Bold.ttf'
    rm -f dv.tbz
fi
ls -la *.ttf
