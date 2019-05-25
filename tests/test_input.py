import pytest
import urwid
from pingtop import global_input


def test_global_input():
    global current_sort_column
    with pytest.raises(urwid.main_loop.ExitMainLoop):
        global_input("q")
