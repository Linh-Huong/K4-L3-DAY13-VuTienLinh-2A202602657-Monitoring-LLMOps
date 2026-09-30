from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    cccd_samples = (
        "001201012345",
        "079203004567",
        "038099001234",
    )
    for cccd in cccd_samples:
        out = scrub_text(f"So CCCD cua toi la: {cccd}")
        assert cccd not in out
        assert "REDACTED_CCCD" in out


def test_scrub_credit_card() -> None:
    card_samples = (
        "4111222233334444",
        "4111 2222 3333 4444",
        "4111-2222-3333-4444",
        "5500 0000 0000 0004",
    )
    for card in card_samples:
        out = scrub_text(f"Thanh toan qua the: {card}")
        assert card not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_scrub_passport() -> None:
    passport_samples = (
        "B1234567",
        "C9876543",
        "P12345678",
    )
    for passport in passport_samples:
        out = scrub_text(f"So ho chieu: {passport}")
        assert passport not in out
        assert "REDACTED_PASSPORT" in out


def test_scrub_multiple_pii() -> None:
    raw_message = (
        "Khach hang Nguyen Van A, email: a.nguyen@example.com, "
        "SDT: 0912345678, CCCD: 001203004567, Card: 4111-2222-3333-4444."
    )
    safe = scrub_text(raw_message)
    assert "a.nguyen@example.com" not in safe
    assert "0912345678" not in safe
    assert "001203004567" not in safe
    assert "4111-2222-3333-4444" not in safe
    assert "REDACTED_EMAIL" in safe
    assert "REDACTED_PHONE_VN" in safe
    assert "REDACTED_CCCD" in safe
    assert "REDACTED_CREDIT_CARD" in safe
