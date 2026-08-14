from typing import List, Optional
from pydantic import BaseModel


class StarPackage(BaseModel):
    """
    Schema for a Telegram Stars top-up package.
    """
    id: str
    title: str
    description: str
    stars_amount: int
    credits_count: int
    icon: str = "🌟"


STAR_PACKAGES: List[StarPackage] = [
    StarPackage(
        id="stars_10",
        title="Starter Package",
        description="10 AI Generation Credits",
        stars_amount=25,
        credits_count=10,
        icon="🌟",
    ),
    StarPackage(
        id="stars_50",
        title="Pro Pack (Popular)",
        description="50 AI Generation Credits",
        stars_amount=100,
        credits_count=50,
        icon="🌟🌟",
    ),
    StarPackage(
        id="stars_150",
        title="Ultra Value Pack",
        description="150 AI Generation Credits",
        stars_amount=250,
        credits_count=150,
        icon="🌟🌟🌟",
    ),
]


def get_package_by_id(package_id: str) -> Optional[StarPackage]:
    for pkg in STAR_PACKAGES:
        if pkg.id == package_id:
            return pkg
    return None
