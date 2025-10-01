import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from gemini_client import GeminiClient


@pytest.fixture
def mock_genai():
    """Mock Google Generative AI module."""
    with patch('gemini_client.genai') as mock:
        mock_model = Mock()
        mock_model.generate_content = Mock()
        mock.GenerativeModel.return_value = mock_model
        yield mock


@pytest.fixture
def gemini_client(mock_genai):
    """Gemini client instance for testing."""
    return GeminiClient(api_key="test-api-key")


@pytest.fixture
def sample_html():
    """Sample HTML content for testing."""
    return """
    <div class="job-posting">
        <h1>Test Software Engineer</h1>
        <div class="company">Test Company</div>
        <div class="location">Test Location</div>
        <div class="description">
            Test job description with sufficient content for testing.
        </div>
        <div class="salary">$50,000 - $100,000</div>
        <div class="type">Full-time</div>
        <div class="level">Mid-level</div>
        <a href="https://example.com/apply" class="apply-btn">Apply Now</a>
    </div>
    """


@pytest.fixture
def expected_job_data():
    """Expected parsed job data."""
    return {
        "job_title": "Test Software Engineer",
        "company_name": "Test Company",
        "job_location": "Test Location",
        "job_description": "Test job description with sufficient content for testing.",
        "salary_range": "$50,000 - $100,000",
        "job_type": "Full-time",
        "experience_level": "Mid-level",
        "skills_required": ["Test Skill 1", "Test Skill 2"],
        "remote_option": False,
        "application_url": "https://example.com/apply",
        "posted_date": None,
        "confidence": 0.85
    }


