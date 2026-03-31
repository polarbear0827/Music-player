import pytest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogs.music import is_spotify_url, get_track_info_from_spotify

def test_is_spotify_url():
    valid_track = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT?si=123"
    valid_album = "https://open.spotify.com/album/0eYZtVRBgZDpEibSKVri8P?si=123"
    valid_playlist = "https://open.spotify.com/playlist/37i9dQZF1E36g57M77uXtz"
    invalid = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    assert is_spotify_url(valid_track) is True
    assert is_spotify_url(valid_album) is True
    assert is_spotify_url(valid_playlist) is True
    assert is_spotify_url(invalid) is False

@patch('cogs.music.sp')
def test_get_track_info_from_spotify_track(mock_sp):
    # Mocking spotipy track response
    mock_track_data = {
        'name': 'Never Gonna Give You Up',
        'artists': [{'name': 'Rick Astley'}]
    }
    mock_sp.track.return_value = mock_track_data
    
    url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
    result = get_track_info_from_spotify(url)
    
    assert result == ["Rick Astley - Never Gonna Give You Up"]
    mock_sp.track.assert_called_once_with("4cOdK2wGLETKBW3PvgPWqT")

@patch('cogs.music.sp')
def test_get_track_info_from_spotify_album(mock_sp):
    # Mocking spotipy album response
    mock_album_data = {
        'items': [
            {'name': 'Idol', 'artists': [{'name': 'YOASOBI'}]},
            {'name': 'Seventeen', 'artists': [{'name': 'YOASOBI'}]}
        ]
    }
    mock_sp.album_tracks.return_value = mock_album_data
    
    url = "https://open.spotify.com/album/0eYZtVRBgZDpEibSKVri8P"
    result = get_track_info_from_spotify(url)
    
    assert result == ["YOASOBI - Idol", "YOASOBI - Seventeen"]
    mock_sp.album_tracks.assert_called_once_with("0eYZtVRBgZDpEibSKVri8P")
