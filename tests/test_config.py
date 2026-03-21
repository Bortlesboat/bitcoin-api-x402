"""Tests for x402 configuration."""

import os
import pytest

from bitcoin_api_x402.config import X402Config, load_config


class TestX402Config:
    """Test configuration dataclass."""

    def test_defaults(self):
        cfg = X402Config()
        assert cfg.pay_to_address == ""
        assert cfg.network == "eip155:8453"
        assert cfg.facilitator_url == "https://x402.org/facilitator"
        assert cfg.scheme == "exact"

    def test_validate_missing_address(self):
        cfg = X402Config()
        with pytest.raises(ValueError, match="X402_PAY_TO_ADDRESS is required"):
            cfg.validate()

    def test_validate_invalid_address_format(self):
        cfg = X402Config(pay_to_address="not-an-address")
        with pytest.raises(ValueError, match="valid EVM address"):
            cfg.validate()

    def test_validate_short_address(self):
        cfg = X402Config(pay_to_address="0x1234")
        with pytest.raises(ValueError, match="valid EVM address"):
            cfg.validate()

    def test_validate_valid_address(self):
        cfg = X402Config(pay_to_address="0xAbCdEf0123456789AbCdEf0123456789AbCdEf01")
        cfg.validate()  # Should not raise

    def test_custom_values(self):
        cfg = X402Config(
            pay_to_address="0xAbCdEf0123456789AbCdEf0123456789AbCdEf01",
            network="eip155:1",
            facilitator_url="https://custom.facilitator.com",
            scheme="flexible",
        )
        assert cfg.network == "eip155:1"
        assert cfg.facilitator_url == "https://custom.facilitator.com"
        assert cfg.scheme == "flexible"


class TestLoadConfig:
    """Test loading config from environment variables."""

    def test_load_defaults(self, monkeypatch):
        for key in ["X402_PAY_TO_ADDRESS", "X402_NETWORK", "X402_FACILITATOR_URL",
                     "X402_SCHEME"]:
            monkeypatch.delenv(key, raising=False)

        cfg = load_config()
        assert cfg.pay_to_address == ""
        assert cfg.network == "eip155:8453"

    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("X402_PAY_TO_ADDRESS", "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01")
        monkeypatch.setenv("X402_NETWORK", "eip155:1")
        monkeypatch.setenv("X402_FACILITATOR_URL", "https://test.facilitator.com")
        monkeypatch.setenv("X402_SCHEME", "flexible")

        cfg = load_config()
        assert cfg.pay_to_address == "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
        assert cfg.network == "eip155:1"
        assert cfg.facilitator_url == "https://test.facilitator.com"
        assert cfg.scheme == "flexible"

    def test_partial_env(self, monkeypatch):
        monkeypatch.setenv("X402_PAY_TO_ADDRESS", "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01")
        for key in ["X402_NETWORK", "X402_FACILITATOR_URL", "X402_SCHEME"]:
            monkeypatch.delenv(key, raising=False)

        cfg = load_config()
        assert cfg.pay_to_address == "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
        assert cfg.network == "eip155:8453"  # default
