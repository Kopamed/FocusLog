# FocusLog

An open-source time-tracking daemon for Linux that automatically captures screenshots every 15 seconds, classifies them using OpenAI's vision API, and stores everything in a SQLite database.

## Features

- 🖥️ **Automatic Screenshot Capture**: Uses `grim` for Wayland screenshot capture every 15 seconds
- 🤖 **AI Classification**: Sends screenshots to OpenAI for intelligent activity classification
- 💾 **SQLite Storage**: Stores both screenshots and classifications in a local database
- ⚙️ **Customizable**: Configure capture interval, classification prompts, and OpenAI models
- 🔒 **Privacy-First**: All data stored locally; OpenAI API calls are the only external communication

## Requirements

### System Requirements

- Linux with Wayland (for `grim` screenshot utility)
- Python 3.8+

### Installation

1. **Install system dependencies** (grim for screenshots):

   ```bash
   # Debian/Ubuntu
   sudo apt install grim

   # Arch Linux
   sudo pacman -S grim

   # Fedora
   sudo dnf install grim
   ```

2. **Install Python dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up OpenAI API key**:

   ```bash
   export OPENAI_API_KEY='your-api-key-here'
   ```

   Or create a `.env` file:

   ```
   OPENAI_API_KEY=your-api-key-here
   ```

## Usage

### Basic Usage

Run the daemon with default settings (15-second intervals):

```bash
python -m focuslogd.daemon
```

Or directly:

```bash
python src/focuslogd/daemon.py
```

### Command-Line Options

```bash
python src/focuslogd/daemon.py [OPTIONS]

Options:
  -i, --interval SECONDS      Screenshot capture interval (default: 15)
  -d, --database PATH         SQLite database file path (default: focuslog.db)
  -k, --api-key KEY          OpenAI API key (or use OPENAI_API_KEY env var)
  -m, --model MODEL          OpenAI model to use (default: gpt-4o-mini)
  -p, --prompt-file PATH     Custom classification prompt file
  -h, --help                 Show help message
```

### Examples

**30-second intervals with custom database location:**

```bash
python src/focuslogd/daemon.py -i 30 -d ~/my-focuslog.db
```

**Using a custom classification prompt:**

```bash
python src/focuslogd/daemon.py -p my_prompt.txt
```

**Using a different OpenAI model:**

```bash
python src/focuslogd/daemon.py -m gpt-4o
```

### Custom Classification Prompts

You can customize how screenshots are classified by providing your own prompt. Create a text file (e.g., `my_prompt.txt`) with your classification instructions:

```
Analyze this screenshot and determine if the user is:
1. Writing code
2. In a meeting
3. Browsing social media
4. Other activity

Respond with the category and confidence level.
```

Then run:

```bash
python src/focuslogd/daemon.py -p my_prompt.txt
```

A default prompt is provided in `classification_prompt.txt` which you can modify.

## Viewing Captured Data

Use the included utilities to view database statistics and recent captures:

### View Recent Captures

```bash
python view_logs.py

# Show only statistics
python view_logs.py --stats-only

# Show last 20 captures
python view_logs.py -n 20

# Use custom database location
python view_logs.py -d ~/my-focuslog.db
```

### View All Labels

```bash
python view_labels.py

# Show labels with usage counts
python view_labels.py -d ~/my-focuslog.db
```

### View Summaries

```bash
python view_summaries.py

# Show only 5-minute summaries
python view_summaries.py -t 5min

# Show only hourly summaries
python view_summaries.py -t hourly

# Show last 20 summaries
python view_summaries.py -n 20
```

## Web Dashboard

Launch the interactive web dashboard for rich visualizations:

```bash
./run_dashboard.sh
# or
python src/dashboard/app.py
```

Then open **http://localhost:5000** in your browser.

### Dashboard Features

- **📊 Real-time Stats** - Total captures, labels, database size
- **⏱️ Time by Label** - Bar chart showing hours spent per activity
- **🥧 Label Distribution** - Pie chart of activity breakdown
- **📈 Activity Timeline** - Stacked hourly view of all labels
- **🔥 Activity Heatmap** - 7-day hourly heatmap showing when you're active
- **📝 Recent Summaries** - Latest 5-min and hourly summaries
- **📸 Recent Captures** - Latest screenshots with labels and descriptions
- **📅 Date Range Filters** - View stats for today, last 24h, last 7 days, or custom range
- **🔄 Auto-refresh** - Updates every 30 seconds

