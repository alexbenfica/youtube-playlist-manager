#!/usr/bin/env python3
"""YouTube Utils - Playlist Importer

Main CLI entry point for YouTube utilities including playlist import from URLs.
"""

import argparse
import os
import re
import sys
from typing import List, Tuple, Optional
from urllib.parse import urlparse, parse_qs

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# YouTube API scopes - read/write access for playlists
SCOPES = ['https://www.googleapis.com/auth/youtube']

# Token storage
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract video ID from various YouTube URL formats.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID

    Args:
        url: YouTube URL string

    Returns:
        Video ID string or None if invalid
    """
    url = url.strip()
    if not url:
        return None

    # Pattern 1: youtu.be/VIDEO_ID
    if 'youtu.be/' in url:
        match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url)
        if match:
            return match.group(1)

    # Pattern 2: youtube.com with v parameter
    if 'youtube.com' in url:
        parsed = urlparse(url)

        # Check for v parameter in query string
        if parsed.query:
            params = parse_qs(parsed.query)
            if 'v' in params and params['v']:
                video_id = params['v'][0]
                if len(video_id) == 11:
                    return video_id

        # Pattern 3: /embed/VIDEO_ID or /v/VIDEO_ID
        match = re.search(r'/(embed|v)/([a-zA-Z0-9_-]{11})', url)
        if match:
            return match.group(2)

    # If it looks like a video ID by itself
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url

    return None


def authenticate_youtube() -> object:
    """
    Authenticate with YouTube Data API v3 using OAuth 2.0.

    Returns:
        YouTube API service object

    Raises:
        FileNotFoundError: If credentials.json is not found
        Exception: For authentication errors
    """
    creds = None

    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' not found. Please download it from Google Cloud Console.\n"
                    "See README.md for instructions."
                )
            print("Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print("Authentication successful!")

    return build('youtube', 'v3', credentials=creds)


def get_channel_info(youtube):
    """
    Get information about the authenticated user's channel.

    Args:
        youtube: YouTube API service object

    Returns:
        Channel info dict or None if failed
    """
    try:
        request = youtube.channels().list(
            part="snippet",
            mine=True
        )
        response = request.execute()
        if response.get('items'):
            channel = response['items'][0]
            return {
                'title': channel['snippet']['title'],
                'id': channel['id'],
                'description': channel['snippet'].get('description', '')
            }
    except HttpError as e:
        print(f"  ⚠ Failed to get channel info: {e}")
    return None


def get_watch_later_playlist_id(youtube):
    """
    Get the actual Watch Later playlist ID for the authenticated user.

    Args:
        youtube: YouTube API service object

    Returns:
        Playlist ID string or None if not found
    """
    try:
        print("  Searching for Watch Later playlist...")
        request = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50
        )
        response = request.execute()

        print(f"  Found {len(response.get('items', []))} playlists:")
        for playlist in response.get('items', []):
            title = playlist['snippet']['title']
            pid = playlist['id']
            print(f"    - {title} (ID: {pid})")
            # Check for various possible Watch Later names
            watch_later_names = ['Watch Later', 'Assistir mais tarde', 'Ver más tarde', 'Watch later', 'WL']
            if title in watch_later_names or pid == 'WL':
                return pid

        # If not found in first page, check if there are more pages
        next_page_token = response.get('nextPageToken')
        while next_page_token:
            request = youtube.playlists().list(
                part="snippet",
                mine=True,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()

            for playlist in response.get('items', []):
                title = playlist['snippet']['title']
                pid = playlist['id']
                print(f"    - {title} (ID: {pid})")
                # Check for various possible Watch Later names
                watch_later_names = ['Watch Later', 'Assistir mais tarde', 'Ver más tarde', 'Watch later', 'WL']
                if title in watch_later_names or pid == 'WL':
                    return pid

            next_page_token = response.get('nextPageToken')

    except HttpError as e:
        print(f"  ⚠ Failed to get playlists: {e}")
    return None
def create_playlist(youtube, title: str, description: str = "", privacy_status: str = "unlisted") -> Tuple[str, str]:
    """
    Create a new YouTube playlist.

    Args:
        youtube: YouTube API service object
        title: Playlist title
        description: Playlist description
        privacy_status: 'public', 'private', or 'unlisted'

    Returns:
        Tuple of (playlist_id, playlist_url)

    Raises:
        HttpError: If playlist creation fails
    """
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }
    )

    try:
        response = request.execute()
        playlist_id = response['id']
        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

        return playlist_id, playlist_url
    except HttpError as e:
        status_code = e.resp.status if hasattr(e.resp, 'status') else 'unknown'
        error_reason = e.error_details[0].get('reason', 'unknown') if e.error_details else 'unknown'

        if status_code == 403:
            raise HttpError(e.resp, e.content, f"Failed to create playlist: API Error 403 - Insufficient permissions. Error reason: {error_reason}. Check OAuth scopes.")
        else:
            raise HttpError(e.resp, e.content, f"Failed to create playlist: {error_reason}")


def add_video_to_playlist(youtube, playlist_id: str, video_id: str) -> bool:
    """
    Add a video to a playlist.

    Args:
        youtube: YouTube API service object
        playlist_id: Target playlist ID
        video_id: Video ID to add

    Returns:
        True if successful, False otherwise
    """
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        ).execute()
        return True
    except HttpError as e:
        status_code = e.resp.status if hasattr(e.resp, 'status') else 'unknown'
        error_reason = e.error_details[0].get('reason', 'unknown') if e.error_details else 'unknown'

        if status_code == 403:
            print(f"  ✗ Failed to add video {video_id}: API Error 403 - Insufficient permissions")
            print(f"    Error reason: {error_reason}")
            print(f"    This usually means the OAuth scope is insufficient for playlist modifications.")
        else:
            print(f"  ✗ Failed to add video {video_id}: {error_reason}")
        return False


def read_video_urls(file_path: str) -> List[str]:
    """
    Read video URLs from a text file.

    Args:
        file_path: Path to text file with one URL per line

    Returns:
        List of URL strings

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    return lines


