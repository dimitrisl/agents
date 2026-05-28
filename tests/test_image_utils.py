import os
from backend.utils.image_utils import save_custom_portrait, PORTRAIT_DIR


def test_save_custom_portrait():
    # Setup test dir
    test_filename = "test_portrait_123.png"
    test_filepath = os.path.join(PORTRAIT_DIR, test_filename)

    # Ensure clean state
    if os.path.exists(test_filepath):
        os.remove(test_filepath)

    image_bytes = b"fake_png_data"
    saved_path = save_custom_portrait(image_bytes, test_filename)

    assert saved_path == test_filepath
    assert os.path.exists(test_filepath)
    with open(test_filepath, "rb") as f:
        assert f.read() == image_bytes

    # Cleanup
    if os.path.exists(test_filepath):
        os.remove(test_filepath)
