"""Tests for StackResolver MVP (Issue 2.1)"""

import pytest

from foursouls.engine.stack import Stack, StackResolver
from foursouls.model.effects import AppendMarkerEffect
from foursouls.model.refs import PlayerId


class TestStackItem:
    """Test StackItem construction with targets and metadata"""

    def test_stack_item_basic(self):
        """Test creating a basic StackItem without targets/metadata"""
        stack = Stack()
        item = stack.push(
            controller_id=PlayerId("P1"),
            source="test_source",
            effect=AppendMarkerEffect("A"),
            label="TestLabel",
        )

        assert item.stack_id == 1
        assert item.controller_id == PlayerId("P1")
        assert item.label == "TestLabel"
        assert item.targets == []
        assert item.metadata == {}

    def test_stack_item_with_targets(self):
        """Test creating a StackItem with targets"""
        stack = Stack()
        targets = [PlayerId("P2"), PlayerId("P3")]
        item = stack.push(
            controller_id=PlayerId("P1"),
            source="test_source",
            effect=AppendMarkerEffect("B"),
            label="TargetedAbility",
            targets=targets,
        )

        assert item.targets == targets

    def test_stack_item_with_metadata(self):
        """Test creating a StackItem with metadata"""
        stack = Stack()
        metadata = {"x_value": 5, "revealed_card": "bomb"}
        item = stack.push(
            controller_id=PlayerId("P1"),
            source="card_ability",
            effect=AppendMarkerEffect("C"),
            label="MetadataItem",
            metadata=metadata,
        )

        assert item.metadata == metadata
        assert item.metadata["x_value"] == 5
        assert item.metadata["revealed_card"] == "bomb"

    def test_stack_item_with_targets_and_metadata(self):
        """Test creating a StackItem with both targets and metadata"""
        stack = Stack()
        targets = [PlayerId("P2")]
        metadata = {"damage": 3, "element": "fire"}
        item = stack.push(
            controller_id=PlayerId("P1"),
            source="spell_card",
            effect=AppendMarkerEffect("D"),
            label="DamageSpell",
            targets=targets,
            metadata=metadata,
        )

        assert item.targets == targets
        assert item.metadata == metadata


class TestStackLIFO:
    """Test LIFO (Last In, First Out) behavior"""

    def test_push_pop_order(self):
        """Test that items are popped in LIFO order"""
        stack = Stack()

        item1 = stack.push(
            controller_id=PlayerId("P1"),
            source="source1",
            effect=AppendMarkerEffect("1"),
            label="First",
        )
        item2 = stack.push(
            controller_id=PlayerId("P1"),
            source="source2",
            effect=AppendMarkerEffect("2"),
            label="Second",
        )
        item3 = stack.push(
            controller_id=PlayerId("P1"),
            source="source3",
            effect=AppendMarkerEffect("3"),
            label="Third",
        )

        # Pop in LIFO order
        assert stack.pop() == item3
        assert stack.pop() == item2
        assert stack.pop() == item1
        assert stack.empty()

    def test_stack_ids_increment(self):
        """Test that stack IDs increment sequentially"""
        stack = Stack()

        ids = []
        for i in range(5):
            item = stack.push(
                controller_id=PlayerId("P1"),
                source=f"source{i}",
                effect=AppendMarkerEffect(f"{i}"),
            )
            ids.append(item.stack_id)

        assert ids == [1, 2, 3, 4, 5]


class TestStackResolver:
    """Test StackResolver MVP functionality"""

    def test_resolve_next_empty_stack(self):
        """Test resolve_next on empty stack returns None"""
        stack = Stack()
        resolver = StackResolver(stack)

        assert resolver.resolve_next() is None
        assert not resolver.has_pending_items()

    def test_resolve_next_single_item(self):
        """Test resolving a single item"""
        stack = Stack()
        resolver = StackResolver(stack)

        item = stack.push(
            controller_id=PlayerId("P1"),
            source="test",
            effect=AppendMarkerEffect("A"),
            label="Solo",
        )

        assert resolver.has_pending_items()
        resolved = resolver.resolve_next()
        assert resolved == item
        assert not resolver.has_pending_items()

    def test_resolve_next_lifo_order(self):
        """Test that resolve_next returns items in LIFO order"""
        stack = Stack()
        resolver = StackResolver(stack)

        item1 = stack.push(
            controller_id=PlayerId("P1"),
            source="1",
            effect=AppendMarkerEffect("1"),
            label="First",
        )
        item2 = stack.push(
            controller_id=PlayerId("P1"),
            source="2",
            effect=AppendMarkerEffect("2"),
            label="Second",
        )
        item3 = stack.push(
            controller_id=PlayerId("P1"),
            source="3",
            effect=AppendMarkerEffect("3"),
            label="Third",
        )

        assert resolver.resolve_next() == item3
        assert resolver.resolve_next() == item2
        assert resolver.resolve_next() == item1
        assert resolver.resolve_next() is None