def get_watch_later_videos(youtube) -> List[str]:
    """
    Fetch all video IDs from the Watch Later playlist.

    Args:
        youtube: YouTube API service object

    Returns:
        List of video IDs

    Raises:
        HttpError: If fetching fails
    """
    video_ids = []
    next_page_token = None

    # First try to get the actual Watch Later playlist ID
    watch_later_id = get_watch_later_playlist_id(youtube)
    if watch_later_id:
        print(f"  Found Watch Later playlist ID: {watch_later_id}")
        playlist_id = watch_later_id
    else:
        print(f"  Using default Watch Later ID: WL")
        playlist_id = "WL"

    try:
        while True:
            request = youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()

            print(response)

            for item in response.get('items', []):
                video_id = item['snippet']['resourceId']['videoId']
                video_ids.append(video_id)

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

    except HttpError as e:
        status_code = e.resp.status if hasattr(e.resp, 'status') else 'unknown'
        error_message = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)
        error_reason = e.error_details[0].get('reason', 'unknown') if e.error_details else 'unknown'

        if status_code == 403:
            print(f"  ✗ API Error 403: Insufficient permissions")
            print(f"    Error reason: {error_reason}")
            print(f"    This usually means the OAuth scope is insufficient.")
            print(f"    Current scopes: {SCOPES}")
            print(f"    Try deleting token.json and re-authenticating.")
        else:
            print(f"  ✗ API Error {status_code}: {error_reason}")
            print(f"    Response: {error_message}")

        raise HttpError(e.resp, e.content, f"Failed to fetch Watch Later videos: {error_reason}")

    return video_ids


