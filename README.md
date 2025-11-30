# YouTube Utils

A Python tool for YouTube playlist management and video operations. Currently supports importing videos from a text file into a new YouTube playlist.

## Features

- **Playlist Import**: Create a playlist from a text file containing YouTube URLs
- **Watch Later Backup**: Duplicate your Watch Later playlist into a new playlist
- Supports all YouTube URL formats (youtube.com, youtu.be, embed, etc.)
- OAuth 2.0 authentication with YouTube Data API v3
- Configurable playlist privacy (public, private, unlisted)
- Default unlisted privacy for all playlists
- Automatic error handling for invalid or deleted videos
- Detailed progress reporting

## Prerequisites

1. **Python 3.8+**
2. **Poetry** - Install from [python-poetry.org](https://python-poetry.org/docs/#installation)
3. **YouTube Data API v3 credentials**

## Setup

### 1. Enable YouTube Data API v3

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** > **Library**
4. Search for "YouTube Data API v3"
5. Click **Enable**

### 2. Create OAuth 2.0 Credentials

1. In Google Cloud Console, go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - Choose "External" (unless you have a Google Workspace)
   - Fill in app name, user support email, and developer contact
   - Add scope: `https://www.googleapis.com/auth/youtube`
   - Add your email as a test user
4. For Application type, select **Desktop app**
5. Give it a name (e.g., "YouTube Utils")
6. Click **Create**
7. Download the credentials file

### 3. Place Credentials File

1. Rename the downloaded file to `credentials.json`
2. Place it in the project root directory:
   ```
   youtube_utils/
   ├── credentials.json  ← Place here
   ├── pyproject.toml
   ├── src/
   └── ...
   ```

### 4. Install Dependencies

```bash
cd youtube_utils
poetry install
```

This will install all required dependencies:
- `google-api-python-client` - YouTube Data API client
- `google-auth-oauthlib` - OAuth 2.0 authentication
- `google-auth-httplib2` - HTTP transport for authentication

## Usage

### First-Time Authentication

On your first run, the tool will open a browser window for OAuth authentication:

1. Sign in with your Google account
2. Grant permission to manage your YouTube account
3. The tool will save a `token.json` file for future use

### Command: playlist-from-url

Import videos from a text file into a new YouTube playlist.

**Basic usage:**
```bash
poetry run playlist-import playlist-from-url videos.txt
```

**With custom options:**
```bash
poetry run playlist-import playlist-from-url videos.txt \
  --title "My Awesome Playlist" \
  --description "A collection of great videos" \
  --privacy unlisted
```

**Arguments:**
- `file` - Path to text file with one YouTube URL per line (required)
- `--title` - Playlist title (default: "Imported Playlist")
- `--description` - Playlist description (default: "Playlist created with youtube-utils")
- `--privacy` - Privacy status: `public`, `private`, or `unlisted` (default: unlisted)

### Command: duplicate-watch-later

Duplicate your Watch Later playlist into a new playlist.

**Basic usage:**
```bash
poetry run playlist-import duplicate-watch-later
```

**With custom options:**
```bash
poetry run playlist-import duplicate-watch-later \
  --title "Watch Later Archive 2025" \
  --description "Archived watch later videos" \
  --privacy private
```

**Arguments:**
- `--title` - Playlist title (default: "Watch Later Backup")
- `--description` - Playlist description (default: "Backup of Watch Later playlist created with youtube-utils")
- `--privacy` - Privacy status: `public`, `private`, or `unlisted` (default: unlisted)

**Note:** This command fetches all videos from your Watch Later playlist and adds them to a new playlist. The original Watch Later playlist remains unchanged.

### Input File Format

Create a text file (e.g., `videos.txt`) with one YouTube URL per line:

```text
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/9bZkp7q19f0
https://www.youtube.com/watch?v=jNQXAC9IVRw
# Lines starting with # are ignored (comments)
https://www.youtube.com/embed/oHg5SJYRHA0
```

**Supported URL formats:**
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
- `https://www.youtube.com/v/VIDEO_ID`
- `https://m.youtube.com/watch?v=VIDEO_ID`
- Raw video ID: `VIDEO_ID`

### Example Output

```
YouTube Playlist Importer
==================================================
Input file: videos.txt
Playlist title: Imported Playlist
Privacy: unlisted

✓ Read 15 URLs from file
✓ Extracted 15 valid video IDs

✓ Authenticated with YouTube API

✓ Created playlist: Imported Playlist
  Playlist ID: PLxxxxxxxxxxxxxxxxxxxxxx
  Playlist URL: https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxx

Adding videos to playlist...
  [1/15] Adding video dQw4w9WgXcQ... ✓
  [2/15] Adding video 9bZkp7q19f0... ✓
  [3/15] Adding video jNQXAC9IVRw... ✓
  ...

==================================================
Summary:
  Playlist URL: https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxx
  Playlist ID: PLxxxxxxxxxxxxxxxxxxxxxx
  Total added: 13
  Total skipped: 2 (invalid or deleted videos)
==================================================
```

## Project Structure

```
youtube_utils/
├── credentials.json       # OAuth credentials (you provide)
├── token.json            # Generated after first auth
├── pyproject.toml        # Poetry configuration
├── README.md
├── videos.txt            # Your input file (you create)
└── src/
    └── playlist_importer/
        ├── __init__.py
        └── main.py       # Main implementation
```

## Troubleshooting

### "credentials.json not found"
- Make sure you've downloaded OAuth credentials from Google Cloud Console
- Rename the file to `credentials.json`
- Place it in the project root directory

### "Access Not Configured"
- Enable YouTube Data API v3 in Google Cloud Console
- Wait a few minutes for the API to activate

### "Invalid grant" or token errors
- Delete `token.json` and re-authenticate
- Make sure your OAuth consent screen includes the correct scope

### Videos being skipped
- Video may be deleted or private
- Video ID might be invalid
- You may not have permission to add certain videos

## API Quotas

YouTube Data API v3 has daily quota limits:
- Default quota: 10,000 units per day
- Creating a playlist: 50 units
- Adding a video: 50 units

With default quotas, you can add ~195 videos per day. For higher limits, request a quota increase in Google Cloud Console.

## Future Commands

This tool is designed to be extensible. Future commands may include:
- Video download utilities
- Playlist management (delete, update, merge)
- Channel statistics
- Subtitle extraction

## License

MIT

## Contributing

Contributions welcome! This is a work in progress with more features planned.