@pytest.mark.asyncio
class TestGeminiClient:
    """Test cases for Gemini API client."""

    def test_initialization_with_api_key(self, mock_genai):
        """Test Gemini client initialization with API key."""
        client = GeminiClient(api_key="test-key")
        
        assert client.api_key == "test-key"
        assert client.available is True
        mock_genai.configure.assert_called_once_with(api_key="test-key")
        mock_genai.GenerativeModel.assert_called_once_with('gemini-1.5-flash')

    def test_initialization_without_api_key(self, mock_genai):
        """Test Gemini client initialization without API key."""
        with patch('gemini_client.settings') as mock_settings:
            mock_settings.GEMINI_API_KEY = None
            client = GeminiClient()
            
            assert client.available is False
            mock_genai.configure.assert_not_called()

    def test_initialization_with_exception(self, mock_genai):
        """Test Gemini client initialization with exception."""
        mock_genai.configure.side_effect = Exception("API Error")
        
        client = GeminiClient(api_key="test-key")
        
        assert client.available is False

    async def test_parse_job_data_success(self, gemini_client, sample_html, expected_job_data, mock_genai):
        """Test successful job data parsing."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.text = json.dumps(expected_job_data)
        mock_genai.GenerativeModel.return_value.generate_content.return_value = mock_response
        
        result = await gemini_client.parse_job_data(sample_html)
        
        assert result == expected_job_data
        assert result["confidence"] == 0.85
        mock_genai.GenerativeModel.return_value.generate_content.assert_called_once()

    async def test_parse_job_data_with_field_mapping(self, gemini_client, sample_html, mock_genai):
        """Test job data parsing with custom field mapping."""
        field_mapping = {
            "title_selector": "h1",
            "company_selector": ".company",
            "location_selector": ".location"
        }
        
        mock_response = Mock()
        mock_response.text = json.dumps({"job_title": "Engineer", "confidence": 0.8})
        mock_genai.GenerativeModel.return_value.generate_content.return_value = mock_response
        
        result = await gemini_client.parse_job_data(sample_html, field_mapping)
        
        assert result["job_title"] == "Engineer"
        # Verify field mapping was included in prompt
        call_args = mock_genai.GenerativeModel.return_value.generate_content.call_args[0][0]
        assert "title_selector" in call_args

    async def test_parse_job_data_client_unavailable(self, mock_genai):
        """Test parsing when client is unavailable."""
        client = GeminiClient()
        client.available = False
        
        with pytest.raises(Exception, match="Gemini client not available"):
            await client.parse_job_data("<html>test</html>")

    async def test_parse_job_data_invalid_json_response(self, gemini_client, sample_html, mock_genai):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.text = "Invalid JSON response"
        mock_genai.GenerativeModel.return_value.generate_content.return_value = mock_response
        
        with pytest.raises(Exception, match="Invalid JSON response from Gemini"):
            await gemini_client.parse_job_data(sample_html)

    async def test_parse_job_data_api_error(self, gemini_client, sample_html, mock_genai):
        """Test handling of API errors."""
        mock_genai.GenerativeModel.return_value.generate_content.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            await gemini_client.parse_job_data(sample_html)

    def test_clean_html_with_beautifulsoup(self, gemini_client):
        """Test HTML cleaning with BeautifulSoup."""
        html_content = """
        <html>
            <head><title>Test Job</title></head>
            <body>
                <script>alert('test');</script>
                <style>body { color: red; }</style>
                <div>Test Engineer</div>
                <p>Test Company</p>
            </body>
        </html>
        """
        
        with patch('bs4.BeautifulSoup') as mock_bs:
            # Mock the soup object and its methods
            mock_soup = Mock()
            mock_soup.get_text.return_value = "Test Engineer Test Company"
            
            # Mock the script/style removal
            mock_soup.return_value = []
            mock_bs.return_value = mock_soup
            
            result = gemini_client._clean_html(html_content)
            
            assert "Test Engineer Test Company" in result
            mock_bs.assert_called_once_with(html_content, 'html.parser')

    def test_clean_html_fallback(self, gemini_client):
        """Test HTML cleaning fallback when BeautifulSoup fails."""
        html_content = "<div>Test content</div>"
        
        with patch('bs4.BeautifulSoup', side_effect=Exception("Import error")):
            result = gemini_client._clean_html(html_content)
            
            assert result == html_content

    def test_calculate_confidence_high_score(self, gemini_client):
        """Test confidence calculation for complete data."""
        complete_data = {
            "job_title": "Test Engineer",
            "company_name": "Test Company",
            "job_location": "Test Location",
            "job_description": "Test job description",
            "salary_range": "$50k-$100k",
            "job_type": "Full-time",
            "experience_level": "Mid-level"
        }
        
        confidence = gemini_client._calculate_confidence(complete_data)
        
        assert confidence == 1.0

    def test_calculate_confidence_partial_score(self, gemini_client):
        """Test confidence calculation for partial data."""
        partial_data = {
            "job_title": "Test Engineer",
            "company_name": "Test Company",
            "job_location": "Test Location"
            # Missing optional fields
        }
        
        confidence = gemini_client._calculate_confidence(partial_data)
        
        assert 0.7 <= confidence < 1.0  # Should have required fields (0.7) but no optional fields

    def test_calculate_confidence_low_score(self, gemini_client):
        """Test confidence calculation for incomplete data."""
        incomplete_data = {
            "job_title": "Test Engineer"
            # Missing required fields
        }
        
        confidence = gemini_client._calculate_confidence(incomplete_data)
        
        assert confidence < 0.7

    async def test_test_connection_success(self, gemini_client, mock_genai):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.text = json.dumps({"test": "success"})
        mock_genai.GenerativeModel.return_value.generate_content.return_value = mock_response
        
        result = await gemini_client.test_connection()
        
        assert result is True

    async def test_test_connection_failure(self, gemini_client, mock_genai):
        """Test failed connection test."""
        mock_genai.GenerativeModel.return_value.generate_content.side_effect = Exception("Connection error")
        
        result = await gemini_client.test_connection()
        
        assert result is False

    async def test_test_connection_unavailable(self, mock_genai):
        """Test connection test when client is unavailable."""
        client = GeminiClient()
        client.available = False
        
        result = await client.test_connection()
        
        assert result is False