class TestInterruptWindow:
    """Test interrupt window functionality"""

    def test_interrupt_window_closed_by_default(self):
        """Test that interrupt window is closed by default"""
        stack = Stack()
        resolver = StackResolver(stack)

        assert not resolver.interrupt_window_open

    def test_cannot_push_interrupt_when_closed(self):
        """Test that pushing during closed window raises error"""
        stack = Stack()
        resolver = StackResolver(stack)

        with pytest.raises(RuntimeError, match="no interrupt window open"):
            resolver.push_interrupt(
                controller_id=PlayerId("P1"),
                source="test",
                effect=AppendMarkerEffect("X"),
            )

    def test_open_and_close_interrupt_window(self):
        """Test opening and closing interrupt window"""
        stack = Stack()
        resolver = StackResolver(stack)

        resolver.open_interrupt_window()
        assert resolver.interrupt_window_open

        resolver.close_interrupt_window()
        assert not resolver.interrupt_window_open

    def test_push_interrupt_when_open(self):
        """Test pushing an interrupt when window is open"""
        stack = Stack()
        resolver = StackResolver(stack)

        # Push initial item
        item1 = stack.push(
            controller_id=PlayerId("P1"),
            source="main",
            effect=AppendMarkerEffect("Main"),
            label="Main",
        )

        # Open interrupt window and push response
        resolver.open_interrupt_window()
        item2 = resolver.push_interrupt(
            controller_id=PlayerId("P2"),
            source="response",
            effect=AppendMarkerEffect("Response"),
            label="Response",
        )
        resolver.close_interrupt_window()

        # Response should resolve first (LIFO)
        assert resolver.resolve_next() == item2
        assert resolver.resolve_next() == item1

    def test_multiple_interrupts_nested(self):
        """Test multiple interrupts during same window"""
        stack = Stack()
        resolver = StackResolver(stack)

        item1 = stack.push(
            controller_id=PlayerId("P1"),
            source="main",
            effect=AppendMarkerEffect("1"),
            label="Main",
        )

        resolver.open_interrupt_window()

        item2 = resolver.push_interrupt(
            controller_id=PlayerId("P2"),
            source="response1",
            effect=AppendMarkerEffect("2"),
            label="Response1",
        )

        item3 = resolver.push_interrupt(
            controller_id=PlayerId("P3"),
            source="response2",
            effect=AppendMarkerEffect("3"),
            label="Response2",
        )

        resolver.close_interrupt_window()

        # Should resolve in LIFO: 3, 2, 1
        assert resolver.resolve_next() == item3
        assert resolver.resolve_next() == item2
        assert resolver.resolve_next() == item1

    def test_interrupt_with_targets_and_metadata(self):
        """Test pushing interrupt with targets and metadata"""
        stack = Stack()
        resolver = StackResolver(stack)

        resolver.open_interrupt_window()

        targets = [PlayerId("P1")]
        metadata = {"power": 10}

        item = resolver.push_interrupt(
            controller_id=PlayerId("P2"),
            source="ability",
            effect=AppendMarkerEffect("X"),
            label="TargetedResponse",
            targets=targets,
            metadata=metadata,
        )

        resolver.close_interrupt_window()

        assert item.targets == targets
        assert item.metadata == metadata


class TestDeterministicResolution:
    """Test deterministic behavior of stack resolution"""

    def test_deterministic_id_assignment(self):
        """Test that stack IDs are assigned deterministically"""
        stack1 = Stack()
        stack2 = Stack()

        ids1 = []
        ids2 = []

        for i in range(3):
            item1 = stack1.push(
                controller_id=PlayerId("P1"),
                source=f"s{i}",
                effect=AppendMarkerEffect(f"{i}"),
            )
            ids1.append(item1.stack_id)

            item2 = stack2.push(
                controller_id=PlayerId("P1"),
                source=f"s{i}",
                effect=AppendMarkerEffect(f"{i}"),
            )
            ids2.append(item2.stack_id)

        assert ids1 == ids2 == [1, 2, 3]

    def test_resolution_order_deterministic(self):
        """Test that resolution order is deterministic"""
        stack1 = Stack()
        resolver1 = StackResolver(stack1)

        stack2 = Stack()
        resolver2 = StackResolver(stack2)

        # Create identical stacks
        for i in range(5):
            stack1.push(
                controller_id=PlayerId("P1"),
                source=f"s{i}",
                effect=AppendMarkerEffect(f"{i}"),
                label=f"Item{i}",
            )
            stack2.push(
                controller_id=PlayerId("P1"),
                source=f"s{i}",
                effect=AppendMarkerEffect(f"{i}"),
                label=f"Item{i}",
            )

        # Resolve in same order and verify labels match
        labels1 = []
        labels2 = []

        while True:
            item1 = resolver1.resolve_next()
            item2 = resolver2.resolve_next()

            if item1 is None and item2 is None:
                break

            labels1.append(item1.label if item1 else None)
            labels2.append(item2.label if item2 else None)

        assert labels1 == labels2
        # Should be in reverse order (LIFO)
        assert labels1 == ["Item4", "Item3", "Item2", "Item1", "Item0"]
