"""models.messages 消息序列查询工具测试：find_message / find_marked_span / find_marked_spans。"""

from ai_rpg.models import (
    AIMessage,
    ChatMessage,
    HumanMessage,
    MessageSpan,
    SystemMessage,
    find_marked_span,
    find_marked_spans,
    find_message,
)


#######################################################################################################################################
def _sample() -> list[ChatMessage]:
    """两个用 loop_id / loop_id_end 标记的区间，中间夹一条无标记消息。"""
    return [
        SystemMessage(content="sys"),
        HumanMessage(content="L1-start", loop_id="L1"),
        AIMessage(content="L1-ai"),
        HumanMessage(content="L1-end", loop_id_end="L1"),
        HumanMessage(content="orphan"),
        HumanMessage(content="L2-start", loop_id="L2"),
        AIMessage(content="L2-ai", loop_id_end="L2"),
    ]


#######################################################################################################################################
def test_find_message_forward_and_reverse() -> None:
    messages = _sample()
    is_ai = lambda m: isinstance(m, AIMessage)  # noqa: E731

    first = find_message(messages, is_ai)
    last = find_message(messages, is_ai, reverse=True)

    assert first is messages[2]
    assert last is messages[6]


#######################################################################################################################################
def test_find_message_no_match_returns_none() -> None:
    assert find_message(_sample(), lambda m: m.content == "missing") is None


#######################################################################################################################################
def test_find_marked_span_with_distinct_end_attr() -> None:
    messages = _sample()
    span = find_marked_span(messages, "loop_id", "L1", end_attr="loop_id_end")

    assert isinstance(span, MessageSpan)
    assert (span.start_index, span.end_index) == (1, 3)
    assert span.messages == messages[1:4]
    assert span.start_message is messages[1]
    assert span.end_message is messages[3]
    assert len(span) == 3


#######################################################################################################################################
def test_find_marked_span_same_attr_marks_first_and_last() -> None:
    """end_attr 缺省等于 start_attr：首尾同一属性标记。"""
    messages: list[ChatMessage] = [
        HumanMessage(content="region-a", tag="R", note="start"),
        AIMessage(content="region-b"),
        HumanMessage(content="region-c", tag="R", note="end"),
    ]
    span = find_marked_span(messages, "tag", "R")

    assert span is not None
    assert (span.start_index, span.end_index) == (0, 2)


#######################################################################################################################################
def test_find_marked_span_falls_back_to_next_marker() -> None:
    """缺失终点标记时，退化为「下一个起点标记前一条」。"""
    messages: list[ChatMessage] = [
        HumanMessage(content="a", loop_id="L1"),
        AIMessage(content="b"),
        HumanMessage(content="c", loop_id="L2"),
        AIMessage(content="d"),
    ]
    span = find_marked_span(messages, "loop_id", "L1", end_attr="loop_id_end")

    assert span is not None
    assert (span.start_index, span.end_index) == (0, 1)


#######################################################################################################################################
def test_find_marked_span_falls_back_to_sequence_end() -> None:
    messages: list[ChatMessage] = [
        HumanMessage(content="a", loop_id="L1"),
        AIMessage(content="b"),
    ]
    span = find_marked_span(messages, "loop_id", "L1", end_attr="loop_id_end")

    assert span is not None
    assert (span.start_index, span.end_index) == (0, 1)


#######################################################################################################################################
def test_find_marked_span_unknown_value_returns_none() -> None:
    assert (
        find_marked_span(_sample(), "loop_id", "NOPE", end_attr="loop_id_end") is None
    )


#######################################################################################################################################
def test_find_marked_span_none_value_returns_none() -> None:
    """value=None 表示「无标记」，直接返回 None，避免把无标记消息误判为区间。"""
    assert find_marked_span(_sample(), "loop_id", None, end_attr="loop_id_end") is None


#######################################################################################################################################
def test_find_marked_spans_returns_all_in_order() -> None:
    spans = find_marked_spans(_sample(), "loop_id", end_attr="loop_id_end")

    assert [s.start_index for s in spans] == [1, 5]
    assert [(s.start_index, s.end_index) for s in spans] == [(1, 3), (5, 6)]
