#!/bin/bash
# Install ffmpeg for video generation

echo "Installing ffmpeg..."

if [ -f /etc/os-release ]; then
    . /etc/os-release
    case $ID in
        ubuntu|debian)
            sudo apt update
            sudo apt install -y ffmpeg
            ;;
        fedora|rhel|centos)
            sudo dnf install -y ffmpeg
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm ffmpeg
            ;;
        *)
            echo "Unsupported distribution: $ID"
            echo "Please install ffmpeg manually"
            exit 1
            ;;
    esac
else
    echo "Cannot detect OS. Please install ffmpeg manually:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  Fedora: sudo dnf install ffmpeg"
    echo "  Arch: sudo pacman -S ffmpeg"
    exit 1
fi

echo "✓ ffmpeg installed successfully"
echo ""
echo "Now run the migration script to add video support to existing database:"
echo "  python3 add_video_column.py"
