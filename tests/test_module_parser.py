from unittest.mock import MagicMock, patch

import pytest

from backend.services.module_parser_service import ModuleParserService


@pytest.fixture
def mock_gemini_client():
    with patch("backend.services.module_parser_service.get_llm_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        # Mock file upload
        mock_provider.upload_file.return_value = "files/mock123"

        # Mock generation response
        mock_provider.generate_json_from_files.return_value = [
            {"name": "Klarg", "role": "Boss", "ac": 16, "hp": 27, "page_number_for_art": 12}
        ]

        yield mock_provider


@pytest.fixture
def parser_service(mock_gemini_client):
    # Temporarily set env var to avoid "API_KEY not found" warning/disablement
    with patch.dict("os.environ", {"GEMINI_API_KEY": "mock_api_key"}):
        service = ModuleParserService()
        return service


def test_upload_pdf_to_gemini(parser_service, mock_gemini_client):
    result = parser_service.upload_pdf_to_gemini("dummy/path.pdf")
    mock_gemini_client.upload_file.assert_called_once_with(file_path="dummy/path.pdf")
    assert result == "files/mock123"


def test_extract_npcs(parser_service, mock_gemini_client):
    mock_file = MagicMock()
    result = parser_service.extract_npcs(mock_file)

    # Assert it parses JSON correctly
    assert len(result) == 1
    assert result[0]["name"] == "Klarg"
    assert result[0]["ac"] == 16
    assert result[0]["page_number_for_art"] == 12


@patch("backend.services.module_parser_service.pdfplumber.open")
def test_extract_image_from_page(mock_pdfplumber_open, parser_service):
    # Mock the pdf
    mock_pdf = MagicMock()
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    # Mock page
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]  # len(pages) = 1

    # Mock image list in page
    mock_img = {
        "x0": 10,
        "top": 10,
        "x1": 100,
        "bottom": 100,
        "width": 90,
        "height": 90,
    }
    mock_page.images = [mock_img]

    # Mock crop and to_image
    mock_cropped = MagicMock()
    mock_page.crop.return_value = mock_cropped

    mock_pil = MagicMock()
    mock_cropped.to_image.return_value.original = mock_pil

    # Run test
    result = parser_service.extract_image_from_page("dummy.pdf", 1, "Klarg")

    # Assert
    assert result is not None
    assert "klarg_1.png" in result
    mock_pil.save.assert_called_once()
