from pathlib import PurePosixPath

from ptk.domain.layout import Layout, safe


def test_folder_structure_follows_variant_action_step():
    layout = Layout(PurePosixPath("/p"))
    assert (
        str(layout.build_dir("b_us", "build", ("checks", "lint")))
        == "/p/_builds/b_us/build/checks/lint"
    )
    assert (
        str(layout.step_log("b_us", "build", ("checks", "lint")))
        == "/p/_logs/b_us/build/checks/lint.log"
    )
    assert str(layout.run_log("b_us", "build")) == "/p/_logs/b_us/build/run.log"
    assert (
        str(layout.reports_dir("b_us", "test", ("robot",)))
        == "/p/_reports/b_us/test/robot"
    )
    assert str(layout.bin_dir("b_us")) == "/p/_bin/b_us"
    assert str(layout.build_dir(None, "build")) == "/p/_builds/default/build"


def test_names_are_sanitised():
    assert safe("a b/c:d") == "a_b_c_d"
    assert safe("..") == "_"