## Database Schema

The SQLite database uses multiple tables for flexible activity tracking:

### `captures` table

| Column               | Type     | Description                            |
| -------------------- | -------- | -------------------------------------- |
| id                   | INTEGER  | Primary key                            |
| timestamp            | DATETIME | When the screenshot was taken          |
| screenshot           | BLOB     | PNG image data                         |
| description          | TEXT     | Detailed description of activity       |
| classification_raw   | TEXT     | Full JSON response from OpenAI API     |
| classification_error | TEXT     | Error message if classification failed |
| created_at           | DATETIME | When the record was created            |

### `labels` table

| Column     | Type     | Description                            |
| ---------- | -------- | -------------------------------------- |
| id         | INTEGER  | Primary key                            |
| name       | TEXT     | Label name (e.g., "coding", "meeting") |
| created_at | DATETIME | When label was first created           |
| last_used  | DATETIME | Last time this label was used          |

### `captures_labels` junction table

Links captures to labels (many-to-many relationship - one capture can have multiple labels)

### `summaries` table

| Column       | Type     | Description                     |
| ------------ | -------- | ------------------------------- |
| id           | INTEGER  | Primary key                     |
| summary_type | TEXT     | Type: '5min', 'hourly', 'daily' |
| start_time   | DATETIME | Start of summary period         |
| end_time     | DATETIME | End of summary period           |
| content      | TEXT     | Summary content                 |
| created_at   | DATETIME | When summary was created        |

## Architecture

```
focuslogd/
├── capture/
│   ├── base.py          # Abstract capture strategy
│   └── grim.py          # Grim/Wayland implementation
├── classifier.py        # OpenAI classification logic
├── database.py          # SQLite storage layer
└── daemon.py            # Main service orchestration
```

## Cost Considerations

Using `gpt-4o-mini` with "low" detail setting for vision:

- Approximately **$0.001-0.002 per screenshot**
- At 15-second intervals: ~240 screenshots/hour = **$0.24-0.48/hour**
- 8-hour workday: **$2-4/day**

To reduce costs:

- Increase capture interval (`-i 30` for 30 seconds)
- Modify the classifier to use lower detail settings
- Process screenshots in batches during off-hours

## Privacy & Security

- **All screenshots stored locally** in SQLite database
- **No telemetry or external services** except OpenAI API calls
- **OpenAI API calls** send screenshots for classification
- Consider OpenAI's data usage policies for sensitive information
- Database file can be encrypted at rest using disk encryption

## Automatic Summaries

FocusLog automatically generates hierarchical summaries:

### 5-Minute Summaries

- Generated every 5 minutes
- Aggregates ~20 screenshots (at 15-second intervals)
- Identifies main activities and transitions
- Provides context for the next classification

### Hourly Summaries

- Generated every hour
- Aggregates 12 x 5-minute summaries
- Shows productivity patterns and focus areas
- Highlights significant transitions and insights

All summaries are stored in the database and can be viewed with `python view_summaries.py`.

## Future Enhancements

Future versions could include:

- [ ] Daily summaries (aggregating hourly summaries)
- [ ] Weekly/monthly analytics and trends
- [ ] Batch processing for end-of-day classification (50% cost reduction)
- [ ] Application window detection and tracking
- [ ] Web UI for browsing captures and statistics
- [ ] Export to various formats (JSON, CSV, etc.)
- [ ] Integration with other productivity tools
- [ ] Local classification models (no API costs)
- [ ] Support for X11 screenshot capture

## Troubleshooting

**"grim is not installed"**

- Install grim: `sudo apt install grim` (or equivalent for your distro)
- Ensure you're running Wayland, not X11

**"OpenAI API key not provided"**

- Set the `OPENAI_API_KEY` environment variable
- Or pass it with `-k` flag

**Screenshots are large**

- Screenshots are stored as PNG blobs in the database
- Use the `get_statistics()` method to monitor database size
- Consider implementing cleanup policies for old captures

## License

See LICENSE file for details.

## Contributing

Contributions welcome! This project is in early development and the classification system is intentionally kept as a placeholder for customization.
