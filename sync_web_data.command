#!/bin/bash
set -e

cd "$(dirname "$0")"
cp "Noongar categories.csv" "web/Noongar categories.csv"
echo "Web app dictionary data updated."