def playlist_from_url(args):
    """
    Command: Import videos from a text file into a new YouTube playlist.

    Args:
        args: Parsed command-line arguments
    """
    input_file = args.file
    playlist_title = args.title
    playlist_description = args.description
    privacy_status = args.privacy

    print(f"YouTube Playlist Importer")
    print(f"{'=' * 50}")
    print(f"Input file: {input_file}")
    print(f"Playlist title: {playlist_title}")
    print(f"Privacy: {privacy_status}")
    print()

    # Step 1: Read URLs from file
    try:
        urls = read_video_urls(input_file)
        print(f"✓ Read {len(urls)} URLs from file")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

    if not urls:
        print("✗ Error: No URLs found in file")
        sys.exit(1)

    # Step 2: Extract video IDs
    video_ids = []
    invalid_urls = []

    for url in urls:
        video_id = extract_video_id(url)
        if video_id:
            video_ids.append(video_id)
        else:
            invalid_urls.append(url)

    print(f"✓ Extracted {len(video_ids)} valid video IDs")
    if invalid_urls:
        print(f"⚠ Skipped {len(invalid_urls)} invalid URLs")
    print()

    if not video_ids:
        print("✗ Error: No valid video IDs found")
        sys.exit(1)

    # Step 3: Authenticate with YouTube
    try:
        youtube = authenticate_youtube()
        print("✓ Authenticated with YouTube API")

        # Get and display channel info
        channel_info = get_channel_info(youtube)
        if channel_info:
            print(f"  Authenticated as: {channel_info['title']} (Channel ID: {channel_info['id']})")
        print()
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Authentication error: {e}")
        sys.exit(1)

    # Step 4: Create playlist
    try:
        playlist_id, playlist_url = create_playlist(
            youtube,
            playlist_title,
            playlist_description,
            privacy_status
        )
        print(f"✓ Created playlist: {playlist_title}")
        print(f"  Playlist ID: {playlist_id}")
        print(f"  Playlist URL: {playlist_url}")
        print()
    except HttpError as e:
        print(f"✗ Failed to create playlist: {e}")
        sys.exit(1)

    # Step 5: Add videos to playlist
    print(f"Adding videos to playlist...")
    added_count = 0
    skipped_count = 0

    for i, video_id in enumerate(video_ids, 1):
        print(f"  [{i}/{len(video_ids)}] Adding video {video_id}...", end=" ")
        if add_video_to_playlist(youtube, playlist_id, video_id):
            print("✓")
            added_count += 1
        else:
            print()
            skipped_count += 1

    # Step 6: Print summary
    print()
    print(f"{'=' * 50}")
    print(f"Summary:")
    print(f"  Playlist URL: {playlist_url}")
    print(f"  Playlist ID: {playlist_id}")
    print(f"  Total added: {added_count}")
    print(f"  Total skipped: {skipped_count} (invalid or deleted videos)")
    print(f"{'=' * 50}")


