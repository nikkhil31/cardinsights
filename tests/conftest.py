import pytest


def pytest_addoption(parser):
    parser.addoption("--pdf", action="store", default=None, help="Path to a real SBI statement PDF")


@pytest.fixture
def pdf_path(request):
    p = request.config.getoption("--pdf")
    if not p:
        pytest.skip("pass --pdf=/path/to/statement.pdf to run")
    return p
