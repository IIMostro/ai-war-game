from ai_war_game.interfaces.envelope import CommandEnvelope, CommandSource


def test_should_convert_to_command_request(now_utc):
    envelope = CommandEnvelope(
        source=CommandSource.CLI,
        player_id="p1",
        save_id="save-1",
        command_text="进军洛阳",
        timestamp=now_utc,
    )

    request = envelope.to_command_request()

    assert request.save_id == "save-1"
    assert request.player_id == "p1"
    assert request.text == "进军洛阳"
    assert request.issued_at == now_utc


def test_should_reject_blank_command_text(now_utc):
    try:
        CommandEnvelope(
            source=CommandSource.CLI,
            player_id="p1",
            save_id="save-1",
            command_text="   ",
            timestamp=now_utc,
        )
    except ValueError as exc:
        assert str(exc) == "command_text"
    else:
        raise AssertionError("应抛出 ValueError")