def playlist_from_playlist_url(args):
    """
    Command: Import videos from a public YouTube playlist URL into a new playlist.

    Args:
        args: Parsed command-line arguments
    """
    playlist_url = args.url
    new_playlist_title = args.title
    playlist_description = args.description
    privacy_status = args.privacy

    print(f"YouTube Playlist Importer from URL")
    print(f"{'=' * 50}")
    print(f"Source playlist URL: {playlist_url}")
    print(f"New playlist title: {new_playlist_title}")
    print(f"Privacy: {privacy_status}")
    print()

    # Extract playlist ID from URL
    playlist_id_match = re.search(r'list=([A-Za-z0-9_-]+)', playlist_url)
    if not playlist_id_match:
        print("✗ Error: Invalid playlist URL")
        sys.exit(1)

    source_playlist_id = playlist_id_match.group(1)
    print(f"✓ Extracted playlist ID: {source_playlist_id}")
    print()

    # Step 1: Authenticate with YouTube
    try:
        youtube = authenticate_youtube()
        print("✓ Authenticated with YouTube API")

        # Get and display channel info
        channel_info = get_channel_info(youtube)
        if channel_info:
            print(f"  Authenticated as: {channel_info['title']} (Channel ID: {channel_info['id']})")
        print()
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Authentication error: {e}")
        sys.exit(1)

    # Step 2: Fetch videos from source playlist
    print(f"Fetching videos from source playlist...")
    try:
        video_ids = []
        next_page_token = None

        while True:
            request = youtube.playlistItems().list(
                part="snippet",
                playlistId=source_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response.get('items', []):
                video_id = item['snippet']['resourceId']['videoId']
                video_ids.append(video_id)

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

        print(f"✓ Found {len(video_ids)} videos in source playlist")
        print()
    except HttpError as e:
        status_code = e.resp.status if hasattr(e.resp, 'status') else 'unknown'
        error_message = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)
        error_reason = e.error_details[0].get('reason', 'unknown') if e.error_details else 'unknown'

        if status_code == 403:
            print(f"  ✗ API Error 403: Cannot access playlist. Make sure it's public.")
            print(f"    Error reason: {error_reason}")
        else:
            print(f"  ✗ API Error {status_code}: {error_reason}")
        sys.exit(1)

    if not video_ids:
        print("✗ Error: No videos found in source playlist")
        sys.exit(1)

    # Step 3: Create new playlist
    try:
        new_playlist_id, new_playlist_url = create_playlist(
            youtube,
            new_playlist_title,
            playlist_description,
            privacy_status
        )
        print(f"✓ Created playlist: {new_playlist_title}")
        print(f"  Playlist ID: {new_playlist_id}")
        print(f"  Playlist URL: {new_playlist_url}")
        print()
    except HttpError as e:
        print(f"✗ Failed to create playlist: {e}")
        sys.exit(1)

    # Step 4: Add videos to new playlist
    print(f"Copying videos to new playlist...")
    added_count = 0
    skipped_count = 0

    for i, video_id in enumerate(video_ids, 1):
        print(f"  [{i}/{len(video_ids)}] Adding video {video_id}...", end=" ")
        if add_video_to_playlist(youtube, new_playlist_id, video_id):
            print("✓")
            added_count += 1
        else:
            print()
            skipped_count += 1

    # Step 5: Print summary
    print()
    print(f"{'=' * 50}")
    print(f"Summary:")
    print(f"  Source playlist: {playlist_url}")
    print(f"  New playlist URL: {new_playlist_url}")
    print(f"  New playlist ID: {new_playlist_id}")
    print(f"  Total copied: {added_count}")
    print(f"  Total skipped: {skipped_count} (invalid or deleted videos)")
    print(f"{'=' * 50}")
    """
    Command: Duplicate Watch Later playlist into a new playlist.

    Args:
        args: Parsed command-line arguments
    """
    playlist_title = args.title
    playlist_description = args.description
    privacy_status = args.privacy

    print(f"YouTube Watch Later Duplicator")
    print(f"{'=' * 50}")
    print(f"Playlist title: {playlist_title}")
    print(f"Privacy: {privacy_status}")
    print()

    # Step 1: Authenticate with YouTube
    try:
        youtube = authenticate_youtube()
        print("✓ Authenticated with YouTube API")

        # Get and display channel info
        channel_info = get_channel_info(youtube)
        if channel_info:
            print(f"  Authenticated as: {channel_info['title']} (Channel ID: {channel_info['id']})")
        print()
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Authentication error: {e}")
        sys.exit(1)

    # Step 2: Fetch Watch Later videos
    watch_later_url = "https://www.youtube.com/playlist?list=WL"
    print(f"Fetching videos from Watch Later...")
    print(f"  Watch Later URL: {watch_later_url}")
    try:
        video_ids = get_watch_later_videos(youtube)
        print(f"✓ Found {len(video_ids)} videos in Watch Later")
        print()
    except HttpError as e:
        print(f"✗ Failed to fetch Watch Later videos: {e}")
        sys.exit(1)

    if not video_ids:
        print("✗ Error: No videos found in Watch Later playlist")
        print()
        print("This might be due to API limitations or account settings.")
        print("As an alternative, you can manually export your Watch Later videos:")
        print("1. Go to https://www.youtube.com/playlist?list=WL")
        print("2. Click the three dots (...) next to a video")
        print("3. Select 'Save to playlist' and create a new public playlist")
        print("4. Then use: python -m src.playlist_importer.main playlist-from-url --file exported_urls.txt")
        print("   (where exported_urls.txt contains the video URLs)")
        sys.exit(1)

    # Step 3: Create new playlist
    try:
        playlist_id, playlist_url = create_playlist(
            youtube,
            playlist_title,
            playlist_description,
            privacy_status
        )
        print(f"✓ Created playlist: {playlist_title}")
        print(f"  Playlist ID: {playlist_id}")
        print(f"  Playlist URL: {playlist_url}")
        print()
    except HttpError as e:
        print(f"✗ Failed to create playlist: {e}")
        sys.exit(1)

    # Step 4: Add videos to new playlist
    print(f"Duplicating videos to new playlist...")
    added_count = 0
    skipped_count = 0

    for i, video_id in enumerate(video_ids, 1):
        print(f"  [{i}/{len(video_ids)}] Adding video {video_id}...", end=" ")
        if add_video_to_playlist(youtube, playlist_id, video_id):
            print("✓")
            added_count += 1
        else:
            print()
            skipped_count += 1

    # Step 5: Print summary
    print()
    print(f"{'=' * 50}")
    print(f"Summary:")
    print(f"  Playlist URL: {playlist_url}")
    print(f"  Playlist ID: {playlist_id}")
    print(f"  Total added: {added_count}")
    print(f"  Total skipped: {skipped_count} (invalid or deleted videos)")
    print(f"{'=' * 50}")


