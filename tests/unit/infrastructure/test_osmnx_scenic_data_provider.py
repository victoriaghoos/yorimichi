import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

import pytest

from yorimichi.infrastructure.osmnx_scenic_data_provider import OSMnxScenicDataProvider


def test_get_scenic_penalty_raises_if_not_loaded():
    """
    Confirms the defensive check: calling get_scenic_penalty() before load()
    fails loudly and clearly, rather than crashing on a None tree with a
    confusing AttributeError.
    """
    provider = OSMnxScenicDataProvider()

    with pytest.raises(RuntimeError, match="load\\(\\) must be called"):
        provider.get_scenic_penalty(35.0, 135.0)


def test_implements_iscenic_data_provider_interface():
    """Sanity check: OSMnxScenicDataProvider actually satisfies the Domain contract."""
    from yorimichi.domain.repositories import IScenicDataProvider

    provider = OSMnxScenicDataProvider()
    assert isinstance(provider, IScenicDataProvider)