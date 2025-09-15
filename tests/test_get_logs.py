import logging
import time
import unittest

from tidewave.tools.get_logs import get_logs


class TestGetLogs(unittest.TestCase):
    """Test suite for get_logs function using real logging functionality."""

    def setUp(self):
        """Set up test environment by getting a logger to write test messages."""
        self.test_logger = logging.getLogger("test_get_logs")
        self.test_logger.setLevel(logging.DEBUG)

    def test_get_logs_retrieves_written_messages(self):
        """Test that get_logs retrieves messages that were actually logged."""
        test_message = f"TEST_MESSAGE_{int(time.time() * 1000)}"
        self.test_logger.info(test_message)

        result = get_logs(tail=50)
        self.assertIn(test_message, result)

    def test_get_logs_with_tail_parameter(self):
        """Test that tail parameter limits the number of lines returned."""
        timestamp = int(time.time() * 1000)

        for i in range(5):
            message = f"TAIL_TEST_MESSAGE_{timestamp}_{i}"
            self.test_logger.info(message)

        result = get_logs(tail=2)

        lines = result.strip().split("\n")
        self.assertLessEqual(len(lines), 2)

    def test_get_logs_with_grep_filter(self):
        """Test that grep parameter filters log messages correctly."""
        timestamp = int(time.time() * 1000)

        info_message = f"GREP_INFO_TEST_{timestamp}"
        error_message = f"GREP_ERROR_TEST_{timestamp}"
        debug_message = f"GREP_DEBUG_TEST_{timestamp}"

        self.test_logger.info(info_message)
        self.test_logger.error(error_message)
        self.test_logger.debug(debug_message)

        result = get_logs(tail=50, grep="ERROR")

        self.assertIn(error_message, result)
        self.assertNotIn(info_message, result)
        self.assertNotIn(debug_message, result)

    def test_get_logs_case_insensitive_grep(self):
        """Test that grep filtering is case insensitive."""
        timestamp = int(time.time() * 1000)

        message1 = f"case_test_INFO_{timestamp}"
        message2 = f"case_test_info_{timestamp}"

        self.test_logger.info(message1)
        self.test_logger.info(message2)

        result = get_logs(tail=50, grep="INFO")
        self.assertIn(message1, result)
        self.assertIn(message2, result)

    def test_get_logs_with_invalid_regex(self):
        """Test that invalid regex returns appropriate error message."""
        result = get_logs(tail=10, grep="[invalid")
        self.assertIn("Invalid regular expression", result)

    def test_get_logs_with_zero_tail(self):
        """Test that zero tail returns appropriate error message."""
        result = get_logs(tail=0)
        self.assertEqual(result, "Tail parameter must be a positive integer")

    def test_get_logs_with_negative_tail(self):
        """Test that negative tail returns appropriate error message."""
        result = get_logs(tail=-5)
        self.assertEqual(result, "Tail parameter must be a positive integer")

    def test_get_logs_unicode_content(self):
        """Test that unicode characters in log messages are handled correctly."""
        timestamp = int(time.time() * 1000)

        unicode_messages = [
            f"UNICODE_EMOJI_{timestamp}_🚀",
            f"UNICODE_POLISH_{timestamp}_Błąd_połączenia",
            f"UNICODE_CHINESE_{timestamp}_用户已登录",
        ]

        for message in unicode_messages:
            self.test_logger.info(message)

        result = get_logs(tail=50)

        for message in unicode_messages:
            self.assertIn(message, result)

    def test_get_logs_no_matching_grep_pattern(self):
        """Test behavior when grep pattern matches no log entries."""
        # Use a very specific timestamp to ensure uniqueness
        unique_timestamp = f"NOMATCH_{int(time.time() * 1000000)}"
        self.test_logger.info(f"This message contains {unique_timestamp}")

        # Search for something that definitely won't match
        result = get_logs(tail=50, grep="DEFINITELY_NOT_IN_LOGS_XYZ123")
        self.assertIn("No log entries found matching pattern", result)

    def test_get_logs_complex_regex_pattern(self):
        """Test get_logs with complex regular expression patterns."""
        timestamp = int(time.time() * 1000)

        messages = [
            f"REGEX_TEST_2023-01-01_{timestamp}",
            f"REGEX_TEST_2023-01-02_{timestamp}",
            f"REGEX_TEST_2024-01-01_{timestamp}",
        ]

        for message in messages:
            self.test_logger.info(message)

        # Use regex to match only 2023 dates
        result = get_logs(tail=50, grep=r"2023-01-0[12]")

        self.assertIn(f"REGEX_TEST_2023-01-01_{timestamp}", result)
        self.assertIn(f"REGEX_TEST_2023-01-02_{timestamp}", result)