def duplicate_watch_later(args):
    """
    Command: Duplicate Watch Later playlist into a new playlist.

    Args:
        args: Parsed command-line arguments
    """
    playlist_title = args.title
    playlist_description = args.description
    privacy_status = args.privacy

    print(f"YouTube Watch Later Duplicator")
    print(f"{'=' * 50}")
    print(f"Playlist title: {playlist_title}")
    print(f"Privacy: {privacy_status}")
    print()

    # Step 1: Authenticate with YouTube
    try:
        youtube = authenticate_youtube()
        print("✓ Authenticated with YouTube API")

        # Get and display channel info
        channel_info = get_channel_info(youtube)
        if channel_info:
            print(f"  Authenticated as: {channel_info['title']} (Channel ID: {channel_info['id']})")
        print()
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Authentication error: {e}")
        sys.exit(1)

    # Step 2: Fetch Watch Later videos
    watch_later_url = "https://www.youtube.com/playlist?list=WL"
    print(f"Fetching videos from Watch Later...")
    print(f"  Watch Later URL: {watch_later_url}")
    try:
        video_ids = get_watch_later_videos(youtube)
        print(f"✓ Found {len(video_ids)} videos in Watch Later")
        print()
    except HttpError as e:
        print(f"✗ Failed to fetch Watch Later videos: {e}")
        sys.exit(1)

    if not video_ids:
        print("✗ Error: No videos found in Watch Later playlist")
        print()
        print("This might be due to API limitations or account settings.")
        print("As an alternative, you can manually export your Watch Later videos:")
        print("1. Go to https://www.youtube.com/playlist?list=WL")
        print("2. Click the three dots (...) next to a video")
        print("3. Select 'Save to playlist' and create a new public playlist")
        print("4. Then use: python -m src.playlist_importer.main playlist-from-playlist-url [PLAYLIST_URL]")
        sys.exit(1)

    # Step 3: Create new playlist
    try:
        playlist_id, playlist_url = create_playlist(
            youtube,
            playlist_title,
            playlist_description,
            privacy_status
        )
        print(f"✓ Created playlist: {playlist_title}")
        print(f"  Playlist ID: {playlist_id}")
        print(f"  Playlist URL: {playlist_url}")
        print()
    except HttpError as e:
        print(f"✗ Failed to create playlist: {e}")
        sys.exit(1)

    # Step 4: Add videos to new playlist
    print(f"Duplicating videos to new playlist...")
    added_count = 0
    skipped_count = 0

    for i, video_id in enumerate(video_ids, 1):
        print(f"  [{i}/{len(video_ids)}] Adding video {video_id}...", end=" ")
        if add_video_to_playlist(youtube, playlist_id, video_id):
            print("✓")
            added_count += 1
        else:
            print()
            skipped_count += 1

    # Step 5: Print summary
    print()
    print(f"{'=' * 50}")
    print(f"Summary:")
    print(f"  Playlist URL: {playlist_url}")
    print(f"  Playlist ID: {playlist_id}")
    print(f"  Total added: {added_count}")
    print(f"  Total skipped: {skipped_count} (invalid or deleted videos)")
    print(f"{'=' * 50}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='playlist-import',
        description='YouTube utilities for playlist management and video operations',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Subcommand: playlist-from-url
    playlist_parser = subparsers.add_parser(
        'playlist-from-url',
        help='Create a playlist from a text file containing YouTube URLs'
    )
    playlist_parser.add_argument(
        'file',
        help='Path to text file with one YouTube URL per line'
    )
    playlist_parser.add_argument(
        '--title',
        default='Imported Playlist',
        help='Title for the new playlist (default: "Imported Playlist")'
    )
    playlist_parser.add_argument(
        '--description',
        default='Playlist created with youtube-utils',
        help='Description for the new playlist (default: "Playlist created with youtube-utils")'
    )
    playlist_parser.add_argument(
        '--privacy',
        choices=['public', 'private', 'unlisted'],
        default='unlisted',
        help='Privacy status for the playlist (default: unlisted)'
    )
    playlist_parser.set_defaults(func=playlist_from_url)

    # Subcommand: playlist-from-playlist-url
    playlist_url_parser = subparsers.add_parser(
        'playlist-from-playlist-url',
        help='Copy videos from a public playlist URL to a new playlist'
    )
    playlist_url_parser.add_argument(
        'url',
        help='URL of the public playlist to copy from'
    )
    playlist_url_parser.add_argument(
        '--title',
        default='Copied Playlist',
        help='Title for the new playlist (default: "Copied Playlist")'
    )
    playlist_url_parser.add_argument(
        '--description',
        default='Playlist copied with youtube-utils',
        help='Description for the new playlist (default: "Playlist copied with youtube-utils")'
    )
    playlist_url_parser.add_argument(
        '--privacy',
        choices=['public', 'private', 'unlisted'],
        default='unlisted',
        help='Privacy status for the playlist (default: unlisted)'
    )
    playlist_url_parser.set_defaults(func=playlist_from_playlist_url)

    # Subcommand: duplicate-watch-later
    watch_later_parser = subparsers.add_parser(
        'duplicate-watch-later',
        help='Duplicate your Watch Later playlist into a new playlist'
    )
    watch_later_parser.add_argument(
        '--title',
        default='Watch Later Backup',
        help='Title for the new playlist (default: "Watch Later Backup")'
    )
    watch_later_parser.add_argument(
        '--description',
        default='Backup of Watch Later playlist created with youtube-utils',
        help='Description for the new playlist (default: "Backup of Watch Later playlist created with youtube-utils")'
    )
    watch_later_parser.add_argument(
        '--privacy',
        choices=['public', 'private', 'unlisted'],
        default='unlisted',
        help='Privacy status for the playlist (default: unlisted)'
    )
    watch_later_parser.set_defaults(func=duplicate_watch_later)

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
